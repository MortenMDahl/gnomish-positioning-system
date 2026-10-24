# Gates: S1, closed building shells with baked faces, Trade District square (sandbox) (2026-10-24)

Request: "Yes" (start the first sandbox experiment of the shell plan of 2026-10-23). Kill criteria from the plan:
footprint fit (IoU) under 0.85 for more than 15 % of units; visible ordering errors between neighbours; Render over
12 ms at 200 yd; Morten judges the 200 / 420 yd shots worse than the old blocks.
All numbers: the sandbox (Lua 5.4 under lupa, the call-counting harness of perf_poc7), the game is down.

- [x] G1: shells for the whole export square, closed: every top edge meets a wall or a neighbour
  CHECK: sh_build3.py counts; sh_vis.py ID renders, 121 directions 20-90 degrees down, 3,072 px: share of pixels that see a back face (into a shell)
  EVIDENCE: coverage build (sh_build3.py): level 0 6,110 regions, 70,893 faces (61,872 seen from somewhere, kept); 1: 34,725 (31,083); 2: 14,438 (12,645); 3: 6,176 (5,501); 4 (66.7-yd blocks): 1,957 (1,806). Back-face pixels 0.014 / 0.011 / 0.008 / 0.006 / 0.005 % (levels 0-4). From straight above, ground the game covers and level 0 does not: 360 of 158,242 yd2 (0.2 %); level 3: 1.2 %
- [x] G2: footprint fit
  CHECK: sh_fit3.py: per unit of at least 150 yd2, IoU of its shell against the cells where its real geometry is highest from above (0.25 yd)
  EXPECT: under 15 % of units below 0.85
  EVIDENCE: level 0 (the near level): 233 units, median 0.947, 6.9 % under 0.85, 1.7 % under 0.7. Coarser levels, used further away: 1: 0.904 / 17.2 %; 2: 0.884 / 27.5 %; 3: 0.825 / 66.1 %
- [x] G3: baked faces
  CHECK: sh_bakeprep.py / sh_bake.py / sh_fill.py counts; pages and samples viewed
  EVIDENCE: every kept face has a picture (an orthographic render of the game's geometry within a slab round the face, the game's textures and the addon's shading): level 0 at 3 px/yd 39,446 pictures in 6 pages of 2,048 x 2,048 (20.9 M px used), 1 at 2 px/yd 2 pages (8.1 M), 2 at 2 px/yd 2 pages (6.2 M), 3 at 1 px/yd 1 page (1.6 M), 4 at 0.75 px/yd 1 page (0.6 M); 1-10 % of pictures had nothing in their slab (unit's mean colour). PNG 44 MB, JPEG for the sandbox 15.2 MB; as DXT1 BLP with mips about 25 MB packed tight, 33.6 MB as 12 full pages (estimate, unverified: no BLP made yet)
- [x] G4: drawn in the sandbox (Shells.lua through ns.ExtraMeshes), every unit, no budget, no Lua errors
  CHECK: smoke_shells.py, run_page.py shells
  EVIDENCE: 763 units + 71 blocks; e.g. close view 487 drawn (0 / 0 / 16 / 471 / 0 at levels 0-4), 0 waiting; far view the 71 blocks; no Lua errors in any run; data addon GPS3D_City_Stormwind loads on demand (4,403,010 bytes of Lua, was 8,824,933)
- [x] G5: draw order
  CHECK: order_shells.py: per canvas pixel, the face the depth buckets put on top against the face truly nearest (plane hit by the view ray), 0.3 yd tolerance
  EVIDENCE: first build (one shell per piece-based unit; footprints overlapped 44-52 %): 12-38 % of shell pixels wrong whatever the order (simulated keys). Rebuilt as one coverage (sh_build3.py) and ordered by each face's horizontal distance from the camera in buckets of their own above the ground (log-spaced, 768 of 1,024; GPS3D.lua BUCKET_FRAMES 8 -> 16): wrong 0.14 / 0.05 / 0.20 / 0.10 % (near / close / high / far), same bucket 0.0 / 0.04 / 0.46 / 0.01 %
- [x] G6: cost (Render's Lua ms turning, median of 40 frames, fresh game per setting, orbit at the streets' height, 2 runs)
  CHECK: TH=117.5 perf_shells.py
  EXPECT: 200 yd under 12 ms
  EVIDENCE: shells (levels at 14 / 7 / 4.5 px a yard, blocks under 1.2): near 8.4, 8.4; close 5.7, 5.6; high 10.1, 10.7; far 7.7, 7.6. Finer levels (6 / 4 / 3): 21.6, 19.9; 9.7, 9.8; 10.9, 9.8; 7.8, 7.8. Old blocks: 4.5, 4.3; 5.9, 5.3; 10.0, 9.8; 12.5, 12.6. C calls turning at close: shells 12,543, old blocks 15,221. (Orbit at the ground under the view instead: shells 10.0, 9.7 / 8.5, 8.2 / 9.6, 9.0 / 7.9, 7.5; old blocks 7.1, 6.9 / 5.1, 5.2 / 9.8, 9.1 / 15.4, 14.1)
- [x] G7: look: page shots at 90 / 200 / 420 / 2,000 yd, shells (default and finer levels) beside the old blocks
  EVIDENCE: shells_s1_sandbox.png (viewed; sent). Z-buffer renders of every level against the game's own models: scratchpad shtv_*_pair.png (viewed)
- [x] G8: kill criteria evaluated; committed and pushed; the sandbox artifact runs it
  EVIDENCE: in the report and README.md; commit and artifact version in the report

# S1b: sharper near buildings (shells S1) + performance (2026-10-24)

Request: "make the near buildings sharper and evaluate performance". Sandbox only (the game is down).
Magnification = screen px per picture px along the picture's most stretched axis (1 = as sharp as the screen).

- [x] S1b-G1: baseline sharpness measured at the views (closeup 45, near 90, close 200, high 420, far 2,000 yd)
  CHECK: sharp_shells.py (PPY=3,2,2,1,0.75 PX="14 7 4.5 1.2", the data before)
  EVIDENCE: building pixels, median magnification / share over 3x: closeup 6.84 / 99.3 %, near 4.45 / 95.5 %, close 3.29 / 61.2 %, high 1.68 / 0 %, far 0.46 / 0 %
- [x] S1b-G2: near buildings sharper
  CHECK: sharp_shells.py on variant E (no level 0; 5 / 4 / 2.5 / 0.75 px a yard; PX 14 10 5.5 1.2)
  EXPECT: near and close: median at most half of baseline, share over 3x at most half
  EVIDENCE: closeup 4.05 / 71.1 %, near 1.94 / 8.7 % (half of 4.45 = 2.23; half of 95.5 % = 47.8 %), close 1.36 / 0.0 % (half of 3.29 = 1.65), high 0.67 / 0 %, far 0.46 / 0 %. Closeup (45 yd) improves less and is still soft.
- [x] S1b-G3: performance (Render's Lua ms turning, median of 40 frames, 3 runs alternating; C calls a frame)
  CHECK: TH=117.5 perf_shells.py, base data with PX 14 7 4.5 against E
  EXPECT: close under 12 ms; no view over 1.25x baseline
  EVIDENCE: closeup base 14.9, 16.1 ms / 24,275 calls -> E 8.8, 8.8 / 16,631; near 11.2, 9.7, 9.9 / 17,836 -> 7.9, 7.9, 7.0 / 13,160; close 6.5, 6.8, 6.8 / 12,556 -> 6.8, 7.1, 6.3 / 12,138; high 14.1, 14.5, 12.8 / 25,062 -> 13.2, 13.0, 11.7 / 25,060; far 12.5, 11.6, 9.9 / 20,218 -> 9.5, 9.1, 8.8 / 20,218 (same calls: same work, ms noise of this machine about +-15 %)
- [x] S1b-G4: data and texture memory
  CHECK: sh_bakeprep / sh_tolua output; pages referenced per view (sharp_shells.py)
  EVIDENCE: pictures 37.4 -> 66.4 M px used, pages 12 -> 20 (2,048^2), DXT1+mips estimate 33.6 -> 56 MB (no BLP made), sandbox JPEG 15.2 -> 23.9 MB; Lua data 4,403,010 -> 2,065,254 bytes (no level-0 strings). Pages a view draws from: closeup 11 -> 15, near 10 -> 11, close 3 -> 2, high 2 -> 3, far 1 -> 1. Other variants (estimates, sh_dataest.py + sharp_shells.py): densities x1.5 keeping level 0: 61.5 MB, near 2.97; x2 keeping level 0: 95 MB, near 2.22
- [x] S1b-G5: shots before / after at 45, 90, 200 yd, viewed
  EVIDENCE: /mnt/user-data/outputs/shells_sharper_before_after.png, shots/sharp_crop_near.png (viewed: roof tiles, stone courses and windows visible after, a smear before)
- [x] S1b-G6: nothing broken
  EVIDENCE: order_shells.py wrong 0.01 / 0.10 / 0.20 / 0.10 % (near / close / high / far); smoke_shells.py all views drawn, 0 waiting; `level 0` clamps to level 1 (243 units at level 1); coverage from above at level 1: 267 yd2 missing (0.2 %, level 0 had 360), 5,166 yd2 extra (level 0: 2,879: buildings slightly fatter); page load: only the CDN / Google Fonts requests fail (blocked here, as before)
- [x] S1b-G7: committed and pushed to poc-shells (MortenMDahl), sandbox artifact updated, README/GATES in testing/ updated
  EVIDENCE: commit 5862150

# S1c: notes for after the in-game test, no-brainer speed-ups, sandbox up to date (2026-10-24)

Request: "Take detailed notes of the things that should be done after we test in-game, and do the no-brainer stuff
now. After that, make sure the sandbox is up to date so I can check it out myself". No-brainer = no change to what
is drawn, no game needed to know it is right, measurable in the sandbox.

- [x] S1c-G1: detailed notes: testing/2026-10-24-poc-shells/NEXT.md (getting shells into the game, what the probe must answer and the decision rules, speed-ups 2.1-2.3 with where / gain / risks / tests, ship blockers, measured negatives, done this round)
- [x] S1c-G2: shell face middles at decode, `math.log` / `sr.kmin` once per frame
  EVIDENCE: with level hysteresis held at 1, every shell face's bucket and corners identical old vs new over 35 snapshots (83,828 faces; 5 views + turn / zoom / pan paths); Render close 6.4, 6.3, 6.4 -> 6.1, 6.1, 6.0 ms, near 7.7, 7.2, 7.7 -> 7.2, 7.3, 7.1, others within noise
- [x] S1c-G2b (found on the way): level hysteresis against the level wanted last (`u.want`), so a decode-budget fallback no longer sticks; deterministic run to run (two runs identical)
- ABANDON S1c-G3: Shells.lua block cull + Tidy over live units: S.Frame 0.85-0.95 -> 0.98-1.15 ms (+15 %, 3 runs alternating); reverted, listed in NEXT.md as measured negative
- ABANDON S1c-G4: cutting 4-corner faces at the near plane: the 5-corner case needs a design (NEXT.md 2.1); nothing reaches the canvas today (0 of 287-354 crossing quads at 45 / 25 / 15 yd), so it is no quality fix now, only a prerequisite of 2.1
- [x] S1c-G5: /gps3d probe part 4 one-call move (SetVertexOffset / SetPoint / AdjustPointsOffset per 1,000 calls, snapping)
  EVIDENCE: test_probe.py 35 of 35 (new check passes; the glide check, failing on this branch since the shells at 35 px and passing with shells off, now tracks a ground vertex)
- [x] S1c-G6: nothing else changed
  EVIDENCE: page shots closeup / near / close pixel-identical to before (max difference 0), also after the .jpg path change; perf_shells calls: closeup 16,631 -> 16,639, near 13,160 -> 13,146 (both from the hysteresis fix's level choice; identical with hysteresis held), close / high / far identical; test_luac 3 of 3; test_world 58 of 62 (the 4 known "blocks 0" failures); smoke_shells 4 views, 0 waiting; order_shells wrong 0.01 / 0.10 / 0.20 / 0.10 %
- [x] S1c-G7: committed + pushed (poc-shells, MortenMDahl), JPEG pages on Morten's PC, sandbox artifact republished and loading the new files
  EVIDENCE: commit 6aea0ba

# S1d: the city's ground, shells vs mountains, five levels of detail, ghosts, all buildings (2026-10-24)

Requests: "We do need to load the ground, or it looks like all the buildings are flying" (then: raise the ground's
heights "the way we do to raise mountains") / "the high level can remain even if we are zoomed a bit more out ... 5
levels of detail, with a range at which that detail shifts in, and how detailed it is at that level" / "the buildings
are visible through mountains now" / "please add all buildings in the game, not just SW" / "There also appears to be
some dual textures".

- [x] S1d-G1: terrain in front of shells hides them
  CHECK: tools/sandbox/order_all.py (per pixel: the nearest triangle, ground included, against the one drawn on top), FLOORCELLS=sh_floorcells.json
  EVIDENCE: shell over nearer real ground 0.03-1.05 % of pixels before (5 views + 3 mountain views, first run this round) -> now near / close / sw_s / sw_low / far 0.0 / 0.0 / 0.0 / 0.0 / 0.003 %; ground over nearer shell 0.0 / 0.0 / 0.049 / 0.0 / 0.002 %; shell over shell 0.07 / 0.087 / 0.145 / 0.019 / 0.002 % (unchanged). The city's floor poking up through a shell and drawn behind it (intended) 0.25-2.1 %.
- [x] S1d-G2: no flying: the ground raised to the buildings' floor
  CHECK: scripts/build_city_floor.py (all maps), scripts/build_terrain_lod.py check, page shots before / after
  EVIDENCE: map 0: 4,901 grid points raised in 207 tiles (mean 32.8 yd, at most 119.5: CAP 120); 15 maps' World_*.lua changed; build_terrain_lod check passes with the weights; shots of the square's south and south-east sides before / after viewed (canals and streets at the buildings' feet, no ground 40 yd below)
- [x] S1d-G3: five levels with sliders, live, defaults restorable
  CHECK: run_page.py shellsopts (the page's Options panel)
  EVIDENCE: rows "Shells level 1 detail", "level 2-5 from / detail", "Shells levels [Defaults]" present; moving level 2 from to 250 yd and level 1 detail to set 1: LodText "1) from 0 yd: set 1 ... 2) from 250 yd ..." and the close view's units at level 1 0 -> 176; Defaults back to 0/3, 70/5, 125/7, 300/7, 580/9. Slider labels wrap under the slider in the sandbox (shots/shellsopts_crop.png)
- [x] S1d-G4: performance measured
  CHECK: perf_shells.py VARS=shells, 5 views
  EVIDENCE: alternating run earlier this round, code before S1d -> S1d (same raised ground data): closeup 8.4, 9.3 -> 10.0, 9.8 ms / 16,639 -> 18,489 calls; near 7.2, 7.6 -> 10.9, 10.5 / 13,146 -> 18,654; close 6.4, 6.3 -> 7.7, 7.8 / 12,138 -> 15,184; high 13.1, 13.2 -> 15.2, 14.5 / 25,060 -> 26,165; far 9.6, 9.4 -> 9.1, 9.0 / 20,218 -> 18,948 (the floor ground now drawn). Final code and data, two runs: closeup 9.0, 8.9 / 14,223; near 12.3, 11.1 / 18,615; close 8.1, 8.1 / 14,698; high 17.5, 15.7 / 26,123; far 11.4, 9.6 / 19,095. (The closeup view's centre now sits on the raised floor, which puts its camera inside a building: not comparable with before. The floor picture adds no calls: closeup identical with it off.)
- [x] S1d-G5: all buildings in the game: plan, sizes, what runs on Morten's PC
  EVIDENCE: ALL_BUILDINGS.md (about 116 squares' worth of buildings, measured from the blocks' rasters; tiers from 240 MB + 6.5 GB down to blocks everywhere at about 9 MB + 45-60 MB; plan in 5 steps; the city floor already done for every map); the export must run on Morten's PC (the cloud has one square's triangles)
- [x] S1d-G6: nothing broken
  EVIDENCE: test_luac 3 of 3; test_world 58 of 62 (the 4 known); test_probe 35 of 35 (its call-count check now leaves out frames in which meshes were made, which the probe documents it does not count); test_terrain 3 of 5, the same 2 failing with the data before S1d (Hyjal far view mean 2.32 px both; zoom worst 9.24 -> 9.34 px); test_settings and test_choice fail identically with the code before S1d (the page list predates the poc branches; `c.key` API); smoke_shells 4 views drawn, 0 waiting; order_shells (fixed for meshes by set) wrong 0.09 / 0.20 / 0.21 / 0.09 % (near / close / high / far)
- [x] S1d-G8: no ghost of the buildings on the ground
  CHECK: run_page.py shellslook at the gate (3 views) and in the district (3 views), `/gps3d shells floor off` (minimap) against on
  EVIDENCE: shots/cmp_gateA/B/C.png, cmp_near/close/canal.png viewed: the blurred white copy of the gate's towers and bridge on the water and the blue roof smears between the houses are gone with the floor picture; the picture: 2,048 px over 548 yd (3.74 px/yd), low streets 19 %, refilled under buildings / raised streets 40 %, raised streets 6.6 %
- [x] S1d-G7: committed + pushed (poc-shells, MortenMDahl), pages on Morten's PC, sandbox republished
  EVIDENCE: poc-shells 3ff836d on GitHub (git ls-remote = local HEAD); 45 S*.jpg pages + Floor.jpg written to prototypes/GPS3D_City_Stormwind/Shells on Morten's PC; sandbox artifact versions 15-16: 45 S pages + FLOOR.jpg, L pages removed, Shells_Stormwind.lua 8,699,731 bytes, GPS3D.lua 157,484 bytes (= local)
