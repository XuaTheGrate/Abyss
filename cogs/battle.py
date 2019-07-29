import asyncio
import random
import uuid

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
                self.battles.pop(uid)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.bot.send_error(f""">>> Task_kill error occured
```py
{formats.format_exc(e)}
```""")
            self._task = self.bot.loop.create_task(self.task_kill())

    async def cog_command_error(self, ctx, error):
        if isinstance(error, BattleException):
            m = f""">>> Error occured during battle.
User: {error.battle.player.owner} ({error.battle.player.owner.id})
Guild: {error.battle.ctx.guild} ({error.battle.ctx.guild.id})
Encounter: {error.battle.enemy}
```py
{formats.format_exc(error)}
```"""
            await ctx.send("An internal error occured during battle. The battle has been terminated.")
            return await self.bot.send_error(m)

        self.bot.dispatch("command_error", ctx, error, force=True)

    @commands.command(hidden=True, name=str(uuid.uuid4()))
    async def yayeet(self, ctx, *, battle, err=None):
        """If you are reading this, message Xua with the code `185621` for a surprise."""
        await self._queue.put(battle.player.owner.id)
        if err:
            raise BattleException(battle, err)

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
            {"$where": lambda d: abs((d['level']+around)-5) <= 3}).to_list(None)
        if not encounters:
            raise RuntimeError("`{'$where': lambda d: abs((d['level']+around)-5) <= 3}` -> None")

        enc = random.choice(encounters)

        enemy = bt.Enemy(**enc)
        await ctx.send(_("You searched around and found a **{0}**!").format(enemy.name))
        self.battles[ctx.author.id] = bt.WildBattle(ctx.player, enemy, ctx)


def setup(bot):
    bot.add_cog(BattleSystem(bot))
