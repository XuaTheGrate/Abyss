import asyncio
import random
import datetime
from discord.ext import commands
from .utils.objects import Player, Skill

import collections


class LRUDict(collections.OrderedDict):
    """a dictionary with fixed size, sorted by last use

    credit to lambda#0987"""

    def __init__(self, size, bot):
        super().__init__()
        self.size = size
        self.bot = bot

    def __getitem__(self, key):
        # move key to the end
        result = super().__getitem__(key)
        del self[key]
        super().__setitem__(key, result)
        return result

    def __setitem__(self, key, value):
        try:
            # if an entry exists at key, make sure it's moved up
            del self[key]
        except KeyError:
            # we only need to do this when adding a new key
            if len(self) >= self.size:
                k, v = self.popitem(last=False)
                asyncio.run_coroutine_threadsafe(v.save(self.bot), loop=self.bot.loop)

        super().__setitem__(key, value)


class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = LRUDict(20, bot)
        self.skill_cache = {}
        self._base_demon_cache = {}
        self._skill_cache_task = self.bot.loop.create_task(self.cache_skills())
        self.bot.unload_tasks[self] = self._unloader_task = self.bot.loop.create_task(self.flush_cached_players())

    def __repr__(self):
        return f"<PlayerHandler {len(self.players)} loaded,\n\t{self._skill_cache_task!r}>"

    def cog_unload(self):
        task = self.bot.unload_tasks.pop(self)
        task.cancel()

    async def cog_before_invoke(self, ctx):
        try:
            ctx.player = self.players[ctx.author.id]
        except KeyError:
            data = await self.bot.db.adventure2.accounts.find_one({"owner": ctx.author.id})
            if not data:
                ctx.player = None
                return
            ctx.player = self.players[ctx.author.id] = player = Player(**data)
            player._populate_skills(self.bot)

    async def flush_cached_players(self):
        await self.bot.wait_for("logout")
        for i in range(len(self.players)):
            _, player = self.players.popitem()
            await player.save(self.bot)

    async def cache_skills(self):
        await self.bot.prepared.wait()

        async for skill in self.bot.db.adventure2.skills.find():
            skill.pop("_id")
            self.skill_cache[skill['name']] = Skill(**skill)

        async for demon in self.bot.db.adventure2.basedemons.find():
            demon.pop("_id")
            self._base_demon_cache[demon['name']] = demon

    # -- finally, some fucking commands -- #

    @commands.command()
    async def create(self, ctx):
        """Creates a new player.
        You will be given a random demon to use throughout your journey.
        You cannot change this, it is the same demon even if you reset your account.

        Todo:
        If you are a premium user, you can choose your demon.
        Otherwise, your demon will be fixed."""
        if ctx.player:
            return await ctx.send("You already own a player.")

        msg = _("This appears to be a public server. The messages sent can get spammy, or cause ratelimits.\n"
                "It is advised to use a private server/channel.")

        if sum(not m.bot for m in ctx.guild.members) > 100:
            await ctx.send(msg)
            await asyncio.sleep(5)

        for msg in reversed(await self.bot.redis.smembers("messages:0")):
            n = await ctx.send(msg.decode())
            await n.add_reaction('\u25b6')
            if not await self.bot.continue_script(n, ctx.author):
                return

        random.seed(ctx.author.id)
        demon = random.choice(list(self._base_demon_cache.keys()))
        random.seed(int(datetime.datetime.utcnow().timestamp()))
        data = self._base_demon_cache[demon]
        data['owner'] = ctx.author.id
        data['exp'] = 0
        player = Player(**data)
        player._populate_skills(self.bot)
        await player.save(self.bot)

        await ctx.send(
            _("???: The deed is done. You have been given the demon `{player.name}`. Use its power wisely..."))


def setup(bot):
    bot.add_cog(Players(bot))
