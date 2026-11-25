import math
import time
import tkinter as tk
import colorsys

from game_config import (NEUTRAL, PLAYER, TERRAIN_COLORS, TRANSPORT_STATS,
                         UNIT_TYPES)
from unit_effects import morale_level_for


INK_COLOR = "#202c27"


def _nearest_hex_position(world_x, world_y, columns, rows, radius):
    column_spacing = math.sqrt(3.0) * radius
    row_spacing = 1.5 * radius
    nearest_row = int(math.floor(world_y / row_spacing + 0.5))
    nearest_row = max(0, min(rows - 1, nearest_row))
    best_position = None
    best_distance = float("inf")

    # Staggered rows mean the closest center can be one row from the vertical nearest.
    for row in range(max(0, nearest_row - 1), min(rows, nearest_row + 2)):
        projected_col = world_x / column_spacing - (row % 2) / 2.0
        first_col = int(math.floor(projected_col))
        candidate_cols = (max(0, min(columns - 1, first_col)),
                          max(0, min(columns - 1, first_col + 1)))
        for col in candidate_cols:
            center_x = column_spacing * (col + (row % 2) / 2.0)
            center_y = row_spacing * row
            distance = (world_x - center_x) ** 2 + (world_y - center_y) ** 2
            if distance < best_distance:
                best_position = (col, row)
                best_distance = distance
    return best_position, best_distance


def _desaturate_color(color, factor=0.55):
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
    fill_rgb = colorsys.hsv_to_rgb(hue, (0.2 + (index % 4) * 0.035) * 0.5, 0.96)
    mark_rgb = colorsys.hsv_to_rgb(hue, 0.62 * 0.45, 0.58)
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
        self.max_zoom = 2.0
        self.detail_threshold = 40.0
        self.allow_low_detail_interaction = False
        self.force_overview = False
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.country_fill_colors = {}
        self.country_mark_colors = {}
        self.hex_items = {}
        self.corner_gap_items = {}
        self.corner_gap_tiles = {}
        self.corner_gap_geometry = {}
        self.tile_corner_gaps = {}
        self.territory_edge_sides = {}
        self.territory_edge_items = {}
        self.territory_edge_segments = {}
        self.territory_segment_items = {}
        self.territory_vertex_corners = {}
        self.territory_vertex_segments = {}
        self.territory_side_edges = {}
        self.territory_edge_vertices = {}
        self.territory_edge_kinds = {}
        self.tile_boundary_edges = {}
        self.city_territory_tiles = {}
        self.tile_city_owner = {}
        self._text_fonts = {}
        self._zoom_stroke_widths = {}
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
        self._screen_geometry = None
        self._canvas_size = None
        self._canvas_zoom = self.zoom
        self._canvas_pan = (self.pan_x, self.pan_y)
        self._camera_update_id = None
        self._detail_visibility_key = None
        self._style_update_id = None
        self._style_zoom = self.zoom
        self.unit_animation_active = False
        self.unit_animation_after_id = None
        self._drawn_state_key = None
        self._drawn_background_key = None
        self._drawn_unit_key = None
        self._drawn_selection_key = None
        self.bind("<Configure>", self._on_canvas_resize)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1.0 / 1.12))

    def set_selection(self, selected_hex, selected_unit, attack_target):
        previous = (self.selected_hex, self.selected_unit, self.attack_target)
        self.selected_hex = selected_hex
        self.selected_unit = selected_unit
        self.attack_target = attack_target
        background_key = self._background_state_key()
        unit_key = self._unit_state_key()
        if (self.hex_items and self._drawn_background_key != background_key and
            self._update_city_ownership(self._drawn_background_key,
                                        background_key)):
            self._drawn_background_key = background_key
            self.delete("selection-overlay")
            self._draw_selection_overlay()
            self._drawn_state_key = self._visual_state_key()
            self._drawn_selection_key = self._selection_state_key()
        if self._drawn_background_key == background_key and self.hex_items:
            if self._drawn_unit_key != unit_key:
                self.delete("unit-layer")
                self.delete("selection-overlay")
                self._draw_unit_layer()
                self._draw_selection_overlay()
                self._drawn_unit_key = unit_key
                self._detail_visibility_key = None
                self._update_detail_visibility()
                self._drawn_selection_key = self._selection_state_key()
                self._drawn_state_key = self._visual_state_key()
                return
            selection_key = self._selection_state_key()
            if self._drawn_selection_key != selection_key:
                self.delete("selection-overlay")
                self._draw_selection_overlay()
                self._drawn_selection_key = selection_key
                self._drawn_state_key = self._visual_state_key()
                return
            if previous != (selected_hex, selected_unit, attack_target):
                self.delete("selection-overlay")
                self._draw_selection_overlay()
                self._drawn_selection_key = self._selection_state_key()
                self._drawn_state_key = self._visual_state_key()
            return
        self.draw()

    def _background_state_key(self):
        countries = self.model.countries
        if isinstance(countries, dict):
            countries = countries.values()
        country_state = tuple(sorted(
            (country["id"], country["faction"], country.get("color"))
            for country in countries))
        city_state = tuple(sorted(
            (position, city.get("owner"), city.get("name"),
             city.get("city_level"), city.get("industry_level"),
             city.get("research_level"), city.get("health"),
             city.get("max_health"))
            for position, city in self.model.cities.items()))
        return id(self.model), country_state, city_state

    def _unit_state_key(self):
        unit_state = tuple(sorted(
            (getattr(unit, "id", id(unit)), unit.position, unit.owner,
             unit.kind, unit.hp, unit.max_hp,
             getattr(unit, "movement_left", None), getattr(unit, "attacked", None),
             getattr(unit, "embarked", None), self._morale_level(unit))
            for unit in self.model.units))
        return unit_state, getattr(self.model, "phase", None)

    @staticmethod
    def _morale_level(unit):
        return morale_level_for(unit) if hasattr(unit, "statuses") else 0

    def _selection_state_key(self):
        city = self.model.cities.get(self.selected_hex)
        city_health = ((city.get("health"), city.get("max_health"))
                       if city else None)
        return self.selected_hex, self.selected_unit, self.attack_target, city_health

    def _visual_state_key(self):
        return (self._background_state_key(), self._unit_state_key(),
                self._selection_state_key())

    def _city_owner_tag(self, position):
        return "city-owner-{}-{}".format(position[0], position[1])

    def _city_health_color(self, city):
        owner_faction = self.model.faction_for(city["owner"])
        player_faction = getattr(self.model, "player_faction", PLAYER)
        if owner_faction == NEUTRAL:
            return "#bec4c0"
        return "#e4aaa4" if owner_faction != player_faction else "#afd1a5"

    def _update_city_ownership(self, previous, current):
        if previous is None or previous[:2] != current[:2]:
            return False
        old_cities = {city[0]: city[1:] for city in previous[2]}
        new_cities = {city[0]: city[1:] for city in current[2]}
        if old_cities.keys() != new_cities.keys():
            return False
        changed = []
        for position, old_city in old_cities.items():
            new_city = new_cities[position]
            if old_city[1:5] != new_city[1:5]:
                return False
            if old_city[0] != new_city[0] or old_city[5:] != new_city[5:]:
                changed.append(position)
        if not changed:
            return False
        if any(old_cities[position][0] != new_cities[position][0]
               for position in changed):
            return False
        boundary_changed = False
        for city_position in changed:
            city = self.model.cities[city_position]
            city_tag = "{}-{}".format(*city_position)
            owner_changed = old_cities[city_position][0] != new_cities[city_position][0]
            if owner_changed:
                owner_color = self.country_mark_colors.get(city["owner"], "#47745f")
                self.itemconfigure(self._city_owner_tag(city_position),
                                   fill=owner_color)
                self.itemconfigure("city-health-{}".format(city_tag),
                                   fill=self._city_health_color(city))
            track = self.find_withtag("city-health-track-{}".format(city_tag))
            health = self.find_withtag("city-health-{}".format(city_tag))
            if track and health:
                left, top, right, bottom = self.coords(track[0])
                ratio = (float(city["health"]) / city["max_health"]
                         if city["max_health"] else 0.0)
                self.coords(health[0], left, top,
                            left + (right - left) * ratio, bottom)
            if owner_changed:
                for position in self.city_territory_tiles.get(city_position, ()):
                    item = self.hex_items.get(position)
                    if item is not None:
                        self.itemconfigure(item, fill=self._hex_fill(position))
                        self._update_corner_gaps(position)
                    for edge in self.tile_boundary_edges.get(position, ()):
                        boundary_changed = (
                            self._update_territory_edge(edge, rebuild=False) or
                            boundary_changed)
        if boundary_changed:
            self._rebuild_territory_vertex_segments()
        return True

    def _on_canvas_resize(self, event):
        current_size = (event.width, event.height)
        previous_size = self._canvas_size
        self._canvas_size = current_size
        self._update_screen_geometry(*current_size)
        if previous_size is None:
            self.after_idle(self._draw_if_empty)
            return
        if self.hex_items:
            delta_x = (current_size[0] - previous_size[0]) / 2.0
            delta_y = (current_size[1] - previous_size[1]) / 2.0
            self.move("all", delta_x, delta_y)
        else:
            self.after_idle(self._draw_if_empty)

    def _draw_if_empty(self):
        if self.winfo_exists() and not self.hex_items:
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

    def _hex_fill(self, position):
        terrain = self.model.tiles[position]
        city = self.model.city_for_hex(position)
        terrain_color = TERRAIN_COLORS[terrain]
        if not city:
            return terrain_color
        country_color = self.country_fill_colors.get(city["owner"], terrain_color)
        return _mix_colors(terrain_color, country_color, 0.55)

    def _create_text(self, *coordinates, **options):
        max_font_size = options.pop("max_font_size", None)
        item = self.create_text(*coordinates, **options)
        font = options.get("font")
        if isinstance(font, tuple) and len(font) > 1:
            self._text_fonts[item] = (
                font[0], float(font[1]), font[2:], max_font_size)
            if max_font_size is not None:
                self.itemconfigure(
                    item, font=(font[0], max(1, round(min(font[1], max_font_size))),
                                *font[2:]))
        return item

    def _scale_item_styles(self, factor):
        for item, font in tuple(self._text_fonts.items()):
            if not self.type(item):
                self._text_fonts.pop(item, None)
                continue
            family, size, styles, max_size = font
            size *= factor
            self._text_fonts[item] = (family, size, styles, max_size)
            display_size = min(size, max_size) if max_size is not None else size
            self.itemconfigure(
                item, font=(family, max(1, round(display_size)), *styles))

    def _world_center(self):
        first = self._center((0, 0))
        last = self._center((self.model.columns - 1, self.model.rows - 1))
        return (first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0

    def _update_screen_geometry(self, width=None, height=None):
        width = max(self.winfo_width() if width is None else width, 1)
        height = max(self.winfo_height() if height is None else height, 1)
        origin_x, origin_y = self._world_center()
        self._screen_geometry = width, height, origin_x, origin_y

    def _screen_center(self, position):
        world_x, world_y = self._center(position)
        if self._screen_geometry is None:
            self._update_screen_geometry()
        width, height, origin_x, origin_y = self._screen_geometry
        return (width / 2.0 + self.pan_x + (world_x - origin_x) * self.zoom,
                height / 2.0 + self.pan_y + (world_y - origin_y) * self.zoom)

    def _hex_points(self, center_x, center_y, radius):
        points = []
        for index in range(6):
            angle = math.radians(30 + 60 * index)
            points.extend((center_x + radius * math.cos(angle),
                           center_y + radius * math.sin(angle)))
        return points

    def _create_cell_arc(self, position, side_index, color, width, tags):
        center_x, center_y = self._screen_center(position)
        arc_radius = self.radius * self.zoom * math.sqrt(3.0) / 2.0
        bounds = (center_x - arc_radius, center_y - arc_radius,
                  center_x + arc_radius, center_y + arc_radius)
        start = (300.0 - side_index * 60.0) % 360.0
        item = self.create_arc(*bounds, start=start, extent=-60.0,
                               style=tk.ARC, outline=color, width=width,
                               tags=tags)
        self._track_zoom_stroke(item, width)
        return item

    def _track_zoom_stroke(self, item, width):
        self._zoom_stroke_widths[item] = width / max(self.zoom, 0.001)
        return item

    def _draw_cell_arcs(self, boundary_sides, color, width, tags):
        segments = self._cell_arc_segments(boundary_sides)
        return [self._create_cell_arc(position, side_index, color, width, tags)
                for position, side_index in segments]

    def _corner_gap_fill(self, positions):
        colors = [(position, self._hex_fill(position)) for position in positions]
        counts = {}
        for _, color in colors:
            counts[color] = counts.get(color, 0) + 1
        highest_count = max(counts.values())
        if highest_count > 1:
            majority = next(color for _, color in colors
                            if counts[color] == highest_count)
            return dict((position, majority) for position, _ in colors)
        return dict(colors)

    def _draw_corner_gaps(self):
        self.corner_gap_items = {}
        self.corner_gap_tiles = {}
        self.corner_gap_geometry = {}
        self.tile_corner_gaps = {}
        vertices = {}
        for position in self.model.tiles:
            center_x, center_y = self._screen_center(position)
            points = self._hex_points(center_x, center_y, self.radius * self.zoom)
            for vertex_index in range(6):
                vertex = (round(points[2 * vertex_index], 3),
                          round(points[2 * vertex_index + 1], 3))
                vertices.setdefault(vertex, []).append((position, vertex_index, points))

        for vertex, corners in vertices.items():
            positions = tuple(sorted(
                {position for position, _, _ in corners},
                key=lambda position: (position[1], position[0])))
            midpoints = {}
            tile_midpoints = {}
            for position, vertex_index, points in corners:
                tile_midpoints[position] = []
                for side_index in ((vertex_index - 1) % 6, vertex_index):
                    next_index = (side_index + 1) % 6
                    midpoint = (
                        (points[2 * side_index] + points[2 * next_index]) / 2.0,
                        (points[2 * side_index + 1] + points[2 * next_index + 1]) / 2.0)
                    midpoint_key = (round(midpoint[0], 3), round(midpoint[1], 3))
                    midpoints[midpoint_key] = midpoint
                    tile_midpoints[position].append(midpoint_key)
            if len(positions) < 3:
                items = {}
                for position in positions:
                    points = next(points for tile, _, points in corners
                                  if tile == position)
                    vertex_index = next(index for tile, index, _ in corners
                                        if tile == position)
                    previous_index = (vertex_index - 1) % 6
                    next_index = (vertex_index + 1) % 6
                    previous_midpoint = (
                        (points[2 * previous_index] + points[2 * vertex_index]) / 2.0,
                        (points[2 * previous_index + 1] +
                         points[2 * vertex_index + 1]) / 2.0)
                    next_midpoint = (
                        (points[2 * vertex_index] + points[2 * next_index]) / 2.0,
                        (points[2 * vertex_index + 1] +
                         points[2 * next_index + 1]) / 2.0)
                    item = self.create_polygon(
                        previous_midpoint[0], previous_midpoint[1],
                        vertex[0], vertex[1],
                        next_midpoint[0], next_midpoint[1],
                        fill=self._hex_fill(position), outline="",
                        tags=("hex-fill", "hex-corner-gap"))
                    items[position] = item
                    self.tile_corner_gaps.setdefault(position, set()).add(vertex)
                self.corner_gap_items[vertex] = items
                self.corner_gap_tiles[vertex] = positions
                continue
            if len(midpoints) != 3:
                continue
            midpoint_order = sorted(
                midpoints,
                key=lambda point: math.atan2(
                    midpoints[point][1] - vertex[1],
                    midpoints[point][0] - vertex[0]))
            triangle = [midpoints[key] for key in midpoint_order]
            triangle_indices = dict((key, index)
                                    for index, key in enumerate(midpoint_order))
            centroid = (sum(point[0] for point in triangle) / 3.0,
                        sum(point[1] for point in triangle) / 3.0)
            geometry = (triangle, centroid, positions, triangle_indices,
                        tile_midpoints)
            self.corner_gap_geometry[vertex] = geometry
            gap_fills = self._corner_gap_fill(positions)
            items = self._create_corner_gap_pieces(geometry, gap_fills)
            self.corner_gap_items[vertex] = items
            self.corner_gap_tiles[vertex] = positions
            for position in positions:
                self.tile_corner_gaps.setdefault(position, set()).add(vertex)

    def _create_corner_gap_pieces(self, geometry, fills):
        triangle, centroid, positions, triangle_indices, tile_midpoints = geometry
        if len(set(fills.values())) == 1:
            item = self.create_polygon(
                *(coordinate for point in triangle for coordinate in point),
                fill=next(iter(fills.values())), outline="",
                tags=("hex-corner-gap",))
            return dict((position, item) for position in positions)

        items = {}
        for position in positions:
            first, second = sorted(
                triangle_indices[key] for key in tile_midpoints[position])
            coordinates = [value for point in
                           (centroid, triangle[first], triangle[second])
                           for value in point]
            items[position] = self.create_polygon(
                *coordinates, fill=fills[position], outline="",
                tags=("hex-corner-gap",))
        return items

    def _update_corner_gaps(self, position):
        for vertex in self.tile_corner_gaps.get(position, ()):
            items = self.corner_gap_items.get(vertex, {})
            fills = self._corner_gap_fill(self.corner_gap_tiles[vertex])
            geometry = self.corner_gap_geometry.get(vertex)
            if geometry:
                for item in set(items.values()):
                    self.delete(item)
                items = self._create_corner_gap_pieces(geometry, fills)
                self.corner_gap_items[vertex] = items
                self.tag_lower("hex-corner-gap", "hex-fill")
            else:
                for tile, item in items.items():
                    self.itemconfigure(item, fill=fills[tile])

    @staticmethod
    def _cell_arc_segments(boundary_sides):
        segments = set()
        for position, side_index in boundary_sides:
            segments.add((position, (side_index - 1) % 6))
            segments.add((position, side_index))
        return segments

    def _draw_smooth_cell_boundary(self, positions, color, width, tags):
        positions = set(positions)
        edges = []
        for position in positions:
            if position[1] % 2:
                directions = (
                    (1, 0, 5), (-1, 0, 2), (0, -1, 3),
                    (1, -1, 4), (0, 1, 1), (1, 1, 0))
            else:
                directions = (
                    (1, 0, 5), (-1, 0, 2), (-1, -1, 3),
                    (0, -1, 4), (-1, 1, 1), (0, 1, 0))
            center_x, center_y = self._screen_center(position)
            points = self._hex_points(
                center_x, center_y, self.radius * self.zoom)
            for delta_col, delta_row, side_index in directions:
                neighbor = (position[0] + delta_col,
                            position[1] + delta_row)
                if neighbor in positions:
                    continue
                first = (points[2 * side_index], points[2 * side_index + 1])
                next_index = (side_index + 1) % 6
                second = (points[2 * next_index], points[2 * next_index + 1])
                edges.append((first, second))

        def point_key(point):
            return (round(point[0], 3), round(point[1], 3))

        outgoing = {}
        for edge_index, (first, _) in enumerate(edges):
            outgoing.setdefault(point_key(first), []).append(edge_index)
        remaining = set(range(len(edges)))
        while remaining:
            first_edge = min(remaining)
            first_point = edges[first_edge][0]
            edge_index = first_edge
            loop = []
            while edge_index in remaining:
                remaining.remove(edge_index)
                start, end = edges[edge_index]
                loop.append(start)
                end_key = point_key(end)
                if end_key == point_key(first_point):
                    break
                candidates = [candidate for candidate in outgoing.get(end_key, ())
                              if candidate in remaining]
                if not candidates:
                    loop = []
                    break
                incoming = (end[0] - start[0], end[1] - start[1])

                def straightness(candidate):
                    next_start, next_end = edges[candidate]
                    direction = (next_end[0] - next_start[0],
                                 next_end[1] - next_start[1])
                    lengths = math.hypot(*incoming) * math.hypot(*direction)
                    return ((incoming[0] * direction[0] +
                             incoming[1] * direction[1]) / lengths
                            if lengths else -1)

                edge_index = max(candidates, key=straightness)
            if len(loop) >= 3:
                coordinates = [value for point in loop for value in point]
                item = self.create_polygon(
                    *coordinates, fill="", outline=color, width=width,
                    smooth=True, splinesteps=12, joinstyle=tk.ROUND,
                    tags=tags)
                self._track_zoom_stroke(item, width)

    def _draw_terrain_symbol(self, terrain, center_x, center_y):
        if terrain in ("Plain", "Water"):
            return
        scale = max(0.2, min(1.25, self.zoom))
        width = max(0.6, self.zoom)
        if terrain == "Forest":
            color = "#3e5e49"
            for offset in (-3, 2):
                self.create_polygon(
                    center_x + offset * scale, center_y - 5 * scale,
                    center_x + (offset - 4) * scale, center_y + 3 * scale,
                    center_x + (offset + 4) * scale, center_y + 3 * scale,
                    fill=color, outline="",
                    tags=("terrain-icon", "terrain-detail"))
        elif terrain == "Hill":
            self.create_line(center_x - 8 * scale, center_y + 4 * scale,
                             center_x - 2 * scale, center_y - 4 * scale,
                             center_x + 2 * scale, center_y + 1 * scale,
                             center_x + 6 * scale, center_y - 4 * scale,
                             center_x + 9 * scale, center_y + 4 * scale,
                             fill="#756b50", width=width,
                             joinstyle=tk.ROUND,
                             tags=("terrain-icon", "terrain-detail"))
        elif terrain == "Desert":
            for offset in (-2, 3):
                self.create_line(center_x - 7 * scale, center_y + offset * scale,
                                 center_x - 3 * scale, center_y + (offset - 1) * scale,
                                 center_x + scale, center_y + offset * scale,
                                 center_x + 6 * scale, center_y + (offset - 1) * scale,
                                 fill="#9a7a43", width=width, smooth=True,
                                 tags=("terrain-icon", "terrain-detail"))
        else:
            self.create_line(center_x - 5 * scale, center_y + 3 * scale,
                             center_x - 2 * scale, center_y - 2 * scale,
                             center_x, center_y + 3 * scale,
                             center_x + 3 * scale, center_y - 3 * scale,
                             center_x + 6 * scale, center_y + 3 * scale,
                             fill="#66764f", width=width,
                             joinstyle=tk.ROUND,
                             tags=("terrain-icon", "terrain-detail"))

    @staticmethod
    def _roman_numeral(value):
        if value == 0:
            return "N"
        if value < 0:
            return str(value)
        result = []
        for amount, symbol in ((90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
                               (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
            count, value = divmod(value, amount)
            result.extend([symbol] * count)
        return "".join(result)

    def _draw_city_overview(self, city, position, center_x, center_y):
        owner_color = self.country_mark_colors.get(city["owner"], "#777777")
        marker_radius = 2.0
        self.create_oval(
            center_x - marker_radius, center_y - marker_radius,
            center_x + marker_radius, center_y + marker_radius,
            fill=owner_color, outline=INK_COLOR, width=1,
            tags=("overview-city", self._city_owner_tag(position)))
        self._create_text(
            center_x + marker_radius + 2, center_y - 2,
            text=city["name"], fill=INK_COLOR,
            font=("Segoe UI", 8, "bold"), max_font_size=8, anchor="w",
            tags=("overview-city-label", "overview-city"))

    def _draw_city_detail(self, city, position, center_x, center_y):
        diameter = self.radius * 2 * self.zoom
        center_x -= diameter * 0.035
        bar_width = diameter * 0.78
        bar_height = diameter * 0.12
        badge_center_x = center_x - diameter * 0.27
        bar_left = badge_center_x
        bar_top = center_y - diameter * 0.35
        bar_bottom = bar_top + bar_height
        level_radius = diameter * 0.13
        owner_color = self.country_mark_colors.get(city["owner"], "#777777")
        health_color = self._city_health_color(city)

        name_size = max(5, min(9, int(diameter * 0.72 /
                                      max(1, len(city["name"]) * 0.58))))
        self._create_text(
            center_x + diameter * 0.08, bar_top - 1,
            text=city["name"], fill=INK_COLOR,
            font=("Segoe UI", name_size, "bold"), max_font_size=9,
            anchor="s", tags=("city-label", "city-detail"))

        city_tag = "{}-{}".format(*position)
        self.create_rectangle(
            bar_left, bar_top, bar_left + bar_width, bar_bottom,
            fill="#898d8b", outline=INK_COLOR, width=1,
            tags=("city-marker", "city-detail",
                  "city-health-overlay",
                  "city-health-track-{}".format(city_tag)))
        ratio = (float(city["health"]) / city["max_health"]
                 if city["max_health"] else 0.0)
        self.create_rectangle(
            bar_left, bar_top, bar_left + bar_width * ratio, bar_bottom,
            fill=health_color, outline="",
            tags=("city-health-{}".format(city_tag), "city-health-overlay",
                  "city-detail"))
        badge_center_y = (bar_top + bar_bottom) / 2.0 + diameter * 0.03
        self.create_oval(
            badge_center_x - level_radius,
            badge_center_y - level_radius,
            badge_center_x + level_radius,
            badge_center_y + level_radius,
            fill=owner_color, outline=INK_COLOR, width=1,
            tags=("city-detail", "city-level-badge",
                self._city_owner_tag(position)))
        self.create_text(
            badge_center_x, badge_center_y,
            text=self._roman_numeral(city["city_level"]), fill="white",
            font=("Segoe UI", max(6, int(diameter * 0.19)), "bold"),
            tags=("city-detail", "city-level-badge"))

        level_top = bar_bottom
        level_height = diameter * 0.08
        level_width = bar_width * 0.25
        level_top -= level_height * 0.5
        level_left = bar_left + level_radius * 0.75
        production_levels = (
            (city["industry_level"], "#c9ac4b"),
            (city["research_level"], "#b6aec5"))
        visible_levels = [item for item in production_levels if item[0] > 0]
        for index, (value, fill) in enumerate(visible_levels):
            left = level_left + index * level_width
            top = level_top 
            top += diameter * 0.03
            level_tag = "city-level-{}-{}-{}".format(
                position[0], position[1], index)
            self.create_rectangle(
                left, top, left + level_width, top + level_height,
                fill=fill, outline=INK_COLOR, width=0.5,
                    tags=("city-detail", "city-production-level",
                        "city-level-block", level_tag))
            self.create_text(
                left + level_width / 2.0, top + level_height / 2.0,
                text=self._roman_numeral(value), fill="white",
                    font=("Segoe UI", max(6, int(diameter * 0.1)), "bold"),
                    tags=("city-detail", "city-production-level",
                        "city-level-text", level_tag))

        icon_x = center_x
        house_width = diameter * 0.3
        house_top = center_y - diameter * 0.12
        wall_top = center_y - diameter * 0.04
        house_bottom = center_y + diameter * 0.12
        house_tag = "city-house-{}-{}".format(*position)
        self.create_polygon(
            icon_x, house_top,
            icon_x + house_width / 2.0, wall_top,
            icon_x + house_width / 2.0, house_bottom,
            icon_x - house_width / 2.0, house_bottom,
            icon_x - house_width / 2.0, wall_top,
            fill="#fffdf5", outline=INK_COLOR, width=0.5,
            tags=("city-marker", "city-detail", "city-house", house_tag))
        self.create_line(
            icon_x, center_y + diameter * 0.04, icon_x, house_bottom,
            fill="#8e938f", width=max(0.5, self.zoom),
            tags=("city-marker", "city-detail", "city-house", house_tag))

    def draw(self):
        if not self.winfo_exists():
            return
        if self._camera_update_id is not None:
            self.after_cancel(self._camera_update_id)
            self._camera_update_id = None
        self.delete("all")
        self._update_screen_geometry()
        self._detail_visibility_key = None
        self._text_fonts = {}
        self._zoom_stroke_widths = {}
        if self._style_update_id is not None:
            self.after_cancel(self._style_update_id)
            self._style_update_id = None
        self.hex_items = {}
        radius = self.radius * self.zoom
        low_detail = 2 * radius <= self.detail_threshold
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
            fill = self._hex_fill(position)
            fill_radius = radius * math.sqrt(3.0) / 2.0
            self.hex_items[position] = self.create_oval(
                center_x - fill_radius, center_y - fill_radius,
                center_x + fill_radius, center_y + fill_radius,
                fill=fill, outline="", width=0, tags=("hex-fill",))

            self._draw_terrain_symbol(terrain, center_x, center_y)

            city = self.model.cities.get(position)
            if city:
                self._draw_city_overview(city, position, center_x, center_y)
                self._draw_city_detail(city, position, center_x, center_y)
        self._draw_corner_gaps()
        self.tag_lower("hex-fill")
        self.tag_lower("hex-corner-gap", "hex-fill")
        self._draw_city_territory_boundaries()
        if self.find_withtag("city-detail"):
            self.tag_lower("territory-boundary", "city-detail")

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

        self._draw_unit_layer()
        self._draw_selection_overlay()
        self._tag_display_layers()
        self._update_detail_visibility()

        self._canvas_size = (self.winfo_width(), self.winfo_height())
        self._canvas_zoom = self.zoom
        self._canvas_pan = (self.pan_x, self.pan_y)
        self._style_zoom = self.zoom
        self._drawn_state_key = self._visual_state_key()
        self._drawn_background_key = self._background_state_key()
        self._drawn_unit_key = self._unit_state_key()
        self._drawn_selection_key = self._selection_state_key()

    def _draw_unit_layer(self):
        self.overview_unit_items = {}
        for unit in self.model.units:
            unit_tag = "unit-animation-{}".format(
                getattr(unit, "id", id(unit)))
            center_x, center_y = self._screen_center(unit.position)
            unit_faction = self.model.faction_for(unit.owner)
            unit_color = (self.country_mark_colors.get(unit.owner, "#777777")
                          if unit_faction != NEUTRAL else "#777777")
            mark = (TRANSPORT_STATS["symbol"] if unit.embarked else
                    UNIT_TYPES[unit.kind]["symbol"])
            badge = max(2.8, min(5.0, 5 * self.zoom))
            unit_y = center_y + 3 * self.zoom
            self.overview_unit_items[unit_tag] = self.create_oval(
                center_x - badge, unit_y - badge,
                center_x + badge, unit_y + badge,
                fill=unit_color, outline="", width=0,
                tags=("unit-layer", "overview-unit", unit_tag))

            unit_y = center_y + 7 * self.zoom
            badge = 12 * self.zoom
            player_country_id = getattr(self.model, "player_country_id", None)
            is_player_unit = (unit.owner == player_country_id if player_country_id
                             else unit.faction == PLAYER)
            if (is_player_unit and getattr(self.model, "phase", None) == PLAYER and
                    (unit.movement_left > 0 or not unit.attacked)):
                marker_size = 4 * self.zoom
                offset = badge + 5 * self.zoom
                for delta_x, delta_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    marker_x = center_x + delta_x * offset
                    marker_y = unit_y + delta_y * offset
                    if delta_y < 0:
                        points = (marker_x, marker_y - marker_size,
                                  marker_x - marker_size, marker_y + marker_size / 2,
                                  marker_x + marker_size, marker_y + marker_size / 2)
                    elif delta_y > 0:
                        points = (marker_x, marker_y + marker_size,
                                  marker_x - marker_size, marker_y - marker_size / 2,
                                  marker_x + marker_size, marker_y - marker_size / 2)
                    elif delta_x < 0:
                        points = (marker_x - marker_size, marker_y,
                                  marker_x + marker_size / 2, marker_y - marker_size,
                                  marker_x + marker_size / 2, marker_y + marker_size)
                    else:
                        points = (marker_x + marker_size, marker_y,
                                  marker_x - marker_size / 2, marker_y - marker_size,
                                  marker_x - marker_size / 2, marker_y + marker_size)
                    self.create_polygon(*points, fill="#d0a44c", outline="",
                                        tags=("unit-layer", "unit-detail",
                                        "action-ready", unit_tag))
            self.create_oval(center_x - badge, unit_y - badge,
                             center_x + badge, unit_y + badge,
                             fill=unit_color, outline="#fff9e9",
                             width=max(1, self.zoom),
                             tags=("unit-layer", "unit-detail", unit_tag))
            self._create_text(center_x, unit_y, text=mark, fill="white",
                              font=("Segoe UI", max(7, int(9 * self.zoom)), "bold"),
                              max_font_size=12,
                              tags=("unit-layer", "unit-detail", unit_tag))
            morale_level = self._morale_level(unit)
            if morale_level:
                marker_x = center_x + badge * 0.62
                marker_y = unit_y - badge * 0.58
                marker_size = badge * 0.6
                if morale_level > 0:
                    direction, color = "up", "#f0c83e"
                elif morale_level <= -2:
                    direction, color = "down", "#505050"
                else:
                    direction, color = "down", "#a5a5a5"
                self._draw_morale_arrow(marker_x, marker_y, marker_size,
                                        direction, color,
                                    tags=("unit-layer", "unit-detail",
                                        "unit-status", unit_tag))
                if morale_level <= -2:
                    overlap = marker_size * 0.24
                    self._draw_morale_arrow(
                        marker_x - overlap, marker_y, marker_size, "down", color,
                        tags=("unit-layer", "unit-detail", "unit-status",
                            unit_tag))
                    self._draw_morale_arrow(
                        marker_x + overlap, marker_y, marker_size, "down", color,
                        tags=("unit-layer", "unit-detail", "unit-status",
                            unit_tag))
            bar_width = 23 * self.zoom
            bar_y = unit_y + 15 * self.zoom
            self.create_rectangle(center_x - bar_width / 2, bar_y,
                                  center_x + bar_width / 2,
                                  bar_y + 3 * self.zoom,
                                  fill="#898d8b", outline="",
                                  tags=("unit-layer", "unit-detail", unit_tag))
            player_faction = getattr(self.model, "player_faction", PLAYER)
            health_color = ("#87a777" if unit_faction == player_faction else
                            "#999999" if unit_faction == NEUTRAL else "#cf7564")
            self.create_rectangle(center_x - bar_width / 2, bar_y,
                                  center_x - bar_width / 2 +
                                  bar_width * unit.hp / unit.max_hp,
                                  bar_y + 3 * self.zoom, fill=health_color,
                                  outline="", tags=("unit-layer", "unit-detail",
                                                   unit_tag))
        self.addtag_withtag("detail-layer", "unit-detail")
        self.addtag_withtag("overview-layer", "overview-unit")
        self.tag_raise("city-production-level")
        self.tag_raise("city-health-overlay")
        self.tag_raise("city-level-badge")

    def animate_unit_path(self, unit_id, start_position, path, duration=0.2):
        if not path or self.unit_animation_active:
            return False
        tag = "unit-animation-{}".format(unit_id)
        if not self.find_withtag(tag):
            return False
        positions = [start_position] + list(path)
        points = [self._screen_center(position) for position in positions]
        lengths = [math.hypot(second[0] - first[0], second[1] - first[1])
                   for first, second in zip(points, points[1:])]
        total_length = sum(lengths)
        if total_length <= 0:
            return False
        self.move(tag, points[0][0] - points[-1][0],
                  points[0][1] - points[-1][1])
        self.unit_animation_active = True
        start_time = time.time()
        previous_point = points[0]

        def animate_frame():
            nonlocal previous_point
            if not self.winfo_exists():
                self.unit_animation_active = False
                self.unit_animation_after_id = None
                return
            progress = min(1.0, (time.time() - start_time) / duration)
            distance = total_length * progress
            remaining = distance
            current_point = points[-1]
            for index, length in enumerate(lengths):
                if remaining <= length or index == len(lengths) - 1:
                    ratio = min(1.0, remaining / length) if length else 1.0
                    first, second = points[index], points[index + 1]
                    current_point = (first[0] + (second[0] - first[0]) * ratio,
                                     first[1] + (second[1] - first[1]) * ratio)
                    break
                remaining -= length
            self.move(tag, current_point[0] - previous_point[0],
                      current_point[1] - previous_point[1])
            previous_point = current_point
            if progress >= 1.0:
                self.unit_animation_active = False
                self.unit_animation_after_id = None
                return
            self.unit_animation_after_id = self.after(16, animate_frame)

        self.unit_animation_after_id = self.after(0, animate_frame)
        return True

    def animate_damage_number(self, position, damage, delay=0):
        def start_animation():
            if not self.winfo_exists():
                return
            center_x, center_y = self._screen_center(position)
            start_y = center_y - 10 * self.zoom
            text = self.create_text(
                center_x, start_y, text="-{}".format(damage),
                fill="#f2eee2", font=("Segoe UI", max(10, int(13 * self.zoom)),
                                      "bold"),
                tags=("floating-damage",))
            start_color = (242, 238, 226)
            background_color = tuple(
                channel // 256 for channel in
                self.winfo_rgb(self.cget("background")))
            duration = 720
            started = time.time()

            def animate_frame():
                if not self.winfo_exists():
                    return
                progress = min(1.0, (time.time() - started) * 1000.0 / duration)
                self.coords(text, center_x,
                            start_y - 28 * self.zoom * progress)
                color = "#%02x%02x%02x" % tuple(
                    int(start + (end - start) * progress)
                    for start, end in zip(start_color, background_color))
                self.itemconfigure(text, fill=color)
                if progress >= 1.0:
                    self.delete(text)
                    return
                self.after(35, animate_frame)

            self.after(0, animate_frame)

        self.after(max(0, delay), start_animation)
        return True

    def _draw_selection_overlay(self):
        radius = self.radius * self.zoom
        if self.selected_hex in self.model.tiles:
            self._draw_cell_arcs(
                [(self.selected_hex, index) for index in range(6)],
                "#202c27", self.zoom * 3.0,
                ("selection-overlay", "hex-highlight"))
        if self.attack_target in self.model.tiles:
            self._draw_cell_arcs(
                [(self.attack_target, index) for index in range(6)],
                "#b95849", self.zoom * 3.0,
                ("selection-overlay", "hex-highlight"))

        city = self.model.cities.get(self.selected_hex)
        if city and self.model.unit_at(self.selected_hex) is None:
            center_x, center_y = self._screen_center(self.selected_hex)
            city_bar_width = 23 * self.zoom
            city_bar_y = center_y + 2 * self.zoom
            owner_color = self.country_mark_colors.get(city["owner"], "#47745f")
            self.create_rectangle(center_x - city_bar_width / 2, city_bar_y,
                                  center_x + city_bar_width / 2,
                                  city_bar_y + 3 * self.zoom,
                                  fill="#f2eee2", outline="",
                                  tags="selection-overlay")
            self.create_rectangle(
                center_x - city_bar_width / 2, city_bar_y,
                center_x - city_bar_width / 2 + city_bar_width * city["health"] /
                city["max_health"], city_bar_y + 3 * self.zoom,
                fill=self._city_health_color(city), outline="",
                tags="selection-overlay")

        if (self.selected_unit and self.model.phase == PLAYER and
                self.selected_unit.owner == getattr(self.model, "player_country_id", None) and
                not self.selected_unit.attacked):
            if self.selected_unit.movement_left > 0:
                current_reachable = set(
                    self.model.movement_paths(self.selected_unit))
                current_reachable.add(self.selected_unit.position)
                if getattr(self.selected_unit, "movement_extended", False):
                    base_reachable = set(self.model.movement_paths(
                        self.selected_unit,
                        budget=self.selected_unit.base_movement))
                    base_reachable.add(self.selected_unit.position)
                    self._draw_smooth_cell_boundary(
                        current_reachable, "#df7b32", self.zoom * 4,
                        ("selection-overlay", "move-range",
                         "extended-move-range"))
                    self._draw_smooth_cell_boundary(
                        base_reachable, "#c08d28", self.zoom * 4,
                        ("selection-overlay", "move-range", "base-move-range"))
                else:
                    self._draw_smooth_cell_boundary(
                        current_reachable, "#c08d28", self.zoom * 4,
                        ("selection-overlay", "move-range", "base-move-range"))
            for enemy in self.model.units:
                if enemy.faction in (self.selected_unit.faction, NEUTRAL):
                    continue
                if self.model.distance(self.selected_unit.position, enemy.position) <= self.selected_unit.range:
                    center_x, center_y = self._screen_center(enemy.position)
                    self._draw_attack_marker(center_x, center_y, radius)
            for position, city in self.model.cities.items():
                if (city["health"] > 0 and
                        self.model.faction_for(city["owner"]) != self.selected_unit.faction and
                        self.model.distance(self.selected_unit.position, position) <=
                        self.selected_unit.range):
                    center_x, center_y = self._screen_center(position)
                    self._draw_attack_marker(center_x, center_y, radius)
                self.addtag_withtag("detail-layer", "selection-overlay")
                self.itemconfigure("selection-overlay",
                           state="hidden" if self.low_detail else "normal")

    def _draw_attack_marker(self, center_x, center_y, radius):
        marker_radius = radius * 0.62
        arm = radius * 0.9
        gap = radius * 0.38
        color = "#74352f"
        width = self.zoom * 2.5
        item = self.create_oval(center_x - marker_radius, center_y - marker_radius,
                                center_x + marker_radius, center_y + marker_radius,
                                fill="", outline=color, width=width,
                                tags=("selection-overlay", "attack-range"))
        self._track_zoom_stroke(item, width)
        for start_x, start_y, end_x, end_y in (
                (-arm, 0, -gap, 0), (gap, 0, arm, 0),
                (0, -arm, 0, -gap), (0, gap, 0, arm)):
            item = self.create_line(center_x + start_x, center_y + start_y,
                                    center_x + end_x, center_y + end_y,
                                    fill=color, width=width, capstyle=tk.ROUND,
                                    tags=("selection-overlay", "attack-range"))
            self._track_zoom_stroke(item, width)

    def _draw_morale_arrow(self, center_x, center_y, size, direction, color,
                           tags="unit-status"):
        half = size / 2.0
        stem = size * 0.28
        if direction == "up":
            points = (center_x, center_y - half,
                      center_x + half, center_y,
                      center_x + stem / 2, center_y,
                      center_x + stem / 2, center_y + half,
                      center_x - stem / 2, center_y + half,
                      center_x - stem / 2, center_y,
                      center_x - half, center_y)
        else:
            points = (center_x, center_y + half,
                      center_x + half, center_y,
                      center_x + stem / 2, center_y,
                      center_x + stem / 2, center_y - half,
                      center_x - stem / 2, center_y - half,
                      center_x - stem / 2, center_y,
                      center_x - half, center_y)
        self.create_polygon(*points, fill=color, outline="#303030",
                            width=max(1, self.zoom), tags=tags)

    def _on_press(self, event):
        if self.unit_animation_active:
            return
        self.drag_origin = (event.x, event.y)
        self.last_drag_position = (event.x, event.y)
        self.dragged = False
        self.paint_dragging = False
        self.last_painted_hex = None
        if ((not self.low_detail or self.allow_low_detail_interaction) and
            self.on_hex_drag and not (event.state & 0x0001)):
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.paint_dragging = bool(self.on_hex_drag(position))
                if self.paint_dragging:
                    self.last_painted_hex = position

    def _on_drag(self, event):
        if self.unit_animation_active:
            return
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
            self._schedule_camera_transform()
            self.last_drag_position = (event.x, event.y)

    def _on_release(self, event):
        if self.unit_animation_active:
            self.drag_origin = None
            self.last_drag_position = None
            return
        if ((not self.low_detail or self.allow_low_detail_interaction) and
            not self.dragged):
            position = self._hex_at(event.x, event.y)
            if position is not None:
                self.on_hex_click(position)
        self.drag_origin = None
        self.last_drag_position = None
        self.paint_dragging = False
        self.last_painted_hex = None

    def _draw_city_territory_boundaries(self):
        self.territory_edge_sides = {}
        self.territory_edge_items = {}
        self.territory_edge_segments = {}
        self.territory_segment_items = {}
        self.territory_vertex_corners = {}
        self.territory_vertex_segments = {}
        self.territory_side_edges = {}
        self.territory_edge_vertices = {}
        self.territory_edge_kinds = {}
        self.tile_boundary_edges = {}
        self.city_territory_tiles = {}
        self.tile_city_owner = {}
        for position, terrain in self.model.tiles.items():
            city = self.model.city_for_hex(position)
            if city:
                city_position = city["position"]
                self.tile_city_owner[position] = city_position
                self.city_territory_tiles.setdefault(
                    city_position, []).append(position)
            center_x, center_y = self._screen_center(position)
            points = self._hex_points(center_x, center_y, self.radius * self.zoom)
            vertices = [(points[index * 2], points[index * 2 + 1])
                        for index in range(6)]
            for index, vertex in enumerate(vertices):
                vertex_key = (round(vertex[0], 3), round(vertex[1], 3))
                self.territory_vertex_corners.setdefault(
                    vertex_key, []).append((position, index))
            for index in range(6):
                first = vertices[index]
                second = vertices[(index + 1) % 6]
                first_vertex = (round(first[0], 3), round(first[1], 3))
                second_vertex = (round(second[0], 3), round(second[1], 3))
                key = tuple(sorted((first_vertex, second_vertex)))
                self.territory_edge_sides.setdefault(key, []).append(
                    (position, index))
                self.territory_side_edges[(position, index)] = key
                self.territory_edge_vertices[key] = (first_vertex, second_vertex)
                self.tile_boundary_edges.setdefault(position, []).append(key)
        for key in self.territory_edge_sides:
            kind = self._territory_edge_kind(key)
            if kind is not None:
                self.territory_edge_kinds[key] = kind
        self._rebuild_territory_vertex_segments()

    def _territory_edge_kind(self, key):
        sides = self.territory_edge_sides[key]
        if len(sides) != 2:
            return None
        first_position, second_position = sides[0][0], sides[1][0]
        if (self.model.tiles[first_position] == "Water" or
                self.model.tiles[second_position] == "Water"):
            return None
        first_city = self.model.city_for_hex(first_position)
        second_city = self.model.city_for_hex(second_position)
        first_territory = first_city["position"] if first_city else None
        second_territory = second_city["position"] if second_city else None
        if first_territory == second_territory:
            return None
        if (first_city is not None and second_city is not None and
                first_city["owner"] != second_city["owner"]):
            return "national"
        return "city"

    def _update_territory_edge(self, key, rebuild=True):
        old_kind = self.territory_edge_kinds.get(key)
        new_kind = self._territory_edge_kind(key)
        if old_kind == new_kind:
            return False
        if new_kind is None:
            self.territory_edge_kinds.pop(key, None)
        else:
            self.territory_edge_kinds[key] = new_kind
        if rebuild:
            self._rebuild_territory_vertex_segments()
        return True

    def _territory_edge_midpoint(self, edge):
        sides = self.territory_edge_sides.get(edge, ())
        if not sides:
            return ((edge[0][0] + edge[1][0]) / 2.0,
                    (edge[0][1] + edge[1][1]) / 2.0)
        position, side_index = sides[0]
        center_x, center_y = self._screen_center(position)
        points = self._hex_points(center_x, center_y, self.radius * self.zoom)
        next_index = (side_index + 1) % 6
        return ((points[2 * side_index] + points[2 * next_index]) / 2.0,
                (points[2 * side_index + 1] + points[2 * next_index + 1]) / 2.0)

    def _territory_vertex_point(self, corner):
        position, vertex_index = corner
        center_x, center_y = self._screen_center(position)
        points = self._hex_points(center_x, center_y, self.radius * self.zoom)
        return (points[2 * vertex_index], points[2 * vertex_index + 1])

    def _territory_color_key(self, position):
        return self._hex_fill(position)

    def _rebuild_territory_vertex_segments(self):
        for item in self.territory_segment_items.values():
            self.delete(item)
        self.territory_segment_items = {}
        self.territory_vertex_segments = {}
        for vertex, corners in self.territory_vertex_corners.items():
            vertex_point = self._territory_vertex_point(corners[0])
            incident_edges = set()
            for position, vertex_index in corners:
                incident_edges.add(self.territory_side_edges[
                    (position, (vertex_index - 1) % 6)])
                incident_edges.add(self.territory_side_edges[
                    (position, vertex_index)])
            active_edges = [(edge, self.territory_edge_kinds[edge])
                            for edge in incident_edges
                            if edge in self.territory_edge_kinds]
            junction_edges = {edge for edge, _ in active_edges}
            positions = set(position for position, _ in corners)
            three_color_vertex = (
                len(positions) == 3 and len(set(
                    self._territory_color_key(position)
                    for position in positions)) == 3)

            if three_color_vertex or len(junction_edges) >= 3:
                for edge in junction_edges:
                    kind = self.territory_edge_kinds.get(edge, "city")
                    midpoint = self._territory_edge_midpoint(edge)
                    color = "#263b30" if kind == "national" else "#506657"
                    line_width = (2.2 if kind == "national" else 1.8) * self.zoom
                    item = self.create_line(
                        midpoint[0], midpoint[1],
                        vertex_point[0], vertex_point[1],
                        fill=color, width=line_width, capstyle=tk.ROUND,
                        tags=("territory-boundary", "territory-junction"))
                    self._track_zoom_stroke(item, line_width)
                    key = ("junction", vertex, edge)
                    self.territory_segment_items[key] = item
                    self.territory_vertex_segments.setdefault(
                        vertex, set()).add(key)
                continue

            if len(active_edges) == 1:
                edge, kind = active_edges[0]
                if any(len(self.territory_edge_sides[candidate]) == 1
                       for candidate in incident_edges if candidate != edge):
                    midpoint = self._territory_edge_midpoint(edge)
                    color = "#263b30" if kind == "national" else "#506657"
                    line_width = (2.2 if kind == "national" else 1.8) * self.zoom
                    item = self.create_line(
                        midpoint[0], midpoint[1],
                        vertex_point[0], vertex_point[1],
                        fill=color, width=line_width, capstyle=tk.ROUND,
                        tags=("territory-boundary", "territory-outer-extension"))
                    self._track_zoom_stroke(item, line_width)
                    key = ("outer-extension", vertex, edge)
                    self.territory_segment_items[key] = item
                    self.territory_vertex_segments.setdefault(
                        vertex, set()).add(key)
                continue

            if len(active_edges) == 2:
                active_keys = {edge for edge, _ in active_edges}
                for position, vertex_index in corners:
                    first_side = (vertex_index - 1) % 6
                    first_edge = self.territory_side_edges[(position, first_side)]
                    second_edge = self.territory_side_edges[(position, vertex_index)]
                    if first_edge not in active_keys or second_edge not in active_keys:
                        continue
                    kinds = (self.territory_edge_kinds[first_edge],
                             self.territory_edge_kinds[second_edge])
                    national_border = "national" in kinds
                    color = "#263b30" if national_border else "#506657"
                    line_width = (2.2 if national_border else 1.8) * self.zoom
                    segment = (position, first_side)
                    item = self._create_cell_arc(
                        position, first_side, color, line_width,
                        "territory-boundary")
                    self.territory_segment_items[segment] = item
                    self.territory_vertex_segments.setdefault(
                        vertex, set()).add(segment)

    def _on_wheel(self, event):
        if self.unit_animation_active:
            return
        factor = 1.12 if event.delta > 0 else 1.0 / 1.12
        self._zoom_at(event.x, event.y, factor)

    def _zoom_at(self, x, y, factor):
        if self.unit_animation_active:
            return
        old_zoom = self.zoom
        new_zoom = max(self.min_zoom, min(self.max_zoom, old_zoom * factor))
        if new_zoom == old_zoom:
            return
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        world_x = (x - width / 2.0 - self.pan_x) / old_zoom
        world_y = (y - height / 2.0 - self.pan_y) / old_zoom
        self.zoom = new_zoom
        self.pan_x = x - width / 2.0 - world_x * new_zoom
        self.pan_y = y - height / 2.0 - world_y * new_zoom
        self._schedule_camera_transform()
        self._update_detail_visibility()
        if self._style_update_id is not None:
            self.after_cancel(self._style_update_id)
        self._style_update_id = self.after(130, self._apply_zoom_styles)

    def _schedule_camera_transform(self):
        if self._camera_update_id is None:
            self._camera_update_id = self.after(16, self._apply_camera_transform)

    def _apply_camera_transform(self):
        self._camera_update_id = None
        if not self.hex_items:
            return
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        old_pan_x, old_pan_y = self._canvas_pan
        scale = self.zoom / self._canvas_zoom
        if scale != 1.0:
            self.scale("all", width / 2.0 + old_pan_x,
                       height / 2.0 + old_pan_y, scale, scale)
        delta_x = self.pan_x - old_pan_x
        delta_y = self.pan_y - old_pan_y
        if delta_x or delta_y:
            self.move("all", delta_x, delta_y)
        self._canvas_zoom = self.zoom
        self._canvas_pan = (self.pan_x, self.pan_y)
        self._update_overview_unit_markers()

    def _update_overview_unit_markers(self):
        for unit in self.model.units:
            unit_tag = "unit-animation-{}".format(
                getattr(unit, "id", id(unit)))
            item = self.overview_unit_items.get(unit_tag)
            if item is None or not self.type(item):
                continue
            center_x, center_y = self._screen_center(unit.position)
            radius = max(2.8, min(5.0, 5 * self.zoom))
            unit_y = center_y + 3 * self.zoom
            self.coords(item, center_x - radius, unit_y - radius,
                        center_x + radius, unit_y + radius)

    def _apply_zoom_styles(self):
        self._style_update_id = None
        if self._style_zoom == self.zoom:
            return
        self._scale_item_styles(self.zoom / self._style_zoom)
        self._apply_zoom_stroke_widths()
        self._style_zoom = self.zoom

    def _apply_zoom_stroke_widths(self):
        for item, base_width in tuple(self._zoom_stroke_widths.items()):
            if not self.type(item):
                self._zoom_stroke_widths.pop(item, None)
                continue
            self.itemconfigure(item, width=max(0.1, base_width * self.zoom))

    def _update_detail_visibility(self):
        self.low_detail = (self.force_overview or
                           2 * self.radius * self.zoom <= self.detail_threshold)
        detailed_state = "hidden" if self.low_detail else "normal"
        overview_state = "normal" if self.low_detail else "hidden"
        terrain_state = ("hidden" if self.low_detail or self.zoom < 0.28
                         else "normal")
        label_state = ("normal" if not self.low_detail and self.zoom >= 0.6
                       else "hidden")
        visibility_key = (detailed_state, overview_state, terrain_state, label_state)
        if visibility_key == self._detail_visibility_key:
            return
        self._detail_visibility_key = visibility_key
        self.itemconfigure("overview-layer", state=overview_state)
        self.itemconfigure("detail-layer", state=detailed_state)
        self.itemconfigure("terrain-detail", state=terrain_state)
        self.itemconfigure("city-label", state=label_state)

    def _tag_display_layers(self):
        for tag in ("city-detail", "unit-detail", "selection-overlay", "river",
                    "territory-boundary", "terrain-detail", "city-label"):
            self.addtag_withtag("detail-layer", tag)
        for tag in ("overview-city", "overview-unit"):
            self.addtag_withtag("overview-layer", tag)
    def set_hex_territory(self, position):
        item = self.hex_items.get(position)
        if item is None:
            return
        old_city = self.tile_city_owner.pop(position, None)
        if old_city is not None:
            self.city_territory_tiles.get(old_city, []).remove(position)
        city = self.model.city_for_hex(position)
        if city:
            city_position = city["position"]
            self.tile_city_owner[position] = city_position
            self.city_territory_tiles.setdefault(city_position, []).append(position)
        self.itemconfigure(item, fill=self._hex_fill(position))
        self._update_corner_gaps(position)
        boundary_changed = False
        for key in self.tile_boundary_edges.get(position, ()):
            boundary_changed = (
                self._update_territory_edge(key, rebuild=False) or
                boundary_changed)
        if boundary_changed:
            self._rebuild_territory_vertex_segments()

    def _hex_at(self, x, y):
        center_x, center_y = self._world_center()
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        world_x = (x - width / 2.0 - self.pan_x) / self.zoom + center_x
        world_y = (y - height / 2.0 - self.pan_y) / self.zoom + center_y
        best_position, best_distance = _nearest_hex_position(
            world_x, world_y, self.model.columns, self.model.rows, self.radius)
        if best_distance <= (self.radius * 1.08) ** 2:
            return best_position
        return None