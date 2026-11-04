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

Use **Settings** to browse playable JSON maps, choose a country before starting, and start or restart a campaign. During play the country choice is locked; **Change country** returns to setup. **Debug mode** is off by default; enable it in Settings to show the resource-account selector, map/turn/city diagnostics, hex coordinates, field report, and status text. The player controls only the selected country. Every other non-neutral country, including allies, is controlled by the AI after the player's turn; it favors empty enemy cities and spreads units across targets. Neutral countries neither act nor take damage, and their territory remains gray. The map fills the window; use the mouse wheel to zoom and drag with the left mouse button to pan. **End turn** is in the lower-right corner. Select one of your country's units, move to a highlighted hex, or mark an opposing unit/city in range and use **Attack target** in Settings. River borders are shown in blue; crossing one uses all remaining movement points, including for infantry. Hex colors identify the country owning each city's manually painted territory, and the territory changes color when the city is captured. Country colors are slightly muted; terrain uses restrained single-color symbols over terrain-tinted territory. Cities use building markers, with names and levels shown when zoomed in. Enemy cities block entry while they have HP; attack them to reduce their HP. Garrisoned units and their city share incoming damage, and a friendly garrison heals in its city each round. Infantry ignores extra land-terrain movement costs, tanks regain an attack after a kill, and artillery attacks suppress counterattacks. A surviving unit counterattacks at 75% of its current attack if the attacker is within its range; skills, statuses, and terrain modify counterattack damage. A kill has a 33% chance to grant +25% attack for three rounds; being flanked reduces attack by 25%, while being surrounded reduces it by 50%. Flanking and surrounded penalties disappear immediately when the formation breaks. Unit attack stays at full strength above 50% HP, then decreases linearly to half strength at 0 HP. When a hex is 40 pixels wide or smaller, the map switches to an overview: terrain detail, river strokes, and hex seams disappear while territory boundaries, cities, and units remain visible. Hex selection and editing are disabled in this view; panning remains available.

In the editor, drag the divider to resize the tools sidebar and map; the sidebar scrolls when its contents exceed the window height. Choose a terrain, city, territory, river, starting unit, or erase tool. Select a city and click or drag over land hexes to paint its territory; choose **Unassigned (clear)** to remove a land hex from its city. In the City tool, click an existing city to edit its name, owner, city level, industry level, or research level, then apply the changes or delete it. To add or remove a river, click its two neighboring land hexes; clicking an existing river edge toggles it off. Hold Shift while dragging to pan. Sea hexes never belong to a city. New cities claim only their own land hex until you paint more territory. Every land hex must be assigned, and every city must own at least one hex before a map can be played. Use the **Countries** tab to add countries, assign each to player, enemy, or neutral faction, and set its independent starting resources. Adjust a country's hue, saturation, and brightness with the HSB sliders; the swatch updates live and its hex color is saved with the map. Neutral territory appears gray; its configured country color remains stored and appears if the country is later reassigned to a faction. In-game joining is not implemented. City HP follows the configured city-level values. Map dimensions can be set from 4 to 200 columns and rows. Zoom out for the overview; large maps can be panned. Save maps as JSON in the `maps` folder to make them available under **Choose map**. Maps can start without units; recruit at cities during the campaign. Older map files are upgraded when opened.

## Campaign Rules

Embarking and landing both require a unit to start its move with full movement points.

Click a non-neutral country's territory and confirm the in-app prompt to start the campaign as that country. Settings no longer contains a Start campaign control; use it to browse maps or restart a running campaign. During your turn, clicking an enemy unit or living enemy city in range attacks it immediately; the Settings target command remains available as an alternate route. Movement highlights exclude occupied hexes and living enemy cities, which also block pathing. Entering water requires a unit to start the move with all movement points available, and water transitions use the full movement allowance. Newly recruited units cannot move during their recruitment turn. The AI recruits affordable units and uses its forces to pursue enemy cities and targets. Four yellow direction markers indicate a unit that has not acted, thick solid outlines show reachable hexes, and dark red reticles mark attackable enemies. Status icons appear beside units on the map; skill and status icons open an in-app description panel.

## Modules

- `game_config.py`: unit balance, terrain costs, city HP/recovery, and combat constants
- `maps/default_map.json` and `maps/eu.json`: playable campaign maps
- `map_data.py`: version 7 JSON map format, faction/color/river validation, and file operations
- `map_editor.py`: standalone hex-map editor
- `game_model.py`: terrain, cities, units, combat, and turn rules
- `unit_effects.py`: extensible unit skills and morale statuses
- `hex_map.py`: hex drawing, mouse input, zoom, and panning
- `app.py`: window layout, commands, and status display
- `steel_dominion.py`: application entry point

## Update Log

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