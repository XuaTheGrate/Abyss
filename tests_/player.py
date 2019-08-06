from cogs.utils.player import Player
from cogs.utils.objects import Skill
from cogs.utils import enums


pdata = {
    "owner": 1234,
    "name": "Arthur",
    "skills": ["Divine Sword", "Insta-Heal", "Break", "Spell Master", "Diarahan", "Repel Fire"],  # dekaja, heat riser, vanity
    # wont actually have Repel Fire
    "exp": 970299,
    "stats": [99, 99, 99, 99, 99],
    "resistances": [2, 2, 2, 2, 2, 2, 2, 2, 0, 0],
    "arcana": 20,
    "specialty": "LIGHT",
    "description": "A test description. Shouldn't matter that badly.",
    "stat_points": 0,
    "skill_leaf": None,
    "ap": 0,
    "unsetskills": ["Mediarahan"],
    "finished_leaves": []
}

# this is my unique demon, for my use only
# during an online battle, if you can defeat me
# you will be awarded the skill card for Divine Sword
# Divine Sword deals 7x (colossal is 5x) Almighty damage to one enemy

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
    "Divine Sword": Skill(
        name="Divine Sword",
        type="almighty",
        severity="colossal",
        cost=466,
        desc="Deals extreme almighty damage to one enemy. A very rare skill."
    ),
    "Insta-Heal": Skill(
        name="Insta-Heal",
        type="passive",
        severity="light",
        cost=0,
        desc="Will heal status ailments after one turn."
    ),
    "Break": Skill(
        name="Break",
        type="support",
        severity="light",
        cost=0,
        desc="Fully heals SP and doubles Endurance. Cannot move for two turns."
    ),
    "Spell Master": Skill(
        name="Spell Master",
        type="passive",
        severity="light",
        cost=0,
        desc="Halves cost of all Magic skills."
    ),
    "Diarahan": Skill(
        name="Diarahan",
        type="healing",
        severity="colossal",
        cost=24,
        desc="Fully heals one ally."
    ),
    "Mediarahan": Skill(
        name="Mediarahan",
        type="healing",
        severity="colossal",
        cost=40,
        desc="Fully heals all allies."
    ),
    "High Counter": Skill(
        name="High Counter",
        type="passive",
        severity="light",
        cost=0,
        desc="High chance to counter physical attacks."
    ),
    "Repel Fire": Skill(
        name="Repel Fire",
        type="passive",
        severity="light",
        cost=0,
        desc="Repels fire attacks and provides immunity to the Burn ailment."
    )
}


class DummyAttrs:
    skill_cache = skill_cache


class DummyBot:
    players = DummyAttrs()

    @staticmethod
    def get_user(id):
        return id - 1


import builtins


class Thing:
    def __getattr__(self, item):
        return lambda *__, **_: None


builtins.log = Thing()

bot = DummyBot()


def run():
    player = Player(**pdata)
    player._populate_skills(bot)
    assert player.level == 99, player.level
    assert player.max_hp == 585, player.max_hp
    assert player.exp_to_next_level() == 29701, player.exp_to_next_level()
    assert player.arcana is enums.Arcana.JUDGEMENT, repr(player.arcana)
    assert player.owner == player._owner_id - 1, (player.owner, player._owner_id)
    # in reality, the better assertion would be `isinstance(owner, User)`
    # but we just need to confirm that it changed at all, thanks to the DummyBot

    assert skill_cache['Diarahan'] in player.skills, player.skills
    assert skill_cache['Mediarahan'] in player.unset_skills, player.unset_skills

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

    assert player.get_counter() is None
    player.skills.append(skill_cache['High Counter'])
    assert player.get_counter() is not None

    for a in range(50):
        dmg = player.take_damage(player, skill_cache['Divine Sword'])

    assert not dmg.did_weak, repr(dmg)
    if not dmg.miss:
        assert abs(dmg.damage_dealt-25) <= 4, repr(dmg)
    else:
        assert dmg.damage_dealt == 0
    assert dmg.resistance is enums.ResistanceModifier.NORMAL

    player._shields['Electric'] = 3
    assert player._shields['Electric'] == 3
    assert player.resists(enums.SkillType.ELECTRIC) is enums.ResistanceModifier.IMMUNE
    player.pre_turn()
    player.pre_turn()
    assert player._shields['Electric'] == 1
    player.pre_turn()
    assert 'Electric' not in player._shields
    assert player.resists(enums.SkillType.ELECTRIC) is not enums.ResistanceModifier.IMMUNE

    player.refresh_stat_modifier(enums.StatModifier.RAKU, True)
    assert player._until_clear[1] == 3
    assert player.affected_by(enums.StatModifier.RAKU) == 1.05
    player.pre_turn()
    assert player._until_clear[1] == 2
    player.refresh_stat_modifier(enums.StatModifier.RAKU, False)
    assert player.affected_by(enums.StatModifier.RAKU) == 1.0
    player.pre_turn()
    player.refresh_stat_modifier(enums.StatModifier.RAKU, False)
    assert player.affected_by(enums.StatModifier.RAKU) == 0.95
    for a in range(4):
        player.pre_turn()
    assert player._stat_mod == [0, 0, 0]
    assert player._until_clear == [0, 0, 0]

    player.refresh_stat_modifier(enums.StatModifier.TARU, True)
    player.refresh_stat_modifier(enums.StatModifier.RAKU, True)

    for k, v in player.to_json().items():
        if pdata[k] != v:
            raise AssertionError((k, v))
    assert player.to_json() == pdata

    assert player.is_fainted(), (player.is_fainted(), player.hp, player.max_hp)
    assert player.hp == 0
    # print("Tests complete.")
