import collections
import json

from .enums import *


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


class CaseInsensitiveDict(dict):
    def __init__(self, mapping):
        super().__init__()
        self.update(mapping)

    def update(self, mapping=None, **kwargs):
        if mapping:
            if isinstance(mapping, dict):
                mapping = mapping.items()
            mapping = {k.lower(): v for k, v in mapping}
        kwargs = {k.lower(): v for k, v in kwargs}
        return super().update(mapping, **kwargs)

    def __getitem__(self, item):
        if isinstance(item, str):
            item = item.lower()
        return super().__getitem__(item)

    def __setitem__(self, key, value):
        if isinstance(key, str):
            key = key.lower()
        return super().__setitem__(key, value)

    def __delitem__(self, key):
        if isinstance(key, str):
            key = key.lower()
        return super().__delitem__(key)


class DamageResult:
    __slots__ = ('resistance', 'damage_dealt', 'critical', 'miss', 'fainted', 'was_reflected', 'did_weak', 'skill',
                 'countered', 'endured')

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
        self.endured = False

    def __repr__(self):
        return (f"<DamageResult resistance={self.resistance!r} damage_dealt={self.damage_dealt} "
                f"critical={self.critical} miss={self.miss} did_weak={self.did_weak} skill={self.skill}"
                f" countered={self.countered} endured={self.endured}>")


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
