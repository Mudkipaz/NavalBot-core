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

from math import trunc

import discord
import util
from cmds import command

from voice.stores import voice_params


@command("again")
async def again(client: discord.Client, message: discord.Message):
    """
    Adds this item to the queue again.
    """

    # Standard checks.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    # Get the item from the queue.
    i = voice_params[message.server.id].get("curr_coro")
    if not i:
        await client.send_message(message.channel, content=":x: Nothing to play again.")
        return

    # Add it to the queue.
    try:
        queue = voice_params[message.server.id]["queue"]
        title = voice_params[message.server.id]["title"]
        assert isinstance(queue, asyncio.Queue)
        queue.put_nowait((i, title))
    except KeyError:
        await client.send_message(message.channel, content=":x: No queue to place item on.")
    except asyncio.QueueFull:
        await client.send_message(message.channel, content=":x: Queue is full.")
    else:
        await client.send_message(message.channel, content=":heavy_check_mark: Repeating track.")


@command("shuffle")
@util.with_permission("Bot Commander", "Voice", "Admin")
async def shuffle(client: discord.Client, message: discord.Message):
    """
    Shuffles the queue.
    """
    # Standard checks.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get("queue")
    if not queue:
        await client.send_message(message.channel, ":x: There is no queue for this server.")
        # this never happens

    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    new_queue = asyncio.Queue(maxsize=qsize)
    assert isinstance(queue, asyncio.Queue)
    deq = list(queue._queue)

    # shuffle deq
    random.shuffle(deq)

    # append all items
    for i in deq:
        try:
            new_queue.put_nowait(i)
        except asyncio.QueueFull:
            # wat
            break

    # set the new queue
    voice_params[message.server.id]["queue"] = new_queue

    await client.send_message(message.channel, ":heavy_check_mark: Shuffled queue.")


@command("queued")
@command("queue")
async def get_queued_vids(client: discord.Client, message: discord.Message):
    # STILL HORRIBLE

    # Get the current player instance.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get('queue', [])
    if queue:
        queue = queue._queue

    # Get the start pos.
    try:
        start_pos = int(message.content.split(" ")[1])
    except (ValueError, IndexError):
        start_pos = 0

    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    s = "**Currently queued: ({}/{})**".format(len(queue), qsize)
    if not queue or len(queue) == 0:
        s += "\n`Nothing is queued.`"
        await client.send_message(message.channel, s)
        return

    if start_pos + 1 > len(queue):
        await client.send_message(message.channel, ":x: Queue is not as long as that.")
        return
    if start_pos < 0:
        await client.send_message(message.channel, ":x: Cannot check queue for negative numbers.")
        return

    for item in range(start_pos, start_pos + len(queue) if len(queue) < 10 else start_pos + 10):
        try:
            i = queue[item]
        except IndexError:
            break
        if isinstance(i[1], str):
            title = i[1]
            df = "??:??"
        else:
            title = i[1].get("title")
            # get duration
            dm, ds = divmod(i[1].get("duration"), 60)
            df = "`[{:02d}:{:02d}]`".format(trunc(dm), trunc(ds))
        s += "\n{}. `{}` `{}`".format(item + 1, title, df)

    if len(queue) > start_pos + 10:
        s += "\n(Omitted {} queued items.)".format((len(queue) - 10) - start_pos)
    await client.send_message(message.channel, s)


@command("skip")
@util.with_permission("Bot Commander", "Voice", "Admin")
async def skip(client: discord.Client, message: discord.Message):
    """
    Skips ahead one or more tracks.
    """
    # Get the current player instance.
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    playing = voice_params[message.server.id].get("playing")
    if not playing:
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    player = voice_params[message.server.id].get("player")
    if not player:
        # ???
        await client.send_message(message.channel, content=":x: No song is currently playing on this server.")
        return

    # Get the max queue size
    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    try:
        aaa = message.content.split(" ")
        if aaa[1] == "all":
            to_skip = 9999999
        else:
            to_skip = int(aaa[1])

    except IndexError:
        to_skip = 1
    except ValueError:
        to_skip = 1

    # Re-arrange the queue.
    queue = voice_params[message.server.id].get("queue")
    if not queue:
        # what
        await client.send_message(message.channel, content=":x: This kills the bot")
        return
    assert isinstance(queue, asyncio.Queue)

    if to_skip == 1:
        # Just stop the player.
        player.stop()
        await client.send_message(message.channel, content=":heavy_check_mark: Skipped current song.")
        return

    # Remove 1 off of to_skip to represent the current song
    to_skip -= 1

    player.stop()

    internal_queue = list(queue._queue)
    if len(internal_queue) < to_skip:
        del voice_params[message.server.id]["queue"]
        player.stop()
        await client.send_message(message.channel, ":x: Reached end of queue - stopped playing.")
        # Kill the task.
        ts = voice_params[message.server.id]["task"]
        if ts:
            assert isinstance(ts, asyncio.Task)
            ts.cancel()
        del voice_params[message.server.id]["task"]
        # Kill the player.
        del voice_params[message.server.id]["player"]
        del voice_params[message.server.id]["playing"]
        return

    # Put things from index: onto the queue.
    new_queue = asyncio.Queue(maxsize=qsize)
    for i in internal_queue[to_skip:]:
        try:
            new_queue.put_nowait(i)
        except asyncio.QueueFull:
            # if the queue-size was shrunk between playing and a skip, this might happen
            pass

    voice_params[message.server.id]["queue"] = new_queue
    await client.send_message(message.channel, ":heavy_check_mark: Skipped {} items.".format(to_skip + 1))


@command("move")
@util.enforce_args(2, error_msg=":x: You must provide two numbers: The original position, and the new position.")
async def move(client: discord.Client, message: discord.Message, args: list):
    """
    Moves a song in the queue from position <x> to position <y>.
    """
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get("queue")
    if not queue:
        # ???
        return

    try:
        fr, to = int(args[0]) - 1, int(args[1]) - 1
    except ValueError:
        await client.send_message(message.channel, ":x: You must provide two numbers.")
        return

    assert isinstance(queue, asyncio.Queue)

    # Turn into list, pop from index, insert at index.
    internal_queue = list(queue._queue)
    try:
        got = internal_queue.pop(fr)
        internal_queue.insert(to, got)
    except IndexError as e:
        await client.send_message(message.channel, ":x: Could not find track at index `{}`.".format(fr))
        return

    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    # Re-create queue, blah blah blah
    new_queue = asyncio.Queue(maxsize=qsize)

    for i in internal_queue:
        try:
            new_queue.put_nowait(i)
        except asyncio.QueueFull:
            pass

    # Set new queue.
    voice_params[message.server.id]["queue"] = new_queue
    if isinstance(got[1], str):
        title = got[1]
    else:
        title = got[1].get("title")

    await client.send_message(message.channel, ":heavy_check_mark: Moved item `{}` to position `{}`.".format(title,
                                                                                                             to + 1))


@command("remove")
@util.with_permission("Bot Commander", "Voice", "Admin")
@util.enforce_args(1, error_msg=":x: You must give an index to remove.")
async def remove_vid(client: discord.Client, message: discord.Message, args: list):
    """
    Removes a video at a specific index from the queue.
    """
    if not discord.opus.is_loaded():
        await client.send_message(message.channel, content=":x: Cannot load voice module.")
        return

    if message.server.id not in voice_params:
        await client.send_message(message.channel, content=":x: Not currently connected on this server.")
        return

    queue = voice_params[message.server.id].get("queue")
    if not queue:
        # ???
        return

    assert isinstance(queue, asyncio.Queue)

    # Standard prodecure - turn deque into a list
    internal_queue = list(queue._queue)
    try:
        removed = internal_queue.pop(int(args[0]) - 1)
    except IndexError:
        await client.send_message(message.channel, ":x: No track at index `{}`".format(args[0]))
        return
    except ValueError:
        await client.send_message(message.channel, ":x: Not a valid index.")
        return

    qsize = util.get_config(message.server.id, "max_queue", default=99, type_=int)

    # Re-create queue, blah blah blah
    new_queue = asyncio.Queue(maxsize=qsize)

    for i in internal_queue:
        try:
            new_queue.put_nowait(i)
        except asyncio.QueueFull:
            pass

    if isinstance(removed[1], str):
        title = removed[1]
    else:
        title = removed[1].get("title")

    voice_params[message.server.id]["queue"] = new_queue
    await client.send_message(message.channel, ":heavy_check_mark: Deleted item {} `({})`.".format(args[0], title))