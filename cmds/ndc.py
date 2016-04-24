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

# Owner commands.
import sys

import discord
import importlib
import subprocess
import asyncio
import re

# RCE ids
import cmds
import util

getter = re.compile(r'`{1,3}(.*?)`{1,3}')

loop = asyncio.get_event_loop()


@cmds.command("reload")
@util.only(util.get_config(None, "RCE_ID", default=0, type_=int))
@util.enforce_args(1, "You must pick a file to reload.")
async def reload_f(client: discord.Client, message: discord.Message, args: list):
    """
    Reloads a module in the bot.
    """
    mod = args[0]
    if mod not in sys.modules:
        await client.send_message(message.channel, ":x: Module is not loaded.")
        return
    # Reload using importlib.
    new_mod = importlib.reload(sys.modules[mod])
    # Update sys.modules
    sys.modules[mod] = new_mod
    await client.send_message(message.channel, ":heavy_check_mark: Reloaded module.")


@cmds.command("sql")
@util.only(util.get_config(None, "RCE_ID", default=0, type_=int))
async def sql(client: discord.Client, message: discord.Message):
    sql_cmd = getter.findall(message.content)
    if not sql_cmd:
        return
    util.cursor.execute(sql_cmd[0])
    await client.send_message(message.channel, "`{}`".format(util.cursor.fetchall()))


@cmds.command("py")
@util.only(util.get_config(None, "RCE_ID", default=0, type_=int))
async def py(client: discord.Client, message: discord.Message):
    match = getter.findall(message.content)
    if not match:
        return
    else:
        result = eval(match[0])
        await client.send_message(message.channel, "```{}```".format(result))