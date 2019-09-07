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
    'ailment': 0x5f128a
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
    "almighty": "almighty",
    "passive": "passive",
    "ailment": "ailment",
    "support": "support",
    "healing": "healing"
}

TYPE_TO_EMOJI = {
    'physical': PartialEmoji(animated=False, name="phys", id=596539297814020108),
    'gun': PartialEmoji(animated=False, name="gun", id=596539459151986688),
    'fire': PartialEmoji(animated=False, name="fire", id=596539579390230528),
    'ice': PartialEmoji(animated=False, name="ice", id=596539715952443392),
    'electric': PartialEmoji(animated=False, name="elec", id=596539642988462090),
    'wind': PartialEmoji(animated=False, name="wind", id=596539771787018241),
    'nuclear': PartialEmoji(animated=False, name="nuke", id=596539998791008279),
    'psychokinetic': PartialEmoji(animated=False, name="psy", id=596539924828782603),
    'bless': PartialEmoji(animated=False, name="bless", id=596540126251712538),
    'curse': PartialEmoji(animated=False, name="curse", id=596540064096321548),
    'almighty': PartialEmoji(animated=False, name="almighty", id=596540181088305153),
    'support': PartialEmoji(animated=False, name='support', id=604534784437387265),
    'passive': PartialEmoji(animated=False, name='passive', id=604535071537496064),
    'ailment': PartialEmoji(animated=False, name='ailment', id=604534890641227776),
    'healing': PartialEmoji(animated=False, name='healing', id=604534971012481055)
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
