import random
import heapq

from game_config import (
    CITY_HEAL_PER_TURN,
    CITY_PRODUCTION_PER_LEVEL,
    CITY_SETUP,
    COUNTRY_SETUP,
    DAMAGE_RANDOM_BONUS,
    DEFENSIVE_TERRAINS,
    ENEMY,
    INFANTRY_TYPE,
    MAP_COLUMNS,
    MAP_ROWS,
    MIN_DAMAGE,
    PLAYER,
    RIVER_EDGES,
    STARTING_UNITS,
    TERRAIN_DEFENSE_BONUS,
    TERRAIN_LAYOUT,
    TERRAIN_MOVEMENT_COST,
    TERRITORY_LAYOUT,
    TRANSPORT_STATS,
    UNIT_TYPES,
    city_hp_for_level,
)
from map_data import validate_playable_map

class Unit(object):
    next_id = 1

    def __init__(self, kind, owner, position, faction=None):
        info = UNIT_TYPES[kind]
        self.id = Unit.next_id
        Unit.next_id += 1
        self.kind = kind
        self.owner = owner
        self.faction = faction if faction is not None else owner
        self.position = position
        self.hp = info["hp"]
        self.max_hp = info["hp"]
        self.original_attack = info["attack"]
        self.original_range = info["range"]
        self.original_movement = info["movement"]
        self.attack = self.original_attack
        self.range = self.original_range
        self.movement = self.original_movement
        self.movement_left = self.movement
        self.attacks_per_turn = 1
        self.attacks_left = self.attacks_per_turn
        self.embarked = False

    @property
    def attacked(self):
        return self.attacks_left <= 0

    @property
    def effective_attack(self):
        health_ratio = max(0.0, min(1.0, float(self.hp) / self.max_hp))
        if health_ratio >= 0.5:
            return float(self.attack)
        return self.attack * (0.5 + health_ratio)

    @attacked.setter
    def attacked(self, value):
        self.attacks_left = 0 if value else self.attacks_per_turn

    def embark(self):
        if self.embarked:
            return
        self.embarked = True
        self.attack = TRANSPORT_STATS["attack"]
        self.range = TRANSPORT_STATS["range"]
        self.movement = TRANSPORT_STATS["movement"]

    def disembark(self):
        if not self.embarked:
            return
        self.embarked = False
        self.attack = self.original_attack
        self.range = self.original_range
        self.movement = self.original_movement


class GameModel(object):
    columns = MAP_COLUMNS
    rows = MAP_ROWS

    def __init__(self, map_data=None):
        self.turn = 1
        self.phase = PLAYER
        self.winner = None
        self.columns = MAP_COLUMNS
        self.rows = MAP_ROWS
        self.tiles = {}
        self.river_edges = {frozenset(edge) for edge in RIVER_EDGES}
        self.countries = {}
        self.cities = {}
        self.territory_city = {}
        self.units = []
        if map_data is None:
            self._create_world()
        else:
            self._create_custom_world(map_data)

    def _create_custom_world(self, map_data):
        map_data = validate_playable_map(map_data)
        self.columns = map_data["columns"]
        self.rows = map_data["rows"]
        self.river_edges = set()
        for country_data in map_data["countries"]:
            self.countries[country_data["id"]] = {
                "id": country_data["id"],
                "name": country_data["name"],
                "faction": country_data["faction"],
                "resources": dict(country_data["resources"]),
            }
        for row, terrain_row in enumerate(map_data["terrain"]):
            for col, terrain in enumerate(terrain_row):
                self.tiles[(col, row)] = terrain

        for city_data in map_data["cities"]:
            position = (city_data["col"], city_data["row"])
            city = {
                "position": position,
                "name": city_data["name"],
                "owner": city_data["owner"],
                "city_level": 1,
                "industry_level": 1,
                "research_level": 1,
                "health": city_data["health"],
                "max_health": city_data["max_health"],
            }
            for level_key in ("city_level", "industry_level", "research_level"):
                city[level_key] = city_data[level_key]
            self.cities[position] = city
        self.territory_city = {
            (col, row): tuple(city_position)
            for row, territory_row in enumerate(map_data["territories"])
            for col, city_position in enumerate(territory_row)
            if city_position is not None
        }
        for unit_data in map_data["units"]:
            country = self.countries[unit_data["owner"]]
            self.units.append(Unit(unit_data["type"], unit_data["owner"],
                                   (unit_data["col"], unit_data["row"]), country["faction"]))

    def _create_world(self):
        for country_data in COUNTRY_SETUP:
            self.countries[country_data["id"]] = {
                "id": country_data["id"],
                "name": country_data["name"],
                "faction": country_data["faction"],
                "resources": dict(country_data["resources"]),
            }
        terrain_positions = {
            terrain: set(positions) for terrain, positions in TERRAIN_LAYOUT.items()
        }
        for row in range(self.rows):
            for col in range(self.columns):
                position = (col, row)
                terrain = next((name for name, positions in terrain_positions.items()
                                if position in positions), "Plain")
                self.tiles[position] = terrain

        for city in CITY_SETUP:
            configured_city = dict(city)
            configured_city["max_health"] = city_hp_for_level(city["city_level"])
            configured_city["health"] = configured_city["max_health"]
            self.cities[city["position"]] = configured_city
        city_symbols = {
            "L": (1, 4), "P": (3, 3), "G": (6, 3), "W": (7, 4), "M": (8, 5),
        }
        self.territory_city = {
            (col, row): city_symbols[symbol]
            for row, territory_row in enumerate(TERRITORY_LAYOUT)
            for col, symbol in enumerate(territory_row)
            if self.tiles[(col, row)] != "Water"
        }
        self.units.extend(Unit(kind, owner, position, self.countries[owner]["faction"])
                          for kind, owner, position in STARTING_UNITS)

    @property
    def resources(self):
        country_id = self.first_country_for(PLAYER)
        return self.countries[country_id]["resources"]

    def first_country_for(self, faction):
        return next(country_id for country_id, country in self.countries.items()
                    if country["faction"] == faction)

    def faction_for(self, country_id):
        return self.countries[country_id]["faction"]

    def country_name(self, country_id):
        return self.countries[country_id]["name"]

    def city_for_hex(self, position):
        city_position = self.territory_city.get(position)
        return self.cities.get(city_position)

    def unit_at(self, position):
        for unit in self.units:
            if unit.position == position:
                return unit
        return None

    def neighbors(self, position):
        col, row = position
        if row % 2:
            directions = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1))
        else:
            directions = ((1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
        result = []
        for delta_col, delta_row in directions:
            neighbor = (col + delta_col, row + delta_row)
            if neighbor in self.tiles:
                result.append(neighbor)
        return result

    @staticmethod
    def distance(first, second):
        first_row = first[1]
        second_row = second[1]
        first_axial_col = first[0] - (first_row - (first_row & 1)) // 2
        second_axial_col = second[0] - (second_row - (second_row & 1)) // 2
        delta_col = first_axial_col - second_axial_col
        delta_row = first_row - second_row
        return (abs(delta_col) + abs(delta_row) + abs(delta_col + delta_row)) // 2

    def crosses_river(self, first, second):
        return frozenset((first, second)) in self.river_edges

    @staticmethod
    def terrain_movement_cost(unit, terrain):
        if unit.kind == INFANTRY_TYPE and not unit.embarked and terrain != "Water":
            return TERRAIN_MOVEMENT_COST["Plain"]
        return TERRAIN_MOVEMENT_COST[terrain]

    def movement_paths(self, unit):
        if unit not in self.units or unit.attacked or unit.movement_left <= 0:
            return {}

        budget = unit.movement_left
        best_cost = {unit.position: 0}
        previous = {}
        queue = [(0, unit.position)]
        while queue:
            spent, position = heapq.heappop(queue)
            if spent != best_cost[position] or spent >= budget:
                continue
            for neighbor in self.neighbors(position):
                occupant = self.unit_at(neighbor)
                if occupant and occupant is not unit:
                    continue
                city = self.cities.get(neighbor)
                if (city and city["health"] > 0 and
                        self.faction_for(city["owner"]) != unit.faction):
                    continue

                current_is_water = self.tiles[position] == "Water"
                next_is_water = self.tiles[neighbor] == "Water"
                if current_is_water != next_is_water or self.crosses_river(position, neighbor):
                    next_spent = budget
                else:
                    next_spent = spent + self.terrain_movement_cost(unit, self.tiles[neighbor])
                if next_spent > budget or next_spent >= best_cost.get(neighbor, budget + 1):
                    continue

                best_cost[neighbor] = next_spent
                previous[neighbor] = position
                heapq.heappush(queue, (next_spent, neighbor))

        paths = {}
        for destination in best_cost:
            if destination == unit.position:
                continue
            path = []
            position = destination
            while position != unit.position:
                path.append(position)
                position = previous[position]
            paths[destination] = list(reversed(path))
        return paths

    def owned_cities(self, owner):
        if owner in self.countries:
            return sum(1 for city in self.cities.values() if city["owner"] == owner)
        return sum(1 for city in self.cities.values()
                   if self.faction_for(city["owner"]) == owner)

    @staticmethod
    def city_production(city):
        return {
            resource: city[level_key] * rate
            for resource, level_key, rate in (
                ("money", "city_level", CITY_PRODUCTION_PER_LEVEL["money"]),
                ("steel", "industry_level", CITY_PRODUCTION_PER_LEVEL["steel"]),
                ("technology", "research_level", CITY_PRODUCTION_PER_LEVEL["technology"]),
            )
        }

    def income_for(self, owner):
        income = {"money": 0, "steel": 0, "technology": 0}
        country_ids = ([owner] if owner in self.countries else [
            country_id for country_id, country in self.countries.items()
            if country["faction"] == owner
        ])
        for city in self.cities.values():
            if city["owner"] not in country_ids:
                continue
            production = self.city_production(city)
            for resource, amount in production.items():
                income[resource] += amount
        return income

    def recruit(self, city_position, kind):
        city = self.cities.get(city_position)
        if (self.phase != PLAYER or not city or
                self.faction_for(city["owner"]) != PLAYER):
            return None, "Select one of your cities to recruit."
        if kind not in UNIT_TYPES:
            return None, "Unknown unit type."
        cost = UNIT_TYPES[kind]["cost"]
        resources = self.countries[city["owner"]]["resources"]
        missing = [resource for resource, amount in cost.items()
               if resources[resource] < amount]
        if missing:
            return None, "Not enough resources to recruit {}.".format(kind)

        deployment = None
        if self.unit_at(city_position) is None:
            deployment = city_position
        else:
            for neighbor in self.neighbors(city_position):
                if self.tiles[neighbor] != "Water" and self.unit_at(neighbor) is None:
                    deployment = neighbor
                    break
        if deployment is None:
            return None, "No open hex is available near this city."

        for resource, amount in cost.items():
            resources[resource] -= amount
        unit = Unit(kind, city["owner"], deployment, PLAYER)
        unit.movement_left = unit.movement
        unit.attacks_left = unit.attacks_per_turn
        self.units.append(unit)
        return unit, "{} recruited in {}.".format(kind, city["name"])

    def move(self, unit, destination):
        if (unit not in self.units or unit.faction != self.phase or unit.attacked or
                unit.movement_left <= 0):
            return False, ["This unit cannot move now."]
        path = self.movement_paths(unit).get(destination)
        if not path:
            return False, ["That destination is blocked or out of movement range."]

        starting_position = unit.position
        events = []
        water_transition = None
        crossed_river = False
        for position in path:
            previous_position = unit.position
            previous_is_water = self.tiles[previous_position] == "Water"
            next_is_water = self.tiles[position] == "Water"
            if previous_is_water != next_is_water:
                if next_is_water:
                    unit.embark()
                    water_transition = "embarked"
                else:
                    unit.disembark()
                    water_transition = "landed"
                unit.movement_left = 0
            elif self.crosses_river(previous_position, position):
                unit.movement_left = 0
                crossed_river = True
            else:
                unit.movement_left -= self.terrain_movement_cost(unit, self.tiles[position])
            unit.position = position
            events.extend(self._capture_city(position, unit.owner))

        traveled = len(path)
        events.insert(0, "{} moved {} hexes ({} MP left).".format(
            unit.kind, traveled, unit.movement_left))
        if water_transition:
            events.append("{} as a transport; movement exhausted for this turn.".format(
                water_transition.capitalize()))
        if crossed_river:
            events.append("Crossed a river; movement exhausted for this turn.")
        self._check_winner()
        return True, events

    def attack(self, attacker, target_position):
        if (self.phase not in (PLAYER, ENEMY) or attacker not in self.units or
                attacker.faction != self.phase or attacker.attacked):
            return False, ["This unit cannot attack now."]
        defender = self.unit_at(target_position)
        city = self.cities.get(target_position)
        hostile_city = (city and self.faction_for(city["owner"]) != attacker.faction and
                        city["health"] > 0)
        if defender and defender.faction == attacker.faction:
            return False, ["Select an opposing unit or city as the target."]
        if not defender and not hostile_city:
            return False, ["Select an opposing unit or city as the target."]
        if self.distance(attacker.position, target_position) > attacker.range:
            return False, ["The target is out of range."]

        terrain_bonus = (TERRAIN_DEFENSE_BONUS
                         if self.tiles[target_position] in DEFENSIVE_TERRAINS else 0)
        damage = max(MIN_DAMAGE, int(round(
            attacker.effective_attack + random.randint(*DAMAGE_RANDOM_BONUS) - terrain_bonus)))
        city_damage = 0
        unit_damage = damage
        if city and self.faction_for(city["owner"]) != attacker.faction:
            if defender:
                city_damage = damage // 2
                unit_damage = damage - city_damage
            else:
                city_damage = damage
                unit_damage = 0
            city["health"] = max(0, city["health"] - city_damage)
        if defender:
            defender.hp -= unit_damage
        attacker.attacked = True
        attacker.movement_left = 0
        attacker_country = self.country_name(attacker.owner)
        events = ["{} {} dealt {} damage.".format(attacker_country, attacker.kind, damage)]
        if defender:
            events.append("{} took {} damage.".format(defender.kind, unit_damage))
        if city_damage:
            events.append("{} city HP: {}/{} (-{}).".format(
                city["name"], city["health"], city["max_health"], city_damage))
        if defender and defender.hp <= 0:
            self.units.remove(defender)
            events.append("{} {} was destroyed.".format(
                self.country_name(defender.owner), defender.kind))
            can_advance = (not city or self.faction_for(city["owner"]) == attacker.faction or
                           city["health"] <= 0)
            if attacker.kind != "Artillery" and can_advance:
                attacker.position = target_position
                events.extend(self._capture_city(target_position, attacker.owner))
        self._check_winner()
        return True, events

    def _capture_city(self, position, country_id):
        city = self.cities.get(position)
        if not city or self.faction_for(city["owner"]) == self.faction_for(country_id):
            return []
        city["owner"] = country_id
        city["health"] = city["max_health"]
        return ["{} captured {}.".format(self.country_name(country_id), city["name"])]

    def _heal_garrison_units(self):
        for unit in self.units:
            city = self.cities.get(unit.position)
            if (city and self.faction_for(city["owner"]) == unit.faction and
                    unit.hp < unit.max_hp):
                unit.hp = min(unit.max_hp, unit.hp + CITY_HEAL_PER_TURN)

    def enemy_turn(self):
        if self.phase not in (PLAYER, ENEMY):
            return ["It is not the player turn."], self.winner

        self.phase = ENEMY
        events = ["Enemy forces are taking their turn."]
        for enemy in list(self.units):
            if enemy.faction != ENEMY or enemy not in self.units:
                continue
            player_units = [unit for unit in self.units if unit.faction == PLAYER]
            player_cities = [position for position, city in self.cities.items()
                             if self.faction_for(city["owner"]) == PLAYER]
            targets = [unit.position for unit in player_units]
            targets.extend(position for position in player_cities if position not in targets)
            if not targets:
                break
            target_position = min(targets, key=lambda position: self.distance(
                enemy.position, position))
            if self.distance(enemy.position, target_position) <= enemy.range:
                _, attack_events = self.attack(enemy, target_position)
                events.extend(attack_events)
                continue

            paths = self.movement_paths(enemy)
            options = list(paths)
            if options:
                destination = min(options, key=lambda position: (
                    min(self.distance(position, target) for target in targets),
                    -len(paths[position])))
                current_distance = min(self.distance(enemy.position, target)
                                       for target in targets)
                next_distance = min(self.distance(destination, target) for target in targets)
                if next_distance < current_distance:
                    moved, movement_events = self.move(enemy, destination)
                    if moved:
                        events.extend(movement_events)
                        current_targets = [unit.position for unit in self.units
                                           if unit.faction == PLAYER]
                        current_targets.extend(position for position, city in self.cities.items()
                                               if self.faction_for(city["owner"]) == PLAYER and
                                               position not in current_targets)
                        if current_targets:
                            target_position = min(current_targets, key=lambda position:
                                                  self.distance(enemy.position, position))
                            if self.distance(enemy.position, target_position) <= enemy.range:
                                _, attack_events = self.attack(enemy, target_position)
                                events.extend(attack_events)

        self.winner = self._check_winner()
        if self.winner:
            return events, self.winner

        self.turn += 1
        income = self.income_for(PLAYER)
        for country_id, country in self.countries.items():
            country_income = self.income_for(country_id)
            for resource, amount in country_income.items():
                country["resources"][resource] += amount
        for unit in self.units:
            unit.movement_left = unit.movement
            unit.attacked = False
        self._heal_garrison_units()
        self.phase = PLAYER
        events.append("Turn {} begins. Income: +{} money, +{} steel, +{} technology.".format(
            self.turn, income["money"], income["steel"], income["technology"]))
        return events, None

    def _check_winner(self):
        if self.owned_cities(ENEMY) == 0:
            self.phase = "over"
            self.winner = PLAYER
        elif self.owned_cities(PLAYER) == 0:
            self.phase = "over"
            self.winner = ENEMY
        return self.winner