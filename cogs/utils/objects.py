import collections
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
# SEV -> Skill Severity, maybe be moved to the last
# RKU -> Targets Raku modifier
# ATK -> Attackers level
# TRG -> Targets level
# BASE ------v
SKILL_BASE = 65  # can be modified if need be


class JSONable:
    __json__ = ()

    @staticmethod
    def _serialize(o):
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
    def __init__(self, name, cost, skills, bot, unlocks=None, unlock_requires=None):
        self.name = name
        self.unlocks = unlocks or []
        self.cost = cost
        self.skills = [bot.players.skill_cache[s] for s in skills]
        self.unlock_requires = unlock_requires or []

    def __repr__(self):
        return f"<SkillTree(leaf) {self.name}, ${self.cost}," \
            f" {len(self.unlocks)} unlocks, {len(self.unlock_requires)} to unlock," \
            f" {len(self.skills)} skills>"


class Branch:
    def __init__(self, name, leaves, bot):
        self.name = name
        self.leaves = {}
        for leafn, data in leaves.items():
            d = {"name": leafn, **data, 'bot': bot}
            leaf = Leaf(**d)
            for unlock in leaf.unlocks:
                if unlock in self.leaves and leafn not in self.leaves[unlock].unlock_requires:
                    self.leaves[unlock].unlock_requires.append(leafn)
            for lock in leaf.unlock_requires:
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


class ListCycle:
    def __init__(self, iterable):
        self._iter = collections.deque(iterable)

    def __repr__(self):
        return f"ListCycle(deque({list(map(str, self._iter))}))"

    def active(self):
        # log.debug("cycle.active() -> %s", list(map(str, self._iter)))
        return self._iter[0]

    def cycle(self):
        # log.debug("cycle.cycle<pre>() -> %s", list(map(str, self._iter)))
        self._iter.append(self._iter.popleft())
        # log.debug("cycle.cycle<post>() -> %s", list(map(str, self._iter)))

    def decycle(self):
        # log.debug("cycle.decycle<pre>() -> %s", list(map(str, self._iter)))
        self._iter.appendleft(self._iter.pop())
        # log.debug("cycle.decycle<pre>() -> %s", list(map(str, self._iter)))

    def remove(self, item):
        # log.debug("cycle.remove<pre>() -> %s", list(map(str, self._iter)))
        self._iter.remove(item)
        self.decycle()
        # log.debug("cycle.remove<post>() -> %s", list(map(str, self._iter)))

    def __next__(self):
        return self.active()


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
        self.severity = Severity[kwargs.pop("severity").upper()]
        self.cost = kwargs.pop("cost")
        self.description = kwargs.pop("desc")
        self.accuracy = kwargs.pop("accuracy", 90)

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

        base = 5 * math.sqrt((attacker.magic if self.uses_sp else attacker.strength) / target.endurance * (
                SKILL_BASE * self.severity.value)) * random.uniform(0.95, 1.05)
        base *= attacker.affected_by(StatModifier.TARU)
        base /= target.affected_by(StatModifier.RAKU)
        base += (attacker.level - target.level)
        return base


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
    def activate(self, player):
        typ = self.name.split(" ")[0]
        player._shields[typ] = 3  # little hacky, but its easiest this way


class StatusMod(Skill):
    def __init__(self, **kwargs):
        name = kwargs['name']
        super().__init__(**kwargs)
        if name.startswith('Dek'):
            self.target = None
        else:  # None for Dekaja/Dekunda
            self.target = StatModifier[name[:4].upper()]
        self.boost = name.endswith("kaja")
        # if the skill is Dekaja, the target is inversed

    def filter_targets(self, battle, enemy=False):
        # return the player if its Dekunda/*Kaja, else the enemies
        if self.target is None:
            if self.boost:  # Dekaja
                return (battle.player,) if enemy else battle.enemies
            # Dekunda
            return battle.enemies if enemy else (battle.player,)
        else:
            if self.boost:  # *kaja
                return battle.enemies if enemy else (battle.player,)
            # *nda
            return (battle.player,) if enemy else battle.enemies


subclasses = {
    "Counter": Counter,
    "Counterstrike": Counter,
    "High Counter": Counter
}
types = ("Curse", "Bless", "Fire", "Elec", "Nuke", "Wind", "Ice", "Psy")
for t in types:
    for r in ("Absorb", "Null", "Repel", "Resist", "Dodge", "Evade"):
        subclasses[f"{r} {t}"] = PassiveImmunity
    subclasses[f"{t} Shield"] = ShieldSkill

for s in ('Taru', 'Raku', 'Suku', 'De'):
    for a in ('kaja', 'nda'):
        if s == 'De' and a == 'nda':
            a = 'kunda'
        subclasses[f"{s}{a}"] = StatusMod


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
