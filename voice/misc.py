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

import discord

import util

from cmds import command
from voice.stores import voice_params, voice_locks


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
