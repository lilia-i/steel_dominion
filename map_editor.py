import colorsys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from game_config import (
    CITY_MAX_LEVEL,
    ENEMY,
    NEUTRAL,
    PLAYER,
    TERRAIN_COLORS,
    UNIT_TYPES,
    city_hp_for_level,
)
from hex_map import HexMapView, _country_colors
from i18n import (
    LocalizedStringVar,
    apply_language,
    load_language,
    set_language,
    translate,
)
from map_data import (
    MAX_MAP_SIZE,
    MIN_MAP_SIZE,
    hex_neighbors,
    load_map_file,
    new_map_data,
    save_map_file,
)
from ui_helpers import ScrollableFrame


INK = "#202c27"
PAPER = "#e8e7df"
ERASE_LAYERS = ("Unit", "Terrain", "Territory", "City", "River")


class EditorMapModel(object):
    def __init__(self, map_data):
        self.columns = map_data["columns"]
        self.rows = map_data["rows"]
        self.tiles = {
            (col, row): map_data["terrain"][row][col]
            for row in range(self.rows)
            for col in range(self.columns)
        }
        self.cities = {
            (city["col"], city["row"]): {
                "position": (city["col"], city["row"]),
                "name": city["name"],
                "owner": city["owner"],
                "city_level": city["city_level"],
                "industry_level": city["industry_level"],
                "research_level": city["research_level"],
                "health": city["health"],
                "max_health": city["max_health"],
            }
            for city in map_data["cities"]
        }
        self.territory_city = {
            (col, row): tuple(city_position)
            for row, territory_row in enumerate(map_data["territories"])
            for col, city_position in enumerate(territory_row)
            if city_position is not None
        }
        countries = {country["id"]: country for country in map_data["countries"]}
        self.countries = list(map_data["countries"])
        self.units = [
            EditorUnit(unit["type"], unit["owner"], countries[unit["owner"]]["faction"],
                       (unit["col"], unit["row"]))
            for unit in map_data["units"]
        ]
        self.units_by_position = {unit.position: unit for unit in self.units}
        self.river_edges = {
            frozenset((tuple(edge[0]), tuple(edge[1])))
            for edge in map_data["rivers"]
        }

    def unit_at(self, position):
        return self.units_by_position.get(position)

    def faction_for(self, country_id):
        return next(country["faction"] for country in self.countries
                    if country["id"] == country_id)

    def city_for_hex(self, position):
        city_position = self.territory_city.get(position)
        return self.cities.get(city_position)


class EditorUnit(object):
    def __init__(self, kind, owner, faction, position):
        self.kind = kind
        self.level = 1
        self.owner = owner
        self.faction = faction
        self.position = position
        self.hp = UNIT_TYPES[kind]["hp"]
        self.max_hp = self.hp
        self.attacked = False
        self.embarked = False


class MapEditorApp(object):
    clear_territory_label = "Unassigned (clear)"

    def __init__(self, root, on_close=None):
        self.root = root
        self.on_close = on_close
        self.root.title("Steel Dominion | Map Editor")
        self.root.geometry("1180x780")
        self.root.minsize(820, 560)
        self.root.configure(bg=PAPER)

        self.data = new_map_data()
        self.mode = tk.StringVar(value="Terrain")
        self.terrain = tk.StringVar(value="Forest")
        self.terrain_display = tk.StringVar(value=translate("Forest"))
        self.city_name = tk.StringVar(value="City")
        self.city_owner = tk.StringVar()
        self.city_level = tk.IntVar(value=1)
        self.industry_level = tk.IntVar(value=1)
        self.research_level = tk.IntVar(value=1)
        self.city_hp_preview = LocalizedStringVar(
            value="Maximum HP: {}".format(city_hp_for_level(1)))
        self.city_level.trace("w", self._update_city_hp_preview)
        self.selected_city_position = None
        self.selected_unit_position = None
        self.river_start = None
        self.territory_city_var = tk.StringVar()
        self.unit_kind = tk.StringVar(value="Infantry")
        self.unit_kind_display = tk.StringVar(value=translate("Infantry"))
        self.unit_owner = tk.StringVar()
        self.unit_selection_var = LocalizedStringVar(value="No unit selected")
        self.erase_layer = tk.StringVar(value="Unit")
        self.erase_layer_display = tk.StringVar(value=translate("Unit"))
        self.country_name = tk.StringVar()
        self.country_faction = tk.StringVar(value=PLAYER)
        self.country_faction_display = tk.StringVar(value=translate(PLAYER))
        self.country_war_entry_turn = tk.IntVar(value=1)
        self.country_hue = tk.DoubleVar(value=48)
        self.country_saturation = tk.DoubleVar(value=56)
        self.country_brightness = tk.DoubleVar(value=96)
        self.country_color_hex = tk.StringVar(value="#f4e36d")
        self.country_hue_label = tk.StringVar(value="Hue 48")
        self.country_saturation_label = tk.StringVar(value="Saturation 56%")
        self.country_brightness_label = tk.StringVar(value="Brightness 96%")
        self._loading_country_color = False
        self.country_resources = {
            key: tk.IntVar(value=0) for key in ("money", "steel", "technology")
        }
        self.selected_country_id = self.data["countries"][0]["id"]
        self._initial_fit_done = False
        self.columns = tk.IntVar(value=self.data["columns"])
        self.rows = tk.IntVar(value=self.data["rows"])
        self.status = LocalizedStringVar(
            value="Choose a tool, then click map hexes.")
        self._build_ui()
        self._replace_editor_model(fit=True)
        apply_language(self.root)

    def _close_editor(self):
        if self.on_close is not None:
            self.on_close()
        else:
            self.root.destroy()

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        style.configure("TButton", padding=(8, 6), font=("Segoe UI", 9, "bold"))

        header = tk.Frame(self.root, bg=INK, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="STEEL DOMINION  /  MAP EDITOR", bg=INK, fg="#f5f2e8",
                 font=("Georgia", 16, "bold")).pack(side="left", padx=20, pady=15)
        self.main_menu_button = ttk.Button(
            header, text="Back to main menu", command=self._close_editor)
        self.main_menu_button.pack(side="right", padx=16)

        body = ttk.Frame(self.root, padding=12)
        body.pack(fill="both", expand=True)
        splitter = ttk.Panedwindow(body, orient="horizontal")
        splitter.pack(fill="both", expand=True)
        sidebar_pane = ttk.Frame(splitter, width=270)
        sidebar_scroll = ScrollableFrame(sidebar_pane, canvas_bg=PAPER)
        sidebar_scroll.pack(fill="both", expand=True)
        sidebar = sidebar_scroll.content
        self.sidebar_scroll = sidebar_scroll
        self.splitter = splitter
        self._initial_sidebar_sash_set = False

        files = ttk.LabelFrame(sidebar, text="MAP FILE", padding=10)
        files.pack(fill="x", pady=(0, 10))
        ttk.Button(files, text="New blank map", command=self._new_map).pack(fill="x", pady=3)
        ttk.Button(files, text="Open map...", command=self._open_map).pack(fill="x", pady=3)
        ttk.Button(files, text="Save map...", command=self._save_map).pack(fill="x", pady=3)

        dimensions = ttk.LabelFrame(sidebar, text="SIZE", padding=10)
        dimensions.pack(fill="x", pady=(0, 10))
        size_row = ttk.Frame(dimensions)
        size_row.pack(fill="x", pady=(0, 7))
        ttk.Label(size_row, text="Columns").pack(side="left")
        tk.Spinbox(size_row, from_=MIN_MAP_SIZE, to=MAX_MAP_SIZE, width=4,
                   textvariable=self.columns).pack(side="right")
        ttk.Label(size_row, text="Rows").pack(side="left", padx=(12, 0))
        tk.Spinbox(size_row, from_=MIN_MAP_SIZE, to=MAX_MAP_SIZE, width=4,
                   textvariable=self.rows).pack(side="right")
        ttk.Button(dimensions, text="Apply size", command=self._resize_map).pack(fill="x")

        tools = ttk.Notebook(sidebar)
        tools.pack(fill="both", expand=True)
        edit_tab = ttk.Frame(tools, padding=8)
        country_tab = ttk.Frame(tools, padding=8)
        tools.add(edit_tab, text="Edit")
        tools.add(country_tab, text="Countries")
        self.tools = tools

        for label in ("Terrain", "City", "Territory", "River", "Unit", "Erase"):
            ttk.Radiobutton(edit_tab, text=label, value=label, variable=self.mode,
                            command=self._update_tool_state).pack(anchor="w", pady=2)

        self.terrain_controls = ttk.Frame(edit_tab)
        self.terrain_controls.pack(fill="x")
        self.terrain_choice = ttk.Combobox(
            self.terrain_controls, textvariable=self.terrain_display,
            values=self._sorted_translations(TERRAIN_COLORS),
            state="readonly")
        self.terrain_choice.pack(fill="x", pady=(5, 8))
        self.terrain_choice.bind("<<ComboboxSelected>>", self._select_terrain)

        self.city_controls = ttk.Frame(edit_tab)
        self.city_controls.pack(fill="x")
        ttk.Label(self.city_controls, text="City name").pack(anchor="w")
        self.city_name_entry = ttk.Entry(self.city_controls, textvariable=self.city_name)
        self.city_name_entry.pack(fill="x", pady=(3, 7))
        ttk.Label(self.city_controls, text="City country").pack(anchor="w")
        self.city_owner_choice = ttk.Combobox(self.city_controls, textvariable=self.city_owner,
                                              state="readonly")
        self.city_owner_choice.pack(fill="x", pady=(0, 5))
        city_level_row = ttk.Frame(self.city_controls)
        city_level_row.pack(fill="x", pady=(0, 8))
        ttk.Label(city_level_row, text="City level").pack(side="left")
        self.city_level_spin = tk.Spinbox(
            city_level_row, from_=1, to=CITY_MAX_LEVEL, width=4,
            textvariable=self.city_level, command=self._update_city_hp_preview)
        self.city_level_spin.pack(side="right")
        production_levels = ttk.Frame(self.city_controls)
        production_levels.pack(fill="x", pady=(0, 5))
        for label, variable, attribute in (
                ("Industry", self.industry_level, "industry_level_spin"),
                ("Research", self.research_level, "research_level_spin")):
            level_group = ttk.Frame(production_levels)
            level_group.pack(side="left", expand=True, fill="x")
            ttk.Label(level_group, text=label).pack(side="left")
            spinbox = tk.Spinbox(level_group, from_=0, to=99, width=3,
                                 textvariable=variable)
            spinbox.pack(side="right", padx=(2, 8))
            setattr(self, attribute, spinbox)
        ttk.Label(self.city_controls, textvariable=self.city_hp_preview).pack(anchor="w", pady=(0, 7))
        city_buttons = ttk.Frame(self.city_controls)
        city_buttons.pack(fill="x", pady=(0, 7))
        ttk.Button(city_buttons, text="Apply city", command=self._apply_city).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(city_buttons, text="Delete city", command=self._delete_selected_city).pack(
            side="left", expand=True, fill="x", padx=(3, 0))
        self.territory_controls = ttk.Frame(edit_tab)
        self.territory_controls.pack(fill="x")
        ttk.Label(self.territory_controls, text="Paint hexes for city").pack(anchor="w")
        self.territory_choice = ttk.Combobox(
            self.territory_controls, textvariable=self.territory_city_var,
            state="readonly")
        self.territory_choice.pack(fill="x", pady=(2, 8))
        self.unit_controls = ttk.Frame(edit_tab)
        self.unit_controls.pack(fill="x")
        self.unit_choice = ttk.Combobox(
            self.unit_controls, textvariable=self.unit_kind_display,
            values=self._sorted_translations(UNIT_TYPES), state="readonly")
        self.unit_choice.pack(fill="x", pady=(0, 5))
        self.unit_choice.bind("<<ComboboxSelected>>", self._select_unit_kind)
        ttk.Label(self.unit_controls, text="Starting unit country").pack(anchor="w")
        self.unit_owner_choice = ttk.Combobox(self.unit_controls, textvariable=self.unit_owner,
                                              state="readonly")
        self.unit_owner_choice.pack(fill="x")
        ttk.Label(self.unit_controls, textvariable=self.unit_selection_var).pack(
            anchor="w", pady=(6, 2))
        unit_buttons = ttk.Frame(self.unit_controls)
        unit_buttons.pack(fill="x")
        self.apply_unit_button = ttk.Button(
            unit_buttons, text="Apply unit", command=self._apply_selected_unit,
            state="disabled")
        self.apply_unit_button.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.delete_unit_button = ttk.Button(
            unit_buttons, text="Delete unit", command=self._delete_selected_unit,
            state="disabled")
        self.delete_unit_button.pack(side="left", expand=True, fill="x", padx=(3, 0))
        self.erase_controls = ttk.Frame(edit_tab)
        ttk.Label(self.erase_controls, text="Erase layer").pack(anchor="w")
        self.erase_layer_choice = ttk.Combobox(
            self.erase_controls, textvariable=self.erase_layer_display,
            values=self._sorted_translations(ERASE_LAYERS),
            state="readonly")
        self.erase_layer_choice.pack(fill="x", pady=(2, 0))
        self.erase_layer_choice.bind(
            "<<ComboboxSelected>>", self._select_erase_layer)

        country_list_frame = ttk.Frame(country_tab)
        country_list_frame.pack(fill="x")
        self.country_list = tk.Listbox(country_list_frame, height=5, exportselection=False,
                                       borderwidth=0, highlightthickness=1)
        self.country_list.pack(fill="x")
        self.country_list.bind("<<ListboxSelect>>", self._select_country)
        country_form = ttk.LabelFrame(country_tab, text="COUNTRY SETTINGS", padding=8)
        country_form.pack(fill="x", pady=(8, 0))
        ttk.Label(country_form, text="Name").pack(anchor="w")
        ttk.Entry(country_form, textvariable=self.country_name).pack(fill="x", pady=(2, 6))
        ttk.Label(country_form, text="Faction").pack(anchor="w")
        self.country_faction_choice = ttk.Combobox(
            country_form, textvariable=self.country_faction_display,
            values=self._sorted_translations(
                value.title() for value in (PLAYER, ENEMY, NEUTRAL)),
            state="readonly")
        self.country_faction_choice.pack(fill="x", pady=(2, 6))
        self.country_faction_choice.bind(
            "<<ComboboxSelected>>", self._select_country_faction)
        ttk.Label(country_form, text="Join war on turn").pack(anchor="w")
        tk.Spinbox(country_form, from_=1, to=9999, width=8,
                   textvariable=self.country_war_entry_turn).pack(
                       anchor="w", pady=(2, 6))
        ttk.Label(country_form, text="Country color (HSB)").pack(anchor="w", pady=(2, 2))
        color_preview_row = ttk.Frame(country_form)
        color_preview_row.pack(fill="x", pady=(0, 4))
        self.country_color_swatch = tk.Label(
            color_preview_row, text="      ", bg=self.country_color_hex.get(),
            relief="solid", borderwidth=1)
        self.country_color_swatch.pack(side="left", padx=(0, 7))
        ttk.Label(color_preview_row, textvariable=self.country_color_hex).pack(side="left")
        for label_var, variable, start, end in (
                (self.country_hue_label, self.country_hue, 0, 360),
                (self.country_saturation_label, self.country_saturation, 0, 100),
                (self.country_brightness_label, self.country_brightness, 0, 100)):
            scale_row = ttk.Frame(country_form)
            scale_row.pack(fill="x", pady=1)
            ttk.Label(scale_row, textvariable=label_var, width=15).pack(side="left")
            ttk.Scale(scale_row, from_=start, to=end, variable=variable,
                      command=self._update_country_color_preview).pack(
                          side="left", fill="x", expand=True)
        for key in ("money", "steel", "technology"):
            resource_row = ttk.Frame(country_form)
            resource_row.pack(fill="x", pady=1)
            ttk.Label(resource_row, text=key.title()).pack(side="left")
            tk.Spinbox(resource_row, from_=0, to=999999, width=8,
                       textvariable=self.country_resources[key]).pack(side="right")
        country_buttons = ttk.Frame(country_form)
        country_buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(country_buttons, text="Add", command=self._add_country).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(country_buttons, text="Apply", command=self._apply_country).pack(
            side="left", expand=True, fill="x", padx=3)
        ttk.Button(country_buttons, text="Remove", command=self._remove_country).pack(
            side="left", expand=True, fill="x", padx=(3, 0))

        map_frame = ttk.Frame(splitter)
        splitter.add(sidebar_pane, weight=0)
        splitter.add(map_frame, weight=1)
        splitter.bind("<Configure>", lambda event: self._set_initial_sidebar_width(), add="+")
        self.map_view = HexMapView(
            map_frame, EditorMapModel(self.data), self._on_hex_click,
            bg="#dfe7df", highlightthickness=1, highlightbackground="#d2d6cd", cursor="fleur")
        self.map_view.max_zoom = 4.0
        self.map_view.detail_threshold = 40.0
        self.map_view.allow_low_detail_interaction = True
        self.map_view.on_hex_drag = self._on_hex_drag
        self.map_view.bind("<Configure>", self._fit_initial_map, add="+")
        self.map_view.pack(fill="both", expand=True)

        status = tk.Label(self.root, textvariable=self.status, anchor="w", padx=14, pady=7,
                          bg="#dcded5", fg="#526057", font=("Segoe UI", 9))
        status.pack(fill="x", side="bottom")
        self._refresh_country_controls(self.selected_country_id)
        self._update_tool_state()

    def _set_initial_sidebar_width(self):
        if self._initial_sidebar_sash_set or self.splitter.winfo_width() <= 1:
            return
        self._initial_sidebar_sash_set = True
        self.splitter.sashpos(0, 280)

    def _update_tool_state(self):
        if self.mode.get() != "River":
            self.river_start = None
        terrain_state = "readonly" if self.mode.get() == "Terrain" else "disabled"
        city_state = "normal" if self.mode.get() == "City" else "disabled"
        city_owner_state = "readonly" if self.mode.get() == "City" else "disabled"
        territory_state = "readonly" if self.mode.get() == "Territory" else "disabled"
        unit_state = "readonly" if self.mode.get() == "Unit" else "disabled"
        self.terrain_choice.configure(state=terrain_state)
        self.city_name_entry.configure(state=city_state)
        self.city_owner_choice.configure(state=city_owner_state)
        self.city_level_spin.configure(state="normal" if self.mode.get() == "City" else "disabled")
        self.industry_level_spin.configure(state="normal" if self.mode.get() == "City" else "disabled")
        self.research_level_spin.configure(state="normal" if self.mode.get() == "City" else "disabled")
        self.territory_choice.configure(state=territory_state)
        self.unit_choice.configure(state=unit_state)
        self.unit_owner_choice.configure(state=unit_state)
        selected_unit_state = (
            "normal" if self.mode.get() == "Unit" and
            self.selected_unit_position is not None else "disabled")
        self.apply_unit_button.configure(state=selected_unit_state)
        self.delete_unit_button.configure(state=selected_unit_state)
        for mode, panel in (
                ("Terrain", self.terrain_controls),
                ("City", self.city_controls),
                ("Territory", self.territory_controls),
                ("Unit", self.unit_controls),
                ("Erase", self.erase_controls)):
            if self.mode.get() == mode:
                panel.pack(fill="x", pady=(5, 0))
            else:
                panel.pack_forget()

    def _update_city_hp_preview(self, *args):
        try:
            hp = city_hp_for_level(self.city_level.get())
        except (tk.TclError, TypeError):
            return
        self.city_hp_preview.set("Maximum HP: {}".format(hp))

    def _select_terrain(self, event=None):
        selected = self.terrain_display.get()
        self.terrain.set(next((value for value in TERRAIN_COLORS
                               if translate(value) == selected), selected))

    def _select_unit_kind(self, event=None):
        selected = self.unit_kind_display.get()
        self.unit_kind.set(next((value for value in UNIT_TYPES
                                 if translate(value) == selected), selected))

    def _select_erase_layer(self, event=None):
        selected = self.erase_layer_display.get()
        self.erase_layer.set(next((value for value in ERASE_LAYERS
                                   if translate(value) == selected), selected))

    def _select_country_faction(self, event=None):
        selected = self.country_faction_display.get()
        factions = (PLAYER, ENEMY, NEUTRAL)
        self.country_faction.set(next((value for value in factions
                                       if translate(value.title()) == selected),
                                      selected))

    def _country_id_for_name(self, name):
        return self.country_ids_by_name.get(name)

    def _refresh_country_controls(self, select_id=None):
        countries = self.data["countries"]
        self.country_ids_by_name = {
            country["name"]: country["id"] for country in countries
        }
        names = sorted((country["name"] for country in countries),
                   key=lambda name: translate(name).casefold())
        self.city_owner_choice.configure(values=names)
        self.unit_owner_choice.configure(values=names)
        self._refresh_territory_choices()
        city_owner_id = self._country_id_for_name(self.city_owner.get())
        unit_owner_id = self._country_id_for_name(self.unit_owner.get())
        if city_owner_id is None and countries:
            self.city_owner.set(countries[0]["name"])
        if unit_owner_id is None and countries:
            self.unit_owner.set(countries[0]["name"])

        self.country_list.delete(0, tk.END)
        self.country_list._language_original_items = []
        self.country_list_ids = []
        sorted_countries = sorted(
            countries,
            key=lambda country: translate("{}  [{}]".format(
                country["name"], country["faction"].title())).casefold())
        countries_by_id = {country["id"]: country for country in countries}
        for country in sorted_countries:
            self.country_list_ids.append(country["id"])
            label = "{}  [{}]".format(
                country["name"], country["faction"].title())
            self.country_list._language_original_items.append(label)
            self.country_list.insert(tk.END, translate(label))
        if select_id not in self.country_list_ids:
            select_id = self.country_list_ids[0] if self.country_list_ids else None
        self.selected_country_id = select_id
        if select_id is None:
            self.country_name.set("")
            for variable in self.country_resources.values():
                variable.set(0)
            return
        index = self.country_list_ids.index(select_id)
        self.country_list.selection_clear(0, tk.END)
        self.country_list.selection_set(index)
        self.country_list.see(index)
        self._load_country_fields(countries_by_id[select_id])

    @staticmethod
    def _city_label(city):
        return "{} ({}, {})".format(city["name"], city["col"] + 1, city["row"] + 1)

    def _refresh_territory_choices(self):
        cities = self.data["cities"]
        self.city_positions_by_label = {
            self._city_label(city): (city["col"], city["row"])
            for city in cities
        }
        labels = [self.clear_territory_label] + sorted(
            self.city_positions_by_label,
            key=lambda label: translate(label).casefold())
        selected = self.territory_city_var.get()
        self.territory_choice.configure(values=labels)
        if selected not in labels:
            self.territory_city_var.set(self.clear_territory_label)

    def _territory_target(self):
        selected = self.territory_city_var.get()
        return self.city_positions_by_label.get(selected)

    def _paint_territory(self, position, update_status=True):
        col, row = position
        if self.data["terrain"][row][col] == "Water":
            self.data["territories"][row][col] = None
            self.map_view.model.territory_city.pop(position, None)
            self.map_view.set_hex_territory(position)
            if update_status:
                self.status.set("Sea hexes do not belong to a city.")
            return True
        city_position = self._territory_target()
        if city_position is None:
            self.data["territories"][row][col] = None
            self.map_view.model.territory_city.pop(position, None)
            self.map_view.set_hex_territory(position)
            if update_status:
                self.status.set("Hex {}, {} is now unassigned.".format(col + 1, row + 1))
            return True
        self.data["territories"][row][col] = list(city_position)
        self.map_view.model.territory_city[position] = city_position
        self.map_view.set_hex_territory(position)
        if update_status:
            self.status.set("Hex {}, {} assigned to {}.".format(
                col + 1, row + 1, self.territory_city_var.get()))
        return True

    def _on_hex_drag(self, position):
        if self.mode.get() != "Territory":
            return False
        return self._paint_territory(position, update_status=False)

    def _apply_city(self):
        position = self.selected_city_position
        if position is None:
            self.status.set("Select a hex for the city first.")
            return
        col, row = position
        name = self.city_name.get().strip()
        owner = self._country_id_for_name(self.city_owner.get())
        try:
            level = self.city_level.get()
            industry_level = self.industry_level.get()
            research_level = self.research_level.get()
        except tk.TclError:
            self.status.set("City, industry, and research levels must be whole numbers.")
            return
        if (not name or len(name) > 30 or not owner or
                not 1 <= level <= CITY_MAX_LEVEL or
                not 0 <= industry_level <= 99 or not 0 <= research_level <= 99):
            self.status.set(
                "Set a valid city, industry, and research level (city: 1 to {}; production: 0 to 99).".format(
                    CITY_MAX_LEVEL))
            return
        if self.data["terrain"][row][col] == "Water":
            self.data["terrain"][row][col] = "Plain"
            self.data["territories"][row][col] = None
            self.data["rivers"] = [
                edge for edge in self.data["rivers"]
                if position not in (tuple(edge[0]), tuple(edge[1]))
            ]
        max_health = city_hp_for_level(level)
        city = next((item for item in self.data["cities"]
                     if (item["col"], item["row"]) == position), None)
        if city:
            health = min(city["health"], max_health)
            city.update({"name": name, "owner": owner, "city_level": level,
                         "industry_level": industry_level,
                         "research_level": research_level,
                         "health": health, "max_health": max_health})
        else:
            self.data["cities"].append({
                "col": col, "row": row, "name": name, "owner": owner,
                "city_level": level, "health": max_health, "max_health": max_health,
                "industry_level": industry_level, "research_level": research_level,
            })
            self.data["territories"][row][col] = [col, row]
        self._refresh_territory_choices()
        self._replace_editor_model()
        self.status.set("{} city updated.".format(name))

    def _delete_city_at(self, position):
        city = next((item for item in self.data["cities"]
                     if (item["col"], item["row"]) == position), None)
        if not city:
            return False
        self.data["cities"].remove(city)
        surviving_city_positions = [
            (item["col"], item["row"]) for item in self.data["cities"]]
        for row, territory_row in enumerate(self.data["territories"]):
            for col, city_position in enumerate(territory_row):
                if city_position is not None and tuple(city_position) == position:
                    terrain = self.data["terrain"][row][col]
                    replacement = self._nearest_city_position(
                        (col, row), surviving_city_positions)
                    territory_row[col] = (list(replacement)
                                           if replacement is not None and terrain != "Water"
                                           else None)
        for city_position in surviving_city_positions:
            col, row = city_position
            self.data["territories"][row][col] = [col, row]
        if self.selected_city_position == position:
            self.selected_city_position = None
        self._refresh_territory_choices()
        self._replace_editor_model()
        self.status.set("{} deleted; its land territory was reassigned.".format(
            city["name"]))
        return True

    @staticmethod
    def _hex_distance(first, second):
        first_row, second_row = first[1], second[1]
        first_axial_col = first[0] - (first_row - (first_row & 1)) // 2
        second_axial_col = second[0] - (second_row - (second_row & 1)) // 2
        delta_col = first_axial_col - second_axial_col
        delta_row = first_row - second_row
        return (abs(delta_col) + abs(delta_row) +
                abs(delta_col + delta_row)) // 2

    @classmethod
    def _nearest_city_position(cls, position, city_positions):
        if not city_positions:
            return None
        return min(city_positions, key=lambda city_position: (
            cls._hex_distance(position, city_position), city_position))

    def _delete_selected_city(self):
        if self.selected_city_position is None or not self._delete_city_at(
                self.selected_city_position):
            self.status.set("Select a city to delete.")

    def _selected_unit(self):
        if self.selected_unit_position is None:
            return None
        return next((unit for unit in self.data["units"]
                     if (unit["col"], unit["row"]) ==
                     self.selected_unit_position), None)

    def _apply_selected_unit(self):
        unit = self._selected_unit()
        owner = self._country_id_for_name(self.unit_owner.get())
        if unit is None:
            self.status.set("Select a deployed unit first.")
            return
        if owner is None:
            self.status.set("Add a country before placing starting units.")
            return
        unit["type"] = self.unit_kind.get()
        unit["owner"] = owner
        self.unit_selection_var.set("{} at hex {}, {}".format(
            self.unit_kind.get(), self.selected_unit_position[0] + 1,
            self.selected_unit_position[1] + 1))
        self._replace_editor_model()
        self.status.set("Starting unit updated.")

    def _delete_selected_unit(self):
        unit = self._selected_unit()
        if unit is None:
            self.selected_unit_position = None
            self.status.set("Select a deployed unit first.")
            self._update_tool_state()
            return
        self.data["units"].remove(unit)
        self.selected_unit_position = None
        self.unit_selection_var.set("No unit selected")
        self._replace_editor_model()
        self._update_tool_state()
        self.status.set("Starting unit deleted.")

    def _select_deployed_unit(self, position):
        unit = next((unit for unit in self.data["units"]
                     if (unit["col"], unit["row"]) == position), None)
        if unit is None:
            return False
        self.selected_unit_position = position
        self.unit_kind.set(unit["type"])
        self.unit_kind_display.set(translate(unit["type"]))
        country = next(item for item in self.data["countries"]
                       if item["id"] == unit["owner"])
        self.unit_owner.set(country["name"])
        self.unit_selection_var.set("{} at hex {}, {}".format(
            unit["type"], position[0] + 1, position[1] + 1))
        self.map_view.set_selection(position, None, None)
        self._update_tool_state()
        self.status.set("{} selected. Apply changes or delete the unit.".format(
            unit["type"]))
        return True

    def _toggle_river(self, position):
        if self.river_start is None:
            self.river_start = position
            self.map_view.set_selection(position, None, None)
            self.status.set("Choose a neighboring land hex to complete the river edge.")
            return
        first = self.river_start
        self.river_start = None
        if position not in hex_neighbors(self.data["columns"], self.data["rows"], first):
            self.map_view.set_selection(None, None, None)
            self.status.set("River endpoints must be neighboring hexes.")
            return
        if (self.data["terrain"][first[1]][first[0]] == "Water" or
                self.data["terrain"][position[1]][position[0]] == "Water"):
            self.map_view.set_selection(None, None, None)
            self.status.set("Rivers can only be drawn between land hexes.")
            return
        edge = [list(first), list(position)]
        key = frozenset((first, position))
        existing = next((item for item in self.data["rivers"]
                         if frozenset((tuple(item[0]), tuple(item[1]))) == key), None)
        if existing:
            self.data["rivers"].remove(existing)
            self.status.set("River edge removed.")
        else:
            self.data["rivers"].append(edge)
            self.status.set("River edge added.")
        self._replace_editor_model()

    def _load_country_fields(self, country):
        self.country_name.set(country["name"])
        self.country_faction.set(country["faction"])
        self.country_faction_display.set(translate(country["faction"].title()))
        self.country_war_entry_turn.set(country.get("war_entry_turn", 1))
        for key, variable in self.country_resources.items():
            variable.set(country["resources"][key])
        index = self.country_list_ids.index(country["id"])
        color = country.get("color") or _country_colors(index, country["faction"])[0]
        self._set_country_color(color)

    def _set_country_color(self, color):
        rgb = tuple(int(color[offset:offset + 2], 16) / 255.0
                    for offset in (1, 3, 5))
        hue, saturation, brightness = colorsys.rgb_to_hsv(*rgb)
        self._loading_country_color = True
        self.country_hue.set(hue * 360)
        self.country_saturation.set(saturation * 100)
        self.country_brightness.set(brightness * 100)
        self._loading_country_color = False
        self._update_country_color_preview()

    def _update_country_color_preview(self, value=None):
        if self._loading_country_color:
            return
        hue = self.country_hue.get()
        saturation = self.country_saturation.get()
        brightness = self.country_brightness.get()
        self.country_hue_label.set("Hue {}".format(int(round(hue)) % 360))
        self.country_saturation_label.set(
            "Saturation {}%".format(int(round(saturation)))
        )
        self.country_brightness_label.set(
            "Brightness {}%".format(int(round(brightness)))
        )
        rgb = colorsys.hsv_to_rgb((hue % 360) / 360.0,
                                  saturation / 100.0, brightness / 100.0)
        color = "#%02x%02x%02x" % tuple(int(round(channel * 255)) for channel in rgb)
        self.country_color_hex.set(color)
        self.country_color_swatch.configure(bg=color)

    def _select_country(self, event=None):
        selection = self.country_list.curselection()
        if not selection:
            return
        index = selection[0]
        self.selected_country_id = self.country_list_ids[index]
        country = next(country for country in self.data["countries"]
                   if country["id"] == self.selected_country_id)
        self._load_country_fields(country)

    def _add_country(self):
        index = 1
        existing_ids = {country["id"] for country in self.data["countries"]}
        while "country_{}".format(index) in existing_ids:
            index += 1
        country = {
            "id": "country_{}".format(index),
            "name": "Country {}".format(index),
            "faction": self.country_faction.get(),
            "war_entry_turn": 1,
            "color": self.country_color_hex.get(),
            "resources": {"money": 16, "steel": 8, "technology": 3},
        }
        self.data["countries"].append(country)
        self._refresh_country_controls(country["id"])
        self._replace_editor_model()
        self.status.set("{} added. Assign it at least one city before starting a game.".format(
            country["name"]))

    def _apply_country(self):
        country = next((item for item in self.data["countries"]
                        if item["id"] == self.selected_country_id), None)
        if not country:
            self.status.set("Select a country first.")
            return
        name = self.country_name.get().strip()
        if not name or len(name) > 30:
            self.status.set("Country names must contain 1 to 30 characters.")
            return
        if any(item is not country and item["name"].casefold() == name.casefold()
               for item in self.data["countries"]):
            self.status.set("Country names must be unique.")
            return
        try:
            resources = {key: variable.get()
                         for key, variable in self.country_resources.items()}
            war_entry_turn = self.country_war_entry_turn.get()
        except tk.TclError:
            self.status.set("Resource balances and war entry turn must be whole numbers.")
            return
        if any(amount < 0 or amount > 999999 for amount in resources.values()):
            self.status.set("Resource balances must be from 0 to 999999.")
            return
        if war_entry_turn < 1:
            self.status.set("War entry turn must be at least 1.")
            return
        country["name"] = name
        country["faction"] = self.country_faction.get()
        country["war_entry_turn"] = war_entry_turn
        country["color"] = self.country_color_hex.get()
        country["resources"] = resources
        self._refresh_country_controls(country["id"])
        self._replace_editor_model()
        self.status.set("{} country settings updated.".format(name))

    def _remove_country(self):
        country_id = self.selected_country_id
        if not country_id:
            return
        country = next(item for item in self.data["countries"] if item["id"] == country_id)
        if any(city["owner"] == country_id for city in self.data["cities"]):
            self.status.set("Move or erase this country's cities before removing it.")
            return
        self.data["units"] = [unit for unit in self.data["units"]
                              if unit["owner"] != country_id]
        self.data["countries"].remove(country)
        self._refresh_country_controls()
        self._replace_editor_model()
        self.status.set("{} removed.".format(country["name"]))

    def _replace_editor_model(self, fit=False):
        self.map_view.model = EditorMapModel(self.data)
        if fit and self.map_view.winfo_width() > 1 and self.map_view.winfo_height() > 1:
            self.map_view.fit_map(draw=False)
        self.map_view.set_selection(None, None, None)
        if fit and (self.map_view.winfo_width() <= 1 or self.map_view.winfo_height() <= 1):
            self.root.after_idle(lambda: self.map_view.fit_map(draw=False))

    def _fit_initial_map(self, event):
        if not self._initial_fit_done and event.width > 1 and event.height > 1:
            self._initial_fit_done = True
            self.map_view.fit_map()

    @staticmethod
    def _sorted_translations(values):
        return sorted((translate(value) for value in values),
                      key=lambda value: value.casefold())

    def _on_hex_click(self, position):
        col, row = position
        city_owner = self._country_id_for_name(self.city_owner.get())
        unit_owner = self._country_id_for_name(self.unit_owner.get())
        if self.mode.get() == "Terrain":
            if (self.terrain.get() == "Water" and
                    (position in self.map_view.model.cities or self.map_view.model.unit_at(position))):
                self.status.set("Cities and units cannot be placed on water. Move or erase them first.")
                return
            self.data["terrain"][row][col] = self.terrain.get()
            if self.terrain.get() == "Water":
                self.data["territories"][row][col] = None
                self.map_view.model.territory_city.pop(position, None)
                self.data["rivers"] = [
                    edge for edge in self.data["rivers"]
                    if position not in (tuple(edge[0]), tuple(edge[1]))
                ]
            self.status.set("{} set at hex {}, {}.".format(self.terrain.get(), col + 1, row + 1))
        elif self.mode.get() == "Territory":
            self._paint_territory(position)
            return
        elif self.mode.get() == "River":
            self._toggle_river(position)
            return
        elif self.mode.get() == "City":
            existing_city = self.map_view.model.cities.get(position)
            self.selected_city_position = position
            if existing_city:
                self.city_name.set(existing_city["name"])
                self.city_owner.set(next(
                    country["name"] for country in self.data["countries"]
                    if country["id"] == existing_city["owner"]))
                self.city_level.set(existing_city["city_level"])
                self.industry_level.set(existing_city["industry_level"])
                self.research_level.set(existing_city["research_level"])
                self.status.set("{} selected. Edit its fields and apply, or delete it.".format(
                    existing_city["name"]))
            else:
                self.industry_level.set(1)
                self.research_level.set(1)
                self.status.set("Hex {}, {} selected. Set city properties and apply to place.".format(
                    col + 1, row + 1))
            self.map_view.set_selection(position, None, None)
            return
        elif self.mode.get() == "Unit":
            if self._select_deployed_unit(position):
                return
            if not unit_owner:
                self.status.set("Add a country before placing starting units.")
                return
            if self.data["terrain"][row][col] == "Water":
                self.status.set("Starting units cannot be placed on water.")
                return
            self.data["units"] = [
                unit for unit in self.data["units"]
                if (unit["col"], unit["row"]) != position
            ]
            self.data["units"].append({
                "col": col,
                "row": row,
                "type": self.unit_kind.get(),
                "owner": unit_owner,
            })
            self.selected_unit_position = position
            self.unit_selection_var.set("{} at hex {}, {}".format(
                self.unit_kind.get(), col + 1, row + 1))
            self.status.set("{} assigned to {} at hex {}, {}.".format(
                self.unit_kind.get(), self.unit_owner.get(), col + 1, row + 1))
            self._update_tool_state()
        elif self.mode.get() == "Erase":
            layer = self.erase_layer.get()
            if layer == "Unit":
                unit = next((unit for unit in self.data["units"]
                             if (unit["col"], unit["row"]) == position), None)
                if unit is None:
                    self.status.set("No starting unit on this hex.")
                else:
                    self.data["units"].remove(unit)
                    if self.selected_unit_position == position:
                        self.selected_unit_position = None
                        self.unit_selection_var.set("No unit selected")
                    self.status.set("Starting unit erased.")
            elif layer == "City":
                if self._delete_city_at(position):
                    return
                self.status.set("No city on this hex.")
            elif layer == "River":
                river_index = next((index for index, edge in enumerate(self.data["rivers"])
                                    if position in (tuple(edge[0]), tuple(edge[1]))), None)
                if river_index is None:
                    self.status.set("No river edge on this hex.")
                else:
                    self.data["rivers"].pop(river_index)
                    self.status.set("River edge erased.")
            elif layer == "Terrain":
                if self.data["terrain"][row][col] == "Plain":
                    self.status.set("Terrain is already Plain.")
                else:
                    self.data["terrain"][row][col] = "Plain"
                    if self.data["territories"][row][col] is None:
                        city_positions = [
                            (city["col"], city["row"])
                            for city in self.data["cities"]]
                        nearest_city = self._nearest_city_position(
                            position, city_positions)
                        if nearest_city is not None:
                            self.data["territories"][row][col] = list(nearest_city)
                    self.status.set("Terrain erased.")
            else:
                if self.data["territories"][row][col] is None:
                    self.status.set("No territory assignment on this hex.")
                else:
                    self.data["territories"][row][col] = None
                    self.status.set("Territory assignment erased.")
        self._replace_editor_model()

    def _new_map(self):
        if not messagebox.askyesno(translate("New map"),
                       translate("Discard the current map and create a blank one?"),
                                   parent=self.root):
            return
        try:
            self.data = new_map_data(self.columns.get(), self.rows.get())
        except (tk.TclError, ValueError) as error:
            messagebox.showerror(translate("Invalid map size"), str(error),
                                 parent=self.root)
            return
        self.selected_city_position = None
        self.selected_unit_position = None
        self.unit_selection_var.set("No unit selected")
        self._refresh_country_controls(self.data["countries"][0]["id"])
        self._replace_editor_model(fit=True)
        self.status.set("Blank {} x {} map created.".format(
            self.data["columns"], self.data["rows"]))

    def _resize_map(self):
        try:
            columns = self.columns.get()
            rows = self.rows.get()
            resized = new_map_data(columns, rows)
        except (tk.TclError, ValueError) as error:
            messagebox.showerror(translate("Invalid map size"), str(error),
                                 parent=self.root)
            return

        old_columns = self.data["columns"]
        old_rows = self.data["rows"]
        removed_cities = sum(1 for city in self.data["cities"]
                     if city["col"] >= columns or city["row"] >= rows)
        removed_units = sum(
            1 for unit in self.data["units"]
            if unit["col"] >= columns or unit["row"] >= rows)
        for row in range(min(rows, old_rows)):
            for col in range(min(columns, old_columns)):
                resized["terrain"][row][col] = self.data["terrain"][row][col]
                resized["territories"][row][col] = self.data["territories"][row][col]
        resized["cities"] = [
            city for city in self.data["cities"]
            if city["col"] < columns and city["row"] < rows
        ]
        resized["countries"] = [
            dict(country, resources=dict(country["resources"]))
            for country in self.data["countries"]]
        resized["units"] = [
            unit for unit in self.data["units"]
            if unit["col"] < columns and unit["row"] < rows
        ]
        resized["rivers"] = [
            edge for edge in self.data["rivers"]
            if all(point[0] < columns and point[1] < rows for point in edge)
        ]
        surviving_cities = {(city["col"], city["row"]) for city in resized["cities"]}
        for row, territory_row in enumerate(resized["territories"]):
            for col, city_position in enumerate(territory_row):
                if city_position is not None and tuple(city_position) not in surviving_cities:
                    nearest_city = self._nearest_city_position(
                        (col, row), surviving_cities)
                    territory_row[col] = (list(nearest_city)
                                           if nearest_city is not None and
                                           resized["terrain"][row][col] != "Water"
                                           else None)
        for city_position in surviving_cities:
            col, row = city_position
            resized["territories"][row][col] = [col, row]
        self.data = resized
        self.columns.set(columns)
        self.rows.set(rows)
        surviving_country_ids = {
            country["id"] for country in resized["countries"]}
        selected_country = self.selected_country_id
        if selected_country not in surviving_country_ids:
            selected_country = (resized["countries"][0]["id"]
                                if resized["countries"] else None)
        self._refresh_country_controls(selected_country)
        self.selected_city_position = None
        self.selected_unit_position = None
        self.unit_selection_var.set("No unit selected")
        self._replace_editor_model(fit=True)
        self.status.set("Map resized to {} x {}. Removed {} city/cities and {} unit(s) outside the new size.".format(
            columns, rows, removed_cities, removed_units))

    def _open_map(self):
        path = filedialog.askopenfilename(
            parent=self.root, title=translate("Open map"),
            filetypes=((translate("Steel Dominion map"), "*.json"),
                       (translate("All files"), "*.*")))
        if not path:
            return
        try:
            data = load_map_file(path, allow_invalid_territories=True)
        except (OSError, ValueError) as error:
            messagebox.showerror(translate("Unable to open map"), str(error),
                                 parent=self.root)
            return
        self.data = data
        self.columns.set(data["columns"])
        self.rows.set(data["rows"])
        self.selected_city_position = None
        self.selected_unit_position = None
        self.unit_selection_var.set("No unit selected")
        self._refresh_country_controls(data["countries"][0]["id"] if data["countries"] else None)
        self._replace_editor_model(fit=False)
        self.status.set("Map opened: {} x {}, {} cities.".format(
            data["columns"], data["rows"], len(data["cities"])))

    def _save_map(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title=translate("Save map"), defaultextension=".json",
            filetypes=((translate("Steel Dominion map"), "*.json"),
                       (translate("All files"), "*.*")))
        if not path:
            return
        try:
            save_map_file(path, self.data)
        except (OSError, ValueError) as error:
            messagebox.showerror(translate("Unable to save map"), str(error),
                                 parent=self.root)
            return
        self.status.set("Map saved to {}.".format(path))


def run_editor():
    root = tk.Tk()
    set_language(load_language())
    MapEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_editor()