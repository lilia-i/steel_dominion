PLAYER = "player"
ENEMY = "enemy"
NEUTRAL = "neutral"

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

CITY_PRODUCTION_PER_LEVEL = {"money": 2, "steel": 2, "technology": 1}
CITY_BASE_HP = 150
CITY_HP_PER_LEVEL = 30
CITY_MAX_HP = 300
CITY_MAX_LEVEL = 6
CITY_HEAL_PER_TURN = 12


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)
