import random

from game_config import NEUTRAL, TERRAIN_MOVEMENT_COST
from map_data import hex_neighbor_positions


class UnitSkill(object):
    name = ""
    icon = "?"
    description = ""

    def can_move(self, model, unit):
        return True

    def can_attack(self, model, unit):
        return True

    def resolve_attack_target(self, model, unit, target_position):
        return target_position

    def prevents_counterattack(self, model, attacker, defender, target_position):
        return False

    def movement_cost(self, model, unit, terrain, base_cost):
        return base_cost

    def damage_multiplier(self, model, attacker, defender, city, damage_type, terrain):
        return 1.0

    def incoming_damage_multiplier(self, model, unit, attacker, damage_type, terrain):
        return 1.0

    def on_kill(self, model, unit):
        return []


class InfantryTerrainSkill(UnitSkill):
    name = "Terrain training"
    icon = "I"
    description = "Infantry uses Plain movement cost on land terrain."

    def movement_cost(self, model, unit, terrain, base_cost):
        if not unit.embarked and terrain != "Water":
            return TERRAIN_MOVEMENT_COST["Plain"]
        return base_cost


class TankMomentumSkill(UnitSkill):
    name = "Momentum"
    icon = "T"
    description = "Destroying an enemy unit restores this turn's attack."

    def on_kill(self, model, unit):
        unit.attacks_left = max(unit.attacks_left, unit.attacks_per_turn)
        return ["{} can attack again after the kill.".format(unit.kind)]


class ArtillerySuppressionSkill(UnitSkill):
    name = "Suppressive fire"
    icon = "A"
    description = "Units hit by artillery cannot counterattack."

    def prevents_counterattack(self, model, attacker, defender, target_position):
        return defender is not None


UNIT_SKILLS = {
    "Infantry": (InfantryTerrainSkill(),),
    "Tank": (TankMomentumSkill(),),
    "Artillery": (ArtillerySuppressionSkill(),),
}


class UnitStatus(object):
    name = ""
    icon = "?"
    description = ""
    attack_multiplier = 1.0
    morale_level = None
    tactical = False

    def can_move(self, model, unit):
        return True

    def can_attack(self, model, unit):
        return True

    def resolve_attack_target(self, model, unit, target_position):
        return target_position

    def prevents_counterattack(self, model, attacker, defender, target_position):
        return False

    def movement_cost(self, model, unit, terrain, base_cost):
        return base_cost

    def damage_multiplier(self, model, attacker, defender, city, damage_type, terrain):
        return 1.0

    def incoming_damage_multiplier(self, model, unit, attacker, damage_type, terrain):
        return 1.0

    def advance_round(self):
        return True


class MoraleBoost(UnitStatus):
    name = "High morale"
    icon = "+"
    description = "A kill has a 33% chance to grant +25% attack for 3 rounds."
    attack_multiplier = 1.25
    morale_level = 1

    def __init__(self):
        self.rounds_left = 3

    def advance_round(self):
        self.rounds_left -= 1
        return self.rounds_left > 0


class FlankedMorale(UnitStatus):
    name = "Flanked"
    icon = "!"
    description = "Two opposing units on opposite sides reduce attack by 25%."
    attack_multiplier = 0.75
    morale_level = -1
    tactical = True

    def applies(self, model, unit, units_by_position=None):
        return _has_opposite_hostiles(model, unit, units_by_position)


class SurroundedMorale(UnitStatus):
    name = "Surrounded"
    icon = "X"
    description = "Opposing units in all six neighboring hexes reduce attack by 50%."
    attack_multiplier = 0.5
    morale_level = -2
    tactical = True

    def applies(self, model, unit, units_by_position=None):
        positions = hex_neighbor_positions(unit.position)
        return (all(position in model.tiles for position in positions) and
                all(_is_hostile_unit(model, unit, position, units_by_position)
                    for position in positions))


TACTICAL_STATUSES = (SurroundedMorale, FlankedMorale)


def get_unit_skills(unit_or_kind):
    kind = unit_or_kind if isinstance(unit_or_kind, str) else unit_or_kind.kind
    return UNIT_SKILLS.get(kind, ())


def get_unit_statuses(unit):
    return tuple(unit.statuses)


def attack_multiplier_for(unit):
    result = 1.0
    morale_level = 0
    for status in unit.statuses:
        if status.morale_level is None:
            result *= status.attack_multiplier
        else:
            morale_level += status.morale_level
    if morale_level:
        result *= 1.0 + 0.25 * morale_level
    return result


def morale_level_for(unit):
    return sum(status.morale_level for status in unit.statuses
               if status.morale_level is not None)


def unit_can_move(model, unit):
    return all(effect.can_move(model, unit)
               for effect in get_unit_skills(unit) + get_unit_statuses(unit))


def unit_can_attack(model, unit):
    return all(effect.can_attack(model, unit)
               for effect in get_unit_skills(unit) + get_unit_statuses(unit))


def resolve_attack_target(model, unit, target_position):
    for effect in get_unit_skills(unit) + get_unit_statuses(unit):
        target_position = effect.resolve_attack_target(model, unit, target_position)
    return target_position


def prevents_counterattack(model, attacker, defender, target_position):
    return any(effect.prevents_counterattack(
        model, attacker, defender, target_position)
        for effect in get_unit_skills(attacker) + get_unit_statuses(attacker))


def movement_cost_for(model, unit, terrain, base_cost):
    result = base_cost
    for effect in get_unit_skills(unit) + get_unit_statuses(unit):
        result = effect.movement_cost(model, unit, terrain, result)
    return result


def damage_multiplier_for(model, attacker, defender, city, damage_type, terrain):
    result = 1.0
    for effect in get_unit_skills(attacker) + get_unit_statuses(attacker):
        result *= effect.damage_multiplier(
            model, attacker, defender, city, damage_type, terrain)
    return result


def incoming_damage_multiplier_for(model, unit, attacker, damage_type, terrain):
    result = 1.0
    for effect in get_unit_skills(unit) + get_unit_statuses(unit):
        result *= effect.incoming_damage_multiplier(
            model, unit, attacker, damage_type, terrain)
    return result


def process_kill(model, unit):
    events = []
    for skill in get_unit_skills(unit):
        events.extend(skill.on_kill(model, unit))
    if random.random() < 0.33:
        existing = next((status for status in unit.statuses
                         if isinstance(status, MoraleBoost)), None)
        if existing:
            existing.rounds_left = 3
        else:
            unit.statuses.append(MoraleBoost())
        events.append("{} gained high morale: attack increased for 3 rounds.".format(
            unit.kind))
    return events


def refresh_tactical_statuses(model):
    units_by_position = getattr(model, "units_by_position", None)
    if units_by_position is None:
        units_by_position = {unit.position: unit for unit in model.units}
    for unit in model.units:
        unit.statuses = [status for status in unit.statuses if not status.tactical]
        for status_type in TACTICAL_STATUSES:
            status = status_type()
            if status.applies(model, unit, units_by_position):
                unit.statuses.append(status)
                break


def advance_statuses(model):
    for unit in model.units:
        unit.statuses = [status for status in unit.statuses if status.advance_round()]
    refresh_tactical_statuses(model)


def _is_hostile_unit(model, unit, position, units_by_position=None):
    other = (units_by_position.get(position) if units_by_position is not None
             else model.unit_at(position))
    return bool(other and other.faction not in (unit.faction, NEUTRAL))


def _has_opposite_hostiles(model, unit, units_by_position=None):
    positions = hex_neighbor_positions(unit.position)
    return any(_is_hostile_unit(model, unit, positions[first], units_by_position) and
               _is_hostile_unit(model, unit, positions[second], units_by_position)
               for first, second in ((0, 1), (2, 5), (3, 4)))
