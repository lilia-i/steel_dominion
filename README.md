# Steel Dominion

A small turn-based hex strategy game built with Python and Tkinter.

## Requirements

- Python 3.6 or newer
- Tkinter (included with most Windows Python installations)

## Run

```powershell
python steel_dominion.py
```

Run the standalone map editor with:

```powershell
python map_editor.py
```

## Portable Build

Install PyInstaller 4.10 for Python 3.6, then build from PowerShell:

```powershell
py -3.6 -m pip install PyInstaller==4.10
.\build_portable.ps1
```

The output is `dist/SteelDominion/`; keep the whole folder together when moving it. Python 3.6's PyInstaller places runtime files beside the executable rather than in `_internal/`. Edit `maps/` and `config.json` beside the executable. `config.json` is required at startup and is the authoritative source for unit, transport, terrain, resource, city, and combat values; missing or invalid required settings produce a configuration error instead of falling back to duplicate Python defaults.

Add custom unit types directly under `unit_types`. Give each entry a stable `id`; maps and saves use this ID, so keep it unchanged when renaming the unit. The entry key or `name_en` is the English display name, and optional `name_zh` sets the Chinese display name. Display names may contain spaces. Each entry also needs a category, one-character `symbol`, a `cost` with `money`, `steel`, and `technology`, plus positive integer `attack`, `range`, `hp`, and `movement` values. For example:

```json
"Scout": {
	"id": "scout",
	"name_en": "Recon Scout",
	"name_zh": "Õì²ì±ø",
	"category": "infantry",
	"symbol": "R",
	"cost": {"money": 50, "steel": 3, "technology": 0},
	"attack": 12,
	"range": 1,
	"hp": 60,
	"movement": 24
}
```

Each unit may also define a `skills` list using only the behavior `id`, display `icon`, and that behavior's parameters. Give each unit a category such as `infantry`, `armor`, `artillery`, or `ship`; multiple unit types can share one category. The `damage_bonus_vs_category` skill uses `target_category` and `bonus`, so an armor bonus applies to every current and future unit categorized as `armor`. Other built-in IDs are `terrain_training` (parameter `terrain`), `tank_momentum`, and `artillery_suppression`. Skill names and descriptions are supplied by the game. New behavior IDs still need an implementation in `unit_effects.py`. Transport category, display letter, and optional skills are set under `transport_stats`.

Use **Settings** to browse playable JSON maps, choose a country before starting, and start or restart a campaign. During play the country choice is locked; **Change country** returns to setup. **Debug mode** is off by default; enable it in Settings to show the resource-account selector, map/turn/city diagnostics, hex coordinates, field report, and status text. The player controls only the selected country. Every other non-neutral country, including allies, is controlled by the AI after the player's turn; it favors empty enemy cities and spreads units across targets. Neutral countries neither act nor take damage, and their territory remains gray. The map fills the window; use the mouse wheel to zoom and drag with the left mouse button to pan. **End turn** is in the lower-right corner. Select one of your country's units, move to a highlighted hex, or mark an opposing unit/city in range and use **Attack target** in Settings. River borders are shown in blue; crossing one uses all remaining movement points, including for infantry. Hex colors identify the country owning each city's manually painted territory, and the territory changes color when the city is captured. Country colors are slightly muted; terrain uses restrained single-color symbols over terrain-tinted territory. Cities use building markers, with names and levels shown when zoomed in. Enemy cities block entry while they have HP; attack them to reduce their HP. Garrisoned units and their city share incoming damage, and a friendly garrison heals in its city each round. Infantry ignores extra land-terrain movement costs, tanks regain an attack after a kill, and artillery attacks suppress counterattacks. A surviving unit counterattacks at 75% of its current attack if the attacker is within its range; skills, statuses, and terrain modify counterattack damage. A kill has a 33% chance to grant +25% attack for three rounds; being flanked reduces attack by 25%, while being surrounded reduces it by 50%. Flanking and surrounded penalties disappear immediately when the formation breaks. Unit attack stays at full strength above 50% HP, then decreases linearly to half strength at 0 HP. When a hex is 40 pixels wide or smaller, the map switches to an overview: terrain detail, river strokes, and hex seams disappear while territory boundaries, cities, and units remain visible. Hex selection and editing are disabled in this view; panning remains available.

In the editor, drag the divider to resize the tools sidebar and map; the sidebar scrolls when its contents exceed the window height. Choose a terrain, city, territory, river, starting unit, or erase tool. Select a city and click or drag over land hexes to paint its territory; choose **Unassigned (clear)** to remove a land hex from its city. In the City tool, click an existing city to edit its name, owner, city level, industry level, or research level, then apply the changes or delete it. To add or remove a river, click its two neighboring land hexes; clicking an existing river edge toggles it off. Hold Shift while dragging to pan. Sea hexes never belong to a city. New cities claim only their own land hex until you paint more territory. Every land hex must be assigned, and every city must own at least one hex before a map can be played. Use the **Countries** tab to add countries, assign each to player, enemy, or neutral faction, and set its independent starting resources. Adjust a country's hue, saturation, and brightness with the HSB sliders; the swatch updates live and its hex color is saved with the map. Neutral territory appears gray; its configured country color remains stored and appears if the country is later reassigned to a faction. In-game joining is not implemented. City HP follows the configured city-level values. Map dimensions can be set from 4 to 200 columns and rows. Zoom out for the overview; large maps can be panned. Save maps as JSON in the `maps` folder to make them available under **Choose map**. Maps can start without units; recruit at cities during the campaign. Older map files are upgraded when opened.

## Campaign Rules

Embarking and landing both require a unit to start its move with full movement points.

Click a non-neutral country's territory and confirm the in-app prompt to start the campaign as that country. Settings no longer contains a Start campaign control; use it to browse maps or restart a running campaign. During your turn, clicking an enemy unit or living enemy city in range attacks it immediately; the Settings target command remains available as an alternate route. Movement highlights exclude occupied hexes and living enemy cities, which also block pathing. Entering water requires a unit to start the move with all movement points available, and water transitions use the full movement allowance. Newly recruited units cannot move or attack until the next turn. Units can only be recruited on unoccupied city hexes. AI recruitment continues until resources or unoccupied owned cities run out, favoring cities near enemy pressure. AI scores enemy units and cities together by value, damage, distance, and nearby support; it moves toward a better position before attacking the best currently attackable target. Capturing a city does not restore its HP. AI turns run without blocking map interaction. Four yellow direction markers indicate a unit that has not acted, thick solid outlines show reachable hexes, and dark red reticles mark attackable enemies. Status icons appear beside units on the map; skill and status icons open an in-app description panel.

## Modules

- `game_config.py`: unit balance, terrain costs, city HP/recovery, and combat constants
- `maps/default_map.json`, `maps/eu.json`, and `maps/EU2.json`: playable campaign maps
- `map_data.py`: version 7 JSON map format, faction/color/river validation, and file operations
- `map_editor.py`: standalone hex-map editor
- `game_model.py`: terrain, cities, units, combat, and turn rules
- `game_ai.py`: AI recruitment, theater priorities, movement, and attacks
- `unit_effects.py`: extensible unit skills and morale statuses
- `hex_map.py`: hex drawing, mouse input, zoom, and panning
- `app.py`: window layout, commands, and status display
- `steel_dominion.py`: application entry point

## Update Log
- Record updates under the latest version; do not use dates unless explicitly requested.

### v0.2
- Added a map resource strip and a selection info overlay; moved unit details and recruitment into modal in-window panels.
- Added EU city industry and research levels, including level 0, with player and enemy production totals balanced.
- Improved map interaction with camera-style panning, city-territory borders, and overview mode at 40 pixels per hex.
- Units now spend all remaining movement after a successful move.
- Expanded the map to fill the game window, moved campaign controls and reports into Settings, and added an End turn button at the lower right.
- Reorganized unit details into a profile-and-status layout and recruitment into a side-by-side unit comparison list.
- Added an opt-in Debug mode for diagnostics, removed duplicate or nonessential UI from normal play, and reduced the main window minimum size to 640 x 420.
- Prioritized AI capture of open enemy cities, added target-spread scoring, and implemented extensible unit skills plus morale statuses.
- Extended skill/status hooks for action gating, target resolution, terrain-aware damage, and incoming damage modifiers; no additional effects were added.
- Added 75% in-range counterattacks and replaced artillery's damage bonus with suppressive fire that prevents counterattacks.

### v0.3
- Added AI recruitment for affordable units and prevented newly recruited units from moving on their recruitment turn.
- Required full movement points to embark or land, and kept enemy units and living enemy cities impassable.
- Added setup-time country confirmation from territory clicks and immediate attacks when clicking an in-range enemy.
- Replaced system skill popups with in-app description panels and presented skills as clickable icons.
- Made action readiness, reachable hexes, attackable targets, and unit statuses more visible on the map.
- Set the initial window size to the 640 x 420 minimum.
- Simplified unit details to show maximum movement only and removed the Field Status panel.
- Replaced recruit radio buttons with whole-row unit selection and aligned each unit's stats in shared columns.
- Limited movement-range outlines to the outer ring of reachable hexes.
- Combined morale effects by level: high morale offsets flanking, while surrounding reduces boosted morale to one level below normal; effects update when statuses expire or formations break.
- Displayed each resource account's per-turn income beside its current stock in the top bar.

### v0.4
- Ran AI turns asynchronously so the interface remains responsive while the AI acts.
- Added a one-step movement undo that is available before the moved unit attacks; attacks, recruitment, and ending the turn commit the movement.
- Let tanks retain movement after a kill when they had not moved before attacking.
- Restricted player and AI recruitment to unoccupied owned city hexes; AI recruits repeatedly until resources or city slots run out, prioritizing besieged and frontline cities.
- Made AI evaluate useful movement before attacking, then attack the best currently reachable target.
- Kept captured city HP unchanged instead of restoring it.
- Prevented newly recruited units from moving or attacking until their next turn.
- Reduced city HP to two-thirds of its previous configured values; map loading now recalculates current and maximum city HP from the configured formula, ignoring saved HP values.
- Adjusted EU city levels for an overall Allied-to-Axis income ratio of about 1.15:1; set starting Tank/Artillery/Infantry counts to 11/8/21 for the Allies and 18/10/18 for the Axis, distributed across national territories rather than concentrated on the Maginot front.
- Added Desert terrain with its own map color and dune symbol, plus a movement cost of 2.
- Rebalanced EU starting forces among active countries and redistributed initial resources from the United Kingdom to the Soviet Union and from Italy to Germany, preserving faction totals.
- Added `maps/EU2.json` with 23 historically named cities in oversized regions; each new city owns only its city hex until its surrounding territory is assigned. Income remains near a 1.15:1 player-to-enemy ratio, with randomized nearby valid city placement.
- Removed white outlines between hexes and drew selected-hex, movement-range, and territory-boundary edges as circular arcs.
- Filled each hex with an overlapping circle so neighboring colors join into smooth regions; kept territory, selection, and movement arcs independent from fill transitions.
- Used exact circular arcs for territory, selection, and movement edges, independently from fill colors.
- Rebalanced EU forces by the eastern, western, and UK-Italy theaters while preserving total units, resource stocks, and income.
- Added slight AI randomness when choosing among equally or nearly equally scored recruitment, target, and movement options.
- Reduced country color saturation and switched map zoom/pan to coalesced Canvas camera transforms without rebuilding the map on each input event.
- Kept territory painting, city ownership colors, unit states, and selection overlays on localized update paths; overview/detail changes switch prebuilt layers after zoom input settles.
- Filled triangular gaps at three-cell corners with three equal-area pieces: majority fill when colors repeat, or one piece per tile fill when all three differ; city, national, selection, and movement boundaries use the same inner-circle arc geometry.

### v0.5
- Cached local AI target factors and unit positions to reduce repeated full-army scans without changing scores or tactical statuses.
- Replaced full-map hex hit scans with constant-size geometric candidate checks.
- Let the editor open maps with malformed territory grids and clear invalid assignments for repair; game loading remains strict.
- Preserved the editor's current zoom when opening maps and showed tool controls only for the active editing mode.
- Reused computed movement paths and added a 0.4-second player movement animation.
- Removed Plain and Water terrain symbols while retaining their terrain fills.
- Added setup-time overview country selection and a country briefing with cities, forces, income and reserves; unit HP appears after country selection.
- Replaced city name labels with compact cards showing HP and all three city/production levels.
- Added city names and simplified unit marks in overview; city detail markers use a level badge, adjacent Roman-numeral production bars and faction-colored health bar with gray damage remainder.
- Used overlapping circular terrain fills, muted country colors, and prebuilt overview/detail Canvas layers with grouped visibility; cached screen geometry and maintained one model-wide unit-position index.
- Removed unused movement-range edge collection and obsolete city HP constants.

### v0.6
- Added an in-app campaign entry, per-map autosaves with restore/overwrite controls, and an exit-to-country-selection action.
- Kept country setup in overview mode and removed the selected-hex information panel from the map view.
- Hid zero-level industry and research blocks, and positioned the remaining production block in the first slot.
- Removed the separate map-selection page; the entry button opens the default map's country setup, where a persistent sidebar switches maps and loads each map's independent save.
- Added an Auto action beneath Settings to run the selected country's AI recruitment, movement, and attacks without advancing the turn.
- Added a main-page map editor entry that opens the existing editor and returns to the main page when closed.
- Added portable one-folder packaging for Python 3.6 with editable external `maps/` and `config.json` data.
- Replaced campaign result popups with an in-app summary of final city counts, final turn, and surviving forces; confirming deletes the completed map save and returns to country selection.
- Added Debug-mode full AI control with automatic map fitting, pause/resume, and exit controls.
- Persisted cumulative player-side and enemy-side win totals for repeated full AI runs on EU2.
- Capped AI reinforcements at a minimum of 3 units or the owned city-level total times the faction-specific `player_ai_units_per_city_level` / `enemy_ai_units_per_city_level` setting; the player-controlled country is exempt.
- Added per-turn maintenance across money, steel, and technology based on configured unit purchase costs and `unit_maintenance_rate`; each resource's total is rounded down after summing and shown beside its income.
- Added Debug-bar live comparisons for both factions' per-turn resource income and total current unit HP.
- Units without an attack for more than two full rounds receive triple movement; moving beyond their base range applies a temporary second-level morale penalty that clears after attacking or returning within base range. Base and extended player movement ranges use yellow and orange outlines.
- Displayed floating, fading damage numbers over units hit by player attacks or counterattacks.
- Added persistent English and Simplified Chinese UI languages, including the campaign, settings, editor, dynamic status, and battle messages.
- Improved AI strategy by weighting city level and production in target and recruitment choices, defending threatened low-health cities first, and discouraging crowded movement destinations.
- Moved AI decisions into `game_ai.py`; units prioritize recapturing cities originally owned by their country, and cities not attacked during the round recover HP at the configured city healing rate.
- Limited AI movement goals to the local front, reduced city-value pull, increased priority for enemy units in friendly territory, and made in-range attacks take precedence over repositioning.
- Balanced AI recruitment placement against local force strength, prioritizing outnumbered or besieged cities without prohibiting recruitment when the faction is globally ahead.
- Added deployed-unit selection and editing, selectable layer erasing, and direct map-edge clipping that reassigns removed-city territory while preserving country data.
- Sorted map editor country, city-territory, unit, terrain, faction, and erase-layer choices alphabetically while preserving their data mappings.

### v0.7
- Changed city assaults so city HP absorbs only the damage it can take; overflow damages the garrison, and attacks against a city with 0 HP deal all damage to its garrison. City and garrison damage numbers appear separately in sequence.
- In normal campaigns, losing every city owned by the selected country now ends the game immediately; Debug mode retains faction-wide victory rules, and AI actions stop as soon as the result is decided.
- Allowed movement routes through allied units without allowing occupied hexes as destinations. Allied cities with HP block entry; entering a 0-HP allied city transfers it to the moving unit's country. AI avoids routes that capture allied cities whenever a safe alternative exists.
- Shows an action-ready marker after movement only when the unit can still attack and has a valid target in range.
- Added a compact Debug-only map overlay comparing faction income and total unit HP.
- Added `movement_animation_duration`, `forced_march_multiplier`, and `forced_march_unattacked_turns` configuration settings.
- Added a per-country war entry turn. Before entry, a country is neutral for AI control and combat, and its income uses the configurable `non_participant_income_multiplier`; its units and cities join their assigned faction when the turn begins. The selected player country is active from the start.
- Added an in-game notification when a country enters the war; the notice waits for confirmation before automated turns continue.
- Added configurable level 1¨C3 unit recruitment, with level-based cost, HP, and attack multipliers while movement remains unchanged. Unit level is saved, and older saves default to level 1.
- Added level badges for units and cities, plus compact production-level markers; one, two, or three unit-level marks indicate the recruited unit's level.
- Updated Auto recruitment to consider resource surplus as well as local force pressure when choosing unit level, and to fall back to an affordable lower level.
- Added war-entry-turn editing for countries in the map editor.