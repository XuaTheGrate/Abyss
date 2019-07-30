import asyncio
import math
import random
import re
from contextlib import suppress
from itertools import cycle

from .player import Player

NL = '\n'


class Enemy(Player):
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random

    # true battles will avoid skills that you are immune to,
    # and aim for skills that you are weak to / support themself
    def __init__(self, **kwargs):
        kwargs['skills'] = kwargs.pop("moves")
        self.level_ = kwargs.pop("level")
        super().__init__(**kwargs)

    def __repr__(self):
        return "<Enemy>"

    def __str__(self):
        return self.name

    @property
    def exp(self):
        return math.ceil(self.level_ ** 3 / random.uniform(1, 3))


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
    if battle.player.is_fainted():
        return False
    return not all(e.is_fainted() for e in battle.enemies)


class TargetSession(ui.Session):
    def __init__(self, *enemies):
        super().__init__(timeout=180)
        self.enemies = {
            f"{c+1}\u20e3": enemies[c] for c in range(len(enemies))
        }
        self.result = None
        for e in self.enemies.keys():
            self.add_button(self.button, e)

    async def stop(self):
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        await super().stop()

    async def button(self, payload):
        try:
            self.result = self.enemies[str(payload.emoji)]
        finally:
            await self.stop()


class InitialSession(ui.Session):
    def __init__(self, battle):
        super().__init__(timeout=180)
        self.battle = battle
        self.player = battle.player
        self.enemies = battle.enemies
        self.bot = battle.ctx.bot
        self.result = None  # dict, {"type": "fight/run", data: [whatever is necessary]}
        self.add_command(self.select_skill, "("+"|".join(map(str, self.player.skills))+")")

    async def stop(self):
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        await super().stop()

    async def select_target(self):
        menu = TargetSession(*filter(lambda d: not d.is_fainted(), self.enemies))
        await menu.start()
        if not menu.result:
            raise RuntimeError
        return menu.result

    async def select_skill(self, message, skill):
        obj = self.bot.players.skill_cache[skill.title()]
        target = await self.select_target()
        self.result = {"type": "fight", "data": {"skill": obj, "target": target}}
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
        return f"""[{self.player.owner.name}] {self.player.name}
VS
{NL.join(f"[Wild] {e}" for e in self.enemies)}

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
        chance = 75 - (max(self.enemies, key=lambda e: e.level).level - self.player.level)
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
    def __init__(self, player, ctx, *enemies, ambush=False, ambushed=False):
        assert not all((ambush, ambushed))  # dont set ambush AND ambushed to True
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").cog_command_error
        self.player = player
        self.enemies = sorted(enemies, key=lambda e: e.agility, reverse=True)
        self.menu = InitialSession(self)
        self.ambush = True if ambush else False if ambushed else None
        # True -> player got the initiative
        # False -> enemy got the jump
        # None -> proceed by agility
        if self.ambush is True:
            self.order = cycle([self.player, *self.enemies])
        elif self.ambush is False:
            self.order = cycle([*self.enemies, self.player])
        else:
            self.order = cycle(sorted([self.player, *self.enemies], key=lambda i: i.agility, reverse=True))
        self.main.start(self)

    async def stop(self):
        self.main.stop()
        await self.menu.stop()

    async def handle_player_choices(self):
        await self.menu.start(self.ctx)
        result = self.menu.result
        if result is None:
            raise RuntimeError("thats not normal")
        await self.ctx.send(result)

    async def handle_enemy_choices(self, enemy):
        await self.ctx.send(enemy)

    @tasks.loop()
    async def main(self, _):
        if not confirm_not_dead(self):
            await self.stop()
            return
        nxt = next(self.order)
        if not isinstance(nxt, Enemy):
            return await self.handle_player_choices()
        if not nxt.is_fainted():
            await self.handle_enemy_choices(nxt)

    @main.before_loop
    async def pre_battle_start(self, __):
        if self.ambush is True:
            await self.ctx.send(_("{0} {1}! You surprised them!").format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies')))
        elif self.ambush is False:
            await self.ctx.send(_("It's an ambush! There are {0} {1}!").format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies')))
        else:
            await self.ctx.send(_("There are {0} {1}! Attack!").format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies')))

    @main.after_loop
    async def post_battle_complete(self):
        if self.main.failed():
            err = self.main.exception()
        else:
            err = None
        await self.cmd(self.ctx, err, battle=self)
