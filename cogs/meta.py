import importlib
import sys

from discord.ext import commands

from .utils.formats import format_exc


class Meta(commands.Cog):
    @commands.command()
    async def ping(self, ctx):
        """Get my websocket latency to Discord."""
        await ctx.send(f":ping_pong: Pong! | {ctx.bot.latency*1000:.2f}ms websocket latency.")

    @commands.command()
    async def info(self, ctx):
        """Information about the bot."""
        await ctx.send(f"""Hi! I'm {ctx.me.name}, a W.I.P. RPG bot for Discord.
I am in very beta, be careful when using my commands as they are not ready for public use yet.
Currently gazing over {len(ctx.bot.guilds)} servers, enjoying {len(ctx.bot.users):,} users' company.
I don't have my own support server, so you can join my owners general server here: <https://discord.gg/hkweDCD>""")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, *, module):
        try:
            sys.modules[module] = importlib.reload(__import__(module))
            await ctx.send(ctx.bot.tick_yes)
        except Exception as e:
            await ctx.send(ctx.bot.tick_no)
            ctx.bot.send_error(f'```py\n{format_exc(e)}\n```')


def setup(bot):
    bot.add_cog(Meta())
