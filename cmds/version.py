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

import re

import aiohttp
import discord

# =============== Commands
import cmds


def read_version(data):
    regexp = re.compile(r"^\W*?VERSION\W*=\W*([\d.abrc]+)")

    for line in data:
        match = regexp.match(line)
        if match is not None:
            return match.group(1)
    else:
        print("Cannot get new version from GitHub.")


@cmds.command("version")
async def version(client: discord.Client, message: discord.Message):
    """
    Checks for the latest stable version of NavalBot.
    """
    # region VERSION
    VERSION = "3.2.0"
    VERSIONT = tuple(int(i) for i in VERSION.split("."))
    # endregion

    # Version info is defined above so it can be reloaded as required.

    await client.send_message(
        message.channel,
        "Version **{}**, written by SunDwarf (https://github.com/SunDwarf) and shadow (https://github.com/ilevn)"
            .format(VERSION)
    )
    # Download the latest version
    async with aiohttp.ClientSession() as sess:
        s = await sess.get("https://raw.githubusercontent.com/SunDwarf/NavalBot/develop/cmds/version.py")
        assert isinstance(s, aiohttp.ClientResponse)
        data = await s.read()
        data = data.decode().split('\n')

    version = read_version(data)
    if not version:
        await client.send_message(message.channel, ":grey_exclamation: Could not download version information.")
        return
    if tuple(int(i) for i in version.split(".")) > VERSIONT:
        await client.send_message(message.channel, ":exclamation: *New version available:* **{}**".format(version))
    elif tuple(int(i) for i in version.split(".")) < VERSIONT:
        await client.send_message(message.channel, ":grey_exclamation: *You are running a newer version than the one "
                                                   "available online ({}).*".format(version))
    else:
        await client.send_message(message.channel, ":grey_exclamation: *You are running the latest version.*")
