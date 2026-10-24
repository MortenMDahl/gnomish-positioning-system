# All buildings in the game as shells: plan and sizes (2026-10-24)

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

- A size budget for the 3D data (download and memory), so the tiers can be set.
- Running the geometry export on his PC (step 1); everything after it can run in the cloud.
