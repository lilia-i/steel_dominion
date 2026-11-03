import json
import re

from game_config import ENEMY, NEUTRAL, PLAYER, TERRAIN_COLORS, UNIT_TYPES, city_hp_for_level


MAP_FORMAT_VERSION = 7
MIN_MAP_SIZE = 4
MAX_MAP_SIZE = 200
TERRAINS = tuple(TERRAIN_COLORS.keys())
RESOURCE_KEYS = ("money", "steel", "technology")
DEFAULT_RESOURCES = {"money": 16, "steel": 8, "technology": 3}
DEFAULT_CITY_HP = city_hp_for_level(1)


def _validate_size(columns, rows):
    for label, value in (("columns", columns), ("rows", rows)):
        if type(value) is not int or not MIN_MAP_SIZE <= value <= MAX_MAP_SIZE:
            raise ValueError("Map {} must be between {} and {}.".format(
                label, MIN_MAP_SIZE, MAX_MAP_SIZE))


def new_map_data(columns=10, rows=8):
    _validate_size(columns, rows)
    return {
        "version": MAP_FORMAT_VERSION,
        "columns": columns,
        "rows": rows,
        "terrain": [["Plain" for _ in range(columns)] for _ in range(rows)],
        "territories": [[None for _ in range(columns)] for _ in range(rows)],
        "rivers": [],
        "countries": [
            {"id": "allied", "name": "Allied State", "faction": PLAYER,
             "resources": dict(DEFAULT_RESOURCES)},
            {"id": "axis", "name": "Axis State", "faction": ENEMY,
             "resources": dict(DEFAULT_RESOURCES)},
        ],
        "cities": [],
        "units": [],
    }


def _upgrade_v1_map(data):
    countries = [
        {"id": "allied", "name": "Allied State", "faction": PLAYER,
         "resources": dict(DEFAULT_RESOURCES)},
        {"id": "axis", "name": "Axis State", "faction": ENEMY,
         "resources": dict(DEFAULT_RESOURCES)},
    ]
    cities = []
    units = []
    owner_ids = {PLAYER: "allied", ENEMY: "axis"}
    for city in data.get("cities", []):
        upgraded = dict(city)
        upgraded["owner"] = owner_ids.get(city.get("owner"), city.get("owner"))
        city_level = city.get("city_level", 1)
        if type(city_level) is not int or city_level < 1:
            city_level = 1
        upgraded["health"] = city_hp_for_level(city_level)
        upgraded["max_health"] = city_hp_for_level(city_level)
        cities.append(upgraded)
        units.append({
            "col": city.get("col"), "row": city.get("row"),
            "type": "Infantry", "owner": upgraded["owner"],
        })
    upgraded_map = dict(data)
    upgraded_map.update({
        "version": 2,
        "countries": countries,
        "cities": cities,
        "units": units,
    })
    return upgraded_map


def _upgrade_v2_map(data):
    upgraded_map = dict(data)
    cities = []
    for city in data.get("cities", []):
        upgraded = dict(city)
        city_level = upgraded.get("city_level", 1)
        if type(city_level) is not int or city_level < 1:
            city_level = 1
        max_health = city_hp_for_level(city_level)
        health = upgraded.get("health", max_health)
        if type(health) is not int or health < 0:
            health = max_health
        upgraded["max_health"] = max_health
        upgraded["health"] = min(health, max_health)
        cities.append(upgraded)
    upgraded_map["version"] = 3
    upgraded_map["cities"] = cities
    return upgraded_map


def _upgrade_v3_map(data):
    upgraded_map = dict(data)
    city_positions = [(city["col"], city["row"]) for city in data.get("cities", [])]
    assignments = assign_city_territories(
        data["columns"], data["rows"], city_positions)
    upgraded_map["territories"] = [
        [list(assignments[(col, row)])
         if (col, row) in assignments and data["terrain"][row][col] != "Water" else None
         for col in range(data["columns"])]
        for row in range(data["rows"])
    ]
    upgraded_map["version"] = 4
    return upgraded_map


def _upgrade_v4_map(data):
    upgraded_map = dict(data)
    upgraded_map["rivers"] = []
    upgraded_map["version"] = 5
    return upgraded_map


def _upgrade_v5_map(data):
    upgraded_map = dict(data)
    upgraded_map["version"] = 6
    return upgraded_map


def _upgrade_v6_map(data):
    upgraded_map = dict(data)
    upgraded_map["version"] = MAP_FORMAT_VERSION
    return upgraded_map


def normalize_map_data(data):
    if not isinstance(data, dict):
        raise ValueError("Map data must be a JSON object.")
    if data.get("version") == 1:
        data = _upgrade_v1_map(data)
    if data.get("version") == 2:
        data = _upgrade_v2_map(data)
    if data.get("version") == 3:
        data = _upgrade_v3_map(data)
    if data.get("version") == 4:
        data = _upgrade_v4_map(data)
    if data.get("version") == 5:
        data = _upgrade_v5_map(data)
    if data.get("version") == 6:
        data = _upgrade_v6_map(data)
    if data.get("version") != MAP_FORMAT_VERSION:
        raise ValueError("Unsupported map format version.")

    columns = data.get("columns")
    rows = data.get("rows")
    _validate_size(columns, rows)

    terrain = data.get("terrain")
    if not isinstance(terrain, list) or len(terrain) != rows:
        raise ValueError("Terrain must contain one row per map row.")
    normalized_terrain = []
    for row in terrain:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError("Every terrain row must match the map width.")
        if any(cell not in TERRAINS for cell in row):
            raise ValueError("Terrain contains an unknown terrain type.")
        normalized_terrain.append(list(row))

    countries = data.get("countries")
    if not isinstance(countries, list):
        raise ValueError("Countries must be a list.")
    normalized_countries = []
    country_ids = set()
    country_names = set()
    for country in countries:
        if not isinstance(country, dict):
            raise ValueError("Each country must be an object.")
        country_id = country.get("id")
        if not isinstance(country_id, str) or not re.match(r"^[A-Za-z0-9_-]{1,32}$", country_id):
            raise ValueError("Country IDs must use 1 to 32 letters, numbers, '_' or '-'.")
        name = country.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 30:
            raise ValueError("Country names must contain 1 to 30 characters.")
        if country_id in country_ids or name.strip().casefold() in country_names:
            raise ValueError("Country IDs and names must be unique.")
        faction = country.get("faction")
        if faction not in (PLAYER, ENEMY, NEUTRAL):
            raise ValueError("Each country must belong to player, enemy, or neutral faction.")
        resources = country.get("resources")
        if not isinstance(resources, dict):
            raise ValueError("Each country needs its own resource balances.")
        color = country.get("color")
        if color is not None and (not isinstance(color, str) or
                                  not re.match(r"^#[0-9A-Fa-f]{6}$", color)):
            raise ValueError("Country colors must be six-digit hexadecimal values.")
        normalized_resources = {}
        for resource in RESOURCE_KEYS:
            amount = resources.get(resource)
            if type(amount) is not int or not 0 <= amount <= 999999:
                raise ValueError("Country resources must be integers from 0 to 999999.")
            normalized_resources[resource] = amount
        country_ids.add(country_id)
        country_names.add(name.strip().casefold())
        normalized_countries.append({
            "id": country_id,
            "name": name.strip(),
            "faction": faction,
            "color": color.lower() if color else None,
            "resources": normalized_resources,
        })

    cities = data.get("cities")
    if not isinstance(cities, list):
        raise ValueError("Cities must be a list.")
    normalized_cities = []
    occupied = set()
    for city in cities:
        if not isinstance(city, dict):
            raise ValueError("Each city must be an object.")
        col = city.get("col")
        row = city.get("row")
        if (type(col) is not int or type(row) is not int or
                not 0 <= col < columns or not 0 <= row < rows):
            raise ValueError("A city is outside the map.")
        position = (col, row)
        if position in occupied:
            raise ValueError("Only one city can occupy each hex.")
        if normalized_terrain[row][col] == "Water":
            raise ValueError("Cities cannot be placed on water.")
        name = city.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 30:
            raise ValueError("City names must contain 1 to 30 characters.")
        owner = city.get("owner")
        if owner not in country_ids:
            raise ValueError("Each city must belong to an existing country.")
        city_level = city.get("city_level", 1)
        if type(city_level) is not int or not 1 <= city_level <= 99:
            raise ValueError("City level must be from 1 to 99.")
        expected_max_health = city_hp_for_level(city_level)
        max_health = city.get("max_health", expected_max_health)
        health = city.get("health", max_health)
        if (type(max_health) is not int or max_health != expected_max_health or
                type(health) is not int or not 0 <= health <= max_health):
            raise ValueError("City HP maximum must match its level and configured maximum.")
        levels = {}
        for level_key in ("city_level", "industry_level", "research_level"):
            level = city_level if level_key == "city_level" else city.get(level_key, 1)
            if type(level) is not int or not 1 <= level <= 99:
                raise ValueError("City production levels must be from 1 to 99.")
            levels[level_key] = level
        occupied.add(position)
        normalized_city = {
            "col": col,
            "row": row,
            "name": name.strip(),
            "owner": owner,
            "health": health,
            "max_health": max_health,
        }
        normalized_city.update(levels)
        normalized_cities.append(normalized_city)

    territories = data.get("territories")
    if not isinstance(territories, list) or len(territories) != rows:
        raise ValueError("Territories must contain one row per map row.")
    normalized_territories = []
    city_positions = set(occupied)
    for row_index, territory_row in enumerate(territories):
        if not isinstance(territory_row, list) or len(territory_row) != columns:
            raise ValueError("Every territory row must match the map width.")
        normalized_row = []
        for col, city_position in enumerate(territory_row):
            if normalized_terrain[row_index][col] == "Water":
                if city_position is not None:
                    raise ValueError("Sea hexes cannot belong to a city territory.")
                normalized_row.append(None)
                continue
            if city_position is None:
                normalized_row.append(None)
                continue
            if (not isinstance(city_position, list) or len(city_position) != 2 or
                    type(city_position[0]) is not int or type(city_position[1]) is not int or
                    tuple(city_position) not in city_positions):
                raise ValueError("Territory cells must reference an existing city.")
            normalized_row.append(list(city_position))
        normalized_territories.append(normalized_row)

    rivers = data.get("rivers", [])
    if not isinstance(rivers, list):
        raise ValueError("Rivers must be a list of hex edges.")
    normalized_rivers = []
    river_edges = set()
    for edge in rivers:
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("Each river must connect two adjacent hexes.")
        endpoints = []
        for point in edge:
            if (not isinstance(point, list) or len(point) != 2 or
                    type(point[0]) is not int or type(point[1]) is not int or
                    not 0 <= point[0] < columns or not 0 <= point[1] < rows):
                raise ValueError("River endpoints must be inside the map.")
            if normalized_terrain[point[1]][point[0]] == "Water":
                raise ValueError("Rivers can only be drawn between land hexes.")
            endpoints.append(tuple(point))
        first, second = sorted(endpoints)
        edge_key = frozenset((first, second))
        if first == second or second not in hex_neighbors(columns, rows, first):
            raise ValueError("Each river must connect two adjacent hexes.")
        if edge_key in river_edges:
            raise ValueError("A river edge can only be drawn once.")
        river_edges.add(edge_key)
        normalized_rivers.append([list(first), list(second)])

    units = data.get("units")
    if not isinstance(units, list):
        raise ValueError("Starting units must be a list.")
    normalized_units = []
    unit_positions = set()
    for unit in units:
        if not isinstance(unit, dict):
            raise ValueError("Each starting unit must be an object.")
        col = unit.get("col")
        row = unit.get("row")
        if (type(col) is not int or type(row) is not int or
                not 0 <= col < columns or not 0 <= row < rows):
            raise ValueError("A starting unit is outside the map.")
        position = (col, row)
        if position in unit_positions:
            raise ValueError("Only one starting unit can occupy each hex.")
        if normalized_terrain[row][col] == "Water":
            raise ValueError("Starting units cannot be placed on water.")
        kind = unit.get("type")
        if kind not in UNIT_TYPES:
            raise ValueError("Starting unit type is unknown.")
        owner = unit.get("owner")
        if owner not in country_ids:
            raise ValueError("Each starting unit must belong to an existing country.")
        unit_positions.add(position)
        normalized_units.append({"col": col, "row": row, "type": kind, "owner": owner})

    return {
        "version": MAP_FORMAT_VERSION,
        "columns": columns,
        "rows": rows,
        "terrain": normalized_terrain,
        "territories": normalized_territories,
        "rivers": normalized_rivers,
        "countries": normalized_countries,
        "cities": normalized_cities,
        "units": normalized_units,
    }


def validate_playable_map(data):
    normalized = normalize_map_data(data)
    countries = {country["id"]: country for country in normalized["countries"]}
    city_owners = {city["owner"] for city in normalized["cities"]}
    for country in normalized["countries"]:
        if country["id"] not in city_owners:
            raise ValueError("Every country needs at least one city.")
    factions = {country["faction"] for country in normalized["countries"]}
    if PLAYER not in factions or ENEMY not in factions:
        raise ValueError("A playable map needs countries in both player and enemy factions.")
    unit_factions = {countries[unit["owner"]]["faction"] for unit in normalized["units"]}
    if PLAYER not in unit_factions or ENEMY not in unit_factions:
        raise ValueError("A playable map needs at least one starting unit for each faction.")
    assigned_positions = set()
    for row, territory_row in enumerate(normalized["territories"]):
        for col, city_position in enumerate(territory_row):
            if normalized["terrain"][row][col] == "Water":
                if city_position is not None:
                    raise ValueError("Sea hexes cannot belong to a city territory.")
                continue
            if city_position is None:
                raise ValueError("Every land hex must be manually assigned to a city.")
            owner_position = tuple(city_position)
            assigned_positions.add(owner_position)
    if len(assigned_positions) != len(normalized["cities"]):
        raise ValueError("Every city must own at least one hex.")
    return normalized


def assign_city_territories(columns, rows, city_positions):
    assigned = {}
    queue = []
    for position in city_positions:
        if position not in assigned:
            assigned[position] = position
            queue.append(position)

    index = 0
    while index < len(queue):
        col, row = queue[index]
        index += 1
        if row % 2:
            directions = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1))
        else:
            directions = ((1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
        for delta_col, delta_row in directions:
            neighbor = (col + delta_col, row + delta_row)
            if (0 <= neighbor[0] < columns and 0 <= neighbor[1] < rows and
                    neighbor not in assigned):
                assigned[neighbor] = assigned[(col, row)]
                queue.append(neighbor)
    return assigned


def hex_neighbors(columns, rows, position):
    col, row = position
    if row % 2:
        directions = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1))
    else:
        directions = ((1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
    return [(col + delta_col, row + delta_row)
            for delta_col, delta_row in directions
            if 0 <= col + delta_col < columns and 0 <= row + delta_row < rows]


def load_map_file(path):
    with open(path, "r", encoding="utf-8") as source:
        return normalize_map_data(json.load(source))


def save_map_file(path, data):
    normalized = normalize_map_data(data)
    with open(path, "w", encoding="utf-8") as destination:
        json.dump(normalized, destination, ensure_ascii=False, indent=2)
        destination.write("\n")