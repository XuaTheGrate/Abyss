import math
import operator
import random
import re

from .enums import *
from .objects import DamageResult, JSONable, Skill, GenericAttack
from .lookups import TYPE_SHORTEN


CRITICAL_BASE = 4


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
            return [z.name for z in self.unset_skills]
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
            self._skills = skills
        self.skills.append(GenericAttack)
        self.exp = kwargs.pop("exp")
        self.strength, self.magic, self.endurance, self.agility, self.luck = kwargs.pop("stats")
        # self.resistances = dict(zip(SkillType, map(ResistanceModifier, kwargs.pop("resistances"))))
        self._resistances = kwargs.pop("resistances")
        self.resistances = dict(zip(SkillType, [
                    ResistanceModifier.WEAK if x == 3
                    else ResistanceModifier.NORMAL if x == 2
                    else ResistanceModifier.RESIST
                    for x in self._resistances]))
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
        self._next_level = self.level+1
        self.finished_leaves = kwargs.pop("finished_leaves", [])

    def __str__(self):
        return self.name

    def __repr__(self):
        return (f"Player(owner={self._owner_id}, "
                f"name='{self.name}', "
                f"skills={self.skills}, "
                f"exp={self.exp}, "
                f"stats={self.stats}, "
                f"resistances={self._resistances}, "
                f"description='{self.description}', "
                f"stat_points={self.stat_points}, "
                f"arcana={self.arcana.value}, "
                f"specialty='{self.specialty.name}', "
                f"skill_leaf='{self._active_leaf}', "
                f"ap={self.ap_points}, "
                f"unsetskills={self._unset_skills}, "
                f"finished_leaves={self.finished_leaves})")

    def _debug_repr(self):
        return f"""```
Player
    name: {self.name}
    skills: {", ".join(map(operator.attrgetter('name'), self.skills))}
    exp: {self.exp}
    stats: {self.stats}
    resistances: {self._resistances}
    description: {self.description}
    stat_points: {self.stat_points}
    arcana: {self.arcana!r}
    specialty: {self.specialty!r}
    leaf: {self.leaf}
    ap_points: {self.ap_points}
    finished_leaves: {self.finished_leaves}
    unset_skills: {self.unset_skills}

    level: {self.level}
    hp: {self.hp}
    max_hp: {self.max_hp}
    sp: {self.sp}
    max_sp: {self.max_sp}
    can_level_up: {self.can_level_up}
    exp_tp_next_level: {self.exp_to_next_level()}
    is_fainted: {self.is_fainted()}

    debug: {self.debug}
    _damage_taken: {self._damage_taken}    
    _sp_used: {self._sp_used}
    _stat_mod: {self._stat_mod}
    _until_clear: {self._until_clear}
    _next_level: {self._next_level}
    _active_leaf: {self._active_leaf}
```"""

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
        else:
            self._sp_used += round(value)

    @property
    def max_sp(self):
        return math.ceil(10 + self.magic + (3.6 * self.level))

    @property
    def level(self):
        return min(99, max(math.floor(self.exp**.333), 1))

    def level_up(self):
        while self._next_level <= self.level:
            self._next_level += 1
            self.stat_points += 3

    @property
    def can_level_up(self):
        return self._next_level <= self.level

    def exp_to_next_level(self):
        return self._next_level**3 - self.exp

    def _populate_skills(self, bot):
        self.owner = bot.get_user(self._owner_id)
        for skill in self._skills:
            self.skills.append(bot.players.skill_cache[skill])
        for skill in self._unset_skills:
            self.unset_skills.append(bot.players.skill_cache[skill])

    def affected_by(self, modifier):
        modifier = getattr(modifier, 'value', modifier)

        return 1.0 if self._stat_mod[modifier] == 0 \
            else 1.05 if self._stat_mod[modifier] == 1 \
            else 0.95

    def resists(self, type):
        passive = self.get_passive_immunity(type)
        if passive and not passive.is_evasion:
            return passive.immunity_handle()
        try:
            return self.resistances[type]
        except KeyError:
            if not isinstance(type, SkillType):
                raise
            return ResistanceModifier.NORMAL

    def is_fainted(self):
        if self.hp <= 0:
            self._stat_mod = [0, 0, 0]
            return True
        return False

    def get_counter(self):
        h = None
        for skill in self.skills:
            if skill.is_counter_like:
                if not h:
                    h = skill
                else:
                    if skill.base > h.base:  # high counter has higher priority over counterstrike
                        h = skill
        return h

    def get_passive_immunity(self, type):
        fmt = re.compile(fr"(?:Null|Repel|Absorb|Resist|Dodge|Evade) {TYPE_SHORTEN[type.name.lower()].title()}")
        for skill in self.skills:
            if skill.is_passive_immunity and fmt.findall(skill.name):
                return skill

    def take_damage(self, attacker, skill, *,  from_reflect=False, counter=False):
        res = self.resists(skill.type)
        result = DamageResult()
        result.skill = skill
        if counter:
            result.countered = True

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
            if s_counter and s_counter.try_counter(attacker, self, skill):
                return attacker.take_damage(self, skill, counter=True)

        result.resistance = res

        if res is ResistanceModifier.IMMUNE:
            return result

        if self.try_evade(attacker.agility/10, skill, attacker.affected_by(StatModifier.SUKU)):
            result.miss = True
            return result

        if skill.is_instant_kill:
            self.hp = self.max_hp
            result.damage_dealt = self.max_hp
            return result

        base = skill.damage_calc(attacker, self)

        if from_reflect or counter:
            base /= 1.35  # reflected damage is weakened
        else:  # counters arent supposed to crit :^^)
            if not skill.uses_sp and res is not ResistanceModifier.WEAK:  # weakness comes before criticals
                if attacker.try_crit(self.luck, self.affected_by(StatModifier.SUKU)):
                    base *= 1.75
                    result.critical = True
                    result.did_weak = True

        if res is ResistanceModifier.WEAK:
            base *= 1.5
            result.did_weak = True
        elif res is ResistanceModifier.RESIST:
            base *= 0.5

        base = math.ceil(base)

        if res is not ResistanceModifier.ABSORB:
            self.hp = base
            result.damage_dealt = base
            result.fainted = self.is_fainted()
        else:
            base /= 2
            self.hp = -base
            result.damage_dealt = -base

        return result

    def try_crit(self, luck_mod, suku_mod):
        base = CRITICAL_BASE
        base /= suku_mod
        base += ((self.luck/10) - (luck_mod/10))
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

    def try_evade(self, modifier, skill, suku_mod):
        ag = self.agility / 10
        if not skill.is_instant_kill:
            base = (skill.accuracy + modifier/2) - ag/2
        else:
            base = skill.accuracy - ag/2
            if self.resists(skill.type) is ResistanceModifier.WEAK:
                base *= 1.1
            elif self.resists(skill.type) is ResistanceModifier.RESIST:
                base *= 0.9

        passive = self.get_passive_immunity(skill.type)
        if passive and passive.is_evasion:
            base += passive.immunity_handle()

        my_suku = self.affected_by(StatModifier.SUKU)
        base *= my_suku
        base /= suku_mod
        log.debug(f"Attacker: {suku_mod:.2f}/{90*suku_mod:.2f} |"
                  f" Me: {my_suku:.2f}/{90/my_suku:.2f} | {100-base:.2f} evasion chance")
        return random.uniform(1, 100) > base

    async def save(self, bot):
        data = self.to_json()
        await bot.db.abyss.accounts.replace_one({"owner": self._owner_id}, data, upsert=True)
