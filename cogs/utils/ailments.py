import asyncio
import functools
import operator
import random

from .enums import SkillType


class UserIsImmobilized(Exception):
    pass  # raise this when you are unable to move


class UserTurnInterrupted(Exception):
    pass  # raise this when your turn was interrupted (eg confuse/brainwash)


class AilmentRemoved(Exception):
    pass  # raise this when the ailment has been removed


class _Ailment:
    emote = None
    # the emote to appear next to the user inflicted with this ailment

    cannot_move_msg = "> __{self.player}__ can't move!"
    # the message to display when UserIsImmobilized gets raised

    def __init__(self, player, type):
        self.type = type
        self.player = player
        self.counter = 0
        if any(s.name == 'Fast Heal' for s in player.skills):
            self.clear_at = random.randint(1, 4)
        elif any(s.name == 'Insta-Heal' for s in player.skills):
            self.clear_at = 1
        else:
            self.clear_at = random.randint(2, 7)

    def __repr__(self):
        return f"<Ailment: {self.name}, {self.player!r}, {self.counter}, {self.type!r}>"

    @property
    def name(self):
        return self.__class__.__name__

    # Forget is already handled in battle

    def pre_turn_effect(self):
        # for freeze, shock, sleep, confuse, fear, despair, rage, brainwash
        if self.counter == self.clear_at:
            raise AilmentRemoved
        self.counter += 1

    async def pre_turn_effect_async(self, battle):  # pylint: disable=unused-argument
        self.pre_turn_effect()

    def post_turn_effect(self):
        pass  # for burn


class Burn(_Ailment):
    """
    After you take your turn, you will take 6% of your max HP in damage.
    """
    emote = "\N{FIRE}"

    def post_turn_effect(self):
        self.player.hp = self.player.max_hp * 0.06


class Forget(_Ailment):
    """
    You will be unable to use your skills.
    You can still use Attack and Guard, and your passive skills will still work.
    """
    emote = '\N{SPEAKER WITH CANCELLATION STROKE}'


class Freeze(_Ailment):
    """
    You are unable to move.
    """
    emote = '\N{SNOWFLAKE}'
    cannot_move_msg = "> __{self.player}__ is frozen!"

    def pre_turn_effect(self):
        super().pre_turn_effect()
        raise UserIsImmobilized


class Shock(_Ailment):
    """
    High chance of being immobilized. If you hit someone with your Attack, or they hit you with their Attack,
    there is a medium chance of them being inflicted with Shock.
    """
    emote = '\N{HIGH VOLTAGE SIGN}'
    cannot_move_msg = "> __{self.player}__ is paralyzed!"

    def pre_turn_effect(self):
        super().pre_turn_effect()
        if random.randint(1, 10) != 1:
            raise UserIsImmobilized


class Dizzy(_Ailment):
    """
    Accuracy is severely reduced.
    """
    emote = '\N{DIZZY SYMBOL}'


class Hunger(_Ailment):
    """
    Attack power is greatly reduced.
    """
    emote = '\N{HAMBURGER}'


class Despair(_Ailment):
    """
    Unable to move, and you will lose 6% SP per turn.
    """
    emote = '\N{FEARFUL FACE}'
    cannot_move_msg = "> __{self.player}__ despairs..."

    def pre_turn_effect(self):
        super().pre_turn_effect()
        self.player.sp = self.player.max_sp*0.06
        raise UserIsImmobilized


class Sleep(_Ailment):
    """
    You are unable to move, however your HP and SP will recover by 8% every turn. You have a high chance of waking if
    the enemy hits you with a physical attack.
    """
    emote = '\N{SLEEPING SYMBOL}'
    cannot_move_msg = "> __{self.player}__ is asleep!"

    def pre_turn_effect(self):
        self.player.hp = -(self.player.max_hp*0.08)
        self.player.sp = -(self.player.max_sp*0.08)
        super().pre_turn_effect()
        raise UserIsImmobilized


class Fear(_Ailment, Exception):
    """
    High chance of being immobilized. Low chance of running away from battle.
    """
    emote = '\N{FACE SCREAMING IN FEAR}'
    cannot_move_msg = "> __{self.player}__ is immobilized with fear!"

    def pre_turn_effect(self):
        super().pre_turn_effect()
        if random.randint(1, 10) != 1:
            raise UserIsImmobilized
        if random.randint(1, 10) == 1:
            raise self


def _skill_cost(player, skill):
    cost = skill.cost
    if skill.uses_sp:
        if any(ss.name == 'Spell Master' for ss in player.skills):
            cost = cost / 2
        return player.sp >= cost
    if any(ss.name == 'Arms Master' for ss in player.skills):
        cost = cost / 2
    cost = player.max_hp * (cost / 100)  # we wanted a % smh
    return player.hp > cost


class Confuse(_Ailment):
    """
    Chance to throw away an item/credits, do nothing or use a random skill.
    """
    emote = "\u2754"

    async def pre_turn_effect_async(self, battle):
        self.pre_turn_effect()
        choice = random.randint(1, 5)
        # 1 -> throw away item
        # 2 -> throw away credits
        # 3 -> do nothing
        # 4 -> use a random skill
        # 5 -> continue as normal
        if choice != 5:
            await battle.ctx.send(f"> __{self.player}__ is confused!")
            await asyncio.sleep(1.1)
        if choice == 1:
            if not self.player.inventory.items:
                choice = 3
            else:
                items = functools.reduce(operator.add, self.player.inventory.items.values())
                if not items:
                    raise UserTurnInterrupted()
                select = random.choice(items)
                self.player.inventory.remove_item(select.name)
                await battle.ctx.send(f"Threw away 1x `{select}`!")
                raise UserTurnInterrupted()
        if choice == 2:
            # todo: when credits are added, add chance to throw them away during confusion
            await battle.ctx.send(f"Threw away `0` Credits!")
            raise UserTurnInterrupted()
        if choice == 3:
            raise UserTurnInterrupted()
        if choice == 4:
            raise UserTurnInterrupted()
            # todo: this, one day
            # select: Skill
            # select = random.choice(itertools.filterfalse(
            #     lambda s: s.type is not SkillType.PASSIVE, self.player.skills))
            # if select.uses_sp:
            #     if any(s.name == 'Spell Master' for s in self.player.skills):
            #         cost = select.cost/2
            #     else:
            #         cost = select.cost
            #     if cost > self.player.sp:
            #         await battle.ctx.send("Not enough SP!")
            #     else:
            #         if select.target == 'enemy':
            #             target = random.choice(battle.enemies if self.player not in battle.enemies
            #                                    else battle.players),
            #         elif select.target == "enemies":
            #             target = battle.enemies if self.player not in battle.enemies else battle.players
            #         elif select.target == "self":
            #             target = self.player
            #         elif select.target == "ally":
            #             target = random.choice(battle.enemeis if self.player in battle.enemeis else battle.players),
            #         elif select.target == "allies":
            #             target = battle.enemies if self.player in battle.enemeis else battle.players
            #         else:
            #             raise RuntimeError("??????????????????")
            #         await battle.ctx.send("got this far, its gonna be difficult to continue")
            #     raise UserTurnInterrupted()


class Brainwash(_Ailment):
    """
    Chance to heal/buff the enemy.
    """
    emote = "\N{PLAYING CARD BLACK JOKER}"

    async def pre_turn_effect_async(self, battle):
        self.pre_turn_effect()
        choice = random.choice((True, False))
        if choice:
            await battle.ctx.send(f"> __{self.player}__ is brainwashed!")
            await asyncio.sleep(1)
            skills = [s for s in self.player.skills if s.type in (SkillType.SUPPORT, SkillType.HEALING)
                      and s.target != 'self' and _skill_cost(self.player, s) and s.name != 'Guard']
            if not skills:
                raise UserTurnInterrupted
            skill = random.choice(skills)
            if skill.uses_sp:
                if any(s.name == 'Spell Master' for s in self.player.skills):
                    cost = skill.cost/2
                else:
                    cost = skill.cost
                self.player.sp = cost
            else:
                if any(s.name == 'Arms Master' for s in self.player.skills):
                    cost = skill.cost/2
                else:
                    cost = skill.cost
                cost = self.player.max_hp * (cost / 100)
                self.player.hp = cost
            await battle.ctx.send(f"__{self.player}__ used `{skill}`!")
            if self.player in battle.players:
                if skill.target in ('enemy', 'enemies'):
                    await skill.effect(battle, battle.players)
                else:
                    await skill.effect(battle, battle.enemies)
            else:
                if skill.target in ('enemy', 'enemies'):
                    await skill.effect(battle, battle.enemies)
                else:
                    await skill.effect(battle, battle.players)
            raise UserTurnInterrupted


class Rage(_Ailment):
    """
    Ignores commands and attacks enemies.
    Attack boosted but defense lowered.
    """
    emote = '\N{POUTING FACE}'

    async def pre_turn_effect_async(self, battle):
        self.pre_turn_effect()
        raise UserIsImmobilized  # temp, fixme
