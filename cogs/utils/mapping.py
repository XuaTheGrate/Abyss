import json

import numpy.random as random


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
        if self.areas[player.area]['treasurecount'] == key:  # None doesn't matter since we havent seen any treasures
            # also its set to None every 24h
            return False  # return False indicating that no treasures are available here
        await self.bot.redis.hincrby(f'treasures_found:{player.owner.id}', player.area, 1)
        # otherwise, return None (we didnt find anything) or an item/treasure demon
        choice = random.uniform()
        if choice <= 0.1:
            # remind me to start a Treasure Demon battle
            return None
        elif choice <= 0.9:
            # return an item of some kind
            return None
        else:
            return None  # we didnt find anything


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
            self.maps[md['name']] = Map(self.bot, md['name'], md)
