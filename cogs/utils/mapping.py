import json

import math


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


class MapManager:
    def __init__(self, location_data, biome_data, max_x, max_y):
        self.locations = []
        self.biomes = []
        self.coordinates = {}

        self.max_x, self.max_y = max_x, max_y

        self.initiate_coordinates()
        # self.initiate_locations(location_data)
        self.initiate_biomes(biome_data)

    @classmethod
    def from_dict(cls, config: dict):
        return cls(config.get("locations"), config.get("biomes"), config.get("max_x"), config.get("max_y"))

    @classmethod
    def from_file(cls, filename: str):
        with open(filename, "r") as f:
            config = json.load(f)
        return cls.from_dict(config)

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
