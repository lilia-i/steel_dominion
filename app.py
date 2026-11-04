import os
import tkinter as tk
from tkinter import messagebox, ttk

from game_config import ENEMY, NEUTRAL, PLAYER
from game_model import GameModel
from game_dialogs import (
    CountryChoiceDialog,
    RecruitDialog,
    SettingsDialog,
    UnitInfoDialog,
)
from hex_map import HexMapView
from map_data import load_map_file


INK = "#202c27"
MUTED = "#768078"
PAPER = "#e8e7df"
GREEN = "#47745f"


class GameApp(object):
    def __init__(self, root):
        self.root = root
        self.root.title("Steel Dominion | Hex Campaign")
        self.root.geometry("640x420")
        self.root.minsize(640, 420)
        self.root.configure(bg=PAPER)

        self.maps_directory = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "maps")
        self.current_map_path = os.path.join(self.maps_directory, "default_map.json")
        self.current_map_name = "Default Map"
        self.map_data = None
        self.model = GameModel()
        self.player_country_id = self.model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.setup_country_confirmed = False
        self.debug_mode = False
        self.model.phase = "setup"
        self.resource_country_id = self.player_country_id
        self.selected_hex = (2, 4)
        self.selected_unit = None
        self.attack_target = None
        self.result_shown = False
        self.history = []
        self.message = "Choose your country, then start the campaign."
        self._build_ui()
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
        self.income_vars = {key: tk.StringVar(value="+0/turn")
                    for key in ("money", "steel", "technology")}
        self.map_view = HexMapView(
            self.root, self.model, self._on_hex_click,
            bg="#dfe7df", highlightthickness=0, cursor="fleur")
        self.map_view.pack(fill="both", expand=True)

        resource_strip = tk.Frame(self.root, bg="#d9ddd5", height=36,
                                  highlightthickness=1, highlightbackground="#c9cec4")
        resource_strip.place(x=0, y=0, relwidth=1.0, height=36)
        for key, label, symbol, accent in (
            ("money", "MONEY", "$", "#aa8437"),
            ("steel", "STEEL", "S", "#54747a"),
            ("technology", "TECH", "T", "#47745f")):
            cell = tk.Frame(resource_strip, bg="#d9ddd5")
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
        self.settings_button = ttk.Button(
            resource_strip, text="Settings", command=self._show_settings)
        self.settings_button.pack(side="right", padx=8, pady=3)

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
        self.end_turn_button = ttk.Button(
            self.map_view, text="End turn  >", style="Accent.TButton",
            command=self._end_turn)
        self.status_var = tk.StringVar(value=self.message)
        self.status_label = tk.Label(
            self.map_view, textvariable=self.status_var, anchor="w", padx=8, pady=4,
            bg="#f4f3ed", fg="#526057", font=("Segoe UI", 9))

    def _log(self, message):
        self.history.insert(0, "T{:02d}  {}".format(self.model.turn, message))
        del self.history[40:]

    def _show_settings(self):
        SettingsDialog(
            self.root, self.model, self.player_country_id,
            self.pending_player_country_id, self.resource_country_id,
            self.campaign_started, self.current_map_name, self.history,
            self.debug_mode, self.attack_target,
            self._on_settings_resource_selected, self._open_map_selector,
            self._settings_campaign_action, self._restart, self._attack,
            self._cancel_attack, self._on_debug_changed)

    def _on_debug_changed(self, enabled):
        self.debug_mode = bool(enabled)
        self._refresh()

    def _on_hex_click(self, position):
        if not self.campaign_started:
            if not self.setup_country_confirmed:
                city = self.model.city_for_hex(position)
                if city and self.model.faction_for(city["owner"]) != NEUTRAL:
                    CountryChoiceDialog(
                        self.root, self.model, city["owner"],
                        self._on_setup_country_confirmed)
                return
            self.selected_hex = position
            self.selected_unit = None
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
            if position in self.model.movement_paths(self.selected_unit):
                moved, events = self.model.move(self.selected_unit, position)
                self._show_events(events)
                if moved:
                    self.selected_hex = position
                    self.message = events[-1]
                    self._announce_result()
                else:
                    self.message = events[-1]
                self.attack_target = None
                self._refresh()
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
        if (not self.campaign_started or self.model.phase != PLAYER or not city or
                city["owner"] != self.player_country_id):
            return
        RecruitDialog(self.root, self.model, city, self.player_country_id,
                      self.campaign_started, self._on_recruited)

    def _on_recruited(self, unit, message):
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
        self.player_country_id = country_id
        self._reset_campaign("Campaign started as {}.".format(
            self.model.country_name(country_id)))

    def _attack(self):
        if not self.selected_unit or self.attack_target is None:
            return
        attacked, events = self.model.attack(self.selected_unit, self.attack_target)
        self._show_events(events)
        if attacked:
            self.message = events[0]
            self.attack_target = None
            self._announce_result()
        else:
            self.message = events[-1]
        self._refresh()

    def _cancel_attack(self):
        self.attack_target = None
        self.message = "Target cleared."
        self._refresh()

    def _settings_campaign_action(self):
        if self.campaign_started:
            self._reset_campaign("Campaign restarted as {}.".format(
                self.model.country_name(self.player_country_id)))
        else:
            self._restart()

    def _end_turn(self):
        if not self.campaign_started or self.model.phase != PLAYER:
            return
        self.model.phase = ENEMY
        self.message = "AI forces are taking their turn..."
        self._refresh()
        self.root.after(450, self._run_enemy_turn)

    def _run_enemy_turn(self):
        events, winner = self.model.enemy_turn()
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

    def _show_events(self, events):
        for event in events:
            self._log(event)

    def _announce_result(self):
        if not self.model.winner or self.result_shown:
            return
        self.result_shown = True
        if self.model.winner == PLAYER:
            self.message = "Victory: all opposing cities have been captured."
            title = "Campaign victory"
        else:
            self.message = "Defeat: all of your faction's cities have fallen."
            title = "Campaign lost"
        self._refresh()
        messagebox.showinfo(title, self.message)

    def _restart(self):
        if self.campaign_started:
            self.campaign_started = False
            self.setup_country_confirmed = False
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
        self.setup_country_confirmed = True
        self.resource_country_id = self.player_country_id
        self.selected_unit = next(
            (unit for unit in self.model.units if unit.owner == self.player_country_id), None)
        self.selected_hex = (self.selected_unit.position if self.selected_unit else
                             next(city["position"] for city in self.model.cities.values()
                                  if city["owner"] == self.player_country_id))
        self.attack_target = None
        self.result_shown = False
        self.message = message
        self.history = []
        self._log("Campaign started as {}.".format(
            self.model.country_name(self.player_country_id)))
        self.map_view.model = self.model
        self.map_view.fit_map(draw=False)
        self._refresh()

    def _open_map_selector(self):
        if self.campaign_started and self.model.phase == ENEMY:
            return

        records = []
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
            records.append(record)

        dialog = tk.Toplevel(self.root)
        dialog.title("Choose campaign map")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.geometry("640x410")
        dialog.configure(bg=PAPER)

        header = tk.Frame(dialog, bg=INK, padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="SELECT CAMPAIGN MAP", bg=INK, fg="#f5f2e8",
                 font=("Georgia", 14, "bold")).pack(anchor="w")
        tk.Label(header, text="Choose a map from the maps folder.", bg=INK,
                 fg="#a9b3a9", font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        content = ttk.Frame(dialog, padding=(18, 16, 18, 10))
        content.pack(fill="both", expand=True)
        content.columnconfigure(1, weight=1)
        ttk.Label(content, text="AVAILABLE MAPS").grid(row=0, column=0, sticky="w",
                                                       pady=(0, 6))
        ttk.Label(content, text="MAP INTEL").grid(row=0, column=1, sticky="w",
                                                  padx=(18, 0), pady=(0, 6))

        list_frame = ttk.Frame(content)
        list_frame.grid(row=1, column=0, sticky="nsew")
        map_list = tk.Listbox(list_frame, width=24, height=13, exportselection=False,
                              activestyle="none", borderwidth=0, highlightthickness=1,
                              highlightbackground="#c9cec4", bg="#f4f3ed", fg=INK,
                              selectbackground=GREEN, selectforeground="white",
                              font=("Segoe UI", 10))
        map_scroll = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=map_list.yview)
        map_list.configure(yscrollcommand=map_scroll.set)
        map_list.pack(side="left", fill="both", expand=True)
        map_scroll.pack(side="right", fill="y")

        preview = ttk.LabelFrame(content, text="", padding=14)
        preview.grid(row=1, column=1, sticky="nsew", padx=(18, 0))
        preview_name = tk.StringVar(value="Select a map")
        preview_details = tk.StringVar(value="")
        ttk.Label(preview, textvariable=preview_name,
                  font=("Georgia", 16, "bold")).pack(anchor="w", pady=(4, 10))
        ttk.Label(preview, textvariable=preview_details, justify="left",
                  wraplength=275, style="Muted.TLabel").pack(anchor="w")

        selected_record = [None]
        for record in records:
            label = record["name"]
            if record["error"]:
                label += "  [INVALID]"
            map_list.insert(tk.END, label)

        def update_preview(event=None):
            selection = map_list.curselection()
            if not selection:
                selected_record[0] = None
                preview_name.set("No maps found")
                preview_details.set("Add playable .json maps to the maps folder.")
                choose_button.configure(state="disabled")
                return
            record = records[selection[0]]
            selected_record[0] = record
            preview_name.set(record["name"])
            if record["error"]:
                preview_details.set("This map cannot be played.\n\n{}".format(
                    record["error"]))
                choose_button.configure(state="disabled")
                return
            data = record["data"]
            neutral_count = sum(1 for country in data["countries"]
                                if country["faction"] == NEUTRAL)
            preview_details.set(
                "{} x {} hexes\n{} countries ({} neutral)\n"
                "{} cities / {} starting units\n{} rivers".format(
                    data["columns"], data["rows"], len(data["countries"]),
                    neutral_count, len(data["cities"]), len(data["units"]),
                    len(data["rivers"])))
            choose_button.configure(state="normal")

        def choose_map():
            record = selected_record[0]
            if record and not record["error"] and self._apply_map_record(record):
                dialog.destroy()

        map_list.bind("<<ListboxSelect>>", update_preview)
        map_list.bind("<Double-Button-1>", lambda event: choose_map())
        actions = ttk.Frame(dialog, padding=(18, 0, 18, 16))
        actions.pack(fill="x")
        choose_button = ttk.Button(actions, text="Use map", style="Accent.TButton",
                                   command=choose_map)
        choose_button.pack(side="right")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(
            side="right", padx=(0, 8))

        if records:
            current_path = os.path.normcase(os.path.abspath(self.current_map_path))
            initial_index = next((index for index, record in enumerate(records)
                                  if os.path.normcase(os.path.abspath(record["path"])) ==
                                  current_path), 0)
            map_list.selection_set(initial_index)
            map_list.activate(initial_index)
            map_list.see(initial_index)
        update_preview()
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.grab_set()

    def _apply_map_record(self, record):
        try:
            map_data = record["data"]
            model = GameModel(map_data, self.player_country_id)
        except (OSError, ValueError, TypeError, KeyError) as error:
            messagebox.showerror("Unable to load map", str(error), parent=self.root)
            return False

        self.model = model
        self.map_data = map_data
        self.current_map_path = record["path"]
        self.current_map_name = record["name"]
        self.player_country_id = model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.setup_country_confirmed = False
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
        account_country_id = (self.player_country_id if self.campaign_started else
                              self.pending_player_country_id)
        if (self.resource_country_id not in self.model.countries or
                self.model.faction_for(self.resource_country_id) !=
                self.model.faction_for(account_country_id)):
            self.resource_country_id = account_country_id
        resources = self.model.countries[self.resource_country_id]["resources"]
        income = self.model.income_for(self.resource_country_id)
        for resource in ("money", "steel", "technology"):
            self.stat_vars[resource].set(str(resources[resource]))
            self.income_vars[resource].set("+{}/turn".format(income[resource]))

        city = self.model.cities.get(self.selected_hex)
        unit = self.model.unit_at(self.selected_hex)
        self._update_map_info(city, unit)

        selected_unit = (self.selected_unit if self.selected_unit in self.model.units else None)
        self.end_turn_button.configure(
            state="normal" if self.campaign_started and self.model.phase == PLAYER
            else "disabled")
        self.end_turn_button.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")
        self.unit_info_button.place_forget()
        self.city_recruit_button.place_forget()
        can_recruit = (self.campaign_started and self.model.phase == PLAYER and city and
                       city["owner"] == self.player_country_id)
        if unit or can_recruit:
            unit_offset = -16 if can_recruit else 0
            city_offset = 16 if unit else 0
        if unit:
            self.unit_info_button.place(
                relx=0.5, rely=1.0, x=unit_offset, y=-3, anchor="s")
        if can_recruit:
            self.city_recruit_button.place(
                relx=0.5, rely=1.0, x=city_offset, y=-3, anchor="s")
        self.map_view.set_selection(
            self.selected_hex if (self.campaign_started or
                                  self.setup_country_confirmed) else None,
            selected_unit if self.campaign_started else None,
            self.attack_target if self.campaign_started else None)
        self.status_var.set(self.message)
        if self.debug_mode:
            self.status_label.place(x=10, rely=1.0, y=-8, anchor="sw")
            self.status_label.lift()
        else:
            self.status_label.place_forget()

    def _update_map_info(self, city, unit):
        if not self.campaign_started or self.selected_hex not in self.model.tiles:
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