import math
import random
import re

from .enums import SkillType, ResistanceModifier


class Enemy:
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random

    # true battles will avoid skills that you are immune to,
    # and aim for skills that you are weak to / support themself
    def __init__(self, **data):
        bot = data.pop('bot')
        self.name = data.pop('name')
        self.level = data.pop('level')
        self.skills = [bot.players.skill_cache[n] for n in data.pop('moves')]
        self.strength, self.magic, self.endurance, self.agility, self.luck = data.pop('stats')
        self.resistances = dict(zip(SkillType, map(ResistanceModifier, data.pop("resistances"))))
        self._damage_taken = 0
        self._sp_used = 0

    def __repr__(self):
        return "<Enemy>"

    def __str__(self):
        return self.name

    @property
    def hp(self):
        return self.max_hp - self._damage_taken

    @hp.setter
    def hp(self, value):
        if self.hp - value <= 0:
            self._damage_taken = self.max_hp
        else:
            self._damage_taken += value

    @property
    def max_hp(self):
        return math.ceil(20 + self.endurance + (4.7 * self.level))

    @property
    def sp(self):
        return self.max_sp - self._sp_used

    @sp.setter
    def sp(self, value):
        if self.sp - value <= 0:
            self._sp_used = self.max_sp
        else:
            self._sp_used += value

    @property
    def max_sp(self):
        return math.ceil(10 + self.magic + (3.6 * self.level))

    def is_fainted(self):
        return self.hp <= 0

    def exp(self):
        return math.ceil(self.level ** 3 / random.uniform(1, 3))


class BattleResult:
    def __init__(self):
        self.flee = False
        self.fainted = False
        self.exp_gained = 0  # always 0 if flee or fainted is True
        self.cash_gained = 0  # negative if fainted is True, or 0 if flee is True
        self.timeout = False

    def __repr__(self):
        return (f"<BattleResult {'+' if self.timeout else '-'}timeout, "
                f"{'+' if self.flee else '-'}ran away, "
                f"{'+' if self.fainted else '-'}fainted, "
                f"{'-' if self.fainted else ''}{self.cash_gained}$ earned, "
                f"{self.exp_gained} EXP earned>")


import discord
from discord.ext import ui, tasks

from . import lookups

# exp = ceil(level ** 3 / uniform(1, 3))


def confirm_not_dead(battle):
    return not battle.enemy.is_fainted() and not battle.player.is_fainted()


class InitialSession(ui.Session):
    def __init__(self, battle):
        super().__init__(timeout=180)
        self.battle = battle
        self.player = battle.player
        self.enemy = battle.enemy
        self.bot = battle.ctx.bot
        self.result = None  # dict, {"type": "fight/run", data: [whatever is necessary]}
        self.add_command(self.select_skill, "("+"|".join(map(str, self.player.skills))+")")

    async def select_skill(self, message, skill):
        obj = self.bot.players.skill_cache[skill.title()]
        self.result = {"type": "fight", "data": {"skill": obj}}
        await self.stop()

    async def handle_timeout(self):
        self.result = {"type": "run", "data": {"timeout": True}}
        await self.stop()

    async def on_message(self, message):
        if message.channel.id != self.message.channel.id:
            return

        if message.author.id not in self.allowed_users:
            return

        for pattern, command in self.__ui_commands__.items():
            match = re.fullmatch(pattern, message.content, flags=re.IGNORECASE)
            if not match:
                continue

            callback = command.__get__(self, self.__class__)
            await self._queue.put((callback, message, *match.groups()))
            break

    @property
    def header(self):
        return f"""[{self.player.owner.name}] {self.player.name} VS {self.enemy.name} [Wild]
{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP"""

    def get_home_content(self):
        return _(f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{INFORMATION SOURCE} Help
\N{RUNNER} Escape
""")

    async def send_initial_message(self):
        return await self.context.send(self.get_home_content())

    @ui.button('\N{CROSSED SWORDS}')
    async def fight(self, __):
        skills = "\n".join(
            [f"{lookups.TYPE_TO_EMOJI[s.type.name.lower()]} {s}" for s in self.player.skills]
        )
        await self.message.edit(content=_(
            f"{self.header}\n\n{skills}\n\n> Use \N{HOUSE BUILDING} to go back"), embed=None)

    @ui.button("\N{INFORMATION SOURCE}")
    async def info(self, __):
        embed = discord.Embed(title=_("How to: Interactive Battle"))
        embed.description = _("""Partially ported from Adventure, the battle system has been revived!
Various buttons have been reacted for use, but move selection requires you to send a message.
\N{CROSSED SWORDS} Brings you to the Fight menu, where you select your moves.
\N{INFORMATION SOURCE} Shows this page.
\N{RUNNER} Runs from the battle. Useful if you don't think you can beat this enemy.
\N{HOUSE BUILDING} Brings you back to the home screen.

For more information regarding battles, see `$faq battles`.""")
        await self.message.edit(content="", embed=embed)

    @ui.button("\N{RUNNER}")
    async def escape(self, _):
        chance = 75 - (self.enemy.level - self.player.level)
        if random.randint(1, 100) < chance:
            self.result = {"type": "run", "data": {"success": True}}
        else:
            self.result = {"type": "run", "data": {"success": False}}
        return await self.stop()

    @ui.button("\N{HOUSE BUILDING}")
    async def ret(self, _):
        await self.message.edit(content=f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{INFORMATION SOURCE} Help
\N{RUNNER} Escape""", embed=None)


class WildBattle:
    def __init__(self, player, enemy, ctx):
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").yayeet
        self.player = player
        self.enemy = enemy
        self.menu = InitialSession(self)
        self.main.start(self)

    @tasks.loop()
    async def main(self, _):
        if not confirm_not_dead(self):
            self.main.stop()
            return
        await self.menu.start(self.ctx)
        result = self.menu.result
        if result is None:
            raise RuntimeError("thats not normal")
        await self.ctx.send("need to handle messages but if you got this far ur the best programmer")

    @main.after_loop
    async def post_battle_complete(self):
        if self.main.failed():
            err = self.main.exception()
            await self.ctx.invoke(self.cmd, battle=self, err=err)
            return
        # do exp stuff here
        await self.ctx.invoke(self.cmd, battle=self)
