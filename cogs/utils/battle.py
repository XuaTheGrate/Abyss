import asyncio
import math
import random
import re
from contextlib import suppress
from itertools import cycle

from .player import Player
from .enums import ResistanceModifier

NL = '\n'


class Enemy(Player):
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random

    # true battles will avoid skills that you are immune to,
    # and aim for skills that you are weak to / support themself
    def __init__(self, **kwargs):
        kwargs['skills'] = kwargs.pop("moves")
        self.level_ = kwargs.pop("level")
        kwargs['arcana'] = 0
        kwargs['exp'] = 0
        kwargs['owner'] = 0
        kwargs['specialty'] = 'almighty'
        super().__init__(**kwargs)

    def __repr__(self):
        return "<Enemy>"

    def __str__(self):
        return self.name

    def get_exp(self):
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
            log.debug(f"added button for {self.enemies[e]}")
            self.add_button(self.button, e)

    async def send_initial_message(self):
        c = [_("Pick a target!\n")]
        c.extend([f"{a} {b.name}" for a, b in self.enemies.items()])
        log.debug("target session initial message")
        return await self.context.send(NL.join(c))

    async def stop(self):
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        log.debug("le stop()")
        await super().stop()

    async def button(self, payload):
        try:
            log.debug("le button")
            self.result = self.enemies[str(payload.emoji)]
        finally:
            await self.stop()


class InitialSession(ui.Session):
    def __init__(self, battle):
        super().__init__(timeout=180)
        log.debug("initial session init")
        self.battle = battle
        self.player = battle.player
        self.enemies = battle.enemies
        self.bot = battle.ctx.bot
        self.result = None  # dict, {"type": "fight/run", data: [whatever is necessary]}
        self.add_command(self.select_skill, "("+"|".join(map(str, self.player.skills))+")")

    async def stop(self):
        log.debug("initialsession stop()")
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        await super().stop()

    async def select_target(self):
        log.debug("initialsession target selector")
        menu = TargetSession(*[e for e in self.enemies if not e.is_fainted()])
        await menu.start(self.context)
        if not menu.result:
            log.debug("no result")
            raise RuntimeError
        log.debug(f"result: {menu.result!r}")
        return menu.result

    async def select_skill(self, message, skill):
        obj = self.bot.players.skill_cache[skill.title()]
        target = await self.select_target()
        self.result = {"type": "fight", "data": {"skill": obj, "target": target}}
        log.debug(f"select skill: {self.result}")
        await self.stop()

    async def handle_timeout(self):
        self.result = {"type": "run", "data": {"timeout": True}}
        log.debug("timeout")
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
            log.debug("callback found for message")
            callback = command.__get__(self, self.__class__)
            await self._queue.put((callback, message, *match.groups()))
            break

    @property
    def header(self):
        return f"""[{self.player.owner.name}] {self.player.name}
VS
{NL.join(f"[Wild] {e}" if not e.is_fainted() else f"[Wild] ~~{e}~~" for e in self.enemies)}

{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP"""

    def get_home_content(self):
        return _(f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{INFORMATION SOURCE} Help
\N{RUNNER} Escape
""")

    async def send_initial_message(self):
        log.debug("sent initial message")
        return await self.context.send(self.get_home_content())

    @ui.button('\N{CROSSED SWORDS}')
    async def fight(self, __):
        log.debug("fight() called")
        skills = []
        for skill in self.player.skills:
            e = lookups.TYPE_TO_EMOJI[skill.type.name.lower()]
            if skill.uses_sp:
                cost = skill.cost
                can_use = self.player.sp >= cost
                t = 'SP'
            else:
                cost = self.player.max_hp // skill.cost
                can_use = self.player.max_hp > cost
                t = 'HP'
            if can_use:
                skills.append(f"{e} {skill} ({cost} {t})")
            else:
                skills.append(f"{e} ~~{skill} ({cost} {t})~~")

        await self.message.edit(content=_(
            f"{self.header}\n\n{NL.join(skills)}\n\n> Use \N{HOUSE BUILDING} to go back"), embed=None)

    @ui.button("\N{INFORMATION SOURCE}")
    async def info(self, __):
        log.debug("info() called")
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
        log.debug("escape() called")
        chance = 75 - (max(self.enemies, key=lambda e: e.level).level - self.player.level)
        if random.randint(1, 100) < chance:
            self.result = {"type": "run", "data": {"success": True}}
        else:
            self.result = {"type": "run", "data": {"success": False}}
        return await self.stop()

    @ui.button("\N{HOUSE BUILDING}")
    async def ret(self, _):
        log.debug("ret() called")
        await self.message.edit(content=f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{INFORMATION SOURCE} Help
\N{RUNNER} Escape""", embed=None)


res_msgs = {
    ResistanceModifier.NORMAL: "__{demon}__ used `{skill}`! __{tdemon}__ took {damage} damage!",
    ResistanceModifier.WEAK: "__{demon}__ used `{skill}`, and __{tdemon}__"
                             " is **weak** to {skill.type.name} attacks! __{tdemon}__ took {damage} damage!",
    ResistanceModifier.ABSORB: "__{demon}__ used `{skill}`, but __{tdemon}__ "
                               "**absorbs** {skill.type.name} attacks! __{tdemon}__ healed for {damage} damage!",
    ResistanceModifier.RESIST: "__{demon}__ used `{skill}`, but __{tdemon}__ **resists**"
                               " {skill.type.name} attacks. __{tdemon}__ took {damage} damage!",
    ResistanceModifier.IMMUNE: "__{demon}__ used `{skill}`, but __{tdemon}__ is **immune**"
                               " to {skill.type.name} attacks."
}

MSG_MISS = "__{demon}__ used `{skill}`, but __{tdemon}__ evaded the attack!"

REFL_BASE = "__{demon}__ used `{skill}`, but __{tdemon}__ **reflects** {skill.type.name} attacks! "
refl_msgs = {
    ResistanceModifier.NORMAL: "__{demon}__ took {damage} damage!",
    ResistanceModifier.WEAK: "__{demon}__ is **weak** to {skill.type.name} attacks and took {damage} damage!",
    ResistanceModifier.ABSORB: "__{demon}__ **absorbs** {skill.type.name} attacks and healed for {damage} HP!",
    ResistanceModifier.IMMUNE: "__{demon}__ is **immune** to {skill.type.name} attacks!",
    ResistanceModifier.RESIST: "__{demon}__ **resists** {skill.type.name} attacks and took {damage} damage!"
}


def get_message(resistance, reflect=False):
    if reflect:
        return _(REFL_BASE) + _(refl_msgs[resistance])
    return _(res_msgs[resistance])


class ListCycle:
    def __init__(self, iterable):
        self._iter = iterable
        self.current = 0
        self.max = len(iterable)-1

    def active(self):
        return self._iter[self.current]

    def cycle(self):
        if self.current == self.max:
            self.current = 0
        else:
            self.current += 1

    def remove(self, item):
        self._iter.remove(item)
        if self.current == self.max:
            self.current -= 1
        self.max = len(self._iter)-1

    def __next__(self):
        return self.active()


class WildBattle:
    def __init__(self, player, ctx, *enemies, ambush=False, ambushed=False):
        assert not all((ambush, ambushed))  # dont set ambush AND ambushed to True
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").cog_command_error
        self.player = player
        self.menu = None
        self.enemies = sorted(enemies, key=lambda e: e.agility, reverse=True)
        self.ambush = True if ambush else False if ambushed else None
        self._stopping = False
        # True -> player got the initiative
        # False -> enemy got the jump
        # None -> proceed by agility
        if self.ambush is True:
            self.order = [self.player, *self.enemies]
        elif self.ambush is False:
            self.order = [*self.enemies, self.player]
        else:
            self.order = sorted([self.player, *self.enemies], key=lambda i: i.agility, reverse=True)
        self.order = ListCycle(self.order)
        self.main.start()

    async def stop(self):
        self._stopping = True
        self.main.stop()
        with suppress(AttributeError):
            await self.menu.stop()

    async def handle_player_choices(self):
        log.debug("get menu")
        self.menu = InitialSession(self)
        log.debug("got menu")
        await self.menu.start(self.ctx)
        log.debug("started menu")
        result = self.menu.result
        log.debug("got player result")
        await self.menu.stop()
        log.debug("stopped menu")
        if result is None and not self._stopping:
            log.debug("result was none")
            raise RuntimeError("thats not normal")

        if result['type'] == 'run':
            if result['data'].get('timeout', False) or result['data'].get('success', True):
                await self.ctx.send(_("> You successfully ran away!"))
                await self.stop()
            else:
                await self.ctx.send(_("> You failed to run!"))
            return

        # type must be fight
        skill = result['data']['skill']

        if skill.uses_sp:
            if self.player.sp < skill.cost:
                await self.ctx.send(_("You don't have enough SP for this move!"))
                return
            self.player.sp = skill.cost
        else:
            cost = self.player.max_hp // skill.cost
            if cost > self.player.hp:
                await self.ctx.send(_("You don't have enough HP for this move!"))
                return
            self.player.hp = cost

        target = result['data']['target']
        if not skill.is_damaging_skill:
            await self.ctx.send("unhandled atm")
        else:
            res = target.take_damage(self.player, skill)
            if res.miss:
                await self.ctx.send(_(MSG_MISS).format(demon=self.player, tdemon=target, skill=skill))
                return
            msg = get_message(res.resistance, res.was_reflected)
            if res.critical:
                msg = _("CRITICAL! ") + msg
            msg = msg.format(demon=self.player, tdemon=target, damage=res.damage_dealt, skill=skill)
            await self.ctx.send(msg)

    async def handle_enemy_choices(self, enemy):
        log.debug("handle_enemy_choices todo")
        await self.ctx.send(f"{enemy} did a thing (it didnt but it will)")

    @tasks.loop()
    async def main(self):
        log.debug("starting loop")
        if not confirm_not_dead(self):
            log.debug("confirm not dead failed, stopping")
            await self.stop()
            return
        nxt = self.order.active()
        if not isinstance(nxt, Enemy):
            log.debug("next: player")
            await self.handle_player_choices()
        else:
            if not nxt.is_fainted():
                log.debug("next enemy not fainted")
                await self.handle_enemy_choices(nxt)
            else:
                self.order.remove(nxt)
        self.order.cycle()

    @main.before_loop
    async def pre_battle_start(self):
        log.debug("pre battle, determining ambush")
        if self.ambush is True:
            log.debug("player initiative")
            await self.ctx.send(_("> {0} {1}! You surprised {2}!").format(
                len(self.enemies),
                _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('it') if len(self.enemies) == 1 else _('them')
            ))
        elif self.ambush is False:
            log.debug("enemy initiative")
            await self.ctx.send(_("> It's an ambush! There {2} {0} {1}!").format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')
            ))
        else:
            log.debug("regular initiative")
            await self.ctx.send(_("> There {2} {0} {1}! Attack!").format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')))

    @main.after_loop
    async def post_battle_complete(self):
        log.debug("complete")
        if self.main.failed():
            err = self.main.exception()
            log.debug(f"error occured: {err!r}")
        else:
            err = None
        await self.cmd(self.ctx, err, battle=self)
        await self.ctx.send("game over")
        log.debug("finish")
