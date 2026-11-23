# -*- coding: gbk -*-
import json
import re
import tkinter as tk
import weakref

from app_paths import application_path
from game_config import UNIT_TYPES


LANGUAGES = {"en": "English", "zh": "简体中文"}
CURRENT_LANGUAGE = "zh"
_LOCALIZED_VARIABLES = []

TRANSLATIONS = {
    "Steel Dominion | Hex Campaign": "钢铁霸权 | 六角战役",
    "Steel Dominion | Map Editor": "钢铁霸权 | 地图编辑器",
    "STEEL DOMINION": "钢铁霸权",
    "STEEL DOMINION  /  MAP EDITOR": "钢铁霸权  /  地图编辑器",
    "Hex Campaign": "六角战役",
    "Enter campaign": "进入战役",
    "Edit map": "编辑地图",
    "No unit selected": "未选择单位",
    "Apply unit": "应用单位修改",
    "Delete unit": "删除单位",
    "Erase layer": "擦除对象",
    "No starting unit on this hex.": "此地块没有起始单位。",
    "No city on this hex.": "此地块没有城市。",
    "No river edge on this hex.": "此地块没有河流边。",
    "Terrain is already Plain.": "此地块已经是平原。",
    "Select a deployed unit first.": "请先选择已部署的单位。",
    "Starting unit updated.": "已更新起始单位。",
    "Starting unit deleted.": "已删除起始单位。",
    "Starting unit erased.": "已擦除起始单位。",
    "River edge erased.": "已擦除河流边界。",
    "Terrain erased.": "已擦除地形。",
    "Territory assignment erased.": "已擦除疆域分配。",
    "Nothing to erase here.": "此处没有可擦除对象。",
    "{} deleted; its land territory was reassigned.": "{} 已删除，其所属疆域已重新分配。",
    "{} city/cities, {} unit(s), and {} country/countries will be removed. Continue?": "将删除 {} 座城市、{} 个单位和 {} 个国家。是否继续？",
    "The resized map must retain cities for both player and enemy factions.": "缩小后的地图必须保留玩家和敌对阵营的城市。",
    "Map resized to {} x {}. Removed {} city/cities and {} unit(s) outside the new size.": "地图已调整为 {} x {}，已删除界外 {} 座城市和 {} 个单位。",
    "Back to main menu": "返回主菜单",
    "Settings": "设置",
    "Auto": "自动行动",
    "Auto...": "自动行动中…",
    "Auto done": "自动行动完成",
    "Auto failed": "自动行动失败",
    "End turn  >": "结束回合  >",
    "CAMPAIGN MAPS": "战役地图",
    "Default Map": "默认地图",
    "Eu": "欧洲",
    "Eu2": "欧洲 2",
    "Load save": "读取存档",
    "Replace saved campaign?": "覆盖现有存档？",
    "Starting here will overwrite this map's saved game.": "开始新战役将覆盖此地图的存档。",
    "Cancel": "取消",
    "Overwrite and start": "覆盖并开始",
    "Choose country": "选择国家",
    "CONTROLLED CITIES": "控制的城市",
    "STARTING FORCE": "初始部队",
    "INCOME PER TURN": "每回合收入",
    "Combat profile": "战斗属性",
    "COMBAT PROFILE": "战斗属性",
    "UNIT / COST": "单位 / 费用",
    "ATTACK": "攻击",
    "RANGE": "射程",
    "HP": "生命",
    "MOVE": "移动",
    "Recruit": "招募",
    "Campaign settings": "战役设置",
    "CAMPAIGN DETAILS": "战役信息",
    "MAP": "地图",
    "TURN": "回合",
    "STATUS": "状态",
    "CITIES": "城市",
    "Campaign setup": "战役准备",
    "Player turn": "玩家回合",
    "AI turn": "AI 回合",
    "Campaign complete": "战役结束",
    "Resource account": "资源账户",
    "Debug mode": "调试模式",
    "Choose map": "选择地图",
    "Restart campaign": "重新开始战役",
    "Exit": "退出到选国",
    "Attack target": "攻击目标",
    "Clear target": "清除目标",
    "FIELD REPORT": "战场记录",
    "MAP EDITOR": "地图编辑器",
    "MAP FILE": "地图文件",
    "New blank map": "新建空白地图",
    "Open map...": "打开地图...",
    "Save map...": "保存地图...",
    "SIZE": "尺寸",
    "Columns": "列数",
    "Rows": "行数",
    "Apply size": "应用尺寸",
    "Edit": "编辑",
    "Countries": "国家",
    "Terrain": "地形",
    "City": "城市",
    "Territory": "领土",
    "River": "河流",
    "Unit": "单位",
    "Erase": "擦除",
    "City name": "城市名称",
    "City country": "所属国家",
    "City level": "城市等级",
    "Industry level": "工业等级",
    "Research level": "科技等级",
    "Apply city": "应用城市设置",
    "Delete city": "删除城市",
    "Paint hexes for city": "为城市绘制地块",
    "Starting unit country": "初始单位所属国家",
    "COUNTRY SETTINGS": "国家设置",
    "Name": "名称",
    "Faction": "阵营",
    "Country color (HSB)": "国家颜色 (HSB)",
    "Add": "添加",
    "Apply": "应用",
    "Remove": "移除",
    "Choose a tool, then click map hexes.": "选择工具，然后点击地图六角格。",
    "Choose your country, then start the campaign.": "选择国家以开始战役。",
    "Choose a country to continue.": "选择国家以继续。",
    "Hex selected.": "已选择地块。",
    "Select one of your units.": "请选择己方单位。",
    "Target cleared.": "已清除目标。",
    "Last movement withdrawn.": "已撤回上一步移动。",
    "AI forces are taking their turn...": "AI 正在行动...",
    "AI is taking actions for this turn...": "AI 正在代你行动...",
    "AI actions complete.": "自动行动完成。",
    "AI turn failed: {}": "AI 回合失败：{}",
    "AI actions failed: {}": "自动行动失败：{}",
    "Enemy turn complete.": "敌方回合结束。",
    "Victory: all opposing cities have been captured.": "胜利：已占领所有敌方城市。",
    "Defeat: all of your faction's cities have fallen.": "失败：己方阵营的城市已全部失守。",
    "Choose a country, then restart the campaign.": "选择国家以重新开始战役。",
    "No playable maps were found.": "没有找到可用地图。",
    "Select a playable map.": "请选择可用地图。",
    "This map cannot be played.\n{}": "此地图无法游玩。\n{}",
    "{} x {} hexes\n{} countries / {} cities\n{} starting units":
        "{} × {} 格\n{} 个国家 / {} 座城市\n{} 支初始部队",
    "Neutral units cannot be commanded or attacked.": "中立单位不能被指挥或攻击。",
    "Neutral units cannot be attacked.": "不能攻击中立单位。",
    "This unit cannot attack now.": "该单位目前无法攻击。",
    "Select a valid target.": "请选择有效目标。",
    "The target is out of range.": "目标超出攻击范围。",
    "Select an opposing unit or city as the target.": "请选择敌方单位或城市作为目标。",
    "The city must be empty to recruit a unit.": "城市内必须没有单位才能招募。",
    "You can only recruit from your own cities.": "只能从己方城市招募。",
    "The campaign must be started before recruiting units.": "开始战役后才能招募单位。",
    "Recruitment is available during the player turn.": "只能在玩家回合招募。",
    "Insufficient resources: {}.": "资源不足：{}。",
    "Ready to deploy at {}.": "可在{}部署。",
    "Start the campaign before recruiting units.": "开始战役后才能招募单位。",
    "You must start the move with full movement points to embark or land.":
        "登船或登陆必须从满移动力状态开始移动。",
    "Unable to load map": "无法加载地图",
    "Loaded saved campaign: {}.": "已读取存档：{}。",
    "Unable to load saved campaign: {}": "无法读取存档：{}",
    "Unable to load map": "无法加载地图",
    "loaded. Choose a country, then start the campaign.": "已加载。选择国家以开始战役。",
}

TRANSLATIONS.update({
    "Language": "\u8bed\u8a00",
    "P/E $ {} / {} S {} / {} T {} / {}":
        "\u6536\u5165 \u73a9/\u654c \u8d44 {} / {} \u94a2 {} / {} \u79d1 {} / {}",
    "HP P/E {} / {}": "\u90e8\u961f\u603b\u751f\u547d \u73a9/\u654c {} / {}",
    "/turn": "/\u56de\u5408",
    "Overextended": "\u8fc7\u5ea6\u5ef6\u4f38",
    "Overextended movement temporarily reduces attack by 50%.": "\u8d85\u51fa\u57fa\u7840\u884c\u52a8\u8303\u56f4\u79fb\u52a8\u4f1a\u6682\u65f6\u964d\u4f4e 50% \u653b\u51fb\u529b\u3002",
    "Turn {} begins. Income: +{} money, +{} steel, +{} technology; maintenance: -{} money, -{} steel, -{} technology.":
        "\u7b2c {} \u56de\u5408\u5f00\u59cb\u3002\u6536\u5165\uff1a+{} \u8d44\u91d1\u3001+{} \u94a2\u94c1\u3001+{} \u79d1\u6280\uff1b\u7ef4\u62a4\u8d39\uff1a-{} \u8d44\u91d1\u3001-{} \u94a2\u94c1\u3001-{} \u79d1\u6280\u3002",
    "Full AI control": "\u5168 AI \u63a7\u5236",
    "Pause": "\u6682\u505c",
    "Continue": "\u7ee7\u7eed",
    "Pausing...": "\u6b63\u5728\u6682\u505c...",
    "Exit full AI": "\u9000\u51fa\u5168 AI \u63a7\u5236",
    "Full AI control started.": "\u5168 AI \u63a7\u5236\u5df2\u542f\u52a8\u3002",
    "Full AI control will pause after this round.": "\u672c\u56de\u5408\u7ed3\u675f\u540e\u6682\u505c\u5168 AI \u63a7\u5236\u3002",
    "Full AI control paused.": "\u5168 AI \u63a7\u5236\u5df2\u6682\u505c\u3002",
    "Full AI control resumed.": "\u5168 AI \u63a7\u5236\u5df2\u7ee7\u7eed\u3002",
    "Full AI control will stop after current AI actions.": "\u5f53\u524d AI \u884c\u52a8\u7ed3\u675f\u540e\u9000\u51fa\u5168 AI \u63a7\u5236\u3002",
    "Full AI control stopped.": "\u5df2\u9000\u51fa\u5168 AI \u63a7\u5236\u3002",
    "Confirm": "\u786e\u5b9a",
    "Player faction cities: {}": "\u73a9\u5bb6\u9635\u8425\u57ce\u5e02\uff1a{}",
    "Enemy faction cities: {}": "\u654c\u65b9\u9635\u8425\u57ce\u5e02\uff1a{}",
    "Final turn: {}": "\u6700\u7ec8\u56de\u5408\uff1a{}",
    "Surviving units: {} / {}": "\u5b58\u6d3b\u90e8\u961f\uff1a{} / {}",
    "EU2 full AI results: {} games / Player {} wins / Enemy {} wins": "EU2 \u5168 AI \u6218\u5f79\u7edf\u8ba1\uff1a{} \u5c40 / \u73a9\u5bb6\u65b9\u80dc {} \u5c40 / \u654c\u65b9\u80dc {} \u5c40",
    "Unable to delete campaign save: {}": "\u65e0\u6cd5\u5220\u9664\u6218\u5f79\u5b58\u6863\uff1a{}",
    "MONEY": "\u8d44\u91d1",
    "STEEL": "\u94a2\u94c1",
    "TECH": "\u79d1\u6280",
    "Money": "\u8d44\u91d1",
    "Steel": "\u94a2\u94c1",
    "Technology": "\u79d1\u6280",
    "Industry": "\u5de5\u4e1a",
    "Research": "\u79d1\u6280",
    "+{}/turn": "+{}/\u56de\u5408",
    "Steel Dominion map": "Steel Dominion \u5730\u56fe",
    "All files": "\u6240\u6709\u6587\u4ef6",
    "Recruit units": "\u62db\u52df\u5355\u4f4d",
    "EU": "\u6b27\u6d32",
    "EU2": "\u6b27\u6d32 2",
    "Recruit {}": "\u62db\u52df{}",
    "Infantry": "\u6b65\u5175",
    "Tank": "\u5766\u514b",
    "Artillery": "\u706b\u70ae",
    "Plain": "\u5e73\u539f",
    "Forest": "\u68ee\u6797",
    "Hill": "\u4e18\u9675",
    "Desert": "\u6c99\u6f20",
    "Water": "\u6c34\u57df",
    "player": "\u73a9\u5bb6",
    "enemy": "\u654c\u65b9",
    "Player": "\u73a9\u5bb6",
    "Enemy": "\u654c\u65b9",
    "Unassigned (clear)": "\u672a\u5206\u914d\uff08\u6e05\u9664\uff09",
    "Player faction": "\u73a9\u5bb6\u9635\u8425",
    "Enemy faction": "\u654c\u65b9\u9635\u8425",
    "Neutral": "\u4e2d\u7acb",
    "Maximum HP: {}": "\u6700\u5927\u751f\u547d\u503c\uff1a{}",
    "{} / {} controlled": "\u5df2\u63a7\u5236 {} / {} \u5ea7\u57ce\u5e02",
    "{}  [{}]": "{}  [{}]",
    "{}  /  {} cities  /  {} starting units": "{}  /  {} \u5ea7\u57ce\u5e02  /  {} \u652f\u521d\u59cb\u90e8\u961f",
    "{}  /  City Lv {}": "{}  /  \u57ce\u5e02 {} \u7ea7",
    "Cost  Money {}  /  Steel {}  /  Tech {}": "\u82b1\u8d39  \u8d44\u91d1 {}  /  \u94a2\u94c1 {}  /  \u79d1\u6280 {}",
    "STOCK {}": "\u5e93\u5b58 {}",
    "T{}  {}": "\u7b2c {} \u56de\u5408  {}",
    "Attack used; this unit is spent for the turn.": "\u672c\u56de\u5408\u653b\u51fb\u6b21\u6570\u5df2\u7528\u5b8c\uff0c\u8be5\u5355\u4f4d\u672c\u56de\u5408\u5df2\u8017\u5c3d\u3002",
    "{} MP and {}/{} attack available; red outlines mark targets in range.": "\u5269\u4f59 {} \u79fb\u52a8\u529b\uff0c\u653b\u51fb {}/{} \u6b21\u53ef\u7528\uff1b\u7ea2\u8272\u8f6e\u5ed3\u4e3a\u53ef\u653b\u51fb\u76ee\u6807\u3002",
    "0 MP; {}/{} attack available. Red outlines mark targets in range.": "\u79fb\u52a8\u529b\u4e3a 0\uff0c\u653b\u51fb {}/{} \u6b21\u53ef\u7528\u3002\u7ea2\u8272\u8f6e\u5ed3\u4e3a\u53ef\u653b\u51fb\u76ee\u6807\u3002",
    "Selected {}. {}": "\u5df2\u9009\u62e9 {}\u3002{}",
    "{}: select a unit or recruit here.": "{}\uff1a\u9009\u62e9\u5355\u4f4d\u6216\u5728\u6b64\u5904\u62db\u52df\u3002",
    "Campaign victory": "\u6218\u5f79\u80dc\u5229",
    "Campaign lost": "\u6218\u5f79\u5931\u8d25",
    "{} as a transport; movement exhausted for this turn.": "{} \u5df2\u88c5\u8f7d\u4e3a\u8fd0\u8f93\u8239\uff0c\u672c\u56de\u5408\u79fb\u52a8\u529b\u8017\u5c3d\u3002",
    "Crossed a river; movement exhausted for this turn.": "\u6e21\u8fc7\u6cb3\u6d41\uff0c\u672c\u56de\u5408\u79fb\u52a8\u529b\u8017\u5c3d\u3002",
    "{} took {} damage.": "{} \u53d7\u5230 {} \u70b9\u4f24\u5bb3\u3002",
    "{} city HP: {}/{} (-{}).": "{} \u57ce\u5e02\u751f\u547d\u503c\uff1a{}/{}\uff08-{}\uff09\u3002",
    "{} {} was destroyed.": "{} {} \u5df2\u88ab\u6467\u6bc1\u3002",
    "{} retained movement after a kill.": "{} \u51fb\u6740\u76ee\u6807\u540e\u4fdd\u7559\u79fb\u52a8\u529b\u3002",
    "{} {} was destroyed by a counterattack.": "{} {} \u88ab\u53cd\u51fb\u6467\u6bc1\u3002",
    "{} captured {}.": "{} \u5360\u9886\u4e86 {}\u3002",
    "{} recruited in {}.": "{} \u5df2\u5728 {} \u62db\u52df\u3002",
    "Turn {} begins. Income: +{} money, +{} steel, +{} technology; maintenance: -{} money.": "\u7b2c {} \u56de\u5408\u5f00\u59cb\u3002\u6536\u5165\uff1a+{} \u8d44\u91d1\u3001+{} \u94a2\u94c1\u3001+{} \u79d1\u6280\uff1b\u7ef4\u62a4\u8d39\uff1a-{} \u8d44\u91d1\u3002",
    "Terrain training": "\u5730\u5f62\u8bad\u7ec3",
    "Uses configured terrain movement cost on land.": "\u5728\u9646\u5730\u4e0a\u4f7f\u7528\u914d\u7f6e\u7684\u5730\u5f62\u79fb\u52a8\u6d88\u8017\u3002",
    "Momentum": "\u52bf\u4e0d\u53ef\u6321",
    "A kill preserves remaining movement and restores this turn's attack.": "\u51fb\u6740\u654c\u65b9\u5355\u4f4d\u540e\u4fdd\u7559\u5269\u4f59\u79fb\u52a8\u529b\uff0c\u5e76\u6062\u590d\u672c\u56de\u5408\u653b\u51fb\u6b21\u6570\u3002",
    "Suppressive fire": "\u538b\u5236\u5c04\u51fb",
    "Units hit by artillery cannot counterattack.": "\u88ab\u706b\u70ae\u51fb\u4e2d\u7684\u5355\u4f4d\u65e0\u6cd5\u53cd\u51fb\u3002",
    "Category bonus": "\u7c7b\u522b\u589e\u4f24",
    "{}% bonus damage against {} units.": "\u5bf9 {1} \u5355\u4f4d\u9020\u6210 {0}% \u989d\u5916\u4f24\u5bb3\u3002",
    "infantry": "\u6b65\u5175",
    "armor": "\u88c5\u7532",
    "artillery": "\u706b\u70ae",
    "ship": "\u8239\u53ea",
    "High morale": "\u58eb\u6c14\u9ad8\u6602",
    "A kill has a 33% chance to grant +25% attack for 3 rounds.": "\u51fb\u6740\u654c\u65b9\u5355\u4f4d\u65f6\uff0c\u6709 33% \u51e0\u7387\u83b7\u5f97\u653b\u51fb\u529b +25%\uff0c\u6301\u7eed 3 \u56de\u5408\u3002",
    "Flanked": "\u4fa7\u7ffc\u53d7\u654c",
    "Two opposing units on opposite sides reduce attack by 25%.": "\u76f8\u5bf9\u65b9\u5411\u7684\u4e24\u4e2a\u654c\u65b9\u5355\u4f4d\u4f1a\u4f7f\u653b\u51fb\u529b\u964d\u4f4e 25%\u3002",
    "Surrounded": "\u88ab\u5305\u56f4",
    "Opposing units in all six neighboring hexes reduce attack by 50%.": "\u516d\u4e2a\u76f8\u90bb\u5730\u5757\u5747\u6709\u654c\u65b9\u5355\u4f4d\u65f6\uff0c\u653b\u51fb\u529b\u964d\u4f4e 50%\u3002",
    "Sea hexes do not belong to a city.": "\u6d77\u6d0b\u5730\u5757\u4e0d\u5c5e\u4e8e\u57ce\u5e02\u3002",
    "Hex {}, {} is now unassigned.": "\u5730\u5757 {}, {} \u5df2\u53d6\u6d88\u5f52\u5c5e\u3002",
    "Hex {}, {} assigned to {}.": "\u5730\u5757 {}, {} \u5df2\u5206\u914d\u7ed9 {}\u3002",
    "Select a hex for the city first.": "\u8bf7\u5148\u4e3a\u57ce\u5e02\u9009\u62e9\u5730\u5757\u3002",
    "City, industry, and research levels must be whole numbers.": "\u57ce\u5e02\u3001\u5de5\u4e1a\u548c\u79d1\u6280\u7b49\u7ea7\u5fc5\u987b\u4e3a\u6574\u6570\u3002",
    "{} city updated.": "\u57ce\u5e02 {} \u5df2\u66f4\u65b0\u3002",
    "{} deleted; its land territory is unassigned.": "\u57ce\u5e02 {} \u5df2\u5220\u9664\uff0c\u5176\u9886\u571f\u5df2\u53d6\u6d88\u5f52\u5c5e\u3002",
    "Select a city to delete.": "\u8bf7\u9009\u62e9\u8981\u5220\u9664\u7684\u57ce\u5e02\u3002",
    "Choose a neighboring land hex to complete the river edge.": "\u8bf7\u9009\u62e9\u76f8\u90bb\u7684\u9646\u5730\u5730\u5757\u4ee5\u5b8c\u6210\u6cb3\u6d41\u8fb9\u7f18\u3002",
    "River endpoints must be neighboring hexes.": "\u6cb3\u6d41\u4e24\u7aef\u5fc5\u987b\u662f\u76f8\u90bb\u5730\u5757\u3002",
    "Rivers can only be drawn between land hexes.": "\u6cb3\u6d41\u53ea\u80fd\u7ed8\u5236\u5728\u9646\u5730\u5730\u5757\u4e4b\u95f4\u3002",
    "River edge removed.": "\u6cb3\u6d41\u8fb9\u7f18\u5df2\u79fb\u9664\u3002",
    "River edge added.": "\u6cb3\u6d41\u8fb9\u7f18\u5df2\u6dfb\u52a0\u3002",
    "{} added. Assign it at least one city before starting a game.": "\u5df2\u6dfb\u52a0 {}\u3002\u5f00\u59cb\u6e38\u620f\u524d\u8bf7\u4e3a\u5176\u5206\u914d\u81f3\u5c11\u4e00\u5ea7\u57ce\u5e02\u3002",
    "Select a country first.": "\u8bf7\u5148\u9009\u62e9\u56fd\u5bb6\u3002",
    "Country names must contain 1 to 30 characters.": "\u56fd\u5bb6\u540d\u79f0\u5fc5\u987b\u5305\u542b 1 \u5230 30 \u4e2a\u5b57\u7b26\u3002",
    "Country names must be unique.": "\u56fd\u5bb6\u540d\u79f0\u4e0d\u80fd\u91cd\u590d\u3002",
    "Resource balances must be whole numbers.": "\u8d44\u6e90\u6570\u91cf\u5fc5\u987b\u4e3a\u6574\u6570\u3002",
    "Resource balances must be from 0 to 999999.": "\u8d44\u6e90\u6570\u91cf\u5fc5\u987b\u5728 0 \u5230 999999 \u4e4b\u95f4\u3002",
    "{} country settings updated.": "\u56fd\u5bb6 {} \u8bbe\u7f6e\u5df2\u66f4\u65b0\u3002",
    "Move or erase this country's cities before removing it.": "\u79fb\u52a8\u6216\u64e6\u9664\u8be5\u56fd\u5bb6\u7684\u57ce\u5e02\u540e\u624d\u80fd\u79fb\u9664\u5b83\u3002",
    "{} removed.": "{} \u5df2\u79fb\u9664\u3002",
    "Zoom in to edit hexes.": "\u8bf7\u653e\u5927\u5730\u56fe\u540e\u7f16\u8f91\u5730\u5757\u3002",
    "Cities and units cannot be placed on water. Move or erase them first.": "\u57ce\u5e02\u548c\u5355\u4f4d\u4e0d\u80fd\u653e\u5728\u6c34\u57df\u3002\u8bf7\u5148\u79fb\u52a8\u6216\u64e6\u9664\u5b83\u4eec\u3002",
    "{} set at hex {}, {}.": "\u5df2\u5728\u5730\u5757 {}, {} \u8bbe\u7f6e {}\u3002",
    "{} selected. Edit its fields and apply, or delete it.": "\u5df2\u9009\u62e9 {}\u3002\u7f16\u8f91\u5e76\u5e94\u7528\u5b57\u6bb5\uff0c\u6216\u5220\u9664\u5b83\u3002",
    "Hex {}, {} selected. Set city properties and apply to place.": "\u5df2\u9009\u62e9\u5730\u5757 {}, {}\u3002\u8bbe\u7f6e\u57ce\u5e02\u5c5e\u6027\u5e76\u5e94\u7528\u4ee5\u653e\u7f6e\u3002",
    "Add a country before placing starting units.": "\u653e\u7f6e\u521d\u59cb\u5355\u4f4d\u524d\u8bf7\u5148\u6dfb\u52a0\u56fd\u5bb6\u3002",
    "Starting units cannot be placed on water.": "\u521d\u59cb\u5355\u4f4d\u4e0d\u80fd\u653e\u7f6e\u5728\u6c34\u57df\u3002",
    "{} assigned to {} at hex {}, {}.": "\u5df2\u5c06 {} \u5206\u914d\u7ed9 {}\uff0c\u4f4d\u4e8e\u5730\u5757 {}, {}\u3002",
    "Hex {}, {} cleared.": "\u5730\u5757 {}, {} \u5df2\u6e05\u9664\u3002",
    "Blank {} x {} map created.": "\u5df2\u521b\u5efa {} × {} \u7a7a\u767d\u5730\u56fe\u3002",
    "Map resized to {} x {}.": "\u5730\u56fe\u5df2\u8c03\u6574\u4e3a {} × {}\u3002",
    "Map opened: {} x {}, {} cities.": "\u5df2\u6253\u5f00\u5730\u56fe\uff1a{} × {}\uff0c{} \u5ea7\u57ce\u5e02\u3002",
    "Map saved to {}.": "\u5730\u56fe\u5df2\u4fdd\u5b58\u5230 {}\u3002",
    "Discard the current map and create a blank one?": "\u653e\u5f03\u5f53\u524d\u5730\u56fe\u5e76\u521b\u5efa\u7a7a\u767d\u5730\u56fe\u5417\uff1f",
    "New map": "\u65b0\u5efa\u5730\u56fe",
    "Invalid map size": "\u5730\u56fe\u5c3a\u5bf8\u65e0\u6548",
    "Open map": "\u6253\u5f00\u5730\u56fe",
    "Save map": "\u4fdd\u5b58\u5730\u56fe",
    "Resize map": "\u8c03\u6574\u5730\u56fe\u5c3a\u5bf8",
    "{} city/cities and {} unit(s) outside the new size will be removed. Continue?": "\u65b0\u5c3a\u5bf8\u5916\u7684 {} \u5ea7\u57ce\u5e02\u548c {} \u4e2a\u5355\u4f4d\u5c06\u88ab\u5220\u9664\u3002\u7ee7\u7eed\u5417\uff1f"
})


_REVERSE_TRANSLATIONS = dict((translated, source)
                             for source, translated in TRANSLATIONS.items())


def set_language(language):
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = language if language in LANGUAGES else "en"
    live_variables = []
    for variable_ref in _LOCALIZED_VARIABLES:
        variable = variable_ref()
        if variable is None:
            continue
        try:
            variable.set_language(CURRENT_LANGUAGE)
        except tk.TclError:
            continue
        live_variables.append(variable_ref)
    _LOCALIZED_VARIABLES[:] = live_variables


def load_language():
    try:
        with open(application_path("config.json"), "r") as config_file:
            config = json.load(config_file)
    except (IOError, OSError, ValueError, TypeError):
        return CURRENT_LANGUAGE
    language = config.get("language", CURRENT_LANGUAGE)
    return language if language in LANGUAGES else CURRENT_LANGUAGE


def save_language(language):
    path = application_path("config.json")
    try:
        with open(path, "r") as config_file:
            config = json.load(config_file)
    except (IOError, OSError):
        config = {}
    except (ValueError, TypeError):
        return
    if not isinstance(config, dict):
        return
    config["language"] = language
    try:
        with open(path, "w") as config_file:
            json.dump(config, config_file, indent=2, sort_keys=True)
            config_file.write("\n")
    except (IOError, OSError):
        pass


def translate(text, language=None):
    language = language or CURRENT_LANGUAGE
    if not isinstance(text, str):
        return text
    if language == "en":
        for unit_id, unit_data in UNIT_TYPES.items():
            if text in (unit_id, unit_data.get("name_en"),
                        unit_data.get("name_zh")):
                return unit_data["name_en"]
        return _REVERSE_TRANSLATIONS.get(text, text)
    for unit_id, unit_data in UNIT_TYPES.items():
        if text in (unit_id, unit_data.get("name_en"),
                    unit_data.get("name_zh")):
            return unit_data.get("name_zh", unit_data["name_en"])
    if text in TRANSLATIONS:
        return TRANSLATIONS[text]
    for source, translated in TRANSLATIONS.items():
        if "{}" in source:
            parts = source.split("{}")
            pattern = "^" + "(.*?)".join(re.escape(part) for part in parts) + "$"
            match = re.match(pattern, text, re.DOTALL)
            if match:
                try:
                    return translated.format(*(
                        translate(group, language) for group in match.groups()))
                except (IndexError, ValueError):
                    pass
    return text


class LocalizedStringVar(tk.StringVar):
    def __init__(self, value="", master=None):
        self.source_value = value
        tk.StringVar.__init__(self, master=master, value=translate(value))
        _LOCALIZED_VARIABLES.append(weakref.ref(self))

    def set(self, value):
        self.source_value = value
        tk.StringVar.set(self, translate(value))

    def set_language(self, language):
        tk.StringVar.set(self, translate(self.source_value, language))


def apply_language(widget, language=None):
    language = language or CURRENT_LANGUAGE
    try:
        if "text" in widget.keys():
            original = getattr(widget, "_language_original_text", None)
            if original is None:
                original = widget.cget("text")
                widget._language_original_text = original
            widget.configure(text=translate(original, language))
    except (AttributeError, TypeError):
        pass

    try:
        if widget.winfo_class() == "Listbox":
            original_items = getattr(widget, "_language_original_items", None)
            if original_items is None:
                original_items = [widget.get(index) for index in range(widget.size())]
                widget._language_original_items = original_items
            selected = widget.curselection()
            widget.delete(0, "end")
            for item in original_items:
                widget.insert("end", translate(item, language))
            for index in selected:
                widget.selection_set(index)
    except (AttributeError, TypeError):
        pass

    try:
        if widget.winfo_class() == "TNotebook":
            original_tabs = getattr(widget, "_language_original_tabs", {})
            for tab_id in widget.tabs():
                if tab_id not in original_tabs:
                    original_tabs[tab_id] = widget.tab(tab_id, "text")
                widget.tab(tab_id, text=translate(original_tabs[tab_id], language))
            widget._language_original_tabs = original_tabs
    except (AttributeError, TypeError):
        pass

    for child in widget.winfo_children():
        apply_language(child, language)
