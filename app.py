import copy
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from game_config import ENEMY, NEUTRAL, PLAYER
from game_model import GameModel, Unit
from app_paths import application_path
from game_dialogs import (
    CountryChoiceDialog,
    RecruitDialog,
    SettingsDialog,
    UnitInfoDialog,
)
from hex_map import HexMapView
from map_editor import MapEditorApp
from map_data import load_map_file
from i18n import (LANGUAGES, LocalizedStringVar, apply_language, load_language, save_language,
                  set_language, translate)
from unit_effects import (
    FlankedMorale,
    MoraleBoost,
    OverextendedMorale,
    SurroundedMorale,
    refresh_tactical_statuses,
)


INK = "#202c27"
MUTED = "#768078"
PAPER = "#e8e7df"
GREEN = "#47745f"


class GameApp(object):
    def __init__(self, root):
        self.root = root
        self.language = load_language()
        set_language(self.language)
        self.root.title(translate("Steel Dominion | Hex Campaign", self.language))
        self.root.geometry("640x420")
        self.root.minsize(640, 420)
        self.root.configure(bg=PAPER)

        self.maps_directory = application_path("maps")
        self.saves_directory = application_path("saves")
        self.current_map_path = os.path.join(self.maps_directory, "default_map.json")
        self.current_map_name = "Default Map"
        self.map_data = None
        self.model = GameModel()
        self.player_country_id = self.model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.setup_page_active = False
        self.setup_country_confirmed = False
        self.debug_mode = False
        self.model.phase = "setup"
        self.resource_country_id = self.player_country_id
        self.selected_hex = (2, 4)
        self.selected_unit = None
        self.attack_target = None
        self.result_shown = False
        self.history = []
        self.move_undo = None
        self.attacked_unit_ids = set()
        self.ai_running = False
        self.full_ai_mode = False
        self.full_ai_paused = False
        self._full_ai_after_id = None
        self._eu2_ai_result_recorded = False
        self._result_was_full_ai = False
        self.eu2_ai_stats_path = os.path.join(
            self.saves_directory, "EU2_ai_results.json")
        self.eu2_ai_stats = self._load_eu2_ai_stats()
        self.ai_result_queue = queue.Queue()
        self._entry_page = None
        self._editor_window = None
        self._editor_app = None
        self.map_records = []
        self._selected_map_record = None
        self._updating_map_list = False
        self._overwrite_prompt = None
        self._last_saved_payload = None
        self.message = "Choose your country, then start the campaign."
        self._build_ui()
        apply_language(self.root, self.language)
        self._log("Choose a country to begin the campaign.")
        self._refresh()

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", padding=(9, 7), font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background=GREEN, foreground="white")
        style.map("Accent.TButton", background=[("active", "#365b49"), ("disabled", "#aab5ad")])
        style.configure("MapIcon.TButton", padding=(0, 0), font=("Segoe UI", 8, "bold"))
        style.configure("MapAction.TButton", padding=(2, 1), font=("Segoe UI", 8, "bold"),
                        background=GREEN, foreground="white")
        style.map("MapAction.TButton",
                  background=[("active", "#365b49"), ("disabled", "#aab5ad")])
        style.configure("TCombobox", padding=5)

        self.stat_vars = {key: tk.StringVar(value="-")
                          for key in ("money", "steel", "technology")}
        self.income_vars = {key: tk.StringVar(value="+0")
                    for key in ("money", "steel", "technology")}
        self.maintenance_vars = {key: tk.StringVar(value="-0")
                     for key in ("money", "steel", "technology")}
        self.income_suffix_var = LocalizedStringVar(value="/turn")
        self.debug_income_comparison = LocalizedStringVar()
        self.debug_hp_comparison = LocalizedStringVar()
        self.game_area = tk.Frame(self.root, bg="#dfe7df")
        self.game_area.pack(fill="both", expand=True)
        self.map_view = HexMapView(
            self.game_area, self.model, self._on_hex_click,
            bg="#dfe7df", highlightthickness=0, cursor="fleur")
        self.map_view.pack(side="left", fill="both", expand=True)

        self.resource_strip = tk.Frame(
            self.root, bg="#d9ddd5", height=36, highlightthickness=1,
            highlightbackground="#c9cec4")
        self.resource_strip.place(x=0, y=0, relwidth=1.0, height=36)
        for key, label, symbol, accent in (
            ("money", "MONEY", "$", "#aa8437"),
            ("steel", "STEEL", "S", "#54747a"),
            ("technology", "TECH", "T", "#47745f")):
            cell = tk.Frame(self.resource_strip, bg="#d9ddd5")
            cell.pack(side="left", fill="y", padx=(12, 14))
            tk.Label(cell, text=symbol, bg="#d9ddd5", fg=accent,
                 font=("Georgia", 12, "bold")).pack(side="left", padx=(0, 6))
            tk.Label(cell, text=label, bg="#d9ddd5", fg=MUTED,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(0, 5))
            tk.Label(cell, textvariable=self.stat_vars[key], bg="#d9ddd5", fg=INK,
                 font=("Consolas", 11, "bold")).pack(side="left")
            tk.Label(cell, textvariable=self.income_vars[key], bg="#d9ddd5",
                     fg=GREEN, font=("Consolas", 8, "bold")).pack(
                         side="left", padx=(5, 0))
            tk.Label(cell, textvariable=self.maintenance_vars[key],
                     bg="#d9ddd5", fg="#b75a52",
                     font=("Consolas", 8, "bold")).pack(side="left")
            tk.Label(cell, textvariable=self.income_suffix_var,
                     bg="#d9ddd5", fg=GREEN,
                     font=("Consolas", 8, "bold")).pack(side="left")
        self.settings_button = ttk.Button(
            self.resource_strip, text="Settings", command=self._show_settings)
        self.settings_button.pack(side="right", padx=8, pady=3)
        self.debug_comparison = tk.Frame(self.resource_strip, bg="#d9ddd5")
        tk.Label(self.debug_comparison, textvariable=self.debug_income_comparison,
                 bg="#d9ddd5", fg=INK, font=("Consolas", 8, "bold")).pack(
                     anchor="e")
        tk.Label(self.debug_comparison, textvariable=self.debug_hp_comparison,
                 bg="#d9ddd5", fg=GREEN, font=("Consolas", 8, "bold")).pack(
                     anchor="e")
        self.debug_comparison.pack(side="right", padx=(0, 8))
        self.auto_button = ttk.Button(
            self.root, text="Auto", command=self._auto_player_turn)

        self.hex_info_panel = tk.Frame(
            self.map_view, bg="#f4f3ed", padx=10, pady=8,
            highlightthickness=1, highlightbackground="#aeb8ac")
        self.hex_info_title = tk.StringVar()
        self.hex_info_owner = tk.StringVar()
        self.hex_info_details = tk.StringVar()
        tk.Label(self.hex_info_panel, textvariable=self.hex_info_title, bg="#f4f3ed",
                 fg=INK, font=("Georgia", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.hex_info_panel, textvariable=self.hex_info_owner, bg="#f4f3ed",
                 fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(2, 5))
        tk.Label(self.hex_info_panel, textvariable=self.hex_info_details, bg="#f4f3ed",
                 fg=INK, font=("Segoe UI", 9), justify="left", anchor="w",
                 wraplength=250).pack(fill="x")
        self.hex_info_panel.place_forget()

        self.unit_info_button = ttk.Button(
            self.map_view, text="i", width=2, style="MapIcon.TButton",
            command=self._show_unit_details)
        self.city_recruit_button = ttk.Button(
            self.map_view, text="+", width=2, style="MapAction.TButton",
            command=self._show_recruit_dialog)
        self.undo_move_button = ttk.Button(
            self.map_view, text="\u21b6", width=2, style="MapIcon.TButton",
            command=self._undo_move)
        self.end_turn_button = ttk.Button(
            self.map_view, text="End turn  >", style="Accent.TButton",
            command=self._end_turn)
        self.status_var = LocalizedStringVar(value=self.message)
        self.status_label = tk.Label(
            self.map_view, textvariable=self.status_var, anchor="w", padx=8, pady=4,
            bg="#f4f3ed", fg="#526057", font=("Segoe UI", 9))
        self._build_map_sidebar()
        self._build_entry_page()
        self._build_result_overlay()

    def _build_result_overlay(self):
        self.result_overlay = tk.Frame(self.root, bg="#dfe7df")
        panel = tk.Frame(self.result_overlay, bg=PAPER, padx=30, pady=26,
                         highlightthickness=1, highlightbackground="#aeb8ac")
        panel.place(relx=0.5, rely=0.5, anchor="center")
        self.result_title = LocalizedStringVar()
        self.result_city_vars = [LocalizedStringVar(), LocalizedStringVar()]
        self.result_turn_var = LocalizedStringVar()
        self.result_unit_var = LocalizedStringVar()
        self.result_stats_var = LocalizedStringVar()
        self.result_error_var = LocalizedStringVar()
        tk.Label(panel, textvariable=self.result_title, bg=PAPER, fg=INK,
                 font=("Georgia", 22, "bold")).pack(anchor="w", pady=(0, 14))
        for variable in self.result_city_vars:
            tk.Label(panel, textvariable=variable, bg=PAPER, fg=INK,
                     font=("Segoe UI", 11)).pack(anchor="w", pady=3)
        tk.Label(panel, textvariable=self.result_turn_var, bg=PAPER, fg=INK,
                 font=("Segoe UI", 11)).pack(anchor="w", pady=3)
        tk.Label(panel, textvariable=self.result_unit_var, bg=PAPER, fg=INK,
                 font=("Segoe UI", 11)).pack(anchor="w", pady=3)
        self.result_stats_label = tk.Label(
            panel, textvariable=self.result_stats_var, bg="#e7ebe3", fg=INK,
            justify="left", wraplength=410, padx=10, pady=8,
            font=("Segoe UI", 10, "bold"))
        self.result_error_label = tk.Label(
            panel, textvariable=self.result_error_var, bg=PAPER, fg="#a3443c",
            justify="left", wraplength=410, font=("Segoe UI", 9))
        self.result_confirm_button = ttk.Button(
            panel, text="Confirm", style="Accent.TButton",
            command=self._close_result)
        self.result_confirm_button.pack(anchor="e", pady=(20, 0))
        self.result_overlay.place_forget()

    def _load_eu2_ai_stats(self):
        try:
            with open(self.eu2_ai_stats_path, "r") as stats_file:
                stats = json.load(stats_file)
            return {
                "games": max(0, int(stats.get("games", 0))),
                "player_wins": max(0, int(stats.get("player_wins", 0))),
                "enemy_wins": max(0, int(stats.get("enemy_wins", 0))),
            }
        except (IOError, OSError, ValueError, TypeError, AttributeError):
            return {"games": 0, "player_wins": 0, "enemy_wins": 0}

    def _is_eu2_map(self):
        return os.path.basename(self.current_map_path).lower() == "eu2.json"

    def _record_eu2_ai_result(self, winner):
        if self._eu2_ai_result_recorded or not self._is_eu2_map():
            return
        self._eu2_ai_result_recorded = True
        self.eu2_ai_stats["games"] += 1
        key = "player_wins" if winner == PLAYER else "enemy_wins"
        self.eu2_ai_stats[key] += 1
        try:
            if not os.path.isdir(self.saves_directory):
                os.makedirs(self.saves_directory)
            temporary_path = self.eu2_ai_stats_path + ".tmp"
            with open(temporary_path, "w") as stats_file:
                json.dump(self.eu2_ai_stats, stats_file, indent=2, sort_keys=True)
                stats_file.write("\n")
            os.replace(temporary_path, self.eu2_ai_stats_path)
        except (IOError, OSError):
            try:
                if os.path.exists(self.eu2_ai_stats_path + ".tmp"):
                    os.remove(self.eu2_ai_stats_path + ".tmp")
            except OSError:
                pass

    def _build_entry_page(self):
        page = tk.Frame(self.root, bg=PAPER)
        masthead = tk.Frame(page, bg=INK, padx=28, pady=24)
        masthead.pack(fill="x")
        language_row = tk.Frame(masthead, bg=INK)
        language_row.place(relx=1.0, x=-20, y=18, anchor="ne")
        self.entry_language_label = tk.Label(
            language_row, text="Language", bg=INK, fg="#a9b3a9",
            font=("Segoe UI", 9))
        self.entry_language_label.pack(side="left", padx=(0, 7))
        self.entry_language_var = tk.StringVar(value=LANGUAGES[self.language])
        self.entry_language_choice = ttk.Combobox(
            language_row, textvariable=self.entry_language_var,
            values=tuple(LANGUAGES.values()), state="readonly", width=12)
        self.entry_language_choice.pack(side="left")
        self.entry_language_choice.bind(
            "<<ComboboxSelected>>", self._on_entry_language_selected)
        tk.Label(masthead, text="STEEL DOMINION", bg=INK, fg="#a9b3a9",
                 font=("Consolas", 9, "bold")).pack(anchor="w")
        tk.Label(masthead, text="Hex Campaign", bg=INK, fg="#f5f2e8",
                 font=("Georgia", 24, "bold")).pack(anchor="w", pady=(6, 0))
        content = tk.Frame(page, bg=PAPER, padx=32, pady=28)
        content.pack(fill="both", expand=True)
        actions = ttk.Frame(content)
        actions.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Button(actions, text="Enter campaign", width=24,
                   style="Accent.TButton", command=self._enter_campaign).pack(
                       pady=(0, 10))
        ttk.Button(actions, text="Edit map", width=24,
                   command=self._open_map_editor).pack()
        self._entry_page = page
        page.place(relwidth=1, relheight=1)
        page.lift()

    def _on_entry_language_selected(self, event=None):
        language = next((code for code, label in LANGUAGES.items()
                         if label == self.entry_language_var.get()), "en")
        self._set_language(language)

    def _set_language(self, language):
        self.language = language if language in LANGUAGES else "en"
        set_language(self.language)
        save_language(self.language)
        self.root.title(translate("Steel Dominion | Hex Campaign", self.language))
        self.entry_language_var.set(LANGUAGES[self.language])
        apply_language(self.root, self.language)
        self.status_var.set(self.message)
        self._refresh()

    def _open_map_editor(self):
        if self._editor_window is not None:
            self._editor_window.lift()
            return
        window = tk.Toplevel(self.root)
        self._editor_window = window
        self._editor_app = MapEditorApp(window, self._close_map_editor)
        window.protocol("WM_DELETE_WINDOW", self._close_map_editor)
        self.root.withdraw()

    def _close_map_editor(self):
        if self._editor_window is not None:
            self._editor_window.destroy()
            self._editor_window = None
            self._editor_app = None
        self.root.deiconify()
        self.root.lift()

    def _return_to_main_menu(self):
        self.setup_page_active = False
        if self._entry_page is None:
            self._build_entry_page()
        self._refresh()
        self._entry_page.lift()

    def _build_map_sidebar(self):
        self.map_sidebar = tk.Frame(
            self.game_area, bg=PAPER, width=220, padx=14, pady=14,
            highlightthickness=1, highlightbackground="#c9cec4")
        self.map_sidebar.pack_propagate(False)
        tk.Label(self.map_sidebar, text="CAMPAIGN MAPS", bg=INK, fg="#f5f2e8",
                 padx=12, pady=10, font=("Consolas", 9, "bold")).pack(fill="x")
        list_frame = tk.Frame(self.map_sidebar, bg=PAPER)
        list_frame.pack(fill="both", expand=True, pady=(12, 8))
        self.map_list = tk.Listbox(
            list_frame, exportselection=False, activestyle="none", borderwidth=0,
            highlightthickness=1, highlightbackground="#c9cec4", bg="#f4f3ed",
            fg=INK, selectbackground=GREEN, selectforeground="white",
            font=("Segoe UI", 10))
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.map_list.yview)
        self.map_list.configure(yscrollcommand=scrollbar.set)
        self.map_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.map_list.bind("<<ListboxSelect>>", self._on_map_list_selected)
        self.map_sidebar_status = LocalizedStringVar(value="")
        tk.Label(self.map_sidebar, textvariable=self.map_sidebar_status,
                 bg=PAPER, fg=MUTED, justify="left", anchor="w",
                 wraplength=185, font=("Segoe UI", 8)).pack(fill="x", pady=(0, 8))
        self.load_save_button = ttk.Button(
            self.map_sidebar, text="Load save", command=self._load_selected_save,
            state="disabled")
        self.load_save_button.pack(fill="x")
        self.main_menu_button = ttk.Button(
            self.map_sidebar, text="Back to main menu",
            command=self._return_to_main_menu)
        self.main_menu_button.pack(fill="x", pady=(8, 0))

    def _log(self, message):
        self.history.insert(0, "T{:02d}  {}".format(self.model.turn, message))
        del self.history[40:]

    def _show_settings(self):
        if self.full_ai_mode or self.ai_running:
            return
        SettingsDialog(
            self.root, self.model, self.player_country_id,
            self.pending_player_country_id, self.resource_country_id,
            self.campaign_started, self.current_map_name, self.history,
            self.debug_mode, self.attack_target,
            self._on_settings_resource_selected, self._open_map_selector,
            self._settings_campaign_action, self._exit_to_country, self._attack,
            self._cancel_attack, self._on_debug_changed, self._start_full_ai,
            self.language,
            self._set_language)

    def _exit_to_country(self):
        if not self.campaign_started:
            return
        self.campaign_started = False
        self.setup_page_active = True
        self.setup_country_confirmed = False
        self.selected_unit = None
        self.attack_target = None
        self.pending_player_country_id = self.player_country_id
        self.model.phase = "setup"
        self.message = "Choose a country to continue."
        if not self.map_records:
            self._load_map_records()
        record = next((item for item in self.map_records
                       if os.path.normcase(os.path.abspath(item["path"])) ==
                       os.path.normcase(os.path.abspath(self.current_map_path))), None)
        if record and not record["error"]:
            self._select_map_in_sidebar(record)
        self._refresh()

    def _on_debug_changed(self, enabled):
        self.debug_mode = bool(enabled)
        self._refresh()

    def _on_hex_click(self, position):
        if self.ai_running or self.full_ai_mode:
            return
        if not self.campaign_started:
            if not self.setup_country_confirmed:
                city = self.model.city_for_hex(position)
                if city and self.model.faction_for(city["owner"]) != NEUTRAL:
                    CountryChoiceDialog(
                        self.root, self.model, city["owner"],
                        self._on_setup_country_confirmed)
                    return
            self.selected_hex = position
            self.selected_unit = self.model.unit_at(position)
            self.attack_target = None
            self.message = "Hex selected."
            self._refresh()
            return
        if self.model.phase != PLAYER:
            return
        unit = self.model.unit_at(position)
        if unit and unit.owner == self.player_country_id:
            self.selected_hex = position
            self.selected_unit = unit
            self.attack_target = None
            if unit.attacked:
                action_hint = "Attack used; this unit is spent for the turn."
            elif unit.movement_left > 0:
                action_hint = "{} MP and {}/{} attack available; red outlines mark targets in range.".format(
                    unit.movement_left, unit.attacks_left, unit.attacks_per_turn)
            else:
                action_hint = "0 MP; {}/{} attack available. Red outlines mark targets in range.".format(
                    unit.attacks_left, unit.attacks_per_turn)
            self.message = "Selected {}. {}".format(unit.kind, action_hint)
            self._refresh()
            return

        if unit and self.model.faction_for(unit.owner) == NEUTRAL:
            self.selected_hex = position
            self.selected_unit = unit
            self.attack_target = None
            self.message = "Neutral units cannot be commanded or attacked."
            self._refresh()
            return

        if (self.selected_unit and self.selected_unit.owner == self.player_country_id and
                not self.selected_unit.attacked):
            distance = self.model.distance(self.selected_unit.position, position)
            city = self.model.cities.get(position)
            hostile_target = (unit and unit.faction == self.model.enemy_faction) or (
                city and city["health"] > 0 and
                self.model.faction_for(city["owner"]) == self.model.enemy_faction)
            if hostile_target and distance <= self.selected_unit.range:
                self.attack_target = position
                self.selected_hex = self.selected_unit.position
                self._attack()
                return
            movement_paths = self.model.movement_paths(self.selected_unit)
            if position in movement_paths:
                moving_unit = self.selected_unit
                start_position = moving_unit.position
                movement_path = movement_paths[position]
                move_snapshot = (copy.deepcopy(self.model)
                                 if moving_unit.id not in self.attacked_unit_ids
                                 else None)
                moved, events = self.model.move(
                    moving_unit, position, path=movement_path)
                self._show_events(events)
                if moved:
                    self.move_undo = (move_snapshot, self.selected_unit.id)
                    self.selected_hex = position
                    self.message = events[-1]
                    self._announce_result()
                else:
                    self.message = events[-1]
                self.attack_target = None
                self._refresh()
                if moved and moving_unit.owner == self.player_country_id:
                    self.map_view.animate_unit_path(
                        moving_unit.id, start_position, movement_path, 0.4)
                return

        self.selected_hex = position
        self.selected_unit = None
        self.attack_target = None
        city = self.model.cities.get(position)
        self.message = "{}: select a unit or recruit here.".format(city["name"]) if city else "Select one of your units."
        self._refresh()

    def _show_unit_details(self):
        unit = self.model.unit_at(self.selected_hex)
        if unit:
            UnitInfoDialog(self.root, self.model, unit, self.debug_mode)

    def _show_recruit_dialog(self):
        city = self.model.cities.get(self.selected_hex)
        if (not self.campaign_started or self.ai_running or self.full_ai_mode or
            self.model.phase != PLAYER or not city or
                city["owner"] != self.player_country_id):
            return
        RecruitDialog(self.root, self.model, city, self.player_country_id,
                      self.campaign_started, self._on_recruited)

    def _on_recruited(self, unit, message):
        self.move_undo = None
        self.message = message
        self.selected_unit = unit
        self.selected_hex = unit.position
        self.attack_target = None
        self._log(message)
        self._refresh()

    def _on_settings_resource_selected(self, country_id):
        account_country_id = (self.player_country_id if self.campaign_started else
                              self.pending_player_country_id)
        if (country_id in self.model.countries and
                self.model.faction_for(country_id) == self.model.faction_for(
                    account_country_id)):
            self.resource_country_id = country_id
        self._refresh()

    def _on_setup_country_confirmed(self, country_id):
        if (self.campaign_started or country_id not in self.model.countries or
                self.model.faction_for(country_id) == NEUTRAL):
            return
        self.pending_player_country_id = country_id
        if os.path.isfile(self._save_path_for_map(self.current_map_path)):
            self._show_overwrite_prompt(country_id)
            return
        self.player_country_id = country_id
        self._reset_campaign("Campaign started as {}.".format(
            self.model.country_name(country_id)))

    def _show_overwrite_prompt(self, country_id):
        if self._overwrite_prompt is not None:
            self._overwrite_prompt.destroy()
        overlay = tk.Frame(self.root, bg="#dfe7df")
        panel = tk.Frame(overlay, bg=PAPER, padx=24, pady=20,
                         highlightthickness=1, highlightbackground="#aeb8ac")
        panel.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(panel, text="Replace saved campaign?", bg=PAPER, fg=INK,
                 font=("Georgia", 16, "bold")).pack(anchor="w")
        tk.Label(panel, text="Starting here will overwrite this map's saved game.",
                 bg=PAPER, fg=MUTED, font=("Segoe UI", 9)).pack(
                     anchor="w", pady=(6, 18))
        actions = tk.Frame(panel, bg=PAPER)
        actions.pack(fill="x")

        def cancel():
            overlay.destroy()
            self._overwrite_prompt = None

        def replace_save():
            cancel()
            self.player_country_id = country_id
            self._reset_campaign("Campaign started as {}.".format(
                self.model.country_name(country_id)))

        ttk.Button(actions, text="Cancel", command=cancel).pack(side="right")
        ttk.Button(actions, text="Overwrite and start", style="Accent.TButton",
                   command=replace_save).pack(side="right", padx=(0, 8))
        overlay.place(relwidth=1, relheight=1)
        overlay.lift()
        apply_language(overlay, self.language)
        self._overwrite_prompt = overlay

    def _attack(self):
        if not self.selected_unit or self.attack_target is None:
            return
        attacked, events = self.model.attack(self.selected_unit, self.attack_target)
        damage_events = list(self.model.last_damage_events)
        self._show_events(events)
        if attacked:
            self.attacked_unit_ids.add(self.selected_unit.id)
            self.move_undo = None
            self.message = events[0]
            self.attack_target = None
            self._announce_result()
        else:
            self.message = events[-1]
        self._refresh()
        if attacked:
            for position, damage in damage_events:
                self.map_view.animate_damage_number(position, damage)

    def _cancel_attack(self):
        self.attack_target = None
        self.message = "Target cleared."
        self._refresh()

    def _undo_move(self):
        if (not self.move_undo or not self.campaign_started or
                self.model.phase != PLAYER or not self.selected_unit):
            return
        previous_model, unit_id = self.move_undo
        if (previous_model is None or self.selected_unit.id != unit_id or
                unit_id in self.attacked_unit_ids):
            return
        self.model = previous_model
        self.map_view.model = self.model
        self.selected_unit = next(
            (unit for unit in self.model.units if unit.id == unit_id), None)
        if not self.selected_unit:
            self.move_undo = None
            self._refresh()
            return
        self.selected_hex = self.selected_unit.position
        self.attack_target = None
        self.move_undo = None
        self.message = "Last movement withdrawn."
        self._log(self.message)
        self._refresh()

    def _settings_campaign_action(self):
        if self.campaign_started:
            self._reset_campaign("Campaign restarted as {}.".format(
                self.model.country_name(self.player_country_id)))
        else:
            self._restart()

    def _end_turn(self):
        if (not self.campaign_started or self.full_ai_mode or
            self.model.phase != PLAYER):
            return
        self.move_undo = None
        self.model.phase = ENEMY
        self.ai_running = True
        self.message = "AI forces are taking their turn..."
        self._refresh()
        self.root.after(450, self._run_enemy_turn)

    def _auto_player_turn(self):
        if (not self.campaign_started or self.model.phase != PLAYER or
                self.ai_running):
            return
        self.move_undo = None
        self.ai_running = True
        self.message = "AI is taking actions for this turn..."
        self.auto_button.configure(text="Auto...")
        self._refresh()
        if not self.full_ai_mode:
            self.auto_button.configure(text=translate("Auto...", self.language))
        model = copy.deepcopy(self.model)

        def calculate_turn():
            try:
                events, winner = model.auto_player_turn()
            except Exception as error:
                self.ai_result_queue.put((None, None, None, error))
            else:
                self.ai_result_queue.put((model, events, winner, None))

        threading.Thread(target=calculate_turn, daemon=True).start()
        self.root.after(40, self._poll_auto_player_turn)

    def _poll_auto_player_turn(self):
        try:
            model, events, winner, error = self.ai_result_queue.get_nowait()
        except queue.Empty:
            self.root.after(40, self._poll_auto_player_turn)
            return
        self.ai_running = False
        if error:
            self.full_ai_mode = False
            self.full_ai_paused = False
            self.message = "AI actions failed: {}".format(error)
            self._refresh()
            self.auto_button.configure(text=translate("Auto failed", self.language))
            self.root.after(2200, self._reset_auto_button_label)
            return

        self.model = model
        self.map_view.model = model
        self._show_events(events)
        self.selected_unit = next(
            (unit for unit in model.units
             if unit.owner == self.player_country_id and not unit.attacked), None)
        if self.selected_unit:
            self.selected_hex = self.selected_unit.position
        self.attack_target = None
        self.message = events[-1] if events else "AI actions complete."
        self._refresh()
        if winner:
            self._announce_result()
        elif self.full_ai_mode:
            self.model.phase = ENEMY
            self.ai_running = True
            self.message = "AI forces are taking their turn..."
            self._refresh()
            self.root.after(0, self._run_enemy_turn)
        else:
            self.auto_button.configure(text=translate("Auto done", self.language))
            self.root.after(2200, self._reset_auto_button_label)

    def _reset_auto_button_label(self):
        if self.auto_button.winfo_exists() and not self.full_ai_mode:
            self.auto_button.configure(text=translate("Auto", self.language))

    def _run_enemy_turn(self):
        model = copy.deepcopy(self.model)

        def calculate_turn():
            try:
                events, winner = model.enemy_turn()
            except Exception as error:
                self.ai_result_queue.put((None, None, None, error))
            else:
                self.ai_result_queue.put((model, events, winner, None))

        threading.Thread(target=calculate_turn, daemon=True).start()
        self.root.after(40, self._poll_enemy_turn)

    def _poll_enemy_turn(self):
        try:
            model, events, winner, error = self.ai_result_queue.get_nowait()
        except queue.Empty:
            self.root.after(40, self._poll_enemy_turn)
            return
        self.ai_running = False
        if error:
            self.model.phase = PLAYER
            self.full_ai_mode = False
            self.full_ai_paused = False
            self.message = "AI turn failed: {}".format(error)
            self._refresh()
            return

        self.model = model
        self.map_view.model = self.model
        self.attacked_unit_ids.clear()
        self._show_events(events)
        self.selected_unit = next(
            (unit for unit in self.model.units if unit.owner == self.player_country_id), None)
        if self.selected_unit:
            self.selected_hex = self.selected_unit.position
        self.attack_target = None
        self.message = events[-1] if events else "Enemy turn complete."
        self._refresh()
        if winner:
            self._announce_result()
        elif self.full_ai_mode and not self.full_ai_paused:
            self._schedule_full_ai_round()

    def _start_full_ai(self):
        if (not self.debug_mode or not self.campaign_started or
                self.model.phase != PLAYER or self.ai_running):
            return
        self.full_ai_mode = True
        self.full_ai_paused = False
        self._eu2_ai_result_recorded = False
        self.map_view.fit_map()
        self.root.after_idle(self.map_view.fit_map)
        self.message = "Full AI control started."
        self._refresh()
        self._run_full_ai_round()

    def _run_full_ai_round(self):
        self._full_ai_after_id = None
        if (not self.full_ai_mode or self.full_ai_paused or self.ai_running or
                not self.campaign_started or self.model.phase != PLAYER):
            return
        self._auto_player_turn()

    def _schedule_full_ai_round(self):
        if self._full_ai_after_id is None:
            self._full_ai_after_id = self.root.after(
                300, self._run_full_ai_round)

    def _toggle_full_ai_pause(self):
        if not self.full_ai_mode:
            return
        self.full_ai_paused = not self.full_ai_paused
        if self.full_ai_paused:
            if self._full_ai_after_id is not None:
                self.root.after_cancel(self._full_ai_after_id)
                self._full_ai_after_id = None
            self.message = ("Full AI control will pause after this round."
                            if self.ai_running else "Full AI control paused.")
        else:
            self.message = "Full AI control resumed."
            if not self.ai_running:
                self._schedule_full_ai_round()
        self._refresh()

    def _stop_full_ai(self):
        if not self.full_ai_mode:
            return
        self.full_ai_mode = False
        self.full_ai_paused = False
        if self._full_ai_after_id is not None:
            self.root.after_cancel(self._full_ai_after_id)
            self._full_ai_after_id = None
        self.message = ("Full AI control will stop after current AI actions."
                        if self.ai_running else "Full AI control stopped.")
        self._refresh()

    def _show_events(self, events):
        for event in events:
            self._log(event)

    def _announce_result(self):
        if not self.model.winner or self.result_shown:
            return
        self.result_shown = True
        self._result_was_full_ai = self.full_ai_mode
        self.full_ai_mode = False
        self.full_ai_paused = False
        if self._full_ai_after_id is not None:
            self.root.after_cancel(self._full_ai_after_id)
            self._full_ai_after_id = None
        if self.model.winner == PLAYER:
            self.message = "Victory: all opposing cities have been captured."
            title = "Campaign victory"
        else:
            self.message = "Defeat: all of your faction's cities have fallen."
            title = "Campaign lost"
        if self._result_was_full_ai and self._is_eu2_map():
            self._record_eu2_ai_result(self.model.winner)
        self.result_title.set(title)
        self.result_city_vars[0].set("Player faction cities: {}".format(
            self.model.owned_cities(self.model.player_faction)))
        self.result_city_vars[1].set("Enemy faction cities: {}".format(
            self.model.owned_cities(self.model.enemy_faction)))
        self.result_turn_var.set("Final turn: {}".format(self.model.turn))
        player_units = sum(1 for unit in self.model.units
                           if unit.faction == self.model.player_faction)
        enemy_units = sum(1 for unit in self.model.units
                          if unit.faction == self.model.enemy_faction)
        self.result_unit_var.set("Surviving units: {} / {}".format(
            player_units, enemy_units))
        if self._result_was_full_ai and self._is_eu2_map():
            self.result_stats_var.set(
                "EU2 full AI results: {} games / Player {} wins / Enemy {} wins".format(
                    self.eu2_ai_stats["games"], self.eu2_ai_stats["player_wins"],
                    self.eu2_ai_stats["enemy_wins"]))
            self.result_stats_label.pack(fill="x", pady=(14, 0))
        else:
            self.result_stats_label.pack_forget()
        self.result_error_label.pack_forget()
        self._refresh()
        self.result_overlay.place(relwidth=1.0, relheight=1.0)
        self.result_overlay.lift()

    def _close_result(self):
        save_path = self._save_path_for_map(self.current_map_path)
        try:
            if os.path.exists(save_path):
                os.remove(save_path)
        except OSError as error:
            self.result_error_var.set(
                "Unable to delete campaign save: {}".format(error))
            self.result_error_label.pack(fill="x", pady=(14, 0),
                                         before=self.result_confirm_button)
            return

        self._last_saved_payload = None
        self.result_overlay.place_forget()
        self.result_error_label.pack_forget()
        self.full_ai_mode = False
        self.full_ai_paused = False
        self._result_was_full_ai = False
        if not self.map_records:
            self._load_map_records()
        record = next((item for item in self.map_records
                       if os.path.normcase(os.path.abspath(item["path"])) ==
                       os.path.normcase(os.path.abspath(self.current_map_path))), None)
        if record and not record["error"] and self._apply_map_record(record):
            self._select_map_in_sidebar(record)
        else:
            self.campaign_started = False
            self.setup_page_active = True
            self.setup_country_confirmed = False
            self.selected_unit = None
            self.attack_target = None
            self.pending_player_country_id = self.player_country_id
            self.message = "Choose a country to continue."
            self._refresh()
        self.root.after_idle(self.map_view.fit_map)

    def _restart(self):
        if self.campaign_started:
            self.campaign_started = False
            self.setup_country_confirmed = False
            self.move_undo = None
            self.attacked_unit_ids.clear()
            self.pending_player_country_id = self.player_country_id
            self.model.phase = "setup"
            self.selected_unit = None
            self.attack_target = None
            self.message = "Choose a country, then restart the campaign."
            self._refresh()
            return
        self.player_country_id = self.pending_player_country_id
        self._reset_campaign("Campaign started as {}.".format(
            self.model.country_name(self.player_country_id)))

    def _reset_campaign(self, message):
        self.model = GameModel(self.map_data, self.player_country_id)
        self.player_country_id = self.model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = True
        self.setup_page_active = False
        self.setup_country_confirmed = True
        self.resource_country_id = self.player_country_id
        self.selected_unit = next(
            (unit for unit in self.model.units if unit.owner == self.player_country_id), None)
        self.selected_hex = (self.selected_unit.position if self.selected_unit else
                             next(city["position"] for city in self.model.cities.values()
                                  if city["owner"] == self.player_country_id))
        self.attack_target = None
        self.result_shown = False
        self.move_undo = None
        self.attacked_unit_ids.clear()
        self.message = message
        self.history = []
        self._log("Campaign started as {}.".format(
            self.model.country_name(self.player_country_id)))
        self.map_view.model = self.model
        self.map_view.fit_map(draw=False)
        self._refresh()

    def _load_map_records(self):
        self.map_records = []
        try:
            filenames = sorted(
                (filename for filename in os.listdir(self.maps_directory)
                 if filename.lower().endswith(".json")), key=str.lower)
        except OSError:
            filenames = []
        for filename in filenames:
            path = os.path.join(self.maps_directory, filename)
            stem = os.path.splitext(filename)[0]
            name = stem.replace("_", " ").replace("-", " ").title()
            if len(stem) <= 3:
                name = stem.upper()
            record = {"name": name, "path": path, "data": None, "error": None}
            try:
                record["data"] = load_map_file(path)
                GameModel(record["data"])
            except (OSError, ValueError, TypeError, KeyError) as error:
                record["error"] = str(error)
            self.map_records.append(record)

        self.map_list.delete(0, tk.END)
        self.map_list._language_original_items = []
        for record in self.map_records:
            label = record["name"]
            if record["error"]:
                label += "  [INVALID]"
            self.map_list._language_original_items.append(label)
            self.map_list.insert(tk.END, translate(label, self.language))

    def _enter_campaign(self):
        self._load_map_records()
        default_path = os.path.join(self.maps_directory, "default_map.json")
        record = next((item for item in self.map_records
                       if os.path.normcase(os.path.abspath(item["path"])) ==
                       os.path.normcase(os.path.abspath(default_path)) and
                       not item["error"]), None)
        if record is None:
            record = next((item for item in self.map_records if not item["error"]), None)
        if record is None:
            self.message = "No playable maps were found."
            self.status_var.set(self.message)
            return
        self.setup_page_active = True
        if not self._apply_map_record(record):
            self.setup_page_active = False
            return
        if self._entry_page is not None:
            self._entry_page.destroy()
            self._entry_page = None
        self._select_map_in_sidebar(record)
        self._refresh()

    def _open_map_selector(self):
        if self.campaign_started and self.model.phase == ENEMY:
            return
        if not self.map_records:
            self._load_map_records()
        if self.campaign_started:
            self._exit_to_country()
        else:
            self.setup_page_active = True
            self._refresh()

    def _on_map_list_selected(self, event=None):
        if self._updating_map_list:
            return
        selection = self.map_list.curselection()
        if not selection:
            self._selected_map_record = None
            self.map_sidebar_status.set("Select a playable map.")
            self.load_save_button.configure(state="disabled")
            return
        record = self.map_records[selection[0]]
        self._selected_map_record = record
        if record["error"]:
            self.map_sidebar_status.set(
                "This map cannot be played.\n{}".format(record["error"]))
            self.load_save_button.configure(state="disabled")
            return
        data = record["data"]
        self.map_sidebar_status.set(
            "{} x {} hexes\n{} countries / {} cities\n{} starting units".format(
                data["columns"], data["rows"], len(data["countries"]),
                len(data["cities"]), len(data["units"])))
        self.load_save_button.configure(
            state="normal" if os.path.isfile(
                self._save_path_for_map(record["path"])) else "disabled")
        self._apply_map_record(record)

    def _select_map_in_sidebar(self, record):
        self._selected_map_record = record
        self._updating_map_list = True
        try:
            index = self.map_records.index(record)
            self.map_list.selection_clear(0, tk.END)
            self.map_list.selection_set(index)
            self.map_list.activate(index)
            self.map_list.see(index)
        finally:
            self._updating_map_list = False
        data = record["data"]
        self.map_sidebar_status.set(
            "{} x {} hexes\n{} countries / {} cities\n{} starting units".format(
                data["columns"], data["rows"], len(data["countries"]),
                len(data["cities"]), len(data["units"])))
        self.load_save_button.configure(
            state="normal" if os.path.isfile(
                self._save_path_for_map(record["path"])) else "disabled")

    def _load_selected_save(self):
        record = self._selected_map_record
        if record and not record["error"] and self._load_campaign_save(record):
            self.setup_page_active = False
            if self._entry_page is not None:
                self._entry_page.destroy()
                self._entry_page = None
            self._refresh()

    def _save_path_for_map(self, map_path):
        stem = os.path.splitext(os.path.basename(map_path))[0]
        return os.path.join(self.saves_directory, stem + ".json")

    def _campaign_save_data(self):
        units = []
        for unit in self.model.units:
            statuses = []
            for status in unit.statuses:
                if isinstance(status, MoraleBoost):
                    statuses.append({"type": "MoraleBoost",
                                     "rounds_left": status.rounds_left})
                elif isinstance(status, OverextendedMorale):
                    statuses.append({"type": "OverextendedMorale"})
            units.append({
                "id": unit.id,
                "kind": unit.kind,
                "owner": unit.owner,
                "faction": unit.faction,
                "position": list(unit.position),
                "hp": unit.hp,
                "attack": unit.attack,
                "range": unit.range,
                "movement": unit.movement,
                "base_movement": unit.base_movement,
                "movement_left": unit.movement_left,
                "unattacked_rounds": unit.unattacked_rounds,
                "attacked_this_round": unit.attacked_this_round,
                "movement_extended": unit.movement_extended,
                "attacks_per_turn": unit.attacks_per_turn,
                "attacks_left": unit.attacks_left,
                "embarked": unit.embarked,
                "statuses": statuses,
            })
        return {
            "version": 1,
            "map": os.path.basename(self.current_map_path),
            "player_country_id": self.player_country_id,
            "turn": self.model.turn,
            "winner": self.model.winner,
            "countries": {
                country_id: dict(country["resources"])
                for country_id, country in self.model.countries.items()},
            "cities": [
                {"position": list(position), "owner": city["owner"],
                 "health": city["health"], "max_health": city["max_health"],
                 "attacked_this_round": city.get("attacked_this_round", False)}
                for position, city in self.model.cities.items()],
            "units": units,
            "history": self.history[:40],
        }

    def _save_campaign(self):
        if (not self.campaign_started or self.ai_running or
                self.model.phase not in (PLAYER, "over")):
            return
        data = self._campaign_save_data()
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        if encoded == self._last_saved_payload:
            return
        path = self._save_path_for_map(self.current_map_path)
        temporary_path = path + ".tmp"
        try:
            if not os.path.isdir(self.saves_directory):
                os.makedirs(self.saves_directory)
            with open(temporary_path, "w") as save_file:
                json.dump(data, save_file, indent=2, sort_keys=True)
            os.replace(temporary_path, path)
        except (IOError, OSError):
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)
            except OSError:
                pass
            return
        self._last_saved_payload = encoded

    def _load_campaign_save(self, record):
        try:
            path = self._save_path_for_map(record["path"])
            with open(path, "r") as save_file:
                saved = json.load(save_file)
            player_id = saved["player_country_id"]
            model = GameModel(record["data"], player_id)
            for country_id, resources in saved["countries"].items():
                if country_id in model.countries:
                    model.countries[country_id]["resources"].update(resources)
            for saved_city in saved["cities"]:
                position = tuple(saved_city["position"])
                city = model.cities[position]
                city["owner"] = saved_city["owner"]
                city["health"] = saved_city["health"]
                city["max_health"] = saved_city["max_health"]
                city["attacked_this_round"] = saved_city.get(
                    "attacked_this_round", False)

            model.units = []
            model.units_by_position = {}
            next_unit_id = 1
            for saved_unit in saved["units"]:
                position = tuple(saved_unit["position"])
                unit = Unit(saved_unit["kind"], saved_unit["owner"], position,
                            saved_unit.get("faction"))
                unit.id = int(saved_unit["id"])
                unit.hp = saved_unit["hp"]
                unit.attack = saved_unit["attack"]
                unit.range = saved_unit["range"]
                unit.movement = saved_unit["movement"]
                unit.movement_extended = saved_unit.get("movement_extended", False)
                unit.base_movement = saved_unit.get(
                    "base_movement", unit.movement // 3
                    if unit.movement_extended else unit.movement)
                unit.movement_left = saved_unit["movement_left"]
                unit.unattacked_rounds = saved_unit.get("unattacked_rounds", 0)
                unit.attacked_this_round = saved_unit.get(
                    "attacked_this_round", False)
                unit.attacks_per_turn = saved_unit["attacks_per_turn"]
                unit.attacks_left = saved_unit["attacks_left"]
                unit.embarked = saved_unit["embarked"]
                for status_data in saved_unit.get("statuses", ()):
                    if status_data.get("type") == "MoraleBoost":
                        status = MoraleBoost()
                        status.rounds_left = status_data["rounds_left"]
                        unit.statuses.append(status)
                    elif status_data.get("type") == "OverextendedMorale":
                        unit.statuses.append(OverextendedMorale())
                model._add_unit(unit)
                next_unit_id = max(next_unit_id, unit.id + 1)
            Unit.next_id = max(Unit.next_id, next_unit_id)
            model.turn = saved["turn"]
            model.winner = saved.get("winner")
            model.phase = "over" if model.winner else PLAYER
            refresh_tactical_statuses(model)
        except (IOError, OSError, ValueError, TypeError, KeyError) as error:
            self.message = "Unable to load saved campaign: {}".format(error)
            self.status_var.set(self.message)
            return False

        self.model = model
        self.map_data = record["data"]
        self.current_map_path = record["path"]
        self.current_map_name = record["name"]
        self.player_country_id = model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = True
        self.setup_page_active = False
        self.setup_country_confirmed = True
        self.resource_country_id = self.player_country_id
        self.selected_unit = next(
            (unit for unit in model.units if unit.owner == self.player_country_id), None)
        self.selected_hex = (self.selected_unit.position if self.selected_unit else
                             next(iter(model.cities)))
        self.attack_target = None
        self.result_shown = False
        self.move_undo = None
        self.attacked_unit_ids.clear()
        self.history = saved.get("history", [])
        self.message = "Loaded saved campaign: {}.".format(self.current_map_name)
        self.map_view.model = model
        self.map_view.fit_map(draw=False)
        self._last_saved_payload = None
        self._refresh()
        if model.winner:
            self._announce_result()
        return True

    def _apply_map_record(self, record):
        try:
            map_data = record["data"]
            model = GameModel(map_data, self.player_country_id)
        except (OSError, ValueError, TypeError, KeyError) as error:
            messagebox.showerror(translate("Unable to load map", self.language),
                                 str(error), parent=self.root)
            return False

        self.model = model
        self.map_data = map_data
        self.current_map_path = record["path"]
        self.current_map_name = record["name"]
        self.player_country_id = model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.setup_page_active = True
        self.setup_country_confirmed = False
        self.move_undo = None
        self.attacked_unit_ids.clear()
        self.model.phase = "setup"
        self.resource_country_id = self.player_country_id
        self.selected_unit = None
        self.selected_hex = next(city["position"] for city in model.cities.values()
                                 if city["owner"] == self.player_country_id)
        self.attack_target = None
        self.result_shown = False
        self.message = "{} loaded. Choose a country, then start the campaign.".format(
            self.current_map_name)
        self.history = []
        self._log("{} map selected. Choose a country to begin.".format(
            self.current_map_name))
        self.map_view.model = model
        self.map_view.fit_map(draw=False)
        self._refresh()
        return True

    def _refresh(self):
        self.map_view.allow_low_detail_interaction = not self.campaign_started
        self.map_view.force_overview = not self.campaign_started
        account_country_id = (self.player_country_id if self.campaign_started else
                              self.pending_player_country_id)
        if (self.resource_country_id not in self.model.countries or
                self.model.faction_for(self.resource_country_id) !=
                self.model.faction_for(account_country_id)):
            self.resource_country_id = account_country_id
        resources = self.model.countries[self.resource_country_id]["resources"]
        income = self.model.income_for(self.resource_country_id)
        maintenance = self.model.unit_maintenance_for(self.resource_country_id)
        for resource in ("money", "steel", "technology"):
            self.stat_vars[resource].set(str(resources[resource]))
            self.income_vars[resource].set("+{}".format(income[resource]))
            self.maintenance_vars[resource].set(
                "-{}".format(maintenance[resource]))

        player_income = self.model.income_for(self.model.player_faction)
        enemy_income = self.model.income_for(self.model.enemy_faction)
        player_hp = sum(unit.hp for unit in self.model.units
                        if unit.faction == self.model.player_faction)
        enemy_hp = sum(unit.hp for unit in self.model.units
                       if unit.faction == self.model.enemy_faction)
        self.debug_income_comparison.set(
            "P/E $ {} / {} S {} / {} T {} / {}".format(
                player_income["money"], enemy_income["money"],
                player_income["steel"], enemy_income["steel"],
                player_income["technology"], enemy_income["technology"]))
        self.debug_hp_comparison.set("HP P/E {} / {}".format(
            player_hp, enemy_hp))

        city = self.model.cities.get(self.selected_hex)
        unit = self.model.unit_at(self.selected_hex)
        self.hex_info_panel.place_forget()

        selected_unit = (self.selected_unit if self.selected_unit in self.model.units else None)
        can_start_turn_action = (
            self.campaign_started and self.model.phase == PLAYER and
            not self.ai_running and not self.full_ai_mode)
        if self.full_ai_mode:
            pause_label = ("Pausing..." if self.full_ai_paused and self.ai_running
                           else "Continue" if self.full_ai_paused else "Pause")
            self.end_turn_button.configure(
                text=translate(pause_label, self.language),
                command=self._toggle_full_ai_pause,
                state="disabled" if self.full_ai_paused and self.ai_running
                else "normal")
            self.auto_button.configure(
                text=translate("Exit full AI", self.language),
                command=self._stop_full_ai, state="normal")
        else:
            self.end_turn_button.configure(
                text=translate("End turn  >", self.language),
                command=self._end_turn,
                state="normal" if can_start_turn_action else "disabled")
            self.auto_button.configure(
                text=translate("Auto", self.language),
                command=self._auto_player_turn,
                state="normal" if can_start_turn_action else "disabled")
        self.settings_button.configure(
            state="disabled" if self.ai_running or self.full_ai_mode else "normal")
        self.end_turn_button.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")
        self.unit_info_button.place_forget()
        self.city_recruit_button.place_forget()
        self.undo_move_button.place_forget()
        can_recruit = (self.campaign_started and not self.ai_running and
                   not self.full_ai_mode and
                   self.model.phase == PLAYER and city and
                       city["owner"] == self.player_country_id)
        can_undo_move = (
            self.campaign_started and not self.full_ai_mode and
            self.model.phase == PLAYER and
            selected_unit is not None and
            self.move_undo is not None and
            self.move_undo[0] is not None and
            selected_unit.id == self.move_undo[1] and
            self.move_undo[1] not in self.attacked_unit_ids)
        action_buttons = []
        if unit and not self.full_ai_mode:
            action_buttons.append(self.unit_info_button)
        if can_recruit:
            action_buttons.append(self.city_recruit_button)
        if can_undo_move:
            action_buttons.append(self.undo_move_button)
        first_offset = -16 * (len(action_buttons) - 1)
        for index, button in enumerate(action_buttons):
            button.place(relx=0.5, rely=1.0,
                         x=first_offset + index * 32, y=-3, anchor="s")
        self.map_view.set_selection(
            self.selected_hex,
            selected_unit if self.campaign_started else None,
            self.attack_target if self.campaign_started else None)
        self.status_var.set(self.message)
        if self.debug_mode:
            self.status_label.place(x=10, rely=1.0, y=-8, anchor="sw")
            self.status_label.lift()
        else:
            self.status_label.place_forget()
        if self.campaign_started:
            self.map_sidebar.pack_forget()
            self.resource_strip.place(x=0, y=0, relwidth=1.0, height=36)
            if self.debug_mode:
                self.debug_comparison.pack(side="right", padx=(0, 8),
                                           before=self.settings_button)
            else:
                self.debug_comparison.pack_forget()
            self.auto_button.place(relx=1.0, x=-8, y=40, anchor="ne")
        elif self.setup_page_active:
            self.resource_strip.place_forget()
            self.debug_comparison.pack_forget()
            self.auto_button.place_forget()
            if not self.map_sidebar.winfo_manager():
                self.map_sidebar.pack(side="right", fill="y")
        else:
            self.resource_strip.place_forget()
            self.debug_comparison.pack_forget()
            self.auto_button.place_forget()
            self.map_sidebar.pack_forget()
        self._save_campaign()

    def _update_map_info(self, city, unit):
        if (self.selected_hex not in self.model.tiles or
                (unit is not None and city is None and not self.campaign_started)):
            self.hex_info_panel.place_forget()
            return

        terrain = self.model.tiles[self.selected_hex]
        coordinate = self._coord_label(self.selected_hex)
        if city:
            production = self.model.city_production(city)
            self.hex_info_title.set(city["name"])
            owner_text = self.model.country_name(city["owner"])
            if self.debug_mode:
                owner_text = "{}  /  {}  /  Hex {}".format(
                    owner_text, terrain, coordinate)
            self.hex_info_owner.set(owner_text)
            self.hex_info_details.set(
                "HP: {}/{}\nCity Lv {}  |  Industry Lv {}  |  Research Lv {}\n"
                "Money +{}  |  Steel +{}  |  Tech +{} / turn".format(
                    city["health"], city["max_health"], city["city_level"],
                    city["industry_level"], city["research_level"],
                    production["money"], production["steel"],
                    production["technology"]))
            self.hex_info_panel.place(x=8, y=44, anchor="nw")
            self.hex_info_panel.lift()
            return
        elif unit:
            unit_name = "Transport ship ({})".format(unit.kind) if unit.embarked else unit.kind
            self.hex_info_title.set(unit_name)
            owner_text = self.model.country_name(unit.owner)
            if self.debug_mode:
                owner_text = "{}  /  {}  /  Hex {}".format(
                    owner_text, terrain, coordinate)
            self.hex_info_owner.set(owner_text)
            self.hex_info_details.set("HP: {}/{}".format(unit.hp, unit.max_hp))
        elif self.debug_mode:
            self.hex_info_title.set(terrain)
            self.hex_info_owner.set("Hex {}".format(coordinate))
            self.hex_info_details.set("")
        else:
            self.hex_info_panel.place_forget()
            return
        self.hex_info_panel.place(x=8, y=44, anchor="nw")
        self.hex_info_panel.lift()

    @staticmethod
    def _coord_label(position):
        return "{}-{}".format(position[0] + 1, position[1] + 1)

def run_app():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()