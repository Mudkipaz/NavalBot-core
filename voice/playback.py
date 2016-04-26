"""
=================================

This file is part of NavalBot.
Copyright (C) 2016 Isaac Dickinson

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
import functools
from math import trunc

import youtube_dl

import discord
import util
from cmds import command
from voice.stores import voice_params, voice_locks

# Get loop
from voice.voice_util import find_voice_channel

loop = asyncio.get_event_loop()

async def _await_queue(server_id: str):
    # Awaits new songs on the queue.
    while True:
        queue = voice_params[server_id]["queue"]
        if not queue:
            return
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


async def _oauth2_play_youtube(
        client: discord.Client,
        message: discord.Message,
        voice_client: discord.VoiceClient,
        voice_channel: discord.Channel,
        download_url: str,
        info: dict
):
    """
    Co-routine that is used for the message queue.

    Parameters:
        client:
            The client instance.

        message:
            The message object used to queue, with ?play.

        voice_client:
            The voice client to use to play with.

        voice_channel:
            The channel to join.

        info:
            The youtube_dl information dict.
    """
    # Fix the voice client if we need to.
    vc = await _fix_voice(client, voice_client, voice_channel)
    player = vc.create_ffmpeg_player(download_url)
    voice_params[message.server.id]["playing"] = True
    voice_params[message.server.id]["title"] = info.get("title", "???")
    voice_params[message.server.id]["player"] = player
    voice_params[message.server.id]["progress"] = 0
    voice_params[message.server.id]["duration"] = info.get("duration")
    await client.send_message(message.channel, ":heavy_check_mark: Now playing: `{}`".format(info.get("title", "???")))
    assert isinstance(player, discord.voice_client.ProcessPlayer)
    # Start playing
    player.start()
    # Check ever 0.5 seconds if we're done or not.
    # 0.5 is non-noticable delay, but doesn't kill the CPU.
    while True:
        if player.is_done():
            break
        else:
            if player.is_playing():
                # TODO: Use time.time instead
                voice_params[message.server.id]["progress"] += 0.5
            await asyncio.sleep(0.5)
    # Reset everything after it's done.
    voice_params[message.server.id]["playing"] = False
    voice_params[message.server.id]["title"] = ""
    voice_params[message.server.id]["player"] = None
    voice_params[message.server.id]["progress"] = None
    voice_params[message.server.id]["duration"] = None


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
    # progress/duration
    m, s = divmod(voice_params[message.server.id]["progress"], 60)
    if voice_params[message.server.id]["duration"]:
        dm, ds = divmod(voice_params[message.server.id]["duration"], 60)
    else:
        dm, ds = 0, 0
    playing = "" if player.is_playing() else "`[PAUSED]`"
    print(m, s, dm, ds)
    d_str = "[{:02d}:{:02d} / {:02d}:{:02d}]".format(trunc(m), trunc(s), trunc(dm), trunc(ds))
    await client.send_message(message.channel,
                              content="Currently playing: `{}` `{}` {}".format(title, d_str, playing))


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


@command("pause")
async def pause_vid(client: discord.Client, message: discord.Message):
    """
    Pauses the currently playing track. Use ?resume to continue playing.
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

    assert isinstance(player, discord.voice_client.ProcessPlayer)
    if player.is_playing():
        player.pause()
    else:
        await client.send_message(message.channel, ":x: Track is already paused.")
        return
    await client.send_message(message.channel, ":heavy_check_mark: Paused current track.")


@command("resume")
async def resume(client: discord.Client, message: discord.Message):
    """
    Resumes a paused track.
    """
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

    if player.is_playing():
        await client.send_message(message.channel, ":x: Track is already playing.")
        return
    else:
        player.resume()
    await client.send_message(message.channel, ":heavy_check_mark: Resumed playback.")


@command("play")
@command("playyt")
@command("playyoutube")
@util.enforce_args(1, ":x: You must pass a video!")
async def play_youtube(client: discord.Client, message: discord.Message, args: list):
    """
    Plays a video from any valid streaming source that `youtube-dl` can download from.
    This includes things such as YouTube (obviously) and SoundCloud.
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

    if message.server.id not in voice_locks:
        voice_locks[message.server.id] = asyncio.Lock()

    vidname = ' '.join(args[0:])

    if 'list' in vidname or 'playlist' in vidname:
        await client.send_message(message.channel, ":warning: If this is a playlist, it may take a long time to "
                                                   "download.")

    # Do the same as play_file, but with a youtube streamer.
    # Play it via ffmpeg.

    # Get the max queue size
    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    ydl = youtube_dl.YoutubeDL({"format": 'webm[abr>0]/bestaudio/best', "ignoreerrors": True, "playlistend": qsize,
                                "default_search": "ytsearch", "source_address": "0.0.0.0"})
    func = functools.partial(ydl.extract_info, vidname, download=False)
    # Set the download lock.
    lock = voice_locks.get(message.server.id)
    assert isinstance(lock, asyncio.Lock)
    try:
        if lock.locked():
            await client.send_message(message.channel, ":hourglass: Something else is downloading. Waiting for that "
                                                       "to finish.")
        await lock.acquire()
        await client.send_message(message.channel, ":hourglass: Downloading video information...")
        info = await loop.run_in_executor(None, func)
        lock.release()
    except Exception as e:
        await client.send_message(message.channel, ":no_entry: Something went horribly wrong. Error: {}".format(e))
        lock.release()
        return

    if not info:
        await client.send_message(message.channel, ":no_entry: Something went horribly wrong. Could not get video "
                                                   "information.")
        return

    # Check for a playlist.
    if "entries" in info and len(info['entries']) > 1:
        # Playlist!
        is_playlist = True
        pl_data = info['entries']
    else:
        # We might be a single video inside a playlist. Get that out.
        if 'entries' in info:
            info = info['entries'][0]
        is_playlist = False
        title = info.get('title')
        download_url = info['url']

        pl_data = None

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
        voice_params[message.server.id]["queue"] = asyncio.Queue(maxsize=qsize)

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
                return

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
            queue.put_nowait((_oauth2_play_youtube(
                client, message,
                voice_client, voice_channel,
                download_url, info

            ), info))
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
            # If the playlist is bigger than the queue, stop it from putting onto the queue.
            if num == qsize:
                await client.send_message(
                    message.channel,
                    ":grey_exclamation: Cannot play more than {} "
                    "songs from a playlist. Skipping the rest.".format(qsize)
                )
                break
            # Add it to the queue.
            try:
                queue.put_nowait((_oauth2_play_youtube(
                    client, message,
                    voice_client, voice_channel,
                    download_url, info
                ), item))
            except asyncio.QueueFull:
                await client.send_message(
                    message.channel, ":no_entry: There are too many songs on the queue. "
                                     "Limiting playlist to {}.".format(num)
                )
                break

        # See above, to see justification of num being -1.
        if num == -1:
            await client.send_message(
                message.channel,
                ":x: Search returned nothing, or playlist errored."
            )
            return

        await client.send_message(message.channel, ":heavy_check_mark: Added {} track(s) to queue.".format(num + 1))

    # Create a new task, if applicable.
    if 'task' not in voice_params[message.server.id] or voice_params[message.server.id]["task"].cancelled():
        # Create the new task.
        task = loop.create_task(_await_queue(message.server.id))
        voice_params[message.server.id]["task"] = task
