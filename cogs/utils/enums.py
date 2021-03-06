from discord.enums import Enum


class Arcana(Enum):
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
    # -- physical -- #
    PHYSICAL = 1   # tempest slash
    GUN = 2   # triple down
    # -- magic -- #
    FIRE = 3   # agi,    maragion
    ICE = 4   # bufu,   mabufula
    ELECTRIC = 5   # zio,    mazionga
    WIND = 6   # garu,   magarula
    PSYCHOKINETIC = 7   # psi,    mapsio
    NUCLEAR = 8   # frei,   mafreila
    BLESS = 9   # kouha,  makouga
    CURSE = 10  # eiha,   maeiga
    ALMIGHTY = 11  # megido, black viper
    # -- instant death -- #
    DARK = 16  # mudo, alice is only specialty
    LIGHT = 17  # hama, daisoujou is only specialty
    # -- support -- #
    HEALING = 12  # dia,     patra
    AILMENT = 13  # dormina, pulinpa
    SUPPORT = 14  # tarunda, sukukaja
    # -- other -- #
    PASSIVE = 15  # defense master, ice amp


class Severity(Enum):
    MINISCULE = 0.5
    LIGHT = 0.75
    MEDIUM = 1.0
    HEAVY = 1.5
    SEVERE = 3.0
    COLOSSAL = 5.0
    EXTREME = 7.5


class StatModifier(Enum):
    TARU = 0  # attack
    RAKU = 1  # defense
    SUKU = 2  # accuracy/evasion


class ResistanceModifier(Enum):
    IMMUNE = 0   # n
    RESIST = 1   # s
    NORMAL = 2   # -
    WEAK = 3     # w
    REFLECT = 4  # r
    ABSORB = 5   # d


class AilmentType(Enum):
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


class Weather(Enum):
    SUNNY = 0
    CLOUDY = 1
    RAIN = 2
    SNOW = 3
    FOGGY = 4


class SevereWeather(Enum):
    HEAT_WAVE = 0
    SEVERE_WIND = 1
    THUNDER_STORM = 2
    SNOW_STORM = 3


class Season(Enum):
    SPRING = 0
    SUMMER = 1
    AUTUMN = 2
    WINTER = 3


class ItemType(Enum):
    HEALING = 0
    TRASH = 1
    MATERIAL = 2
    SKILL_CARD = 3
    EQUIPABLE = 4
    UTILITY = 5
    KEY = 6
