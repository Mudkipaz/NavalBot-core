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
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import traceback
from ctypes.util import find_library

import discord
import requests
from colorama import init, Fore, Back, Style

# =============== Commands
import cmds
import util
from cmds import commands
# Fuck off PyCharm
import importlib

from util import db, cursor, get_file, sanitize

init()


importlib.import_module("cmds.cfg")
importlib.import_module("cmds.fun")
importlib.import_module("cmds.moderation")
importlib.import_module("cmds.ndc")
importlib.import_module("cmds.version")

# =============== End commands

loop = asyncio.get_event_loop()

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

# =============== Version information

VERSION = "2.7.1"
VERSIONT = tuple(int(i) for i in VERSION.split("."))


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
if sys.platform == "win32":
    if os.path.exists(os.path.join(os.getcwd(), "libopus.dll")):
        found = "libopus"
    else:
        found = False
else:
    found = find_library("opus")
if found:
    print(">> Loaded libopus from {}".format(found))
    discord.opus.load_opus(found)
else:
    if sys.platform == "win32":
        print(">> Downloading libopus for Windows.")
        sfbit = sys.maxsize > 2 ** 32
        if sfbit:
            to_dl = 'x64'
        else:
            to_dl = 'x86'
        r = requests.get("https://github.com/SexualRhinoceros/MusicBot/raw/develop/libopus-0.{}.dll".format(to_dl),
                         stream=True)
        # Save it as opus.dll
        with open("libopus.dll", 'wb') as f:
            for chunk in r.iter_content(256):
                f.write(chunk)
        discord.opus.load_opus("libopus")
        del sfbit, to_dl
    else:
        print(">> Cannot load opus library - cannot use voice.")
        del found

# Create a client.
client = discord.Client()

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

# Factoid matcher compiled
factoid_matcher = re.compile(r'(.*?) is (.*)')

attrdict = type("AttrDict", (dict,), {"__getattr__": dict.__getitem__, "__setattr__": dict.__setitem__})

# Pre-load the blacklist.
if os.path.exists("blacklist.json"):
    with open("blacklist.json") as f:
        bl = json.load(f)
        bl_mtime = os.stat(f.fileno()).st_mtime
else:
    bl = []
    bl_mtime = time.time()


# Events.
@client.event
async def on_ready():
    # Get the OAuth2 URL, or something
    if client.user.bot:
        bot_id = args.oauth_bot_id
        permissions = discord.Permissions.all_channel()
        oauth_url = discord.utils.oauth_url(str(bot_id), permissions=permissions)
        if bot_id is None:
            logger.critical("You didn't set the bot ID using --oauth-bot-id. Your bot cannot be invited anywhere.")
            sys.exit(1)
        logger.info("NavalBot is now using OAuth2, OAuth URL: {}".format(oauth_url))
    else:
        logger.warning("NavalBot is still using a legacy account. This will stop working soon!")

    # Change voice module as applicable.
    if isinstance(client.voice, dict):
        if client.user.bot:
            logger.info("Using upstream voice module.")
            from cmds import voice_bot as voice
        else:
            logger.error("Using modified discord.py without a bot account! Cannot continue.")
            sys.exit(3)
    else:
        logger.warning("Using queue-based voice module. This is not ideal.")
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

    if not isinstance(message.channel, discord.PrivateChannel):
        #print(Fore.RED + message.server.name, ":", Fore.GREEN + message.channel.name, ":",
        #      Fore.CYAN + message.author.name , ":", Fore.RESET + message.content)
        logger.info("Recieved message: {message.content} from {message.author.name}".format(message=message))
        logger.info(" On channel: #{message.channel.name}".format(message=message))

    # Check if it matches the command prefix.
    if message.author.name == client.user.name:
        logger.info("Not processing own message.")
        return

    # Re-process the blacklist.
    if os.path.exists("blacklist.json"):
        # Get the time
        mtime = os.stat("blacklist.json").st_mtime
        if mtime > bl_mtime:
            logger.debug("Blacklist file changed, reloading...")
            # Update mtime
            global bl_mtime
            bl_mtime = mtime
            # Reload blacklist
            with open("blacklist.json") as f:
                global bl
                bl = json.load(f)

    if message.server.id in bl:
        bb = bl[message.server.id]
        if message.author.id in bb:
            # Ignore message
            logger.warn("Ignoring message, as user is on the blacklist.")
            return

    # Check for a valid server.
    if message.server is not None:
        prefix = util.get_config(message.server.id, "command_prefix", "?")
        autodelete = True if util.get_config(message.server.id, "autodelete") == "True" else False
        if autodelete and message.content.startswith(prefix):
            await client.delete_message(message)
        logger.info(" On server: {} ({})".format(message.server.name, message.server.id))
    else:
        # No DMs
        await client.send_message(message.channel, "I don't accept private messages.")
        return

    if len(message.content) == 0:
        logger.info("Ignoring (presumably) image-only message.")
        return

    if message.content.startswith(prefix):
        cmd_content = message.content[len(prefix):]
        cmd_word = cmd_content.split(" ")[0]
        try:
            coro = commands[cmd_word](client, message)
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
                       "WHERE factoids.name = ? "
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
        sys.exit(1)

    try:
        loop.run_until_complete(client.login(*login))
    except discord.errors.HTTPException as e:
        if e.response.status == 401:
            logger.error("Your bot token is incorrect. Cannot login.")
            return
        else:
            raise

    while True:
        try:
            loop.run_until_complete(client.connect())
        except KeyboardInterrupt:
            try:
                loop.run_until_complete(client.logout())
            except Exception:
                logger.error("Couldn't log out. Oh well. We tried!")
                return
            return
        except RuntimeError:
            logger.error("Session appears to have errored. Exiting.")
            return
        except Exception:
            import traceback
            traceback.print_exc()
            logger.error("Crashed. Don't know how, don't care. Continuing..")
            continue


if __name__ == "__main__":
    main()
