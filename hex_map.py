import math
import tkinter as tk

from game_config import PLAYER, TERRAIN_COLORS


COUNTRY_PALETTE = (
    ("#d3e2ca", "#47745f"),
    ("#ead0c8", "#b95849"),
    ("#c8dce6", "#3d758c"),
    ("#ebddb4", "#987527"),
    ("#d9d0e7", "#70588c"),
    ("#c6e0d9", "#3b8174"),
    ("#e8cfe0", "#98557d"),
    ("#d9d2bd", "#766b43"),
    ("#d1d8ed", "#596b9b"),
    ("#e4d3bf", "#986b42"),
)


class HexMapView(tk.Canvas):
    radius = 35
    sqrt3 = math.sqrt(3)

    def __init__(self, master, model, on_hex_click, **kwargs):
        tk.Canvas.__init__(self, master, **kwargs)
        self.model = model
        self.on_hex_click = on_hex_click
        self.zoom = 1.0
        self.min_zoom = 0.35
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.terrain_images = {}
        self.country_fill_colors = {}
        self.country_mark_colors = {}
        self.hex_items = {}
        self.on_hex_drag = None
        self.paint_dragging = False
        self.last_painted_hex = None
        self.selected_hex = None
        self.selected_unit = None
        self.attack_target = None
        self.drag_origin = None
        self.dragged = False
        self.bind("<Configure>", lambda event: self.draw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1.0 / 1.12))

    def set_selection(self, selected_hex, selected_unit, attack_target):
        self.selected_hex = selected_hex
        self.selected_unit = selected_unit
        self.attack_target = attack_target
        self.draw()

    def fit_map(self, draw=True):
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        map_width = self.sqrt3 * self.radius * (self.model.columns + 0.5)
        map_height = 1.5 * self.radius * (self.model.rows - 1) + 2 * self.radius
        self.min_zoom = 0.35
        self.zoom = max(self.min_zoom,
                min(1.0, (width - 24) / map_width, (height - 24) / map_height))
        self.pan_x = 0.0
        self.pan_y = 0.0
        if draw:
            self.draw()

    def _center(self, position):
        col, row = position
        return (self.sqrt3 * self.radius * (col + (row % 2) / 2.0),
                1.5 * self.radius * row)

    def _world_center(self):
        first = self._center((0, 0))
        last = self._center((self.model.columns - 1, self.model.rows - 1))
        return (first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0

    def _screen_center(self, position):
        world_x, world_y = self._center(position)
        origin_x, origin_y = self._world_center()
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        return (width / 2.0 + self.pan_x + (world_x - origin_x) * self.zoom,
                height / 2.0 + self.pan_y + (world_y - origin_y) * self.zoom)

    def _hex_points(self, center_x, center_y, radius):
        points = []
        for index in range(6):
            angle = math.radians(30 + 60 * index)
            points.extend((center_x + radius * math.cos(angle),
                           center_y + radius * math.sin(angle)))
        return points

    def _terrain_image(self, terrain, size):
        key = (terrain, size)
        if key in self.terrain_images:
            return self.terrain_images[key]

        image = tk.PhotoImage(master=self, width=size, height=size)

        def span(y, left, right, color):
            left = max(0, left)
            right = min(size, right)
            if left < right and 0 <= y < size:
                image.put(color, to=(left, y, right, y + 1))

        def triangle(center_x, top, bottom, half_width, color):
            height = max(1, bottom - top)
            for y in range(max(0, top), min(size, bottom)):
                reach = max(1, int(half_width * (y - top + 1) / height))
                span(y, center_x - reach, center_x + reach + 1, color)

        if terrain == "Forest":
            for center_x, top, width in ((size // 3, size // 5, size // 4),
                                         (size * 2 // 3, size // 3, size // 4)):
                triangle(center_x, top, size * 3 // 4, width, "#32684c")
                triangle(center_x, top + size // 5, size * 3 // 4,
                         max(1, width - 2), "#5c9865")
                trunk_width = max(1, size // 9)
                for y in range(size * 3 // 4, size * 9 // 10):
                    span(y, center_x - trunk_width, center_x + trunk_width + 1, "#76543a")
        elif terrain == "Hill":
            triangle(size // 3, size // 5, size * 4 // 5, size // 3, "#8e7950")
            triangle(size * 2 // 3, size // 3, size * 4 // 5, size // 3, "#b69b64")
            triangle(size // 3, size // 5, size // 2, size // 7, "#f2edda")
        elif terrain == "Water":
            wave_color = "#397f9a"
            for row in (size // 3, size // 2, size * 2 // 3):
                for col in range(size // 8, size * 7 // 8):
                    offset = (col // max(2, size // 4)) % 2
                    span(row + offset, col, col + 2, wave_color)
        else:
            grass_color = "#66864c"
            for col, row in ((size // 4, size // 2), (size // 2, size // 3),
                             (size * 3 // 4, size * 3 // 5)):
                span(row, col, col + 1, grass_color)
                span(row + 1, col - 1, col + 2, grass_color)
                span(row + 2, col, col + 1, grass_color)

        self.terrain_images[key] = image
        return image

    def draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        self.hex_items = {}
        radius = self.radius * self.zoom
        country_data = self.model.countries
        if isinstance(country_data, dict):
            country_ids = list(country_data.keys())
        else:
            country_ids = [country["id"] for country in country_data]
        self.country_fill_colors = {}
        self.country_mark_colors = {}
        for index, country_id in enumerate(country_ids):
            fill, mark = COUNTRY_PALETTE[index % len(COUNTRY_PALETTE)]
            self.country_fill_colors[country_id] = fill
            self.country_mark_colors[country_id] = mark

        for position, terrain in self.model.tiles.items():
            center_x, center_y = self._screen_center(position)
            city = self.model.city_for_hex(position)
            fill = (self.country_fill_colors.get(city["owner"], "#e4e3d9")
                    if city else TERRAIN_COLORS["Water"] if terrain == "Water" else "#e4e3d9")
            outline = "#f3f1e8"
            line_width = max(1, self.zoom * 2.0)
            if position == self.selected_hex:
                outline = "#202c27"
                line_width = max(2, self.zoom * 3.0)
            if position == self.attack_target:
                outline = "#b95849"
                line_width = max(2, self.zoom * 3.0)
            self.hex_items[position] = self.create_polygon(
                self._hex_points(center_x, center_y, radius),
                fill=fill, outline=outline, width=line_width)

            if self.zoom >= 0.22:
                icon_size = max(8, int(24 * self.zoom))
                self.create_image(center_x, center_y,
                                  image=self._terrain_image(terrain, icon_size),
                                  tags="terrain-icon")

            city = self.model.cities.get(position)
            if city and self.zoom >= 0.30:
                owner_color = self.country_mark_colors.get(city["owner"], "#47745f")
                self.create_oval(center_x - 5 * self.zoom, center_y - 14 * self.zoom,
                                 center_x + 5 * self.zoom, center_y - 4 * self.zoom,
                                 fill=owner_color, outline="#fff9e9", width=1)
                self.create_text(center_x, center_y - 20 * self.zoom, text=city["name"],
                                 fill="#202c27",
                                 font=("Segoe UI", max(7, int(9 * self.zoom)), "bold"))
                city_bar_width = 23 * self.zoom
                city_bar_y = center_y - 2 * self.zoom
                self.create_rectangle(center_x - city_bar_width / 2, city_bar_y,
                                      center_x + city_bar_width / 2, city_bar_y + 3 * self.zoom,
                                      fill="#f2eee2", outline="")
                self.create_rectangle(
                    center_x - city_bar_width / 2, city_bar_y,
                    center_x - city_bar_width / 2 + city_bar_width * city["health"] /
                    city["max_health"], city_bar_y + 3 * self.zoom,
                    fill=owner_color, outline="")

            unit = self.model.unit_at(position)
            if unit and self.zoom >= 0.30:
                unit_color = "#47745f" if unit.faction == PLAYER else "#b95849"
                unit_y = center_y + 7 * self.zoom
                badge = 12 * self.zoom
                if unit.faction == PLAYER and not unit.attacked:
                    ready_ring = 3 * self.zoom
                    self.create_oval(center_x - badge - ready_ring, unit_y - badge - ready_ring,
                                     center_x + badge + ready_ring, unit_y + badge + ready_ring,
                                     fill="", outline="#d0a44c", width=max(1, self.zoom),
                                     tags="action-ready")
                self.create_oval(center_x - badge, unit_y - badge,
                                 center_x + badge, unit_y + badge,
                                 fill=unit_color, outline="#fff9e9", width=max(1, self.zoom))
                mark = "S" if unit.embarked else {"Infantry": "I", "Tank": "T", "Artillery": "A"}[unit.kind]
                self.create_text(center_x, unit_y, text=mark, fill="white",
                                 font=("Segoe UI", max(7, int(10 * self.zoom)), "bold"))
                bar_width = 23 * self.zoom
                bar_y = unit_y + 15 * self.zoom
                self.create_rectangle(center_x - bar_width / 2, bar_y,
                                      center_x + bar_width / 2, bar_y + 3 * self.zoom,
                                      fill="#f2eee2", outline="")
                health_color = "#87a777" if unit.faction == PLAYER else "#cf7564"
                self.create_rectangle(center_x - bar_width / 2, bar_y,
                                      center_x - bar_width / 2 + bar_width * unit.hp / unit.max_hp,
                                      bar_y + 3 * self.zoom, fill=health_color, outline="")

        for edge in self.model.river_edges:
            first, second = tuple(edge)
            first_x, first_y = self._screen_center(first)
            second_x, second_y = self._screen_center(second)
            delta_x = second_x - first_x
            delta_y = second_y - first_y
            center_x = (first_x + second_x) / 2.0
            center_y = (first_y + second_y) / 2.0
            center_distance = math.hypot(delta_x, delta_y)
            half_edge = self.radius * self.zoom / 2.0
            offset_x = -delta_y / center_distance * half_edge
            offset_y = delta_x / center_distance * half_edge
            river_points = (center_x - offset_x, center_y - offset_y,
                            center_x + offset_x, center_y + offset_y)
            self.create_line(*river_points, fill="#4f8990", width=max(3, 5 * self.zoom),
                             capstyle=tk.ROUND, tags="river")
            self.create_line(*river_points, fill="#9dc7c6", width=max(1, 2 * self.zoom),
                             capstyle=tk.ROUND, tags="river")

        if (self.selected_unit and self.model.phase == PLAYER and
                not self.selected_unit.attacked):
            if self.selected_unit.movement_left > 0:
                for position in self.model.movement_paths(self.selected_unit):
                    center_x, center_y = self._screen_center(position)
                    self.create_polygon(self._hex_points(center_x, center_y, radius),
                                        fill="", outline="#d0a44c", dash=(4, 3),
                                        width=max(1, self.zoom), tags="move-range")
            for enemy in self.model.units:
                if enemy.faction == self.selected_unit.faction:
                    continue
                if self.model.distance(self.selected_unit.position, enemy.position) <= self.selected_unit.range:
                    center_x, center_y = self._screen_center(enemy.position)
                    self.create_polygon(self._hex_points(center_x, center_y, radius),
                                        fill="", outline="#b95849", dash=(3, 2),
                                        width=max(1, self.zoom), tags="attack-range")
            for position, city in self.model.cities.items():
                if (city["health"] > 0 and
                        self.model.faction_for(city["owner"]) != self.selected_unit.faction and
                        self.model.distance(self.selected_unit.position, position) <=
                        self.selected_unit.range):
                    center_x, center_y = self._screen_center(position)
                    self.create_polygon(self._hex_points(center_x, center_y, radius),
                                        fill="", outline="#b95849", dash=(3, 2),
                                        width=max(1, self.zoom), tags="attack-range")

    def _on_press(self, event):
        self.drag_origin = (event.x, event.y, self.pan_x, self.pan_y)
        self.dragged = False
        self.paint_dragging = False
        self.last_painted_hex = None
        if self.on_hex_drag and not (event.state & 0x0001):
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.paint_dragging = bool(self.on_hex_drag(position))
                if self.paint_dragging:
                    self.last_painted_hex = position

    def _on_drag(self, event):
        if not self.drag_origin:
            return
        start_x, start_y, start_pan_x, start_pan_y = self.drag_origin
        delta_x = event.x - start_x
        delta_y = event.y - start_y
        if abs(delta_x) + abs(delta_y) > 4:
            self.dragged = True
        if self.paint_dragging:
            position = self._hex_at(event.x, event.y)
            if position is not None and position != self.last_painted_hex:
                self.last_painted_hex = position
                self.on_hex_drag(position)
            return
        if self.dragged:
            self.pan_x = start_pan_x + delta_x
            self.pan_y = start_pan_y + delta_y
            self.draw()

    def _on_release(self, event):
        if not self.dragged:
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.on_hex_click(position)
        self.drag_origin = None
        self.paint_dragging = False
        self.last_painted_hex = None

    def _on_wheel(self, event):
        factor = 1.12 if event.delta > 0 else 1.0 / 1.12
        self._zoom_at(event.x, event.y, factor)

    def _zoom_at(self, x, y, factor):
        old_zoom = self.zoom
        new_zoom = max(self.min_zoom, min(2.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return
        center_x, center_y = self._world_center()
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        world_x = (x - width / 2.0 - self.pan_x) / old_zoom
        world_y = (y - height / 2.0 - self.pan_y) / old_zoom
        self.zoom = new_zoom
        self.pan_x = x - width / 2.0 - world_x * new_zoom
        self.pan_y = y - height / 2.0 - world_y * new_zoom
        self.draw()

    def set_hex_territory(self, position):
        item = self.hex_items.get(position)
        if item is None:
            return
        city = self.model.city_for_hex(position)
        terrain = self.model.tiles[position]
        fill = (self.country_fill_colors.get(city["owner"], "#e4e3d9")
            if city else TERRAIN_COLORS["Water"] if terrain == "Water" else "#e4e3d9")
        self.itemconfigure(item, fill=fill)

    def _hex_at(self, x, y):
        center_x, center_y = self._world_center()
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        world_x = (x - width / 2.0 - self.pan_x) / self.zoom + center_x
        world_y = (y - height / 2.0 - self.pan_y) / self.zoom + center_y
        best_position = None
        best_distance = float("inf")
        for position in self.model.tiles:
            tile_x, tile_y = self._center(position)
            distance = (world_x - tile_x) ** 2 + (world_y - tile_y) ** 2
            if distance < best_distance:
                best_position = position
                best_distance = distance
        if best_distance <= (self.radius * 1.08) ** 2:
            return best_position
        return None