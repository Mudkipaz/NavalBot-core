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
import functools
import os
import random

import discord
import psutil
import pyowm
from google import search
from googleapiclient.discovery import build

import cmds
import util

loop = asyncio.get_event_loop()


@cmds.command("choice")
@util.enforce_args(2)
async def choice(client: discord.Client, message: discord.Message, args: list):
    """
    Makes that hard choice for you.
    """
    # Choose a random argument from the list.
    chosen = random.choice(args)
    await client.send_message(message.channel, "My choice was: `{}`".format(chosen))


@cmds.command("info")
async def info(client: discord.Client, message: discord.Message):
    """
    Sends a PM with information about the bot.
    """
    await client.send_message(message.channel, "{} `Ok, check your private messages` 👍".format(message.author.mention))
    await client.send_message(message.author,
                              "Here's a link with some information:"
                              " https://github.com/SunDwarf/NavalBot/blob/stable/README.md")


def _get_google(f):
    return list(f())[0]


@cmds.command("google")
async def google(client: discord.Client, message: discord.Message):
    """
    Searches google for the top two results for the search.
    """
    userinput = ' '.join(message.content.split(" ")[1:])
    f = functools.partial(search, userinput, stop=1)
    f2 = functools.partial(_get_google, f)
    l = await util.with_multiprocessing(f2)
    await client.send_message(message.channel, l)


def _get_weather(api_key, userinput):
    owm = pyowm.OWM(api_key)
    observation = owm.weather_at_place(userinput)
    # Get the weather and stuff.
    w = observation.get_weather()
    wind = w.get_wind()['speed']
    humidity = w.get_humidity()
    temp = w.get_temperature('celsius')['temp']
    return wind, humidity, temp


@cmds.command("weather")
@util.enforce_args(1, ":x: You must specify a village/town/city/settlement to query!")
async def weather(client: discord.Client, message: discord.Message, args: list):
    """
    Displays the weather of a specified place.
    """
    api_key = util.get_config(None, "owm_api_key")
    if not api_key:
        await client.send_message(message.channel, ":exclamation: You have not set the API key. Set it with `setcfg "
                                                   "owm_api_key <your_api_key>`.")
        return
    try:
        userinput = ' '.join(args[0:])
        wind, humidity, temp = await util.with_multiprocessing(functools.partial(_get_weather(api_key, userinput)))
        await client.send_message(
            message.channel,
            '☁_Weather for {}:_\n** Temperature:** {} °C **Humidity:** {} % **Wind:** {} m/s'
                .format(userinput, temp, humidity, wind)
        )
    except AttributeError:
        await client.send_message(message.channel, "This city does not exist")


@cmds.command("commands")
async def commands(client: discord.Client, message: discord.Message):
    """
    Lists the commands for the bot.
    """
    com = ['help', 'lock', 'info', 'version', 'weather', 'whois', 'uptime', 'remindme', 'coin', 'google', 'searchyt',
           'playyt', 'stop', 'skip', 'reset', 'queue', 'shuffle', 'np',
           '\n**Admins only:**\n', 'kick', 'ban', 'unban', 'banned', 'mute', 'unmute', 'delete', 'getcfg', 'avatar',
           'setcfg', 'changename', 'blacklist', 'unblacklist', 'changename', 'broadcast']
    await client.send_message(message.channel, "**These commands are available:**\n{}".format(
        '\n'.join(
            [util.get_config(message.server.id, "command_prefix", "?") + c if ' ' not in c else c for c in com])))


@cmds.command("whois")
async def whois(client: discord.Client, message: discord.Message):
    """
    Displays information about the user specified.
    """
    try:
        await client.send_message(message.channel,
                                  '**Name:** {}\n**ID:** `{}`\n**Created at:** {}\n**Avatar:** {}'.format(
                                      message.mentions[0],
                                      message.mentions[0].id,
                                      message.mentions[0].created_at,
                                      message.mentions[0].avatar_url,
                                  ))
    except IndexError:
        await client.send_message(message.channel, "Usage: ?whois @UserName")


@cmds.command("uptime")
async def uptime(client: discord.Client, message: discord.Message):
    """
    Gives the uptime of the bot.
    """
    upt = datetime.datetime.now() - util.startup
    s = upt.total_seconds()
    formatted = util.format_timedelta(s, "`{hours_total} hours, {minutes} minutes, {seconds} seconds`")
    await client.send_message(message.channel, "Bot has been running for {} since startup of process `#{}`"
                              .format(formatted, os.getpid()))


@cmds.command("stats")
async def stats(client: discord.Client, message: discord.Message):
    """
    Displays statistics about the currently running bot.
    """
    server_count = len(client.servers)
    msgcount = util.msgcount
    if isinstance(client.voice, dict):
        voice_clients = len(client.voice)
    else:
        voice_clients = 1 if client.is_voice_connected() else 0
    # Memory stats
    used_memory = psutil.Process().memory_info().rss
    used_memory = round(used_memory / 1024 / 1024, 2)
    await client.send_message(
        message.channel,
        "Currently running on `{}` server(s). Processed `{}` messages since startup.\n"
        "Connected to `{}` voice channels.\n"
        "Using `{}MB` of memory."
            .format(server_count, msgcount, voice_clients, used_memory))


@cmds.command("searchyt")
@util.enforce_args(1, ":x: You must enter something to search for!")
async def search_youtube(client: discord.Client, message: discord.Message, args: list):
    """
    Searches YouTube for the specified tags.
    """
    # Join up the args
    to_search = " ".join(args)
    # Get the API key
    api_key = util.get_config(None, "youtube_api_key")
    if not api_key:
        await client.send_message(message.channel,
                                  ':x: The YouTube Data API v3 key has not been set!\n'
                                  ':x:Set it with `?setconfig "youtube_api_key" "key"`.')
        return

    # Create a new instance of the APIClient
    yt_api_client = build("youtube", "v3", developerKey=api_key)
    built = yt_api_client.search().list(
        q=to_search,
        part="id,snippet",
        maxResults=1
    )
    search_response = await loop.run_in_executor(None, built.execute)

    items = search_response.get("items", [])
    if not items:
        await client.send_message(message.channel, ":no_entry: No results found for your search.")
        return

    # Load the video data
    video_data = items[0]
    if video_data["id"]["kind"] != "youtube#video":
        await client.send_message(message.channel, ":no_entry: No relevant videos found for your search.")
        return

    title = video_data["snippet"]["title"]
    link = "https://youtube.com/watch?v=" + video_data["id"]["videoId"]
    await client.send_message(message.channel, "**{}**\n{}".format(title, link))


@cmds.command("coin")
async def coin(client: discord.Client, message: discord.Message):
    """
    Flip a coin!
    """
    random_choice = (["Heads!"] * 49) + (["Tails!"] * 49) + ["On the side!"]
    await client.send_message(message.channel, random.choice(random_choice))


@cmds.command("remindme")
@util.enforce_args(2, error_msg=":x: You must provide a time and reason!")
async def remind_me(client: discord.Client, message: discord.Message, args: list):
    """
    Set a reminder
    """
    time = args[0]
    try:
        time = int(time)
    except ValueError:
        await client.send_message(message.channel, ":x: That is not a valid time in seconds!")
        return
    to_remind = ' '.join(args[1:])

    async def __remind_coro():
        await asyncio.sleep(time)
        await client.send_message(message.channel,
                                  "{message.author.mention} Reminder for: `{r}`".format(message=message, r=to_remind))
        return

    await client.send_message(
        message.channel,
        "{message.author.mention} Ok, reminding you in `{s}` seconds for `{r}`.".format(message=message, r=to_remind,
                                                                                        s=time)
    )

    loop.create_task(__remind_coro())
