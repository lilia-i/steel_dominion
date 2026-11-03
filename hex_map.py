import math
import tkinter as tk
import colorsys

from game_config import NEUTRAL, PLAYER, TERRAIN_COLORS


INK_COLOR = "#202c27"


def _desaturate_color(color, factor=0.82):
    channels = tuple(int(color[offset:offset + 2], 16) / 255.0
                     for offset in (1, 3, 5))
    hue, saturation, brightness = colorsys.rgb_to_hsv(*channels)
    muted = colorsys.hsv_to_rgb(hue, saturation * factor, brightness)
    return "#%02x%02x%02x" % tuple(int(channel * 255 + 0.5) for channel in muted)


def _mix_colors(first, second, second_weight):
    first_channels = tuple(int(first[offset:offset + 2], 16) for offset in (1, 3, 5))
    second_channels = tuple(int(second[offset:offset + 2], 16) for offset in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(
        int(first_channel * (1 - second_weight) + second_channel * second_weight + 0.5)
        for first_channel, second_channel in zip(first_channels, second_channels))


def _country_colors(index, faction, color=None):
    if faction == NEUTRAL:
        return "#b8b8b8", "#686868"

    if color:
        color = _desaturate_color(color.lower())
        channels = tuple(int(color[offset:offset + 2], 16) for offset in (1, 3, 5))
        mark = "#%02x%02x%02x" % tuple(int(channel * 0.62) for channel in channels)
        return color, mark

    hue = (index * 0.618033988749895) % 1.0
    fill_rgb = colorsys.hsv_to_rgb(hue, (0.2 + (index % 4) * 0.035) * 0.82, 0.96)
    mark_rgb = colorsys.hsv_to_rgb(hue, 0.62 * 0.82, 0.58)
    fill = "#%02x%02x%02x" % tuple(int(channel * 255) for channel in fill_rgb)
    mark = "#%02x%02x%02x" % tuple(int(channel * 255) for channel in mark_rgb)
    return fill, mark


class HexMapView(tk.Canvas):
    radius = 35
    sqrt3 = math.sqrt(3)

    def __init__(self, master, model, on_hex_click, **kwargs):
        tk.Canvas.__init__(self, master, **kwargs)
        self.model = model
        self.on_hex_click = on_hex_click
        self.zoom = 1.0
        self.min_zoom = 0.04
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.country_fill_colors = {}
        self.country_mark_colors = {}
        self.hex_items = {}
        self.on_hex_drag = None
        self.paint_dragging = False
        self.last_painted_hex = None
        self.selected_hex = None
        self.selected_unit = None
        self.attack_target = None
        self.low_detail = False
        self.drag_origin = None
        self.last_drag_position = None
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
        self.min_zoom = 0.04
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

    def _draw_terrain_symbol(self, terrain, center_x, center_y):
        scale = max(0.55, min(1.25, self.zoom))
        width = max(1, self.zoom)
        if terrain == "Forest":
            color = "#3e5e49"
            for offset in (-3, 2):
                self.create_polygon(
                    center_x + offset * scale, center_y - 5 * scale,
                    center_x + (offset - 4) * scale, center_y + 3 * scale,
                    center_x + (offset + 4) * scale, center_y + 3 * scale,
                    fill=color, outline="", tags="terrain-icon")
        elif terrain == "Hill":
            self.create_line(center_x - 8 * scale, center_y + 4 * scale,
                             center_x - 2 * scale, center_y - 4 * scale,
                             center_x + 2 * scale, center_y + 1 * scale,
                             center_x + 6 * scale, center_y - 4 * scale,
                             center_x + 9 * scale, center_y + 4 * scale,
                             fill="#756b50", width=width,
                             joinstyle=tk.ROUND, tags="terrain-icon")
        elif terrain == "Water":
            for offset in (-2, 3):
                self.create_line(center_x - 7 * scale, center_y + offset * scale,
                                 center_x - 3 * scale, center_y + (offset - 1) * scale,
                                 center_x + scale, center_y + offset * scale,
                                 center_x + 5 * scale, center_y + (offset - 1) * scale,
                                 fill="#357987", width=width, smooth=True,
                                 tags="terrain-icon")
        else:
            self.create_line(center_x - 5 * scale, center_y + 3 * scale,
                             center_x - 2 * scale, center_y - 2 * scale,
                             center_x, center_y + 3 * scale,
                             center_x + 3 * scale, center_y - 3 * scale,
                             center_x + 6 * scale, center_y + 3 * scale,
                             fill="#66764f", width=width,
                             joinstyle=tk.ROUND, tags="terrain-icon")

    def draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        self.hex_items = {}
        radius = self.radius * self.zoom
        low_detail = 2 * radius <= 40
        self.low_detail = low_detail
        country_data = self.model.countries
        if isinstance(country_data, dict):
            country_ids = list(country_data.keys())
            countries_by_id = country_data
        else:
            country_ids = [country["id"] for country in country_data]
            countries_by_id = {country["id"]: country for country in country_data}
        self.country_fill_colors = {}
        self.country_mark_colors = {}
        for index, country_id in enumerate(country_ids):
            country = countries_by_id[country_id]
            fill, mark = _country_colors(
                index, country["faction"], country.get("color"))
            self.country_fill_colors[country_id] = fill
            self.country_mark_colors[country_id] = mark

        for position, terrain in self.model.tiles.items():
            center_x, center_y = self._screen_center(position)
            territory_city = self.model.city_for_hex(position)
            terrain_color = TERRAIN_COLORS[terrain]
            fill = (_mix_colors(terrain_color,
                                self.country_fill_colors.get(territory_city["owner"],
                                                             terrain_color), 0.55)
                    if territory_city else terrain_color)
            outline = "#f3f1e8"
            line_width = max(1, self.zoom * 2.0)
            if not low_detail and position == self.selected_hex:
                outline = "#202c27"
                line_width = max(2, self.zoom * 3.0)
            if not low_detail and position == self.attack_target:
                outline = "#b95849"
                line_width = max(2, self.zoom * 3.0)
            self.hex_items[position] = self.create_polygon(
                self._hex_points(center_x, center_y, radius),
                fill=fill, outline="" if low_detail else outline,
                width=0 if low_detail else line_width)

            if not low_detail and self.zoom >= 0.28:
                self._draw_terrain_symbol(terrain, center_x, center_y)

            city = self.model.cities.get(position)
            if city and low_detail:
                owner_color = self.country_mark_colors.get(city["owner"], "#47745f")
                marker_radius = max(1.5, 5 * self.zoom)
                marker_y = center_y - max(1.0, 4 * self.zoom)
                self.create_polygon(center_x, marker_y - marker_radius,
                                    center_x + marker_radius, marker_y,
                                    center_x, marker_y + marker_radius,
                                    center_x - marker_radius, marker_y,
                                    fill=owner_color, outline="#fff9e9", width=1,
                                    tags="overview-city")
            elif city and not low_detail:
                owner_color = self.country_mark_colors.get(city["owner"], "#47745f")
                icon_y = center_y - 10 * self.zoom
                icon_scale = max(0.45, self.zoom)
                icon_width = 6 * icon_scale
                roof_top = icon_y - 7 * icon_scale
                body_top = icon_y - 2 * icon_scale
                body_bottom = icon_y + 5 * icon_scale
                self.create_polygon(center_x - icon_width, body_top,
                                    center_x, roof_top,
                                    center_x + icon_width, body_top,
                                    fill=owner_color, outline=INK_COLOR,
                                    width=max(1, self.zoom), tags="city-marker")
                self.create_rectangle(center_x - 4.5 * icon_scale, body_top,
                                      center_x + 4.5 * icon_scale, body_bottom,
                                      fill="#f4f1e7", outline=INK_COLOR,
                                      width=max(1, self.zoom), tags="city-marker")
                self.create_rectangle(center_x - icon_scale, center_y - 8 * self.zoom,
                                      center_x + icon_scale, body_bottom,
                                      fill=owner_color, outline="", tags="city-marker")
                if self.zoom >= 0.6:
                    label = "{}  Lv{}".format(city["name"], city["city_level"])
                    label_font = ("Segoe UI", max(7, int(9 * self.zoom)), "bold")
                    label_item = self.create_text(
                        center_x, center_y - 25 * self.zoom, text=label,
                        fill="#202c27", font=label_font, tags="city-label")
                    bounds = self.bbox(label_item)
                    if bounds:
                        left, top, right, bottom = bounds
                        background = self.create_rectangle(
                            left - 4, top - 2, right + 4, bottom + 2,
                            fill="#f4f1e7", outline="#c9c8bb", width=1,
                            tags="city-label")
                        self.tag_lower(background, label_item)
                if (position == self.selected_hex and
                        self.model.unit_at(position) is None):
                    city_bar_width = 23 * self.zoom
                    city_bar_y = center_y + 2 * self.zoom
                    self.create_rectangle(center_x - city_bar_width / 2, city_bar_y,
                                          center_x + city_bar_width / 2,
                                          city_bar_y + 3 * self.zoom,
                                          fill="#f2eee2", outline="")
                    self.create_rectangle(
                        center_x - city_bar_width / 2, city_bar_y,
                        center_x - city_bar_width / 2 + city_bar_width * city["health"] /
                        city["max_health"], city_bar_y + 3 * self.zoom,
                        fill=owner_color, outline="")

            unit = self.model.unit_at(position)
            unit_faction = self.model.faction_for(unit.owner) if unit else None
            unit_color = (self.country_mark_colors.get(unit.owner, "#777777")
                          if unit and unit_faction != NEUTRAL else "#777777")
            if unit and low_detail:
                badge = max(2.0, 7 * self.zoom)
                unit_y = center_y + max(1.0, 4 * self.zoom)
                self.create_oval(center_x - badge, unit_y - badge,
                                 center_x + badge, unit_y + badge,
                                 fill=unit_color, outline="#fff9e9", width=1,
                                 tags="overview-unit")
                mark = "S" if unit.embarked else {
                    "Infantry": "I", "Tank": "T", "Artillery": "A"}[unit.kind]
                self.create_text(center_x, unit_y, text=mark, fill="white",
                                 font=("Segoe UI", 6, "bold"), tags="overview-unit")
            elif unit and not low_detail:
                unit_y = center_y + 7 * self.zoom
                badge = 12 * self.zoom
                player_country_id = getattr(self.model, "player_country_id", None)
                is_player_unit = (unit.owner == player_country_id if player_country_id
                                 else unit.faction == PLAYER)
                if is_player_unit and not unit.attacked:
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
                health_color = ("#87a777" if is_player_unit else
                                "#999999" if unit_faction == NEUTRAL else "#cf7564")
                self.create_rectangle(center_x - bar_width / 2, bar_y,
                                      center_x - bar_width / 2 + bar_width * unit.hp / unit.max_hp,
                                      bar_y + 3 * self.zoom, fill=health_color, outline="")

        self._draw_city_territory_boundaries()

        for edge in (() if low_detail else self.model.river_edges):
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

        if (not low_detail and self.selected_unit and self.model.phase == PLAYER and
            self.selected_unit.owner == getattr(self.model, "player_country_id", None) and
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
        self.drag_origin = (event.x, event.y)
        self.last_drag_position = (event.x, event.y)
        self.dragged = False
        self.paint_dragging = False
        self.last_painted_hex = None
        if not self.low_detail and self.on_hex_drag and not (event.state & 0x0001):
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.paint_dragging = bool(self.on_hex_drag(position))
                if self.paint_dragging:
                    self.last_painted_hex = position

    def _on_drag(self, event):
        if not self.drag_origin:
            return
        start_x, start_y = self.drag_origin
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
            last_x, last_y = self.last_drag_position
            move_x = event.x - last_x
            move_y = event.y - last_y
            self.pan_x += move_x
            self.pan_y += move_y
            self.move("all", move_x, move_y)
            self.last_drag_position = (event.x, event.y)

    def _on_release(self, event):
        if not self.low_detail and not self.dragged:
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.on_hex_click(position)
        self.drag_origin = None
        self.last_drag_position = None
        self.paint_dragging = False
        self.last_painted_hex = None

    def _draw_city_territory_boundaries(self):
        edges = {}
        owners = {}
        for position, terrain in self.model.tiles.items():
            city = self.model.city_for_hex(position)
            owner = city["position"] if city else (
                "__water__" if terrain == "Water" else "__unassigned__")
            owners[position] = owner
            center_x, center_y = self._screen_center(position)
            points = self._hex_points(center_x, center_y, self.radius * self.zoom)
            vertices = [(points[index * 2], points[index * 2 + 1])
                        for index in range(6)]
            for index in range(6):
                first = vertices[index]
                second = vertices[(index + 1) % 6]
                first_vertex = (round(first[0], 3), round(first[1], 3))
                second_vertex = (round(second[0], 3), round(second[1], 3))
                key = tuple(sorted((first_vertex, second_vertex)))
                edges.setdefault(key, []).append((position, first, second))
        for edge_sides in edges.values():
            if len(edge_sides) != 2:
                continue
            first_side, second_side = edge_sides
            first_owner = owners[first_side[0]]
            second_owner = owners[second_side[0]]
            if (first_owner == second_owner or first_owner == "__water__" or
                    second_owner == "__water__"):
                continue
            self.create_line(first_side[1][0], first_side[1][1],
                             first_side[2][0], first_side[2][1],
                             fill="#5c685f",
                             width=(max(1, 2 * self.zoom) if self.low_detail else
                                    max(1, 1.5 * self.zoom)),
                             tags="city-territory-boundary")

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