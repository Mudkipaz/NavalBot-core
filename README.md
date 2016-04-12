# NavalBot 2.x

[![Requirements Status](https://requires.io/github/SunDwarf/NavalBot/requirements.svg?branch=develop)](https://requires.io/github/SunDwarf/NavalBot/requirements/?branch=develop)
![https://img.shields.io/github/release/SunDwarf/NavalBot.svg](https://img.shields.io/github/release/SunDwarf/NavalBot.svg)

A bot for discord servers using [discord.py] (https://github.com/Rapptz/discord.py)

[Join our test server!](https://discord.gg/0tfUHkzxPbHCAel9)  
[Discord Server Requirements] (https://github.com/SunDwarf/NavalBot/blob/develop/requirements.txt)

**If you are running a local version, anything before version 2.5.3 is not supported. Don't even ask.**

## Why use NavalBot?

NavalBot is the best multi purpose bot available.  

It currently supports:

 - Custom factoids
 - Music playing, even in multiple servers
 - Moderation abilities
 - Other fun commands
 
Unlike many other bots, it's also fast due to the asyncio-based back end.

## Download and Installation

1. Download the latest release from [the releases page] (https://github.com/sundwarf/navalbot/releases/latest)  
2. Put the files (unzipped if you downloaded the .zip) in a new folder on your computer.  
3. Open up `__init__.py` and change `RCE_IDS` to match your Discord user id.  

Next, open your command line and launch `bot.py` with the login credentials for your bot.  
E.g: `>>  python bot.py --oauth-bot-id <client-id> --oauth-bot-secret <oauth token>`

## Configuration

Make sure to create a `Bot Commander` role and assign it to your Discord moderators/admins.  
Members with the `Bot Commander` role can execute specifc commands that are inaccessible for regular members.  
Your bot needs the `Admin` flag in order for moderation commands like `?kick` or `?ban` to work. 

## Creating the `Muted` Role

This role is needed for the ?mute and ?unmute command to work

1. Create a role named 'Muted'
2. Go into your server settings and edit the permissions for the role
    - [Screenshot](http://i.imgur.com/0VRu2Ff.png)
    - Make sure that only these three options are enabled
3. Go into the channel specific permissions and make sure that none of the `@everyone` permissions are checked
    - [Screenshot](https://i.imgur.com/3t4zmTF.png)
4. Add the `Muted` role and remove these permissions
    - [Screenshot](https://i.imgur.com/iuKw1i8.png)
    - Repeat this step for every channel in which you want the `Muted` role to work

## Available commands
### Commands
- [Regular commands] (#regular-commands)
- [Music commands] (#music-commands)
- [Moderation commands] (#moderation-commands)
- [Admin/Configuration commands] (#admin-commands)

#### Regular commands:

- ?commands
- ?help
- ?choice
- ?coin
- ?uptime
- ?version
- ?weather
- ?whois
- ?google
- ?info
- ?invite
- ?stats
- ?lock
- ?reddit

#### Music commands:
- ?searchyt
- ?nowplaying
- ?np
- ?playyoutube
- ?playyt / ?play
- ?stop
- ?skip
- ?queue

#### Moderation commands
- ?mute
- ?unmute
- ?kick
- ?ban
- ?unban
- ?delete

#### Admin commands:
- ?setcfg
- ?getcfg
- ?sql
- ?py
- ?update

## Contributing

If you'd like to contribute to Navalbot, you can:

 - [Fork the repository] (https://github.com/SunDwarf/NavalBot/fork)
 - [Create a pull request] (https://github.com/SunDwarf/NavalBot/pull/new)
 - [Create a new issue] (https://github.com/SunDwarf/NavalBot/issues/new)
 

## License

```
This program is free software: you can redistribute it and/or modify  
it under the terms of the GNU General Public License as published by  
the Free Software Foundation, either version 3 of the License, or  
(at your option) any later version.  

This program is distributed in the hope that it will be useful,  
but WITHOUT ANY WARRANTY; without even the implied warranty of  
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the  
GNU General Public License for more details.  

You should have received a copy of the GNU General Public License  
along with this program.  If not, see <http://www.gnu.org/licenses/>.  
```
