from cogs.utils.player import Player
from cogs.utils.objects import Skill
from cogs.utils import enums


pdata = {
    "owner": 1234,
    "name": "Cu Chulainn",
    "skills": ["Ziodyne", "Primal Force", "High Counter", "Repel Fire"],
    "exp": 185124,
    "stats": [45, 37, 40, 53, 39],
    "resistances": [1, 2, 2, 2, 4, 3, 2, 2, 0, 2],
    "arcana": 16,
    "specialty": "ELECTRIC",
    "description": "A test description. Shouldn't matter that badly.",
    "stat_points": 3,
    "skill_leaf": "curse:1",
    "ap": 50,
    "unsetskills": ["Mazionga"],
    "finished_leaves": ["curse:0"]
}

skill_cache = {
    "Attack": Skill(
        name="Attack",
        type="physical",
        severity="light",
        cost=0,
        desc="An electric move."
    ),
    "Guard": Skill(
        name="Guard",
        type="support",
        severity="light",
        cost=0,
        desc="An electric move."
    ),
    "Ziodyne": Skill(
        name="Ziodyne",
        type="electric",
        severity="heavy",
        cost=12,
        desc="An electric move."
    ),
    "Primal Force": Skill(
        name="Primal Force",
        type="physical",
        severity="severe",
        cost=20,
        desc="some phys move"
    ),
    "High Counter": Skill(
        name="High Counter",
        type="passive",
        severity="light",
        cost=0,
        desc="h"
    ),
    "Repel Fire": Skill(
        name="Repel Fire",
        type="passive",
        severity="light",
        cost=0,
        desc="h"
    ),
    "Mazionga": Skill(
        name="Mazionga",
        type="electric",
        severity="medium",
        cost=16,
        desc="An electric move."
    )
}


class DummyAttrs:
    skill_cache = skill_cache


class DummyBot:
    players = DummyAttrs()

    def get_user(self, id):
        return id - 1


import builtins
class Thing:
    def __getattr__(self, item):
        return lambda *__, **_: None
builtins.log = Thing()
bot=DummyBot()


def run():
    player = Player(**pdata)
    player._populate_skills(bot)
    assert player.level == 56, player.level
    assert player.max_hp == 324, player.max_hp
    assert player.exp_to_next_level() == 69, player.exp_to_next_level()
    assert player.arcana is enums.Arcana.TOWER, repr(player.arcana)
    assert player.owner == player._owner_id - 1, (player.owner, player._owner_id)

    assert skill_cache['Ziodyne'] in player.skills, player.skills
    assert skill_cache['Mazionga'] in player.unset_skills, player.unset_skills

    assert player.affected_by(enums.StatModifier.TARU) == 1.0, player.affected_by(enums.StatModifier.TARU)

    assert player.resists(enums.SkillType.ELECTRIC) is enums.ResistanceModifier.RESIST, player.resists(enums.SkillType.ELECTRIC)
    assert player.resists(enums.SkillType.WIND) is enums.ResistanceModifier.WEAK, player.resists(enums.SkillType.WIND)

    assert player.get_passive_immunity(enums.SkillType.FIRE) is not None
    assert player.resists(enums.SkillType.FIRE) is enums.ResistanceModifier.REFLECT

    assert not player.is_fainted(), not player.is_fainted()
    dmg = player.take_damage(player, skill_cache['Ziodyne'])
    assert dmg.resistance is enums.ResistanceModifier.RESIST, dmg.resistance
    assert not dmg.did_weak
    if not dmg.miss:
        assert abs(dmg.damage_dealt-25) <= 4, dmg.damage_dealt
    else:
        assert dmg.damage_dealt == 0

    assert player.get_counter() is not None

    for a in range(50):
        dmg = player.take_damage(player, skill_cache['Ziodyne'])
    dmg.countered=True

    assert dmg.countered
    assert not dmg.did_weak, repr(dmg)
    if not dmg.miss:
        assert abs(dmg.damage_dealt-25) <= 4, repr(dmg)
    else:
        assert dmg.damage_dealt == 0
    assert dmg.resistance is enums.ResistanceModifier.RESIST

    for k, v in player.to_json().items():
        if pdata[k] != v:
            raise AssertionError((k, v))
    assert player.to_json() == pdata

    assert player.is_fainted(), (player.is_fainted(), player.hp, player.max_hp)
    assert player.hp == 0
    # print("Tests complete.")


if __name__ == '__main__':
    while True:
        run()