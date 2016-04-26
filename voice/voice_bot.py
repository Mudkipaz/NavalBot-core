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
import logging
from math import trunc

import discord
import functools
import youtube_dl

import util

from cmds import command

loop = asyncio.get_event_loop()

# Declare variables, inside try to prevent overwrites on reload.
try:
    voice_params
except NameError:
    voice_params = {}

try:
    voice_locks
except NameError:
    voice_locks = {}

logger = logging.getLogger("NavalBot::Voice")

