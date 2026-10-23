# Proof of concept: the game's own buildings in GPS3D (branch `poc-models`, not for release yet)

Experiments of 2026-10-22/23, one commit on top of `main`. What the branch does now:

- **The game's own buildings are the default** in the 3D view (`prototypes/GPS3D/PocModels.lua`); the old jagged
  building blocks are off ("Simple buildings (old)" in the settings, `/gps3d detail` switches them back on).
- **Data**: one load-on-demand addon per city. Only Stormwind's Trade District so far:
  `prototypes/GPS3D_City_Stormwind/` (8.8 MB), loaded when the view comes within 600 yd of it. Everywhere else
  there are no buildings until the pipeline below is run for the rest of the world.
- **Drawing** (GPS3D.lua's triangle path, through `ns.ExtraMeshes`): whole buildings, biggest on screen first, within
  a parts budget that follows the frame time (about 10 ms by default); facing groups that face away are skipped;
  wall rectangles are one texture with 4 corners (a 4-corner part crossing the near plane is not drawn yet).
- **Settings**: The game's buildings (on), Building parts per frame (8,000), Time for the 3D view (10 ms),
  Smallest building part (0). Slash: `/gps3d poc city on|off`, `budget <n>`, `target <ms>`, `min <sq yd>`.

## Measurements (sandbox only; the game was down)

`GATES-perf1.md` has the latest round and its numbers against the version before; the other `GATES-*.md` files
are the earlier steps in order: `GATES.md` (simplified models), `GATES-perbuilding.md` (one house simplified:
it does not pay), `GATES-gamemodels.md` (the game's own triangles), `GATES-distance.md` (size filter and sliders),
`GATES-pieces.md` (whole pieces), `GATES-buildings.md` (whole buildings, back sides), `GATES-perf1.md`.
Still to check in the game: `/gps3d probe` (cost of a texture and a call, the fold of a 4-corner texture,
OffScreenFrame snapshots).

## Making the data (offline, from the game's files)

The scripts here ran in a session scratch folder; they expect these inputs next to them:

1. Export: MapExplorer's reader on Morten's PC (`tools/gps_poc_export.ts` in ClassicWowMapExplorer, not in this
   repo) writes `raw/<city>.json` and the textures; `load.py` reads them.
2. Hidden parts: `pb_vis.py` (145 directions, 3,072 px, the canals' water at 95 yd as an occluder; `pb_vis_all_w.sh`
   runs the 9 tiles of the export square), with `pb_vis.html`.
3. Pieces and the 10-yd cut: `pb_city.py` (with `RANK=value`); buildings: `pb_buildings.py`.
4. The addon data: `pb_city2.py <out addon dir> <name>` (facing groups, 4-corner parts from `pb_quads.py`, the
   compact string layout documented in its header).
5. Checks: `decode_check.py`, `adapt_check.py`, `smoke7.py`, `mem7.py`, `loadtime_city.lua` (Lua 5.1),
   `../../tools/sandbox/perf_poc7.py` and `scn_poccity.py`.

The older scripts (`simplify*.py`, `texture_transfer*.py`, `to_lua.py`, `pb_shell.py` ... and
`tools/sandbox/scn_poc*.py`, `perf_poc*.py` up to 6) belong to the earlier steps; some refer to test data that is
no longer in the branch (`PocData.lua`, `PocCity.lua`).
