# Gates for J2, buildings close up

Measured with `tools/sandbox/test_blocks.py` (native Lua 5.4 + the sandbox engine; `MEASURE=1` prints the
measurements only; `J2_GPS3D=<file>` loads the baseline 8131b6d's GPS3D.lua for the "before" runs). Views:
Orgrimmar's Valley of Strength (1630, -4380) and Stormwind's Trade District (-8830, 640), Free camera,
40/80/150/300 yd, straight down and tilted 45 degrees, simplified building shapes (the default). "In view" =
within 1,000 yd of the view's centre and the block's box (its square, its lowest and highest vertex, 40 px round
the canvas) reaching into the view, counted by the test on its own; "raised" = the block's triangles are drawn
this frame.

8 of 8 gates met (G1 with a partial ABANDON for the two views that cannot fit, see below).

- [x] G1 Share of blocks in view drawn raised, all 16 views: before / after (target 100 %).
  Check: test_blocks.py table, checks 1 and 2. Expected: 100 % in every view.
  EVIDENCE: before 6-67 % (Orgrimmar down 67/38/24/13 %, tilted 31/25/17/11 %; Stormwind down 33/18/18/37 %,
  tilted 10/7/6/11 %, at 40/80/150/300 yd); after 100 % in the 14 views where every block fits the budget at the
  far level. The other two (tilted 300 yd: 4,492 and 5,897 triangles even with all at the far level): 88 % and
  66 % (before 11 % and 11 %), the budget used (3,983 and 3,961 tris) and those left flat the furthest from the
  camera (furthest raised 667 / 541 yd, nearest flat 678 / 541 yd). Checks 1 and 2 PASS.
  ABANDON (partly): 100 % at tilted 300 yd: not possible within the 4,000 budget at the coarsest level the data
  has; raising the budget is a separate choice (frame time).
- [x] G2 Building triangles <= the budget (4,000) in every view.
  Check: test_blocks.py check 3. EVIDENCE: most 3,992 (before 4,000). PASS.
- [x] G3 Zooming 2 % a frame from 600 yd to 15 yd, both places, straight down and tilted: blocks in view that
  appear raised, go flat or change level per frame, before / after: not worse, ideally clearly better.
  Check: test_blocks.py zoom table, check 5. EVIDENCE: over 183 frames each (Orgrimmar down, tilted, Stormwind
  down, tilted): before 58, 100, 116, 91 events (worst frame 17); after 25, 43, 35, 56 (worst frame 4). Flat blocks
  in view per frame before 16.3 / 32.1 / 21.8 / 45.4, after 1.1 / 6.5 / 5.2 / 13.8, and 0 flat in frames where all
  fit (check 6). PASS.
- [x] G4 Mage Quarter looks whole after the change (scn_mage.py through run_page.py, before and after, looked at).
  EVIDENCE: shots/m_before_*.png and m_after_*.png. Tilted 330 yd: before 24 blocks raised, mostly coarse, the
  tower walls with purple minimap streaks stretched down them and the buildings round the quarter flat; after 78
  blocks raised, all at the far level, the ring of walls solid purple and continuous, no streaks, the quarter round
  it raised too (more faceted). Top-down: the ring whole in both; after, the neighbouring spires show as grey
  facets. Check 8 (no minimap stretched down coarse walls) PASS: 0 (before 406 of 1,069 coarse steep triangles).
- [x] G5 Frame time at those views not worse than +15 % (lowest of 3 medians of 21 frames per view, same script).
  EVIDENCE: two interleaved runs each, best of the two per view: sum of the 16 views 66.6 ms before, 64.7 ms after
  (-3 %); per view 0.82x to 1.10x (worst Stormwind tilted 300 yd 4.29 -> 4.71 ms, +10 %).
- [x] G6 Per-frame cap of 1,500 new block triangles kept; decoded-block cache 400 kept; memory reported.
  Check: test_blocks.py check 7. EVIDENCE: BUILD_LIMIT and GEO_LIMIT unchanged and applied as before (one block
  over the cap allowed alone). Zooming: most 1,269 new triangles in a frame, 0 frames over 1,500 with more than one
  new block (before: most 1,988, a single block). At most 87 blocks in view per frame (< 400). Lua memory after
  the 16 views 103 MB, +28 MB over the start (before 102 MB, +22 MB): about +6 MB for the more, smaller meshes.
- [x] G7 New checks fail on the old code (baseline run of test_blocks.py) and pass on the new.
  EVIDENCE: baseline 3 of 8 (FAIL: all raised; nearest raised when over; fewer pops; none flat where all fit;
  no stretched walls); fix 8 of 8.
- [x] G8 Suites pass: test_world, test_models, test_settings, test_luac (RenderWorld upvalues <= 58, main chunk
  locals <= 197). EVIDENCE: test_world 60 of 60, test_models 50 of 50 (its "switched off" check now compares the
  blocks with the view without Models.lua and the ground with the saved copy from before the models, since the
  block choice changed), test_settings 46/46, test_luac 3 of 3 (GPS3D.lua main chunk 196/200, most upvalues 45/60).
