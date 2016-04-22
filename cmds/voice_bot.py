"""
=================================

This file is part of NavalBot.
Copyright (C) 2016 Isaac Dickinson
Copyright (C) 2016 Nils Theres

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>

=================================
"""
import asyncio
import random

import discord
import functools
import youtube_dl

import util

from cmds import command

loop = asyncio.get_event_loop()

voice_params = {}


async def find_voice_channel(server: discord.Server):
    # Search for a voice channel called 'Music' or 'NavalBot'.
    for channel in server.channels:
        assert isinstance(channel, discord.Channel)
        if not channel.type == discord.ChannelType.voice:
            continue
        # Check the name.
        if channel.name.lower() in ['music', 'navalbot']:
            chan = channel
            break
    else:
        return None
    return chan


async def _await_queue(server_id: str):
    # Awaits new songs on the queue.
    while True:
        queue = voice_params[server_id]["queue"]
        try:
            items = await queue.get()
        except RuntimeError:
            return
        # Place the current coroutine on the voice_params
        voice_params[server_id]["curr_coro"] = items[0]
        # Await the playing coroutine.
        await items[0]


async def _fix_voice(client: discord.Client, vc: discord.VoiceClient, channel: discord.Channel):
    """
    Fixes a voice client.

    If it is invalid, it destroys it and creates a new one.
    """
    if not hasattr(vc, 'ws') or not vc.ws.open or not vc.is_connected():
        # Fix it.
        try:
            await asyncio.wait_for(vc.disconnect(), timeout=1)
        except Exception:
            # Tried to send on a closed web socket. We can safely ignore this
            pass
        del client.voice[channel.server.id]
        new_vc = await client.join_voice_channel(channel)
        return new_vc
    else:
        return vc


@command("again")
async def again(client: discord.Client, message: discord.Message):
    """
    Adds this item to the queue again.
    """

    # Standard checks.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    # Get the item from the queue.
    i = voice_params[message.server.id].get("curr_coro")
    if not i:
        await client.send_message(message.channel, content=":x: Nothing to play again.")
        return

    # Add it to the queue.
    try:
        queue = voice_params[message.server.id]["queue"]
        title = voice_params[message.server.id]["title"]
        assert isinstance(queue, asyncio.Queue)
        queue.put_nowait((i, title))
    except KeyError:
        await client.send_message(message.channel, content=":x: No queue to place item on.")
    except asyncio.QueueFull:
        await client.send_message(message.channel, content=":x: Queue is full.")
    else:
        await client.send_message(message.channel, content=":heavy_check_mark: Repeating track.")


@command("shuffle")
@util.with_permission("Bot Commander", "Voice", "Admin")
async def shuffle(client: discord.Client, message: discord.Message):
    """
    Shuffles the queue.
    """
    # Standard checks.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get("queue")
    if not queue:
        await client.send_message(message.channel, ":x: There is no queue for this server.")
        # this never happens
    new_queue = asyncio.Queue(maxsize=100)
    assert isinstance(queue, asyncio.Queue)
    deq = list(queue._queue)

    # shuffle deq
    random.shuffle(deq)

    # append all items
    for i in deq:
        try:
            new_queue.put_nowait(i)
        except asyncio.QueueFull:
            # wat
            break

    # set the new queue
    voice_params[message.server.id]["queue"] = new_queue

    await client.send_message(message.channel, ":heavy_check_mark: Shuffled queue.")


@command("reset")
@util.with_permission("Bot Commander", "Voice", "Admin")
async def reset_voice(client: discord.Client, message: discord.Message):
    """
    Resets NavalBot's voice.

    This stops all currently playing songs in this server, and destroys the queue.
    """
    # Load the server params.
    if message.server.id in voice_params:
        s_p = voice_params[message.server.id]
        # Reset the task.
        task = s_p.get("task")
        if task:
            assert isinstance(task, asyncio.Task)
            # Cancel the task.
            task.cancel()
            del s_p["task"]
        # Empty the queue.
        if 'queue' in s_p:
            del s_p['queue']
        s_p['playing'] = False
        player = s_p.get("player")
        if player:
            assert isinstance(player, discord.voice_client.StreamPlayer)
            player.stop()
            del s_p["player"]
        # Set the dictionary again.
        del voice_params[message.server.id]
    # Disconnect from voice
    if message.server.id in client.voice:
        vc = client.voice[message.server.id]
        if hasattr(vc, 'ws'):
            if vc.ws.open and vc.is_connected():
                await client.voice[message.server.id].disconnect()
        del client.voice[message.server.id]

    await client.send_message(message.channel, ":heavy_check_mark: Reset voice parameters.")


@command("np")
@command("nowplaying")
async def np(client: discord.Client, message: discord.Message):
    # Get the current player instance.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    playing = voice_params[message.server.id].get("playing")
    if not playing:
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    player = voice_params[message.server.id].get("player")
    if not player:
        # ???
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    title = voice_params[message.server.id].get("title", "??? Internal error")
    await client.send_message(message.channel, content="Currently playing: `{}`".format(title))


@command("queued")
@command("queue")
async def get_queued_vids(client: discord.Client, message: discord.Message):
    # STILL HORRIBLE

    # Get the current player instance.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get('queue', [])
    if queue:
        queue = queue._queue

    s = "**Currently queued:**"
    if len(queue) == 0:
        s += "\n`Nothing is queued.`"
        await client.send_message(message.channel, s)
        return

    for item in range(0, len(queue) if len(queue) < 10 else 10):
        i = queue[item]
        title = i[1].get('title')
        s += "\n{}. `{}`".format(item + 1, title)

    if len(queue) > 10:
        s += "\n(Omitted {} queued items.)".format(len(queue) - 10)
    await client.send_message(message.channel, s)


@command("skip")
@command("stop")
@util.with_permission("Bot Commander", "Voice", "Admin")
async def stop_vid(client: discord.Client, message: discord.Message):
    """
    Stops the current track being played on the server.
    You must have the Voice or Bot Commander role to use this command.
    """
    # Get the current player instance.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    playing = voice_params[message.server.id].get("playing")
    if not playing:
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    player = voice_params[message.server.id].get("player")
    if not player:
        # ???
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    # Finally, stop the player.
    player.stop()
    await client.send_message(message.channel, content=":heavy_check_mark: Stopped current song.")


@command("play")
@command("playyt")
@command("playyoutube")
@util.enforce_args(1, ":x: You must pass a video!")
async def play_youtube(client: discord.Client, message: discord.Message, args: list):
    """
    Plays a video from any valid streaming source that `youtube-dl` can download from.
    This included things such as YouTube (obviously) and SoundCloud.
    You must have the Voice or Bot Commander role to use this command.
    Use ?stop or ?skip to skip a song, ?queue to see the current queue of songs, ?np to see the currently playing
    track, and ?reset to fix the queue.
    """
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    voice_channel = await find_voice_channel(message.server)
    if not voice_channel:
        await client.send_message(message.channel, content=":x: Cannot find voice channel for playing music! (channel "
                                                           "must be named `Music` or `NavalBot`.)")
        return

    vidname = ' '.join(args[0:])

    if 'list' in vidname or 'playlist' in vidname:
        await client.send_message(message.channel, ":warning: If this is a playlist, it may take a long time to "
                                                   "download.")

    # Do the same as play_file, but with a youtube streamer.
    # Play it via ffmpeg.

    ydl = youtube_dl.YoutubeDL({"format": 'webm[abr>0]/bestaudio/best', "ignoreerrors": True, "playlistend": 99,
                                "default_search": "ytsearch"})
    func = functools.partial(ydl.extract_info, vidname, download=False)
    try:
        info = await loop.run_in_executor(None, func)
    except Exception as e:
        await client.send_message(message.channel, ":no_entry: Something went horribly wrong. Error: {}".format(e))
        return

    if not info:
        await client.send_message(message.channel, ":no_entry: Something went horribly wrong. Could not get video "
                                                   "information.")
        return

    if "entries" in info:
        # Playlist!
        is_playlist = True
        pl_data = info['entries']
    else:
        is_playlist = False
        title = info.get('title')
        download_url = info['url']

        pl_data = None

        duration = info.get('duration')
        if (duration and int(duration) > (60 * 10)) and not util.has_permissions(
                message.author, {"Bot Commander", "Voice", "Admin"}):
            await client.send_message(message.channel, ":x: Videos are limited to a maximum of 10 minutes.")
            return

    # Contrary to the name, this file DOES use queues.
    # However, unlike voice_queue, OAuth2 bots can run on multiple voice servers at once.
    # This means multiple queues can be used per bot.

    # What this coroutine does:
    # 1. Checks for the queue of a specific server.
    #    If it doesn't find one, it creates a new one. It then opens a new voice connection to the server.
    # 2. Places the coroutine on the server-specific queue.
    # 3. Checks to see if there is a looping task running for fetching new songs off of the queue for that server.
    #    If there isn't, it will create a new one, store it, and so on.

    # Check for the queue.
    if message.server.id not in voice_params:
        # Nope!
        voice_params[message.server.id] = {}
    if 'queue' not in voice_params[message.server.id]:
        voice_params[message.server.id]["queue"] = asyncio.Queue(maxsize=99)

    queue = voice_params[message.server.id]["queue"]

    # Get the voice client.
    if message.server.id not in client.voice:
        try:
            voice_client = await client.join_voice_channel(channel=voice_channel)
        except discord.ClientException:
            await client.send_message(message.channel, ":x: Timed out trying to connect to server. Try ?reset")
            return
    else:
        voice_client = client.voice[message.server.id]
        assert isinstance(voice_client, discord.VoiceClient)
        if not voice_client.is_connected():
            # Re-create the voice client.
            try:
                voice_client = await client.join_voice_channel(channel=voice_channel)
                client.voice[message.server.id] = voice_client
            except discord.ClientException:
                await client.send_message(message.channel, ":x: Error happened on connecting to voice.")

    async def _oauth2_play_youtube(d, t):
        # Fix the voice client if we need to.
        vc = await _fix_voice(client, voice_client, voice_channel)
        player = vc.create_ffmpeg_player(d)
        voice_params[message.server.id]["playing"] = True
        voice_params[message.server.id]["title"] = t
        voice_params[message.server.id]["player"] = player
        await client.send_message(message.channel, ":heavy_check_mark: Now playing: `{}`".format(t))
        assert isinstance(player, discord.voice_client.ProcessPlayer)
        # Start playing
        player.start()
        # Check ever 0.5 seconds if we're done or not.
        # 0.5 is non-noticable delay, but doesn't kill the CPU.
        while True:
            if player.is_done():
                break
            else:
                await asyncio.sleep(0.5)
        # Reset everything after it's done.
        voice_params[message.server.id]["playing"] = False
        voice_params[message.server.id]["title"] = ""
        voice_params[message.server.id]["player"] = None

    # Get the number of songs on the queue.
    items = queue.qsize()

    # Switch based on if we're a playlist.
    if not is_playlist:
        # Send a helpful error message.
        if items != 0:
            await client.send_message(message.channel,
                                      ":heavy_check_mark: You are number {} in the queue.".format(items + 1))
        else:
            await client.send_message(message.channel, ":heavy_check_mark: You are next in the queue.")

        try:
            queue.put_nowait((_oauth2_play_youtube(download_url, title), info))
        except asyncio.QueueFull:
            await client.send_message(message.channel,
                                      ":no_entry: There are too many songs on the queue. Cannot start "
                                      "playing.")

    else:
        # If it's pretending to be a playlist, but there's nothing there, set num to -1 to prevent UnboundLocalError
        if not pl_data:
            num = -1
        # Loop over each item from the playlist.
        for num, item in enumerate(pl_data):
            if not item:
                continue
            if num == 99:
                await client.send_message(
                    message.channel,
                    ":grey_exclamation: Cannot play more than 99 songs from a playlist. Skipping the rest."
                )
                break
            # Add it to the queue.
            try:
                queue.put_nowait((_oauth2_play_youtube(item.get("url"), item.get("title", "???")), item))
            except asyncio.QueueFull:
                await client.send_message(
                    message.channel, ":no_entry: There are too many songs on the queue. Limiting playlist."
                )
                return

        # See above, to see justification of num being -1.
        if num == -1:
            await client.send_message(
                message.channel,
                ":x: Search returned nothing, or playlist errored."
            )
            return

        await client.send_message(message.channel, ":heavy_check_mark: Added {} track(s) to queue.".format(num + 1))

    # Create a new task, if applicable.
    if 'task' not in voice_params[message.server.id]:
        # Create the new task.
        task = loop.create_task(_await_queue(message.server.id))
        voice_params[message.server.id]["task"] = task
