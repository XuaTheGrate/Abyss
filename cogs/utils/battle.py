from . import i18n
from .ailments import *
from .objects import ListCycle
from .player import Player
from .scripts import do_script
from .skills import *
from .targetting import *

NL = '\n'

UNSUPPORTED_SKILLS = ['Growth 1', 'Growth 2', 'Growth 3',
                      'Amrita Shower', 'Amrita Drop',
                      'Fortify Spirit', 'Recarm', 'Samarecarm',
                      'Rebellion', 'Revolution', 'Foul Breath', 'Stagnant Air']


class Enemy(Player):
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random
    # however they will learn not to use a move if you are immune to it
    # also will not choose skills it can afford to use (sp)

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
        state = random.Random(int(''.join(map(str, map(ord, self.name)))))
        return math.ceil(math.sqrt(self.level_ ** 3 / state.uniform(1, 3)))

    def header(self):
        return ("[Wild] " +
                (f"~~{self.name}~~" if self.is_fainted() else f"{self.name}") +
                f" {self.ailment.emote if self.ailment and not self.is_fainted() else ''}")

    @property
    def level(self):
        return self.level_

    def skill_filter(self):
        for skill in self.skills:
            if skill.type is SkillType.PASSIVE:
                continue
            if skill.name in self.unusable_skills:
                continue
            if not skill.uses_sp:
                yield skill
                continue
            if any(s.name == 'Spell Master' for s in self.skills):
                c = skill.cost / 2
            else:
                c = skill.cost
            if c <= self.sp:
                yield skill

    def random_move(self):
        if self.ailment and self.ailment.type is AilmentType.FORGET:
            return GenericAttack
        choices = list(self.skill_filter())
        select = random.choice(choices or (GenericAttack,))
        if select.uses_sp:
            if any(s.name == 'Spell Master' for s in self.skills):
                self.sp = select.cost / 2
            else:
                self.sp = select.cost
        return select


class TreasureDemon(Enemy):
    def header(self):
        return f'[Treasure] {self.name}' + (f' {self.ailment.emote}' if self.ailment else '')

    def get_exp(self):
        return self.level_ * ((self.level_ * 10) + 50)

    @property
    def max_hp(self):  # treasure demons get a boost in hp
        return math.ceil(20 + self.endurance + (5.7 * self.level))

    def get_passive_evasion(self, type):
        return None


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


# exp = ceil(level ** 3 / uniform(1, 3))


def confirm_not_dead(battle):
    if all(p.is_fainted() for p in battle.players):
        return False
    return not all(e.is_fainted() for e in battle.enemies)


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
    def __init__(self, player, ctx, *enemies, ambush=None):
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").cog_command_error
        self.players = (player,)
        self.menu = None
        self.turn_cycle = 0
        self.enemies = sorted(enemies, key=lambda e: e.agility, reverse=True)
        self.ambush = ambush
        # True -> player got the initiative
        # False -> enemy got the jump
        # None -> proceed by agility
        self._stopping = False
        self._ran = False
        if self.ambush is True:
            self.order = [*self.players, *self.enemies]
        elif self.ambush is False:
            self.order = [*self.enemies, *self.players]
        else:
            self.order = sorted([*self.players, *self.enemies], key=lambda i: i.agility, reverse=True)
        self.double_turn = False
        self.order = ListCycle(self.order)
        self._task = self.start()
        self.log = self.ctx.bot.log
        self._turn_task = None

    def task_end(self, task):
        asyncio.ensure_future(self.post_battle_complete(), loop=self.ctx.bot.loop)

    def skip_turn(self):
        if self._turn_task:
            self._turn_task.cancel()

    async def _start(self):
        await self.pre_battle_start()
        while not self._stopping:
            await self.main()
            await asyncio.sleep(1)

    def start(self):
        task = self.ctx.bot.loop.create_task(self._start())
        task.add_done_callback(self.task_end)
        return task

    async def stop(self):
        self._stopping = True
        self._task.cancel()
        with suppress(AttributeError):
            await self.menu.stop()

    async def get_player_choice(self, player):
        self.menu = InitialSession(self, player)
        await self.menu.start(self.ctx)
        try:
            return self.menu.result
        finally:
            await self.menu.stop()

    async def handle_player_choices(self, player):
        # self.log.debug(f"player choices begin {player!r}")
        if not self.double_turn:
            # self.log.debug("not a double turn, run pre turn effects")
            await player.pre_turn_async(self)
        self.double_turn = False
        result = await self.get_player_choice(player)
        # self.log.debug(f"got player choices {result!r}")
        if result is None and not self._stopping:
            self.order.decycle()  # shitty way to do it but w.e
            # self.log.debug(f"stopping due to (result is None)({result is None}) (not self._stopping)({not self._stopping})")
            return await self.stop()

        if self._stopping:
            # self.log.debug("self._stopping is True")
            return

        if result['type'] == 'run':
            # self.log.debug("result['type'] == 'run'")
            if result['data'].get('timeout', False) or result['data'].get('success', True):
                self._ran = True
                await self.ctx.send("> You successfully ran away!")
                await self.stop()
                # self.log.debug("run was successful")
            else:
                await self.ctx.send("> You failed to escape!")
                # self.log.debug("run was NOT successful")
            return

        # type must be fight
        skill = result['data']['skill']
        # self.log.debug(f"got {skill!r} as a skill")

        if skill.name == "Guard":
            player.guarding = True
            # self.log.debug("we did a guard")
            return

        targets = result['data']['targets']
        # self.log.debug(f"got {targets!r} as targets")

        if skill.name in UNSUPPORTED_SKILLS:
            await self.ctx.send("this skill doesnt have a handler, this incident has been reported")
            self.ctx.bot.send_error(f"no skill handler for {skill}")
            self.order.decycle()
            # self.log.debug('skill did not have a handler and was skipped')
            self.double_turn = True
            return

        if skill.uses_sp:
            # self.log.debug("skill uses sp")
            cost = skill.cost
            # self.log.debug(f"skill.cost == {cost}")
            if any(s.name == 'Spell Master' for s in player.skills):
                cost /= 2
                # self.log.debug("cost was halved due to spell master")
            if player.sp < cost:
                await self.ctx.send("You don't have enough SP for this move!")
                # self.log.debug("not enough sp for skill, reverting turn cycle")
                self.double_turn = True
                return self.order.decycle()
            if skill.name != 'Guard' and player.ailment and player.ailment.type is AilmentType.FORGET:
                await self.ctx.send("You've forgotten how to use this move!")
                self.double_turn = True
                # self.log.debug("user forgot skill, reverting turn cycle")
                return self.order.decycle()
            player.sp = cost
            # self.log.debug("subtracted cost from sp")
        else:
            # self.log.debug("skill uses hp")
            if skill.cost != 0:
                cost = player.max_hp * (skill.cost / 100)
                # self.log.debug(f"cost calculated to {cost}/{skill.cost}")
                if any(s.name == 'Arms Master' for s in player.skills):
                    cost /= 2
                    # self.log.debug("lowering cost due to Arms Master")
            else:
                cost = 0
            # self.log.debug(f'skill.cost == {cost}')
            if cost > player.hp:
                # self.log.debug("not enough hp to use skill")
                await self.ctx.send("You don't have enough HP for this move!")
                self.double_turn = True
                return self.order.decycle()
            if skill.name != 'Attack' and player.ailment and player.ailment.type is AilmentType.FORGET:
                await self.ctx.send("You've forgotten how to use this move!")
                self.double_turn = True
                # self.log.debug("forgot how to use skill")
                return self.order.decycle()
            player.hp = cost
            # self.log.debug("subtracted cost from HP")

        if isinstance(skill, (StatusMod, ShieldSkill, HealingSkill, Karn, Charge, AilmentSkill)):
            await self.ctx.send(f"__{player}__ used `{skill}`!")
            await skill.effect(self, targets)
            # self.log.debug("skill is StatusMod, ShieldSkill, HealingSkill, Karn, Charge or Ailment")
            return

        weaked = False
        # log.debug(f'{targets}, {skill.hits}')
        for target in targets:
            force_crit = 0
            # self.log.debug(f"attacking enemy {target!r}")

            for __ in range(random.randint(*skill.hits)):
                # self.log.debug(f'hit enemy {target!r} {__} times')
                if target.is_fainted():
                    # self.log.debug('enemy was fainted')
                    break  # no point hitting the dead
                await asyncio.sleep(1.1)
                res = target.take_damage(player, skill, enforce_crit=force_crit)
                # self.log.debug(f"damage result {res!r}")
                # before we do any message stuff, we have to update the db
                # especially if the result is a miss, itll just return instantly

                if skill.type.value <= 10:
                    # self.log.debug("skill type is CURSE or less")
                    bot = self.ctx.bot
                    data = await bot.db.abyss.demonresearch.find_one({"user_id": player.owner.id, "enemy": target.name})
                    if data:
                        await bot.db.abyss.demonresearch.update_one({'_id': data['_id']}, {
                            "$set": {
                                f"resistances.{skill.type.value-1}": res.resistance.value
                            }})
                        # self.log.debug("updated existing data")
                    else:
                        ress = [-1 for a in range(10)]
                        ress[skill.type.value-1] = res.resistance.value
                        await bot.db.abyss.demonresearch.insert_one({
                            "user_id": player.owner.id,
                            "enemy": target.name,
                            "resistances": ress,
                            "moves": []
                        })
                        # self.log.debug("added new data")

                # this is to ensure crits only happen IF the first hit did land a crit
                # we use a Triboolean:
                # 0: first hit, determine crit
                # 1: first hit passed, it was a crit
                # 2: first hit passed, was not a crit
                force_crit = 1 if res.critical else 2
                # self.log.debug(f'forcing crit: {force_crit==1}')
                msg = get_message(res.resistance, reflect=res.was_reflected, miss=res.miss, critical=res.critical)
                msg = msg.format(demon=player, tdemon=target, damage=res.damage_dealt, skill=skill)
                # self.log.debug(msg)
                await self.ctx.send(msg)
                if res.endured:
                    await self.ctx.send(f"> __{target}__ endured the hit!")
                    # self.log.debug('target endured the hit via Endure or Enduring Soul')

                if res.miss:
                    # the first hit was a miss, so just break
                    # the back door is explained in utils/player.py#L526
                    # self.log.debug("multihit miss backdoor was closed")
                    break

                if skill.type is SkillType.PHYSICAL:
                    if target.ailment and target.ailment.type is AilmentType.SLEEP:
                        if random.randint(1, 6) != 1:
                            target.ailment = None
                            await self.ctx.send(f"> __{target}__ woke up!")
                            # self.log.debug('target awoke due to physical skill')

                if skill.name == 'Attack':
                    if target.ailment and target.ailment.type is AilmentType.SHOCK:
                        if not player.ailment and random.randint(1, 3) == 1:
                            player.ailment = ailments.Shock(player, AilmentType.SHOCK)
                            await self.ctx.send(f"> __{player}__ was inflicted with **Shock**!")
                            # self.log.debug("player was shocked due to GenericAttack")
                    elif not target.ailment and player.ailment and player.ailment.type is AilmentType.SHOCK:
                        target.ailment = ailments.Shock(target, AilmentType.SHOCK)
                        await self.ctx.send(f"> __{target}__ was inflicted with **Shock**!")
                        # self.log.debug("target was shocked due to GenericAttack")

                if res.did_weak:
                    # self.log.debug("managed to land a weak or critical")
                    weaked = True
        if skill.uses_sp:  # reset here so all hits of a skill are charged up
            player.concentrating = False
            # self.log.debug("stopped concentrating")
        else:
            player.charging = False
            # self.log.debug("stopped charging")

        if weaked and confirm_not_dead(self):
            # self.log.debug("doing another turn due to knock down")
            self.order.decycle()
            self.double_turn = True
            await self.ctx.send("> Nice hit! Move again!")
        # self.log.debug("end of function")

    def filter_targets(self, skill, user):
        if skill.target == 'enemies':
            return self.players
        elif skill.target == 'enemy':
            return random.choice(self.players),
        elif skill.target == 'self':
            return user,
        elif skill.target == 'ally':
            return random.choice([e for e in self.enemies if not e.is_fainted()]),
        elif skill.target == 'allies':
            return [e for e in self.enemies if not e.is_fainted()]
        elif skill.target == 'all':
            return [*self.players] + [e for e in self.enemies if not e.is_fainted()]

    async def handle_enemy_choices(self, enemy):
        """
        mongodb.demonresearch.find_one({"enemy": enemy name, "user_id": player id})
        {
            "_id": ...,
            "enemy": "enemy name",
            "user_id": player id,
            "resistances": [
                -1,  # unknown
                0,   # null
                1,   # resist
                2,   # normal
                3,   # weak
                4,   # repel
                5,   # absorb
                -1,
                -1,
                -1
            ],
            "moves": []  # append moves as learnt
        }
        """
        if not self.double_turn:
            await enemy.pre_turn_async(self)
        self.double_turn = False
        skill = enemy.random_move()
        if skill.name not in ('Attack', 'Guard'):
            bot = self.ctx.bot  # no need to keep these
            for p in self.players:
                data = await bot.db.abyss.demonresearch.find_one({"user_id": p.owner.id, "enemy": enemy.name})
                if data:
                    await bot.db.abyss.demonresearch.update_one({"_id": data['_id']},
                                                                {"$addToSet": {"moves": skill.name}})
                else:
                    await bot.db.abyss.demonresearch.insert_one({
                        "user_id": p.owner.id,
                        "enemy": enemy.name,
                        "resistances": [-1 for _z in range(10)],
                        "moves": [skill.name]
                    })
        if skill.name in UNSUPPORTED_SKILLS:
            await self.ctx.send(f"{enemy} used an unhandled skill ({skill.name}), skipping")
            return
        targets = self.filter_targets(skill, enemy)
        if isinstance(skill, (StatusMod, ShieldSkill, HealingSkill, Karn, Charge, AilmentSkill)):
            await self.ctx.send(f"__{enemy}__ used `{skill}`!")
            await skill.effect(self, targets)
            return

        if skill.name == 'Guard':
            await self.ctx.send(f"__{enemy}__ guarded!")
            enemy.guarding = True
            return

        # log.debug(f"enemy: {targets}, {skill.hits}")
        for target in targets:
            weaked = False
            force_crit = 0

            for a in range(random.randint(*skill.hits)):
                await asyncio.sleep(1.1)  # we are sending messages too fast tbh
                res = target.take_damage(enemy, skill, enforce_crit=force_crit)
                force_crit = 1 if res.critical else 2
                if res.did_weak:
                    weaked = True

                if res.resistance in (
                        ResistanceModifier.IMMUNE,
                        ResistanceModifier.REFLECT,
                        ResistanceModifier.ABSORB
                ):
                    enemy.unusable_skills.append(skill.name)
                    # the ai learns not to use it in the future, but still use it this turn

                msg = get_message(res.resistance, reflect=res.was_reflected, miss=res.miss, critical=res.critical)
                msg = msg.format(demon=enemy, tdemon=target, damage=res.damage_dealt, skill=skill)
                await self.ctx.send(msg)

                if skill.type is SkillType.PHYSICAL:
                    if target.ailment and target.ailment.type is AilmentType.SLEEP:
                        if random.randint(1, 6) != 1:
                            target.ailment = None
                            await self.ctx.send(f"> __{target}__ woke up!")

                if skill.name == 'Attack':
                    if target.ailment and target.ailment.type is AilmentType.SHOCK:
                        if not enemy.ailment and random.randint(1, 3) == 1:
                            enemy.ailment = ailments.Shock(enemy, AilmentType.SHOCK)
                            await self.ctx.send(f"> __{enemy}__ was inflicted with **Shock**!")
                    elif not target.ailment and enemy.ailment and enemy.ailment.type is AilmentType.SHOCK:
                        target.ailment = ailments.Shock(target, AilmentType.SHOCK)
                        await self.ctx.send(f"> __{target}__ was inflicted with **Shock**!")

            if skill.uses_sp:
                enemy.concentrating = False
            else:
                enemy.charging = False

            if weaked and not target.is_fainted():
                self.order.decycle()
                self.double_turn = True
                await self.ctx.send("> Watch out, {demon} is attacking again!".format(demon=enemy))

    async def main(self):
        # log.debug("starting loop")
        if not confirm_not_dead(self):
            # log.debug("confirm not dead failed, stopping")
            await self.stop()
            return
        nxt = self.order.active()

        try:
            if not nxt.is_fainted() and nxt.ailment is not None:
                await nxt.ailment.pre_turn_effect_async(self)
        except UserIsImmobilized:
            await self.ctx.send(nxt.ailment.cannot_move_msg.format(self=nxt.ailment))
            self.order.cycle()
            return
        except AilmentRemoved:
            await self.ctx.send(f"> __{nxt}__'s {nxt.ailment.name} wore off!")
            nxt.ailment = None
        except Fear:
            await self.ctx.send(f"> __{nxt}__ ran away!")
            if isinstance(nxt, Enemy):
                nxt.hp = nxt.max_hp  # faint the enemy ig lol
            else:
                await self.stop()
                self._ran = True
                return  # player ran away
            self.order.cycle()
        except UserTurnInterrupted:
            # await self.ctx.send("turn interrupted but no handler has been done")
            self.order.cycle()
            return  # no handler rn

        if not isinstance(nxt, Enemy):
            # log.debug("next: player")
            if not self.double_turn:
                if self.ambush and any(s.name == 'Heat Up' for s in nxt.skills):
                    nxt.hp = -(nxt.max_hp * 0.05)
                    nxt.sp = -10
                self.turn_cycle += 1
            self._turn_task = self.ctx.bot.loop.create_task(self.handle_player_choices(nxt))
            try:
                await self._turn_task
            except asyncio.CancelledError:
                pass
            finally:
                self._turn_task = None
                await self.menu.stop()
        else:
            if not nxt.is_fainted():
                # log.debug("next enemy not fainted")
                if not self.double_turn:
                    if self.ambush is False and any(s.name == 'Heat Up' for s in nxt.skills):
                        nxt.hp = -(nxt.max_hp * 0.05)
                        nxt.sp = -10
                self._turn_task = self.ctx.bot.loop.create_task(self.handle_enemy_choices(nxt))
                try:
                    await self._turn_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self._turn_task = None
            else:
                self.order.remove(nxt)
        if not nxt.is_fainted() and nxt.ailment is not None:
            nxt.ailment.post_turn_effect()
        self.order.cycle()

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

            for p in self.players:
                if any(s.name == 'Fortified Moxy' for s in p.skills):
                    p._ex_crit_mod += 2.5

        elif self.ambush is False:
            # log.debug("enemy initiative")
            await self.ctx.send("> It's an ambush! There {2} {0} {1}!".format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')
            ))

            for p in self.players:
                if any(s.name == 'Adverse Resolve' for s in p.skills):
                    p._ex_crit_mod += 5.0
                if any(s.name == 'Pressing Stance' for s in p.skills):
                    p._ex_evasion_mod += 3.0

            for e in self.enemies:
                if any(s.name == 'Fortified Moxy' for s in e.skills):
                    e._ex_crit_mod += 2.5
        else:
            # log.debug("regular initiative")
            await self.ctx.send("> There {2} {0} {1}! Attack!".format(
                len(self.enemies), _('enemy') if len(self.enemies) == 1 else _('enemies'),
                _('is') if len(self.enemies) == 1 else _('are')))

        for p in self.players:
            p.pre_battle()
        for e in self.enemies:
            e.pre_battle()

    async def post_battle_complete(self):
        # log.debug("complete")
        if not self._task.cancelled() and self._task.exception():
            err = self._task.exception()
            # log.debug(f"error occured: {err!r}")
            await self.cmd(self.ctx, err, battle=self)
            return

        if (p := self.players[0]).is_fainted():
            # TODO: reset map back to first map and lose some cash
            await self.ctx.send("ok so theres supposed to be some magic script thing but i cant figure it out\n"
                                "ill heal you and then kick you from battle because i havent fixed it yet")
            p.post_battle(False)
            p._sp_used = 0
            p.damage_taken = 0
            p.ailment = None
            return await self.cmd(self.ctx, None, battle=self)
            # noinspection PyUnreachableCode
            await do_script(self.ctx, "death", i18n.current_locale.get())
            for p in self.players:
                p.post_battle(False)
                p._sp_used = 0
                p.damage_taken = 0  # heal the player
                p.ailment = None
            return self.main.restart()

        await self.cmd(self.ctx, None, battle=self)

        if self._ran:
            msg = "That was a close one.\n0 EXP and 0 Credits earned."
            exp = 0
            cash = 0
        else:
            exp = sum(e.get_exp() for e in self.enemies)
            cash = 0  # TODO: implement this
            msg = f"Nice work!\n{exp} EXP and {cash} Credits earned."

        for p in self.players:
            p.exp += exp
            p.credits += cash
            p.post_battle(self._ran)
        await self.ctx.send(msg)
        # log.debug("finish")


class PVPBattle(WildBattle):
    def __init__(self, ctx, *, teama, teamb):
        super().__init__(None, ctx, *teamb)
        self.players = tuple(teama)

    async def get_player_choice(self, player):
        self.menu = InitialSession(self, player)
        try:
            await self.menu.start(self.ctx, dm=True)
            return self.menu.result
        finally:
            await self.menu.stop()


class TreasureDemonBattle(WildBattle):
    def __init__(self, *args):
        super().__init__(*args)
        self.run_after = random.randint(2, 4)

    async def handle_enemy_choices(self, enemy):
        if self.turn_cycle == self.run_after:
            await self.ctx.send(f"> **{enemy.name}** ran away!")
            self._ran = True
            await self.stop()
        else:
            await self.ctx.send(f"> **{enemy.name}** is groaning...")

    async def post_battle_complete(self):
        await super().post_battle_complete()
        if not self._ran:
            if random.random() >= 0.5:
                skill = random.choice(self.enemies[0].skills).name
                await self.ctx.send(f"Obtained **Skill Card: {skill}**!")
                for p in self.players:  # im looping here because of possible battle jumping (0o0)
                    p.inventory.add_item(self.ctx.bot.item_cache.items[skill])
