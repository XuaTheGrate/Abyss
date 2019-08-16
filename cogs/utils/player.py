import math
import numpy.random as random
import re

from .enums import *
from .lookups import TYPE_SHORTEN, STAT_MOD
from .objects import DamageResult, JSONable
from .skills import Skill
from .weather import get_current_weather

CRITICAL_BASE = 4

IMMUNITY_ORDER = ['Repel', 'Absorb', 'Null', 'Resist']


class Player(JSONable):
    __json__ = ('owner', 'name', 'skills', 'exp', 'stats', 'resistances', 'arcana', 'specialty', 'stat_points',
                'description', 'skill_leaf', 'ap', 'unsetskills', 'finished_leaves')

    def keygetter(self, key):
        if key == 'owner':
            return self._owner_id
        elif key == 'skills':
            return [z.name for z in self.skills]
        elif key == 'resistances':
            return self._resistances
        elif key == 'arcana':
            return self.arcana.value
        elif key == 'specialty':
            return self.specialty.name
        elif key == 'skill_leaf':
            return self._active_leaf
        elif key == 'ap':
            return self.ap_points
        elif key == 'unsetskills':
            return [z.name for z in self.unset_skills if z.name not in ('Attack', 'Guard')]
        return getattr(self, key)

    def __init__(self, **kwargs):
        # kwargs.pop("_id")
        self._owner_id = kwargs.pop("owner")
        self.owner = None
        self.name = kwargs.pop("name")

        skills = kwargs.pop("skills")
        if skills and all(isinstance(x, Skill) for x in skills):
            self.skills = skills
        else:
            self.skills = []
            self._skills = list({'Attack', 'Guard', *skills})

        self.exp = kwargs.pop("exp")
        self.strength, self.magic, self.endurance, self.agility, self.luck = kwargs.pop("stats")

        # self.resistances = dict(zip(SkillType, map(ResistanceModifier, kwargs.pop("resistances"))))
        self._resistances = kwargs.pop("resistances")
        # noinspection PyTypeChecker
        self.resistances = dict(zip(SkillType, [
            ResistanceModifier.WEAK if x == 3
            else ResistanceModifier.NORMAL if x == 2
            else ResistanceModifier.RESIST
            for x in self._resistances]))
        # noinspection PyArgumentList

        self.arcana = Arcana(kwargs.pop("arcana"))
        self.specialty = SkillType[kwargs.pop("specialty").upper()]
        self.description = kwargs.pop("description", "<no description found, report to Xua>")
        self.stat_points = kwargs.pop("stat_points", 0)
        self.debug = kwargs.pop("testing", False)
        self._active_leaf = kwargs.pop("skill_leaf", None)
        self.leaf = None
        self.ap_points = kwargs.pop("ap", 0)
        self._unset_skills = kwargs.pop("unsetskills", [])
        self.unset_skills = []
        self._damage_taken = 0
        self._sp_used = 0
        self._stat_mod = [0, 0, 0]
        # [attack][defense][agility]
        self._until_clear = [0, 0, 0]  # turns until it gets cleared for each stat, max of 3 turns
        self._next_level = self.level + 1
        self.finished_leaves = kwargs.pop("finished_leaves", [])
        self.guarding = False
        self.ailment = None
        self._shields = {}
        self._ex_crit_mod = 1.0  # handled by the battle system in the pre-loop hook
        self._rebellion = [False, -1]  # Rebellion or Revolution, [(is enabled), (time until clear)]
        self._ailment_buff = -1  # > 0: ailment susceptibility is increased
        self._ex_evasion_mod = 1.0  # handled by the battle system, usually only affected by Pressing Stance
        self._endured = False
        self._charging = False
        self._concentrating = False
        self._tetrakarn = False
        self._makarakarn = False
        self._turns_in_ailment = 0

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<({self.arcana.name}) {self.owner}'s  Level {self.level} {self.name!r}>"

    def _debug_repr(self):
        return f"""Player {self.owner}, {self._owner_id}
--- name: {self.name}
--- skills: {", ".join(map(str, self.skills))}
--- exp: {self.exp}
--- stats: {self.stats}
--- resistances: {self._resistances}
--- description: {self.description}
--- stat_points: {self.stat_points}
--- arcana: {self.arcana!r}
--- specialty: {self.specialty!r}
--- leaf: {self.leaf}
--- ap_points: {self.ap_points}
--- finished_leaves: {self.finished_leaves}
--- unset_skills: {", ".join(map(str, self.unset_skills))}
--- guarding: {self.guarding}

--- level: {self.level}
--- hp: {self.hp}
--- max_hp: {self.max_hp}
--- sp: {self.sp}
--- max_sp: {self.max_sp}
--- can_level_up: {self.can_level_up}
--- ailment: {self.ailment!r}

--- exp_tp_next_level(): {self.exp_to_next_level()}
--- is_fainted(): {self.is_fainted()}
--- get_counter(): {self.get_counter()}

--- debug: {self.debug}
--- _damage_taken: {self._damage_taken}    
--- _sp_used: {self._sp_used}
--- _stat_mod: {self._stat_mod}
--- _until_clear: {self._until_clear}
--- _next_level: {self._next_level}
--- _active_leaf: {self._active_leaf}
--- _shields: {self._shields}
--- _ex_crit_mod: {self._ex_crit_mod}
--- _ailment_buff: {self._ailment_buff}
--- _ex_evasion_mod: {self._ex_evasion_mod}
--- _tetrakarn: {self._tetrakarn}
--- _makarakarn: {self._makarakarn}
--- _endured: {self._endured}
--- _charging: {self._charging}
--- _concentrating: {self._concentrating}
--- _turns_in_ailment: {self._turns_in_ailment}"""

    @property
    def stats(self):
        return [self.strength, self.magic, self.endurance, self.agility, self.luck]

    @property
    def hp(self):
        return self.max_hp - self._damage_taken

    @hp.setter
    def hp(self, value):
        if self.hp - round(value) <= 0:
            self._damage_taken = self.max_hp
        elif (self.hp - round(value)) > self.max_hp:
            self._damage_taken = 0
        else:
            self._damage_taken += round(value)

    @property
    def max_hp(self):
        return math.ceil(20 + self.endurance + (4.7 * self.level))

    @property
    def sp(self):
        return self.max_sp - self._sp_used

    """
In [23]: end = 1
...: for level in range(1, 100):
...:     end = min(99, end)
...:     print(f"Level: {level} | Magic: {end} | SP: {math.ceil(10+end+(3.6*level))}, HP: {math.ceil(20+end+(4.7*level))}")
...:     for a in range(5):
...:         if random.randint(1, 5) == 1:
...:             end += 1
Level: 1 | Magic: 1 | SP: 15, HP: 26
Level: 2 | Magic: 2 | SP: 20, HP: 32
...
Level: 98 | Magic: 91 | SP: 454, HP: 572
Level: 99 | Magic: 92 | SP: 459, HP: 578
"""

    @sp.setter
    def sp(self, value):
        if self.sp - round(value) <= 0:
            self._sp_used = self.max_sp
        elif (self.sp - round(value)) > self.max_sp:
            self._sp_used = 0
        else:
            self._sp_used += round(value)

    @property
    def max_sp(self):
        return math.ceil(10 + self.magic + (3.6 * self.level))

    @property
    def level(self):
        return min(99, max(math.ceil(self.exp ** .333), 1))

    def level_up(self):
        while self._next_level <= self.level:
            self._next_level += 1
            self.stat_points += 3

    @property
    def can_level_up(self):
        return self._next_level <= self.level

    def exp_to_next_level(self):
        return self._next_level ** 3 - self.exp

    def exp_progress(self):
        me = self.exp
        next = self._next_level ** 3
        diff = next - (self.level ** 3)
        mdiff = next - me
        return ((diff - mdiff) / diff) * 100

    def _populate_skills(self, bot):
        self.owner = bot.get_user(self._owner_id)
        for skill in self._skills:
            self.skills.append(bot.players.skill_cache[skill])
        for skill in self._unset_skills:
            self.unset_skills.append(bot.players.skill_cache[skill])

    def affected_by(self, modifier):
        return 1.0 + (0.05 * self._stat_mod[modifier.value])

    def refresh_stat_modifier(self, modifier=None, to=True):
        if not modifier:  # all modifiers
            for i in range(3):
                self._stat_mod[i] += 1 + ((to - 1) * 2)
                self._until_clear[i] = 4
            return
        v = modifier.value
        self._stat_mod[v] += 1 + ((to - 1) * 2)  # 1 for *kaja (True), -1 for *nda (False)
        self._until_clear[v] = 4

    def decrement_stat_modifier(self, modifier=None):
        if not modifier:  # all modifiers
            for i in range(3):
                if self._until_clear[i] >= 0:
                    self._until_clear[i] -= 1
                    if self._until_clear[i] == 0:
                        self._stat_mod[i] = 0
            return
        if self._until_clear[modifier.value] >= 0:
            self._until_clear[modifier.value] -= 1
            if self._until_clear[modifier.value] == 0:
                self._stat_mod[modifier.value] = 0

    async def decrement_stat_modifier_async(self, battle, modifier=None):
        if not modifier:  # all modifiers
            for i in range(3):
                if self._until_clear[i] >= 0:
                    self._until_clear[i] -= 1
                    if self._until_clear[i] == 0:
                        self._stat_mod[i] = 0
                        await battle.ctx.send(f"> __{self.name}__'s {STAT_MOD[i]} reverted.")
            return
        if self._until_clear[modifier.value] >= 0:
            self._until_clear[modifier.value] -= 1
            if self._until_clear[modifier.value] == 0:
                self._stat_mod[modifier.value] = 0
                await battle.ctx.send(f"> __{self.name}__'s {STAT_MOD[modifier.value]} reverted.")

    def clear_stat_modifier(self, modifier=None):
        if not modifier:  # all modifiers
            self._until_clear = [-1, -1, -1]
            self._stat_mod = [0, 0, 0]
        else:
            self._until_clear[modifier.value] = -1
            self._stat_mod[modifier.value] = 0

    def resists(self, type):
        if type in (SkillType.PHYSICAL, SkillType.GUN):
            if self._tetrakarn:
                self._tetrakarn = False
                return ResistanceModifier.REFLECT
        else:
            if self._makarakarn:
                self._makarakarn = False
                return ResistanceModifier.REFLECT

        passive = self.get_passive_immunity(type)
        if passive and not passive.is_evasion:
            get = passive.immunity_handle()  # instead of resisting if you are weak, the weakness is nullified
            if self._resistances[type] is ResistanceModifier.WEAK and get is ResistanceModifier.RESIST:
                return ResistanceModifier.NORMAL
            return get

        if self._shields.get(type.name.title(), 0) > 0:
            return ResistanceModifier.IMMUNE

        try:
            return self.resistances[type]
        except KeyError:
            if not isinstance(type, SkillType):
                raise
            return ResistanceModifier.NORMAL

    def is_fainted(self):
        if self.hp <= 0:
            self._stat_mod = [0, 0, 0]
            self._until_clear = [0, 0, 0]
            return True
        return False

    def get_counter(self):
        h = None
        for skill in self.skills:
            if skill.is_counter_like:
                if not h:
                    h = skill
                else:
                    if skill.accuracy > h.accuracy:  # high counter has higher priority over counterstrike
                        h = skill
        return h

    def get_passive_immunity(self, type):
        f = None
        fmt = re.compile(fr"(Null|Repel|Absorb|Resist) {TYPE_SHORTEN[type.name.lower()].title()}")
        for skill in self.skills:
            if skill.is_passive_immunity:
                n = fmt.findall(skill.name)
                if not n:
                    continue
                n = n[0]
                if not f or IMMUNITY_ORDER.index(n) < IMMUNITY_ORDER.index(f):
                    f = n
        return f

    def get_passive_evasion(self, type):
        f = None
        for skill in self.skills:
            if skill.name == f"Dodge {TYPE_SHORTEN[type.name.lower()].title()}" and not f:
                f = skill
            elif skill.name == f"Evade {TYPE_SHORTEN[type.name.lower()].title()}":
                f = skill
                break
        return f

    def get_auto_mod(self, modifier):
        for skill in self.skills:
            if (skill.name == 'Attack Master' and modifier is StatModifier.TARU) or (
                    skill.name == 'Defense Master' and modifier is StatModifier.RAKU) or (
                    skill.name == 'Speed Master' and modifier is StatModifier.SUKU):
                return skill

    def get_all_auto_mods(self):
        for mod in (StatModifier.TARU, StatModifier.RAKU, StatModifier.SUKU):
            yield self.get_auto_mod(mod)

    def get_regenerate(self):
        if any(s.name.startswith('Regenerate') for s in self.skills):
            return max(filter(lambda s: s.name.startswith('Regenerate'), self.skills), key=lambda s: int(s.name[-1]))

    def get_invigorate(self):
        if any(s.name.startswith('Invigorate') for s in self.skills):
            return max(filter(lambda s: s.name.startswith('Invigorate'), self.skills), key=lambda s: int(s.name[-1]))

    def pre_turn(self):
        self.decrement_stat_modifier()

        for k in self._shields.copy():
            if self._shields[k] >= 0:
                self._shields[k] -= 1
                if self._shields[k] == 0:
                    self._shields.pop(k)

        if self._ailment_buff >= 0:
            self._ailment_buff -= 1

        if self._rebellion[1] >= 0:
            self._rebellion[1] -= 1
            if self._rebellion[1] == 0:
                self._rebellion[0] = False

        reg = self.get_regenerate()
        if reg:
            mod = int(reg.name[-1]) * 2
            self.hp = -(self.max_hp * (mod / 100))
        inv = self.get_invigorate()
        if inv:
            mod = int(inv.name[-1]) * 2 + 1
            self.sp = -mod

        self.guarding = False

    async def pre_turn_async(self, battle):
        await self.decrement_stat_modifier_async(battle)

        for k in self._shields.copy():
            if self._shields[k] >= 0:
                self._shields[k] -= 1
                if self._shields[k] == -1:
                    self._shields.pop(k)
                    await battle.ctx.send(f"> __{self.name}__'s' {k.title()} immunity reverted.")

        if self._ailment_buff >= 0:
            self._ailment_buff -= 1
            if self._ailment_buff == -1:
                await battle.ctx.send(f"> __{self.name}__'s ailment susceptibility reverted.")

        if self._rebellion[1] >= 0:
            self._rebellion[1] -= 1
            if self._rebellion[1] == 0:
                self._rebellion[0] = False
                await battle.ctx.send(f"> __{self.name}__'s critical rate reverted.")

        reg = self.get_regenerate()
        if reg:
            mod = int(reg.name[-1]) * 2
            self.hp = -(self.max_hp * (mod / 100))
        inv = self.get_invigorate()
        if inv:
            mod = int(inv.name[-1]) * 2 + 1
            self.sp = -mod

        self.guarding = False

    def get_boost_amp_mod(self, type):
        base = 1
        for skill in self.skills:
            if skill.name.lower() == f"{type.name.lower()} amp":
                base += 0.5
            elif skill.name.lower() == f"{type.name.lower()} boost":
                base += 0.25
            elif type.name.lower() == 'gun':
                if skill.name.lower() == 'snipe':
                    base += 0.25
                elif skill.name.lower() == 'cripple':
                    base += 0.5
            elif type.name.lower() in ('light', 'dark'):
                if type.name.lower() == 'light' and skill.name.lower() == 'hama boost':
                    base += 19
                elif type.name.lower() == 'dark' and skill.name.lower() == 'mudo boost':
                    base += 19
        return base

    def pre_battle(self):
        for mod in self.get_all_auto_mods():
            if mod:
                self.refresh_stat_modifier(mod)

    def post_battle(self, ran=False):
        self._ex_crit_mod = 1.0
        self.clear_stat_modifier()
        self._charging = False
        self._concentrating = False
        self._tetrakarn = False
        self._makarakarn = False
        self._shields.clear()
        self._ailment_buff = -1
        self._endured = False
        if not ran:
            if any(s.name == 'Victory Cry' for s in self.skills):
                self._sp_used = 0
                self._damage_taken = 0
                return

            if any(s.name == 'Life Aid' for s in self.skills):
                self.sp = -(self.max_sp * 0.08)
                self.hp = -(self.max_hp * 0.08)

    def take_damage(self, attacker, skill, *, from_reflect=False, counter=False, enforce_crit=0):
        res = self.resists(skill.type)
        result = DamageResult()
        result.skill = skill
        if counter:
            result.countered = True

        guarded = self.guarding
        self.guarding = False

        if res is ResistanceModifier.REFLECT:
            if not from_reflect and not counter:
                # from_reflect -> dont loop reflecting skills
                # counter -> dont reflect if the skill was countered
                return attacker.take_damage(self, skill, from_reflect=True)
            res = ResistanceModifier.IMMUNE
            result.was_reflected = True

        if not skill.uses_sp and not from_reflect and not counter:  # dont double proc counter :^)
            # also only applies to physical skills
            s_counter = self.get_counter()
            if s_counter and s_counter.try_counter(attacker, self):
                return attacker.take_damage(self, skill, counter=True)

        result.resistance = res

        if res is ResistanceModifier.IMMUNE:
            return result

        if self.try_evade(attacker, skill):
            result.miss = True
            return result

        if skill.is_instant_kill:
            self.hp = self.max_hp
            result.damage_dealt = self.max_hp
            return result

        base = skill.damage_calc(attacker, self)
        base *= attacker.get_boost_amp_mod(skill.type)
        tmp = False

        if from_reflect or counter:
            base /= 1.35  # reflected damage is weakened
        else:  # counters arent supposed to crit :^^)
            if not skill.uses_sp and res is not ResistanceModifier.WEAK and not guarded:  # weakness comes before criticals
                # guarding also nullifies knock downs, so crits and weaknesses
                if enforce_crit == 0:
                    if skill.type is SkillType.GUN and any(s.name == 'Trigger Happy' for s in self.skills):
                        self._ex_crit_mod += 1.33
                        tmp = True
                    enforce_crit = 1 if attacker.try_crit(self) else 2
                    if tmp:
                        self._ex_crit_mod -= 1.33
                if enforce_crit == 1:
                    base *= 1.75
                    result.critical = True
                    result.did_weak = True

        if guarded and res not in (
                ResistanceModifier.ABSORB,
                ResistanceModifier.REFLECT,
                ResistanceModifier.IMMUNE
        ):
            base *= 0.25

        if res is ResistanceModifier.WEAK and not guarded:
            base *= 1.5
            result.did_weak = True
        elif res is ResistanceModifier.RESIST:
            base *= 0.5

        if attacker.ailment and attacker.ailment.type is AilmentType.HUNGER:
            base *= 0.25

        base = math.ceil(base * skill.severity.value)

        if any(s.name == 'Firm Stance' for s in self.skills):
            base /= 2

        if res is not ResistanceModifier.ABSORB:
            self.hp = base
            result.damage_dealt = base
            result.fainted = self.is_fainted()
        else:
            base /= 2
            self.hp = -base
            result.damage_dealt = -base

        if self.is_fainted() and not self._endured:
            if any(s.name == 'Endure' for s in self.skills):
                self._damage_taken -= 1
                result.fainted = False
                result.endured = self._endured = True
            elif any(s.name == 'Enduring Soul' for s in self.skills):
                self._damage_taken = 0
                result.fainted = False
                result.endured = self._endured = True

        return result

    def try_crit(self, attacker):
        base = CRITICAL_BASE * self._ex_crit_mod
        if any(s.name == 'Apt Pupil' for s in self.skills):
            base *= 3
        if any(s.name == 'Sharp Student' for s in attacker.skills):
            base /= 3
        base += ((self.luck / 10) - ((attacker.luck / 2) / 10))
        base /= attacker.affected_by(StatModifier.SUKU)
        base *= self.affected_by(StatModifier.SUKU)
        return random.uniform(1, 100) <= base

    """ evasion / critical reference
In [58]: for my_suku in (0.95, 1.0, 1.05):
    ...:     for attacker_suku in (0.95, 1.0, 1.05):
    ...:         base = 90  # todo: determine properly
    ...:         base *= attacker_suku
    ...:         base /= my_suku
    ...:         print(f"Attacker: {attacker_suku:.2f}/{90*attacker_suku:.2f} | Me: {my_suku:.2f}/{90/my_suku:.2f} | {100-base:.2f} evasion chance")
    ...:
Attacker: mod \ base * mod | Me: mod \ base / mod | overall evasion chance
Attacker: 0.95/85.50 | Me: 0.95/94.74 | 10.00 evasion chance
Attacker: 1.00/90.00 | Me: 0.95/94.74 | 5.26 evasion chance
Attacker: 1.05/94.50 | Me: 0.95/94.74 | 0.53 evasion chance
Attacker: 0.95/85.50 | Me: 1.00/90.00 | 14.50 evasion chance
Attacker: 1.00/90.00 | Me: 1.00/90.00 | 10.00 evasion chance
Attacker: 1.05/94.50 | Me: 1.00/90.00 | 5.50 evasion chance
Attacker: 0.95/85.50 | Me: 1.05/85.71 | 18.57 evasion chance
Attacker: 1.00/90.00 | Me: 1.05/85.71 | 14.29 evasion chance
Attacker: 1.05/94.50 | Me: 1.05/85.71 | 10.00 evasion chance

In [59]: for my_suku in (0.95, 1.0, 1.05):
    ...:     for attacker_suku in (0.95, 1.0, 1.05):
    ...:         base = 4
    ...:         base /= attacker_suku
    ...:         base += ((my_luck/10) - (attacker_luck/10))
    ...:         base *= my_suku
    ...:         print(f"Attacker: {attacker_suku:.2f} | Me: {my_suku:.2f} | {base:.2f} chance to crit")
    ...:
    ...:
Attacker: mod  | Me: mod  | overall chance to crit
Attacker: 0.95 | Me: 0.95 | 4.00 chance to crit
Attacker: 1.00 | Me: 0.95 | 3.80 chance to crit
Attacker: 1.05 | Me: 0.95 | 3.62 chance to crit
Attacker: 0.95 | Me: 1.00 | 4.21 chance to crit
Attacker: 1.00 | Me: 1.00 | 4.00 chance to crit
Attacker: 1.05 | Me: 1.00 | 3.81 chance to crit
Attacker: 0.95 | Me: 1.05 | 4.42 chance to crit
Attacker: 1.00 | Me: 1.05 | 4.20 chance to crit
Attacker: 1.05 | Me: 1.05 | 4.00 chance to crit
    """

    def try_evade(self, attacker, skill):
        if (
                not skill.is_instant_kill or
                skill.type is not SkillType.AILMENT
        ) and any(s.name == 'Firm Stance' for s in self.skills):
            return False

        ag = self.agility / 10
        if not skill.is_instant_kill:
            base = (skill.accuracy + attacker.agility / 2) - ag / 2
        else:
            base = skill.accuracy - ag / 2
            base += attacker.get_boost_amp_mod(skill.type)  # light/dark only
            if self.resists(skill.type) is ResistanceModifier.WEAK:
                base *= 1.1
            elif self.resists(skill.type) is ResistanceModifier.RESIST:
                base *= 0.9

        passive = self.get_passive_evasion(skill.type)
        if passive:
            base += passive.evasion

        my_suku = self.affected_by(StatModifier.SUKU)
        base *= my_suku
        base /= attacker.affected_by(StatModifier.SUKU)
        # log.debug(f"Attacker: {suku_mod:.2f}/{90 * suku_mod:.2f} |"
        #           f" Me: {my_suku:.2f}/{90 / my_suku:.2f} | {100 - base:.2f} evasion chance")

        if attacker.ailment and attacker.ailment.type is AilmentType.DIZZY:
            base *= 0.25

        if any(s.name == 'Angelic Grace' for s in self.skills):
            base *= 2
        if any(s.name == 'Rainy Play' for s in self.skills):
            if get_current_weather() is Weather.RAIN:
                base *= 2
            elif get_current_weather() is SevereWeather.THUNDER_STORM:
                base *= 3
        return random.uniform(1, 100) > base

    async def save(self, bot):
        data = self.to_json()
        await bot.db.abyss.accounts.replace_one({"owner": self._owner_id}, data, upsert=True)
