import asyncio
import random

import discord
import tabulate
from discord.ext import commands

from cogs.utils.formats import ensure_player
from .utils import battle as bt, formats


class BattleException(commands.CommandError):
    def __init__(self, battle, exc):
        self.battle = battle
        self.original = exc
        super().__init__()


class BattleSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.battles = {}
        self._task = self.bot.loop.create_task(self.task_kill())
        self._queue = asyncio.Queue()

    def cog_unload(self):
        self._task.cancel()

    async def task_kill(self):
        try:
            while True:
                uid = await self._queue.get()
                # log.debug(f"got uid {uid}")
                b = self.battles.pop(uid)
                await b.stop()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.bot.send_error(f""">>> Task_kill error occured
```py
{formats.format_exc(e)}
```""")
            self.bot.log.warning(f"task died with {e}")
            self._task = self.bot.loop.create_task(self.task_kill())

    async def cog_command_error(self, ctx, error, battle=None):
        if battle:
            await self._queue.put(battle.players[0].owner.id)
            if not error:
                return
            m = f""">>> Error occured during battle.
{battle.players}
Guild: {battle.ctx.guild} ({battle.ctx.guild.id})
Encounter: {list(map(str, battle.enemies))}
```py
{formats.format_exc(error)}
```"""
            await ctx.send("An internal error occured during battle. The battle has been terminated.")
            return await self.bot.send_error(m)

        self.bot.dispatch("command_error", ctx, error, force=True)

    @commands.command(hidden=True)
    @commands.is_owner()
    @ensure_player
    async def _encounter(self, ctx, *names):
        enemies = []
        for name in names:
            encounter = await self.bot.db.abyss.encounters.find_one({"name": name})
            e = bt.Enemy(**encounter)
            await e._populate_skills(self.bot)
            e.skills.remove(self.bot.players.skill_cache['Guard'])
            enemies.append(e)
        self.battles[ctx.author.id] = bt.WildBattle(ctx.player, ctx, *enemies)

    @commands.command()
    @ensure_player
    @commands.cooldown(5, 120, commands.BucketType.user)
    async def encounter(self, ctx, *, ___=None, force=False):
        """Searches around for an encounter.

        Ignore the `___` and `force` variables, they are for internal use."""
        if ctx.author.id in self.battles:
            return await ctx.message.add_reaction(self.bot.tick_no)

        if not ctx.player:
            return await ctx.send("You don't own a player.")

        if not force and random.randint(1, 100) > 75:
            return await ctx.send("You searched around but nothing appeared.")

        # around = await self.bot.redis.get(f"keys@{ctx.author.id}")
        # if around is None:
        # raise RuntimeError("story not set :excusemewtf:")

        encounters = await self.bot.db.abyss.encounters.find({
            "name": {"$in": ctx.player.map.areas[ctx.player.area]['encounters']}
        }).to_list(None)

        enc = random.choices(encounters, k=random.randint(1, 3))

        enemies = [await bt.Enemy(**e, bot=self.bot)._populate_skills(self.bot) for e in enc]

        fastest = max(enemies, key=lambda e: e.agility)
        weights = [50, 50, 50]
        weights[0] += fastest.agility - ctx.player.agility
        weights[2] -= fastest.agility - ctx.player.agility
        self.bot.log.debug(
            f"encounter weights: {weights}, {random.choices([False, None, True], k=10, weights=weights)}")
        ambush = random.choices([False,  # Enemy advantage
                                 None,  # Regular batle
                                 True],  # Player advantage
                                k=1, weights=weights)[0]

        self.battles[ctx.author.id] = bt.WildBattle(ctx.player, ctx, *enemies, ambush=ambush)

    @commands.command(enabled=False)
    @ensure_player
    async def pvp(self, ctx, *, user: discord.Member):
        try:
            p2 = self.bot.players.players[user.id]
        except KeyError:
            # todo: cache the player
            return await ctx.send("users player is not loaded.")
        battle = bt.PVPBattle(ctx, teama=(ctx.player,), teamb=(p2,))
        self.battles[ctx.author.id] = battle
        await ctx.send(f'> {ctx.author.display_name} VS {user}')

    @commands.group(hidden=True)
    @commands.is_owner()
    @ensure_player
    async def custom(self, ctx):
        pass

    @custom.command()
    async def new(self, ctx):
        valid = [m['name'] async for m in self.bot.db.abyss.encounters.find()]
        data = tabulate.tabulate([valid[x:x + 4] for x in range(0, len(valid), 4)])
        await ctx.send("You'll need a base demon to go off of. Select one from here:")
        t = self.bot.loop.create_task(ctx.send_as_paginator(data, codeblock=True))
        nvalid = list(map(str.lower, valid))
        choice = None

        while True:
            try:
                select = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
            except asyncio.TimeoutError:
                t.cancel()
                return
            if select.content.lower() not in nvalid:
                await ctx.send("Couldn't find that one, try another.", delete_after=5)
                continue
            else:
                choice = select.content.lower()
                t.cancel()
                break

        # {'_id': ObjectId('5d3befc9ed9940c2bbd6e9ea'), 'name': 'Arsene',
        # 'moves': ['Adverse Resolve', 'Cleave', 'Dream Needle', 'Eiha', 'Sukunda'],
        # 'stats': [2, 2, 2, 3, 1], 'level': 1, 'resistances': [2, 2, 2, 3, 2, 2, 2, 2, 3, 1],
        # 'maps': [754265], 'id': 16,
        # 'desc': "..."}

        demondata = await self.bot.db.abyss.encounters.find_one({"name": valid[nvalid.index(choice)]})
        nd = {'name': demondata['name'], 'desc': demondata['desc']}
        embed = discord.Embed(title=demondata['name'], description=demondata['desc'])
        await ctx.send(f"Great, let's use {demondata['name']}. Next you need to assign a level. Any number between 1-99 is valid.")
        m = await self.bot.wait_for("message", check=lambda m: m.content.isdigit() and 0 < int(m.content) < 100)
        embed.add_field(name='Level', value=m.content)
        nd['level'] = int(m.content)


def setup(bot):
    bot.add_cog(BattleSystem(bot))
