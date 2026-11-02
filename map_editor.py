import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from game_config import (
    CITY_MAX_LEVEL,
    ENEMY,
    PLAYER,
    TERRAIN_COLORS,
    UNIT_TYPES,
    city_hp_for_level,
)
from hex_map import HexMapView
from map_data import MAX_MAP_SIZE, MIN_MAP_SIZE, load_map_file, new_map_data, save_map_file


INK = "#202c27"
PAPER = "#e8e7df"


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
        self.river_edges = set()

    def unit_at(self, position):
        return next((unit for unit in self.units if unit.position == position), None)

    def faction_for(self, country_id):
        return next(country["faction"] for country in self.countries
                    if country["id"] == country_id)

    def city_for_hex(self, position):
        city_position = self.territory_city.get(position)
        return self.cities.get(city_position)


class EditorUnit(object):
    def __init__(self, kind, owner, faction, position):
        self.kind = kind
        self.owner = owner
        self.faction = faction
        self.position = position
        self.hp = UNIT_TYPES[kind]["hp"]
        self.max_hp = self.hp
        self.attacked = False
        self.embarked = False


class MapEditorApp(object):
    def __init__(self, root):
        self.root = root
        self.root.title("Steel Dominion | Map Editor")
        self.root.geometry("1180x780")
        self.root.minsize(820, 560)
        self.root.configure(bg=PAPER)

        self.data = new_map_data()
        self.mode = tk.StringVar(value="Terrain")
        self.terrain = tk.StringVar(value="Forest")
        self.city_name = tk.StringVar(value="City")
        self.city_owner = tk.StringVar()
        self.city_level = tk.IntVar(value=1)
        self.city_hp_preview = tk.StringVar(value="Maximum HP: {}".format(city_hp_for_level(1)))
        self.city_level.trace("w", self._update_city_hp_preview)
        self.territory_city_var = tk.StringVar()
        self.unit_kind = tk.StringVar(value="Infantry")
        self.unit_owner = tk.StringVar()
        self.country_name = tk.StringVar()
        self.country_faction = tk.StringVar(value=PLAYER)
        self.country_resources = {
            key: tk.IntVar(value=0) for key in ("money", "steel", "technology")
        }
        self.selected_country_id = self.data["countries"][0]["id"]
        self._initial_fit_done = False
        self.columns = tk.IntVar(value=self.data["columns"])
        self.rows = tk.IntVar(value=self.data["rows"])
        self.status = tk.StringVar(value="Choose a tool, then click map hexes.")
        self._build_ui()
        self._replace_editor_model(fit=True)

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

        body = ttk.Frame(self.root, padding=12)
        body.pack(fill="both", expand=True)
        sidebar = ttk.Frame(body, width=250)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)

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

        for label in ("Terrain", "City", "Territory", "Unit", "Erase"):
            ttk.Radiobutton(edit_tab, text=label, value=label, variable=self.mode,
                            command=self._update_tool_state).pack(anchor="w", pady=2)

        self.terrain_choice = ttk.Combobox(
            edit_tab, textvariable=self.terrain, values=tuple(TERRAIN_COLORS.keys()),
            state="readonly")
        self.terrain_choice.pack(fill="x", pady=(5, 8))
        ttk.Label(edit_tab, text="City name").pack(anchor="w")
        self.city_name_entry = ttk.Entry(edit_tab, textvariable=self.city_name)
        self.city_name_entry.pack(fill="x", pady=(3, 7))
        ttk.Label(edit_tab, text="City country").pack(anchor="w")
        self.city_owner_choice = ttk.Combobox(edit_tab, textvariable=self.city_owner,
                                              state="readonly")
        self.city_owner_choice.pack(fill="x", pady=(0, 5))
        city_level_row = ttk.Frame(edit_tab)
        city_level_row.pack(fill="x", pady=(0, 8))
        ttk.Label(city_level_row, text="City level").pack(side="left")
        self.city_level_spin = tk.Spinbox(
            city_level_row, from_=1, to=CITY_MAX_LEVEL, width=4,
            textvariable=self.city_level, command=self._update_city_hp_preview)
        self.city_level_spin.pack(side="right")
        ttk.Label(edit_tab, textvariable=self.city_hp_preview).pack(anchor="w", pady=(0, 7))
        ttk.Label(edit_tab, text="Paint hexes for city").pack(anchor="w")
        self.territory_choice = ttk.Combobox(
            edit_tab, textvariable=self.territory_city_var, state="readonly")
        self.territory_choice.pack(fill="x", pady=(2, 8))
        self.unit_choice = ttk.Combobox(edit_tab, textvariable=self.unit_kind,
                                        values=list(UNIT_TYPES.keys()), state="readonly")
        self.unit_choice.pack(fill="x", pady=(0, 5))
        ttk.Label(edit_tab, text="Starting unit country").pack(anchor="w")
        self.unit_owner_choice = ttk.Combobox(edit_tab, textvariable=self.unit_owner,
                                              state="readonly")
        self.unit_owner_choice.pack(fill="x")

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
        ttk.Combobox(country_form, textvariable=self.country_faction,
                     values=(PLAYER, ENEMY), state="readonly").pack(fill="x", pady=(2, 6))
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

        map_frame = ttk.Frame(body)
        map_frame.pack(side="right", fill="both", expand=True)
        self.map_view = HexMapView(
            map_frame, EditorMapModel(self.data), self._on_hex_click,
            bg="#dfe7df", highlightthickness=1, highlightbackground="#d2d6cd", cursor="fleur")
        self.map_view.on_hex_drag = self._on_hex_drag
        self.map_view.bind("<Configure>", self._fit_initial_map, add="+")
        self.map_view.pack(fill="both", expand=True)

        status = tk.Label(self.root, textvariable=self.status, anchor="w", padx=14, pady=7,
                          bg="#dcded5", fg="#526057", font=("Segoe UI", 9))
        status.pack(fill="x", side="bottom")
        self._refresh_country_controls(self.selected_country_id)
        self._update_tool_state()

    def _update_tool_state(self):
        terrain_state = "readonly" if self.mode.get() == "Terrain" else "disabled"
        city_state = "normal" if self.mode.get() == "City" else "disabled"
        city_owner_state = "readonly" if self.mode.get() == "City" else "disabled"
        territory_state = "readonly" if self.mode.get() == "Territory" else "disabled"
        unit_state = "readonly" if self.mode.get() == "Unit" else "disabled"
        self.terrain_choice.configure(state=terrain_state)
        self.city_name_entry.configure(state=city_state)
        self.city_owner_choice.configure(state=city_owner_state)
        self.city_level_spin.configure(state="normal" if self.mode.get() == "City" else "disabled")
        self.territory_choice.configure(state=territory_state)
        self.unit_choice.configure(state=unit_state)
        self.unit_owner_choice.configure(state=unit_state)

    def _update_city_hp_preview(self, *args):
        try:
            hp = city_hp_for_level(self.city_level.get())
        except (tk.TclError, TypeError):
            return
        self.city_hp_preview.set("Maximum HP: {}".format(hp))

    def _country_id_for_name(self, name):
        return next((country["id"] for country in self.data["countries"]
                     if country["name"] == name), None)

    def _refresh_country_controls(self, select_id=None):
        countries = self.data["countries"]
        names = [country["name"] for country in countries]
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
        self.country_list_ids = []
        for country in countries:
            self.country_list_ids.append(country["id"])
            self.country_list.insert(tk.END, "{}  [{}]".format(
                country["name"], country["faction"].title()))
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
        self._load_country_fields(countries[index])

    @staticmethod
    def _city_label(city):
        return "{} ({}, {})".format(city["name"], city["col"] + 1, city["row"] + 1)

    def _refresh_territory_choices(self):
        cities = self.data["cities"]
        labels = [self._city_label(city) for city in cities]
        selected = self.territory_city_var.get()
        self.territory_choice.configure(values=labels)
        if selected not in labels:
            self.territory_city_var.set(labels[0] if labels else "")

    def _territory_target(self):
        selected = self.territory_city_var.get()
        for city in self.data["cities"]:
            if self._city_label(city) == selected:
                return city["col"], city["row"]
        return None

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
            if update_status:
                self.status.set("Place a city before painting its territory.")
            return False
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

    def _load_country_fields(self, country):
        self.country_name.set(country["name"])
        self.country_faction.set(country["faction"])
        for key, variable in self.country_resources.items():
            variable.set(country["resources"][key])

    def _select_country(self, event=None):
        selection = self.country_list.curselection()
        if not selection:
            return
        index = selection[0]
        self.selected_country_id = self.country_list_ids[index]
        self._load_country_fields(self.data["countries"][index])

    def _add_country(self):
        index = 1
        existing_ids = {country["id"] for country in self.data["countries"]}
        while "country_{}".format(index) in existing_ids:
            index += 1
        country = {
            "id": "country_{}".format(index),
            "name": "Country {}".format(index),
            "faction": self.country_faction.get(),
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
        except tk.TclError:
            self.status.set("Resource balances must be whole numbers.")
            return
        if any(amount < 0 or amount > 999999 for amount in resources.values()):
            self.status.set("Resource balances must be from 0 to 999999.")
            return
        country["name"] = name
        country["faction"] = self.country_faction.get()
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
            self.status.set("{} set at hex {}, {}.".format(self.terrain.get(), col + 1, row + 1))
        elif self.mode.get() == "Territory":
            self._paint_territory(position)
            return
        elif self.mode.get() == "City":
            name = self.city_name.get().strip()
            if not name or len(name) > 30 or not city_owner:
                self.status.set("Set a valid city name and country.")
                return
            try:
                city_level = self.city_level.get()
            except tk.TclError:
                self.status.set("City level must be a whole number.")
                return
            if not 1 <= city_level <= CITY_MAX_LEVEL:
                self.status.set("City level must be from 1 to {}.".format(CITY_MAX_LEVEL))
                return
            max_health = city_hp_for_level(city_level)
            if self.data["terrain"][row][col] == "Water":
                self.data["terrain"][row][col] = "Plain"
            self.data["cities"] = [
                city for city in self.data["cities"]
                if (city["col"], city["row"]) != position
            ]
            self.data["cities"].append({
                "col": col,
                "row": row,
                "name": name,
                "owner": city_owner,
                "city_level": city_level,
                "health": max_health,
                "max_health": max_health,
            })
            self.data["territories"][row][col] = [col, row]
            self._refresh_territory_choices()
            self.status.set("{} city placed at hex {}, {}.".format(name, col + 1, row + 1))
        elif self.mode.get() == "Unit":
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
            self.status.set("{} assigned to {} at hex {}, {}.".format(
                self.unit_kind.get(), self.unit_owner.get(), col + 1, row + 1))
        else:
            self.data["terrain"][row][col] = "Plain"
            removed_city_positions = [
                (city["col"], city["row"]) for city in self.data["cities"]
                if (city["col"], city["row"]) == position
            ]
            self.data["cities"] = [
                city for city in self.data["cities"]
                if (city["col"], city["row"]) != position
            ]
            self.data["units"] = [
                unit for unit in self.data["units"]
                if (unit["col"], unit["row"]) != position
            ]
            for territory_row in self.data["territories"]:
                for territory_col, city_position in enumerate(territory_row):
                    if city_position is not None and tuple(city_position) in removed_city_positions:
                        territory_row[territory_col] = None
            self._refresh_territory_choices()
            self.status.set("Hex {}, {} cleared.".format(col + 1, row + 1))
        self._replace_editor_model()

    def _new_map(self):
        if not messagebox.askyesno("New map", "Discard the current map and create a blank one?",
                                   parent=self.root):
            return
        try:
            self.data = new_map_data(self.columns.get(), self.rows.get())
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Invalid map size", str(error), parent=self.root)
            return
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
            messagebox.showerror("Invalid map size", str(error), parent=self.root)
            return

        old_columns = self.data["columns"]
        old_rows = self.data["rows"]
        removed_cities = sum(1 for city in self.data["cities"]
                     if city["col"] >= columns or city["row"] >= rows)
        removed_units = sum(1 for unit in self.data["units"]
                    if unit["col"] >= columns or unit["row"] >= rows)
        if (removed_cities or removed_units) and not messagebox.askyesno(
            "Resize map", "{} city/cities and {} unit(s) outside the new size will be removed. Continue?".format(
                removed_cities, removed_units), parent=self.root):
            return

        for row in range(min(rows, old_rows)):
            for col in range(min(columns, old_columns)):
                resized["terrain"][row][col] = self.data["terrain"][row][col]
                resized["territories"][row][col] = self.data["territories"][row][col]
        resized["cities"] = [
            city for city in self.data["cities"]
            if city["col"] < columns and city["row"] < rows
        ]
        resized["units"] = [
            unit for unit in self.data["units"]
            if unit["col"] < columns and unit["row"] < rows
        ]
        surviving_cities = {(city["col"], city["row"]) for city in resized["cities"]}
        for territory_row in resized["territories"]:
            for col, city_position in enumerate(territory_row):
                if city_position is not None and tuple(city_position) not in surviving_cities:
                    territory_row[col] = None
        self.data = resized
        self.columns.set(columns)
        self.rows.set(rows)
        self._refresh_territory_choices()
        self._replace_editor_model(fit=True)
        self.status.set("Map resized to {} x {}.".format(columns, rows))

    def _open_map(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Open map",
            filetypes=(("Steel Dominion map", "*.json"), ("All files", "*.*")))
        if not path:
            return
        try:
            data = load_map_file(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Unable to open map", str(error), parent=self.root)
            return
        self.data = data
        self.columns.set(data["columns"])
        self.rows.set(data["rows"])
        self._refresh_country_controls(data["countries"][0]["id"] if data["countries"] else None)
        self._replace_editor_model(fit=True)
        self.status.set("Map opened: {} x {}, {} cities.".format(
            data["columns"], data["rows"], len(data["cities"])))

    def _save_map(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Save map", defaultextension=".json",
            filetypes=(("Steel Dominion map", "*.json"), ("All files", "*.*")))
        if not path:
            return
        try:
            save_map_file(path, self.data)
        except (OSError, ValueError) as error:
            messagebox.showerror("Unable to save map", str(error), parent=self.root)
            return
        self.status.set("Map saved to {}.".format(path))


def run_editor():
    root = tk.Tk()
    MapEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_editor()