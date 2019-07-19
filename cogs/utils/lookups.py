from discord import PartialEmoji


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
    "almighty": 0xc9cac9
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
    'almighty': PartialEmoji(animated=False, name="almighty", id=596540181088305153)
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
