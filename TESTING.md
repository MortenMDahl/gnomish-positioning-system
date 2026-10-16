# Testing GPS in game

A step-by-step check of the 2D map (`GnomishPositioningSystem`) and the 3D test (`GPS3D`) in the WoW Forever client. Nothing has run in the game yet, so expect some steps to fail; the point is to find out which, with enough detail to fix them. Each step says what to do, what you should see, and what to do if you don't.

Both addons have a self-test (`/gps test`, `/gps3d test`) that prints a report in chat. Those lines are the most useful thing to send back.

Before the game, the GPS Sandbox page (`tools/sandbox`) runs the same files in a browser with a simulated player: good for trying the controls and the look, not for the game-only questions (image loading by file ID, the real character model, real frame times).

## 0. Before you start

1. Close the game. Copy `Interface/AddOns/GnomishPositioningSystem` and `prototypes/GPS3D` into `C:\Program Files (x86)\World of Warcraft\_classic_beta_\Interface\AddOns\`. You should end up with `...\AddOns\GnomishPositioningSystem\Core.lua` and `...\AddOns\GPS3D\GPS3D.lua`.
2. Start the game. On the character screen, open **AddOns** and check both are listed and ticked. If they show as out of date, tick **Load out of date AddOns** and note the interface number the client wants (the self-test also prints it).
3. Log in and turn on Lua error messages: `/console scriptErrors 1`.
4. Turn on chat logging so the reports are saved to a file: `/chatlog`. The game writes to `_classic_beta_\Logs\WoWChatLog.txt` (the file fills in when you log out or `/reload`).
5. Open MapExplorer in a browser (https://coldensjo.github.io/ClassicWowMapExplorer/, game version Forever). Its top-right corner shows the zone and **tile x_y** under the camera, which is the reference for the alignment checks.

## 1. Loading

Type `/gps`.

You should see the map window in the "tooltip slim" look (`design/gps-style-2d-3d.png`, option 2): a thin grey tooltip border, the zone name in gold at the top left with the map name under it between `<` and `>`, `2D · 3D ×` at the top right (2D in gold), your subzone and coordinates at the bottom left and `- + Me` at the bottom right. No error pop-up.

If there is a Lua error, copy its first lines (file and line number, and the message). If nothing happens at all, check the AddOns list again.

## 2. 2D self-test

Stand outdoors in the Eastern Kingdoms, ideally in Northshire or Elwynn Forest. Type `/gps test`. It prints these lines, then `done`:

| Line | Expected | If not |
|---|---|---|
| `data:` | 48 maps, 3322 tiles, `.jpg`, and the client's interface number | If the interface number is not 16001, the TOC needs that number. |
| `UnitPosition:` | three numbers and `map 0` | `nil` outdoors means the game hides the position. Send the line. |
| `GPS position:` | `map 0 (Eastern Kingdoms), tile x_y` | Compare `tile x_y` with MapExplorer at the same spot. A different tile is an alignment bug: send both. |
| `C_Map:` | Blizzard's own world position | Information for the axis check. |
| `axis check:` | `PASS` | `SWAPPED`: type `/gps swapaxes` and repeat this step (the check itself keeps saying SWAPPED; the arrow should now be right). `MISMATCH`: send the lines. |
| `layout:` | well under 2 ms per redraw | Above 5 ms: send the line; panning will feel heavy. |
| `live minimap tiles:` | `N of N report loaded` | `0 of N`: the game will not load minimap images for addons, which is the biggest risk. Send the line plus a screenshot. |
| `overview images:` | `N of N report loaded` | `0 of N`: the client does not load JPEG from addons. Fix: run `python scripts/build_maptiles.py <path to gps-export.zip> --tga`, copy the addon again, restart the game. |

## 3. 2D: look at it

1. **Terrain.** The window shows the real top-down world, like the minimap. Plain dark-blue squares where there should be land, or black squares, mean images are missing: screenshot.
2. **Your arrow.** It sits where you stand and points where you face. Turn on the spot: if it turns the opposite way, `/gps flipfacing`. Walk a few steps: it moves the same way you do.
3. **Tile numbers.** `/gps grid` shows each tile's `x_y`. Stand on a tile border you can recognise (a road crossing, a building) and check MapExplorer shows the same tile number for that spot. `/gps grid` again hides them.
4. **Zoom.** Mouse wheel. Zooming in should get sharper until roughly one image pixel per yard, then just bigger. Zooming out swaps to the overview images with no jump or shift. The point under the cursor should stay under the cursor while zooming.
5. **Pan.** Drag with the left button. Following stops when you drag; **Me** centres on you and follows again.
6. **Maps.** `<` and `>` step through the maps (Eastern Kingdoms, Kalimdor, then Forever's own maps and the instances). Kalimdor should fit to the main land, not include a tiny island in a far corner.
7. **Window.** Drag the top band (where the title is) to move it, the bottom-right corner to resize it; `×` or **Escape** closes it. `/reload` and `/gps` again: same size, place and zoom.
9. **Look.** Buttons are plain text: grey, white under the mouse, with a tooltip. The top and bottom edges of the map are darkened so the text stays readable over bright terrain. Note anything that is hard to read or overlaps when the window is small.
8. **Key binding.** Options, Keybindings, AddOns: "Toggle the map" can be bound.

## 4. 2D: edge cases

1. **Inside a dungeon.** The arrow disappears and **Me** says your position is not available. No errors.
2. **Zephras Isle** (or any Forever zone with its own map). `/gps test` there should show that map, not "NOT IN GPS DATA".
3. **On a flight path, in combat, while mounted.** The arrow keeps moving; no errors or "action blocked" messages.
4. **UI scale.** Change the UI scale in the options and check dragging and zooming still track the mouse.

## 5. 3D self-test

The 3D window needs GPS (it uses GPS's look and switches with it). Stand anywhere outdoors in the Eastern Kingdoms or Kalimdor, then type `/gps3d test`. It opens the 3D window and prints:

| Line | Expected | If not |
|---|---|---|
| `world data:` | 16 maps, 2277 tiles; buildings: 15 maps, 858 tiles, 11514 blocks, on | Fewer: some `Data\World_*.lua` or `Data\Detail_*.lua` files were not copied or are missing from `GPS3D.toc`. |
| `you:` | your map and position, height, facing | `no 3D terrain for ...` on a continent: send the line (map ID mismatch). `position not available` outdoors: send the line. |
| `height:` | `game Z` is a number close to `map surface` | `game Z nil`: the game gives no height, the arrow uses the map surface. A Z far from the surface: send the line. |
| `render:` | average and worst ms over 36 camera steps, tiles by cell size; buildings: blocks (fine, coarse, far), how far out, triangles; triangles shown | The main number. Under 16 ms is smooth; 16 to 40 ms is usable; above that, lower `/gps3d buildings 2000` (building triangles) or `/gps3d budget 2000` (ground) and send the lines. Buildings cost 2.5 to 4 times the ground alone in cities: run `/gps3d test` in Stormwind or Orgrimmar with buildings on, then `/gps3d detail off` and `/gps3d test` again, and send both render lines. |
| `scene forward` | the two vectors match | Different numbers mean models will drift against the terrain: send the line. |
| `scene right` | matches ours or its exact negative | Send it. |
| `scene fov` | the fov we set | Information for calibration: send it. |
| `images:` | `N of N different terrain images in view report loaded` | `0 of N`: minimap or overview images do not load here. |
| `marker (both):` | `arrow shown, character model loaded=true; camera follow` | `arrow hidden` while you are outdoors, or `loaded=false` / `not created`: send the line and a screenshot. |

`/gps3d pretend` makes a stand-in walk a circle round Northshire Abbey, for testing the marker and the follow modes without walking yourself (`/gps3d pretend` again stops it).

## 6. 3D: look at it, and try the controls

1. **Switching.** In the 2D map, click `3D`: the 3D window opens in exactly the same place and size, and the 2D window closes. `2D` goes back the same way. The key binding closes whichever is open.
2. **The view.** The land around you in perspective with the minimap images on it, a pale sky above the horizon. Buildings stand up out of the ground around the middle of the view, anywhere in the world (look at Stormwind's Mage Quarter in particular: roofs and spires should line up with the minimap image, not break into shards): Northshire Abbey, Goldshire, Stormwind, Orgrimmar, Thunder Bluff. The nearest ones are sharp, those further out coarser, out to about 1,000 yards in towns (less in big cities, where the building budget runs out sooner); beyond that they are painted on the ground. Walls are plain colours, roofs show the minimap. Note whether walking through a city stutters when new buildings appear (they are made at most 1,500 triangles per frame). Zoom out with the wheel: the view should reach the whole continent, coarser in the distance, without gaps between tiles. Walk or ride across zone and tile borders and onto another continent: the view follows. On a map without terrain (most dungeons, Forever's own maps) the footer says so. Screenshots: one close, one zoomed far out.
3. **You.** A minimap arrow lies flat on the ground under you, foreshortened by the perspective (not a flat sticker facing the screen), pointing where you face; your own character model stands on it. Turn on the spot: arrow and model turn with you. If the model faces sideways or backwards, try `/gps3d modelyaw 0`, `180` or `270` and note which is right. `/gps3d marker arrow`, `model` or `both` chooses what is drawn (remembered). Walk into the abbey: the arrow should stay on your floor (seen through the roof) if the `height:` line showed a game Z.
4. **Camera modes**, switched at the bottom right (`Free · Follow · Behind`, the active one in gold; the window opens in Follow or Behind, whichever you used last, or in Free when you are not on the tile):
   - **Follow**: you stay in the middle while you walk. Right-drag turns around you and tilts; the wheel zooms in and out around you.
   - **Behind**: the view turns with you and looks the way you face; your arrow always points up the screen. Right-drag looks to the side (the view keeps that angle as you turn); clicking `Behind` again puts it straight behind you.
   - **Free**: left-drag grabs the ground and moves it (the spot you grabbed stays under the mouse); the wheel zooms toward the mouse; double-click flies to that spot. Left-dragging in Follow or Behind switches to Free; `Follow` or `Behind` flies back to you.
   - **Compass** (`N` on the ring below the close button): shows where north is; click to turn north up (from Behind this switches to Follow).
   - **Tilt**: the window opens looking straight down (the default, **90°** under the compass in gold). Click **90°** to tilt freely: right-drag up and down then stops at 30 degrees above the ground and at straight down. **90°** again flies to straight down and locks it: right-drag then only turns; the button is gold while locked, stays as you left it (locked or free) after closing and reopening the window, and clicking it while locked returns to the tilt you had. Check that the arrow and your character still sit right in the straight-down view.
   - **Height**: in Free, drag the view from a valley over a mountain (Dun Morogh or the Redridge peaks): the camera should keep its height, so the mountain grows toward you instead of the view staying the same size (`testing/height_before_after.png` shows the sandbox). Over a peak taller than the camera, the view stops just above the ground and drops back once you have passed. Zoom all the way in over a peak and onto a roof (Stormwind Cathedral): the zoom stops above it, never inside. Tilted, zoom toward a slope: same. Then tilt (90° off, right-drag to about 30 degrees), zoom in to 100-300 yards and drag the view toward a mountain: the camera should rise over it as it comes into view, never show sky through the ground or the mountain from underneath (`testing/tilt_fixed.png`, bottom row, shows the sandbox). Zoom right in low over a steep slope: the ground just in front of the camera should stay filled, no sky patches at the bottom of the view.
   - Note anything that feels wrong: too fast or slow turning, jumps, the view tilting the wrong way, the wheel zooming the wrong way.
5. **Look for:** triangles flickering or showing through each other (draw order), holes in the ground (culling), walls in the wrong colour, the image upside down or mirrored compared with the 2D map. While the view moves slowly, the ground should not look as if it lags or swims behind the edges of tiles (it skips updates under a quarter pixel; if it does, note it: setting `VO_EPS = 0` near the top of `GPS3D.lua` turns that off).
6. **Other models.** `/gps3d trees` scatters trees, `/gps3d model 106965` places the Elwynn farmhouse (the chat line after 1.5 s says `loaded=true` or `false`), `/gps3d clear` removes them. Turn and zoom: models and your character should stay glued to the terrain and the arrow. If they slide as you zoom, try `/gps3d fov 0.7` and `/gps3d fov 1.0` and note which is better; `/gps3d fov` returns to automatic.

## 7. What to send back

1. `_classic_beta_\Logs\WoWChatLog.txt` (after a `/reload` or logout), or copy the `GPS test` and `GPS3D test` lines by hand.
2. Screenshots from `_classic_beta_\Screenshots` (Print Screen in game): the 2D map zoomed in near you, zoomed out, and the 3D view in Follow, in Behind, and zoomed in on your character.
3. Any Lua error text.
4. Short notes per step: worked, or what you saw instead.

The easiest hand-over is to copy these into a `testing/` folder in this repository.

## Known risks and what fixes them

| Symptom | Likely cause | Fix |
|---|---|---|
| Live tiles `0 of N` loaded, map shows only blurry overview | The client refuses minimap images for addons, or uses other IDs | Check one ID in MapExplorer; if blocked, fall back to bundled tiles at lower resolution (bigger addon) |
| Overview `0 of N` loaded | No JPEG support for addons | Rebuild with `--tga` |
| Arrow on the wrong tile, `axis check: SWAPPED` | UnitPosition order | `/gps swapaxes` (then we fix it in code) |
| Arrow mirrored when turning | Facing direction | `/gps flipfacing` |
| Addon listed as out of date | Interface number changed at launch | Update `## Interface:` in both TOC files |
| 3D render well above 40 ms | Too many triangles per frame | Use the 2-yard mesh nearby, cull off-screen triangles, update less often |
| Models slide against the 3D terrain, or your model stands off the arrow | ModelScene field of view convention | Calibrate with `/gps3d fov`, then fix in code |
| Your model faces the wrong way | Model yaw convention | `/gps3d modelyaw <degrees>` (then fix the default in code) |
| No character model (`not created` or `loaded=false`) | ModelScene actor or `SetModelByUnit` restricted | `/gps3d marker arrow` meanwhile; send the self-test line |
| Arrow on a roof while you are indoors | No usable Z from `UnitPosition` | Expected with a one-surface map; send the `height:` line |
| `3D` button says it needs GPS3D | `GPS3D` folder not copied, or out of date | Copy `prototypes/GPS3D` again; tick it in the AddOns list |
| Triangles flicker or poke through | Draw-order buckets too coarse | More bucket frames, or sort per building |
