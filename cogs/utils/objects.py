import json
import math
import random

from .enums import *

# Damage calc
# DMG = (5 * sqrt(Strength or Magic/Endurance*SkillPower) * random(0.95, 1.05)) / Raku

SKILL_BASE = 65


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
    __slots__ = ('resistance', 'damage_dealt', 'critical', 'miss', 'fainted', 'was_reflected', 'did_weak')

    def __init__(self):
        self.resistance = ResistanceModifier.NORMAL
        self.damage_dealt = 0
        self.critical = False
        self.miss = False
        self.fainted = False
        self.was_reflected = False
        self.did_weak = False

    def __repr__(self):
        return (f"<DamageResult resistance={self.resistance!r} damage_dealt={self.damage_dealt} "
                f"critical={self.critical} miss={self.miss} did_weak={self.did_weak}>")


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
    __slots__ = ('name', 'type', 'severity', 'cost', 'accuracy', 'description')
    __json__ = (*__slots__[:-1], 'desc')

    def keygetter(self, key):
        if key == 'type':
            return self.type.value
        elif key == 'severity':
            return self.severity.name
        elif key == 'desc':
            return self.description
        return getattr(self, key)

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
        # :attr:`.accuracy` usually only applies to Instant-Kill types

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
        return base
