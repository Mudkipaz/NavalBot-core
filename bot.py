"""
The main entry point of NavalBot.

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
import os
import re
import sys
import traceback
from ctypes.util import find_library
import logging
import argparse

import aiohttp
import discord
from discord import Client

# =============== Commands
import cmds
import util
from cmds import commands
# Fuck off PyCharm
import importlib

from util import db, cursor

__zipdep_zipmodules = ['youtube_dl', 'aiohttp', 'blessings', 'chardet', 'curtsies', 'decorator',
                       'discord', 'docopt', 'google', 'greenlet', 'monotonic', 'praw', 'pygments', 'pyowm',
                       'requests', 'six', 'wcwidth', 'websockets', 'ws4py', 'googleapiclient', 'bs4', 'httplib2',
                       'uritemplate', 'oauth2client', 'update_checker', 'nacl']

importlib.import_module("cmds.cfg")
importlib.import_module("cmds.fun")
importlib.import_module("cmds.moderation")
importlib.import_module("cmds.ndc")

# =============== End commands

# =============== Argparse

if __name__ != "__zipdep":
    parser = argparse.ArgumentParser(description="The best discord bot in the world!")

    oauth_group = parser.add_argument_group(title="OAuth2")
    oauth_group.add_argument("--oauth-bot-id", help="OAuth2 Bot ID", type=int)
    oauth_group.add_argument("--oauth-bot-secret", help="OAuth2 Bot secret token")

    ep_group = parser.add_argument_group(title="E-Mail/Password")
    ep_group.add_argument("--ep-email", help="Bot account's email")
    ep_group.add_argument("--ep-password", help="Bot account's password")

    args = parser.parse_args()

# ===============

# Define logging.

def init_logging():
    if sys.platform == "win32":
        logging.basicConfig(filename='nul', level=logging.INFO)
    else:
        logging.basicConfig(filename='/dev/null', level=logging.INFO)

    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] %(name)s -> %(message)s')
    root = logging.getLogger()

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(formatter)
    root.addHandler(consoleHandler)


logger = logging.getLogger("NavalBot")
logger.setLevel(logging.DEBUG)

# Load opus
found = find_library("opus")
if found:
    discord.opus.load_opus(found)
else:
    print(">> Cannot load opus library - cannot use voice.")
    del found

# Create a client.
client = Client()

# Get DB

cursor.execute("""
CREATE TABLE IF NOT EXISTS factoids (
  id INTEGER PRIMARY KEY, name VARCHAR, content VARCHAR, locked INTEGER, locker VARCHAR, server VARCHAR
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS configuration (
  id INTEGER PRIMARY KEY,
  name VARCHAR,
  value VARCHAR,
  server VARCHAR
)
""")

# Version information.
VERSION = "2.1.1"
VERSIONT = tuple(int(i) for i in VERSION.split("."))

# Factoid matcher compiled
factoid_matcher = re.compile(r'(.*?) is (.*)')

loop = asyncio.get_event_loop()

attrdict = type("AttrDict", (dict,), {"__getattr__": dict.__getitem__, "__setattr__": dict.__setitem__})


# Events.
@client.event
async def on_ready():
    # Get the OAuth2 URL, or something
    if not hasattr(client, "email"):
        bot_id = args.oauth_bot_id
        permissions = discord.Permissions.all_channel()
        oauth_url = discord.utils.oauth_url(str(bot_id), permissions=permissions)
        if bot_id is None:
            logger.critical("You didn't set the bot ID using --oauth-bot-id. Your bot cannot be invited anywhere.")
            sys.exit(1)
        logger.info("NavalBot is now using OAuth2, OAuth URL: {}".format(oauth_url))
        from cmds import voice_bot as voice
    else:
        logger.warning("NavalBot is still using a legacy account. This will stop working soon!")
        from cmds import voice_queue as voice
    # print ready msg
    logger.info("Loaded NavalBot, logged in as `{}`.".format(client.user.name))
    # make file dir
    try:
        os.makedirs(os.path.join(os.getcwd(), "files"))
    except FileExistsError:
        pass
    # load the voice handler
    if hasattr(voice, "play_music_from_queue"):
        logger.warning("Using old queue-based music player!")
        loop.create_task(voice.play_music_from_queue())


@client.event
async def on_message(message: discord.Message):
    # Increment the message count.
    util.msgcount += 1
    # print("-> Recieved message:", message.content, "from", message.author.name)
    logger.info("Recieved message: {message.content} from {message.author.name}".format(message=message))
    if not isinstance(message.channel, discord.PrivateChannel):
        # print("--> On channel: #" + message.channel.name)
        logger.info(" On channel: #{message.channel.name}".format(message=message))
    # Check if it matches the command prefix.
    if message.author.name == client.user.name:
        logger.info("Not processing own message.")
        return
    if message.server is not None:
        prefix = util.get_config(message.server.id, "command_prefix", "?")
    else:
        await client.send_message(message.channel, "I don't accept private messages.")
        return
    if len(message.content) == 0:
        logger.info("Ignoring (presumably) image-only message.")
        return
    if message.content[0] == prefix:
        try:
            coro = commands[message.content[1:].split(' ')[0]](client, message)
        except KeyError as e:
            logger.warning("-> No such command: " + str(e))
            coro = default(client=client, message=message)
        try:
            await coro
        except Exception as e:
            if isinstance(e, discord.HTTPException):
                pass
            else:
                await client.send_message(message.channel, content="```\n{}\n```".format(traceback.format_exc()))


# ============= Built-in commands.

def read_version(data):
    regexp = re.compile(r"^VERSION\W*=\W*([\d.abrc]+)")

    for line in data:
        match = regexp.match(line)
        if match is not None:
            return match.group(1)
    else:
        print("Cannot get new version from GitHub.")


@cmds.command("version")
async def version(client: discord.Client, message: discord.Message):
    await client.send_message(
        message.channel,
        "Version **{}**, written by SunDwarf (https://github.com/SunDwarf) and shadow (https://github.com/ilevn)"
            .format(VERSION)
    )
    # Download the latest version
    async with aiohttp.ClientSession() as sess:
        s = await sess.get("https://raw.githubusercontent.com/SunDwarf/NavalBot/stable/bot.py")
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


async def get_file(client: tuple, url, name):
    """
    Get a file from the web using aiohttp, and save it
    """
    with aiohttp.ClientSession() as sess:
        async with sess.get(url) as get:
            assert isinstance(get, aiohttp.ClientResponse)
            if int(get.headers["content-length"]) > 1024 * 1024 * 8:
                # 1gib
                await client[0].send_message(client[1].channel, "File {} is too big to DL")
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


@cmds.command("help")
@util.enforce_args(1, error_msg=":x: You must provide a command for help!")
async def help(client: discord.Client, message: discord.Message, args: list):
    """
    ಠ_ಠ
    """
    # Get the function
    func = cmds.commands.get(args[0])
    if not func:
        await client.send_message(message.channel, ":no_entry: That function does not exist!")
        return

    # Format __doc__
    if not func.__doc__:
        await client.send_message(message.channel, ":x: This function doesn't have help.")
        return
    doc = func.__doc__.split("\n")
    doc = [d.lstrip() for d in doc if d.lstrip()]
    doc = '\n'.join(doc)
    await client.send_message(message.channel, doc)


async def default(client: discord.Client, message: discord.Message):
    data = message.content[1:]
    # Check if it matches a factoid creation
    matches = factoid_matcher.match(data)
    if matches:
        # Set the factoid
        name = matches.groups()[0]
        fac = matches.groups()[1]
        assert isinstance(fac, str)
        if fac.startswith("http") and 'youtube' not in fac:
            # download as a file
            file = sanitize(fac.split('/')[-1])
            client.loop.create_task(get_file((client, message), url=fac, name=file))
            fac = "file:{}".format(file)
        # check if locked
        cursor.execute("SELECT locked, locker FROM factoids "
                       "WHERE factoids.name = ?"
                       "AND factoids.server = ?", (name, message.server.id))
        row = cursor.fetchone()
        if row:
            locked, locker = row
            if locked and locker != message.author.id and int(message.author.id) not in cmds.RCE_IDS:
                await client.send_message(message.channel, "Cannot change factoid `{}` locked by `{}`"
                                          .format(name, locker))
                return
        cursor.execute("""INSERT OR REPLACE
                       INTO factoids (id, name, content, server)
                       VALUES (
                       (SELECT id FROM factoids WHERE name = ? AND server = ?),
                       ?, ?, ?)""", (name, message.server.id, name, fac, message.server.id))
        db.commit()
        await client.send_message(message.channel, "Factoid `{}` is now `{}`".format(name, fac))
    else:
        # Get factoid
        cursor.execute("SELECT (content) FROM factoids "
                       "WHERE factoids.name = ?"
                       "AND factoids.server = ?", (data, message.server.id))
        rows = cursor.fetchone()
        if not rows:
            return
        # Load content
        content = rows[0]
        assert isinstance(content, str)
        # Check if it's a file
        if content.startswith("file:"):
            fname = content.split("file:")[1]
            if not os.path.exists(os.path.join(os.getcwd(), 'files', fname)):
                await client.send_message(message.channel, ":x: Unknown error: File {} does not exist".format(fname))
                return
            # Load the file
            with open(os.path.join(os.getcwd(), 'files', fname), 'rb') as f:
                await client.send_file(message.channel, f)
            return
        await client.send_message(message.channel, content)


def main():
    init_logging()
    # Switch login method based on args.
    if args.oauth_bot_id is not None:
        login = (args.oauth_bot_secret,)
    elif args.ep_email is not None:
        login = (args.ep_email, args.ep_password)
    else:
        logger.error("You must use one login method!")
        loop.set_exception_handler(lambda *args, **kwargs: None)
        sys.exit(1)

    # Create the future
    loop.create_task(client.start(*login))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(client.logout())
        loop.set_exception_handler(lambda *args, **kwargs: None)
    except Exception:
        import traceback
        traceback.print_exc()
        logger.error("Crashed. Don't know how, don't care. Exiting.")
        sys.exit(1)
    finally:
        loop.close()
    logger.info("NavalBot shutting down.")

if __name__ == "__main__":
    main()
