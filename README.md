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

Choose **Play as country** before starting a campaign. During play the choice is locked; **Restart campaign** returns to setup, where you can choose again. The player controls only the selected country. Every other non-neutral country, including allies, is controlled by the AI after the player's turn. The separate resource account selector switches which same-faction country's balances are displayed, but does not grant control. Neutral countries neither act nor take damage, and their territory remains gray. Drag the divider between the map and sidebar to resize either pane; the sidebar scrollbar appears when its contents do not fit. Use the mouse wheel to zoom the map and drag with the left mouse button to pan. Select one of your country's units, move to a highlighted hex, or target an opposing unit/city in range and use **Attack target**. River borders are shown in blue; crossing one uses all remaining movement points, including for infantry. Hex colors identify the country owning each city's manually painted territory, and the territory changes color when the city is captured. Countries retain distinct colors even with large country counts. Terrain uses distinct bitmap icons. Enemy cities block entry while they have HP; attack them to reduce their HP. Garrisoned units and their city share incoming damage, and a friendly garrison heals in its city each round. Unit attack stays at full strength above 50% HP, then decreases linearly to half strength at 0 HP. When a hex is 20 pixels wide or smaller, the map switches to an overview: terrain detail, river strokes, and hex seams disappear while territory boundaries, cities, and units remain visible. Hex selection and editing are disabled in this view; panning remains available.

In the editor, drag the divider to resize the tools sidebar and map; the sidebar scrolls when its contents exceed the window height. Choose a terrain, city, territory, river, starting unit, or erase tool. Select a city and click or drag over land hexes to paint its territory; choose **Unassigned (clear)** to remove a land hex from its city. In the City tool, click an existing city to edit its name, owner, city level, industry level, or research level, then apply the changes or delete it. To add or remove a river, click its two neighboring land hexes; clicking an existing river edge toggles it off. Hold Shift while dragging to pan. Sea hexes never belong to a city. New cities claim only their own land hex until you paint more territory. Every land hex must be assigned, and every city must own at least one hex before a map can be played. Use the **Countries** tab to add countries, assign each to player, enemy, or neutral faction, and set its independent starting resources. Adjust a country's hue, saturation, and brightness with the HSB sliders; the swatch updates live and its hex color is saved with the map. Neutral territory appears gray; its configured country color remains stored and appears if the country is later reassigned to a faction. In-game joining is not implemented. City HP follows the configured city-level values. Map dimensions can be set from 4 to 200 columns and rows. Zoom out for the overview; large maps can be panned. Save maps as JSON, then use **Load map** in the game. Older map files are upgraded when opened.

## Modules

- `game_config.py`: unit balance, terrain costs, city HP/recovery, and combat constants
- `default_map.json`: initial campaign terrain, countries, cities, units, rivers, and territories
- `map_data.py`: version 7 JSON map format, faction/color/river validation, and file operations
- `map_editor.py`: standalone hex-map editor
- `game_model.py`: terrain, cities, units, combat, and turn rules
- `hex_map.py`: hex drawing, mouse input, zoom, and panning
- `app.py`: window layout, commands, and status display
- `steel_dominion.py`: application entry point