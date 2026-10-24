# Proof of concept S1: building shells with baked faces (branch `poc-shells`, from `poc-models`; not for release)

The plan of the 2026-10-23 redesign (sparring with a Fable agent): every building a small closed shell built offline
from the game's own model, each face a picture of the real building rendered onto it, several levels of detail. The
shell is always drawn whole (nothing see-through); the detail lives in the pictures. Measured results: `GATES.md`.

## What is in the branch

- `prototypes/GPS3D/Shells.lua`: draws the shells (through `ns.ExtraMeshes`, GPS3D.lua's triangle path). Every unit
  in view is drawn whole; since 2026-10-24 (S1d) by five levels of detail by distance (yd from the camera to the
  unit's near side, 15 % hysteresis), each level a start distance and a baked set (shape and picture density) chosen
  on the settings page (*Shells level N from / detail*, *Defaults*) or `/gps3d shells lod [reset | <level> <from yd>
  <set>]`; `set <n>` draws one set everywhere. Sets decoded when first needed (6 ms a frame at most), forgotten after
  30 s unused. `/gps3d shells on|off`, `floor on|off` (the city's floor picture, below). Old blocks give way inside
  the city box (`ns.PocCovers`).
- `prototypes/GPS3D/GPS3D.lua`: 16 bucket frames (1,024 buckets, was 8 / 512); with shells in view the ground keeps
  the first 256 and the shells take the rest, ordered by each face's horizontal distance from the camera (log-spaced),
  `ns.shellRange`; `/gps3d shells`.
- `prototypes/GPS3D_City_Stormwind/Shells_Stormwind.lua`: the data (8.7 MB since S1d: 9 baked sets the levels
  choose from, made by `sh_tolua_sets.py`; 2.1 MB for one set per level), the ground cells under the shells' tops
  (`floor`) and the floor picture's box (`floorImage`).
  The pictures are not in the repository (`.gitignore`): 45 pages `Shells\S<set>_<page>.jpg` (51 MB of JPEG) and
  `Shells\Floor.jpg`; the sandbox has copies (`tools/sandbox/site/shells/`); the game would need them as BLP (DXT1).
- `prototypes/GPS3D/Data/World_*.lua`, `Lod_*.lua`: the ground raised to the cities' floors (S1d, below).
- `tools/sandbox/`: `perf_shells.py`, `order_shells.py` (draw-order check), `scn_shells.py` (page shots),
  `smoke_shells.py`; `index.src.html` loads `shells/*.jpg`.

## Next

`NEXT.md`: what to do after the in-game test (getting the shells into the game, what `/gps3d probe stormwind` must
answer and what each answer decides, the speed-ups in order, what was measured negative), written 2026-10-24.

## Making the data (scripts here; inputs from the poc-models export, see testing/2026-10-22-poc-models)

`sh_prep.py` (the visible game triangles per unit) -> `sh_all3.sh`: for each level `sh_build3.py` (the district as one
coverage: owners, regions, simplified borders, faces), `sh_vis.py` (faces never seen dropped), then `sh_bakeprep.py`,
`sh_bake.py` + `sh_bake.html`, `sh_fill.py`, `sh_tolua.py` (`VAR`, `PACK`, `LEVELS`: see `sh_all3.sh`). Checks: `sh_fit3.py`, `sh_cover.py`, `sh_holes.py`,
`sh_tview.py` (z-buffer renders against the game). `sh_build.py` / `sh_build2.py` are the first build (one shell per
piece-based unit), kept for the record: its shells overlapped and could not be ordered.

## Sharper near buildings (2026-10-24, `GATES.md` S1b)

Sharpness is the pictures' pixels per yard against the screen's: `tools/sandbox/sharp_shells.py` measures, per pixel,
how many screen pixels one picture pixel covers (magnification). Before: 4.45 at 90 yd, 3.29 at 200 yd (median of the
buildings' pixels), so blurred. The frame time does not depend on the pictures, only on the faces; the data grows with
the square of the density. So level 0 (the finest shells, 21 M px of pictures, used for 5 % of the pixels at 90 yd) was
dropped and its picture budget given to levels 1-3, at 5 / 4 / 2.5 px a yard (were 2 / 2 / 1), the thresholds moved to
10 / 5.5 so each level serves the densities its pictures can, and the pages packed by place (`PACK=hilbert`).

| | Before | After |
|---|---|---|
| Magnification, median: 45 / 90 / 200 / 420 yd | 6.84 / 4.45 / 3.29 / 1.68 | 4.05 / 1.94 / 1.36 / 0.67 |
| Lua ms turning / C calls: 45 yd | 15-16 / 24,275 | 8.8 / 16,631 |
| 90 yd | 9.7-11.2 / 17,836 | 7.0-7.9 / 13,160 |
| 200 / 420 / 2,000 yd | same work (calls within 0.3 %) | |
| Pictures (DXT1 estimate) | 12 pages, 33.6 MB | 20 pages, 56 MB |
| Lua data | 4.4 MB | 2.1 MB |
| Pages one view draws from | 1-11 | 1-15 |

Costs: data +67 %; level 1 instead of 0 up close, so buildings are a little fatter (5,166 yd2 of shell top beyond the
game's footprint, 2,879 with level 0). Up close (45 yd) still soft (magnification 4): sharp there needs about 10 px a yard
(4x the data), or a different source of detail (the game's own textures tiled over the picture, untested).
Variants estimated: densities x1.5 / x2 keeping level 0: 61.5 / 95 MB, 90 yd at 2.97 / 2.22 (`sh_dataest.py`).

## The city's ground, levels of detail, mountains, ghosts (2026-10-24, `GATES.md` S1d)

- **The city's floor** ("it looks like all the buildings are flying"): the ground grid's heights raised to the
  buildings' floor, the way mountains are made, instead of drawing more: `scripts/build_city_floor.py` takes the
  20th percentile of the 1-yd building raster round each grid point (raise 3-120 yd, never lower, small openings
  closed), for every map (map 0: 4,901 points in 207 tiles; all maps in `World_*.lua`), then
  `scripts/build_terrain_lod.py` rebuilds the ground's levels of detail with the error under the shells weighted
  0.15 (`UNDER_SHELLS`), since the shells hide it.
- **Mountains** ("the buildings are visible through mountains"): with shells in view everything, ground included, is
  ordered by horizontal distance from the camera (log buckets); the ground under the shells' tops (the city's floor,
  `floor` cells) is pushed 25 yd + 0.6 x its size behind, so it never covers a shell standing on it. Shell over
  nearer real ground: 0.03-1.05 % of pixels before, 0-0.003 % after (`tools/sandbox/order_all.py`).
- **Ghosts** ("dual textures"): the minimap image has the buildings drawn from above, so its copy showed on the
  ground beside and under the shells (a bridge on the water under it). `sh_floorimg.py` makes the city's own floor
  picture (2,048 px over the 548-yd box, 3.7 px a yard): the low streets from the bake, the minimap away from
  buildings, and under buildings and raised streets (more than 2.5 yd over the raised ground: bridges, wall-walks)
  the nearest such pixel. GPS3D.lua puts it on the sharp ground tiles' triangles inside the box while the shells
  are on (`ns.floorImage`; `/gps3d shells floor off` shows the minimap to compare).
- **Levels of detail**: five, by distance, each a start and a set (above). Defaults: 0 yd set 3 (0.75-yd shape,
  5 px/yd), 70 yd set 5, 125 yd set 7, 300 yd set 7, 580 yd set 9 (whole blocks).
- Cost: the city's floor is now drawn where it shows, more ground triangles near the camera (NEXT.md section 2.1
  would take them off again).

## Kill criteria (sandbox)

| Criterion | Result |
|---|---|
| Fit: IoU < 0.85 for > 15 % of units | Level 0: 6.9 % (median 0.947). Coarser levels looser (17 / 28 / 66 %), used further away |
| Visible ordering errors between neighbours | 0.05-0.20 % of shell pixels (after the coverage rebuild; 12-38 % before) |
| Render > 12 ms at 200 yd | 5.6-5.7 ms (old blocks 5.3-5.9); finer levels 9.7-9.8 |
| Morten: 200 / 420 yd worse than old blocks | waiting for Morten |

## Open problems

- Data: the pictures for this one 520 x 520 yd square are 66 M px since 2026-10-24 (about 56 MB as DXT1 BLP; 37 M px and
  34 MB before the sharper pictures); all of Stormwind
  would be several times that. The plan assumed about 22 MB for every city. Ways down: level 0 at 2 px/yd (-11 M px),
  the game's own tiled textures on level 0 instead of pictures, fewer pictures for small faces.
- Sharpness: better since 2026-10-24 (above), still soft closer than about 60 yd.
- Eaves count as footprint (soffits were removed by the visibility pass), so buildings are a little fat; bridges are
  solid to the water; walls extended below the real geometry show stretched pictures; level changes pop.
- Only this square has data (all buildings: `ALL_BUILDINGS.md`); the pictures as BLP and everything in the game are untested.
