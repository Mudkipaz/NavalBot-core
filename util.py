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
import datetime
import os
import shlex
import sqlite3
import time
from concurrent import futures
from math import floor

import aiohttp
import discord

db = sqlite3.connect("navalbot.db")
cursor = db.cursor()

startup = datetime.datetime.fromtimestamp(time.time())

# Some useful variables
msgcount = 0

loop = asyncio.get_event_loop()

multi = futures.ProcessPoolExecutor()


async def with_multiprocessing(func):
    """
    Runs a func inside a Multiprocessing executor
    """
    return await loop.run_in_executor(multi, func)


def format_timedelta(value, time_format="{days} days, {hours2}:{minutes2}:{seconds2}"):
    if hasattr(value, 'seconds'):
        seconds = value.seconds + value.days * 24 * 3600
    else:
        seconds = int(value)

    seconds_total = seconds

    minutes = int(floor(seconds / 60))
    minutes_total = minutes
    seconds -= minutes * 60

    hours = int(floor(minutes / 60))
    hours_total = hours
    minutes -= hours * 60

    days = int(floor(hours / 24))
    days_total = days
    hours -= days * 24

    years = int(floor(days / 365))
    years_total = years
    days -= years * 365

    return time_format.format(**{
        'seconds': seconds,
        'seconds2': str(seconds).zfill(2),
        'minutes': minutes,
        'minutes2': str(minutes).zfill(2),
        'hours': hours,
        'hours2': str(hours).zfill(2),
        'days': days,
        'years': years,
        'seconds_total': seconds_total,
        'minutes_total': minutes_total,
        'hours_total': hours_total,
        'days_total': days_total,
        'years_total': years_total,
    })


def get_config(server_id: str, key: str, default=None) -> str:
    """
    Gets a server-specific config value from the DB.
    """
    if server_id:
        cursor.execute("""SELECT value FROM configuration WHERE name = ?
                          AND server = ?""", (key, server_id))
    else:
        cursor.execute("""SELECT value FROM configuration WHERE name = ?""", (key,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        return default


def set_config(server_id: str, key: str, value: str):
    """
    Sets a server-specific config value in the DB
    """
    if server_id:
        cursor.execute("""INSERT OR REPLACE
                       INTO configuration (id, name, value, server)
                       VALUES (
                       (SELECT id FROM configuration WHERE name = ? AND server = ?),
                       ?, ?, ?)""", (key, server_id, key, value, server_id))
    else:
        cursor.execute("INSERT OR REPLACE "
                       "INTO configuration (id, name, value)"
                       "VALUES ((SELECT id FROM configuration WHERE name = ?), ?, ?)", (key, key, value))
    db.commit()


def has_permissions(author: discord.Member, roles: set):
    U_roles = set([r.name for r in author.roles])
    if roles.intersection(U_roles):
        return True
    else:
        return False


def with_permission(*role: str):
    """
    Only allows a command with permission.
    """
    role = set(role)

    def __decorator(func):
        async def __fake_func(client: discord.Client, message: discord.Message):
            # Get the user's roles.
            try:
                assert isinstance(message.author, discord.Member)
            except AssertionError:
                await client.send_message(message.channel, ":no_entry: Cannot determine your role!")
                return
            roles = set([r.name for r in message.author.roles])
            if roles.intersection(role) or message.author == message.server.owner:
                await func(client, message)
            else:
                await client.send_message(message.channel,
                                          ":no_entry: You do not have any of the required roles: `{}`!".format(role))

        __fake_func.__doc__ = func.__doc__

        return __fake_func

    return __decorator


def enforce_args(count: int, error_msg: str = None):
    """
    Ensure a command has been passed a certain amount of arguments.
    """
    if not error_msg:
        error_msg = (":x: Not enough arguments provided! You must provide at least `{}` args! "
                     "You can have spaces in these arguments by surrounding them in `\"\"`.".format(count))
    else:
        error_msg = error_msg.format(max_count=count)

    def __decorator(func):
        async def __fake_enforcing_func(client: discord.Client, message: discord.Message):
            # Check the number of args.
            try:
                split = shlex.split(message.content)
                # Remove the `command` from the front.
                split.pop(0)
                if len(split) < count:
                    await client.send_message(
                        message.channel,
                        error_msg
                    )
                    return
                else:
                    # Await the function.
                    await func(client, message, split)

            except ValueError:
                await client.send_message(message.channel,
                                          ":no_entry: Something went horribly wrong. Could not get video "
                                          "information.")

        __fake_enforcing_func.__doc__ = func.__doc__

        return __fake_enforcing_func

    return __decorator


def only(ids):
    """
    Only allows a specific set of IDs to run the command.
    """
    if isinstance(ids, int):
        ids = [ids]

    def __decorator(func):
        async def __fake_permission_func(client: discord.Client, message: discord.Message):
            # Get the ID.
            u_id = int(message.author.id)
            # Check if it is in the ids specified.
            if u_id in ids:
                await func(client, message)
            else:
                await client.send_message(message.channel,
                                          ":no_entry: This command is restricted to bot owners!")

        __fake_permission_func.__doc__ = func.__doc__

        return __fake_permission_func

    return __decorator


async def get_file(client: tuple, url, name):
    """
    Get a file from the web using aiohttp, and save it
    """
    with aiohttp.ClientSession() as sess:
        async with sess.get(url) as get:
            assert isinstance(get, aiohttp.ClientResponse)
            if int(get.headers["content-length"]) > 1024 * 1024 * 8:
                # 1gib
                await client[0].send_message(client[1].channel, "File {} is too big to DL".format(name))
                return
            else:
                data = await get.read()
                with open(os.path.join(os.getcwd(), 'files', name), 'wb') as f:
                    f.write(data)
                print("--> Saved file to {}".format(name))


def sanitize(param):
    param = param.replace('..', '.').replace('/', '')
    param = param.split('?')[0]
    return param
