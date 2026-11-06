PLAYER = "player"
ENEMY = "enemy"
NEUTRAL = "neutral"

UNIT_TYPES = {
    "Infantry": {
        "cost": {"money": 80, "steel": 5, "technology": 0},
        "attack": 15, 
        "range": 1, 
        "hp": 80, 
        "movement": 6, 
        "mark": "I",
    },
    "Tank": {
        "cost": {"money": 160, "steel": 35, "technology": 5},
        "attack": 20, 
        "range": 1, 
        "hp": 150, 
        "movement": 5, 
        "mark": "T",
    },
    "Artillery": {
        "cost": {"money": 120, "steel": 15, "technology": 10},
        "attack": 22, 
        "range": 2, 
        "hp": 90, 
        "movement": 4, 
        "mark": "A",
    },
}

TRANSPORT_STATS = {
    "attack": 10, 
    "range": 1,   
    "movement": 4,   
    "mark": "S",
}

TERRAIN_COLORS = {
    "Plain": "#d9dfc9",
    "Forest": "#a9bda0",
    "Hill": "#c8bd91",
    "Water": "#b6d0d0",
}

TERRAIN_MOVEMENT_COST = {
    "Plain": 1,   
    "Forest": 3,   
    "Hill": 3,   
    "Water": 1, 
}

DEFENSIVE_TERRAINS = ("Hill", "Forest")
TERRAIN_DEFENSE_BONUS = 0  
MIN_DAMAGE = 1 
DAMAGE_RANDOM_BONUS = (-0.15, 0.15)  

CITY_PRODUCTION_PER_LEVEL = {
    "money": 15,  
    "steel": 3,   
    "technology": 1,  
}
CITY_BASE_HP = 150   
CITY_HP_PER_LEVEL = 30   
CITY_MAX_HP = 300  
CITY_MAX_LEVEL = 6   
CITY_HEAL_PER_TURN = 12  


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)
