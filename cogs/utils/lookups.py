from discord import PartialEmoji

from .enums import *

TYPE_TO_COLOUR = {
    "physical": 0xe79e2d,
    "gun": 0xf3a807,
    "fire": 0xf64d0b,
    "ice": 0x26adf6,
    "electric": 0xf6f826,
    "wind": 0x38e41e,
    "nuclear": 0x39edf5,
    "psychokinetic": 0xe485e2,
    "bless": 0xf5f6b0,
    "curse": 0xf41134,
    "almighty": 0xc9cac9,
    'support': 0x326af5,
    'passive': 0xf5d34b,
    'healing': 0x04dc8c,
    'ailment': 0x5f128a,
    'dark': 0xf41134,
    'light': 0xf5f6b0
}

TYPE_SHORTEN = {
    "physical": "phys",
    "gun": "gun",
    "fire": "fire",
    "ice": "ice",
    "wind": "wind",
    "electric": "elec",
    "nuclear": "nuke",
    "psychokinetic": "psy",
    "bless": "bless",
    "curse": "curse",
    'light': 'light',
    'dark': 'dark',
    "almighty": "almighty",
    "passive": "passive",
    "ailment": "ailment",
    "support": "support",
    "healing": "healing"
}

TYPE_TO_EMOJI = {
    'physical': PartialEmoji(name='phys', id=674200220195749909),
    'gun': PartialEmoji(name='gun', id=674200221462298647),
    'fire': PartialEmoji(name='fire', id=674200222842486784),
    'ice': PartialEmoji(name='ice', id=674200224826261534),
    'electric': PartialEmoji(name='elec', id=674200225543356440),
    'wind': PartialEmoji(name='wind', id=674200226516566027),
    'nuclear': PartialEmoji(name='nuke', id=674200228181573632),
    'psychokinetic': PartialEmoji(name='psy', id=674200229653905408),
    'bless': PartialEmoji(name='bless', id=674200238700888064),
    'curse': PartialEmoji(name='curse', id=674200239455862786),
    'almighty': PartialEmoji(name='almighty', id=674200232288059413),
    'support': PartialEmoji(name='support', id=674200234410246160),
    'passive': PartialEmoji(name='passive', id=674200235400233021),
    'ailment': PartialEmoji(name='ailment', id=674200236637290496),
    'healing': PartialEmoji(name='healing', id=674200237870678016),
    'light': PartialEmoji(name='bless', id=674200238700888064),
    'dark': PartialEmoji(name='curse', id=674200239455862786),
}

ROMAN_NUMERAL = [
    '0',
    'I',
    'II',
    'III',
    'IV',
    'V',
    'VI',
    'VII',
    'VIII',
    'IX',
    'X',
    'XI',
    'XII',
    'XIII',
    'XIV',
    'XV',
    'XVI',
    'XVII',
    'XVIII',
    'XIX',
    'XX'
]

STAT_MOD = [
    'Attack',
    'Defense',
    'Accuracy/Evasion'
]

WEATHER_TO_TYPE = {
    'SUNNY': 'FIRE',
    'RAIN': 'ELECTRIC',
    'SNOW': 'ICE',

    'HEAT_WAVE': 'FIRE',
    'SNOW_STORM': 'ICE',
    'SEVERE_WIND': 'WIND',
    'THUNDER_STORM': 'ELEC'
}

WIND_SPEED_SEASON = {
    Season.SPRING: 3,
    Season.SUMMER: -3,
    Season.AUTUMN: 6,
    Season.WINTER: -6
}

WIND_SPEED_WEATHER = {
    Weather.CLOUDY: 4,
    Weather.SUNNY: -4,
    Weather.FOGGY: -7,
    Weather.SNOW: 6,
    Weather.RAIN: 6,

    SevereWeather.HEAT_WAVE: -17,
    SevereWeather.SEVERE_WIND: 70,
    SevereWeather.SNOW_STORM: 53,
    SevereWeather.THUNDER_STORM: 42
}

STAT_VARIATION = {
    'Chariot': [30.8, 15.4, 23.1, 15.4, 15.4],
    'Death': [23.1, 30.8, 15.4, 15.4, 15.4],
    'Devil': [15.4, 30.8, 15.4, 23.1, 15.4],
    'Emperor': [25.0, 25.0, 16.7, 16.7, 16.7],
    'Empress': [15.4, 30.8, 15.4, 23.1, 15.4],
    'Fool': [20.0, 20.0, 20.0, 20.0, 20.0],
    'Fortune': [15.4, 30.8, 15.4, 15.4, 23.1],
    'Hermit': [15.4, 23.1, 15.4, 30.8, 15.4],
    'Hierophant': [23.1, 23.1, 23.1, 15.4, 15.4],
    'Judgement': [15.4, 30.8, 23.1, 15.4, 15.4],
    'Justice': [15.4, 23.1, 15.4, 30.8, 15.4],
    'Lovers': [15.4, 23.1, 15.4, 15.4, 30.8],
    'Magician': [15.4, 30.8, 15.4, 23.1, 15.4],
    'Moon': [25.0, 25.0, 16.7, 16.7, 16.7],
    'Priestess': [15.4, 30.8, 15.4, 15.4, 23.1],
    'Star': [28.6, 21.4, 14.3, 14.3, 21.4],
    'Strength': [30.8, 15.4, 23.1, 15.4, 15.4],
    'Sun': [14.3, 21.4, 14.3, 28.6, 21.4],
    'Temperance': [23.1, 23.1, 23.1, 15.4, 15.4],
    'Tower': [30.8, 15.4, 23.1, 15.4, 15.4]
}

ITEM_TYPE_STRINGIFY = {
    ItemType.EQUIPABLE: "Equipable",
    ItemType.HEALING: "Healing",
    ItemType.TRASH: "Trash",
    ItemType.MATERIAL: "Materials",
    ItemType.SKILL_CARD: "Skill Cards",
    ItemType.UTILITY: 'Utility',
    ItemType.KEY: 'Key Items'
}
