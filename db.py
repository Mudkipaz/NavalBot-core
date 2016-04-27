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

# This handles aioredis DB stuff.

import aioredis
import util

async def get_config(server_id: str, key: str, default=None, type_: type=str) -> str:
    """
    Gets a config from the redis DB.
    """
    pool = await util.get_pool()
    # Get the value of config:server_id:key.
    built = "config:{sid}:{key}".format(server_id, key)
    async with pool.get() as conn:
        if not conn.exists(built):
            return default
        else:
            data = conn.get(built)
            try:
                return type_(data.decode())
            except ValueError:
                return default

async def set_config(server_id: str, key: str, value: str):
    """
    Sets a config in the redis DB.
    """
    pool = await util.get_pool()
    # Set config:server_id:key.
    built = "config:{sid}:{key}".format(server_id, key)
    async with pool.get() as conn:
        conn.set(built, value)

