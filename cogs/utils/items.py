import json
import os

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

    async def use(self, ctx):
        raise NotImplementedError


class SkillCard(_ItemABC):
    def __init__(self, *, name, type, skill, worth=1, desc="no desc"):
        super().__init__(name=name, worth=worth, type=type, desc=desc)
        self.skill = skill
        self.refusable = skill.name not in ()
        # insert names into the tuple to add non-refusable skills

    def sell_price(self):
        return 1  # skill cards dont sell for shit

    async def use(self, ctx):
        if self.skill in ctx.player.unset_skills or self.skill in ctx.player.skills:
            raise Unusable("You already learnt this skill.")
        ctx.player.unset_skills.append(self.skill)
        await ctx.send(f"{self.skill} is now learnt. Use `$set {self.skill.name.lower()}` to equip it.")


class TrashItem(_ItemABC):
    async def use(self, ctx):
        raise Unusable()


class HealingItem(_ItemABC):
    def __init__(self, *, name, type, heal_type, heal_amount, target, worth=1, desc="no desc"):
        super().__init__(name=name, worth=worth, desc=desc, type=type)
        self.heal_type = heal_type
        self.heal_amount = heal_amount
        self.target = target

    async def use(self, ctx, battle=None):
        # todo: raise Unusable() when no valid targets (ie everyone max sp/hp or no ailments to heal)
        if battle:
            if self.target == 'allies':
                if self.heal_type == 'sp':
                    if all(p._sp_used == 0 for p in battle.players):
                        raise Unusable("No valid targets.")
                    for p in battle.players:
                        if p._sp_used != 0:
                            p.sp = -self.heal_amount  # no point healing the unhealable
                            await ctx.send(f"> __{p}__ healed {self.heal_amount} SP!")
                elif self.heal_type == 'hp':
                    if all(p._damage_taken == 0 for p in battle.players):
                        raise Unusable("No valid targets.")
                    for p in battle.players:
                        if p._damage_taken != 0:
                            p.hp = -self.heal_amount
                            await ctx.send(f"> __{p}__ healed {self.heal_amount} HP!")
                elif self.heal_type == 'ailment':
                    if self.heal_amount != "all":
                        if all(not p.ailment or p.ailment.type.name.lower() != self.heal_amount for p in
                               battle.players):
                            raise Unusable("No valid targets.")
                    for p in battle.players:
                        if p.ailment and (self.heal_amount == 'all' or p.ailment.type.name.lower() == self.heal_amount):
                            p.ailment = None
                            await ctx.send(f"> __{p}__ recovered!")
        else:
            # only one target available
            if self.heal_type == 'sp':
                if ctx.player._sp_used == 0:
                    raise Unusable("SP is full.")
                ctx.player.sp = -self.heal_amount
                await ctx.send(f"Recovered {self.heal_amount} SP.")
            elif self.heal_type == 'hp':
                if ctx.player._damage_taken == 0:
                    raise Unusable("HP is full.")
                ctx.player.hp = -self.heal_amount
                await ctx.send(f"Recovered {self.heal_amount} HP.")
            elif self.heal_type == 'ailment':
                if ctx.player.ailment and (
                        self.heal_amount == 'all' or ctx.player.ailment.type.name.lower() == self.heal_amount):
                    ctx.player.ailment = None
                    await ctx.send(f"Recovered from your ailment.")
                else:
                    raise Unusable()


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
