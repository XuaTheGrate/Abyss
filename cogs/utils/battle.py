import re
from contextlib import suppress

from .objects import ListCycle
from .player import Player
from .skills import *

NL = '\n'

UNSUPPORTED_SKILLS = ['Dia', 'Diarama', 'Diarahan', 'Media', 'Mediarama', 'Mediarahan', 'Salvation',
                      'Fast Heal', 'Evil Touch', 'Evil Smile', 'Taunt',
                      'Abysmal Surge', 'Ominous Words', 'Growth 1', 'Growth 2', 'Growth 3',
                      'Cadenza', 'Oratorio', 'Pulinpa', 'Charge', 'Concentrate', 'Amrita Shower',
                      'Amrita Drop', 'Tetrakarn', 'Makarakarn', 'Brain Jack', 'Marin Karin',
                      'Fortify Spirit',
                      'Makajam', 'Makajamaon', 'Tentarafoo', 'Wage War', 'Dazzler',
                      'Nocturnal Flash', 'Dormina', 'Lullaby', 'Ambient Aid', 'Recarm', 'Samarecarm',
                      'Ailment Boost', 'Divine Grace', 'Rebellion', 'Revolution', 'Insta-Heal',
                      'Ali Dance']


class Enemy(Player):
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random
    # however they will learn not to use a move if you are immune to it

    # true battles will automatically avoid skills that you are immune to,
    # and aim for skills that you are weak to / support themself
    def __init__(self, **kwargs):
        kwargs['skills'] = kwargs.pop("moves")
        self.level_ = kwargs.pop("level")
        kwargs['arcana'] = 0
        kwargs['exp'] = 0
        kwargs['owner'] = 0
        kwargs['specialty'] = 'almighty'
        super().__init__(**kwargs)
        self.unusable_skills = []  # a list of names the ai has learned not to use since they dont work

    def get_exp(self):
        return math.ceil(self.level_ ** 3 / random.uniform(1, 3))

    def random_move(self):
        choices = list(
            filter(
                lambda s: s.type is not SkillType.PASSIVE and (
                    True if not s.uses_sp else s.cost <= self.sp
                ) and s.name not in self.unusable_skills,
                self.skills
            )
        )
        if not choices:
            return self.skills[0]  # 0 is always GenericAttack
        select = random.choice(choices)
        if select.uses_sp:
            if any(s.name == 'Spell Master' for s in self.skills):
                self.sp = select.cost / 2
            else:
                self.sp = select.cost
        return select


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
    def __init__(self, *targets, target):
        super().__init__(timeout=180)
        if target in ('enemy', 'ally'):
            self.targets = {
                f"{c+1}\u20e3": targets[c] for c in range(len(targets))
            }
            for e in self.targets.keys():
                # log.debug(f"added button for {self.enemies[e]}")
                self.add_button(self.button_enemy, e)
        elif target in ('enemies', 'self', 'allies'):
            self.targets = targets
            self.add_button(self.target_enemies, '<:tickYes:568613200728293435>')
        else:
            raise RuntimeError("unhandled target")
        self.result = None
        self.target = target

    async def send_initial_message(self):
        if self.target == 'enemy':
            c = ["**Pick a target!**\n"]
            # noinspection PyUnresolvedReferences
            c.extend([f"{a} {b.name}" for a, b in self.targets.items()])
            # log.debug("target session initial message")
            return await self.context.send(NL.join(c))
        elif self.target == 'enemies':
            c = ["**Targets all enemies**\n"]
            c.extend([str(e) for e in self.targets])
            return await self.context.send(NL.join(c))
        elif self.target == 'self':
            return await self.context.send("**You can only use this skill on yourself**")
        elif self.target == 'allies':
            c = ["**Targets all allies**\n"]
            c.extend([str(e) for e in self.targets])
            return await self.context.send(NL.join(c))
        elif self.target == 'ally':
            c = ["**Choose an ally!**\n"]
            c.extend([str(e) for e in self.targets])
            return await self.context.send(NL.join(c))

    async def stop(self):
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        # log.debug("le stop()")
        await super().stop()

    @ui.button("<:tickNo:568613146152009768>")
    async def cancel(self, _):
        self.result = 'cancel'
        await self.stop()

    async def button_enemy(self, payload):
        # log.debug("le button")
        # noinspection PyTypeChecker
        self.result = (self.targets[str(payload.emoji)],)
        await self.stop()

    async def target_enemies(self, _):
        self.result = self.targets
        await self.stop()


class InitialSession(ui.Session):
    def __init__(self, battle):
        super().__init__(timeout=180)
        # log.debug("initial session init")
        self.battle = battle
        self.player = battle.player
        self.enemies = battle.enemies
        self.bot = battle.ctx.bot
        self.result = None  # dict, {"type": "fight/run", data: [whatever is necessary]}
        self.add_command(self.select_skill, "("+"|".join(map(str, filter(
            lambda s: s.type is not SkillType.PASSIVE, self.player.skills)))+")")

    async def stop(self):
        # log.debug("initialsession stop()")
        with suppress(discord.HTTPException, AttributeError):
            await self.message.delete()
        await super().stop()

    async def select_target(self, target):
        # log.debug("initialsession target selector")
        if target in ('enemy', 'enemies'):
            menu = TargetSession(*[e for e in self.enemies if not e.is_fainted()], target=target)
        elif target == 'self':
            menu = TargetSession(self.player, target=target)
        elif target in ('ally', 'allies'):
            # this is a 1 player only battle, but for future reference this needs to return all allies
            menu = TargetSession(self.player, target=target)
        else:
            raise RuntimeError

        await menu.start(self.context)
        if not menu.result:
            # log.debug("no result")
            return 'cancel'
        # log.debug(f"result: {menu.result!r}")
        return menu.result

    async def select_skill(self, _, skill):
        obj = self.bot.players.skill_cache[skill.title()]
        if skill.lower() == 'guard':
            self.result = {"type": "fight", "data": {"skill": obj}}
            return await self.stop()
        target = await self.select_target(obj.target)
        if target != 'cancel':
            self.result = {"type": "fight", "data": {"skill": obj, "targets": target}}
            # log.debug(f"select skill: {self.result}")
            await self.stop()

    async def handle_timeout(self):
        self.result = {"type": "run", "data": {"timeout": True}}
        # log.debug("timeout")
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
            # log.debug("callback found for message")
            callback = command.__get__(self, self.__class__)
            await self._queue.put((callback, message, *match.groups()))
            break

    @property
    def header(self):
        return f"""(Turn {self.battle.turn_cycle})
[{self.player.owner.name}] {self.player.name}
VS
{NL.join(f"[Wild] {e}" if not e.is_fainted() else f"[Wild] ~~{e}~~" for e in self.enemies)}

{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP"""

    def get_home_content(self):
        return _(f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{BLACK QUESTION MARK ORNAMENT} Help
\N{RUNNER} Escape
""")

    async def send_initial_message(self):
        # log.debug("sent initial message")
        return await self.context.send(self.get_home_content())

    @ui.button('\N{CROSSED SWORDS}')
    async def fight(self, __):
        # log.debug("fight() called")
        skills = []
        for skill in self.player.skills:
            if skill.type is SkillType.PASSIVE:
                continue
            e = lookups.TYPE_TO_EMOJI[skill.type.name.lower()]
            if skill.uses_sp:
                cost = skill.cost
                if any(s.name == 'Spell Master' for s in self.player.skills):
                    cost /= 2
                can_use = self.player.sp >= cost
                t = 'SP'
            else:
                if skill.cost != 0:
                    cost = self.player.max_hp // skill.cost
                    if any(s.name == 'Arms Master' for s in self.player.skills):
                        cost /= 2
                else:
                    cost = 0
                can_use = self.player.max_hp > cost
                t = 'HP'
            if can_use:
                skills.append(f"{e} {skill} ({cost:.0f} {t})")
            else:
                skills.append(f"{e} ~~{skill} ({cost:.0f} {t})~~")

        await self.message.edit(content=_(
            f"{self.header}\n\n{NL.join(skills)}\n\n> Use \N{HOUSE BUILDING} to go back"), embed=None)

    @ui.button("\N{BLACK QUESTION MARK ORNAMENT}")
    async def info(self, __):
        # log.debug("info() called")
        embed = discord.Embed(title="How to: Interactive Battle")
        embed.description = _("""Partially ported from Adventure, the battle system has been revived!
Various buttons have been reacted for use, but move selection requires you to send a message.
\N{CROSSED SWORDS} Brings you to the Fight menu, where you select your moves.
\N{BLACK QUESTION MARK ORNAMENT} Shows this page.
\N{INFORMATION SOURCE} todo
\N{RUNNER} Runs from the battle. Useful if you don't think you can beat this enemy.
\N{HOUSE BUILDING} Brings you back to the home screen.

For more information regarding battles, see `$faq battle`.""")
        await self.message.edit(content="", embed=embed)

    @ui.button("\N{INFORMATION SOURCE}")
    async def status(self, __):
        pass

    @ui.button("\N{RUNNER}")
    async def escape(self, _):
        # log.debug("escape() called")
        chance = 75 - (max(self.enemies, key=lambda e: e.level).level - self.player.level)
        if random.randint(1, 100) < chance:
            self.result = {"type": "run", "data": {"success": True}}
        else:
            self.result = {"type": "run", "data": {"success": False}}
        return await self.stop()

    @ui.button("\N{HOUSE BUILDING}")
    async def ret(self, _):
        # log.debug("ret() called")
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

supp_msgs = [
    {  # False == 0, decrease
        StatModifier.TARU: "__{tdemon}__'s **attack** was lowered!",
        StatModifier.RAKU: "__{tdemon}__'s **defense** was lowered!",
        StatModifier.SUKU: "__{tdemon}__'s **evasion/accuracy** was lowered!"
    },
    {  # True == 1, increase
        StatModifier.TARU: "__{tdemon}__'s **attack** increased!",
        StatModifier.RAKU: "__{tdemon}__'s **defense** increased!",
        StatModifier.SUKU: "__{tdemon}__'s **evasion/accuracy** increased!"
    },
    "__{demon}__ used `{skill}`! "
]


def get_message(resistance, *, reflect=False, miss=False, critical=False):
    if reflect:
        return _(REFL_BASE) + _(refl_msgs[resistance])
    if miss:
        return _(MSG_MISS)
    msg = _(res_msgs[resistance])
    if resistance not in (ResistanceModifier.IMMUNE, ResistanceModifier.WEAK,
                          ResistanceModifier.ABSORB, ResistanceModifier.REFLECT) and critical:
        msg = "CRITICAL! " + msg
    return msg


class WildBattle:
    def __init__(self, player, ctx, *enemies, ambush=False, ambushed=False):
        assert not all((ambush, ambushed))  # dont set ambush AND ambushed to True
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").cog_command_error
        self.player = player
        self.menu = None
        self.turn_cycle = 0
        self.enemies = sorted(enemies, key=lambda e: e.agility, reverse=True)
        self.ambush = True if ambush else False if ambushed else None
        self._stopping = False
        self._ran = False
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
        await self.player.pre_turn_async(self)
        self.menu = InitialSession(self)
        await self.menu.start(self.ctx)
        result = self.menu.result
        await self.menu.stop()
        if result is None and not self._stopping:
            self.order.decycle()  # shitty way to do it but w.e
            return await self.stop()

        if self._stopping:
            return

        if result['type'] == 'run':
            if result['data'].get('timeout', False) or result['data'].get('success', True):
                await self.ctx.send("> You successfully ran away!")
                await self.stop()
                self._ran = True
            else:
                await self.ctx.send("> You failed to escape!")
            return

        # type must be fight
        skill = result['data']['skill']

        if skill.name == "Guard":
            self.player.guarding = True
            return

        targets = result['data']['targets']

        if skill.name in UNSUPPORTED_SKILLS:
            await self.ctx.send("this skill doesnt have a handler, this incident has been reported")
            self.ctx.bot.send_error(f"no skill handler for {skill}")
            self.order.decycle()
            return

        if skill.uses_sp:
            cost = skill.cost
            if any(s.name == 'Spell Master' for s in self.player.skills):
                cost /= 2
            if self.player.sp < cost:
                await self.ctx.send("You don't have enough SP for this move!")
                return self.order.decycle()
            self.player.sp = cost
        else:
            if skill.cost != 0:
                cost = self.player.max_hp // skill.cost
                if any(s.name == 'Arms Master' for s in self.player.skills):
                    cost /= 2
            else:
                cost = 0
            if cost > self.player.hp:
                await self.ctx.send("You don't have enough HP for this move!")
                return self.order.decycle()
            self.player.hp = cost

        if isinstance(skill, (StatusMod, ShieldSkill)):
            await self.ctx.send(f"__{self.player}__ used `{skill}`!")
            await skill.effect(self, targets)
            return

        weaks = []
        for target in targets:
            force_crit = 0

            for __ in range(random.randint(*skill.hits)):
                res = target.take_damage(self.player, skill, enforce_crit=force_crit)
                # this is to ensure crits only happen IF the first hit did land a crit
                # we use a Troolean:
                # 0: first hit, determine crit
                # 1: first hit passed, it was a crit
                # 2: first hit passed, was not a crit
                force_crit = 1 if res.critical else 2
                msg = get_message(res.resistance, reflect=res.was_reflected, miss=res.miss, critical=res.critical)
                msg = msg.format(demon=self.player, tdemon=target, damage=res.damage_dealt, skill=skill)
                await self.ctx.send(msg)
                if res.endured:
                    await self.ctx.send(f"> __{target}__ endured the hit!")

                weaks.append(res.did_weak)

        if all(weaks) and confirm_not_dead(self):
            self.order.decycle()
            await self.ctx.send("> Nice hit! Move again!")

    def filter_targets(self, skill, user):
        if skill.target in ('enemy', 'enemies'):
            if user is self.player:
                return [e for e in self.enemies if not e.is_fainted()]
            return self.player,
        elif skill.target == 'self':
            return user
        elif skill.target in ('allies', 'ally'):
            if user is self.player:
                return self.player,
            return [e for e in self.enemies if not e.is_fainted()]
        elif skill.target == 'all':
            return [self.player] + [e for e in self.enemies if not e.is_fainted()]

    async def handle_enemy_choices(self, enemy):
        await enemy.pre_turn_async(self)
        skill = enemy.random_move()
        if skill.name in UNSUPPORTED_SKILLS:
            await self.ctx.send(f"{enemy} used an unhandled skill ({skill.name}), skipping")
        else:
            targets = self.filter_targets(skill, enemy)
            if isinstance(skill, (StatusMod, ShieldSkill)):
                await self.ctx.send(f"__{enemy}__ used `{skill}`!")
                await skill.effect(self, targets)
                return

            if skill.name == 'Guard':
                await self.ctx.send(f"__{enemy}__ guarded!")
                enemy.guarding = True
                return

            res = self.player.take_damage(enemy, skill)

            if res.resistance in (
                ResistanceModifier.IMMUNE,
                ResistanceModifier.REFLECT,
                ResistanceModifier.ABSORB
            ):
                enemy.unusable_skills.append(skill.name)
                # the ai learns not to use it in the future, but still use it this turn

            msg = get_message(res.resistance, reflect=res.was_reflected, miss=res.miss, critical=res.critical)
            msg = msg.format(demon=enemy, tdemon=self.player, damage=res.damage_dealt, skill=skill)
            await self.ctx.send(msg)
            if res.did_weak:
                self.order.decycle()
                await self.ctx.send("> Watch out, {demon} is attacking again!".format(demon=enemy))

    @tasks.loop(seconds=1)
    async def main(self):
        # log.debug("starting loop")
        if not confirm_not_dead(self):
            # log.debug("confirm not dead failed, stopping")
            await self.stop()
            return
        nxt = self.order.active()
        if not isinstance(nxt, Enemy):
            # log.debug("next: player")
            if self.ambush and any(s.name == 'Heat Up' for s in self.player.skills):
                self.player.hp = -(self.player.max_hp * 0.05)
                self.player.sp = -10
            self.turn_cycle += 1
            await self.handle_player_choices()
        else:
            if not nxt.is_fainted():
                # log.debug("next enemy not fainted")
                if self.ambush is False and any(s.name == 'Heat Up' for s in nxt.skills):
                    nxt.hp = -(nxt.max_hp * 0.05)
                    nxt.sp = -10
                await self.handle_enemy_choices(nxt)
            else:
                self.order.remove(nxt)
        self.order.cycle()

    @main.before_loop
    async def pre_battle_start(self):
        # log.debug("pre battle, determining ambush")
        if self.ambush is True:
            # log.debug("player initiative")
            await self.ctx.send("> {0} {1}! You surprised {2}!".format(
                len(self.enemies),
                _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('it') if len(self.enemies) == 1 else _('them')
            ))

            for e in self.enemies:
                if any(s.name == 'Adverse Resolve' for s in e.skills):
                    e._ex_crit_mod += 5.0
                if any(s.name == 'Pressing Stance' for s in e.skills):
                    e._ex_evasion_mod += 3.0

            if any(s.name == 'Fortified Moxy' for s in self.player.skills):
                self.player._ex_crit_mod += 2.5

        elif self.ambush is False:
            # log.debug("enemy initiative")
            await self.ctx.send("> It's an ambush! There {2} {0} {1}!".format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')
            ))

            if any(s.name == 'Adverse Resolve' for s in self.player.skills):
                self.player._ex_crit_mod += 5.0
            if any(s.name == 'Pressing Stance' for s in self.player.skills):
                self.player._ex_evasion_mod += 3.0

            for e in self.enemies:
                if any(s.name == 'Fortified Moxy' for s in e.skills):
                    e._ex_crit_mod += 2.5
        else:
            # log.debug("regular initiative")
            await self.ctx.send("> There {2} {0} {1}! Attack!".format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')))

        self.player.pre_battle()
        for e in self.enemies:
            e.pre_battle()

    @main.after_loop
    async def post_battle_complete(self):
        # log.debug("complete")
        if self.main.failed():
            err = self.main.exception()
            # log.debug(f"error occured: {err!r}")
        else:
            err = None
        await self.cmd(self.ctx, err, battle=self)
        await self.ctx.send("game over")
        self.player.post_battle(self._ran)
        # log.debug("finish")
