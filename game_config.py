PLAYER = "player"
ENEMY = "enemy"
NEUTRAL = "neutral"

UNIT_TYPES = {
    "Infantry": {
        "cost": {"money": 80, "steel": 5, "technology": 0},  # 招募所需的金钱、钢材、科技
        "attack": 15,  # 基础攻击力
        "range": 1,  # 攻击距离（六角格）
        "hp": 80,  # 初始及最大生命值
        "movement": 6,  # 每回合最大行动力
        "mark": "I",
    },
    "Tank": {
        "cost": {"money": 160, "steel": 35, "technology": 5},  # 招募所需的金钱、钢材、科技
        "attack": 20,  # 基础攻击力
        "range": 1,  # 攻击距离（六角格）
        "hp": 150,  # 初始及最大生命值
        "movement": 5,  # 每回合最大行动力
        "mark": "T",
    },
    "Artillery": {
        "cost": {"money": 120, "steel": 15, "technology": 10},  # 招募所需的金钱、钢材、科技
        "attack": 22,  # 基础攻击力
        "range": 2,  # 攻击距离（六角格）
        "hp": 90,  # 初始及最大生命值
        "movement": 4,  # 每回合最大行动力
        "mark": "A",
    },
}

TRANSPORT_STATS = {
    "attack": 1,  # 登船运输状态下的攻击力
    "range": 1,  # 登船运输状态下的攻击距离（六角格）
    "movement": 4,  # 登船运输状态下的每回合最大行动力
    "mark": "S",
}

TERRAIN_COLORS = {
    "Plain": "#d9dfc9",
    "Forest": "#a9bda0",
    "Hill": "#c8bd91",
    "Water": "#b6d0d0",
}

TERRAIN_MOVEMENT_COST = {
    "Plain": 1,  # 进入平原消耗的行动力
    "Forest": 3,  # 进入森林消耗的行动力（步兵另有地形技能）
    "Hill": 3,  # 进入丘陵消耗的行动力（步兵另有地形技能）
    "Water": 1,  # 水域内移动每格消耗的行动力
}

DEFENSIVE_TERRAINS = ("Hill", "Forest")
TERRAIN_DEFENSE_BONUS = 0  # 防守方位于防御地形时减少的伤害
MIN_DAMAGE = 1  # 单次攻击造成的最低伤害
DAMAGE_RANDOM_BONUS = (-0.15, 0.15)  # 主动攻击和反击的随机伤害浮动比例（-15% 至 +15%）

CITY_PRODUCTION_PER_LEVEL = {
    "money": 15,  # 每级城市等级提供的每回合金钱
    "steel": 3,  # 每级工业等级提供的每回合钢材
    "technology": 1,  # 每级科技等级提供的每回合科技
}
CITY_BASE_HP = 100  # 1 级城市的基础生命值
CITY_HP_PER_LEVEL = 40  # 城市等级每提高一级增加的生命值
CITY_MAX_HP = 300  # 城市生命值上限
CITY_MAX_LEVEL = 6  # 城市、工业、科技等级的最高等级
CITY_HEAL_PER_TURN = 12  # 城内驻军每回合恢复的生命值


def city_hp_for_level(level):
    return min(CITY_MAX_HP, CITY_BASE_HP + (level - 1) * CITY_HP_PER_LEVEL)
