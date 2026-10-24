# Proof of concept S1: building shells with baked faces (branch `poc-shells`, from `poc-models`; not for release)

The plan of the 2026-10-23 redesign (sparring with a Fable agent): every building a small closed shell built offline
from the game's own model, each face a picture of the real building rendered onto it, several levels of detail. The
shell is always drawn whole (nothing see-through); the detail lives in the pictures. Measured results: `GATES.md`.

## What is in the branch

- `prototypes/GPS3D/Shells.lua`: draws the shells (through `ns.ExtraMeshes`, GPS3D.lua's triangle path). Every unit
  in view is drawn whole at the level its size on screen asks for (`S.PX` = 14 / 7 / 4.5 px a yard at its near
  side; whole 66.7-yd blocks under 1.2), levels decoded when first needed (6 ms a frame at most), forgotten after
  30 s unused. `/gps3d shells on|off`, `level <0-4>` (fixed), `px <a> <b> <c> [block]`. Old blocks give way inside
  the city box (`ns.PocCovers`). Settings: *Building shells*.
- `prototypes/GPS3D/GPS3D.lua`: 16 bucket frames (1,024 buckets, was 8 / 512); with shells in view the ground keeps
  the first 256 and the shells take the rest, ordered by each face's horizontal distance from the camera (log-spaced),
  `ns.shellRange`; `/gps3d shells`.
- `prototypes/GPS3D_City_Stormwind/Shells_Stormwind.lua`: the data (4.4 MB; replaces the 8.8 MB of game triangles).
  The pictures are not in the repository: the sandbox has JPEG copies (`tools/sandbox/site/shells/`, made by
  `sh_tolua.py`); the game would need them as BLP (DXT1) in `GPS3D_City_Stormwind\Shells\L<level>_<page>`, not made yet.
- `tools/sandbox/`: `perf_shells.py`, `order_shells.py` (draw-order check), `scn_shells.py` (page shots),
  `smoke_shells.py`; `index.src.html` loads `shells/*.jpg`.

## Making the data (scripts here; inputs from the poc-models export, see testing/2026-10-22-poc-models)

`sh_prep.py` (the visible game triangles per unit) -> `sh_all3.sh`: for each level `sh_build3.py` (the district as one
coverage: owners, regions, simplified borders, faces), `sh_vis.py` (faces never seen dropped), then `sh_bakeprep.py`,
`sh_bake.py` + `sh_bake.html`, `sh_fill.py`, `sh_tolua.py`. Checks: `sh_fit3.py`, `sh_cover.py`, `sh_holes.py`,
`sh_tview.py` (z-buffer renders against the game). `sh_build.py` / `sh_build2.py` are the first build (one shell per
piece-based unit), kept for the record: its shells overlapped and could not be ordered.

## Kill criteria (sandbox)

| Criterion | Result |
|---|---|
| Fit: IoU < 0.85 for > 15 % of units | Level 0: 6.9 % (median 0.947). Coarser levels looser (17 / 28 / 66 %), used further away |
| Visible ordering errors between neighbours | 0.05-0.20 % of shell pixels (after the coverage rebuild; 12-38 % before) |
| Render > 12 ms at 200 yd | 5.6-5.7 ms (old blocks 5.3-5.9); finer levels 9.7-9.8 |
| Morten: 200 / 420 yd worse than old blocks | waiting for Morten |

## Open problems

- Data: the pictures for this one 520 x 520 yd square are 37 M px (about 25-34 MB as DXT1 BLP); all of Stormwind
  would be several times that. The plan assumed about 22 MB for every city. Ways down: level 0 at 2 px/yd (-11 M px),
  the game's own tiled textures on level 0 instead of pictures, fewer pictures for small faces.
- Sharpness: at the default levels the near buildings use coarse levels (pictures at 1-2 px/yd), soft up close;
  the finer levels are sharp but cost 2.4x at 90 yd.
- Eaves count as footprint (soffits were removed by the visibility pass), so buildings are a little fat; bridges are
  solid to the water; walls extended below the real geometry show stretched pictures; level changes pop.
- Only this square has data; the pictures as BLP and everything in the game are untested.
