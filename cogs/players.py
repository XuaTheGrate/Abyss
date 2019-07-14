from discord.ext import commands

from .utils.objects import Player, Skill


class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.skill_cache = {}
        self._preparation_task = self.bot.loop.create_task(self.prepare_players())
        self._skill_cache_task = self.bot.loop.create_task(self.cache_skills())

    def __repr__(self):
        return f"<PlayerHandler {len(self.players)} loaded,\n" \
            f"\t{self._preparation_task!r}\n" \
            f"\t{self._skill_cache_task!r}>"

    async def prepare_players(self):
        await self.bot.prepared.wait()

        async for data in self.bot.db.adventure2.accounts.find():
            player = Player(**data)
            self.players[data['owner_id']] = player

    async def cache_skills(self):
        await self.bot.prepared.wait()

        async for skill in self.bot.db.adventure2.skills.find():
            self.skill_cache[skill['name']] = Skill(**skill)


def setup(bot):
    bot.add_cog(Players(bot))
