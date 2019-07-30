import asyncio
import random

from discord.ext import commands

from .utils import battle as bt, i18n, formats


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
                log.debug(f"got uid {uid}")
                b = self.battles.pop(uid)
                await b.stop()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.bot.send_error(f""">>> Task_kill error occured
```py
{formats.format_exc(e)}
```""")
            log.warning(f"task died with {e}")
            self._task = self.bot.loop.create_task(self.task_kill())

    async def cog_command_error(self, ctx, error, battle=None):
        if battle:
            await self._queue.put(battle)
            if not error:
                return
            m = f""">>> Error occured during battle.
User: {battle.player.owner} ({battle.player.owner.id})
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
    async def _encounter(self, ctx, *names):
        enemies = []
        for name in names:
            encounter = await self.bot.db.abyss.encounters.find_one({"name": name})
            enemies.append(bt.Enemy(**encounter, bot=self.bot))
        self.battles[ctx.author.id] = bt.WildBattle(ctx.player, ctx, *enemies)

    @commands.command()
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def encounter(self, ctx):
        if ctx.author.id in self.battles:
            return await ctx.message.add_reaction(self.bot.tick_no)

        if not ctx.player:
            return await ctx.send(_("You don't own a player."))

        if random.randint(1, 100) > 75:
            return await ctx.send(_("You searched around but nothing appeared."))

        around = await self.bot.redis.get(f"keys@{ctx.author.id}")
        if around is None:
            raise RuntimeError("story not set :excusemewtf:")

        around = int(around)
        encounters = await self.bot.db.abyss.encounters.find(
            {"$where": f"""
var fuckJS = function(obj) {{
    return Math.abs((obj['level']+{around})-5<=3);
}}
return fuckJS(this)"""}).to_list(None)
        if not encounters:
            raise RuntimeError("`{'$where': lambda d: abs((d['level']+around)-5) <= 3}` -> None")

        enc = random.choice(encounters)

        if any(s not in self.bot.players.skill_cache for s in enc['moves']):
            raise RuntimeError(
                f"missing skills: {', '.join(filter(lambda d: d not in self.bot.players.skill_cache, enc['moves']))}")

        enemy = bt.Enemy(**enc, bot=self.bot)
        await ctx.send(_("You searched around and found a **{0}**!").format(enemy.name))
        self.battles[ctx.author.id] = bt.WildBattle(ctx.player, ctx, enemy)


def setup(bot):
    bot.add_cog(BattleSystem(bot))
