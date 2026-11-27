import json
import math
import os
import tempfile
import tkinter as tk
from tkinter import ttk

from app_paths import application_path
from game_config import _load_config
from game_dialogs import _ModalDialog
from i18n import translate
from ui_helpers import ScrollableFrame


PAPER = "#e8e7df"
INK = "#202c27"
GREEN = "#47745f"
MUTED = "#768078"

CONFIG_CATEGORIES = {
    "Cities": (
        "city_base_hp", "city_heal_per_turn", "city_hp_per_level",
        "city_max_level", "city_production_per_level",
    ),
    "Combat": (
        "damage_random_bonus", "critical_hit_chance",
        "critical_hit_multiplier", "min_damage", "terrain_defense_bonus",
    ),
    "Economy": (
        "default_resources", "unit_maintenance_rate",
        "non_participant_income_multiplier",
    ),
    "Movement settings": (
        "movement_animation_duration", "forced_march_multiplier",
        "forced_march_unattacked_turns",
    ),
    "AI": (
        "enemy_ai_units_per_city_level", "player_ai_units_per_city_level",
    ),
    "Terrain": ("terrain_movement_cost",),
    "Transport": ("transport_stats",),
    "Unit level multipliers": ("unit_level_multipliers",),
}

CATEGORY_ORDER = tuple(CONFIG_CATEGORIES) + ("General",)

FIELD_LABELS = {
    "city_base_hp": "City base HP",
    "city_heal_per_turn": "City healing per turn",
    "city_hp_per_level": "City HP per level",
    "city_max_level": "Maximum city level",
    "city_production_per_level": "Production per city level",
    "damage_random_bonus": "Random damage range",
    "critical_hit_chance": "Critical hit chance",
    "critical_hit_multiplier": "Critical hit multiplier",
    "min_damage": "Minimum damage",
    "terrain_defense_bonus": "Terrain defense bonus",
    "default_resources": "Starting resources",
    "unit_maintenance_rate": "Unit maintenance rate",
    "non_participant_income_multiplier": "Non-participant income multiplier",
    "movement_animation_duration": "Movement animation duration",
    "forced_march_multiplier": "Forced march multiplier",
    "forced_march_unattacked_turns": "Forced march turns",
    "enemy_ai_units_per_city_level": "Enemy units per city level",
    "player_ai_units_per_city_level": "Player AI units per city level",
    "terrain_movement_cost": "Movement cost by terrain",
    "transport_stats": "Transport unit stats",
    "unit_level_multipliers": "Unit level multipliers",
    "attack": "Attack",
    "range": "Range",
    "hp": "HP",
    "movement": "Movement",
    "cost": "Cost",
    "money": "Money",
    "steel": "Steel",
    "technology": "Technology",
    "skills": "Skills",
    "bonus": "Bonus",
}

UNIT_TEXT_FIELDS = (
    ("name", "Unit name"),
    ("id", "Unit ID"),
    ("name_en", "English name"),
    ("name_zh", "Chinese name"),
    ("category", "Category"),
    ("symbol", "Map symbol"),
)

UNIT_DEFAULTS = {
    "category": "infantry",
    "cost": {"money": 80, "steel": 0, "technology": 0},
    "attack": 10,
    "range": 1,
    "hp": 50,
    "movement": 15,
    "skills": [],
}


def _numeric_values(value, path=()):
    if type(value) in (int, float):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            for item in _numeric_values(child, path + (key,)):
                yield item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for item in _numeric_values(child, path + (index,)):
                yield item


def _set_config_value(config, path, value):
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


class ConfigDatabaseDialog(_ModalDialog):
    def __init__(self, parent, language="en"):
        parent.update_idletasks()
        width = max(560, min(980, max(parent.winfo_width(), 640) - 32))
        height = max(380, min(720, max(parent.winfo_height(), 420) - 32))
        _ModalDialog.__init__(self, parent, "Database", width, height)
        self.language = language
        self.config_path = application_path("config.json")
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            self.config_data = json.load(config_file)
        self.field_vars = {}
        self.field_types = {}
        self.status_var = tk.StringVar(master=self, value="")

        self._build_header(
            self._tr("Database"), self._tr("Edit numeric config values."),
            eyebrow="CONFIGURATION DATABASE")
        self.scrollable = ScrollableFrame(self, canvas_bg="#f4f3ed")
        self.scrollable.pack(fill="both", expand=True, padx=12, pady=(10, 4))
        self._build_fields()

        footer = ttk.Frame(self, padding=(12, 6, 12, 10))
        footer.pack(fill="x")
        self.status_label = ttk.Label(
            footer, textvariable=self.status_var, foreground=MUTED,
            wraplength=max(180, width - 210))
        self.status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text=self._tr("Save changes"), command=self._save).pack(
            side="right", padx=(8, 0))
        ttk.Button(footer, text=self._tr("Close"), command=self.close).pack(
            side="right")
        self._show_modal()

    def _tr(self, text):
        return translate(text, self.language)

    def _build_fields(self):
        grouped_values = {}
        for path, value in _numeric_values(self.config_data):
            if path[0] == "unit_types":
                continue
            group = next((category for category, keys in CONFIG_CATEGORIES.items()
                          if path[0] in keys), "General")
            grouped_values.setdefault(group, []).append((path, value))

        content = self.scrollable.content
        content.columnconfigure(0, weight=1)
        for group_name in CATEGORY_ORDER:
            entries = grouped_values.get(group_name)
            if not entries:
                continue
            section = ttk.LabelFrame(
                content, text=self._tr(group_name), padding=(10, 7))
            section.pack(fill="x", expand=True, padx=8, pady=5)
            section.columnconfigure(0, weight=1)
            for row, (path, value) in enumerate(entries):
                ttk.Label(section, text=self._format_path(path)).grid(
                    row=row, column=0, sticky="w", padx=(2, 12), pady=3)
                variable = tk.StringVar(master=self, value=self._format_value(value))
                self.field_vars[path] = variable
                self.field_types[path] = type(value)
                ttk.Entry(section, textvariable=variable, width=14,
                          justify="right").grid(
                              row=row, column=1, sticky="e", padx=2, pady=3)
        self._build_unit_types(content)

    def _format_path(self, path):
        labels = []
        for part in path:
            if type(part) is int:
                labels.append(self._tr("Level {}".format(part + 1)))
            else:
                label = FIELD_LABELS.get(part, str(part).replace("_", " ").title())
                labels.append(self._tr(label))
        return " / ".join(labels)

    def _build_unit_types(self, parent):
        self.unit_types_section = ttk.LabelFrame(
            parent, text=self._tr("Unit types"), padding=(10, 7))
        self.unit_types_section.pack(fill="x", expand=True, padx=8, pady=5)
        self.unit_cards_host = ttk.Frame(self.unit_types_section)
        self.unit_cards_host.pack(fill="x", expand=True)
        ttk.Button(
            self.unit_types_section, text=self._tr("Add unit type"),
            command=self._add_unit_type).pack(anchor="e", pady=(7, 0))
        self._rebuild_unit_type_cards()

    def _rebuild_unit_type_cards(self):
        for child in self.unit_cards_host.winfo_children():
            child.destroy()
        self.unit_type_fields = []
        unit_types = self.config_data.get("unit_types", {})
        for unit_name, details in unit_types.items():
            self._build_unit_type_card(unit_name, details, len(unit_types))

    def _build_unit_type_card(self, unit_name, details, unit_count):
        display_name = (details.get("name_zh") if self.language == "zh" else
                        details.get("name_en", unit_name)) or unit_name
        title = "{} / {}".format(display_name, unit_name)
        card = ttk.LabelFrame(
            self.unit_cards_host, text=title, padding=(9, 6))
        card.pack(fill="x", expand=True, pady=4)
        card.columnconfigure(1, weight=1)

        text_vars = {}
        for row, (field, label) in enumerate(UNIT_TEXT_FIELDS):
            if field == "name":
                value = unit_name
            elif field == "name_en":
                value = details.get(field, unit_name)
            else:
                value = details.get(field, "")
            variable = tk.StringVar(master=self, value=value)
            text_vars[field] = variable
            ttk.Label(card, text=self._tr(label)).grid(
                row=row, column=0, sticky="w", padx=(2, 12), pady=2)
            ttk.Entry(card, textvariable=variable).grid(
                row=row, column=1, sticky="ew", padx=2, pady=2)

        numeric_vars = {}
        numeric_types = {}
        row = len(UNIT_TEXT_FIELDS)
        for path, value in _numeric_values(details):
            variable = tk.StringVar(master=self, value=self._format_value(value))
            numeric_vars[path] = variable
            numeric_types[path] = type(value)
            ttk.Label(card, text=self._format_path(path)).grid(
                row=row, column=0, sticky="w", padx=(2, 12), pady=2)
            ttk.Entry(card, textvariable=variable, width=14,
                      justify="right").grid(
                          row=row, column=1, sticky="ew", padx=2, pady=2)
            row += 1

        ttk.Button(
            card, text=self._tr("Remove unit type"),
            command=lambda name=unit_name: self._remove_unit_type(name),
            state="normal" if unit_count > 1 else "disabled").grid(
                row=row, column=1, sticky="e", padx=2, pady=(5, 1))
        self.unit_type_fields.append({
            "original_name": unit_name,
            "text_vars": text_vars,
            "numeric_vars": numeric_vars,
            "numeric_types": numeric_types,
        })

    def _add_unit_type(self):
        unit_types = self.config_data.setdefault("unit_types", {})
        unit_ids = {details.get("id") for details in unit_types.values()}
        index = 1
        while True:
            name = "New Unit {}".format(index)
            unit_id = "new_unit_{}".format(index)
            if name not in unit_types and unit_id not in unit_ids:
                break
            index += 1
        used_symbols = {details.get("symbol") for details in unit_types.values()}
        symbol = next((letter for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                       if letter not in used_symbols), "U")
        details = dict(UNIT_DEFAULTS)
        details.update({
            "id": unit_id,
            "name_en": name,
            "name_zh": "\u65b0\u5175\u79cd {}".format(index),
            "symbol": symbol,
            "cost": dict(UNIT_DEFAULTS["cost"]),
            "skills": [],
        })
        unit_types[name] = details
        self._rebuild_unit_type_cards()
        self.scrollable.canvas.yview_moveto(1.0)

    def _remove_unit_type(self, unit_name):
        unit_types = self.config_data.get("unit_types", {})
        if len(unit_types) <= 1:
            return
        unit_types.pop(unit_name, None)
        self._rebuild_unit_type_cards()

    @staticmethod
    def _format_value(value):
        if type(value) is float:
            return "{:g}".format(value)
        return str(value)

    def _candidate_config(self):
        candidate = json.loads(json.dumps(self.config_data))
        for path, variable in self.field_vars.items():
            value = self._parse_numeric(
                path, variable, self.field_types[path])
            _set_config_value(candidate, path, value)

        updated_unit_types = {}
        for unit in self.unit_type_fields:
            original_name = unit["original_name"]
            text_vars = unit["text_vars"]
            name = text_vars["name"].get().strip()
            if not name or len(name) > 30 or name in updated_unit_types:
                raise ValueError(self._tr("Unit names must be unique and 1 to 30 characters."))
            details = json.loads(json.dumps(
                self.config_data["unit_types"][original_name]))
            details["id"] = text_vars["id"].get().strip()
            details["name_en"] = text_vars["name_en"].get().strip()
            details["category"] = text_vars["category"].get().strip()
            details["symbol"] = text_vars["symbol"].get()
            localized_name = text_vars["name_zh"].get().strip()
            if localized_name:
                details["name_zh"] = localized_name
            else:
                details.pop("name_zh", None)
            for path, variable in unit["numeric_vars"].items():
                value = self._parse_numeric(
                    ("unit_types", original_name) + path,
                    variable, unit["numeric_types"][path])
                _set_config_value(details, path, value)
            updated_unit_types[name] = details
        candidate["unit_types"] = updated_unit_types
        return candidate

    def _parse_numeric(self, path, variable, value_type):
        raw_value = variable.get().strip()
        try:
            value = int(raw_value) if value_type is int else float(raw_value)
        except ValueError:
            raise ValueError(self._tr("Invalid value for {}.").format(
                ".".join(str(part) for part in path)))
        if type(value) is float and not math.isfinite(value):
            raise ValueError(self._tr("Invalid value for {}.").format(
                ".".join(str(part) for part in path)))
        return value

    def _save(self):
        temporary_path = None
        try:
            candidate = self._candidate_config()
            config_directory = os.path.dirname(self.config_path)
            descriptor, temporary_path = tempfile.mkstemp(
                prefix=".config-", suffix=".json", dir=config_directory)
            with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
                json.dump(candidate, config_file, indent=2)
                config_file.write("\n")
            _load_config(temporary_path)
            os.replace(temporary_path, self.config_path)
            temporary_path = None
            self.config_data = candidate
            self._refresh_fields()
            self.status_var.set(self._tr(
                "Saved. Restart the game to apply changes."))
            self.status_label.configure(foreground=GREEN)
        except (IOError, OSError, TypeError, ValueError, RuntimeError) as error:
            self.status_var.set(self._tr("Configuration error: {}").format(error))
            self.status_label.configure(foreground="#a3443c")
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

    def _refresh_fields(self):
        for child in self.scrollable.content.winfo_children():
            child.destroy()
        self.field_vars = {}
        self.field_types = {}
        self._build_fields()