import math
import random

from . import ailments, weather
from .enums import (
    AilmentType,
    ResistanceModifier,
    Severity,
    SevereWeather,
    SkillType,
    StatModifier,
)
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
        if key == 'severity':
            return self.severity.name
        if key == 'desc':
            return self.description
        return getattr(self, key)

    # pylint: disable=self-cls-assignment
    def __new__(cls, **kwargs):
        name = kwargs['name']
        new_cls = SUBCLASSES.get(name, None)
        if new_cls:
            cls = new_cls
        if kwargs['type'] == 'ailment':
            cls = AilmentSkill
        return object.__new__(cls)
    # pylint: enable=self-cls-assignment

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

    @property
    def is_default(self):
        return self.name in ('Guard', 'Attack')

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
        return any(x.lower() in self.name.lower() for x in ('Hama', 'Mudo', 'Die For Me!', 'Samsara'))

    @property
    def is_damaging_skill(self):
        return self.type not in (SkillType.HEALING, SkillType.AILMENT, SkillType.SUPPORT, SkillType.PASSIVE)

    def damage_calc(self, attacker, target):
        if self.is_instant_kill:
            return target.hp

        base = 5 * math.sqrt((attacker.magic if self.uses_sp else attacker.strength) / target.endurance * SKILL_BASE)
        base *= attacker.affected_by(StatModifier.TARU)
        base /= target.affected_by(StatModifier.RAKU)
        base += (attacker.level - target.level)

        current_weather = weather.get_current_weather()

        if isinstance(current_weather, SevereWeather):
            wmod = 3
        else:
            wmod = 2

        weather_mod = WEATHER_TO_TYPE.get(current_weather.name)
        if weather_mod == self.type.name:
            base *= wmod

        if self.type is SkillType.WIND:
            base += weather.get_wind_speed()

        if self.uses_sp:
            if attacker.concentrating:
                base *= 2.5
        else:
            if attacker.charging:
                base *= 2.5

        return max(1, base * random.uniform(0.75, 1.25))


class Counter(Skill):
    def try_counter(self, user, target):
        # we use accuracy here as a hack for how often Counter will proc
        base = self.accuracy + (user.luck-target.luck)
        return random.randint(1, 100) < base


PASSIVE_HANDLES = {
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
        return PASSIVE_HANDLES[self.name.split(" ")[0]]


class ShieldSkill(Skill):
    async def effect(self, battle, targets):
        typ = self.name.split(" ")[0]
        for target in targets:
            if target.shields.get(typ):
                continue
            target.shields[typ] = 3  # little hacky, but its easiest this way
        await battle.ctx.send(f"> Party become protected by an anti-{typ.lower()} shield!")


class Karn(Skill):
    async def effect(self, battle, targets):  # pylint: disable=unused-argument
        target = targets[0]  # single target
        setattr(target, '_'+self.name.lower(), True)


class StatusMod(Skill):
    async def effect(self, battle, targets):
        if self.name == 'Dekunda':
            for target in targets:
                did = False
                for i in range(3):
                    if target.stat_mod[i] == -1:
                        target.stat_mod[i] = 0
                        target.until_clear[i] = -1
                        did = True
                if did:
                    await battle.ctx.send(f"> __{target}__'s stat decrease nullified.")
        elif self.name == 'Dekaja':
            for target in targets:
                did = False
                for i in range(3):
                    if target.stat_mod[i] == 1:
                        target.stat_mod[i] = 0
                        target.until_clear[i] = -1
                        did = True
                if did:
                    await battle.ctx.send(f"> __{target}__'s stat increase nullified.")
        elif self.name not in ('Debilitate', 'Heat Riser'):
            boost = 1 if self.name.endswith("kaja") else -1
            mod = StatModifier[self.name[:4].upper()].value
            for target in targets:
                if target.stat_mod[mod] == boost:
                    target.until_clear[mod] = 4
                    await battle.ctx.send(f"> __{target}__'s {STAT_MOD[mod]} boost extended.")
                else:
                    target.stat_mod[mod] += boost
                    if target.stat_mod[mod] == 0:
                        target.until_clear[mod] = -1
                    else:
                        target.until_clear[mod] = 4
                    await battle.ctx.send(f"> __{target}__'s {STAT_MOD[mod]} "
                                          f"{'increased' if boost==1 else 'decreased'}.")
        else:
            boost = 1 if self.name == 'Heat Riser' else -1
            for target in targets:
                for mod in range(3):
                    if target.stat_mod[mod] == boost:
                        target.until_clear[mod] = 4
                    else:
                        target.stat_mod[mod] += boost
                        if target.stat_mod[mod] == 0:
                            target.until_clear[mod] = -1
                        else:
                            target.until_clear[mod] = 4
                await battle.ctx.send(f"> __{target}__'s Attack, Defense, Agility/Evasion "
                                      f"{'increased' if boost==1 else 'decreased'}.")


class HealingSkill(Skill):
    async def effect(self, battle, targets):
        user = battle.order.active()
        if self.severity is Severity.LIGHT:
            min, max = 40, 60
        elif self.severity is Severity.MEDIUM:
            min, max = 170, 190
        else:
            for target in targets:
                target.damage_taken = 0
                await battle.ctx.send(f"> __{target}__ was healed for {target.max_hp} HP!")
            return
        if any(s.name == 'Divine Grace' for s in user.skills):
            min *= 1.5  # light -> 60, 90
            max *= 1.5  # medium -> 255, 285
        for target in targets:
            heal = random.uniform(min, max)
            target.hp = -heal  # it gets rounded anyways
            await battle.ctx.send(f"> __{target}__ was healed for {heal:.0f} HP!")


class Salvation(HealingSkill):
    async def effect(self, battle, targets):
        for target in targets:
            if target.ailment:
                target.ailment = None
        await super().effect(battle, targets)


class Cadenza(HealingSkill):
    async def effect(self, battle, targets):
        for target in targets:
            target.stat_mod[2] += 1
            if target.stat_mod[2] == 0:
                target.until_clear[2] = -1
            else:
                target.until_clear[2] = 4
        await super().effect(battle, targets)


class Oratorio(HealingSkill):
    async def effect(self, battle, targets):
        for target in targets:
            for mod in range(3):
                if target.stat_mod[mod] == -1:
                    target.stat_mod[mod] = 0
                    target.until_clear[mod] = -1
        await super().effect(battle, targets)


class Charge(Skill):
    async def effect(self, battle, targets):
        target = targets[0]  # only targets the user
        if self.name == 'Charge':
            target.charging = True
        else:
            target.concentrating = True
        await battle.ctx.send(f"> __{target}__ is focused!")


class AilmentSkill(Skill):
    def __init__(self, **kwargs):
        self.ailment = AilmentType[kwargs.pop('ailment').upper()]
        super().__init__(**kwargs)

    async def effect(self, battle, targets):
        ailment = getattr(ailments, self.ailment.name.title())
        for target in targets:
            if target.ailment is not None:
                continue
            if not target.try_evade(battle.order.active(), self):  # ailment landed
                target.ailment = ailment(target, self.ailment)
                await battle.ctx.send(f"> __{target}__ was inflicted with **{target.ailment.name}**")


SUBCLASSES = {
    "Counter": Counter,
    "Counterstrike": Counter,
    "High Counter": Counter
}
SKILL_TYPES = ("Curse", "Bless", "Fire", "Elec", "Nuke", "Wind", "Ice", "Psy", "Phys")
for skill_type in SKILL_TYPES:
    for r in ("Absorb", "Null", "Repel", "Resist", "Dodge", "Evade"):
        SUBCLASSES[f"{r} {skill_type}"] = PassiveImmunity
    SUBCLASSES[f"{skill_type} Shield"] = ShieldSkill

for stat in ('Taru', 'Raku', 'Suku', 'De'):
    for mod in ('kaja', 'nda'):
        if stat == 'De' and mod == 'nda':
            mod = 'kunda'
        SUBCLASSES[f"{stat}{mod}"] = StatusMod

for stat in ('', 'rama', 'rahan'):
    SUBCLASSES['Dia' + stat] = HealingSkill
    SUBCLASSES['Media' + stat] = HealingSkill

SUBCLASSES['Cadenza'] = Cadenza
SUBCLASSES['Oratorio'] = Oratorio
SUBCLASSES['Salvation'] = Salvation
SUBCLASSES['Tetrakarn'] = SUBCLASSES['Makarakarn'] = Karn
SUBCLASSES['Charge'] = SUBCLASSES['Concentrate'] = Charge
SUBCLASSES['Debilitate'] = SUBCLASSES['Heat Riser'] = StatusMod


GenericAttack = Skill(  # pylint: disable=invalid-name
    name="Attack",
    cost=0,
    type="physical",
    severity="miniscule",  # todo: light or miniscule
    desc="A regular attack."
)

Guard = Skill(  # pylint: disable=invalid-name
    name="Guard",
    cost=0,
    type="support",
    severity="light",
    desc="Reduce damage taken for one hit."
)
