from discord.ext import commands

from .utils import i18n


class Locale(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def locale(self, ctx):
        """The base locale command. Does nothing by itself."""
        pass

    @locale.command()
    async def get(self, ctx):
        """Returns your currently active locale."""
        get = await self.bot.redis.get(f"locale:{ctx.author.id}")
        if not get:
            get = 'en_US'
        else:
            get = get.decode()
        await ctx.send("Your current locale is set to `{0}`.".format(get))

    @locale.command()
    async def set(self, ctx, *, locale):
        """Sets your active locale."""
        if locale not in i18n.locales:
            return await ctx.send("Couldn't find that locale.")
        await self.bot.redis.set(f"locale:{ctx.author.id}", locale)
        await ctx.send(self.bot.tick_yes)

    @locale.command()
    async def list(self, ctx):
        """Lists all valid locales."""
        await ctx.send(", ".join(sorted(i18n.locales)))


def setup(bot):
    bot.add_cog(Locale(bot))
