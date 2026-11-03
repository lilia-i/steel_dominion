import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from game_config import ENEMY, NEUTRAL, PLAYER, UNIT_TYPES
from game_model import GameModel
from hex_map import HexMapView
from map_data import load_map_file
from ui_helpers import ScrollableFrame


INK = "#202c27"
MUTED = "#768078"
PAPER = "#e8e7df"
GREEN = "#47745f"


class GameApp(object):
    def __init__(self, root):
        self.root = root
        self.root.title("Steel Dominion | Hex Campaign")
        self.root.geometry("1280x820")
        self.root.minsize(900, 620)
        self.root.configure(bg=PAPER)

        self.map_data = None
        self.model = GameModel()
        self.player_country_id = self.model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.model.phase = "setup"
        self.resource_country_id = self.player_country_id
        self.selected_hex = (2, 4)
        self.selected_unit = None
        self.attack_target = None
        self.result_shown = False
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
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", padding=(9, 7), font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background=GREEN, foreground="white")
        style.map("Accent.TButton", background=[("active", "#365b49"), ("disabled", "#aab5ad")])
        style.configure("TCombobox", padding=5)

        header = tk.Frame(self.root, bg=INK, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg=INK)
        brand.pack(side="left", padx=22, pady=12)
        tk.Label(brand, text="S", bg="#d0a44c", fg=INK, width=2,
                 font=("Georgia", 16, "bold")).pack(side="left", padx=(0, 12))
        title_box = tk.Frame(brand, bg=INK)
        title_box.pack(side="left")
        tk.Label(title_box, text="Steel Dominion", bg=INK, fg="#f5f2e8",
                 font=("Georgia", 17, "bold")).pack(anchor="w")
        tk.Label(title_box, text="EUROPEAN THEATER  /  1942", bg=INK, fg="#a9b3a9",
                 font=("Consolas", 9)).pack(anchor="w", pady=(2, 0))

        self.stat_vars = {}
        stats = tk.Frame(header, bg=INK)
        stats.pack(side="right", padx=24)
        for key, label in (("turn", "TURN"), ("cities", "CITIES"), ("money", "MONEY"),
                   ("steel", "STEEL"), ("technology", "TECH")):
            box = tk.Frame(stats, bg=INK)
            box.pack(side="left", padx=14, pady=14)
            tk.Label(box, text=label, bg=INK, fg="#a9b3a9",
                     font=("Consolas", 9)).pack(anchor="w")
            variable = tk.StringVar(value="-")
            self.stat_vars[key] = variable
            tk.Label(box, textvariable=variable, bg=INK, fg="#f5f2e8",
                     font=("Consolas", 14, "bold")).pack(anchor="w", pady=(3, 0))

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=14, pady=(14, 12))
        map_frame = ttk.Frame(body)
        sidebar_pane = ttk.Frame(body, width=286)
        body.add(map_frame, weight=4)
        body.add(sidebar_pane, weight=1)
        body.bind("<Configure>", lambda event: self._set_initial_sidebar_width(), add="+")
        self.main_splitter = body
        self._initial_sidebar_sash_set = False
        map_heading = ttk.Frame(map_frame)
        map_heading.pack(fill="x", pady=(0, 9))
        ttk.Label(map_heading, text="STRATEGIC MAP", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(map_heading, text="Wheel: zoom  |  Drag: pan  |  Gold ring: attack ready",
              style="Muted.TLabel").pack(side="right")
        self.map_view = HexMapView(
            map_frame, self.model, self._on_hex_click,
            bg="#dfe7df", highlightthickness=1, highlightbackground="#d2d6cd", cursor="fleur")
        self.map_view.pack(fill="both", expand=True)

        sidebar_scroll = ScrollableFrame(sidebar_pane, canvas_bg=PAPER)
        sidebar_scroll.pack(fill="both", expand=True)
        sidebar = sidebar_scroll.content
        self.sidebar_scroll = sidebar_scroll

        info = ttk.LabelFrame(sidebar, text="SECTOR INTEL", padding=12)
        info.pack(fill="x", pady=(0, 10))
        self.info_name = tk.StringVar(value="Unselected")
        ttk.Label(info, textvariable=self.info_name, font=("Georgia", 16, "bold")).pack(anchor="w")
        self.info_owner = tk.StringVar(value="Select a unit or city")
        ttk.Label(info, textvariable=self.info_owner, style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        self.info_details = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.info_details, justify="left", wraplength=240).pack(anchor="w")

        commands = ttk.LabelFrame(sidebar, text="COMMAND", padding=12)
        commands.pack(fill="x", pady=(0, 10))
        ttk.Label(commands, text="Play as country").pack(anchor="w", pady=(0, 3))
        self.player_country_var = tk.StringVar()
        self.player_country_choice = ttk.Combobox(
            commands, textvariable=self.player_country_var, state="readonly")
        self.player_country_choice.pack(fill="x", pady=(0, 8))
        self.player_country_choice.bind("<<ComboboxSelected>>",
                                       self._on_player_country_selected)
        ttk.Label(commands, text="Resource account").pack(anchor="w", pady=(0, 3))
        self.resource_country_var = tk.StringVar()
        self.country_choice = ttk.Combobox(
            commands, textvariable=self.resource_country_var, state="readonly")
        self.country_choice.pack(fill="x", pady=(0, 8))
        self.country_choice.bind("<<ComboboxSelected>>", self._on_country_selected)
        self.type_var = tk.StringVar(value="Infantry")
        self.unit_choice = ttk.Combobox(commands, textvariable=self.type_var,
                                        values=list(UNIT_TYPES.keys()), state="readonly")
        self.unit_choice.pack(fill="x", pady=(0, 8))
        self.unit_choice.bind("<<ComboboxSelected>>", self._update_unit_preview)
        self.unit_preview = tk.StringVar(value="")
        ttk.Label(commands, textvariable=self.unit_preview, style="Muted.TLabel",
              justify="left", wraplength=240).pack(fill="x", pady=(0, 7))
        self.recruit_button = ttk.Button(commands, text="Recruit at city", command=self._recruit)
        self.recruit_button.pack(fill="x", pady=3)
        self.attack_button = ttk.Button(commands, text="Attack target", style="Accent.TButton",
                                        command=self._attack)
        self.attack_button.pack(fill="x", pady=3)
        self.cancel_button = ttk.Button(commands, text="Clear target", command=self._cancel_attack)
        self.cancel_button.pack(fill="x", pady=3)
        self.end_button = ttk.Button(commands, text="End turn  >", command=self._end_turn)
        self.end_button.pack(fill="x", pady=(9, 3))
        self.load_map_button = ttk.Button(commands, text="Load map", command=self._load_map)
        self.load_map_button.pack(fill="x", pady=3)
        self.restart_button = ttk.Button(commands, text="Start campaign", command=self._restart)
        self.restart_button.pack(fill="x", pady=3)
        self._update_unit_preview()

        legend = ttk.LabelFrame(sidebar, text="UNIT ROSTER", padding=12)
        legend.pack(fill="x", pady=(0, 10))
        for kind, details in UNIT_TYPES.items():
            cost = details["cost"]
            ttk.Label(legend, text="{}  ATK {} RNG {} MP {}\nM {} / S {} / T {}".format(
                kind, details["attack"], details["range"], details["movement"],
                cost["money"], cost["steel"], cost["technology"]),
                style="Muted.TLabel").pack(anchor="w", pady=2)

        history = ttk.LabelFrame(sidebar, text="FIELD REPORT", padding=10)
        history.pack(fill="both", expand=True)
        self.log_box = tk.Listbox(history, height=7, borderwidth=0, highlightthickness=0,
                                  bg="#f4f3ed", fg="#46534b", font=("Segoe UI", 9),
                                  activestyle="none")
        self.log_box.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value=self.message)
        status = tk.Label(self.root, textvariable=self.status_var, anchor="w", padx=15, pady=7,
                          bg="#dcded5", fg="#526057", font=("Segoe UI", 9))
        status.pack(fill="x", side="bottom")

    def _set_initial_sidebar_width(self):
        if self._initial_sidebar_sash_set or self.main_splitter.winfo_width() <= 1:
            return
        self._initial_sidebar_sash_set = True
        self.main_splitter.sashpos(0, max(320, self.main_splitter.winfo_width() - 300))

    def _log(self, message):
        self.log_box.insert(0, "T{:02d}  {}".format(self.model.turn, message))
        while self.log_box.size() > 8:
            self.log_box.delete(tk.END)

    def _on_hex_click(self, position):
        if not self.campaign_started or self.model.phase != PLAYER:
            return
        unit = self.model.unit_at(position)
        if unit and unit.owner == self.player_country_id:
            self.selected_hex = position
            self.selected_unit = unit
            self.resource_country_id = unit.owner
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
                self.message = "Target marked. Use Attack target to engage."
                self._refresh()
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
        if city and self.model.faction_for(city["owner"]) == self.model.player_faction:
            self.resource_country_id = city["owner"]
        self.message = "{}: select a unit or recruit here.".format(city["name"]) if city else "Select one of your units."
        self._refresh()

    def _recruit(self):
        unit, message = self.model.recruit(self.selected_hex, self.type_var.get())
        self.message = message
        if unit:
            self.selected_unit = unit
            self.selected_hex = unit.position
            self._log(message)
        self._refresh()

    def _update_unit_preview(self, event=None):
        stats = UNIT_TYPES[self.type_var.get()]
        cost = stats["cost"]
        self.unit_preview.set(
            "ATK {}  |  Range {}  |  HP {}\nMovement {} MP\nCost: M {} / S {} / T {}".format(
                stats["attack"], stats["range"], stats["hp"],
                stats["movement"], cost["money"], cost["steel"], cost["technology"]))

    def _on_country_selected(self, event=None):
        selected_name = self.resource_country_var.get()
        self.resource_country_id = next(
            country_id for country_id, country in self.model.countries.items()
            if country["name"] == selected_name and
            country["faction"] == self.model.player_faction)
        self._refresh()

    def _on_player_country_selected(self, event=None):
        if self.campaign_started:
            self.player_country_var.set(self.model.country_name(self.player_country_id))
            return
        selected_name = self.player_country_var.get()
        selected_id = next(
            (country_id for country_id, country in self.model.countries.items()
             if country["name"] == selected_name and country["faction"] != NEUTRAL),
            None)
        if selected_id is None:
            return
        self.pending_player_country_id = selected_id
        self.message = "{} selected. Start the campaign to confirm.".format(selected_name)
        self._refresh()

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
        self.resource_country_id = self.player_country_id
        self.selected_unit = next(
            (unit for unit in self.model.units if unit.owner == self.player_country_id), None)
        self.selected_hex = (self.selected_unit.position if self.selected_unit else
                             next(city["position"] for city in self.model.cities.values()
                                  if city["owner"] == self.player_country_id))
        self.attack_target = None
        self.result_shown = False
        self.message = message
        self.log_box.delete(0, tk.END)
        self._log("Campaign started as {}.".format(
            self.model.country_name(self.player_country_id)))
        self.map_view.model = self.model
        self.map_view.fit_map(draw=False)
        self._refresh()

    def _load_map(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load custom map",
            filetypes=(("Steel Dominion map", "*.json"), ("All files", "*.*")))
        if not path:
            return
        try:
            map_data = load_map_file(path)
            model = GameModel(map_data, self.player_country_id)
        except (OSError, ValueError) as error:
            messagebox.showerror("Unable to load map", str(error), parent=self.root)
            return

        self.model = model
        self.map_data = map_data
        self.player_country_id = model.player_country_id
        self.pending_player_country_id = self.player_country_id
        self.campaign_started = False
        self.model.phase = "setup"
        self.resource_country_id = self.player_country_id
        self.selected_unit = None
        self.selected_hex = next(city["position"] for city in model.cities.values()
                                 if city["owner"] == self.player_country_id)
        self.attack_target = None
        self.result_shown = False
        self.message = "Custom map loaded. Choose your country, then start the campaign."
        self.log_box.delete(0, tk.END)
        self._log("Custom map loaded. Choose a country to begin.")
        self.map_view.model = model
        self.map_view.fit_map(draw=False)
        self._refresh()

    def _refresh(self):
        player_cities = self.model.owned_cities(self.player_country_id)
        self.stat_vars["turn"].set(str(self.model.turn))
        self.stat_vars["cities"].set("{} / {}".format(player_cities, len(self.model.cities)))
        player_countries = [country for country in self.model.countries.values()
                            if country["faction"] == self.model.faction_for(
                                self.player_country_id)]
        if (self.resource_country_id not in self.model.countries or
                self.model.faction_for(self.resource_country_id) !=
                self.model.faction_for(self.player_country_id)):
            self.resource_country_id = self.player_country_id
        self.country_choice.configure(values=[country["name"] for country in player_countries])
        self.country_choice.configure(state="readonly" if self.campaign_started else "disabled")
        self.resource_country_var.set(self.model.country_name(self.resource_country_id))
        playable_countries = [country for country in self.model.countries.values()
                              if country["faction"] != NEUTRAL]
        self.player_country_choice.configure(
            values=[country["name"] for country in playable_countries],
            state="disabled" if self.campaign_started else "readonly")
        display_country_id = (self.player_country_id if self.campaign_started else
                              self.pending_player_country_id)
        self.player_country_var.set(self.model.country_name(display_country_id))
        self.restart_button.configure(
            text="Restart campaign" if self.campaign_started else "Start campaign")
        resources = self.model.countries[self.resource_country_id]["resources"]
        for resource in ("money", "steel", "technology"):
            self.stat_vars[resource].set(str(resources[resource]))

        city = self.model.cities.get(self.selected_hex)
        unit = self.selected_unit if self.selected_unit in self.model.units else None
        if unit:
            side = self._country_control_label(unit.owner)
            if unit.attacks_left <= 0:
                action = "Turn spent"
            elif unit.movement_left > 0:
                action = "Move + attack ready"
            else:
                action = "Attack ready"
            display_name = "Transport ship ({})".format(unit.kind) if unit.embarked else unit.kind
            unit_state = "Afloat" if unit.embarked else action
            self.info_name.set(display_name)
            self.info_owner.set("{} / {}  |  {}".format(
                self.model.country_name(unit.owner), side, unit_state))
            self.info_details.set("Hex: {}\nStrength: {}/{}\nAttack: {:g} (base {})  |  Range: {}\nMovement: {}/{} MP\nAttacks: {}/{}".format(
                self._coord_label(unit.position), unit.hp, unit.max_hp,
                unit.effective_attack, unit.attack, unit.range,
                unit.movement_left, unit.movement, unit.attacks_left, unit.attacks_per_turn))
            if city:
                self.info_details.set(self.info_details.get() + "\n\n" + self._city_details(city))
        elif city:
            side = self._country_control_label(city["owner"])
            self.info_name.set(city["name"])
            self.info_owner.set("{} / {} controlled city".format(
                self.model.country_name(city["owner"]), side))
            self.info_details.set(self._city_details(city))
        else:
            terrain = self.model.tiles.get(self.selected_hex, "Unknown")
            self.info_name.set("Battlefield hex")
            self.info_owner.set(terrain)
            self.info_details.set("Coordinate: {}\nHills and forests reduce incoming damage.".format(
                self._coord_label(self.selected_hex)))

        can_command = (self.campaign_started and self.model.phase == PLAYER and unit and
               unit.owner == self.player_country_id and not unit.attacked)
        can_recruit = (self.campaign_started and self.model.phase == PLAYER and city and
               city["owner"] == self.player_country_id)
        can_attack = can_command and self.attack_target is not None
        self.recruit_button.configure(state="normal" if can_recruit else "disabled")
        self.attack_button.configure(state="normal" if can_attack else "disabled")
        self.cancel_button.configure(state="normal" if self.attack_target is not None else "disabled")
        self.end_button.configure(
            state="normal" if self.campaign_started and self.model.phase == PLAYER else "disabled")
        self.load_map_button.configure(
            state="normal" if self.campaign_started and self.model.phase in (PLAYER, "over")
            else "disabled")
        self.map_view.set_selection(
            self.selected_hex if self.campaign_started else None,
            unit if self.campaign_started else None,
            self.attack_target if self.campaign_started else None)
        self.status_var.set(self.message)

    @staticmethod
    def _coord_label(position):
        return "{}-{}".format(position[0] + 1, position[1] + 1)

    def _country_control_label(self, country_id):
        faction = self.model.faction_for(country_id)
        if faction == NEUTRAL:
            return "Neutral"
        if country_id == self.player_country_id:
            return "Player controlled"
        if faction == self.model.player_faction:
            return "AI ally"
        return "AI opponent"

    def _city_details(self, city):
        production = self.model.city_production(city)
        return ("HP: {}/{}\n"
            "City Lv {}: +{} money / turn\n"
                "Industry Lv {}: +{} steel / turn\n"
                "Research Lv {}: +{} tech / turn").format(
            city["health"], city["max_health"], city["city_level"], production["money"],
            city["industry_level"], production["steel"],
            city["research_level"], production["technology"])


def run_app():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()