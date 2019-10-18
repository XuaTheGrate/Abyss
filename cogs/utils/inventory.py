from collections import defaultdict

import discord

from cogs.utils.items import dataclass
from .enums import ItemType
from .lookups import ITEM_TYPE_STRINGIFY
from .paginators import EmbedPaginator, PaginationHandler


@dataclass
class _ItemCount:
    def __init__(self, item, count=0):
        self.item = item
        self.count = count

    @property
    def name(self):
        return self.item.name

    def __eq__(self, other):
        return self.item == other

    def __bool__(self):
        return self.count > 0

    def __str__(self):
        return self.name


class Inventory:
    def __init__(self, bot, player, data):
        self.player = player
        self.items = defaultdict(list)
        for t in ItemType:
            self.items[t] = []
        self.pg = None
        self.open = False
        for tab, iids in data.items():
            for item, count in iids:
                self.items[ItemType[tab]].append(_ItemCount(bot.item_cache.get_item(item), count))

    def __repr__(self):
        return f"<{self.player.owner.name}'s inventory, {sum(map(len, self.items.values()))} items>"

    def to_json(self):
        return {t.name: [(str(i), i.count) for i in k] for t, k in self.items.items()}

    def set_closed(self, f):
        self.open = False

    async def view(self, ctx):
        pg = EmbedPaginator()
        for tab in self.items:
            pg.add_page(discord.Embed(title=f"<| {ITEM_TYPE_STRINGIFY[tab]} |>",
                                      description="\n".join(f"{i.count}x {i}" for i in self.items[tab])))
        self.pg = PaginationHandler(ctx.bot, pg, send_as='embed', wrap=True)
        self.pg._timeout.add_done_callback(self.set_closed)
        await self.pg.start(ctx)
        self.open = True

    def _get_item(self, name):
        for t in self.items.values():
            for i in t:
                if i.count > 0 and i.name.lower() == name.lower():
                    return i

    def get_item(self, name):
        i = self._get_item(name)
        if i:
            return i.item

    def get_item_count(self, name):
        i = self._get_item(name)
        if i:
            return i.count
        return 0

    def has_item(self, name, count=1):
        item = self._get_item(name)
        return item and item.count >= count

    def add_item(self, item):
        if item.type not in self.items:
            self.items[item.type] = []
        if not any(i.item == item for i in self.items[item.type]):
            self.items[item.type].append(_ItemCount(item, 1))
        else:
            for i in self.items[item.type]:
                if i.item == item:
                    i.count += 1
                    break

    def remove_item(self, name):
        for tab, items in self.items.items():
            for i in items:
                if i.item.name == name:
                    i.count -= 1
                    if i.count <= 0:
                        self.items[tab].remove(i)
                    return True  # successful
        return False  # didnt remove anything, for debug purposes
