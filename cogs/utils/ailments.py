import asyncio
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

    cannot_move_msg = None
    # the message to display when UserIsImmobilized gets raised

    def __init__(self, player, type):
        self.type = type
        self.player = player
        self.counter = 0
        if any(s.name == 'Fast Heal' for s in player.skills):
            self.clear_at = random.randint(1, 5)
        elif any(s.name == 'Insta-Heal' for s in player.skills):
            self.clear_at = 1
        else:
            self.clear_at = random.randint(2, 8)

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

    async def pre_turn_effect_async(self, battle):
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


def _skill_cost(p, s):
    cost = s.cost
    if s.uses_sp:
        if any(ss.name == 'Spell Master' for ss in p.skills):
            cost = cost / 2
        return p.sp >= cost
    else:
        if any(ss.name == 'Arms Master' for ss in p.skills):
            cost = cost / 2
        cost = p.max_hp * (cost / 100)  # we wanted a % smh
        return p.hp > cost


class Brainwash(_Ailment):
    """
    Chance to heal/buff the enemy.
    """
    emote = "\N{PLAYING CARD BLACK JOKER}"

    async def pre_turn_effect_async(self, battle):
        log.debug("hello, world!")
        super().pre_turn_effect()
        log.debug("the ailment was not cleared")
        choice = random.choice((True, False))
        log.debug(f"choice = {choice}")
        if choice:
            await battle.ctx.send(f"> __{self.player}__ is brainwashed!")
            log.debug("sent msg")
            await asyncio.sleep(1)
            skills = [s for s in self.player.skills if s.type in (SkillType.SUPPORT, SkillType.HEALING)
                      and s.target != 'self' and _skill_cost(self.player, s) and s.name != 'Guard']
            log.debug(f"len(skills) = {len(skills)}")
            if not skills:
                log.debug("no skills found")
                raise UserTurnInterrupted
            s = random.choice(skills)
            log.debug(f"random skill: {s}, {s.uses_sp}")
            if s.uses_sp:
                if any(s.name == 'Spell Master' for s in self.player.skills):
                    c = s.cost/2
                else:
                    c = s.cost
                log.debug(f"costs {c}/{self.player.sp}")
                self.player.sp = c
            else:
                if any(s.name == 'Arms Master' for s in self.player.skills):
                    c = s.cost/2
                else:
                    c = s.cost
                c = self.player.max_hp * (c / 100)
                log.debug(f"costs {c}/{self.player.hp}")
                self.player.hp = c
            await battle.ctx.send(f"__{self.player}__ used `{s}`!")
            log.debug(f"{self.player} used {s}!")
            if self.player is battle.player:
                if s.target in ('enemy', 'enemies'):
                    await s.effect(battle, (self.player,))
                else:
                    await s.effect(battle, battle.enemies)
                log.debug("its the player")
            else:
                if s.target in ('enemy', 'enemies'):
                    await s.effect(battle, battle.enemies)
                else:
                    await s.effect(battle, (self.player,))
                log.debug("it is not the player")
            raise UserTurnInterrupted
