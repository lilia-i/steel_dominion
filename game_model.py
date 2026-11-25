import os
import random
import heapq

from game_config import (
    CITY_HEAL_PER_TURN,
    CITY_PRODUCTION_PER_LEVEL,
    DAMAGE_RANDOM_BONUS,
    DEFENSIVE_TERRAINS,
    ENEMY,
    FORCED_MARCH_MULTIPLIER,
    FORCED_MARCH_UNATTACKED_TURNS,
    MIN_DAMAGE,
    NEUTRAL,
    PLAYER,
    UNIT_MAINTENANCE_RATE,
    TERRAIN_DEFENSE_BONUS,
    TERRAIN_MOVEMENT_COST,
    TRANSPORT_STATS,
    UNIT_TYPES,
)
from game_ai import control_units, recruit_units
from app_paths import application_path
from map_data import hex_neighbors, load_map_file, validate_playable_map
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
    OverextendedMorale,
)

class Unit(object):
    next_id = 1

    def __init__(self, kind, owner, position, faction=None):
        info = UNIT_TYPES[kind]
        self.id = Unit.next_id
        Unit.next_id += 1
        self.kind = kind
        self.original_category = info["category"]
        self.category = self.original_category
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
        self.base_movement = self.original_movement
        self.movement_left = self.movement
        self.unattacked_rounds = 0
        self.attacked_this_round = False
        self.movement_extended = False
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
        self.category = TRANSPORT_STATS["category"]
        self.attack = TRANSPORT_STATS["attack"]
        self.range = TRANSPORT_STATS["range"]
        self.base_movement = TRANSPORT_STATS["movement"]
        self.movement = self.base_movement * (
            FORCED_MARCH_MULTIPLIER if self.movement_extended else 1)

    def disembark(self):
        if not self.embarked:
            return
        self.embarked = False
        self.category = self.original_category
        self.attack = self.original_attack
        self.range = self.original_range
        self.base_movement = self.original_movement
        self.movement = self.base_movement * (
            FORCED_MARCH_MULTIPLIER if self.movement_extended else 1)


class GameModel(object):
    def __init__(self, map_data=None, player_country_id=None):
        self.turn = 1
        self.phase = PLAYER
        self.winner = None
        self.lose_on_country_elimination = False
        self.columns = 0
        self.rows = 0
        self.tiles = {}
        self.river_edges = set()
        self.countries = {}
        self.cities = {}
        self.territory_city = {}
        self.units = []
        self.units_by_position = {}
        self.last_damage_events = []
        if map_data is None:
            map_path = application_path("maps", "default_map.json")
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
                "original_owner": city_data["owner"],
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
            self._add_unit(Unit(unit_data["type"], unit_data["owner"],
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
        return self.units_by_position.get(position)

    def _add_unit(self, unit):
        self.units.append(unit)
        self.units_by_position[unit.position] = unit

    def _spawn_unit(self, kind, owner, position, faction=None):
        unit = Unit(kind, owner, position, faction)
        self._add_unit(unit)
        return unit

    def _remove_unit(self, unit):
        self.units.remove(unit)
        if self.units_by_position.get(unit.position) is unit:
            del self.units_by_position[unit.position]

    def _move_unit(self, unit, position):
        del self.units_by_position[unit.position]
        unit.position = position
        self.units_by_position[position] = unit

    def neighbors(self, position):
        return hex_neighbors(self.columns, self.rows, position)

    def _positions_within(self, position, distance):
        positions = {position}
        frontier = {position}
        for _ in range(distance):
            frontier = {
                neighbor
                for current in frontier
                for neighbor in self.neighbors(current)
            } - positions
            positions.update(frontier)
        return positions

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

    def movement_paths(self, unit, budget=None):
        custom_budget = budget is not None
        if (unit not in self.units or unit.attacked or
                (not custom_budget and unit.movement_left <= 0) or
                not unit_can_move(self, unit)):
            return {}

        budget = unit.movement_left if budget is None else budget
        best_cost = {unit.position: 0}
        previous = {}
        queue = [(0, unit.position)]
        while queue:
            spent, position = heapq.heappop(queue)
            if spent != best_cost[position] or spent >= budget:
                continue
            for neighbor in self.neighbors(position):
                occupant = self.units_by_position.get(neighbor)
                if (occupant and occupant is not unit and
                        occupant.faction != unit.faction):
                    continue
                city = self.cities.get(neighbor)
                if city and city["health"] > 0:
                    city_faction = self.faction_for(city["owner"])
                    if (city_faction != unit.faction or
                            city["owner"] != unit.owner):
                        continue

                current_is_water = self.tiles[position] == "Water"
                next_is_water = self.tiles[neighbor] == "Water"
                if current_is_water != next_is_water:
                    full_budget = (budget == unit.base_movement if custom_budget else
                                   budget == unit.movement and
                                   unit.movement_left == unit.movement)
                    if spent > 0 or not full_budget:
                        continue
                    next_spent = budget
                elif self.crosses_river(position, neighbor):
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
            if (destination == unit.position or
                    self.unit_at(destination) is not None):
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
        country_ids = {owner} if owner in self.countries else {
            country_id for country_id, country in self.countries.items()
            if country["faction"] == owner
        }
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

        if self.unit_at(city_position) is not None:
            return None, "The city must be empty to recruit a unit."

        for resource, amount in cost.items():
            resources[resource] -= amount
        unit = Unit(kind, city["owner"], city_position,
                self.faction_for(city["owner"]))
        unit.movement_left = 0
        unit.attacks_left = 0
        self._add_unit(unit)
        return unit, "{} recruited in {}.".format(kind, city["name"])

    def move(self, unit, destination, path=None):
        if (not self.can_control_unit(unit) or unit.attacked or
                unit.movement_left <= 0 or not unit_can_move(self, unit)):
            return False, ["This unit cannot move now."]
        if path is None:
            path = self.movement_paths(unit).get(destination)
        if not path:
            return False, ["That destination is blocked or out of movement range."]
        if self.unit_at(destination) not in (None, unit):
            return False, ["That destination is occupied."]
        if any(
                self.cities.get(position) and
                self.cities[position]["health"] > 0 and
                self.cities[position]["owner"] != unit.owner and
                self.faction_for(self.cities[position]["owner"]) == unit.faction
                for position in path):
            return False, ["A healthy allied city blocks that route."]

        base_reachable = None
        if unit.movement_extended:
            base_reachable = set(self.movement_paths(unit, budget=unit.base_movement))
            base_reachable.add(unit.position)
        events = []
        water_transition = None
        crossed_river = False
        previous_position = unit.position
        for position in path:
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
            if self.unit_at(position) is None:
                self._move_unit(unit, position)
                events.extend(self._capture_city(position, unit.owner))
            previous_position = position

        unit.movement_left = 0
        if unit.movement_extended:
            if unit.position in base_reachable:
                self._clear_overextended_morale(unit)
                unit.movement_extended = False
                unit.movement = unit.base_movement
            elif not any(isinstance(status, OverextendedMorale)
                         for status in unit.statuses):
                unit.statuses.append(OverextendedMorale())
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
        self.last_damage_events = []
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
        movement_before_attack = attacker.movement_left
        attacker.attacked_this_round = True

        terrain_bonus = (TERRAIN_DEFENSE_BONUS
                         if self.tiles[target_position] in DEFENSIVE_TERRAINS else 0)
        hostile_city = (city if city and self.faction_for(city["owner"]) not in
                        (attacker.faction, NEUTRAL) else None)
        damage = max(MIN_DAMAGE, int(round(
            attacker.effective_attack *
            (1.0 + random.uniform(*DAMAGE_RANDOM_BONUS)) - terrain_bonus)))
        city_damage = 0
        unit_damage = damage
        if city and self.faction_for(city["owner"]) not in (attacker.faction, NEUTRAL):
            if defender:
                if city["health"] > 0:
                    city_base_damage = damage // 2
                    unit_base_damage = damage - city_base_damage
                    city_damage = min(
                        city["health"],
                        max(0, int(round(
                            city_base_damage * damage_multiplier_for(
                                self, attacker, None, city, "city",
                                self.tiles[target_position])))))
                    unit_base_damage += max(
                        0, city_base_damage - city["health"])
                else:
                    unit_base_damage = damage
                unit_damage = max(MIN_DAMAGE, int(round(
                    unit_base_damage * damage_multiplier_for(
                        self, attacker, defender, None, "unit",
                        self.tiles[target_position]) *
                    incoming_damage_multiplier_for(
                        self, defender, attacker, "unit",
                        self.tiles[target_position]))))
            else:
                city_damage = max(MIN_DAMAGE, int(round(
                    damage * damage_multiplier_for(
                        self, attacker, None, city, "city",
                        self.tiles[target_position]))))
                unit_damage = 0
            city["health"] = max(0, city["health"] - city_damage)
            if city_damage:
                city["attacked_this_round"] = True
        elif defender:
            unit_damage = max(MIN_DAMAGE, int(round(
                unit_damage * damage_multiplier_for(
                    self, attacker, defender, None, "unit",
                    self.tiles[target_position]) *
                incoming_damage_multiplier_for(
                    self, defender, attacker, "unit",
                    self.tiles[target_position]))))
        damage = city_damage + unit_damage
        if city_damage:
            self.last_damage_events.append((target_position, city_damage))
        if defender:
            defender.hp -= unit_damage
            self.last_damage_events.append((defender.position, unit_damage))
        attacker.attacked = True
        attacker.unattacked_rounds = 0
        self._clear_overextended_morale(attacker)
        attacker.movement_extended = False
        attacker.movement = attacker.base_movement
        attacker.movement_left = 0
        attacker_country = self.country_name(attacker.owner)
        events = ["{} {} dealt {} damage.".format(attacker_country, attacker.kind, damage)]
        if defender:
            events.append("{} took {} damage.".format(defender.kind, unit_damage))
        if city_damage:
            events.append("{} city HP: {}/{} (-{}).".format(
                city["name"], city["health"], city["max_health"], city_damage))
        if defender and defender.hp <= 0:
            self._remove_unit(defender)
            events.append("{} {} was destroyed.".format(
                self.country_name(defender.owner), defender.kind))
            refresh_tactical_statuses(self)
            events.extend(process_kill(self, attacker, movement_before_attack))
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
        defender.attacked_this_round = True
        terrain = self.tiles[attacker.position]
        terrain_bonus = (TERRAIN_DEFENSE_BONUS
                         if terrain in DEFENSIVE_TERRAINS else 0)
        damage = max(MIN_DAMAGE, int(round(
            defender.effective_attack * 0.75 *
            (1.0 + random.uniform(*DAMAGE_RANDOM_BONUS)) - terrain_bonus)))
        damage = max(MIN_DAMAGE, int(round(
            damage * damage_multiplier_for(
                self, defender, attacker, None, "unit", terrain) *
            incoming_damage_multiplier_for(
                self, attacker, defender, "counter", terrain))))
        attacker.hp -= damage
        self.last_damage_events.append((attacker.position, damage))
        self._clear_overextended_morale(defender)
        defender.movement_extended = False
        defender.movement = defender.base_movement
        events = ["{} {} counterattacked for {} damage.".format(
            self.country_name(defender.owner), defender.kind, damage),
            "{} took {} counterattack damage.".format(attacker.kind, damage)]
        if attacker.hp <= 0:
            self._remove_unit(attacker)
            events.append("{} {} was destroyed by a counterattack.".format(
                self.country_name(attacker.owner), attacker.kind))
            refresh_tactical_statuses(self)
            events.extend(process_kill(self, defender))
        return events

    @staticmethod
    def _clear_overextended_morale(unit):
        unit.statuses = [status for status in unit.statuses
                         if not isinstance(status, OverextendedMorale)]

    def _capture_city(self, position, country_id):
        city = self.cities.get(position)
        if (not city or self.faction_for(city["owner"]) == NEUTRAL or
                self.faction_for(country_id) == NEUTRAL):
            return []
        if (city["owner"] == country_id or
                (self.faction_for(city["owner"]) ==
                 self.faction_for(country_id) and city["health"] > 0)):
            return []
        city["owner"] = country_id
        return ["{} captured {}.".format(self.country_name(country_id), city["name"])]

    def _heal_garrison_units(self):
        for unit in self.units:
            city = self.cities.get(unit.position)
            if (city and self.faction_for(city["owner"]) == unit.faction and
                    unit.hp < unit.max_hp):
                unit.hp = min(unit.max_hp, unit.hp + CITY_HEAL_PER_TURN)
        for city in self.cities.values():
            if (not city.get("attacked_this_round", False) and
                    city["health"] < city["max_health"]):
                city["health"] = min(
                    city["max_health"], city["health"] + CITY_HEAL_PER_TURN)
            city["attacked_this_round"] = False

    def _ai_recruit(self, owner_ids=None):
        return recruit_units(self, owner_ids)

    def _ai_control_units(self, units, target_faction=None):
        return control_units(self, units, target_faction)

    def unit_maintenance_for(self, owner_id):
        return {
            resource: int(sum(
                UNIT_TYPES[unit.kind]["cost"][resource] *
                UNIT_MAINTENANCE_RATE
                for unit in self.units
                if unit.owner == owner_id and unit.faction != NEUTRAL))
            for resource in ("money", "steel", "technology")
        }

    def _charge_unit_maintenance(self):
        maintenance = {
            country_id: self.unit_maintenance_for(country_id)
            for country_id in self.countries
        }
        for country_id, costs in maintenance.items():
            resources = self.countries[country_id]["resources"]
            for resource, amount in costs.items():
                resources[resource] = max(0, resources[resource] - amount)
        return maintenance

    def auto_player_turn(self):
        if self.phase != PLAYER:
            return ["It is not the player turn."], self.winner
        events = ["Automated player actions are complete."]
        events.extend(self._ai_recruit(owner_ids={self.player_country_id}))
        player_units = [unit for unit in self.units
                        if unit.owner == self.player_country_id]
        target_faction = ENEMY if self.player_faction == PLAYER else PLAYER
        events.extend(self._ai_control_units(player_units, target_faction))
        events.extend(self._ai_recruit(owner_ids={self.player_country_id}))
        self.winner = self._check_winner()
        return events, self.winner

    def enemy_turn(self):
        if self.phase not in (PLAYER, ENEMY):
            return ["It is not the player turn."], self.winner

        self.phase = ENEMY
        events = ["Enemy forces are taking their turn."]
        events.extend(self._ai_recruit())
        enemy_units = [unit for unit in self.units
                       if unit.owner != self.player_country_id]
        events.extend(self._ai_control_units(enemy_units))
        self.winner = self._check_winner()
        if self.winner:
            return events, self.winner
        events.extend(self._ai_recruit())

        self.winner = self._check_winner()
        if self.winner:
            return events, self.winner

        self.turn += 1
        income = self.income_for(self.player_faction)
        for country_id, country in self.countries.items():
            country_income = self.income_for(country_id)
            for resource, amount in country_income.items():
                country["resources"][resource] += amount
        maintenance = self._charge_unit_maintenance()
        player_maintenance = {
            resource: sum(
                costs[resource] for country_id, costs in maintenance.items()
                if self.faction_for(country_id) == self.player_faction)
            for resource in ("money", "steel", "technology")
        }
        for unit in self.units:
            if unit.attacked_this_round:
                unit.unattacked_rounds = 0
            else:
                unit.unattacked_rounds += 1
            unit.attacked_this_round = False
            unit.movement_extended = (
                unit.unattacked_rounds >= FORCED_MARCH_UNATTACKED_TURNS)
            unit.movement = unit.base_movement * (
                FORCED_MARCH_MULTIPLIER if unit.movement_extended else 1)
            unit.movement_left = unit.movement
            unit.attacked = False
        advance_statuses(self)
        self._heal_garrison_units()
        self.phase = PLAYER
        events.append("Turn {} begins. Income: +{} money, +{} steel, +{} technology; "
                      "maintenance: -{} money, -{} steel, -{} technology.".format(
            self.turn, income["money"], income["steel"], income["technology"],
            player_maintenance["money"], player_maintenance["steel"],
            player_maintenance["technology"]))
        return events, None

    def _check_winner(self):
        if (self.lose_on_country_elimination and
                self.owned_cities(self.player_country_id) == 0):
            self.phase = "over"
            self.winner = ENEMY
        elif self.owned_cities(self.enemy_faction) == 0:
            self.phase = "over"
            self.winner = PLAYER
        elif self.owned_cities(self.player_faction) == 0:
            self.phase = "over"
            self.winner = ENEMY
        return self.winner