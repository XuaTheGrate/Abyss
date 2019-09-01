import json
import os

from .enums import ItemType


class _ItemABC:
    def __new__(cls, **kwargs):
        tp = kwargs.get('type')
        if tp is ItemType.SKILL_CARD:
            cls = SkillCard
        elif tp is ItemType.TRASH:
            cls = TrashItem
        else:
            raise TypeError("unknown item type '%r', excepted enum ItemType" % tp)
        return object.__new__(cls)

    def __init__(self, *, name: str, type: ItemType, worth: int = 1, desc: str = "no desc"):
        self.name = name
        self.worth = worth
        self.type = type
        self.desc = desc

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'{type(self).__name__}(name={self.name!r}, worth={self.worth!r}, type={self.type!r})'

    def sell_price(self):
        return round(self.worth/2)


class SkillCard(_ItemABC):
    def __init__(self, *, name, worth, desc, type, skill):
        super().__init__(name=name, worth=worth, type=type, desc=desc)
        self.skill = skill
        self.refusable = skill.name not in ()
        # insert names into the tuple to add non-refusable skills

    def sell_price(self):
        return 1  # skill cards dont sell for shit


class TrashItem(_ItemABC):
    pass


class HealingItem(_ItemABC):
    def __init__(self, *, name, worth, desc, type, healtype, healamount, healtarget):
        super().__init__(name=name, worth=worth, desc=desc, type=type)
        self.heal_type = healtype
        self.heal_amount = healamount
        self.target = healtarget


class _ItemCache:
    def __init__(self):
        self.items = {}
        for file in os.listdir("items"):
            tp = ItemType[file[:-5].upper()]
            with open("items/"+file) as f:
                itemdata = json.load(f)

            for item in itemdata:
                item['type'] = tp
                self.items[item['name']] = _ItemABC(**tp)

    def __repr__(self):
        return repr(list(self.items))

    def get_item(self, name):
        return self.items[name]


item_cache = _ItemCache()
