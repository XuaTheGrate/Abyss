import random

from discord.ext import commands

from cogs.utils.formats import SilentError


class Maps(commands.Cog, command_attrs={"enabled": False}):
    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx):
        if self.bot.players.players.get(ctx.author.id, None) in self.bot.get_cog("BattleSystem").battles:
            await ctx.send("Cannot move while in battle.")
            raise SilentError
        if random.randint(1, 5) == 1:  # interrupt the command with an encounter :^)
            await ctx.invoke(self.bot.get_command("encounter"), force=True)
            raise SilentError
        return True

    @commands.command()
    async def search(self, ctx):
        """Looks around to see what you can interact with.
        Has a chance of spawning an enemy, interrupting the search."""

    @commands.command()
    async def inventory(self, ctx):
        """Opens your inventory and shows your items.
        You can select some items and use them if you wish,
        though some items may only be used in battle."""

    @commands.command()
    async def move(self, ctx):
        """Moves to another location.
        You can find what locations are available after `search`ing."""

    @commands.command()
    async def interact(self, ctx):
        """Interacts with an object in this area.
        You can find what objects are available after `search`ing."""


def setup(bot):
    bot.add_cog(Maps(bot))
