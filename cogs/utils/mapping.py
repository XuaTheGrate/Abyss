import json

import random


class Map:
    __slots__ = ('desc', 'name', 'bot', 'areas')

    def __init__(self, bot, name, data):
        self.desc = data['desc']
        self.name = name
        self.bot = bot
        self.areas = {}
        for area in data['areas']:
            self.areas[area.pop('name')] = area

    async def open_treasure(self, player):
        key = await self.bot.redis.hget(f'treasures_found:{player.owner.id}', player.area)
        if key and int(key) == self.areas[player.area]['treasurecount']:
            # also its set to None every 24h
            return -1  # return False indicating that no treasures are available here
        await self.bot.redis.hincrby(f'treasures_found:{player.owner.id}', player.area, 1)
        # otherwise, return None (we didnt find anything) or an item/treasure demon
        choice = random.random()
        if choice <= 0.01:
            # remind me to start a Treasure Demon battle
            return 2
        elif choice <= 0.7:
            # return an item of some kind
            return 1
        else:
            return 0  # we didnt find anything


class MapHandler:
    __slots__ = ('metadata', 'maps', 'bot')

    def __init__(self, bot):
        self.bot = bot
        with open("maps/metadata.json") as f:
            self.metadata = json.load(f)

        self.maps = {}

        for m in self.metadata:
            with open(m['mapfile']) as f:
                md = json.load(f)
            md['desc'] = m['desc']
            self.maps[m['name']] = Map(self.bot, m['name'], md)
