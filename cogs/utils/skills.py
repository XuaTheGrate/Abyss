import math
import random

from . import weather
from .enums import *
from .lookups import WEATHER_TO_TYPE, STAT_MOD
from .objects import JSONable


# Damage calc
# DMG = ((5 * sqrt(STRMAG / END * BASE) * RNG * TRU) / RKU) + (ATK - TRG)
# STRMAG -> Attackers Strength if physical, Magic otherwise
# END -> Targets Endurance
# RNG -> uniform(0.95, 1.05)
# TRU -> Attackers Taru modifier
# RKU -> Targets Raku modifier
# ATK -> Attackers level
# TRG -> Targets level
# BASE ------v
SKILL_BASE = 65  # can be modified if need be


class Skill(JSONable):
    __json__ = ('name', 'type', 'severity', 'cost', 'accuracy', 'desc')

    def keygetter(self, key):
        if key == 'type':
            return self.type.value
        elif key == 'severity':
            return self.severity.name
        elif key == 'desc':
            return self.description
        return getattr(self, key)

    def __new__(cls, **kwargs):
        name = kwargs['name']
        new_cls = subclasses.get(name, None)
        if new_cls:
            cls = new_cls
        self = object.__new__(cls)
        # noinspection PyArgumentList
        cls.__init__(self, **kwargs)
        return self

    def __init__(self, **kwargs):
        self.name = kwargs.pop("name")
        type_ = kwargs.pop("type")
        try:
            self.type = SkillType[type_.upper()]
        except AttributeError:
            # noinspection PyArgumentList
            self.type = SkillType(type_)
        self.severity = Severity[kwargs.pop("severity", "light").upper()]
        self.cost = kwargs.pop("cost", 0)
        self.description = kwargs.pop("desc")
        self.accuracy = kwargs.pop("accuracy", 90)
        self.hits = (kwargs.pop("min_hits", 1), kwargs.pop("max_hits", 1))
        self.target = kwargs.pop("target", "enemy")

        self.is_evasion = False

    @property
    def is_counter_like(self):
        return isinstance(self, Counter)

    @property
    def is_passive_immunity(self):
        return isinstance(self, PassiveImmunity)

    @property
    def is_status_skill(self):
        return isinstance(self, StatusMod)

    def __repr__(self):
        return f"<{type(self).__name__} {self.name!r}, {self.type.name.lower()}>"

    def __str__(self):
        return self.name

    def _debug_repr(self):
        return f"""```
Skill
    name: {self.name}
    type: {self.type!r}
    severity: {self.severity!r}
    cost: {self.cost}
    desc: {self.description}
    accuracy: {self.accuracy}

    uses_sp: {self.uses_sp}
    is_instant_skill: {self.is_instant_kill}
    is_damaging_skill: {self.is_damaging_skill}
```"""

    @property
    def uses_sp(self):
        return self.type not in (SkillType.PHYSICAL, SkillType.GUN)

    @property
    def is_instant_kill(self):
        return any(x.lower() in self.name.lower() for x in ('Hama', 'Mudo', 'Die for Me!', 'Samsara'))

    @property
    def is_damaging_skill(self):
        return self.type not in (SkillType.HEALING, SkillType.AILMENT, SkillType.SUPPORT, SkillType.PASSIVE)

    def damage_calc(self, attacker, target):
        if self.is_instant_kill:
            return target.hp

        base = 5 * math.sqrt((attacker.magic if self.uses_sp else attacker.strength) / target.endurance *
                             SKILL_BASE) * random.uniform(0.95, 1.05)
        base *= attacker.affected_by(StatModifier.TARU)
        base /= target.affected_by(StatModifier.RAKU)
        base += (attacker.level - target.level)

        we = weather.get_current_weather()

        if isinstance(we, SevereWeather):
            wmod = 3
        else:
            wmod = 2

        weather_mod = WEATHER_TO_TYPE.get(we.name)
        if weather_mod == self.type.name:
            base *= wmod

        if self.type is SkillType.WIND:
            base += weather.get_wind_speed()

        if self.uses_sp:
            if attacker._concentrating:
                attacker._concentrating = False
                base *= 2.5
        else:
            if attacker._charging:
                attacker._charging = False
                base *= 2.5

        return max(1, base)


class Counter(Skill):
    def try_counter(self, user, target):
        # we use accuracy here as a hack for how often Counter will proc
        base = self.accuracy + (user.luck-target.luck)
        return random.randint(1, 100) < base


_passive_handles = {
    "Absorb": ResistanceModifier.ABSORB,
    "Repel": ResistanceModifier.REFLECT,
    "Null": ResistanceModifier.IMMUNE,
    "Resist": ResistanceModifier.RESIST
}


class PassiveImmunity(Skill):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_evasion = self.name.startswith(("Dodge", "Evade"))

    def immunity_handle(self):
        if self.is_evasion:
            return self.accuracy  # we use 20 for Evade, or 10 for Dodge
        return _passive_handles[self.name.split(" ")[0]]


class ShieldSkill(Skill):
    def effect(self, targets):
        typ = self.name.split(" ")[0]
        for t in targets:
            t._shields[typ] = 3  # little hacky, but its easiest this way


class StatusMod(Skill):
    async def effect(self, battle, targets):
        if self.name == 'Dekunda':
            for target in targets:
                s = False
                for i in range(3):
                    if target._stat_mod[i] == -1:
                        target._stat_mod[i] = 0
                        target._until_clear[i] = -1
                        s = True
                if s:
                    await battle.ctx.send(f"> __{target}__'s stat decrease nullified.")
        elif self.name == 'Dekaja':
            for target in targets:
                s = False
                for i in range(3):
                    if target._stat_mod[i] == 1:
                        target._stat_mod[i] = 0
                        target._until_clear[i] = -1
                        s = True
                if s:
                    await battle.ctx.send(f"> __{target}__'s stat increase nullified.")
        elif self.name not in ('Debilitate', 'Heat Riser'):
            up = 1 if self.name.endswith("kaja") else -1
            mod = StatModifier[self.name[:4].upper()].value
            for target in targets:
                if target._stat_mod[mod] == up:
                    target._until_clear[mod] = 4
                    await battle.ctx.send(f"> __{target}__'s {STAT_MOD[mod]} boost extended.")
                else:
                    target._stat_mod[mod] += up
                    if target._stat_mod[mod] == 0:
                        target._until_clear[mod] = -1
                    else:
                        target._until_clear[mod] = 4
                    await battle.ctx.send(f"> __{target}__'s {STAT_MOD[mod]} {'increased' if up==1 else 'decreased'}.")
        else:
            await battle.ctx.send("sec")


subclasses = {
    "Counter": Counter,
    "Counterstrike": Counter,
    "High Counter": Counter
}
types = ("Curse", "Bless", "Fire", "Elec", "Nuke", "Wind", "Ice", "Psy", "Phys")
for t in types:
    for r in ("Absorb", "Null", "Repel", "Resist", "Dodge", "Evade"):
        subclasses[f"{r} {t}"] = PassiveImmunity
    subclasses[f"{t} Shield"] = ShieldSkill

for s in ('Taru', 'Raku', 'Suku', 'De'):
    for a in ('kaja', 'nda'):
        if s == 'De' and a == 'nda':
            a = 'kunda'
        subclasses[f"{s}{a}"] = StatusMod

subclasses['Debilitate'] = subclasses['Heat Riser'] = StatusMod


GenericAttack = Skill(
    name="Attack",
    cost=0,
    type="physical",
    severity="miniscule",  # TBD: light or miniscule
    desc="A regular attack."
)

Guard = Skill(
    name="Guard",
    cost=0,
    type="support",
    severity="light",
    desc="Reduce damage taken for one hit."
)
