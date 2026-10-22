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

## GPS as the minimap (2026-10-22, `Minimap.lua`)

The minimap is on screen all the time, so it draws only when the camera moved (you moved more than 0.01 yd, turned, the zoom, size or tilt changed) or building blocks wait to be made, at its own budgets (1,200 ground and 1,500 building triangles against the 3D window's 3,200 and 4,000), and only the ground and blocks (no models, markers or arrow); the per-vertex skips (`VO_EPS`) and the kept choice (A1) work as in the 3D window. Sandbox (`test_minimap.py`, Stormwind's Trade District, zoom 0, 233 yd to the rim, Lua 5.4), per frame: standing still 0.01 ms and no texture calls (no redraw); walking 0.25 yd a frame 1.8 ms, about 1,300 texture calls, 1,700 textures shown, against the 3D window walking the same path 7.8 ms, 18,200 calls, 4,500 textures; turning (Rotate Minimap on, 3 degrees a frame) 7.6 ms and 11,100 calls, every vertex moving. The round mask is one `AddMaskTexture` per texture when the minimap takes the canvas (about 5,900 calls once, the whole pool), none per frame; what masks cost the client per frame is not known (TESTING.md section 17). Memory: nothing of its own beyond GPS3D's caches (Lua heap after walking 300 frames 22.6 MB, off 22.7 MB).

## Applied (2026-10-22, perf round A5): building and model data loaded on demand
## Applied (2026-10-22, perf round, step "probe"): `/gps3d probe`, the in-game measurements

Per continent instead of per band the first use would cost 60 ms (Kalimdor) to 73 ms (the Eastern Kingdoms) in one
frame (measured the same way); per band it is a third of that, at the cost of nine folders to copy instead of three. Drawn: the same, checked
by `test_ondemand.py` (the full draw state, every texture and model actor, against a game with everything loaded at
login, and against the code before this change) and by the page's screenshots (12 views of `scn_buildings.py`
pixel-identical outside the window's title and footer, whose fade differs between two runs of the same code too).
What only the game can tell: the client's own cost of `LoadAddOn` for a 6 MB file (expected near the Lua 5.1 parse
time above) and whether it stutters; TESTING.md section 7 asks for a look.
| | before | after |
Item A5 of the J9 review (moved here from "Ideas looked at and not done"). The buildings (`Detail_*`) and the game's
model placements (`Models_*`) are load-on-demand addons next to GPS3D (`GPS3D_EK1`..`4`, `GPS3D_Kalimdor1`..`3`,
`GPS3D_Instances`, `GPS3D_Models`; `OnDemand.lua`, AGENTS.md *Data on demand*), loaded when the view comes within a
tile of their reach, when anything reads a tile's buildings, or (models) when models are switched on; World, Lod,
the planet and the buildings' index (`Data/DetailParts.lua`, 20 KB) stay at login. Measured with the same data,
before -> after:
The review of 2026-10-22 (J9) found that the sandbox cannot say what one texture or one C call costs in the client,
and that three of its biggest suggestions wait on the client's drawing rules; its section 2 asked for those checks
first. `/gps3d probe` (`Probe.lua`, TESTING.md section 15) runs them in about a minute: frame time, GPS3D's Lua ms,
textures and calls at ground budgets 800 / 3,200 / 6,400 and building budgets 2,000 / 4,000 / 8,000, still,
redrawn and turning (the cost per texture and per call: decides between fewer textures (B1), fewer calls (C1) and
less Lua (A1)); the fold diagonal of a bent texture (B1); whether `RotateTextures` turns vertex-offset geometry
(C2); `SetPointsOffset` on a depth frame of the real ground, its cost and whether your arrow stays on the shifted
ground (C1); `OffScreenFrame` snapshots (C3). Nothing changes in normal frames (its driver frame is hidden until
asked), measured with `perf_focus.py` before and after, same scenes:

| Scene (sandbox, Stormwind unless named) | before: ms / C calls / garbage | after |
|---|---|---|
| login, Lua 5.1 (parse + run of the data GPS3D.toc lists, fastest of 5; `testing/2026-10-22-perf-round/a5_loadtime.lua`) | 224 ms, 69 files, 60.5 MB | 24 ms, 34 files, 6.2 MB |
| Lua heap kept after login, Lua 5.1 | 59.3 MB | 4.8 MB |
| login in the sandbox (Lua 5.4, lupa; `test_ondemand.py`) | 590-700 ms, +59.9 MB | 53-71 ms, +5.4 MB |
| the sandbox page's boot (both addons, WebAssembly Lua) | 1,292 ms | 391 ms |
| first use of a band, Lua 5.1 (one hitch per band per session) | none | 21-22 ms per 6 MB band (EK1-3, Kalimdor1-2), 17 ms Kalimdor3, 8 ms EK4, 35 ms the instances (9.9 MB), 28 ms the models (7.7 MB) |
| first use, sandbox | none | 58-63 ms (EK3, Lua 5.4) |
| the check before every frame | none | 1.5 us, no garbage (10,000 calls) |
| Stormwind Trade District, buildings 4,000, turning 3 deg/frame (`perf_buildings.py`, three runs each) | 5.2 / 6.0 / 7.7 ms | 6.0 / 5.9 / 6.0 ms (same textures, blocks and triangles in every row) |
| turning 3 deg, buildings on | 7.0 / 18,744 / 53 KB | 7.3 / 18,744 / 53 KB |
| camera still, redrawn | 3.6 / 5 / 3 KB | 3.6 / 5 / 3 KB |
| walking 0.25 yd a frame | 5.8 / 19,352 / 3 KB | 6.2 / 19,352 / 3 KB |
| running 20 yd a frame (new blocks) | 18.4 / 19,560 / 194 KB | 17.0 / 19,560 / 194 KB |
| Northshire, turning, buildings on | 6.7 / 17,376 / 3 KB | 5.9 / 17,376 / 3 KB |

(The calls and garbage are exact and identical in all 12 scenes; the milliseconds are the sandbox's noise.) The
probe's own call count agrees with the engine's exact count within 2 % (turning 3 degrees a frame 19,877 against
20,059; turning 0.33 degrees 18,534 against 18,570; redrawn 0 against 5: the marker's). The sandbox's own run
(Stormwind, 330 yd straight down, 30 fps fixed, so its frame times say nothing) gives textures 375 / 1,239 / 4,121
for the ground budgets and 3,005 / 4,488 / 4,750 for the building budgets, turning 1,700 to 19,000 calls a frame,
redrawn 0.

## Applied (2026-10-22, perf round, step A1): the tile and block choice kept between frames

The review of 2026-10-22 (J9, its A1) found `ChooseTiles` (with the level-of-detail controller) and `ns.ChooseBlocks`
running every frame: 6-18 % of the Lua frame in cities, 40-50 % far out. They test every tile and block against
the view grown by 40 px, so their result can only change where something crosses that edge. Now (`ns.choice`, the
wrapper after `ChooseTiles` in `GPS3D.lua`) a frame keeps the last full choice while every point that can show on
the canvas lay inside the grown view it was made for (the view's pyramid between a depth to which everything is
known to be chosen and the farthest the range allows: its 8 corners tested), while the controller rests and the
kept levels stay within its target and the budget, and at most 4 frames (`KEEP`). Each kept tile's level and image
are still worked out per frame; which tiles and blocks are candidates and the blocks' levels wait for the next full
choice. A resize, another map, a budget, buildings switched, the game's buildings covering blocks and the probe
choose afresh at once. `ns.choice.off = true` chooses every frame as before.

The review proposed that the controller simply step only on the full choices, taking the skipped frames' steps
then. Measured, that made the ground jump while zooming (Durotar up to 14.35 px a frame, `test_terrain.py` failed;
before 5.84 px), and one step per full choice let it fall behind (453 instead of 2,107 ground triangles over
Durotar). So a frame is kept only while the controller rests: zooming, when it works every frame, keeps choosing
afresh, and the zoom sweeps and far views of `test_terrain.py` are the same as before (max jumps 5.68 against 5.84
px and so on; same triangles and height errors).

Measured with `tools/sandbox/test_choice.py` (before: `GPS3D_LUA=<the code at 2cce3ea>`; milliseconds best of 3
runs, processor time, another agent's tests sharing the two cores part of the time; calls and garbage exact). Each
of its 1,105 frames is checked against a full choice made again from the same state: no tile or block missing on
the canvas (also with the choice kept as long as the bound alone allows), the full choice on every fresh frame,
differences at most 3 frames (blocks at the budget's far end), corners within `VO_EPS`.

| Scene (sandbox) | kept | Render ms, median | the choice, ms a frame (mean) | saved, share of the frame | C calls a frame (mean) | garbage KB (median) |
|---|---|---|---|---|---|---|
| Stormwind, walk 0.25 yd/frame, straight down | 74 % | 4.37 -> 4.11 | 0.56 -> 0.19 | 8 % | 18241 -> 18250 | 2.8 -> 2.9 |
| Stormwind, walk 0.25 yd/frame, tilted 45 | 74 % | 3.84 -> 3.66 | 0.58 -> 0.19 | 9 % | 14230 -> 14282 | 2.8 -> 2.9 |
| Stormwind, pan 2 yd/frame, straight down | 53 % | 3.78 -> 3.47 | 0.48 -> 0.23 | 6 % | 14897 -> 14771 | 3.2 -> 3.3 |
| Stormwind, turn 1 deg/frame, straight down | 75 % | 4.79 -> 4.31 | 0.58 -> 0.19 | 8 % | 18203 -> 17988 | 2.8 -> 2.9 |
| Stormwind, turn 3 deg/frame, tilted 45 | 0 % | 12.01 -> 11.45 | 0.77 -> 0.70 | 0 % | 21189 -> 21392 | 103.8 -> 70.9 |
| Stormwind, tilt 1 deg/frame, 45 to 89.9 | 36 % | 9.78 -> 9.75 | 0.57 -> 0.38 | 2 % | 20936 -> 20941 | 3.2 -> 3.3 |
| Stormwind, zoom in 2 %/frame, 800 to 240 yd | 23 % | 5.09 -> 4.90 | 0.61 -> 0.47 | 2 % | 17907 -> 18069 | 2.8 -> 2.9 |
| Stormwind, still, redrawn | 90 % | 2.44 -> 1.96 | 0.46 -> 0.07 | 16 % | 101 -> 101 | 2.8 -> 2.9 |
| Orgrimmar, walk 0.25 yd/frame, tilted 45, 150 yd | 69 % | 3.89 -> 4.04 | 0.38 -> 0.15 | 6 % | 13747 -> 13757 | 2.8 -> 2.9 |
| Orgrimmar, pan 1 yd/frame, tilted 45, 150 yd | 52 % | 4.08 -> 4.14 | 0.39 -> 0.22 | 4 % | 13449 -> 13444 | 3.2 -> 3.3 |
| Orgrimmar, turn 1 deg/frame, tilted 45, 150 yd | 47 % | 5.20 -> 5.11 | 0.42 -> 0.25 | 3 % | 14515 -> 14994 | 6.4 -> 6.1 |
| Orgrimmar, zoom out 2 %/frame, 150 to 500 yd | 22 % | 11.91 -> 11.46 | 0.54 -> 0.45 | 1 % | 22376 -> 22608 | 11.9 -> 9.2 |
| Hyjal far, turn 1 deg/frame, 5,000 yd tilted 45 | 57 % | 3.40 -> 3.24 | 1.18 -> 0.75 | 12 % | 5556 -> 5536 | 28.2 -> 16.7 |
| Hyjal far, pan 20 yd/frame, 5,000 yd tilted 45 | 62 % | 2.58 -> 2.08 | 1.03 -> 0.62 | 14 % | 4378 -> 4365 | 7.1 -> 3.5 |
| Hyjal far, tilt 0.5 deg/frame, 5,000 yd | 60 % | 3.34 -> 2.97 | 1.15 -> 0.70 | 13 % | 5710 -> 5660 | 10.5 -> 10.5 |
| Hyjal far, zoom in 2 %/frame, 5,000 to 1,500 yd | 15 % | 5.00 -> 4.91 | 1.32 -> 1.37 | -1 % | 11198 -> 11016 | 64.2 -> 56.3 |
| Hyjal far, still, redrawn | 100 % | 2.24 -> 1.35 | 1.11 -> 0.01 | 49 % | 5 -> 5 | 2.8 -> 2.8 |
| Eastern Kingdoms, turn 1 deg/frame, 12,000 yd tilted 55 | 62 % | 5.07 -> 3.64 | 2.10 -> 1.20 | 18 % | 7496 -> 7478 | 12.0 -> 7.9 |
| Eastern Kingdoms, still, redrawn, 12,000 yd | 93 % | 3.64 -> 1.99 | 1.95 -> 0.13 | 49 % | 58 -> 18 | 2.7 -> 2.7 |

A kept frame's choice costs 0.15 ms against 0.87 ms for a full one (Refresh: each kept tile's level and image; Near
and Inside: the bound). Turning 3 degrees a frame tilted leaves the margin every frame (0 % kept); zooming keeps
few (the controller works). The milliseconds that count are the client's: the same C calls, so only the Lua side
is saved; the debug log's PERF line counts the frames that kept the choice (TESTING.md section 16).

## Applied (2026-10-22, perf round, step A2): pooled building tables

The review of 2026-10-22 (J9, its A2) found that a frame making new building blocks allocated a table per new
triangle (`BuildBlockMesh`) and new arrays per decoded block (`BlockGeo`), while the ground's triangle tables were
pooled since J8. Now the blocks' triangle tables come from that pool and go back with their mesh (`ReleaseMesh`;
every field set again), a released block mesh's `px`, `py`, `pd` and `tris` arrays are used for the next one
(`pool.sets`, its screen positions emptied so it starts as a new mesh), and a decoded block the cache forgets
gives its arrays to the next decode (`pool.geo`; while a mesh still draws its vertices, when that mesh is given
back). Where the allocation went before (busy frames of a shorter first route, wrapped functions, the engine's own tables counted): `BuildBlockMesh` 42 %, the ground's new
tile meshes 21 % (`Lod.NewMesh`'s arrays, not pooled), `BlockGeo` 12 %.

Measured with `tools/sandbox/test_blockbuild.py` (before: `GPS3D_LUA=<the code at 15bb3e4>`; running 20 yd a frame,
three laps round Stormwind, 369 frames of which 220 make blocks; GC stopped during each frame; ms processor time
without the engine's slow `SetParent`, two runs each; calls exact):

| Running 20 yd a frame round Stormwind (sandbox) | before | after |
|---|---|---|
| garbage a frame that makes blocks (median) | 142 KB | 29 KB |
| ... laps 2 and 3 (pools full) | 112 KB | 19 KB |
| ... frames making nothing | 6 KB | 3 KB |
| making blocks, ms a frame (median / worst) | 0.40-0.42 / 8.0-8.5 | 0.36-0.37 / 8.4-8.5 |
| Lua ms a busy frame (median / worst frame) | 6.9-7.0 / 19.7-25.7 | 7.3-7.6 / 22.0-29.5 (noise: frames making nothing moved the same +0.5 ms) |
| C calls a frame (busy median / worst / quiet median) | 19,014 / 36,658 / 17,933 | the same |

Drawn: the same. Every frame every block triangle drawn equals an independent decode and build of its block and
lies where its vertices project (1.3 million triangles), and three views after the run are identical texture for
texture to the code before. The worst frame (2.7 MB) makes new ground tiles, which this step does not touch.
`BUILD_LIMIT` 500 (with the pools): making blocks 4.1-4.8 ms at worst instead of 8.4-8.5, the worst frame 19.2-21.7
ms, but 23 block-frames flat on the canvas (none at 1,500), one block 4 frames (133 ms) late: not applied. In the
game the saving is the collector's: about 110 KB less to collect for every frame that makes blocks.

## Applied (2026-10-22, perf round, step A4): keep less per decoded block

The review of 2026-10-22 (J9, its A4) found that the cache of decoded building blocks (`geoCache`, up to 400 blocks)
kept every block's triangle corners (`idx`), vertex colours (`vc`) and palette for its whole life, though after its
mesh is made only the vertices (`vx`, `vy`, `vh`) are needed every frame; the corners are read again only by
`BlockHeight` (your height, the camera's lift, the quest areas' corners, the cursor's ground point), which also kept
an 8x8 grid of the triangles on every block it was asked of. Now a cached block keeps its vertices and where it is in
its string; the corners, colours and palette are decoded again when a mesh is made (`ns.BlockTris`, into one set of
arrays, `pool.rest`, no garbage), and `BlockHeight` keeps corners and grid for the last 16 blocks asked
(`ns.blockHold`; one array per block for the grid, not one per cell). `ScreenToTerrain` (a wheel step zooms toward
the cursor's ground point, a left-press grabs it) no longer asks a block's triangles where its ray is more than a yard
above the block's highest vertex and the grid there: a low tilted ray passes over up to 14 blocks.

Measured with `tools/sandbox/test_blockmem.py` (before: `GPS3D_LUA=<the code at 7d8f038>`; Lua 5.4; the cache's heap
is every block it holds decoded afresh into new arrays plus the heights' lookups, the difference of the collected heap):

| Stormwind / Orgrimmar, 330 yd following (sandbox) | before | after |
|---|---|---|
| the cache's Lua heap (306 / 371 blocks) | 11,337 / 11,857 KB | 5,312 / 4,901 KB (-53 / -59 %) |
| ... of which the decoded blocks | 9,155 / 10,580 KB (29.9 / 28.5 KB a block) | 3,031 / 3,527 KB (9.9 / 9.5 KB a block) |
| ... of which the heights' lookups | 51 / 36 blocks, 2,182 / 1,277 KB | 16 / 16 blocks, 2,281 / 1,374 KB |
| whole Lua heap after the scenario | 77.3 / 112.9 MB | 72.3 / 92.3 MB |
| making blocks + asking heights, ms a frame (mean): walking 330 yd tilted 45 | 0.013 / 0.021 | 0.025 / 0.027 |
| ... walking 40 yd tilted 20 | 0.048 / 0.028 | 0.049 / 0.029 |
| ... flying 10 yd a frame | 0.43 / 0.39 | 0.52 / 0.41 |
| cursor's ground point, ms (first ask median / worst; asked again median) | 0.73 / 10.4; 0.48 (Stormwind) | 1.27 / 5.1; 0.39 |

Walking the camera and your arrow ask at most 2 blocks a frame and decode one again at most once in 300 frames; Lua
ms a frame were the same within the runs' noise (two runs each, 4.3-10.4 ms medians both). `tools/sandbox/test_blockbuild.py`
(running 20 yd a frame, three laps round the same blocks, four runs each): busy frames' median 6.8-7.8 ms before,
7.8-8.4 after; the heights' re-decoding is 0.2 ms a frame of it on average (blocks under you come back each lap,
more than 16; with `HOLD` 400 the difference goes, 7.3-7.5 ms, and so does the memory saved). Garbage the same (busy
median 29 KB, the palette's colour tables kept in `pool.rest.pal.spare`). Drawn: the same, texture for texture
(both tests' dumps against the code before), every block triangle drawn made from a full decode's corners and
colours (7.7 million checked), every height on a 4-yd grid over both cities exactly a full decode's (120,601 points,
in rows and shuffled), cursor picks identical. In the game the saving is memory (Lua 5.1 keeps about the same 16
bytes a number as 5.4) and the collector's work over it.

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
- Lower `BUILD_LIMIT` (1,500 triangles of new blocks per frame) to spread the hitch when new blocks appear:
  measured in the perf round's A2 (below), 500 halves the time a frame spends making blocks but leaves blocks flat
  on the canvas for up to 4 frames running fast, and the worst frames are not block frames; kept at 1,500.
- Flat arrays instead of a table per triangle: estimated 1-2 ms of Lua per frame, a large refactor.
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
and walking. `test_choice.py` (`CHOICE_PASS=calls`, `GPS3D_LUA=<file>`): a path of walking, panning, turning,
tilting and zooming at four places, Lua ms, the choice's own ms, C calls and garbage per segment.
`test_blockbuild.py` (`MEASURE=1`, `BB_PASS=calls`, `GPS3D_LUA=<file>`): running 20 yd a frame round Stormwind,
garbage, Lua ms, the time making blocks and blocks waiting per frame. In game:
`/gps3d probe` (TESTING.md section 15) measures frame time, Lua ms, textures and calls at six budgets in one go; `/gps3d test` prints render ms; compare `/gps3d detail off`, `/gps3d buildings 2000`.

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

