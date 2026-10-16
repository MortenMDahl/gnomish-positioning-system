# GPS3D performance notes

Kept for a later round of performance work. Everything here was measured in the browser sandbox
(`tools/sandbox`, native Lua 5.4 + a simulated WoW UI), not in the game: call counts are exact, milliseconds
are noisy (about ±20 %) and say nothing certain about the real client, where the Lua-to-C calls
(`SetVertexOffset`, `SetDrawLayer`, `SetParent`, `Show`/`Hide`, `SetTexture`...) are expected to dominate.

## Applied (2026-10-14, the "light" set, 7 changes)

From a review by a separate agent; the applied change as a diff against the previous file:
`tools/sandbox/perf/light.diff`.

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
