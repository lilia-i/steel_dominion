import json

from app_paths import application_path


PLAYER = "player"
ENEMY = "enemy"
NEUTRAL = "neutral"

UNIT_TYPES = {
    "Infantry": {
        "cost": {"money": 80, "steel": 5, "technology": 0},
        "attack": 20, 
        "range": 1, 
        "hp": 80, 
        "movement": 18, 
    },
    "Tank": {
        "cost": {"money": 160, "steel": 35, "technology": 5},
        "attack": 27, 
        "range": 1, 
        "hp": 150, 
        "movement": 15, 
    },
    "Artillery": {
        "cost": {"money": 120, "steel": 15, "technology": 10},
        "attack": 29, 
        "range": 2, 
        "hp": 90, 
        "movement": 12, 
    },
}

TRANSPORT_STATS = {
    "attack": 10, 
    "range": 1,   
    "movement": 12,   
}

TERRAIN_COLORS = {
    "Plain": "#d9dfc9",
    "Forest": "#a9bda0",
    "Hill": "#c8bd91",
    "Desert": "#d7bd82",
    "Water": "#b6d0d0",
}

TERRAIN_MOVEMENT_COST = {
    "Plain": 3,   
    "Forest": 6,   
    "Hill": 7,   
    "Desert": 5,
    "Water": 3, 
}

DEFENSIVE_TERRAINS = ("Hill", "Forest")
TERRAIN_DEFENSE_BONUS = 0  
MIN_DAMAGE = 1 
DAMAGE_RANDOM_BONUS = (-0.15, 0.15)  

CITY_PRODUCTION_PER_LEVEL = {
    "money": 20,  
    "steel": 8,
    "technology": 3,  
}
CITY_BASE_HP = 120
CITY_HP_PER_LEVEL = 24
CITY_MAX_LEVEL = 6
CITY_HEAL_PER_TURN = 12  
DEFAULT_RESOURCES = {"money": 16, "steel": 8, "technology": 3}


def _merge_config(target, overrides):
    if not isinstance(overrides, dict):
        return
    for key, value in overrides.items():
        if key not in target:
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, dict):
            _merge_config(current, value)
        elif isinstance(current, tuple) and isinstance(value, list):
            if all(isinstance(item, str) for item in value):
                target[key] = tuple(value)
        elif (isinstance(current, (int, float)) and
              not isinstance(current, bool) and
              isinstance(value, (int, float)) and
              not isinstance(value, bool)):
            target[key] = value
        elif isinstance(value, type(current)):
            target[key] = value


def _load_external_config():
    try:
        with open(application_path("config.json"), "r") as config_file:
            overrides = json.load(config_file)
    except (IOError, OSError, ValueError, TypeError):
        return

    sections = {
        "unit_types": UNIT_TYPES,
        "transport_stats": TRANSPORT_STATS,
        "terrain_colors": TERRAIN_COLORS,
        "terrain_movement_cost": TERRAIN_MOVEMENT_COST,
        "city_production_per_level": CITY_PRODUCTION_PER_LEVEL,
        "default_resources": DEFAULT_RESOURCES,
    }
    for key, target in sections.items():
        _merge_config(target, overrides.get(key, {}))

    global DEFENSIVE_TERRAINS, TERRAIN_DEFENSE_BONUS, MIN_DAMAGE
    global DAMAGE_RANDOM_BONUS, CITY_BASE_HP, CITY_HP_PER_LEVEL
    global CITY_MAX_LEVEL, CITY_MAX_HP, CITY_HEAL_PER_TURN

    value = overrides.get("defensive_terrains")
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        DEFENSIVE_TERRAINS = tuple(value)
    value = overrides.get("damage_random_bonus")
    if (isinstance(value, list) and len(value) == 2 and
            all(isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in value)):
        DAMAGE_RANDOM_BONUS = tuple(value)
    for key, name in (
            ("terrain_defense_bonus", "TERRAIN_DEFENSE_BONUS"),
            ("min_damage", "MIN_DAMAGE"),
            ("city_base_hp", "CITY_BASE_HP"),
            ("city_hp_per_level", "CITY_HP_PER_LEVEL"),
            ("city_max_level", "CITY_MAX_LEVEL"),
            ("city_heal_per_turn", "CITY_HEAL_PER_TURN")):
        value = overrides.get(key)
        if (isinstance(value, (int, float)) and not isinstance(value, bool)):
            globals()[name] = value
    CITY_MAX_HP = CITY_BASE_HP + (CITY_MAX_LEVEL - 1) * CITY_HP_PER_LEVEL


_load_external_config()


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)
