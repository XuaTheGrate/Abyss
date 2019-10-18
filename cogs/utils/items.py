import json
import os

from .targetting import TargetSession
from .enums import ItemType


def dataclass(cls):
    cls.__repr__ = lambda s: f'{type(s).__name__}({", ".join(f"{x}={y!r}" for x, y in vars(s).items())})'
    cls.__eq__ = lambda s, o: isinstance(o, type(s)) and all(x == y for x, y in zip(vars(s).values(), vars(o).values()))
    return cls


class Unusable(Exception):
    # raised when an item cannot be used
    def __init__(self, message="Cannot use that here."):
        super().__init__(message)


@dataclass
class _ItemABC:
    def __new__(cls, **kwargs):
        tp = kwargs.get('type')
        if tp is ItemType.SKILL_CARD:
            cls = SkillCard
        elif tp is ItemType.HEALING:
            cls = HealingItem
        else:
            if 'recipe' in kwargs:
                cls = Craftable
            else:
                cls = TrashItem
        return object.__new__(cls)

    def __init__(self, *, name: str, type: ItemType, worth: int = 1, desc: str = "no desc", weight: int = 0, dungeons: list = None):
        self.name = name
        self.worth = worth
        self.type = type
        self.desc = desc
        self.weight = weight  # drop weight
        self.dungeons = dungeons or []

    def __str__(self):
        return self.name

    def sell_price(self):
        return round(self.worth/2)

    async def use(self, ctx, battle=None):
        raise NotImplementedError


class Craftable(_ItemABC):
    def __init__(self, *, recipe, makes, time, **kwargs):
        super().__init__(**kwargs)
        self.recipe = recipe
        self.makes = makes
        self.time = time

    async def use(self, ctx, battle=None):
        raise Unusable()

    def can_craft(self, inventory):
        for iname, count in self.recipe:
            print(iname, count)
            if not inventory.has_item(iname, count):
                print('no have', iname, count)
                return False
        return True  # return False never triggered, so we must have all the items


class SkillCard(_ItemABC):
    def __init__(self, *, skill, **kwargs):
        super().__init__(**kwargs)
        self.skill = skill
        self.refusable = skill.name not in ()
        # insert names into the tuple to add non-refusable skills

    def sell_price(self):
        return 1  # skill cards dont sell for shit

    async def use(self, ctx, battle=None):
        if battle:
            raise Unusable('You cannot use this item during battle.')
        if self.skill in ctx.player.unset_skills or self.skill in ctx.player.skills:
            raise Unusable("You already learnt this skill.")
        ctx.player.unset_skills.append(self.skill)
        await ctx.send(f"{self.skill} is now learnt. Use `$set {self.skill.name.lower()}` to equip it.")


class TrashItem(_ItemABC):
    async def use(self, ctx, battle=None):
        raise Unusable()


class HealingItem(_ItemABC):
    # todo: battle items such as `Ice Cube` will be a part of this class

    def __init__(self, *, heal_type, heal_amount, target, **kwargs):
        super().__init__(**kwargs)
        self.heal_type = heal_type
        self.heal_amount = heal_amount
        self.target = target

    async def use(self, ctx, battle=None):
        if battle:
            if self.target not in ('ally', 'allies'):
                raise Unusable("Cannot use this item outside of battle")
            s = TargetSession(*battle.players, target=self.target)
            await s.start(ctx)              # v~~~ everyones sp is full
            if self.heal_type == 'sp' and all(not p._sp_used for p in s.result):
                raise Unusable("All targets' SP is full.")
            elif self.heal_type == 'hp' and all(not p._damage_taken for p in s.result):
                raise Unusable("All targets' HP is full.")
            elif self.heal_type == 'ailment' and all(not p.ailment for p in s.result):
                raise Unusable("No targets have a status effect.")
            for target in s.result:
                if self.heal_type == 'hp':
                    target.hp = -self.heal_amount
                elif self.heal_type == 'sp':
                    target.sp = -self.heal_amount
                elif self.heal_type == 'ailment':
                    target.ailment = None
                else:  # might be ice cube like? idk
                    raise Unusable("You cannot use this item right now.")
            if self.heal_type == 'ailment':
                await ctx.send("Everybody recovered from their ailment.")
            else:
                await ctx.send(f"Everybody recovered {self.heal_amount} {self.heal_type.upper()}.")
        else:
            player = ctx.player
            if self.heal_type == 'hp':
                if not player._damage_taken:
                    raise Unusable("HP is full.")
                player.hp = -self.heal_amount
                await ctx.send(f"Recovered {self.heal_amount} HP.")
            elif self.heal_type == 'sp':
                if not player._sp_used:
                    raise Unusable("SP is full.")
                player.sp = -self.heal_amount
                await ctx.send(f"Recovered {self.heal_amount} SP.")
            elif self.heal_type == 'ailment':
                if not player.ailment:
                    raise Unusable("No ailment to recover.")
                player.ailment = None
                await ctx.send(f"Recovered from your ailment.")
            else:
                raise Unusable("You cannot use this item right now.")


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
        return self.items.get(name)
