from discord.ext import commands


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
Currently gazing over {len(ctx.bot.guilds)} servers, enjoying {len(ctx.bot.users)} users' company.
I don't have my own support server, so you can join my owners general server here: <https://discord.gg/hkweDCD>""")


def setup(bot):
    bot.add_cog(Meta())
