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
