import asyncio

from discord.ext import commands

from cogs.utils.formats import ensure_player
from cogs.utils.items import Unusable


class Maps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(enabled=False)
    @ensure_player
    async def search(self, ctx):
        """Looks around to see what you can interact with.
        Has a chance of spawning an enemy, interrupting the search."""

    @commands.command()
    @ensure_player
    async def inventory(self, ctx):
        """Opens your inventory and shows your items.
        You can select some items and use them if you wish,
        though some items may only be used in battle."""
        await ctx.player.inventory.view(ctx)
        c1 = self.bot.loop.create_task(
            self.bot.wait_for("message",
                              check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                                              and ctx.player.inventory.has_item(m.content.lower()),
                              timeout=60))
        c2 = self.bot.loop.create_task(ctx.player.inventory.pg.wait_stop())
        await asyncio.wait([c1, c2], return_when=asyncio.FIRST_COMPLETED)
        if c2.done():
            c1.cancel()
            return
        try:
            m = c1.result()
        except asyncio.TimeoutError:
            return

        item = ctx.player.inventory.get_item(m.content.lower())
        try:
            await item.use(ctx)
        except Unusable as e:
            await ctx.send(str(e))

    @commands.command(enabled=False)
    @ensure_player
    async def move(self, ctx):
        """Moves to another location.
        You can find what locations are available after `search`ing."""

    @commands.command(enabled=False)
    @ensure_player
    async def interact(self, ctx):
        """Interacts with an object in this area.
        You can find what objects are available after `search`ing."""


def setup(bot):
    bot.add_cog(Maps(bot))
