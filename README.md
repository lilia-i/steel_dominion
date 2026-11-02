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

Use the mouse wheel to zoom the map and drag with the left mouse button to pan. Select an Allied unit, move to a highlighted hex, or target an enemy unit/city in range and use **Attack target**. River borders are shown in blue; crossing one uses all remaining movement points, including for infantry. Hex colors identify the country owning each city's manually painted territory, and the territory changes color when the city is captured. Terrain uses distinct bitmap icons. Enemy cities block entry while they have HP; attack them to reduce their HP. Garrisoned units and their city share incoming damage, and a friendly garrison heals in its city each round. Unit attack stays at full strength above 50% HP, then decreases linearly to half strength at 0 HP.

In the editor, choose a terrain, city, territory, starting unit, or erase tool. Select a city and click or drag over land hexes to paint its territory; hold Shift while dragging to pan. Sea hexes never belong to a city. New cities claim only their own land hex until you paint more territory. Every land hex must be assigned, and every city must own at least one hex before a map can be played. Use the **Countries** tab to add countries, assign each to one of the two factions, and set its independent starting resources. Set a city's level to determine its 15¨C30 HP, and place the initial unit types and countries on the map. Map dimensions can be set from 4 to 200 columns and rows. The minimum zoom keeps each hex large enough to select and inspect; large maps show a partial view and can be panned. Save maps as JSON, then use **Load map** in the game. Older map files are upgraded when opened.

## Modules

- `game_config.py`: unit balance, terrain costs, river edges, city HP/recovery, and default scenario
- `map_data.py`: versioned JSON map format, validation, and file operations
- `map_editor.py`: standalone hex-map editor
- `game_model.py`: terrain, cities, units, combat, and turn rules
- `hex_map.py`: hex drawing, mouse input, zoom, and panning
- `app.py`: window layout, commands, and status display
- `steel_dominion.py`: application entry point