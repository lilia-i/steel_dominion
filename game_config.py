PLAYER = "player"
ENEMY = "enemy"

MAP_COLUMNS = 10
MAP_ROWS = 8

UNIT_TYPES = {
    "Infantry": {"cost": {"money": 4, "steel": 1, "technology": 0}, "attack": 1, "range": 1, "hp": 4, "movement": 3, "mark": "I"},
    "Tank": {"cost": {"money": 6, "steel": 5, "technology": 1}, "attack": 3, "range": 1, "hp": 6, "movement": 5, "mark": "T"},
    "Artillery": {"cost": {"money": 5, "steel": 3, "technology": 2}, "attack": 2, "range": 2, "hp": 3, "movement": 2, "mark": "A"},
}

INFANTRY_TYPE = "Infantry"
TRANSPORT_STATS = {"attack": 1, "range": 1, "movement": 4, "mark": "S"}

TERRAIN_COLORS = {
    "Plain": "#d9dfc9",
    "Forest": "#a9bda0",
    "Hill": "#c8bd91",
    "Water": "#b6d0d0",
}

TERRAIN_MOVEMENT_COST = {
    "Plain": 1,
    "Forest": 2,
    "Hill": 2,
    "Water": 1,
}

DEFENSIVE_TERRAINS = ("Hill", "Forest")
TERRAIN_DEFENSE_BONUS = 1
MIN_DAMAGE = 1
DAMAGE_RANDOM_BONUS = (0, 1)

STARTING_RESOURCES = {"money": 16, "steel": 8, "technology": 3}
CITY_PRODUCTION_PER_LEVEL = {"money": 2, "steel": 2, "technology": 1}
CITY_BASE_HP = 15
CITY_HP_PER_LEVEL = 3
CITY_MAX_HP = 30
CITY_MAX_LEVEL = 6
CITY_HEAL_PER_TURN = 2


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)

COUNTRY_SETUP = (
    {"id": "britain", "name": "Britain", "faction": PLAYER,
     "resources": {"money": 16, "steel": 8, "technology": 3}},
    {"id": "france", "name": "France", "faction": PLAYER,
     "resources": {"money": 12, "steel": 6, "technology": 2}},
    {"id": "germany", "name": "Germany", "faction": ENEMY,
     "resources": {"money": 16, "steel": 8, "technology": 3}},
    {"id": "poland", "name": "Poland", "faction": ENEMY,
     "resources": {"money": 10, "steel": 5, "technology": 1}},
    {"id": "soviet", "name": "Soviet Union", "faction": ENEMY,
     "resources": {"money": 14, "steel": 7, "technology": 2}},
)

TERRAIN_LAYOUT = {
    "Water": ((0, 0), (0, 1), (0, 7), (1, 7), (8, 0), (9, 0),
              (9, 1), (9, 7), (8, 7), (0, 6), (9, 6)),
    "Forest": ((2, 2), (4, 1), (4, 5), (7, 1), (8, 3), (2, 6), (5, 6)),
    "Hill": ((1, 2), (3, 1), (4, 3), (5, 2), (6, 5), (7, 6), (3, 6)),
}

RIVER_EDGES = (
    ((3, 0), (2, 1)),
    ((2, 1), (2, 2)),
    ((2, 2), (2, 3)),
    ((2, 3), (3, 4)),
    ((3, 4), (3, 5)),
    ((3, 5), (3, 6)),
    ((3, 6), (3, 7)),
)

CITY_SETUP = (
    {"position": (1, 4), "name": "London", "owner": "britain",
     "city_level": 2, "industry_level": 1, "research_level": 1},
    {"position": (3, 3), "name": "Paris", "owner": "france",
     "city_level": 1, "industry_level": 2, "research_level": 1},
    {"position": (6, 3), "name": "Berlin", "owner": "germany",
     "city_level": 2, "industry_level": 2, "research_level": 1},
    {"position": (7, 4), "name": "Warsaw", "owner": "poland",
     "city_level": 1, "industry_level": 1, "research_level": 2},
    {"position": (8, 5), "name": "Moscow", "owner": "soviet",
     "city_level": 2, "industry_level": 1, "research_level": 2},
)

STARTING_UNITS = (
    ("Tank", "britain", (1, 4)),
    ("Infantry", "britain", (2, 4)),
    ("Artillery", "france", (3, 3)),
    ("Infantry", "germany", (6, 3)),
    ("Tank", "poland", (6, 4)),
    ("Infantry", "poland", (7, 4)),
    ("Artillery", "soviet", (8, 5)),
)

TERRITORY_LAYOUT = (
    "LLLLPPPGGM",
    "LLLLPPGGMM",
    "LLLPPGGGMM",
    "LLPPPGGWWM",
    "LLPPGGGWWM",
    "LPPGGGWWMM",
    "LPPGGGWWMM",
    "LPPGGGWWMM",
)