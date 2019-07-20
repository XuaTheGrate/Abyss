import asyncio
import itertools
import random
from operator import itemgetter

import discord
from discord.ext import commands

from .utils import lookups, scripts, i18n
from .utils.objects import Player, Skill

import collections


FMT = {
    'weak': 'Weak to:',
    'resist': 'Resists:',
    'immune': 'Immune to:',
    'absorb': 'Absorbs:',
    'reflect': 'Reflects:'
}


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
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def create(self, ctx):
        """Creates a new player.
        You will be given a random demon to use throughout your journey."""
        if ctx.player:
            return await ctx.send(_("You already own a player."))

        msg = _("This appears to be a public server. The messages sent can get spammy, or cause ratelimits.\n"
                "It is advised to use a private server/channel.")

        if sum(not m.bot for m in ctx.guild.members) > 100:
            await ctx.send(msg)
            await asyncio.sleep(5)

        task = self.bot.loop.create_task(scripts.do_script(ctx, "creation", i18n.current_locale.get()))

        if not await self.bot.is_owner(ctx.author):
            demon = random.choice(list(self._base_demon_cache.keys()))
            data = self._base_demon_cache[demon]
            while data['testing']:
                demon = random.choice(list(self._base_demon_cache.keys()))
                data = self._base_demon_cache[demon]
        else:
            data = self._base_demon_cache['debug']
            data['testing'] = True
        data['owner'] = ctx.author.id
        data['exp'] = 0
        player = Player(**data)

        await task
        if not task.result():
            return

        self.players[ctx.author.id] = player
        player._populate_skills(self.bot)
        await player.save(self.bot)

        await ctx.send(
            _("???: The deed is done. You have been given the demon `{player.name}`. Use its power wisely...").format(
                player=player))

    @commands.command()
    async def status(self, ctx):
        """Gets your current players status."""
        if not ctx.player:
            return await ctx.send(_("You don't own a player."))
        embed = discord.Embed(title=ctx.player.name, colour=lookups.TYPE_TO_COLOUR[ctx.player.specialty.name.lower()])
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url_as(format="png", size=32))
        res = {}
        for key, value_iter in itertools.groupby(list(ctx.player.resistances.items()), key=itemgetter(1)):
            res.setdefault(key.name.lower(), []).extend([v[0].name.lower() for v in value_iter])
        res.pop("normal", None)
        spec = f"{lookups.TYPE_TO_EMOJI[ctx.player.specialty.name.lower()]} {ctx.player.specialty.name.title()}"
        res_fmt = "\n".join([f"{FMT[k]}: {' '.join(map(lambda x: str(lookups.TYPE_TO_EMOJI[x.lower()]), v))}" for k, v in res.items()])
        arcana = lookups.ROMAN_NUMERAL[ctx.player.arcana.value]
        desc = _("""**{arcana}** {ctx.player.arcana.name}

{ctx.player.description}

Specializes in {spec} type skills.

__Resistances__
{res_fmt}
""").format(**locals())
        embed.description = desc
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Players(bot))
