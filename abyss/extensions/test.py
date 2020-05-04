from discord.ext import commands

from .utils.checks import better_cooldown


class TestCommands(commands.Cog, command_attrs={"hidden": True}):
    uses = 0

    @commands.command()
    @better_cooldown(3, 60, commands.BucketType.user)
    async def cooldown_test(self, ctx):
        self.uses += 1
        if self.uses % 2 == 0:
            raise Exception
        await ctx.send("ok")


def setup(bot):
    bot.add_cog(TestCommands())
