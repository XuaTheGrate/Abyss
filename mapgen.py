import json

from PIL import Image


BIOME_COLOURS = {
    (254, 216, 0): 'Desert',
    (0, 255, 0): 'Plains',
    (0, 127, 14): 'Forest',
    (127, 106, 0): 'Beach',
    (0, 148, 255): 'Ocean',
    (0, 255, 255): 'River',
    (254, 255, 255): 'Snow',
    (119, 119, 119): 'Mountain'
}

BIOMES = {
    'Plains': {
        'coordinates': [],
        'id': 0,
        'name': 'Plains',
        'encounter_rate': 1.0,
        'travel_cost_multiplier': 1.0
    },
    'Desert': {
        'coordinates': [],
        'id': 1,
        'name': 'Desert',
        'encounter_rate': 0.77,
        'travel_cost_multiplier': 0.94
    },
    'Forest': {
        'coordinates': [],
        'id': 2,
        'name': 'Forest',
        'encounter_rate': 1.25,
        'travel_cost_multiplier': 1.13
    },
    'Ocean': {
        'coordinates': [],
        'id': 3,
        'name': 'Ocean',
        'encounter_rate': 1.5,
        'travel_cost_multiplier': 2.65
    },
    'Beach': {
        'coordinates': [],
        'id': 4,
        'name': 'Beach',
        'encounter_rate': 1.05,
        'travel_cost_multiplier': 1.0
    },
    'River': {
        'coordinates': [],
        'id': 5,
        'name': 'River',
        'encounter_rate': 1.1,
        'travel_cost_multiplier': 1.7
    },
    'Snow': {
        'coordinates': [],
        'id': 6,
        'name': 'Snow',
        'encounter_rate': 1.34,
        'travel_cost_multiplier': 1.49
    },
    'Mountain': {
        'coordinates': [],
        'id': 7,
        'name': 'Mountain',
        'encounter_rate': 1.95,
        'travel_cost_multiplier': 3.0
    }
}


def fmt(r, g, b):
    return int(f"0x{f'{r:x}':0>2}{f'{g:x}':0>2}{f'{b:x}':0>2}", 16)


im = Image.open("map.png").convert('RGB')


def closest(rgb):
    min_colours = {}
    for key, name in BIOME_COLOURS.items():
        r_c, g_c, b_c = key
        rd = (r_c - rgb[0]) ** 2
        gd = (g_c - rgb[1]) ** 2
        bd = (b_c - rgb[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]


for x in range(100):
    for y in range(100):
        xx = x*10
        yy = y*10
        rgb = im.getpixel((xx, yy))
        # print(r, g, b)
        try:
            name = BIOME_COLOURS[rgb]
        except KeyError:
            # nearest = sorted(BIOME_COLOURS.keys(), key=lambda i: abs(num-i))
            name = closest(rgb)
        BIOMES[name]['coordinates'].append([x, y])


d = {"biomes": BIOMES, 'max_x': 100, 'max_y': 100}

with open("output.json", "w") as f:
    json.dump(BIOMES, f)
im.close()

input('run test?')

new = Image.new('RGB', (100, 100))

rev = {v: k for k, v in BIOME_COLOURS.items()}

for bi in BIOMES:
    for c in BIOMES[bi]['coordinates']:
        col = rev[bi]
        new.putpixel(tuple(c), col)

new.save("test.png")
