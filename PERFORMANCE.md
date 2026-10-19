# GPS3D performance notes

Kept for a later round of performance work. Everything here was measured in the browser sandbox
(`tools/sandbox`, native Lua 5.4 + a simulated WoW UI), not in the game: call counts are exact, milliseconds
are noisy (about ±20 %) and say nothing certain about the real client, where the Lua-to-C calls
(`SetVertexOffset`, `SetDrawLayer`, `SetParent`, `Show`/`Hide`, `SetTexture`...) are expected to dominate.

## Applied (2026-10-14, the "light" set, 7 changes)

From a review by a separate agent; the change itself is in the git history (the diff kept here until
2026-10-18 was removed: it could no longer be applied to anything).

1. Free mode: when only you moved, redraw just the marker (`RenderMarker`), not the world.
2. Skip `SetVertexOffset` for vertices that moved less than `VO_EPS` = 0.25 px since last sent (decided per
   vertex so triangles sharing it agree; tile-edge vertices always resent; resent after `SetParent`). Set
   `VO_EPS = 0` to turn it off if the ground ever looks laggy.
3. No per-frame allocation: numeric mesh keys, pooled candidate tables, frame stamp instead of `isActive = {}`,
   static sort comparator, no closures in `FixEdges` / `BuildGridMesh` / `BuildBlockMesh` / marker code.
4. Building level chosen from triangle counts stored by `TileBlocks` (block header), so only the drawn level is
   decoded.
5. Fewer C calls when building meshes: textures remember file and colour; pooled textures are not hidden twice.
6. Single cull/bucket/draw pass; `SetVertexOffset` bound once as a local.
7. Compass and title only updated when they change.

Effect (sandbox, Stormwind, buildings on, budget 4000), before -> after:

| Case | ms | C calls / frame | garbage / frame |
|---|---|---|---|
| camera still, view redrawn | 10.2 -> 5.7 | 16,525 -> 5 | 91 -> 3 KB |
| walking (0.25 yd / frame) | 10.6 -> 8.3 | 16,613 -> 15,468 | 91 -> 3 KB |
| turning 3 deg / frame | 16.6 -> 15.3 | 20,983 -> 20,532 | 168 -> 46 KB |
| ground only, turning | 6.2 -> 5.0 | 6,476 -> 6,445 | 90 -> 65 KB |
| running fast, new blocks | 54.5 -> 43.9 | 24,233 -> 22,976 | 920 -> 504 KB |

## Not applied yet: one texture per ground cell (quads)

Each grid cell is a quad, so it can be one texture (4 vertex offsets) instead of two triangles: half the
ground textures and C calls. Measured on top of the light set: turning in Stormwind 15.3 -> 10.5 ms and
20,532 -> 16,789 calls; ground only 5.0 -> 2.8 ms and 6,445 -> 3,431 calls; running fast 43.9 -> 39.5 ms.

Held back because:
- the client folds a bent texture along one of its diagonals, and we do not know which; `GridHeight` (marker
  height) assumes the north-west to south-east split. Screenshots differ from the triangle version in 1.6-5 %
  of pixels (steep hillsides);
- at the edge of a drawn building block the seam (wall showing through the hill) gets wider: a quad whose centre
  is inside the block gets the depth bias over twice the area of a triangle. Fix idea: bias only quads fully
  inside the block, or split straddling quads back into triangles.
Check the fold in game first (a steep slope, compare with `/gps3d detail off`), then fix the seam and apply.
The change, as a diff against the current GPS3D.lua: `tools/sandbox/perf/quads.diff` (in `BuildGridMesh` and the
draw loop; apply with `patch prototypes/GPS3D/GPS3D.lua < tools/sandbox/perf/quads.diff`).

## Camera clearance and cut triangles (2026-10-16)

The camera's lift samples up to 97 ground heights per camera move (49 round it, up to 48 along the view
line), skipped when the camera is clearly above the tile maxima (`TileTop`, computed once per tile). Without
that skip, walking in Stormwind at distance 800 cost +4 ms per frame (fine building blocks decoded for the
samples); with it, the Stormwind scenes measure the same as before within the sandbox's noise (turning
6.0-7.0 vs 6.2-6.5 ms, walking 5.7-6.3 vs 5.7-6.0 ms over two runs each), the 20 yd/frame hitch scene
29-31 vs 23-29 ms and 637 vs 472 KB garbage. Tilted panning over flat ground (`tools/sandbox/perf_tilt.py`
with FLAT=1, two runs): 30 degrees 5.0-5.1 vs 4.3-4.9 ms, 45 degrees 7.0-7.5 vs 6.1-6.2 ms, same C calls; the
cut-triangle path runs for about 170-200 triangles per frame there, all rejected by a side-of-view test before
any work. Lift alone: about 0.1 ms. If tilted views feel slower in game, the view-ahead samples are the first
thing to thin (`AHEAD_STEP`).

## Ideas looked at and not done

- Bucket hysteresis to cut `SetDrawLayer` calls (~3,000 / frame while turning fast): loosens draw order.
- Dropping grid cells fully under drawn blocks: 5-10 % fewer textures, risks holes where block meshes have gaps.
- Lower `BUILD_LIMIT` (1,500 triangles of new blocks per frame) to spread the hitch when new blocks appear; in
  the sandbox the hitch is mostly the simulated engine's `SetParent`, so measure in game first.
- Flat arrays instead of a table per triangle: estimated 1-2 ms of Lua per frame, a large refactor.
- Building data (54 MB of strings, about 0.17 s parse at login) as load-on-demand addons per continent: saves
  login time and a lot of memory; not prototyped.
- Coarser building data for cities (Stormwind blocks are about 1,300 triangles fine): the old Northshire mesh,
  simplified with meshoptimizer, had 7,262 triangles for the whole tile at 1 yd; delatin gives 14,030 for the
  same tile and error. Worth trying meshoptimizer in the exporter.

## Heights read from the strings (2026-10-17)

`TileHeights` used to decode a tile's 1,089 heights into a table the first time anything touched the
tile, and kept it; zoomed out, the view touches every tile of a continent just for its height range.
Measured in the sandbox (native Lua 5.4), first zoom-out over the Eastern Kingdoms / Kalimdor:
92 / 164 ms in one frame and +20.6 / +28.3 MB of Lua memory, kept. Now the data carries each tile's
highest height (2 characters at the end of its string, `build_world.py`) and heights are read from
the string when asked for (`__index`): 19 / 20 ms and +2.7 MB (mostly the meshes). A steady frame
reads about 240 heights; frame times in towns did not change (`perf_buildings.py`, same within noise).

## How to measure

`tools/sandbox/perf_focus.py <label>`: per-frame median ms, C calls by type and garbage for fixed scenes
(swap `site/addons/GPS3D/GPS3D.lua` to compare versions). `perf_buildings.py`: budgets 2,000 / 4,000 / 8,000
and walking. In game: `/gps3d test` prints render ms; compare `/gps3d detail off`, `/gps3d buildings 2000`.

## Image memory (2026-10-14)

Minimap images are now chosen by on-screen size (`MINIMAP_PX` = 80), not by mesh step. That ended blurry patches
(tilted at 800 yd: 42 % of the screen used the 64-px overview, now 0 %), at the cost of more distinct minimap
images in use: up to 67-74 in the sandbox (straight down at 3,000 yd, tilted at 1,500 yd) instead of up to 19.
At 512 x 512 that is roughly 10-20 MB of texture memory, depending on the client's format. Raise `MINIMAP_PX`
if that turns out to matter.

## Quest markers (2026-10-17)

Measured in the sandbox (native Lua, Elwynn Forest, 7 stand-in quests, best of 3 runs of 60 frames or 200 layouts): the 3D view at 2,500 yd tilted, 5 markers in view, 2.05-2.06 ms per frame with markers against 2.03-2.16 ms without (within the run-to-run noise); the 2D map 0.23-0.26 ms per layout with markers and the tracked quest's area against 0.21 ms without. The quest list is built once per change (0.25 s after a burst of quest events), not per frame; each frame only moves the markers (2D: on every layout; 3D: in `Render`, each quest's ground height looked up once).

## The game's models (2026-10-17)

`Models.lua` puts the game's own props, trees and (if the game allows) buildings in the ModelScene. The Lua side is kept off the per-frame path: `Render` only compares the camera with the last choice (`ns.UpdateModels`, a few comparisons); the choice itself runs at most 10 times a second, and only after the view moved 4 % of the model distance, zoomed 5 %, or turned or tilted 2 degrees. Actors are placed once when chosen (the game moves nothing per frame but the scene's camera), keep their model while chosen again, and an actor already showing a model is reused for the same model before another one loads; at most 40 loads per choice.

Measured in the sandbox (native Lua 5.4; `tools/sandbox/perf_models.py` and `test_models.py`'s COST line): one choice, tilted 400 yd over Goldshire with 250 props, the occlusion test included, 2.9-3.1 ms on average (about 5 ms at worst), so at most about 30 ms a second while the view keeps moving and nothing while it stands still. `Render` itself: 11.3 ms with props off and 13.4 ms with 250 (Goldshire) or 17.8 and 15.6 ms (Stormwind), within the run-to-run spread of the sandbox. Tiles are decoded when first needed (a busy tile, about 4,000 placements, once) and 200 are kept; each map's buildings (2,246 in the Eastern Kingdoms) are listed once.

Not measured here, and the main unknown: what the game itself spends drawing the actors (hundreds of animated M2 models, and WMOs if they load). The debug log's `PERF` lines carry the game's frame rate next to the number of models shown, choices and their times and model loads (TESTING.md section 10 step 4 gives the runs to compare); the settings (*Props and trees at most*, *Model distance*, *Smallest model*) are the knobs.

## The planet (2026-10-19, `Globe.lua`)

Measured in the sandbox (native Lua, `test_globe.py`): a planet frame at 60,000 yd about 0.4 ms of Lua, 100,000 yd 0.3 ms, the bending range (32,000 yd) 0.9 ms, just past the hand-over 2 ms (the overview images and the planet's pages both drawn while they cross-fade, up to two triangles per land tile), against 3.3 ms for the ground at 12,000 yd. No garbage per frame (memory flat over 300 frames: no tables or closures made while drawing). What keeps it cheap:

- the land is coarse where it can be: blocks of 1 to 8 tiles by size on screen and curvature (about 200 triangles for the whole planet at 60,000 yd);
- the sea, its shading and the glow are three textures (a disc cut to the canvas), not triangles;
- a level's unit vectors are kept while the curvature does not change (turning and panning the round planet only rotates them);
- textures are handed out once per level and kept between crossings of the hand-over; zoomed out past 6,000 yd an idle warm-up hands out the hand-over's 4 levels' images 400 a frame, so the first crossing costs about as much as the next frame (5.6 ms against 3.5 in the sandbox) instead of setting about 2,400 images at once;
- the Maelstrom turns on its own (its whirlpool, storm and a lightning flash: up to 12 vertex offsets a frame) without redrawing the planet.

Textures: up to about 5,700 land textures (both continents, each block size), about 90 clouds and their shadows (one quad each, the shadow the cloud's corners moved on screen, no second projection), 8 others, on top of the ground's pool. Images: 8 land pages of 1 MB (512 x 512, 32-bit TGA), 2 of 1 MB for the Maelstrom (whirlpool and storm, 512 x 512) and 9 smaller ones. The planet with the new sky (2026-10-19): 0.4-0.5 ms a frame at 60,000 yd, as before.

## The 2D map with both continents (2026-10-19, `World.lua`, `Core.lua`)

Zoomed out on the Eastern Kingdoms or Kalimdor, the other continent is drawn beside it (its overview images, and its minimap tiles close up). Measured in the sandbox (native Lua, 200 redraws each): 0.14 ms a redraw close up on the Eastern Kingdoms (48 live tiles, the other continent out of view), 0.09 ms zoomed out with both in view (overview images only), 0.16 ms close up over Kalimdor's coast while the view's map is still the Eastern Kingdoms (34 of Kalimdor's tiles). The other continent's images are made once and kept.

