import discord

from .paginators import EmbedPaginator, PaginationHandler


class Inventory:
    def __init__(self, bot, player, data):
        self.player = player
        self.items = {}
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
        await PaginationHandler(ctx.bot, pg, send_as='embed').start(ctx)