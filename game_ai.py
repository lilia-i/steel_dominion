import random

from game_config import (
    ENEMY,
    NEUTRAL,
    PLAYER,
    ENEMY_AI_UNITS_PER_CITY_LEVEL,
    PLAYER_AI_UNITS_PER_CITY_LEVEL,
    UNIT_TYPES,
    unit_level_stats,
)


TARGET_SCORE_MARGIN = 2.0
TARGET_DISTANCE_WINDOW = 3
RECAPTURE_RADIUS = 8
RECAPTURE_BONUS_PER_HEX = 0.25
FORCE_BALANCE_RADIUS = 8


def _city_value(city):
    production = city["industry_level"] + city["research_level"]
    return 0.5 + min(city["city_level"], 6) * 0.25 + min(production, 6) * 0.15


def _recapture_value(model, owner_id, position, target_position):
    target_city = model.cities[target_position]
    if target_city.get("original_owner") != owner_id:
        return 0.0
    distance = model.distance(position, target_position)
    return max(0.0, (RECAPTURE_RADIUS - distance) *
               RECAPTURE_BONUS_PER_HEX)


def _unit_strength(unit):
    health_ratio = (float(unit.hp) / unit.max_hp if unit.max_hp else 0.0)
    return max(0.0, unit.hp) + unit.effective_attack * 2.0 + unit.range * 8.0


def _recruit_priority(kind, level):
    details = unit_level_stats(kind, level)
    strength = (details["hp"] + details["attack"] * 2.0 +
                UNIT_TYPES[kind]["range"] * 8.0)
    cost = sum(details["cost"].values())
    return strength, cost


def _recruit_level_weights(model, owner_id, affordable_by_level):
    faction = model.faction_for(owner_id)
    pressure = max((
        _local_force_deficit(model, faction, city_position)
        for city_position, city in model.cities.items()
        if city["owner"] == owner_id
    ), default=0.0)
    pressure_ratio = max(-1.0, min(1.0, pressure / 180.0))
    resources = model.countries[owner_id]["resources"]
    base_weights = {1: 0.5, 2: 0.3, 3: 0.2}
    weights = []
    for level in sorted(affordable_by_level):
        best_reserve = 1
        for kind, _ in affordable_by_level[level]:
            costs = unit_level_stats(kind, level)["cost"]
            resource_reserve = min((
                resources[resource] // amount
                for resource, amount in costs.items() if amount > 0
            ), default=3)
            best_reserve = max(best_reserve, resource_reserve)
        reserve_bonus = 1.0 + min(2, best_reserve - 1) * 0.4 * (level - 1) / 2.0
        pressure_bonus = max(
            0.25, 1.0 + pressure_ratio * (level - 2) * 0.5)
        weights.append(base_weights[level] * reserve_bonus * pressure_bonus)
    return weights


def _local_force_deficit(model, faction, position):
    friendly_strength = 0.0
    hostile_strength = 0.0
    for unit in model.units:
        distance = model.distance(position, unit.position)
        if distance > FORCE_BALANCE_RADIUS:
            continue
        distance_weight = ((FORCE_BALANCE_RADIUS + 1.0 - distance) /
                           (FORCE_BALANCE_RADIUS + 1.0))
        strength = _unit_strength(unit) * distance_weight
        if unit.faction == faction:
            friendly_strength += strength
        elif unit.faction != NEUTRAL:
            hostile_strength += strength
    return hostile_strength - friendly_strength


def recruit_units(model, owner_ids=None):
    events = []
    occupied_positions = set(model.units_by_position)
    for owner_id, country in model.countries.items():
        if model.faction_for(owner_id) == NEUTRAL:
            continue
        if owner_ids is None and owner_id == model.player_country_id:
            continue
        if owner_ids is not None and owner_id not in owner_ids:
            continue
        resources = country["resources"]
        unit_count = sum(1 for unit in model.units if unit.owner == owner_id)
        city_level_total = sum(
            city["city_level"] for city in model.cities.values()
            if city["owner"] == owner_id)
        unit_limit = None
        if owner_id != model.player_country_id:
            capacity_ratio = (
                PLAYER_AI_UNITS_PER_CITY_LEVEL
                if model.faction_for(owner_id) == model.player_faction else
                ENEMY_AI_UNITS_PER_CITY_LEVEL)
            unit_limit = max(3, int(city_level_total * capacity_ratio))
        while True:
            if unit_limit is not None and unit_count >= unit_limit:
                break
            faction = model.faction_for(owner_id)
            affordable_by_level = {}
            for level in (1, 2, 3):
                affordable_options = [
                    (kind, level)
                    for kind in UNIT_TYPES
                    if all(resources[resource] >= amount
                           for resource, amount in
                           unit_level_stats(kind, level)["cost"].items())]
                if affordable_options:
                    affordable_by_level[level] = affordable_options
            if not affordable_by_level:
                break
            levels = sorted(affordable_by_level)
            weights = _recruit_level_weights(
                model, owner_id, affordable_by_level)
            level = random.choices(levels, weights=weights, k=1)[0]
            affordable_options = affordable_by_level[level]
            best_priority = max(_recruit_priority(kind, level)
                                for kind, level in affordable_options)
            best_options = [(kind, level)
                            for kind, level in affordable_options
                            if _recruit_priority(kind, level) == best_priority]
            kind, level = random.choice(best_options)

            deployments = []
            hostile_units = [unit for unit in model.units
                             if unit.faction not in (faction, NEUTRAL)]
            hostile_cities = [position for position, city in model.cities.items()
                              if model.faction_for(city["owner"]) not in
                              (faction, NEUTRAL)]
            for city_position, city in model.cities.items():
                if city["owner"] != owner_id:
                    continue
                if city_position in occupied_positions:
                    continue
                pressure = [model.distance(city_position, unit.position)
                            for unit in hostile_units]
                siege_count = sum(distance <= 1 for distance in pressure)
                pressure_score = sum(
                    3 if distance <= 1 else 1 if distance <= 3 else 0
                    for distance in pressure)
                front_distances = pressure or [
                    model.distance(city_position, position)
                    for position in hostile_cities]
                front_distance = min(front_distances) if front_distances else (
                    model.columns + model.rows)
                strategic_score = min((
                    model.distance(city_position, position) -
                    _city_value(model.cities[position]) -
                    _recapture_value(model, owner_id, city_position, position)
                    for position in hostile_cities),
                    default=model.columns + model.rows)
                health_ratio = (float(city["health"]) / city["max_health"]
                                if city["max_health"] else 1.0)
                defense_urgency = ((1.0 - health_ratio) *
                                   (1.0 + siege_count * 2 + pressure_score))
                force_deficit = _local_force_deficit(
                    model, faction, city_position)
                city_score = (-defense_urgency, -siege_count,
                              -pressure_score, -force_deficit, strategic_score,
                              front_distance, city_position)
                deployments.append((city_score, city_position, city["name"]))

            if not deployments:
                break
            best_score = min(item[0][:6] for item in deployments)
            best_deployments = [item for item in deployments
                                if item[0][:6] == best_score]
            _, deployment, city_name = random.choice(best_deployments)
            for resource, amount in UNIT_TYPES[kind]["cost"].items():
                resources[resource] -= amount
            unit = model._spawn_unit(kind, owner_id, deployment, faction, level)
            unit.movement_left = 0
            unit.attacks_left = 0
            occupied_positions.add(deployment)
            unit_count += 1
            events.append("{} recruited in {}.".format(kind, city_name))
    return events


def _enemy_targets(model, target_faction):
    targets = set()
    for unit in model.units:
        if unit.faction == target_faction:
            targets.add(unit.position)
    for position, city in model.cities.items():
        if model.faction_for(city["owner"]) == target_faction:
            targets.add(position)
    return sorted(targets)


def _target_factors(model, enemy, targets):
    units_by_position = model.units_by_position
    factors = {}
    for position in targets:
        target_unit = units_by_position.get(position)
        unit_value = 3.0 if target_unit and target_unit.faction != enemy.faction else 0.0
        if unit_value:
            territory_position = model.territory_city.get(position)
            territory_city = model.cities.get(territory_position)
            if (territory_city and
                    model.faction_for(territory_city["owner"]) == enemy.faction):
                unit_value += 4.0
            else:
                near_friendly_city = any(
                    model.faction_for(city["owner"]) == enemy.faction and
                    model.distance(city_position, position) <= 2
                    for city_position, city in model.cities.items())
                if near_friendly_city:
                    unit_value += 2.0
        city = model.cities.get(position)
        city_value = 0.0
        if city and model.faction_for(city["owner"]) != enemy.faction:
            city_value = _city_value(city)
            if city["health"] > 0:
                health_ratio = (float(city["health"]) / city["max_health"]
                                if city["max_health"] else 1.0)
                city_value += (1.0 - health_ratio) * 1.5
            if city.get("original_owner") == enemy.owner:
                city_value += _recapture_value(
                    model, enemy.owner, enemy.position, position)
        factors[position] = (0.0, unit_value, city_value)
    return factors


def _target_score(model, enemy, position, target_factors,
                  from_position=None):
    source = from_position if from_position is not None else enemy.position
    distance = model.distance(source, position)
    support_bonus, unit_value, city_value = target_factors[position]
    return distance - support_bonus - unit_value - city_value


def _is_attack_target(model, enemy, position):
    defender = model.unit_at(position)
    if defender:
        return defender.faction not in (enemy.faction, NEUTRAL)
    city = model.cities.get(position)
    return (city is not None and city["health"] > 0 and
            model.faction_for(city["owner"]) not in (enemy.faction, NEUTRAL))


def _destination_score(model, enemy, position, paths, targets,
                       target_factors):
    target_score = min(_target_score(
        model, enemy, target, target_factors, position) for target in targets)
    return target_score, len(paths[position]), position


def _captures_friendly_city_on_path(model, unit, path):
    return any(
        position in model.cities and
        model.cities[position]["health"] <= 0 and
        model.cities[position]["owner"] != unit.owner and
        model.faction_for(model.cities[position]["owner"]) == unit.faction and
        model.unit_at(position) is None
        for position in path)


def _choose_candidate(scored_candidates, tolerance=0.25):
    best_score = min(score for score, _ in scored_candidates)
    candidates = [candidate for score, candidate in scored_candidates
                  if score <= best_score + tolerance]
    return random.choice(candidates)


def control_units(model, units, target_faction=None):
    events = []
    for unit in list(units):
        if unit.faction == NEUTRAL or unit not in model.units:
            continue
        unit_target_faction = target_faction
        if unit_target_faction is None:
            unit_target_faction = (ENEMY if unit.faction == PLAYER else PLAYER)
        while unit in model.units and not unit.attacked and not model.winner:
            all_targets = _enemy_targets(model, unit_target_faction)
            if not all_targets:
                break
            target_factors = _target_factors(model, unit, all_targets)
            nearest_distance = min(
                model.distance(unit.position, position) for position in all_targets)
            local_targets = [
                position for position in all_targets
                if model.distance(unit.position, position) <=
                nearest_distance + TARGET_DISTANCE_WINDOW]
            target_scores = {
                position: _target_score(model, unit, position, target_factors)
                for position in local_targets
            }
            best_target_score = min(target_scores.values())
            targets = [position for position in local_targets
                       if target_scores[position] <=
                       best_target_score + TARGET_SCORE_MARGIN]
            target_position = _choose_candidate([
                (target_scores[position], position) for position in targets])
            attack_targets = [
                position for position in all_targets
                if model.distance(unit.position, position) <= unit.range and
                _is_attack_target(model, unit, position)]
            attack_position = None
            if attack_targets:
                attack_position = _choose_candidate([
                    (_target_score(model, unit, position, target_factors), position)
                    for position in attack_targets])
            current_score = _target_score(
                model, unit, attack_position if attack_position is not None
                else target_position, target_factors)

            paths = model.movement_paths(unit)
            if paths:
                destination_scores = {
                    position: _destination_score(
                        model, unit, position, paths, targets, target_factors)
                    for position in paths
                }
                safe_destination_scores = {
                    position: score
                    for position, score in destination_scores.items()
                    if not _captures_friendly_city_on_path(
                        model, unit, paths[position])
                }
                if safe_destination_scores:
                    destination_scores = safe_destination_scores
                best_score = min(score[0]
                                 for score in destination_scores.values())
                near_best = [
                    position for position, score in destination_scores.items()
                    if score[0] <= best_score + 0.15
                ]
                best_path_score = min(destination_scores[position][1]
                                      for position in near_best)
                best_paths = [
                    position for position in near_best
                    if destination_scores[position][1] == best_path_score
                ]
                destination = random.choice(best_paths)
                next_score = destination_scores[destination]
                if attack_position is None and next_score[0] < current_score:
                    moved, movement_events = model.move(unit, destination)
                    if moved:
                        events.extend(movement_events)
                        continue
            if attack_position is not None:
                attacked, attack_events = model.attack(unit, attack_position)
                events.extend(attack_events)
                if not attacked or unit.attacked:
                    break
                continue
            break
        if model._check_winner():
            break
    return events