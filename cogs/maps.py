import asyncio
import random

from discord.ext import commands

from cogs.utils.formats import ensure_player, SilentError
from cogs.utils.items import Unusable


class Maps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx):
        if ctx.author.id in self.bot.get_cog("BattleSystem").battles:
            raise SilentError  # cant use these commands during battle
        if ctx.command is self.inventory:
            return  # we dont want to interrupt the search if we are just opening our inventory
        if random.randint(1, 5) == 1:
            await ctx.invoke(self.bot.get_command("encounter"), force=True)
            raise SilentError

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
            self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and ctx.player.inventory.has_item(
                    m.content.lower()),
                timeout=60))
        c2 = self.bot.loop.create_task(ctx.player.inventory.pg.wait_stop())
        await asyncio.wait([c1, c2], return_when=asyncio.FIRST_COMPLETED)
        await ctx.player.inventory.pg.stop()
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
            return
        if not ctx.player.inventory.remove_item(item):
            log.warning(f"apparently {ctx.player} has {item}, but we couldnt remove it for some reason")

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
