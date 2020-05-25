[![CodeFactor](https://www.codefactor.io/repository/github/xuathegrate/abyss/badge/master?s=e6e1f34781addab833895bb700c429580bfe5f35)](https://www.codefactor.io/repository/github/xuathegrate/abyss/overview/master)

Use `$tutorial` to get an understanding on how this bot works.

[**v1.1.0 Changelog**](#changelog)
# Abyss v1.1.0
[Python 3.7/3.8](https://github.com/python/cpython), [discord.py 1.3.0a](https://github.com/Rapptz/discord.py), [AGPLv3](license.md)

A Persona/SMT styled Discord RPG bot.

This bot was originally run under the name `Adventure!`,
but has been ported to a whole new and improved system.

If you encounter any bugs at all, please join the support server
and report it. The link can be found at the bottom of this page.
## Features
#### Immersive Battling Simulator
Engage with your inner demon and defeat the enemy before you.

(Scroll down to see a live example.)
#### Improved Exploration
Explore the dungeon and collect various items to power up
your inner self.
#### Rare Treasure Demons
Have an encounter with the rare Treasure Demon and harness its
power as your own.
#### Dungeon Looting
Explore the (more to come) various dungeons and collect as much
loot as you can find!
#### Crafting
Turn the materials you find during your exploration into useful
tools such as Lockpicks and more!
## W.I.P Features
#### Background Music
Enjoy great tunes in the background as you explore the mass of
dungeons.
#### PVP Simulator
Battle against your friends to see who has the strongest demon
inside of themselves.

![example](https://i.imgur.com/yWeuE82.gif)

## Changelog
**v1.1.0**
* Added lock picks to unlock locked chests.
* Added locked chests.
* Added ability to open chests.
* Added two new item categories, `Key` and `Utility`.
* Fixed a bug where it looked like your turn was skipped.
In reality, it was just that you missed but i never sent the message.
* Added HP and SP to the status menu.
* Moved inventory related commands to their own cog.
* Fixed issue where disabled commands were shown in help.
* Got sick of the new help command, went back to the original.
* Removed LRU dict of players for the time being.
* Added ability to craft items.
Currently can only craft `Lockpick` with `1x Aluminum Sheet`.
* Can now obtain some materials from treasures.
* Can now open your inventory during battle.
You will lose control of battle while this is open.
* Refactored how healing items work via using a TargetSession during battle.
* Fix circular import bug by moving sessions to its own file.

## Misc
Join the support server via [this link](https://discord.gg/hkweDCD)
to receive updates and special features, or to voice your opinion
on what should be changed or added.

## Take control of your inner Demon!

This bot has no relation to Atlus or any of Shin Megami Tensei / Persona.
It is created purely for fans and will be taken down if requested.
