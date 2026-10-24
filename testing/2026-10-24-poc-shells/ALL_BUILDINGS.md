# All buildings in the game as shells: plan, sizes, and phase 1 done (2026-10-24)

Morten asked for every building in the game as shells, not just Stormwind's Trade District. This note says what
that takes, what it would weigh, and the order to do it in. Every size here is an estimate from the one square
that exists (labelled as such); nothing of the world beyond that square has been built yet.

## What one square costs today (measured, sandbox data)

The square: 520 x 520 yd of Stormwind (the Trade District and parts round it), 763 units, 71 blocks of 66.7 yd.

| Part | Size |
|---|---|
| Geometry (Lua), one set per level (levels 1-3 + blocks) | 2.1 MB |
| Geometry (Lua), the 9 sets the sliders choose from | 8.7 MB (the blocks alone: 74 KB) |
| Pictures, one set per level (5 / 4 / 2.5 / 0.75 px a yard) | 66 M px, about 56 MB as DXT1 BLP with mipmaps (not made yet) |
| Pictures, the blocks alone (0.75 px a yard) | 0.6 M px, about 0.5 MB |
| Pictures, the 9 sets | 45 pages, 56 MB as JPEG (the sandbox's) |

## How much game there is (measured from the building blocks' 1-yd rasters)

Built footprint (raster at least 3 yd above the ground grid), all 15 maps, 859 tiles with buildings: 12.1 M
raster cells. The square: about 104,000. So the whole game holds about **116 squares' worth** of buildings (an
estimate: Stormwind is denser than a village, where walls per footprint are more, so the real figure can be
somewhat higher).

## What the whole game would weigh (estimates, x 116)

| Tier | Geometry (Lua) | Pictures (DXT1) | Verdict |
|---|---|---|---|
| Today's square quality everywhere (levels 1-3 + blocks) | about 240 MB | about 6.5 GB | impossible for an addon |
| Coarse units everywhere (level 3, 3-yd shape, 1 px a yard) + blocks | about 35 MB | about 170 MB | too big as a default |
| Blocks everywhere (66.7-yd shells, 0.75 px a yard) | about 9 MB | about 45-60 MB | feasible: the old jagged blocks are 46.7 MB of Lua today |
| Plus finer sets in the capitals' cores only | + 2-9 MB per square | + 5-56 MB per square | choose by a size budget |

So picture-baked shells cannot carry the whole game at the near quality; they can carry it at the far (block)
quality, with finer sets kept for a few places.

## Plan, in order

1. **Export the game's geometry for every tile with buildings** (on Morten's PC: MapExplorer's reader,
   `tools/gps_poc_export.ts` in the ClassicWowMapExplorer checkout, as done for the Trade District on
   2026-10-22; the export format is what `testing/2026-10-22-poc-models/load.py` reads). One run per map; the
   game being down does not matter (it reads the game files). Needed before anything else: the cloud has only
   the one square's triangles.
2. **Make the pipeline run per tile and in batches** (`testing/2026-10-24-poc-shells/sh_all3.sh` today runs one
   square by hand): visibility (`pb_vis.py`, WebGL in headless Chromium), units (`pb_city.py`, `pb_buildings.py`),
   the coverage build (`sh_build3.py`), baking (`sh_bake.py`) and the data addon (`sh_tolua_sets.py`), with one
   data addon per continent band like `GPS3D_EK1..4`, loaded on demand by `OnDemand.lua` (it already loads by
   tile), and `Shells.lua` taking any number of cities and tiles (today one box). Expect hours of compute for
   the whole game.
3. **Phase 1: block shells everywhere** (level 4 only): replaces the old jagged building blocks, about the same
   download, much better look far out. The ground's city floor (`scripts/build_city_floor.py`) is already done
   for every map.
4. **Phase 2: finer sets in the capitals** (Stormwind, Orgrimmar, Ironforge's outside, Thunder Bluff, Darnassus,
   the Undercity's ruins), by a size budget Morten sets: with the sliders he can see which sets are worth their
   size.
5. **Phase 3 (research): the game's own textures for near views.** Shell faces textured with the game's own
   tiled textures (by FileDataID, already in the client: no data to ship), the baked pictures only for far views.
   That is the only way found so far to be sharp up close everywhere without gigabytes of pictures. Untested.

## Decisions needed from Morten

- A size budget for the 3D data (download and memory), so phase 2's tiers can be set. Phase 1 adds 4.6 MB Lua and
  about 39 MB of DXT1 pictures.
- (Done: the geometry export runs on his PC from the Cowork session, no browser needed.)

## Phase 1 done (S1e, 2026-10-24): whole-block shells for every building on both continents

Measured, not estimated:

- **Export (step 1)**, on Morten's PC, with no browser: `scripts/export_tiles_node.ts` on MapExplorer's reader in the
  Cowork VM against the WoW folder. Both continents took 58 s and produced 1.2 GB raw (200 MB + 187 MB gzipped).
  That is 1,724 tiles visited, 799 with building triangles, 3,783 building placements and 2,816 textures (at most
  256 px).
- **Per tile (step 2), in the cloud:** `ab_tile.py`, two at a time, about 50 minutes for all 799 tiles. A busy tile
  (Stormwind's south-east, 200 k triangles) takes about 20 s.
  1. The tile's building triangles. Triangles wholly 2 yd or more under the drawn ground are dropped (cellars,
     caves' tunnels). On map 0, the Trade District square is dropped too, because it has its own finer shells; its
     edge blocks get the part outside the square.
  2. `sh_build3.py 4`: the 66.7-yd blocks as one coverage, every face kept.
  3. `sh_bakeprep.py 4 0.75`, `sh_bake.py`, `sh_fill.py`.

  Results: 751 tiles have shells. Of the other 48, 45 have nothing above the ground (caves, cellars) and 3 hold
  nothing but Orgrimmar's city model (below).
- **Data (step 3):** `ab_collect.py` writes one load-on-demand addon per continent, `GPS3D_Shells0` and
  `GPS3D_Shells1`. Pictures are repacked across tiles in Hilbert order.

  | | Eastern Kingdoms | Kalimdor | Both |
  |---|---|---|---|
  | Tiles | 342 | 409 | 751 (plus 3 Orgrimmar tiles left out) |
  | Blocks | 3,397 | 3,346 | 6,743 |
  | Faces | 54,259 | 52,197 | 106,456 |
  | Lua | 2.3 MB | 2.3 MB | 4.6 MB (the old blocks: 46.7 MB) |
  | Pages (2,048 px) | 6 (6.1 MB JPEG) | 8 (8.0 MB JPEG) | 14 pages, 14 MB JPEG, about 39 MB as DXT1 |

  That is far under the 9 MB + 45-60 MB estimated above. The pictures are 0.75 px a yard; a tile's block faces need
  little picture.
- **In the addon** (`Shells.lua`, `TilesFrame`):
  - Drawn: blocks within 1,500 yd of the camera, in view, nearest first, while their faces fit the budget (5,000 faces
    by default; slider *Whole-block shells budget*, `/gps3d shells tiles <n>`, 0 = none).
  - The old simplified blocks give way in every 66.7-yd square whose shell was drawn last frame. Beyond the budget or
    the reach, the old blocks are still there.
- **Look** (sandbox shots `cmp_*_t.png`):
  - The Undercity's ruins are far better: buildings instead of a blur.
  - Goldshire, Thunder Bluff and the villages show their real walls and roofs.
  - Stormwind's main gate is whole: the old blocks drew its outer half a second time, and a grey wall stood where
    the Trade District's export stopped. Both are gone.
  - Close up, the pictures are soft (0.75 px a yard).
- **Orgrimmar is left to the old blocks.** Its city is one building model whose cliffs overhang the streets. A 2.5D
  shell takes the highest surface over each spot, so it roofed the city over with rock, grey where the bake found
  nothing (`ab_tile.py` `SKIP_WMO`).

  Fixing this needs either shells that can have overhangs, or the cliff left out of the model and only its
  buildings kept. Both are research. Ironforge's gate has one odd block.

## Next for all buildings
- Phase 2: finer unit sets in the capitals (Undercity, Thunder Bluff, Stormwind's other districts), by the size budget.
- Orgrimmar: see above.
- A coarser unit set between set 8 (5,501 faces) and the blocks, so far views of a capital can keep individual
  buildings within the face budget.
