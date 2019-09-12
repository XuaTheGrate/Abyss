import discord

from .paginators import EmbedPaginator, PaginationHandler


class Inventory:
    def __init__(self, bot, player, data):
        self.player = player
        self.items = {}
        self.pg = None
        for tab, iids in data.items():
            self.items[tab] = list(map(bot.item_cache.get_item, iids))

    def __repr__(self):
        return f"<{self.player.owner.name}'s inventory, {sum(map(len, self.items.values()))} items>"

    def to_json(self):
        return {t: list(map(str, k)) for t, k in self.items.items()}

    async def view(self, ctx):
        pg = EmbedPaginator()
        for tab in self.items:
            pg.add_page(discord.Embed(title=tab, description="\n".join(map(str, self.items[tab]))))
        self.pg = PaginationHandler(ctx.bot, pg)
        await self.pg.start(ctx)

    def get_item(self, name):
        for t in self.items.values():
            for i in t:
                if i.name.lower() == name:
                    return i

    def has_item(self, name):
        """Case-insensitive search to check if a player has this item."""
        return self.get_item(name) is not None
