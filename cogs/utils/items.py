import json
import os

from .enums import ItemType

try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls):
        cls.__repr__ = lambda s: f'{type(s).__name__}({", ".join(f"{x}={y!r}" for x, y in vars(s).items())})'
        cls.__eq__ = lambda s, o: all(x == y for x, y in zip(vars(s).values(), vars(o).values()))
        return cls


@dataclass
class _ItemABC:
    def __new__(cls, **kwargs):
        tp = kwargs.get('type')
        if tp is ItemType.SKILL_CARD:
            cls = SkillCard
        elif tp is ItemType.TRASH:
            cls = TrashItem
        elif tp is ItemType.HEALING:
            cls = HealingItem
        else:
            raise TypeError("unknown item type '{!r}', excepted enum ItemType".format(tp))
        return object.__new__(cls)

    def __init__(self, *, name: str, type: ItemType, worth: int = 1, desc: str = "no desc"):
        self.name = name
        self.worth = worth
        self.type = type
        self.desc = desc

    def __str__(self):
        return self.name

    def sell_price(self):
        return round(self.worth/2)


class SkillCard(_ItemABC):
    def __init__(self, *, name, type, skill, worth=1, desc="no desc"):
        super().__init__(name=name, worth=worth, type=type, desc=desc)
        self.skill = skill
        self.refusable = skill.name not in ()
        # insert names into the tuple to add non-refusable skills

    def sell_price(self):
        return 1  # skill cards dont sell for shit


class TrashItem(_ItemABC):
    pass


class HealingItem(_ItemABC):
    def __init__(self, *, name, type, healtype, healamount, healtarget, worth=1, desc="no desc"):
        super().__init__(name=name, worth=worth, desc=desc, type=type)
        self.heal_type = healtype
        self.heal_amount = healamount
        self.target = healtarget


class _ItemCache:
    def __init__(self, playercog):
        self.items = {}
        for file in os.listdir("items"):
            tp = ItemType[file[:-5].upper()]
            with open("items/"+file) as f:
                itemdata = json.load(f)

            for item in itemdata:
                item['type'] = tp
                if item.get('skill'):
                    item['name'] = item['skill']
                    item['skill'] = playercog.skill_cache[item['skill']]
                self.items[item['name']] = _ItemABC(**item)

    def __repr__(self):
        return repr(self.items.keys())

    def get_item(self, name):
        return self.items[name]
