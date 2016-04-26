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
import functools
import logging

import discord
import youtube_dl
from discord.voice_client import StreamPlayer, VoiceClient

import cmds
import util
from cmds import command

voice_params = {"playing": False, "player": None, "file": "", "in_server": None}

loop = asyncio.get_event_loop()

# Create a song queue.
queue = asyncio.Queue(maxsize=100)

logger = logging.getLogger("NavalBot::Voice")


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


async def play_music_from_queue():
    # Loads music from the queue and plays it.
    while True:
        try:
            music_coro = await queue.get()
        except RuntimeError:
            # FUcking asyncio
            return
        # Await the coroutine
        await music_coro[0]


@command("queue")
async def get_queue(client: discord.Client, message: discord.Message):
    # TERRIBLE
    s = "**Currently queued:**"
    if len(queue._queue) == 0:
        s += "\n`Nothing is queued.`"
        await client.send_message(message.channel, s)
        return
    for item in range(0, len(queue._queue)):
        i = queue._queue[item]
        title = i[1]
        s += "\n{}. `{}` - on server `{}`".format(item + 1, title, i[2])
    await client.send_message(message.channel, s)


@command("nowplaying")
@command("np")
async def nowplaying(client: discord.Client, message: discord.Message):
    """
    Displays the currently playing audio.
    """
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if not client.is_voice_connected():
        await client.send_message(message.channel, ":x: I am not in voice currently!")
        return
    if not voice_params["playing"]:
        await client.send_message(message.channel, "No song is currently playing.")
        return
    # Get the player parameter
    player = voice_params["player"]
    assert isinstance(player, StreamPlayer)
    if player.is_done():
        await client.send_message(message.channel, "No song is currently playing.")
        return

    # Return the currently playing song.
    await client.send_message(message.channel, "Currently playing: `{}` in server `{}`."
                              .format(voice_params["file"],
                                      discord.utils.get(client.servers, id=voice_params["in_server"])))


@command("stop")
@util.with_permission("Bot Commander", "Voice")
async def stop(client: discord.Client, message: discord.Message):
    """
    Stops the currently playing audio.
    You must have the Voice or Bot Commander role to use this command.
    """
    # Stop playing.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if not client.is_voice_connected():
        await client.send_message(message.channel, ":x: I am not in voice currently!")
        return

    assert isinstance(message.server, discord.Server)
    if message.server.id != voice_params["in_server"]:
        await client.send_message(message.channel, content=":x: Cannot cancel playing from different server!")
        return

    # Get the voice client.
    voice_client = client.voice
    assert isinstance(voice_client, VoiceClient)
    # Check if we're playing something
    if voice_params["playing"]:
        # Get the player.
        player = voice_params["player"]
        assert isinstance(player, StreamPlayer)
        # Stop it.
        player.stop()
        voice_params["playing"] = False

    await client.send_message(message.channel, ":heavy_check_mark: Stopped playing.")


@command("play")
@command("playyt")
@command("playyoutube")
@util.enforce_args(1, ":x: You must pass a video!")
async def play_youtube(client: discord.Client, message: discord.Message, args: list):
    """
    Plays a video from any valid streaming source that `youtube-dl` can download from.
    This included things such as YouTube (obviously) and SoundCloud.
    You must have the Voice or Bot Commander role to use this command.
    """

    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    voice_channel = await find_voice_channel(message.server)
    if not voice_channel:
        await client.send_message(message.channel, content=":x: Cannot find voice channel for playing music! (channel "
                                                           "must be named `Music` or `NavalBot`.)")
        return

    vidname = args[0]

    # Do the same as play_file, but with a youtube streamer.
    # Play it via ffmpeg.

    ydl = youtube_dl.YoutubeDL({"format": 'webm[abr>0]/bestaudio/best'})
    func = functools.partial(ydl.extract_info, vidname, download=False)
    info = await loop.run_in_executor(None, func)
    if "entries" in info:
        info = info['entries'][0]

    title = info.get('title')
    download_url = info['url']

    duration = info.get('duration')
    if (duration and int(duration) > (60 * 10)) and int(message.author.id) not in cmds.RCE_IDS:
        await client.send_message(message.channel, ":x: Videos are limited to a maximum of 10 minutes.")
        return

    async def _coro_play_youtube(url, title):
        logger.debug("YouTube player loading from queue.")
        # Coroutine to place on the voice queue.
        # Join the channel.
        await client.join_voice_channel(channel=voice_channel)
        # Get the voice client.
        voice_client = client.voice
        # Create a ffmpeg player
        player = voice_client.create_ffmpeg_player(url)
        logger.debug("Now playing: '{}'".format(title))
        # Start playing
        player.start()
        voice_params["player"] = player
        voice_params["playing"] = True
        voice_params["file"] = title
        voice_params["in_server"] = message.server.id
        await client.send_message(message.channel, ":heavy_check_mark: Now playing: `{}`".format(title))
        # Change game.
        await client.change_status(game=discord.Game(name=title))
        # Constantly loop every 0.5s to check if the music has finished.
        while True:
            if player.is_done():
                break
            else:
                await asyncio.sleep(0.5)
        # Leave the voice channel, for the next coroutine to use.
        await client.voice.disconnect()
        voice_params["player"] = None
        voice_params["playing"] = False
        voice_params["file"] = ""
        voice_params["in_server"] = None
        # End game.
        await client.change_status(None)

    # Get the number of songs on the queue.
    items = queue.qsize()

    # Put the coroutine on the queue.
    try:
        queue.put_nowait((_coro_play_youtube(download_url, title), title, message.server.name))
    except asyncio.QueueFull:
        await client.send_message(message.channel, ":no_entry: There are too many songs on the queue. Cannot start "
                                                   "playing.")
        return
    # We're done! Now we can wait for the player coroutine to await our coro.
    # Send a message to the channel telling them what position they are on.
    if items != 0:
        await client.send_message(message.channel,
                                  ":heavy_check_mark: You are number {} in the queue.".format(items + 1))
    else:
        await client.send_message(message.channel, ":heavy_check_mark: You are next in the queue.")
