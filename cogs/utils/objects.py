import json
import math
import random

from discord.enums import Enum


# Damage calc
# DMG = (5 * sqrt(Strength or Magic/Endurance*SkillPower) * random(0.95, 1.05)) / Raku


class Arcana(Enum):
    """Enumeration for various Arcana's."""
    FOOL = 0
    MAGICIAN = 1
    PRIESTESS = 2
    EMPRESS = 3
    EMPEROR = 4
    HIEROPHANT = 5
    LOVERS = 6
    CHARIOT = 7
    JUSTICE = 8
    HERMIT = 9
    FORTUNE = 10
    STRENGTH = 11
    HANGED = 12
    DEATH = 13
    TEMPERANCE = 14
    DEVIL = 15
    TOWER = 16
    STAR = 17
    MOON = 18
    SUN = 19
    JUDGEMENT = 20


class SkillType(Enum):
    """Enumeration for various skill types."""
    # -- physical -- #
    PHYSICAL      = 1   # tempest slash
    GUN           = 2   # triple down
    # -- magic -- #
    FIRE          = 3   # agi,    maragion
    ICE           = 4   # bufu,   mabufula
    ELECTRIC      = 5   # zio,    mazionga
    WIND          = 6   # garu,   magarula
    PSYCHOKINETIC = 7   # psi,    mapsio
    NUCLEAR       = 8   # frei,   mafreila
    BLESS         = 9   # kouha,  hama
    CURSE         = 10  # eiha,   mudo
    ALMIGHTY      = 11  # megido, black viper
    # -- support -- #
    HEALING       = 12  # dia,     patra
    AILMENT       = 13  # dormina, pulinpa
    SUPPORT       = 14  # tarunda, sukukaja
    # -- other -- #
    PASSIVE       = 15  # defense master, ice amp


class Severity(Enum):
    """Enumeration lookup for skill severity modifiers."""
    null = 0.0
    MINISCULE = 0.5
    LIGHT = 0.75
    MEDIUM = 1.0
    HEAVY = 1.5
    SEVERE = 3.0
    COLOSSAL = 5.0


class StatModifier(Enum):
    """Enumeration for *kaja and *nda."""
    TARU = 0  # attack
    RAKU = 1  # defense
    SUKU = 2  # accuracy/evasion


class ResistanceModifier(Enum):
    """Enumeration for the resistances."""
    IMMUNE = 0
    RESIST = 1
    NORMAL = 2
    WEAK = 3
    REFLECT = 4
    ABSORB = 5


class Ailment(Enum):
    """Enumeration for various ailments."""
    DESPAIR = 0
    BRAINWASH = 1
    DIZZY = 2
    FEAR = 3
    SLEEP = 4
    HUNGER = 5
    FORGET = 6
    CONFUSE = 7
    RAGE = 8
    BURN = 9
    FREEZE = 10
    SHOCK = 11


SKILL_BASE = 65
CRITICAL_BASE = 4


class JSONable:
    """To be subclassed.
    Allows objects to be JSON serializable, via :meth:`.to_json`."""
    __json__ = ()

    @staticmethod
    def _serialize(o):
        if not hasattr(o, '__json__'):
            return str(o)
        return {k: o.keygetter(k) for k in o.__json__ if not k.startswith('_')}

    def keygetter(self, key):
        """Allows you to map certain attributes to other names.

        Parameters
        ----------
        key: :class:`str`
            The key to get.

        Returns
        -------
        Any
            The attribute."""
        return getattr(self, key)

    def to_json(self):
        """Converts this object into a JSON-like object.

        Returns
        -------
        :class:`dict`
            The object converted for json storage."""
        ret = json.loads(json.dumps(self, default=self._serialize))
        return ret


class DamageResult:
    """Details about the result of a demon taking damage.

    Attributes
    ----------
    resistance: :class:`ResistanceModifier`
        The resistance modifier for the skill.
    damage_dealt: :class:`int`
        The total damage dealt.
    critical: :class:`bool`
        Whether the hit was a critical hit.
    miss: :class:`bool`
        Whether the skill missed.
    fainted: :class:`bool`
        Whether the skill used cause the target to faint.
    was_reflected: :class:`bool`
        Whether the skill was initially reflected.
    """
    __slots__ = ('resistance', 'damage_dealt', 'critical', 'miss', 'fainted', 'was_reflected')

    def __init__(self):
        self.resistance = ResistanceModifier.NORMAL
        self.damage_dealt = 0
        self.critical = False
        self.miss = False
        self.fainted = False
        self.was_reflected = False

    def __repr__(self):
        return (f"<DamageResult resistance={self.resistance!r} damage_dealt={self.damage_dealt} "
                f"critical={self.critical} miss={self.miss}>")


class Skill(JSONable):
    """A skill used for battling stuff.
    These aren't created manually, rather cached for later use.

    Attributes
    ----------
    name: :class:`str`
        The name of the skill.
    type: :class:`SkillType`
        The type of skill it can be.
    severity: :class:`Severity`
        The severity of the skill, ``severity.value`` will be
        a :class:`float`, for their total damage adjustment.
    cost: :class:`int`
        The total HP/SP cost for this skill.
    description: :class:`str`
        The skill's description, showing what it does.
    accuracy: :class:`int`
        The skills sub accuracy. 90 if it's not an instant kill
        type move."""
    __slots__ = ('name', 'type', 'severity', 'cost', 'accuracy', 'description')
    __json__ = (*__slots__[:-1], 'desc')

    def keygetter(self, key):
        """"""
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
        except (AttributeError, KeyError):
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

    @property
    def uses_sp(self):
        """A property which denotes whether :attr:`cost` uses HP or SP.

        Returns
        -------
        :class:`bool`
            ``True`` if it uses SP, otherwise it uses HP."""
        return self.type not in (SkillType.PHYSICAL, SkillType.GUN)

    @property
    def is_instant_kill(self):
        """A property which denotes whether this skill is an instant-kill
         type skill.
         
         Returns
         -------
         :class:`bool`
            This skill is an instant kill type skill."""    # automatically takes Ma* and *on into account
        return any(x.lower() in self.name.lower() for x in ('Hama', 'Mudo', 'Die for Me!', 'Samsara'))

    def damage_calc(self, attacker, target):
        """A helper function to calculate the damage ``demon`` would take.
        This takes into account endurance.
        Evasion checks are not determined here, but under :meth:`Player.take_damage`.
        Resistance checks are also checked in the above method.

        Parameters
        ----------
        attacker: :class:`Player`
            The attacking demon.
        target: :class:`Player`
            The target demon. Takes their endurance stat into account.

        Returns
        -------
        :class:`float`
            The total damage the demon would take."""
        if self.is_instant_kill:
            return target.hp

        base = 5 * math.sqrt((attacker.magic if self.uses_sp else attacker.strength) / target.endurance * SKILL_BASE
                             ) * random.uniform(0.95, 1.05)
        base *= attacker.affected_by(StatModifier.TARU)
        base /= target.affected_by(StatModifier.RAKU)
        return min(target.hp, base)


class Player(JSONable):
    """The Player object, designated for every account found.
    Mostly contains helpers for internal stuff.

    Attributes
    ----------
    name: :class:`str`
        The name of the demon for this player.
    owner: :class:`discord.User`
        The user this player is wrapped around.
    skills: List[:class:`Skill`]
        A list of skills this player has learnt and can use.
    exp: :class:`int`
        The total experience of this player.
    resistances: Mapping[:class:`SkillType`, :class:`ResistanceModifier`]
        A mapping of types and modifiers to denote the demon's
        resistances.
    arcana: :class:`Arcana`
        The arcana for this demon.
    specialty: :class:`SkillType`
        The type of skill this demon specializes in.
    stat_points: :class:`int`
        The remaining unspent skill points this player has.
    strength: :class:`int`
        Between 1-99, denotes the total physical strength of
        this player. Determines strength of physical attacks.
    magic: :class:`int`
        Between 1-99, denotes the total magical strength of
        this player. Determines strength of magic attacks, as
        well as the overall SP of this player.
    endurance: :class:`int`
        Between 1-99, denotes the total endurance of this
        player. Determines overall HP of this player.
    agility: :class:`int`
        Between 1-99, denotes the total agility of this
        player. Determines evasion chance and hit rate.
    luck: :class:`int`
        Between 1-99, denotes the total luck of this player.
        Determines how often status effects land, as well as
        your critical chance.
    """
    __json__ = ('owner', 'name', 'skills', 'exp', 'stats', 'resistances', 'arcana', 'specialty', 'stat_points')

    def keygetter(self, key):
        if key == 'owner':
            return self._owner_id
        elif key == 'skills':
            return list([z.name for z in self.skills])
        elif key == 'resistances':
            return list([z.value for z in self.resistances.values()])
        elif key == 'arcana':
            return self.arcana.value
        elif key == 'specialty':
            return self.specialty.name
        return getattr(self, key)

    def __init__(self, **kwargs):
        self._owner_id = kwargs.pop("owner")
        self.owner = None
        self.name = kwargs.pop("name")
        skills = kwargs.pop("skills")
        if all(isinstance(x, Skill) for x in skills):
            self.skills = skills
        else:
            self.skills = []
            self._skills = skills
        self.exp = kwargs.pop("exp")
        self.strength, self.magic, self.endurance, self.agility, self.luck = kwargs.pop("stats")
        self.resistances = dict(zip(SkillType, map(ResistanceModifier, kwargs.pop("resistances"))))
        self.arcana = Arcana(kwargs.pop("arcana"))
        self.specialty = SkillType[kwargs.pop("specialty").upper()]
        self.description = kwargs.pop("description", "<no description found, report to Xua>")
        self.stat_points = kwargs.pop("stat_points", 0)
        self._damage_taken = 0
        self._sp_used = 0
        self._stat_mod = '000'
        # [attack][defense][agility]
        self._until_clear = [0, 0, 0]  # turns until it gets cleared for each stat, max of 3 turns
        self._next_level = self.level+1

    def __repr__(self):
        return (f"Player(owner={self._owner_id}, "
                f"name='{self.name}', "
                f"skills={self.skills}, "
                f"exp={self.exp}, "
                f"stats=[{self.strength}, {self.magic}, {self.endurance}, {self.agility}, {self.luck}], "
                f"resistances=[{', '.join(str(k.value) for k in self.resistances.values())}], "
                f"description='{self.description}', "
                f"stat_points={self.stat_points})")

    @property
    def stats(self):
        return self.strength, self.magic, self.endurance, self.agility, self.luck

    @property
    def hp(self):
        """Returns the total HP this player has remaining.
        Same formula as :attr:`.max_hp`, but includes total
        damage taken.

        Returns
        -------
        :class:`int`
            The HP remaining."""
        return self.max_hp - self._damage_taken

    @hp.setter
    def hp(self, value):
        self._damage_taken = max(0, self._damage_taken + value)

    @property
    def max_hp(self):
        """Returns the maximum HP this player can have.
        ``ceil(50 + (4.7 * level))``

        Returns
        -------
        :class:`int`
            The maximum HP."""
        return math.ceil(50 + (4.7 * self.level))
        
    @property
    def sp(self):
        """Returns the total SP this player has remaining.
        SP is used for non special moves such as Curse or
        Healing types.
        
        Returns
        -------
        :class:`int`
            The SP remaining.
        """
        return self.max_sp - self._sp_used
        
    @sp.setter
    def sp(self, value):
        self._sp_used = max(0, self._sp_used + value)
        
    @property
    def max_sp(self):
        """Returns the total SP this player can have.
        ``ceil(30 + (3.6 * level))``
        
        Returns
        -------
        :class:`int`
            The maximum SP.
            """
        return math.ceil(30 + (3.6 * self.level))

    @property
    def level(self):
        """Returns the current level of the player.
        Calculated by EXP, as simple as ``level = ceil(exp**.334)``
        Minimum of 1 and maximum of 99.

        Returns
        -------
        :class:`int`
            The current player's level."""
        return min(99, max(math.ceil(self.exp**.334), 1))

    def level_up(self):
        """Levels up the player."""
        self._next_level += 1

    @property
    def can_level_up(self):
        """Returns whether or not you are able to level up.

        Returns
        -------
        :class:`bool`
            The player is ready to level up."""
        return self._next_level >= self.level

    def exp_to_next_level(self):
        """Returns the total experience until the next level.

        Returns
        -------
        :class:`int`
            The total experience this player has until he can level up."""
        return self._next_level**3 - self.exp

    def _populate_skills(self, bot):
        self.owner = bot.get_user(self._owner_id)
        for skill in self._skills:
            self.skills.append(bot.players.skill_cache[skill])

    def affected_by(self, modifier):
        """Returns a calculation modifier for specified key.

        Parameters
        ----------
        modifier: Union[:class:`StatModifier`, :class:`int`]
            The modifier to check against.

        Returns
        -------
        :class:`float`
            The total modifier."""
        modifier = getattr(modifier, 'value', modifier)

        return 1.0 if self._stat_mod[modifier] == '0' \
            else 1.05 if self._stat_mod[modifier] == '1' \
            else 0.95

    def resists(self, type):
        """Gets how resisted the type is.

        Parameters
        ----------
        type: :class:`SkillType`
            The skill type to check against.

        Returns
        -------
        :class:`ResistanceModifier`
            The modifier on how badly it resists."""
        try:
            return self.resistances[type]
        except KeyError:
            if not isinstance(type, SkillType):
                raise
            return ResistanceModifier.NORMAL

    def is_fainted(self):
        """Helper function to determine whether the player has fainted or not.
        Checks solely against HP.
        If this is ``True``, will reset all stat modifiers.

        Returns
        -------
        :class:`bool`
            The player has fainted."""
        if self.hp <= 0:
            self._stat_mod = '000'
            self._stat_up = '000'
            return True
        return False

    def take_damage(self, attacker, skill, *,  from_reflect=False):
        """A helper function for taking damage during battles.

        Parameters
        ----------
        attacker: :class:`Player`
            The attacking demon.
        skill: :class:`Skill`
            The skill the attacking demon used.
        from_reflect: :class:`bool`
            Whether the skill came from a reflection. Defaults ``False``.

        Returns
        -------
        :class:`DamageResult`
            The result of what happened when taking damage.
        """
        res = self.resists(skill.type)
        result = DamageResult()

        if res is ResistanceModifier.REFLECT:
            if not from_reflect:
                return attacker.take_damage(self, skill, from_reflect=True)
            res = ResistanceModifier.IMMUNE
            result.was_reflected = True

        result.resistance = res

        if res is ResistanceModifier.IMMUNE:
            return result

        if self.try_evade(attacker.agility/10, skill, attacker.affected_by(StatModifier.SUKU)):
            result.miss = True
            return result

        if skill.is_instant_kill:
            self.hp = self.max_hp
            result.damage_dealt = self.max_hp
            return result

        base = skill.damage_calc(attacker, self)

        if not skill.uses_sp:
            if attacker.try_crit(self.luck, self.affected_by(StatModifier.SUKU)):
                base *= 1.75

        if res is ResistanceModifier.WEAK:
            base *= 1.5
        elif res is ResistanceModifier.RESIST:
            base *= 0.5

        base = math.ceil(base)

        if res is not ResistanceModifier.ABSORB:
            self.hp = base
            result.damage_dealt = base
            result.fainted = self.is_fainted()
        else:
            self.hp = -base
            result.damage_dealt = -base

        return result

    def try_crit(self, luck_mod, suku_mod):
        """Returns a bool indicating whether ``self`` landed a successful critical hit.

        Parameters
        ----------
        luck_mod: :class:`int`
            The attacker's luck.
        suku_mod: :class:`float`
            The attacker's Suku* modifier.

        Returns
        -------
        :class:`bool`
            Whether a critical hit was landed."""
        base = CRITICAL_BASE
        base /= suku_mod
        base += ((self.luck/10) - (luck_mod/10))
        base *= self.affected_by(StatModifier.SUKU)
        return random.uniform(1, 100) <= base
        
    """ evasion / critical reference
In [58]: for my_suku in (0.95, 1.0, 1.05):
    ...:     for attacker_suku in (0.95, 1.0, 1.05):
    ...:         base = 90  # todo: determine properly
    ...:         base *= attacker_suku
    ...:         base /= my_suku
    ...:         print(f"Attacker: {attacker_suku:.2f}/{90*attacker_suku:.2f} | Me: {my_suku:.2f}/{90/my_suku:.2f} | {100-base:.2f} evasion chance")
    ...:
Attacker: mod \ base * mod | Me: mod \ base / mod | overall evasion chance
Attacker: 0.95/85.50 | Me: 0.95/94.74 | 10.00 evasion chance
Attacker: 1.00/90.00 | Me: 0.95/94.74 | 5.26 evasion chance
Attacker: 1.05/94.50 | Me: 0.95/94.74 | 0.53 evasion chance
Attacker: 0.95/85.50 | Me: 1.00/90.00 | 14.50 evasion chance
Attacker: 1.00/90.00 | Me: 1.00/90.00 | 10.00 evasion chance
Attacker: 1.05/94.50 | Me: 1.00/90.00 | 5.50 evasion chance
Attacker: 0.95/85.50 | Me: 1.05/85.71 | 18.57 evasion chance
Attacker: 1.00/90.00 | Me: 1.05/85.71 | 14.29 evasion chance
Attacker: 1.05/94.50 | Me: 1.05/85.71 | 10.00 evasion chance

In [59]: for my_suku in (0.95, 1.0, 1.05):
    ...:     for attacker_suku in (0.95, 1.0, 1.05):
    ...:         base = 4
    ...:         base /= attacker_suku
    ...:         base += ((my_luck/10) - (attacker_luck/10))
    ...:         base *= my_suku
    ...:         print(f"Attacker: {attacker_suku:.2f} | Me: {my_suku:.2f} | {base:.2f} chance to crit")
    ...:
    ...:
Attacker: mod  | Me: mod  | overall chance to crit
Attacker: 0.95 | Me: 0.95 | 4.00 chance to crit
Attacker: 1.00 | Me: 0.95 | 3.80 chance to crit
Attacker: 1.05 | Me: 0.95 | 3.62 chance to crit
Attacker: 0.95 | Me: 1.00 | 4.21 chance to crit
Attacker: 1.00 | Me: 1.00 | 4.00 chance to crit
Attacker: 1.05 | Me: 1.00 | 3.81 chance to crit
Attacker: 0.95 | Me: 1.05 | 4.42 chance to crit
Attacker: 1.00 | Me: 1.05 | 4.20 chance to crit
Attacker: 1.05 | Me: 1.05 | 4.00 chance to crit
    """

    def try_evade(self, modifier, skill, suku_mod):
        """Returns a bool indicating whether ``self`` successfully evaded the attack.
        Formula as follows:
            (non instant kill)
            ``(SkillAccuracy + (Modifier / 10) / 2) - (Agility / 10) / 2``

            (instant kill)
            ``SkillAccuracy - (Agility / 10) / 2``

            The base is then * by ``self``'s Suku* boost, finally / the attackers Suku* boost.
            If the attack is an instant kill, the base is also * by ``self``'s resistance.


        Parameters
        ----------
        modifier: :class:`int`
            The agility modifier of the attacking demon.
        skill: :class:`Skill`
            The skill to attempt to evade.
        suku_mod: :class:`float`
            The Suku* modifier of the attacking demon.

        Returns
        -------
        :class:`bool`
            Whether you successfully evaded the attack."""
        ag = self.agility / 10
        if not skill.is_instant_kill:
            base = (skill.accuracy + modifier/2) - ag/2
        else:
            base = skill.accuracy - ag/2
            if self.resists(skill.type) is ResistanceModifier.WEAK:
                base *= 1.1
            elif self.resists(skill.type) is ResistanceModifier.RESIST:
                base *= 0.9

        base *= self.affected_by(StatModifier.SUKU)
        base /= suku_mod

        return random.uniform(1, 100) < base

    async def save(self, bot):
        """Flushes the player to the database.
        Usually not called manually.
        Requires passing of the ``bot`` parameter to access the database.
        
        Parameters
        ----------
        bot: :class:`bot.bot.AdventureTwo`
            The bot object to save
        """
        data = self.to_json()
        await bot.db.adventure2.accounts.replace_one({"owner": self._owner_id}, data, upsert=True)
