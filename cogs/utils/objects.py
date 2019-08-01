import json
import math
import random

from .enums import *

# Damage calc
# DMG = ((5 * sqrt(STRMAG / END * BASE) * RNG * TRU * SEV) / RKU) + (ATK - TRG)
# STRMAG -> Attackers Strength if physical, Magic otherwise
# END -> Targets Endurance
# RNG -> uniform(0.95, 1.05)
# TRU -> Attackers Taru modifier
# SEV -> Skill Severity
# RKU -> Targets Raku modifier
# ATK -> Attackers level
# TRG -> Targets level
# BASE -v
SKILL_BASE = 65  # can be modified if need be


class JSONable:
    __json__ = ()

    def _serialize(self, o):
        return {k: o.keygetter(k) for k in o.__json__ if not k.startswith('_')}

    def keygetter(self, key):
        return getattr(self, key)

    def to_json(self):
        ret = json.loads(json.dumps(self, default=self._serialize))
        return ret


class DamageResult:
    __slots__ = ('resistance', 'damage_dealt', 'critical', 'miss', 'fainted', 'was_reflected', 'did_weak', 'skill',
                 'countered')

    def __init__(self):
        self.resistance = ResistanceModifier.NORMAL
        self.damage_dealt = 0
        self.critical = False
        self.miss = False
        self.fainted = False
        self.was_reflected = False
        self.did_weak = False
        self.skill = None
        self.countered = False

    def __repr__(self):
        return (f"<DamageResult resistance={self.resistance!r} damage_dealt={self.damage_dealt} "
                f"critical={self.critical} miss={self.miss} did_weak={self.did_weak} skill={self.skill}"
                f" countered={self.countered}>")


class Leaf:
    def __init__(self, name, cost, skills, bot, unlocks=None, unlockRequires=None):
        self.name = name
        self.unlocks = unlocks or []
        self.cost = cost
        self.skills = [bot.players.skill_cache[s] for s in skills]
        self.unlockRequires = unlockRequires or []

    def __repr__(self):
        return f"<SkillTree(leaf) {self.name}, ${self.cost}," \
            f" {len(self.unlocks)} unlocks, {len(self.unlockRequires)} to unlock," \
            f" {len(self.skills)} skills>"


class Branch:
    def __init__(self, name, leaves, bot):
        self.name = name
        self.leaves = {}
        for leafn, data in leaves.items():
            d = {"name": leafn, **data, 'bot': bot}
            leaf = Leaf(**d)
            for unlock in leaf.unlocks:
                if unlock in self.leaves and leafn not in self.leaves[unlock].unlockRequires:
                    self.leaves[unlock].unlockRequires.append(leafn)
            for lock in leaf.unlockRequires:
                if lock in self.leaves and leafn not in self.leaves[lock].unlocks:
                    self.leaves[lock].unlocks.append(leafn)
            self.leaves[leafn] = leaf

    def __repr__(self):
        return f"<SkillTree(branch) {self.name}, {len(self.leaves)} leaves>"


class SkillTree:
    def __init__(self, data, bot):
        self.branches = {}
        for branchname, branchdata in data.items():
            self.branches[branchname] = Branch(branchname, branchdata, bot)

    def __repr__(self):
        return f"<SkillTree {len(self.branches)} branches>"


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
        new_cls = passives.get(name, None)
        if new_cls:
            cls = new_cls
        self = object.__new__(cls)
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
        self.severity = Severity[kwargs.pop("severity").upper()]
        self.cost = kwargs.pop("cost")
        self.description = kwargs.pop("desc")
        self.accuracy = kwargs.pop("accuracy", 90)

        # for subclasses
        self.is_counter_like = False
        self.is_passive_immunity = False
        self.is_evasion = False

    def __repr__(self):
        return (f"Skill(name='{self.name}', "
                f"type={self.type.value}, "
                f"severity='{self.severity.name}', "
                f"cost={self.cost}, "
                f"desc='{self.description}', "
                f"accuracy={self.accuracy})")

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

        base = 5 * math.sqrt((attacker.magic if self.uses_sp else attacker.strength) / target.endurance * (
                SKILL_BASE * self.severity.value)) * random.uniform(0.95, 1.05)
        base *= attacker.affected_by(StatModifier.TARU)
        base /= target.affected_by(StatModifier.RAKU)
        base += (attacker.level - target.level)
        return base


class Counter(Skill):
    base = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_counter_like = True

    def try_counter(self, user, target, skill):
        if skill.uses_sp:
            return False
        base = 10 + (user.luck-target.luck)
        return random.randint(1, 100) < base


class Counterstrike(Counter):
    base = 15


class HighCounter(Counter):
    base = 20


_passive_handles = {
    "Absorb": ResistanceModifier.ABSORB,
    "Repel": ResistanceModifier.REFLECT,
    "Null": ResistanceModifier.IMMUNE,
    "Resist": ResistanceModifier.RESIST
}


class PassiveImmunity(Skill):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_passive_immunity = True
        self.is_evasion = self.name.startswith(("Dodge", "Evade"))

    def immunity_handle(self):
        if self.is_evasion:
            return self.accuracy  # :^) we use 20 for Evade, or 10 for Dodge
        return _passive_handles[self.name.split(" ")[0]]


passives = {
    "Counter": Counter,
    "Counterstrike": Counterstrike,
    "High Counter": HighCounter
}

for t in ("Curse", "Bless", "Fire", "Elec", "Nuke", "Wind", "Ice", "Psy"):
    for r in ("Absorb", "Null", "Repel", "Resist", "Dodge", "Evade"):
        passives[f"{r} {t}"] = PassiveImmunity


GenericAttack = Skill(
    name="Attack",
    cost=0,
    type="physical",
    severity="miniscule",
    desc="A regular attack."
)

Guard = Skill(
    name="Guard",
    cost=0,
    type="support",
    severity="light",
    desc="Reduce damage taken for one hit."
)
