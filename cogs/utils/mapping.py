import json
import math
import os
import time

from PIL import Image


def fmt(r, g, b):
    return f"0x{f'{r:x}':0>2}{f'{g:x}':0>2}{f'{b:x}':0>2}"


class Attr(dict):
    def __getattr__(self, item):
        return self.__getitem__(item)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)

    def __delattr__(self, key):
        return self.__delitem__(key)


with open("maps/metadata.json") as f:
    metadata = json.load(f, object_hook=Attr)


def generate(file="map.png"):
    start = time.perf_counter()
    fname, fext = file.split(".", 1)
    biome_file = f"{fname}_BIOMES.{fext}"
    location_file = f"{fname}_LOCATIONS.{fext}"

    im = Image.open(biome_file).convert('RGB')
    lx, ly = im.size
    biomes = {}
    locations = {}
    for x in range(lx//10):
        for y in range(ly//10):
            xx = x*10
            yy = y*10
            rgb = im.getpixel((xx, yy))
            bs = fmt(*rgb)
            # print(r, g, b)
            if bs not in biomes:
                biomes[bs] = {'colour': rgb, 'coordinates': [], 'name': metadata.__biomes[bs].name}
            biomes[bs]['coordinates'].append([x, y])
    log.info("biome data loaded for {}, {:.1f}ms", file, (time.perf_counter()-start)*1000)

    im.close()
    im = Image.open(location_file).convert('RGB')
    assert im.size == (lx, ly)
    for x in range(lx):
        for y in range(ly):
            xx, yy = x*10, y*10
            rgb = im.getpixel((xx, yy))
            i = 0
            while i in locations:
                i += 1
            locations[i] = {'colour': rgb, 'coordinates': []}
            locations[i]['coordinates'].append([x, y])
    raw_map_data = {"biomes": biomes, 'locations': locations,
                    'max_x': lx//10, 'max_y': ly//10, 'name': metadata[file].name}
    log.info("location data loaded for {}, {:.1f}ms", file, (time.perf_counter()-start)*1000)
    im.close()
    return raw_map_data


# THIS IS FROM THE bresenham LIBRARY ON PIP
# https://pypi.org/project/bresenham/
# I DID NOT CODE THIS
def bresenham(coord1, coord2):
    """Yield integer coordinates on the line from (x0, y0) to (x1, y1).

    The result will contain both the start and the end point.
    """
    x0, y0 = coord1
    x1, y1 = coord2

    dx = x1 - x0
    dy = y1 - y0

    xsign = 1 if dx > 0 else -1
    ysign = 1 if dy > 0 else -1

    dx = abs(dx)
    dy = abs(dy)

    if dx > dy:
        xx, xy, yx, yy = xsign, 0, 0, ysign
    else:
        dx, dy = dy, dx
        xx, xy, yx, yy = 0, ysign, xsign, 0

    d = 2*dy - dx
    y = 0

    for x in range(dx + 1):
        yield x0 + x*xx + y*yx, y0 + x*xy + y*yy
        if d >= 0:
            y += 1
            d -= 2*dx
        d += 2*dy


class Biome:
    def __init__(self, map_manager, id, encounter_rate, name, coordinates, travel_cost_multiplier):
        self.id = id
        self.encounter_rate = encounter_rate
        self.name = name
        self.map_manager = map_manager
        self.travel_cost_multiplier = travel_cost_multiplier

        self.coordinates = []
        for coordinate in coordinates:
            self.coordinates.append(map_manager.coordinates[tuple(coordinate)])

    def __repr__(self):
        return f"<Biome id={self.id} name={self.name!r}>"


class Location:
    def __init__(self, map_manager, name, coordinates):
        self.name = name
        self.map_manager = map_manager

        self.coordinates = []
        for coordinate in coordinates:
            self.coordinates.append(map_manager.coordinates[tuple(coordinate)])

    def __repr__(self):
        return f"<Location name={self.name!r}>"


class Map:
    def __init__(self, location_data, biome_data, max_x, max_y):
        self.locations = []
        self.biomes = []
        self.coordinates = {}
        self.name = metadata

        self.max_x, self.max_y = max_x, max_y

        self.initiate_coordinates()
        # self.initiate_locations(location_data)
        self.initiate_biomes(biome_data)

    def __repr__(self):
        return f"<Map"

    @classmethod
    def from_dict(cls, config: dict):
        return cls(config.get("locations"), config.get("biomes"), config.get("max_x"), config.get("max_y"))

    @classmethod
    def from_image(cls, name='map.png'):
        return cls.from_dict(generate(name))

    def initiate_locations(self, location_data):
        for location in location_data:
            self.locations.append(
                Location(
                    self,
                    location.get("name"), location.get("coordinates")
                )
            )

    def initiate_biomes(self, biome_data):
        for name, biome in biome_data.items():
            self.biomes.append(
                Biome(
                    self,
                    biome.get("id"), biome.get("encounter_rate"),
                    biome.get("name"), biome.get("coordinates"),
                    biome.get("cost_multiplier")
                )
            )

    def initiate_coordinates(self):
        for x in range(0, self.max_x):
            for y in range(0, self.max_y):
                self.coordinates[x, y] = Coordinate(self, x, y)

    def get_coordinate(self, x, y):
        for coordinate in self.coordinates:
            if coordinate.x == x and coordinate.y == y:
                return coordinate

    def location_at(self, coordinate):
        for location in self.locations:
            if coordinate in location.coordinates:
                return location
        return None

    def biome_at(self, coordinate):
        for biome in self.biomes:
            if coordinate in biome.coordinates:
                return biome
        return None


class Coordinate:
    def __init__(self, map_manager, x, y):
        self.x, self.y = x, y
        self.map_manager = map_manager

    def __eq__(self, other):
        return other.x == self.x and other.y == self.y

    def __repr__(self):
        return f"<Coordinate ({self.x}, {self.y})>"

    def __iter__(self):
        yield self.x
        yield self.y

    @property
    def location(self):
        return self.map_manager.location_at(self)

    @property
    def biome(self):
        return self.map_manager.biome_at(self)

    def distance_to(self, other):
        return math.sqrt(math.pow(self.x - other.x, 2) - math.pow(self.y - other.y, 2))

    def coordinates_between(self, other):
        return [self.map_manager.get_coordinate(c[0], c[1]) for c in bresenham(self, other)] + [self, other]

    def biomes_between(self, other):
        return [c.biome for c in self.coordinates_between(other)]


class MapManager:
    def __init__(self):
        self.maps = {}
        for file in metadata['maps']:
            self.maps[file[:-4]] = Map.from_image(f'maps/{file}')
