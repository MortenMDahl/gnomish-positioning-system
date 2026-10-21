# Testing GPS in game

A step-by-step check of the 2D map and the traditional map (`GnomishPositioningSystem`) and the 3D test (`GPS3D`) in the WoW Forever client. Nothing has run in the game yet, so expect some steps to fail; the point is to find out which, with enough detail to fix them. Each step says what to do, what you should see, and what to do if you don't.

Both addons have a self-test (`/gps test`, `/gps3d test`) that prints a report in chat. Those lines are the most useful thing to send back.

What this test decides (send these even if everything else works):

- **3D quest areas.** Built since 2026-10-21 (GPS3D's `QuestAreas.lua`): the area's shape comes from the quest-area frame's hit-test, tried with the frame hidden, at alpha 0, then behind the 3D view's ground. The `quest areas:` line of `/gps3d test` (section 9 step 4) says which way works, or why none does (then the 3D view keeps quest markers only, with no error).
- **2D quest areas.** Kept only if `quests: 2.` says `made` and section 9 step 3 shows the area lined up and cut off at the window edge.
- **The game's own buildings in the 3D view.** Possible only if the `models: building (WMO) probe` line (section 6) says `loaded=true` with a box, and section 10 step 1's chat line agrees; otherwise buildings stay as GPS's simplified shapes and only props and trees are the game's models.
- **Other addons' markers**: section 11 step 1's `/gps test` lines say which addons' map layers work in GPS's traditional map.
- **How many of the game's models the 3D view can afford**: the `PERF` lines of section 10 step 4.
- **Minimap images by file ID, JPEG overviews, model field of view and yaw, taint from Blizzard's map code**: sections 2, 6 and 7.

Before the game, the GPS Sandbox page (`tools/sandbox`) runs the same files in a browser with a simulated player: good for trying the controls and the look, not for the game-only questions (image loading by file ID, the real character model, real frame times).

## 0. Before you start

1. Close the game. Copy `Interface/AddOns/GnomishPositioningSystem` and `prototypes/GPS3D` into `C:\Program Files (x86)\World of Warcraft\_classic_beta_\Interface\AddOns\`. You should end up with `...\AddOns\GnomishPositioningSystem\Core.lua` and `...\AddOns\GPS3D\GPS3D.lua`.
2. Start the game. On the character screen, open **AddOns** and check both are listed and ticked. If they show as out of date, tick **Load out of date AddOns** and note the interface number the client wants (the self-test also prints it).
3. Log in and turn on Lua error messages: `/console scriptErrors 1`.
4. Turn on chat logging so the reports are saved to a file: `/chatlog`. The game writes to `_classic_beta_\Logs\WoWChatLog.txt` (the file fills in when you log out or `/reload`).
5. Open MapExplorer in a browser (https://coldensjo.github.io/ClassicWowMapExplorer/, game version Forever). Its top-right corner shows the zone and **tile x_y** under the camera, which is the reference for the alignment checks.

## 1. Loading

Type `/gps`.

You should see the map window in the "minimap rings" look (option B of the look study): no frame, just a thin black edge; the zone name in gold at the top left with the map name under it between `<` and `>`; the game's red close button at the top right; under it, down the right edge, three round buttons in the minimap's gold ring (a compass, its needle pointing up since this map is always north-up; the mode ring, showing `2D`; and Me with the player arrow, gold while the map follows you); two smaller rings with `+` and `-` (zoom) at the bottom right; your subzone and coordinates at the bottom left. Hover a ring: a tooltip says what it does. No error pop-up, and no green-and-black checkered squares (a texture or atlas that did not load: note which button).

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
| `modes:` | `2D, 3D, Map; opening here picks 2D map` (outdoors; the mode you chose last) | `3D` missing: the GPS3D folder is not loaded. `Map` missing: Blizzard's map canvas is not there; see the next line. |
| `world map:` | `the game's layout; side by side on the 2D map: Eastern Kingdoms (scale 1.00..), Kalimdor (scale 0.99..)` | `the classic layout (...)`: the game gives no world-map numbers, so GPS places the continents by the classic world map's (the reason in brackets); both still show side by side. Send the line either way. |
| `traditional map:` | `your map <id> (<zone>), 1 art layer(s) or more, 21 data providers, controls at level 9501 above pins (up to about 2200)` | `NOT available`, or a Lua error naming `Blizzard_MapCanvas` or `MapWindow.lua`: send the line and the error. Fewer than 21 providers: some of Blizzard's map pins are missing in this client (send the line; the map still works). |
| `layout:` | well under 2 ms per redraw | Above 5 ms: send the line; panning will feel heavy. |
| `live minimap tiles:` | `N of N report loaded` | `0 of N`: the game will not load minimap images for addons, which is the biggest risk. Send the line plus a screenshot. |
| `overview images:` | `N of N report loaded` | `0 of N`: the client does not load JPEG from addons. Fix: run `python scripts/build_maptiles.py <path to gps-export.zip> --tga`, copy the addon again, restart the game. |
| `look:` | `close, ring, disc and arrow art loaded` | `NOT loaded: ...`: that piece of the game's art (an atlas or file the look borrows) is not there in this client; send the line and a screenshot of the window. |

## 3. 2D: look at it

1. **Terrain.** The window shows the real top-down world, like the minimap. Plain dark-blue squares where there should be land, or black squares, mean images are missing: screenshot.
2. **Your arrow.** It sits where you stand and points where you face. Turn on the spot: if it turns the opposite way, `/gps flipfacing`. Walk a few steps: it moves the same way you do.
3. **Tile numbers.** `/gps grid` shows each tile's `x_y`. Stand on a tile border you can recognise (a road crossing, a building) and check MapExplorer shows the same tile number for that spot. `/gps grid` again hides them.
4. **Zoom.** Mouse wheel. Zooming in should get sharper until roughly one image pixel per yard, then just bigger. Zooming out swaps to the overview images with no jump or shift. Zoom far out over a coast (the Eastern Kingdoms' west side): the sea should keep the same dark colour past the map's last tiles, with no lighter band or edge. The point under the cursor should stay under the cursor while zooming.
5. **Pan.** Drag with the left button. Following stops when you drag; **Me** centres on you and follows again. While following, run: the map should move with you smoothly, every frame, not in small jumps. Take a boat, zeppelin or portal to the other continent with the map open and following: it switches to that continent with you.
6. **Title.** Pan from your zone into the next one: the title at the top left changes to the zone in the middle of the view (the sea between zones shows the continent's name), while the bottom left keeps saying where you are. The same in the 3D view when you drag it elsewhere.
7. **Both continents.** Zoom out (the wheel) until the window shows more than the Eastern Kingdoms: Kalimdor appears to the west across the sea, where Blizzard's world map has it, in the same dark sea with no lighter lines along the edges of the images. Drag over to Kalimdor: once the middle of the view is nearer Kalimdor, the subtitle says Kalimdor (nothing moves when it does) and the title shows Kalimdor's zones; zoomed in there, Kalimdor's own minimap images. Not following you, your arrow stays where you are on the Eastern Kingdoms. Screenshot zoomed out with both in view.
8. **Maps.** `<` and `>` step through the maps (Eastern Kingdoms, Kalimdor, then Forever's own maps and the instances). Kalimdor should fit to the main land, not include a tiny island in a far corner. `/reload` after browsing to Kalimdor: it should still show Kalimdor. In the 3D view the same `<` and `>` show the next map with terrain whole from above; the Me ring brings you back.
9. **Window.** Drag the top band (where the title is) to move it, the bottom-right corner to resize it; `×` or **Escape** closes it. `/reload` and `/gps` again: same size, place and zoom. The same in the 3D view and the traditional map: a window you moved opens there again, whichever mode you close it in.
10. **Look.** Buttons are plain text: grey, white under the mouse, with a tooltip. The top and bottom edges of the map are darkened so the text stays readable over bright terrain. Note anything that is hard to read or overlaps when the window is small.
11. **Key binding.** Options, Keybindings, AddOns: "Toggle the map" can be bound.

## 4. 2D: edge cases

1. **Inside a dungeon.** With the 2D map open (following you) as you enter, it switches to the traditional map (section 5) after the loading screen; closed, `/gps` or the key opens the traditional map there. Leaving the dungeon switches back to the mode you chose. In the 2D map itself (pick it with the mode ring), the arrow disappears and **Me** says your position is not available. No errors.
2. **Zephras Isle** (or any Forever zone with its own map). `/gps test` there should show that map, not "NOT IN GPS DATA".
3. **On a flight path, in combat, while mounted.** The arrow keeps moving; no errors or "action blocked" messages.
4. **UI scale.** Change the UI scale in the options and check dragging and zooming still track the mouse.

## 5. The traditional map

Blizzard's own map art (zones, continents, dungeon floors) with Blizzard's pins and your arrow, in the GPS window. Open it with the mode ring (from the 2D map: right-click; from the 3D view: click) or `/gps map`; `/gps 2d` and `/gps 3d` go back. Whichever mode you pick is the one `/gps` and the key open next time, except where GPS cannot show you (dungeons, raids, battlegrounds without GPS data), where the traditional map opens.

1. **Look.** The same window: thin black edge, the map's name in gold at the top left with the map it belongs to under it, the red close button, the compass, the mode ring (a folded map) and Me down the right edge (at exactly the same places as in the 2D map and the 3D view: switching with the mode ring leaves the mouse on it), the zoom rings at the bottom right, where you are at the bottom left. Inside it, Blizzard's painted map, not the minimap images. Hover the mode ring: `Traditional map`, `Click: 2D map of the same place`, `Right-click: 3D view`.
2. **Pins and your arrow.** Your arrow (Blizzard's, the same as on the world map) sits where you stand and turns with you; party members show as dots. Flight points, dungeon entrances and points of interest show as on Blizzard's map. None of them may draw over the rings, the close button or the title (the controls sit at frame level 9501, the pins below about 2200): screenshot if one does.
3. **Moving around the map** (Blizzard's mouse controls): hover a zone on a continent map: it lights up and its name shows under the title band; click it to open it; right-click goes to the map above (zone, continent, Azeroth); the wheel zooms, and once zoomed in, left-drag pans. The zoom rings zoom too. **Me** returns to the map you are on (gold while it shows it); the map follows you into the next zone while it shows yours.
4. **Dungeons.** Enter one with floors (The Deadmines, Blackrock Depths): the title is the dungeon, the subtitle the floor with `<` `>` and `(1 of 2)`; `<` `>` change floor; your arrow is on your floor; walking to another floor follows you there.
5. **Switching.** From the traditional map, click the mode ring: the 2D map opens in the same place and size, looking where the traditional map looked (or following you, when it showed your map). From the 2D map looking elsewhere, right-click the mode ring: the traditional map opens on that zone.
6. **Window.** Drag the top band to move it and the corner to resize it (the map refits); `×` or Escape closes it; `/gps` again opens it at that place and size.
7. **No side effects.** After using it (also in combat), open Blizzard's own world map (the default `M` key, if GPS's binding is on another key) and use a quest item or an action bar: no "Interface action failed because of an AddOn" messages and no Lua errors. GPS builds its own map from Blizzard's map code and does not touch Blizzard's world map window, but this is the place where taint would show.

## 6. 3D self-test

The 3D window needs GPS (it uses GPS's look and switches with it). Stand anywhere outdoors in the Eastern Kingdoms or Kalimdor, then type `/gps3d test`. It opens the 3D window in place of whichever GPS window is open (like the mode ring; `/gps3d` alone opens and closes it the same way, never next to another GPS window) and prints:

| Line | Expected | If not |
|---|---|---|
| `world data:` | 16 maps, 2277 tiles; buildings: 15 maps, 859 tiles, 9645 blocks, on | Fewer: some `Data\World_*.lua` or `Data\Detail_*.lua` files were not copied or are missing from `GPS3D.toc`. |
| `you:` | your map and position, height, facing | `no 3D terrain for ...` on a continent: send the line (map ID mismatch). `position not available` outdoors: send the line. |
| `height:` | `game Z` is a number close to `map surface` | `game Z nil`: the game gives no height, the arrow uses the map surface. A Z far from the surface: send the line. |
| `render:` | average and worst ms over 36 camera steps, tiles by cell size; buildings: blocks (fine, coarse, far), how far out, triangles; triangles shown | The main number. Under 16 ms is smooth; 16 to 40 ms is usable; above that, lower `/gps3d buildings 2000` (building triangles) or `/gps3d budget 2000` (ground) and send the lines. Buildings cost 2.5 to 4 times the ground alone in cities: run `/gps3d test` in Stormwind or Orgrimmar with buildings on, then `/gps3d detail off` and `/gps3d test` again, and send both render lines. |
| `scene forward` | the two vectors match | Different numbers mean models will drift against the terrain: send the line. |
| `scene right` | matches ours or its exact negative | Send it. |
| `scene fov` | the fov we set | Information for calibration: send it. |
| `images:` | `N of N different terrain images in view report loaded` | `0 of N`: minimap or overview images do not load here. |
| `icons:` | `3 of 3` | Fewer: the addon's own TGA icons in `GnomishPositioningSystem\Media\` did not load (check the folder was copied); send the line. |
| `marker (both):` | `arrow shown, character model loaded=true; camera follow` | `arrow hidden` while you are outdoors, or `loaded=false` / `not created`: send the line and a screenshot. |
| `models data:` | 16 maps, 1132 tiles, 415011 placements of 9441 models (196 of them caves and mines) | Fewer: some `Data\Models_*.lua` files were not copied or are missing from `GPS3D.toc`. |
| `models: buildings ...; props and trees on ...; N shown (B buildings), L loading, F failed, A actors` | N above 0 outdoors; F 0 | F above 0: some of the game's models do not load in an addon's view; send the line. |
| `models: building (WMO) probe fileID ...: set=... loaded=... box ...` | **The answer to whether real buildings are possible.** `set=true loaded=true box` with three sizes in yards: the game draws its buildings for addons | `loaded=false` or `box none`: the game does not; buildings stay as GPS's simplified shapes (section 10). Send the line either way. |
| `models: prop (M2) probe fileID ...: set=true loaded=true box ...` | loaded, with a box | `loaded=false`: models do not load at all here; send the line. |

`/gps3d pretend` makes a stand-in walk a circle round Northshire Abbey, for testing the marker and the follow modes without walking yourself (`/gps3d pretend` again stops it).

## 7. 3D: look at it, and try the controls

1. **Switching.** In the 2D map, click the mode ring (`2D`): the 3D window opens in exactly the same place and size, and the 2D window closes. Its rings, top to bottom: compass, the mode ring (`3D`) and Me, at exactly the same places as in the 2D map (the mouse stays on the mode ring), then the camera mode and straight down / tilted (a little grid of ground that turns and tilts with the view). The mode ring steps 2D map, 3D view, traditional map and round again; a right-click steps back (so from the 3D view, right-click returns to the 2D map). The key binding closes whichever is open.
2. **The view.** The land around you in perspective with the minimap images on it. Beyond the map's last tiles the background is the same dark sea as the open sea in the minimap images, so zooming far out over a coast shows no edge where the tiles end (the same in the 2D map). Buildings stand up out of the ground around the middle of the view, anywhere in the world (look at Stormwind's Mage Quarter in particular: roofs and spires should line up with the minimap image, not break into shards): Northshire Abbey, Goldshire, Stormwind, Orgrimmar, Thunder Bluff. Caves and mines show only what the game draws outside: at the cave just east of Northshire Valley the rock around the entrance stands at the foot of the cliff (the game draws it over a hole in the terrain), and no tunnel raises the ground behind it; compare with the game from above. The nearest ones are sharp, those further out coarser, out to about 1,000 yards in towns (less in big cities, where the building budget runs out sooner); beyond that they are painted on the ground. Walls are plain colours, roofs show the minimap. Note whether walking through a city stutters when new buildings appear (they are made at most 1,500 triangles per frame). Zoom out with the wheel: the view should reach the whole continent, coarser in the distance, without gaps between tiles. Walk or ride across zone and tile borders and onto another continent: the view follows. On a map without terrain (most dungeons, Forever's own maps) the footer says so. Screenshots: one close, one zoomed far out.
3. **You.** A minimap arrow lies flat on the ground under you, foreshortened by the perspective (not a flat sticker facing the screen), pointing where you face; your own character model stands on it. Turn on the spot: arrow and model turn with you. If the model faces sideways or backwards, try `/gps3d modelyaw 0`, `180` or `270` and note which is right. `/gps3d marker arrow`, `model` or `both` chooses what is drawn (remembered). Walk into the abbey: the arrow should stay on your floor (seen through the roof) if the `height:` line showed a game Z.
4. **Camera modes**, stepped by the camera-mode ring: Follow, then Behind, then Free, then Follow again; its icon shows the mode (Follow: a dot with an arrow circling it; Behind: your arrow with the view's cone behind it; Free: four arrows). The footer ends with the mode (`Following`, `Behind you`, `Free camera`), the camera-mode ring and Me are gold while the view is locked onto you, and its tooltip lists the mouse controls for the mode. The window opens in Follow or Behind, whichever you used last, or in Free when you are not on the tile:
   - **Follow**: you stay in the middle while you walk. Right-drag turns around you and tilts; the wheel zooms in and out around you.
   - **Behind**: the view turns with you and looks the way you face; your arrow always points up the screen. Right-drag looks to the side (the view keeps that angle as you turn); clicking Me puts it straight behind you again.
   - **Free**: left-drag grabs the ground and moves it (the spot you grabbed stays under the mouse); the wheel zooms toward the mouse; double-click flies to that spot. Left-dragging in Follow or Behind switches to Free; Me flies back to you (in Follow or Behind, whichever you used last).
   - **Compass** (the top ring, a red and grey needle): the red half points north; click to turn north up (from Behind this switches to Follow).
   - **Tilt**: the window opens looking straight down (the default: the bottom ring shows a square grid, in gold, turning with the view like the compass needle). Click it to tilt freely (it turns brass, and its grid leans back in perspective as you tilt): right-drag up and down then stops at 45 degrees (halfway between level and straight down) and at straight down. Clicking it again flies to straight down and locks it: right-drag then only turns; the ring is gold with a square grid while locked, stays as you left it (locked or free) after closing and reopening the window, and clicking it while locked returns to the tilt you had. Check that the arrow and your character still sit right in the straight-down view.
   - **Height**: in Free, drag the view from a valley over a mountain (Dun Morogh or the Redridge peaks): the camera should keep its height, so the mountain grows toward you instead of the view staying the same size (`testing/height_before_after.png` shows the sandbox). Over a peak taller than the camera, the view stops just above the ground and drops back once you have passed. Zoom all the way in over a peak and onto a roof (Stormwind Cathedral): the zoom stops above it, never inside. Tilted, zoom toward a slope: same. Then tilt (straight-down ring off, right-drag as far as it goes, 45 degrees), zoom in to 100-300 yards and drag the view toward a mountain: the camera should rise over it as it comes into view, never show sky through the ground or the mountain from underneath (`testing/tilt_fixed.png`, bottom row, shows the sandbox). Zoom right in low over a steep slope: the ground just in front of the camera should stay filled, no sky patches at the bottom of the view.
   - Note anything that feels wrong: too fast or slow turning, jumps, the view tilting the wrong way, the wheel zooming the wrong way.
5. **Look for:** triangles flickering or showing through each other (draw order), holes in the ground (culling), walls in the wrong colour, the image upside down or mirrored compared with the 2D map. While the view moves slowly, the ground should not look as if it lags or swims behind the edges of tiles (it skips updates under a quarter pixel; if it does, note it: setting `VO_EPS = 0` near the top of `GPS3D.lua` turns that off).
6. **Other models.** `/gps3d trees` scatters trees, `/gps3d model <fileID>` places any model at the middle of the view (the chat line after 1.5 s says `loaded=true` or `false`; 7962574 is Forever's Stormwind City (one building model for the whole city, its lamps, trees and benches included), 106965 the Elwynn farmhouse), `/gps3d clear` removes them. Turn and zoom: models and your character should stay glued to the terrain and the arrow. If they slide as you zoom, try `/gps3d fov 0.7` and `/gps3d fov 1.0` and note which is better; `/gps3d fov` returns to automatic.

## 8. Settings

GPS has a page in the game's options: **Options**, **AddOns**, **Gnomish Positioning System** (or `/gps options`, which opens it there). The changes apply at once and are kept after `/reload`; the options' **Defaults** button sets the page back to a fresh install.

1. **The page.** The sections: *Map window* (Opens as, Traditional map where GPS can't show you, Map key opens (section 13), Window: Reset), *Quests* (Your quests on the 2D map and in the 3D view), *Other addons* (Other addons' map markers, section 11), *3D view* (You are shown as, Camera on you, Look straight down, Buildings, Building detail, Buildings close up, Props and trees, Props and trees at most, Model distance, Smallest model, Ground detail, Turn your character; only with GPS3D loaded) and *Position fixes* (Swap the map's axes, Turn the arrow the other way). Each shows a tooltip under the mouse. Missing page or a Lua error when opening the options: send the error.
2. **Opens as.** Pick *3D view*, close the options, press the map key: the 3D view opens. The mode ring changes this setting too (reopen the options to see it).
3. **Traditional map where GPS can't show you.** Off, then enter a dungeon with the 2D map open: it stays the 2D map (the arrow is gone, Me says your position is not available). On again: the next dungeon switches to the traditional map as in section 4.
4. **Window: Reset.** Move and resize the map, then click Reset: it is back in the middle at its first size (also when the 3D view or the traditional map is the one open).
5. **3D view.** With the 3D view open beside the options (move the window): *You are shown as* switches between the arrow, your character and both; *Camera on you* Behind turns the view to look your way; *Look straight down* off tilts the view; *Buildings* off flattens the towns; lower *Building detail* and *Ground detail* make the view coarser and faster (compare the frame rate in a city); *Turn your character* turns the model in steps of 15 degrees. The five model settings are tried in section 10.
6. **Position fixes.** The same as `/gps swapaxes` and `/gps flipfacing`: tick one only when the self-test or section 3 says so.

## 9. Quests

Have a few quests in your log in one zone, one of them tracked (click its number in the objective tracker). GPS shows them on the 2D map and in the 3D view; the traditional map shows them as Blizzard's map does. Options, AddOns, Gnomish Positioning System, *Quests* turns GPS's off; Blizzard's own option to show quest objectives on the map turns them off too.

1. **`/gps test`.** Five `quests:` lines; the third and fourth answer what only the game can:

| Line | Expected | If not |
|---|---|---|
| `quests: N zones on this map, M of your quests with a point on them, tracking ...; shown: yes` | N above 10 on a continent, M your quests in it | `0 zones`: send it (GPS found no zone maps here). `shown: no`: the setting or Blizzard's quest option is off. |
| `quests: 1. Blizzard's quest button (POIButtonTemplate): made` | made | NOT made: markers fall back to a plain quest mark; send the line. |
| `quests: 2. quest-area frame (QuestPOIFrame): made` | made | NOT made: no objective areas in GPS's 2D map; send the line. |
| `quests: 3. area hit-test for quest ...: shown A, invisible (alpha 0) B, hidden C -> 3D areas ...` | A above 0; send the numbers whatever they are | `UNKNOWN`: track a quest that shows an area on Blizzard's map and run `/gps test` again. |
| `quests: 4. look: ...` | a reminder for step 3 below | |

2. **2D markers.** Each quest has its number (or `?` when it is ready to hand in) where Blizzard's map puts it: compare with the traditional map (mode ring) at the same place. Hover one: its title and the objectives left, and its area appears. Click one: it becomes the tracked quest (the objective tracker agrees) and its area is drawn. Pan and zoom: markers stay put on the ground.
3. **2D areas.** The tracked quest's area (the shaded blob of Blizzard's map) lies over the same ground as on the traditional map. Zoom all the way in on it: it stays drawn and lined up, and is cut off at the window edge, not drawn outside it. Screenshot of both maps at the same place.
4. **3D markers and areas.** The same numbers stand on the ground at the same places; turn and tilt the view: they stay on their spots, disappear when off the view. Click one: it is tracked. The tracked quest's area lies on the ground under its marker in the same place and shape as on the 2D map (a translucent blue-violet fill with a brighter border; it appears a few frames after the quest is tracked); hover another marker: its area appears too, and goes when the mouse leaves. Over hills it follows the ground; tilt the view: it stays on the ground. Then `/gps3d test` and send its `quest areas:` line: `from the quest-area frame's hit-test ..., frame hidden` (or `at alpha 0`, or `behind the 3D view's ground`) and the last area's numbers (pieces, hit-tests, ms). `way not known yet (no area found ...)` with a quest that does show an area on the 2D map, or `none: ...`: send the line and a screenshot. Also check nothing flashes in the middle of the screen or in the 3D window while an area is being found (the frame that is asked is meant to stay invisible).
5. **Traditional map.** Your quests' numbers, the tracked quest's area, quest givers (`!`) and your map pin show as on Blizzard's world map; hover a number: its area; click: tracked.
6. **No side effects.** After clicking quest numbers in GPS's windows (also in combat), use the objective tracker and an action bar: no "Interface action failed because of an AddOn" messages and no Lua errors.

## 10. The game's own models (3D view)

The 3D view draws the game's own props and trees (off by default; *Props and trees* in the settings) and, if the game allows it, its buildings where they stand in the world, around the middle of the view. **Big buildings:** with the game's buildings on, fly to Mount Hyjal and zoom in on Nordrassil, the World Tree, from the side and from above: the tree once, with no blocky copy of it standing in or around it (until 2026-10-19 the parts of it further than *Model distance* from the middle of the view were also drawn as simplified shapes). Screenshots, and note anything else that looks wrong there. Turn the debug log on first (section 11): its `PERF` lines every 5 seconds give the game's frame rate and how many models are drawn, which is what this section measures.

1. **Buildings: the game's or simplified?** (Since 2026-10-21 the simplified shapes are the default: trying the game's buildings crashed Forever's client the first time the 3D view opened. Only try this deliberately, with nothing to lose: `/gps3d models buildings game`, or *Buildings close up* in Options. If the game crashes, `/gps3d models buildings simple` is already the saved choice after a restart.) Once chosen, the first time the 3D view looks at a place with buildings, GPS3D tries the game's own buildings and says in chat which way it went: *the game draws its own buildings in the 3D view* or *this game does not draw buildings (WMO models) in an addon's 3D view*. The `/gps3d test` probe line (section 6) says the same. Either way, send the chat line. The answer is kept per game version; `/gps3d models wmo` asks again.
2. **Look.** Props and trees are off by default (since 2026-10-19): turn on *Props and trees* in the settings (or `/gps3d models props on`) for this step. Goldshire and Northshire, tilted (straight-down ring off), 200 to 600 yards out: trees, fences, lamp posts, carts, rocks stand where they stand in the game world; compare with the game's own view from the same place (screenshots of both). Check in particular:
   - **Turn:** fences run along the roads and fields as in the game, signposts and carts face the same way. If every model is turned by the same angle, try `/gps3d models turn 90`, `180`, `270` (and `0` back) and note which is right.
   - **Lean:** on slopes, trees and fence posts that lean in the game lean the same way here. If they lean the wrong way, try `/gps3d models tilt flip` (or `off`: all upright) and note it.
   - **Size and height:** models are the game's size and stand on the ground, not floating or sunk (a few yards off everywhere: send a screenshot).
   - **Buildings,** if the game draws them: Northshire Abbey, Goldshire's inn and Stormwind look like the game's (textures, windows), and within the model distance GPS's simplified shapes are gone (no double walls); further out the simplified shapes remain.
   - **Caves and mines,** if the game draws buildings: look down on the cave just east of Northshire Valley and the mine in Northshire from a tilt. The cave's rock should look like the game's, with the ground around it. If tunnels, floors or rooms show through the ground, type `/gps3d models caves off` (their outside parts then stay as simplified shapes) and send a screenshot of both.
   - **Over the ground:** models are drawn over the terrain; tilted, a tree behind a hill should be left out, not drawn through the hill (note any that show through).
3. **Settings** (Options, AddOns, Gnomish Positioning System, *3D view*; or `/gps3d models ...`): *Buildings close up* (the game's / simplified), *Props and trees* on and off, *Props and trees at most* (50 to 1,500; `/gps3d models count`), *Model distance* (200 to 2,000 yd; `range`), *Smallest model* (2 to 40 px; `px`). `/gps3d models` alone prints what is shown.
4. **Performance.** In Goldshire and in Stormwind's Trade District, tilted, 400 yards out, with the debug log on: wait 10 seconds at each of these and type `/gps debug mark` with what you set (for example `/gps debug mark props 250`): props off; props 250 (the default); props 1000; model distance 1500; buildings simplified. Turn the view slowly for a few seconds at each. The log's `PERF` lines then show, for each, the frame rate (`game ... fps`), the 3D frame time, and `models: N shown ..., C choices, X ms average` (how long choosing took). Also note whether panning feels smooth while models appear (at most 40 new models load per tenth of a second).

## 11. Other addons' map markers

GPS shows other addons' markers in its windows while those addons are installed (Options, AddOns, Gnomish Positioning System, *Other addons*). Have GatherMate2 and HandyNotes (with a plugin such as HandyNotes: WoW Forever) installed if you can, and RareScanner.

1. **`/gps test`.** Two `other addons:` lines: the map layers copied onto the traditional map (expected: `GatherMate2, HandyNotes`, and RareScanner if it adds its own layer), those not copied with the reason (`TomTom (skipped: pins of HereBeDragons-Pins ...)` and Questie's are expected: their icons cannot be on two maps), and GatherMate2's node count for the map you are on. A layer listed as `failed` errored on GPS's map and was switched off: send the line (the reason is in it).
2. **Traditional map.** Open it on a zone where you have gathered or where HandyNotes has notes: GatherMate2's nodes and HandyNotes's icons are drawn as on Blizzard's world map. Hover one: its tooltip. Right-click a GatherMate2 node: its menu (delete, TomTom waypoint). Gather a new node, then open the map: it is there.
3. **2D map.** Zoom in to about a zone across the window: GatherMate2's nodes appear at the same places as on Blizzard's map (compare the two at the same spot), with the same icons and size; its own settings (which types to show, icon scale, transparency) apply. Hover and right-click as above. Zoomed further out, they are not drawn.
4. **3D view.** The same nodes stand on the ground around the middle of the view (within about 700 yards, with the camera closer than 2,000).
5. **The setting.** *Other addons' map markers* off: none of the above in any GPS window; on: back.
6. **No side effects.** Blizzard's own world map still shows these addons' markers as before; no Lua errors and no "Interface action failed because of an AddOn" messages, also after right-clicking nodes in GPS's windows.
7. Not covered yet: TomTom's waypoints and Questie's markers (a pin library, see above), and Leatrix Maps's changes to Blizzard's world map (its own window); TomTom's arrow works as always.

## 12. The planet (3D view zoomed all the way out)

On the Eastern Kingdoms and Kalimdor the 3D view's wheel zooms on past its old limit (14,000 yards) out to the whole planet: the view straightens to look straight down (14,000 to 18,000 yards; quest markers and your character fade out), the planet view takes over at 18,000 yards, the ground bends into a ball, the sea turns from the minimap's dark water to blue, and clouds, the Maelstrom and the glow round the planet's edge fade in. Dungeons and battlegrounds still stop at 14,000 yards.

1. **`/gps3d test`** adds three `planet:` lines:
   - *the world map from the game*: GPS3D reads where the continents sit on Blizzard's world map (`C_Map.GetMapRectOnMap` and each continent's world corners) and prints the numbers next to the classic numbers it ships. Expected: the two sets close (within a few hundred yards) and *using the game layout*. If the line says the game gives no layout, GPS3D uses the classic numbers: send the line either way.
   - a frame time at 60,000 yards: expected a few milliseconds.
   - *N of M images (`Globe\*.tga`) report loaded*: expected all (8 art images and 8 land pages). If fewer, the planet has holes where the land pages are, or no clouds or Maelstrom: send the line.
2. **Look, zooming out slowly with the wheel from your character to the planet** (the view following you): no jump anywhere, in particular at 18,000 yards (the ground giving way to the planet view: nothing should move or change sharpness) and while the sea turns blue. Then the whole planet: both continents, Kalimdor to the west across the sea, the Maelstrom between them (a dark whirlpool with foam streaking into it, under a spiral of grey storm cloud turning more slowly, now and then a flash of lightning), clouds of several kinds (storm spirals in the middle latitudes, the southern ones turning the other way, fronts trailing from them, fields of cumulus, thin veils of cirrus) each with a faint shadow on the sea below it toward the lower right, the side of the planet away from the light darker (clouds too), a glow round the edge, black space, your arrow where you are. Screenshots at a few steps, and one close to the Maelstrom (about 30,000 yards).
3. **Controls on the planet:** drag turns the planet (the point grabbed stays under the cursor), the wheel zooms toward the cursor, right-drag turns the view, double-click a continent flies down to it, `<` `>` turn the planet to the other continent, Me flies back to you. Dragging over to the other continent and zooming in there shows that continent's ground. Spin it: drag sideways again and again, round the far side (open sea and clouds) and back, several times: it keeps turning (until 2026-10-19 it got stuck on the far side), the continents come back upright, and the compass points to the planet's north all the way round; a click on it turns that north up. Dragging up or down stops 70 degrees from the equator. From the far side, Me and double-click fly round the planet at an even pace.
4. **Speed** with the debug log on (`PERF` lines): zoom out to the planet, turn it for a few seconds, `/gps debug mark planet`; zoom back in, `/gps debug mark ground`. The 3D frame times should be no worse on the planet than close to the ground.

## 13. The map key (GPS or Blizzard's map) and full screen

A globe button chooses what the game's map key (Key Bindings, *Toggle World Map*, M unless you changed it) opens: GPS or Blizzard's own Map & Quest Log. It is at the top right of GPS's windows (left of the full-screen button and the close X) and on Blizzard's map (left of its maximize arrow). Gold: the map key opens GPS. Start with the choice on Blizzard's map (a fresh install) and the debug log on.

1. **Blizzard's map.** Press M: Blizzard's map opens as always. Look at its top right: a round gold-ringed globe sits just left of the maximize arrow, the same height, not covering it or the title. Its tooltip says what the map key opens and what a click does. Send a screenshot of that corner.
2. **Switch to GPS.** Open a zone that is not yours on Blizzard's map (Westfall, say) and click the globe: Blizzard's map closes and GPS opens on that zone. Press M: GPS closes; M again: GPS opens. Press L (quest log): Blizzard's map opens with the quest log; M now opens GPS and closes Blizzard's map. GPS's own key binding (if you set one) still works.
3. **Switch back.** In GPS click the globe at the top right: GPS closes and Blizzard's map opens; M opens Blizzard's map again. `/gps mapkey gps` and `/gps mapkey blizzard`, and *Map key opens* on the settings page, do the same without switching windows.
4. **Rebinding.** With the choice on GPS, bind *Toggle World Map* to another key in Key Bindings: the new key opens GPS, M no longer does anything of the map's. Bind it back.
5. **Combat.** In combat, click a globe or use `/gps mapkey`: GPS says the change waits for the end of combat (the game allows no binding changes then), and no "Interface action failed because of an AddOn" message appears. After combat the key does what the choice says. In combat with the choice on GPS, M opens and closes GPS.
6. **Taint.** After switching back and forth a few times (also once in a group), use Blizzard's map normally: click quests in its log, track one, open the map in combat with M (choice on Blizzard's map). No "Interface action failed" messages, no Lua errors, and no `TAINT` lines in the debug log. Send the `map key:` line of `/gps test`: it says the choice, which keys Blizzard's map key has, and what the game reports for them (`M -> GPS_TOGGLE` while the choice is GPS).
7. **Full screen.** In the 2D map, the arrow button left of the close X: the window fills the screen; the button turns into the "back" arrow and the resize corner goes; dragging the title band does nothing. Switch modes with the mode ring: 3D view and traditional map fill the screen too. Click the arrow again: the window is back at exactly its old place and size. Turn it on, `/reload`, press the key: GPS opens at full screen. Change the UI scale or the resolution while it is on: it still fills the screen. Escape still closes it. `/gps reset` turns it off.

## 14. What to send back

**The debug log first.** Before you start, type `/gps debug on` (or tick *Keep a debug log* in Options, AddOns, Gnomish Positioning System). GPS then writes down what it does: windows, maps, your position, quests, settings, frame times, and every Lua error in GPS with its stack. When something looks wrong, type `/gps debug mark` and a few words (for example `/gps debug mark arrow points the wrong way`) so the moment is easy to find. At the end, `/reload` or log out: the game writes the log to `_classic_beta_\WTF\Account\<your account>\SavedVariables\GnomishPositioningSystem.lua`. Send that file (it also holds GPS's settings; nothing else). It never grows past about 1 MB: if you forget to turn it off, the oldest lines go and the file stays that size; GPS reminds you at each login while it is on. `/gps debug off` stops it, `/gps debug clear` empties it, `/gps debug show` shows the newest lines in a window to copy.


1. `_classic_beta_\Logs\WoWChatLog.txt` (after a `/reload` or logout), or copy the `GPS test` and `GPS3D test` lines by hand; the five `quests:` lines with a quest tracked (section 9) above all.
2. Screenshots from `_classic_beta_\Screenshots` (Print Screen in game): the 2D map zoomed in near you, zoomed out, the traditional map on a zone and in a dungeon, and the 3D view in Follow, in Behind, and zoomed in on your character; with a quest tracked, the 2D map and the traditional map at the same place (its area on both), the 2D map zoomed all the way in on that area, and the 3D view with your quest markers; the 3D view tilted over Goldshire with the game's models, next to the game's own view of the same place (section 10).
3. Any Lua error text.
4. Short notes per step: worked, or what you saw instead.

The easiest hand-over is to copy these into a `testing/` folder in this repository.

## Known risks and what fixes them

- **The planet and the 2D map's two continents: the game's world map gives no layout, or a different one.** GPS (`World.lua`) then places the continents by the classic world map's numbers (section 12, line 1); if the game's numbers differ a lot from those, the planet still works but the continents sit as the game's world map has them. The land pages (`Globe\Land_*.tga`, 512 x 512, 32-bit) not loading would leave the continents missing on the planet beyond about 25,000 yards: the `planet:` images line says so.
- **The game's buildings (WMOs) do not draw in an addon's ModelScene.** Quite possible: Blizzard's source does not say either way. GPS3D checks it and keeps the simplified shapes; only the chat line and the probe line are needed.
- **Every model turned or leaning wrong.** The rotation is read exactly from the game files (checked against MapExplorer's matrices), but the order in which the game's actors apply yaw, pitch and roll is not in Blizzard's source: `/gps3d models turn <deg>` and `/gps3d models tilt flip|off` correct it without new code; send which one was right.
- **Frame rate drops with many models.** Lower *Props and trees at most*, *Model distance*, or raise *Smallest model*; send the PERF lines from section 10.

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
| `traditional map: ... NOT available`, or `/gps map` says Blizzard's map is not available | `MapCanvasMixin` missing (Blizzard_WorldMap not loaded) | Send the line; GPS tries to load `Blizzard_WorldMap` itself first |
| Lua error in `Blizzard_MapCanvas` or `MapWindow.lua` when the traditional map opens | The canvas is built differently from Blizzard's XML in this client | Send the error; `tools/sandbox/test_blizzard_canvas.py` runs Blizzard's canvas code against `MapWindow.lua` and is where to reproduce it |
| Map pins draw over the rings | Pin frame levels above 9500 in this client | Send a screenshot; raise `CHROME_LEVEL` in `MapWindow.lua` |
| "Interface action failed because of an AddOn" after using the traditional map | Taint from Blizzard's map code run by GPS | Send the message and what you clicked; the data provider list in `MapWindow.lua` can be cut down |
| Mode ring says the 3D view needs GPS3D | `GPS3D` folder not copied, or out of date | Copy `prototypes/GPS3D` again; tick it in the AddOns list |
| Triangles flicker or poke through | Draw-order buckets too coarse | More bucket frames, or sort per building |
| `quests: 0 zones on this map` | GPS found no uiMap at the points it tried on this map | Send the line and where you stood; the zone search in `Quests.lua` (`ZonesOn`) needs another starting point |
| Quest markers away from where Blizzard's map puts them | `C_Map.GetWorldPosFromMapPos` axis order differs from what GPS assumes | Send a screenshot of both maps at the same place; swap the axes in `Quests.lua` (`Q.ToGrid`) |
| `quests: 1. ... NOT made` | `POIButtonTemplate` not usable by addons here | Markers fall back to a plain quest mark (no number); send the line |
| `quests: 2. ... NOT made` | Addons may not make a `QuestPOIFrame` | No 2D or 3D areas; markers still work; send the line |
| 2D area missing when zoomed far in, drawn outside the window, or off its place | The area frame does not like very large sizes, or ignores clipping | Send the screenshots; cap the zoom at which areas are drawn |
| `quests: 3. ... NOT possible this way` | The hit-test answers only for a shown, visible frame | The 3D view asks a frame drawn behind its own ground instead (the `quest areas:` line of `/gps3d test` says `behind the 3D view's ground`) |
| `quest areas: ... way not known yet` with a tracked quest that has an area on the 2D map | The hit-test does not answer an addon's frame at all, or wants other coordinates | 3D keeps markers only; send the line and the `quests: 3.` line |
| 3D area in the wrong place or mirrored against the 2D one | The hit-test's x and y are not the zone's 0..1 coordinates as Blizzard's map passes them | Send screenshots of both; the sampler in `Quests.lua` (`Step`) converts the points |
| "Interface action failed because of an AddOn" after clicking a quest number | Taint from Blizzard's quest button run by GPS | Send the message; GPS's markers can track with `C_SuperTrack` directly instead of Blizzard's button |
