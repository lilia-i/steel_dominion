import os
import random
import heapq

from game_config import (
    CITY_HEAL_PER_TURN,
    CITY_PRODUCTION_PER_LEVEL,
    DAMAGE_RANDOM_BONUS,
    DEFENSIVE_TERRAINS,
    ENEMY,
    MIN_DAMAGE,
    NEUTRAL,
    PLAYER,
    TERRAIN_DEFENSE_BONUS,
    TERRAIN_MOVEMENT_COST,
    TRANSPORT_STATS,
    UNIT_TYPES,
)
from map_data import load_map_file, validate_playable_map
from unit_effects import (
    advance_statuses,
    attack_multiplier_for,
    damage_multiplier_for,
    incoming_damage_multiplier_for,
    movement_cost_for,
    process_kill,
    prevents_counterattack,
    refresh_tactical_statuses,
    resolve_attack_target,
    unit_can_attack,
    unit_can_move,
)

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
        self.statuses = []

    @property
    def attacked(self):
        return self.attacks_left <= 0

    @property
    def effective_attack(self):
        health_ratio = max(0.0, min(1.0, float(self.hp) / self.max_hp))
        health_factor = 1.0 if health_ratio >= 0.5 else 0.5 + health_ratio
        return self.attack * health_factor * attack_multiplier_for(self)

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
    def __init__(self, map_data=None, player_country_id=None):
        self.turn = 1
        self.phase = PLAYER
        self.winner = None
        self.columns = 0
        self.rows = 0
        self.tiles = {}
        self.river_edges = set()
        self.countries = {}
        self.cities = {}
        self.territory_city = {}
        self.units = []
        if map_data is None:
            map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "maps", "default_map.json")
            map_data = load_map_file(map_path)
        self._create_custom_world(map_data)
        eligible_countries = [country_id for country_id, country in self.countries.items()
                              if country["faction"] != NEUTRAL]
        if not eligible_countries:
            raise ValueError("A campaign needs at least one non-neutral country.")
        if player_country_id not in eligible_countries:
            player_country_id = next(
                (country_id for country_id in eligible_countries
                 if self.countries[country_id]["faction"] == PLAYER),
                eligible_countries[0])
        self.player_country_id = player_country_id
        self.player_faction = self.faction_for(player_country_id)
        self.enemy_faction = ENEMY if self.player_faction == PLAYER else PLAYER

    def can_control_unit(self, unit):
        if unit not in self.units or unit.faction == NEUTRAL:
            return False
        if self.phase == PLAYER:
            return unit.owner == self.player_country_id
        if self.phase == ENEMY:
            return unit.owner != self.player_country_id
        return False

    def _create_custom_world(self, map_data):
        map_data = validate_playable_map(map_data)
        self.columns = map_data["columns"]
        self.rows = map_data["rows"]
        self.river_edges = {
            frozenset((tuple(edge[0]), tuple(edge[1])))
            for edge in map_data["rivers"]
        }
        for country_data in map_data["countries"]:
            self.countries[country_data["id"]] = {
                "id": country_data["id"],
                "name": country_data["name"],
                "faction": country_data["faction"],
                "color": country_data.get("color"),
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

    @property
    def resources(self):
        country_id = self.player_country_id
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

    def terrain_movement_cost(self, unit, terrain):
        return movement_cost_for(self, unit, terrain, TERRAIN_MOVEMENT_COST[terrain])

    def movement_paths(self, unit):
        if (unit not in self.units or unit.attacked or unit.movement_left <= 0 or
                not unit_can_move(self, unit)):
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
                city["owner"] != self.player_country_id):
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
        unit = Unit(kind, city["owner"], deployment, self.faction_for(city["owner"]))
        unit.movement_left = unit.movement
        unit.attacks_left = unit.attacks_per_turn
        self.units.append(unit)
        return unit, "{} recruited in {}.".format(kind, city["name"])

    def move(self, unit, destination):
        if (not self.can_control_unit(unit) or unit.attacked or
                unit.movement_left <= 0 or not unit_can_move(self, unit)):
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

        unit.movement_left = 0
        refresh_tactical_statuses(self)
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
        if (not self.can_control_unit(attacker) or attacker.attacked or
                not unit_can_attack(self, attacker)):
            return False, ["This unit cannot attack now."]
        target_position = resolve_attack_target(self, attacker, target_position)
        if target_position not in self.tiles:
            return False, ["Select a valid target."]
        refresh_tactical_statuses(self)
        defender = self.unit_at(target_position)
        city = self.cities.get(target_position)
        if defender and self.faction_for(defender.owner) == NEUTRAL:
            return False, ["Neutral units cannot be attacked."]
        hostile_city = (city and self.faction_for(city["owner"]) not in
                        (attacker.faction, NEUTRAL) and
                        city["health"] > 0)
        if defender and defender.faction == attacker.faction:
            return False, ["Select an opposing unit or city as the target."]
        if not defender and not hostile_city:
            return False, ["Select an opposing unit or city as the target."]
        if self.distance(attacker.position, target_position) > attacker.range:
            return False, ["The target is out of range."]

        terrain_bonus = (TERRAIN_DEFENSE_BONUS
                         if self.tiles[target_position] in DEFENSIVE_TERRAINS else 0)
        hostile_city = (city if city and self.faction_for(city["owner"]) not in
                        (attacker.faction, NEUTRAL) else None)
        damage = max(MIN_DAMAGE, int(round(
            attacker.effective_attack + random.randint(*DAMAGE_RANDOM_BONUS) -
            terrain_bonus)))
        city_damage = 0
        unit_damage = damage
        if city and self.faction_for(city["owner"]) not in (attacker.faction, NEUTRAL):
            if defender:
                city_damage = damage // 2
                unit_damage = damage - city_damage
                unit_damage = max(MIN_DAMAGE, int(round(
                    unit_damage * damage_multiplier_for(
                        self, attacker, defender, hostile_city, "unit",
                        self.tiles[target_position]) *
                    incoming_damage_multiplier_for(
                        self, defender, attacker, "unit",
                        self.tiles[target_position]))))
                city_damage = int(round(
                    city_damage * damage_multiplier_for(
                        self, attacker, None, city, "city",
                        self.tiles[target_position])))
            else:
                city_damage = max(MIN_DAMAGE, int(round(
                    damage * damage_multiplier_for(
                        self, attacker, None, city, "city",
                        self.tiles[target_position]))))
                unit_damage = 0
            city["health"] = max(0, city["health"] - city_damage)
        elif defender:
            unit_damage = max(MIN_DAMAGE, int(round(
                unit_damage * damage_multiplier_for(
                    self, attacker, defender, None, "unit",
                    self.tiles[target_position]) *
                incoming_damage_multiplier_for(
                    self, defender, attacker, "unit",
                    self.tiles[target_position]))))
        damage = city_damage + unit_damage
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
            refresh_tactical_statuses(self)
            events.extend(process_kill(self, attacker))
            can_advance = (not city or self.faction_for(city["owner"]) == attacker.faction or
                           city["health"] <= 0)
            if attacker.kind != "Artillery" and can_advance:
                attacker.position = target_position
                events.extend(self._capture_city(target_position, attacker.owner))
        elif (defender and defender in self.units and
              self.distance(attacker.position, defender.position) <= defender.range):
            events.extend(self._counterattack(attacker, defender, target_position))
        refresh_tactical_statuses(self)
        self._check_winner()
        return True, events

    def _counterattack(self, attacker, defender, target_position):
        if (not unit_can_attack(self, defender) or
                prevents_counterattack(self, attacker, defender, target_position)):
            return []
        terrain = self.tiles[attacker.position]
        terrain_bonus = (TERRAIN_DEFENSE_BONUS
                         if terrain in DEFENSIVE_TERRAINS else 0)
        damage = max(MIN_DAMAGE, int(round(
            defender.effective_attack * 0.75 +
            random.randint(*DAMAGE_RANDOM_BONUS) - terrain_bonus)))
        damage = max(MIN_DAMAGE, int(round(
            damage * damage_multiplier_for(
                self, defender, attacker, None, "unit", terrain) *
            incoming_damage_multiplier_for(
                self, attacker, defender, "counter", terrain))))
        attacker.hp -= damage
        events = ["{} {} counterattacked for {} damage.".format(
            self.country_name(defender.owner), defender.kind, damage),
            "{} took {} counterattack damage.".format(attacker.kind, damage)]
        if attacker.hp <= 0:
            self.units.remove(attacker)
            events.append("{} {} was destroyed by a counterattack.".format(
                self.country_name(attacker.owner), attacker.kind))
            refresh_tactical_statuses(self)
            events.extend(process_kill(self, defender))
        return events

    def _capture_city(self, position, country_id):
        city = self.cities.get(position)
        if (not city or self.faction_for(city["owner"]) == NEUTRAL or
            self.faction_for(country_id) == NEUTRAL or
            self.faction_for(city["owner"]) == self.faction_for(country_id)):
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

    def _enemy_targets(self, enemy, target_faction):
        priorities = {}
        for unit in self.units:
            if unit.faction == target_faction:
                priorities[unit.position] = 2
        for position, city in self.cities.items():
            if self.faction_for(city["owner"]) != target_faction:
                continue
            occupant = self.unit_at(position)
            if occupant and occupant.faction == target_faction:
                continue
            priorities[position] = 0 if city["health"] <= 0 else 1
        return [(priority, position) for position, priority in priorities.items()]

    def _enemy_target_score(self, enemy, priority, position, from_position=None):
        source = from_position if from_position is not None else enemy.position
        distance = self.distance(source, position)
        support = sum(1 for unit in self.units
                      if unit is not enemy and unit.faction == enemy.faction and
                      self.distance(unit.position, position) <= 2)
        return priority, distance + support * 1.5, distance

    def _enemy_destination_score(self, enemy, position, paths, targets):
        target_score, _ = min(
            (self._enemy_target_score(enemy, priority, target, position), target)
            for priority, target in targets)
        nearby_units = sum(1 for unit in self.units
                           if unit is not enemy and unit.faction == enemy.faction and
                           self.distance(unit.position, position) <= 1)
        return (target_score[0], target_score[1] + nearby_units * 0.4,
                target_score[2], -len(paths[position]), position)

    def enemy_turn(self):
        if self.phase not in (PLAYER, ENEMY):
            return ["It is not the player turn."], self.winner

        self.phase = ENEMY
        events = ["Enemy forces are taking their turn."]
        for enemy in list(self.units):
            if (enemy.owner == self.player_country_id or
                    enemy.faction == NEUTRAL or enemy not in self.units):
                continue
            target_faction = (ENEMY if enemy.faction == PLAYER else PLAYER)
            while enemy in self.units and not enemy.attacked:
                targets = self._enemy_targets(enemy, target_faction)
                if not targets:
                    break
                priority, target_position = min(
                    targets, key=lambda item: self._enemy_target_score(
                        enemy, item[0], item[1]))
                city = self.cities.get(target_position)
                open_city = (city and city["health"] <= 0 and
                             self.unit_at(target_position) is None)
                if (not open_city and
                        self.distance(enemy.position, target_position) <= enemy.range):
                    attacked, attack_events = self.attack(enemy, target_position)
                    events.extend(attack_events)
                    if attacked and not enemy.attacked:
                        continue
                    if attacked:
                        break

                paths = self.movement_paths(enemy)
                if not paths:
                    break
                destination = min(paths, key=lambda position:
                                  self._enemy_destination_score(
                                      enemy, position, paths, targets))
                current_score = self._enemy_target_score(
                    enemy, priority, target_position)
                next_score = self._enemy_destination_score(
                    enemy, destination, paths, targets)
                if not (next_score[0] < current_score[0] or
                        next_score[2] < current_score[2]):
                    break
                moved, movement_events = self.move(enemy, destination)
                if not moved:
                    break
                events.extend(movement_events)
            if self._check_winner():
                break

        self.winner = self._check_winner()
        if self.winner:
            return events, self.winner

        self.turn += 1
        income = self.income_for(self.player_faction)
        for country_id, country in self.countries.items():
            country_income = self.income_for(country_id)
            for resource, amount in country_income.items():
                country["resources"][resource] += amount
        for unit in self.units:
            unit.movement_left = unit.movement
            unit.attacked = False
        advance_statuses(self)
        self._heal_garrison_units()
        self.phase = PLAYER
        events.append("Turn {} begins. Income: +{} money, +{} steel, +{} technology.".format(
            self.turn, income["money"], income["steel"], income["technology"]))
        return events, None

    def _check_winner(self):
        if self.owned_cities(self.enemy_faction) == 0:
            self.phase = "over"
            self.winner = PLAYER
        elif self.owned_cities(self.player_faction) == 0:
            self.phase = "over"
            self.winner = ENEMY
        return self.winner