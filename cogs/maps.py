from discord.ext import commands
from .utils.mapping import MapManager


class Maps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mapmgr = MapManager()


def setup(bot):
    bot.add_cog(Maps(bot))
