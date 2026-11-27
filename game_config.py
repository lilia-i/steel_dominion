import json
import math

from app_paths import application_path


PLAYER = "player"
ENEMY = "enemy"
NEUTRAL = "neutral"

def _positive_integer(value):
    return type(value) is int and value > 0


def _load_skill_definitions(data, label):
    if not isinstance(data, list):
        raise ValueError("{} skills must be a list.".format(label))
    for skill in data:
        if (not isinstance(skill, dict) or
                any(not isinstance(skill.get(key), str) or not skill[key]
                    for key in ("id", "icon"))):
            raise ValueError("{} has an invalid skill definition.".format(label))
    return [dict(skill) for skill in data]


def _load_unit_types(data):
    if not isinstance(data, dict) or not data:
        raise ValueError("config.json must define at least one unit type.")
    resources = ("money", "steel", "technology")
    stats = ("attack", "range", "hp", "movement")
    unit_types = {}
    for name, details in data.items():
        if (not isinstance(name, str) or not name.strip() or len(name) > 30 or
                not isinstance(details, dict)):
            raise ValueError("config.json contains an invalid unit type.")
        unit_id = details.get("id", name)
        if (not isinstance(unit_id, str) or not unit_id.strip() or
                len(unit_id) > 30 or unit_id in unit_types):
            raise ValueError("Unit {} has an invalid or duplicate ID.".format(name))
        display_name = details.get("name_en", name)
        if (not isinstance(display_name, str) or not display_name.strip() or
                len(display_name) > 30):
            raise ValueError("Unit {} has an invalid English display name.".format(name))
        localized_name = details.get("name_zh")
        if (localized_name is not None and
            (not isinstance(localized_name, str) or
             not localized_name.strip() or len(localized_name) > 30)):
            raise ValueError("Unit {} has an invalid Chinese display name.".format(name))
        symbol = details.get("symbol")
        if not isinstance(symbol, str) or len(symbol) != 1 or symbol.isspace():
            raise ValueError("Unit {} must define a one-character symbol.".format(name))
        category = details.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Unit {} must define a category.".format(name))
        cost = details.get("cost")
        if (not isinstance(cost, dict) or
                any(type(cost.get(resource)) is not int or cost[resource] < 0
                    for resource in resources) or
                any(not _positive_integer(details.get(stat)) for stat in stats)):
            raise ValueError("Unit {} has invalid cost or combat stats.".format(name))
        skills = _load_skill_definitions(details.get("skills", []), name)
        unit_types[unit_id] = {
            "cost": dict((resource, cost[resource]) for resource in resources),
            "category": category,
            "symbol": symbol,
            "name_en": display_name,
        }
        unit_types[unit_id].update(dict((stat, details[stat]) for stat in stats))
        unit_types[unit_id]["skills"] = skills
        if localized_name is not None:
            unit_types[unit_id]["name_zh"] = localized_name
    return unit_types


def _load_config(config_path=None):
    try:
        path = config_path or application_path("config.json")
        with open(path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (IOError, OSError, ValueError, TypeError) as error:
        raise RuntimeError("Unable to load required config.json: {}".format(error))
    if not isinstance(config, dict):
        raise ValueError("config.json must contain a JSON object.")

    terrain_colors = config.get("terrain_colors")
    terrain_costs = config.get("terrain_movement_cost")
    if (not isinstance(terrain_colors, dict) or not terrain_colors or
            any(not isinstance(name, str) or not isinstance(color, str)
                for name, color in terrain_colors.items()) or
            not isinstance(terrain_costs, dict) or
            set(terrain_colors) != set(terrain_costs) or
            any(not _positive_integer(cost) for cost in terrain_costs.values())):
        raise ValueError("config.json has invalid terrain colors or movement costs.")

    resources = ("money", "steel", "technology")
    for key in ("city_production_per_level", "default_resources"):
        values = config.get(key)
        if (not isinstance(values, dict) or
                any(type(values.get(resource)) is not int or values[resource] < 0
                    for resource in resources)):
            raise ValueError("config.json has invalid {} values.".format(key))

    legacy_capacity = config.get("ai_units_per_city_level", 0.7)
    for key in ("player_ai_units_per_city_level",
                "enemy_ai_units_per_city_level", "unit_maintenance_rate"):
        value = config.get(key, legacy_capacity if key != "unit_maintenance_rate"
                           else 0.05)
        if (not isinstance(value, (int, float)) or isinstance(value, bool) or
                not math.isfinite(value) or value < 0):
            raise ValueError("config.json has an invalid {} value.".format(key))
        config[key] = value

    transport_stats = config.get("transport_stats")
    if (not isinstance(transport_stats, dict) or
            any(not _positive_integer(transport_stats.get(key))
                for key in ("attack", "range", "movement")) or
            not isinstance(transport_stats.get("symbol"), str) or
            len(transport_stats["symbol"]) != 1 or
            transport_stats["symbol"].isspace() or
            not isinstance(transport_stats.get("category"), str) or
            not transport_stats["category"].strip()):
        raise ValueError("config.json has invalid transport stats.")
    transport_skills = _load_skill_definitions(
        transport_stats.get("skills", []), "transport")

    defensive_terrains = config.get("defensive_terrains")
    if (not isinstance(defensive_terrains, list) or
            any(terrain not in terrain_colors for terrain in defensive_terrains)):
        raise ValueError("config.json has invalid defensive terrains.")
    damage_bonus = config.get("damage_random_bonus")
    if (not isinstance(damage_bonus, list) or len(damage_bonus) != 2 or
            any(not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in damage_bonus)):
        raise ValueError("config.json has invalid damage random bonus.")
    critical_hit_chance = config.get("critical_hit_chance", 0.05)
    if (not isinstance(critical_hit_chance, (int, float)) or
            isinstance(critical_hit_chance, bool) or
            not math.isfinite(critical_hit_chance) or
            not 0.0 <= critical_hit_chance <= 1.0):
        raise ValueError("config.json has an invalid critical_hit_chance value.")
    critical_hit_multiplier = config.get("critical_hit_multiplier", 2.0)
    if (not isinstance(critical_hit_multiplier, (int, float)) or
            isinstance(critical_hit_multiplier, bool) or
            not math.isfinite(critical_hit_multiplier) or
            critical_hit_multiplier <= 0):
        raise ValueError(
            "config.json has an invalid critical_hit_multiplier value.")

    integer_settings = {
        "min_damage": True,
        "city_base_hp": True,
        "city_hp_per_level": True,
        "city_max_level": True,
        "city_heal_per_turn": False,
    }
    for key, positive in integer_settings.items():
        value = config.get(key)
        if (type(value) is not int or
                (value <= 0 if positive else value < 0)):
            raise ValueError("config.json has an invalid {} value.".format(key))
    for key, default in (
            ("forced_march_multiplier", 3),
            ("forced_march_unattacked_turns", 3)):
        value = config.get(key, default)
        if type(value) is not int or value <= 0:
            raise ValueError("config.json has an invalid {} value.".format(key))
        config[key] = value
    level_multipliers = config.get("unit_level_multipliers", {
        "cost": [1.0, 1.8, 2.5],
        "hp": [1.0, 1.8, 2.7],
        "attack": [1.0, 1.15, 1.4],
    })
    if not isinstance(level_multipliers, dict):
        raise ValueError("config.json has invalid unit level multipliers.")
    normalized_multipliers = {}
    for stat in ("cost", "hp", "attack"):
        values = level_multipliers.get(stat)
        if (not isinstance(values, list) or len(values) != 3 or
                any(not isinstance(value, (int, float)) or
                    isinstance(value, bool) or not math.isfinite(value) or
                    value <= 0 for value in values)):
            raise ValueError(
                "config.json has invalid unit level {} multipliers.".format(stat))
        normalized_multipliers[stat] = tuple(values)
    config["unit_level_multipliers"] = normalized_multipliers
    income_multiplier = config.get("non_participant_income_multiplier", 0.5)
    if (not isinstance(income_multiplier, (int, float)) or
            isinstance(income_multiplier, bool) or
            not math.isfinite(income_multiplier) or income_multiplier < 0):
        raise ValueError(
            "config.json has an invalid non_participant_income_multiplier value.")
    config["non_participant_income_multiplier"] = income_multiplier
    animation_duration = config.get("movement_animation_duration", 0.4)
    if (not isinstance(animation_duration, (int, float)) or
            isinstance(animation_duration, bool) or
            not math.isfinite(animation_duration) or animation_duration <= 0):
        raise ValueError("config.json has an invalid movement_animation_duration value.")
    config["movement_animation_duration"] = animation_duration
    terrain_defense_bonus = config.get("terrain_defense_bonus")
    if (not isinstance(terrain_defense_bonus, (int, float)) or
            isinstance(terrain_defense_bonus, bool)):
        raise ValueError("config.json has an invalid terrain_defense_bonus value.")

    config["unit_types"] = _load_unit_types(config.get("unit_types"))
    config["transport_stats"] = dict((key, transport_stats[key])
                                     for key in ("attack", "range", "movement",
                                                 "category", "symbol"))
    config["transport_stats"]["skills"] = transport_skills
    config["terrain_colors"] = dict(terrain_colors)
    config["terrain_movement_cost"] = dict(terrain_costs)
    config["defensive_terrains"] = tuple(defensive_terrains)
    config["damage_random_bonus"] = tuple(damage_bonus)
    return config


_CONFIG = _load_config()
UNIT_TYPES = _CONFIG["unit_types"]
TRANSPORT_STATS = _CONFIG["transport_stats"]
TERRAIN_COLORS = _CONFIG["terrain_colors"]
TERRAIN_MOVEMENT_COST = _CONFIG["terrain_movement_cost"]
DEFENSIVE_TERRAINS = _CONFIG["defensive_terrains"]
TERRAIN_DEFENSE_BONUS = _CONFIG["terrain_defense_bonus"]
MIN_DAMAGE = _CONFIG["min_damage"]
DAMAGE_RANDOM_BONUS = _CONFIG["damage_random_bonus"]
CRITICAL_HIT_CHANCE = _CONFIG["critical_hit_chance"]
CRITICAL_HIT_MULTIPLIER = _CONFIG["critical_hit_multiplier"]
CITY_PRODUCTION_PER_LEVEL = _CONFIG["city_production_per_level"]
CITY_BASE_HP = _CONFIG["city_base_hp"]
CITY_HP_PER_LEVEL = _CONFIG["city_hp_per_level"]
CITY_MAX_LEVEL = _CONFIG["city_max_level"]
CITY_MAX_HP = CITY_BASE_HP + (CITY_MAX_LEVEL - 1) * CITY_HP_PER_LEVEL
CITY_HEAL_PER_TURN = _CONFIG["city_heal_per_turn"]
DEFAULT_RESOURCES = _CONFIG["default_resources"]
PLAYER_AI_UNITS_PER_CITY_LEVEL = _CONFIG["player_ai_units_per_city_level"]
ENEMY_AI_UNITS_PER_CITY_LEVEL = _CONFIG["enemy_ai_units_per_city_level"]
UNIT_MAINTENANCE_RATE = _CONFIG["unit_maintenance_rate"]
MOVEMENT_ANIMATION_DURATION = _CONFIG["movement_animation_duration"]
FORCED_MARCH_MULTIPLIER = _CONFIG["forced_march_multiplier"]
FORCED_MARCH_UNATTACKED_TURNS = _CONFIG["forced_march_unattacked_turns"]
NON_PARTICIPANT_INCOME_MULTIPLIER = _CONFIG[
    "non_participant_income_multiplier"]
UNIT_LEVEL_MULTIPLIERS = _CONFIG["unit_level_multipliers"]


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)


def unit_level_stats(kind, level):
    if type(level) is not int or level not in (1, 2, 3):
        raise ValueError("Unit level must be 1, 2, or 3.")
    details = UNIT_TYPES[kind]

    def scaled(value, multiplier):
        return int(math.floor(value * multiplier + 0.5))

    index = level - 1
    return {
        "cost": {
            resource: scaled(amount, UNIT_LEVEL_MULTIPLIERS["cost"][index])
            for resource, amount in details["cost"].items()
        },
        "hp": scaled(details["hp"], UNIT_LEVEL_MULTIPLIERS["hp"][index]),
        "attack": scaled(details["attack"], UNIT_LEVEL_MULTIPLIERS["attack"][index]),
        "movement": details["movement"],
    }
