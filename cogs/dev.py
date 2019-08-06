import importlib
import sys

from discord.ext import commands

from .utils.formats import format_exc


class Developers(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.group()
    async def dev(self, ctx):
        pass

    @dev.command()
    async def reload(self, ctx, *, module):
        try:
            sys.modules[module] = importlib.reload(sys.modules[module])
            await ctx.send(ctx.bot.tick_yes)
        except Exception as e:
            await ctx.send(ctx.bot.tick_no)
            ctx.bot.send_error(f'```py\n{format_exc(e)}\n```')

    @dev.command()
    async def cleanup(self, ctx):
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            await ctx.channel.purge(check=lambda m: m.author == ctx.me or m.content.startswith("$"), before=ctx.message)
        else:
            await ctx.channel.purge(check=lambda m: m.author == ctx.me, bulk=False)


def setup(bot):
    bot.add_cog(Developers(bot))
