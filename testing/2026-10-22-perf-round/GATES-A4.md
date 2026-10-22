# GATES: step A4 of the perf round (2026-10-22): keep less per decoded block

The J9 review's A4: the cache of decoded building blocks (`geoCache`, `GEO_LIMIT` 400) kept every block's triangle
corners (`idx`), vertex colours (`vc`) and palette for its whole life, though once its mesh is made only the vertices
(`vx`, `vy`, `vh`) are needed every frame; `BlockHeight` read the corners again and kept an 8x8 triangle grid on
every block it was asked of. Drop them from the cache, decode them again from the string when asked, keep the
heights' decode for the few blocks under the camera. The review estimated -40-50 % of the cache's memory. Branch
`perf`, worktree `/home/claude/wt/P`, code before = `prototypes/GPS3D/GPS3D.lua` at 7d8f038 (`GPS3D_LUA=<file>`).

Scenario before and after: `tools/sandbox/test_blockmem.py` (new), Lua 5.4 through lupa, real data, 1280 x 800,
buildings 4,000. Per city (Stormwind round the Trade District, Mage Quarter, Cathedral and Old Town; Orgrimmar round
the Valley of Strength): a lap flown at 10 yd a frame following at 330 yd tilted 45 and again straight down, 300
frames walking 0.25 yd a frame (a run at 30 fps) tilted 45 and 300 at 40 yd tilted 20, the cursor's ground point at
24 places x 3 at 60 yd tilted 15 and 330 yd tilted 45, `GroundHeight` on a 4-yd grid over the city (rows, then
20,000 of the points shuffled). The cache's memory: every block it holds decoded afresh into new arrays, plus the
heights' lookups asked again for the blocks that had them, the difference of the collected Lua heap. Plus
`tools/sandbox/test_blockbuild.py` (A2's: running 20 yd a frame, three laps round Stormwind). Milliseconds:
processor time, GC stopped during the frame, without the engine's slow `SetParent`; this agent alone on the two cores,
runs sequential and alternating before/after.

## Gates

- [x] **G1 Reproduced and measured before.** Check: `GPS3D_LUA=<before> python3 test_blockmem.py`.
  EVIDENCE: Stormwind 306 blocks cached: 9,155 KB decoded (29.9 KB a block) + height grids on 51 of them 2,182 KB =
  11,337 KB; Orgrimmar 371 blocks: 10,580 + 1,277 (36 blocks) = 11,857 KB. Whole Lua heap after the scenario 77.3 /
  112.9 MB. Every cached block keeps corners, colours and palette (306 / 371).
- [x] **G2 Less kept, memory down by the review's 40-50 % or more.** Checks *memory* (per block, heights included,
  under 65 % of before) and *kept* (no cached block keeps corners, colours or a palette; at most `HOLD` 16 keep
  height lookups). EVIDENCE: Stormwind 11,337 -> 5,312 KB (-53 %; decoded 9,155 -> 3,031, heights 2,182 -> 2,281 for
  16 blocks), Orgrimmar 11,857 -> 4,901 KB (-59 %; 10,580 -> 3,527, 1,277 -> 1,374); whole heap 77.3 -> 72.3 MB and
  112.9 -> 92.3 MB; 0 blocks keep corners. Both fail on the code before (37.0 / 32.0 KB a block; 306 / 371 keep them).
- [x] **G3 Heights identical.** Check *heights* (every `GroundHeight` on the grid equal to a full decode's, the block
  decoded in the test and its triangles found the same way) and the dump comparison (sha1 of every height, before vs
  after). EVIDENCE: Stormwind 42,813 + 20,000 points (35,759 + 16,824 on buildings), Orgrimmar 37,788 + 20,000
  (27,251 + 14,384): 0 differ from the full decode; sha1 3721022edc59 / d7fdec195e95 / 7eb8f5ee572a / f936059c5451
  before and after. The shuffled order makes the 16-block hold forget all the time (16,338 and 12,328 decodes).
- [x] **G4 Nothing drawn differently.** Checks *corners* (`ns.BlockTris` equal to a full decode for every block
  round each city at all three levels, 1,170 blocks; every block triangle drawn every frame made from a full
  decode's corners and its image or wall colour, 7,719,547 checked) and the dumps (every texture shown, two views per
  city, and every cursor pick) against the code before; `test_blockbuild.py` with `BB_COMPARE` (A2's exact check
  every frame: 1.33 million triangles, 3.2 million corners on screen; three views). EVIDENCE: 0 wrong; views
  identical (Stormwind 3,518 and 2,537 textures, Orgrimmar 4,424 and 3,379; Trade District f84a99a553a1, Mage
  Quarter 0fcffaccba1d, Cathedral 1129c9e3c3d1 both); cursor picks identical (144 per city).
- [x] **G5 The new checks fail on the code before, and catch broken holds (mutations).** EVIDENCE: on the code
  before 2 of 7 pass (*memory* x2, *kept* x2 and *held* fail; *heights* and *corners* pass, as they must). Mutations:
  a held entry used without checking it is this block's (`if not e`) -> the addon errors in `BlockHeight` (test exits
  1); the grid's first cell starting one late (`at[0] = 2`) -> *heights* fails (107 and 138 points wrong).
- [x] **G6 No frame-time regression walking or running.** Check: `MEASURE=1 test_blockmem.py`, two runs each
  alternating. EVIDENCE: the work this step changed (making blocks + asking blocks' heights, mean ms a frame):
  walking 330 yd tilted 45 0.013 -> 0.025 (Stormwind), 0.021 -> 0.027 (Orgrimmar); 40 yd tilted 20 0.048 -> 0.049,
  0.028 -> 0.029; flying 10 yd a frame 0.43 -> 0.52, 0.39 -> 0.41. Walking asks at most 2 blocks a frame and decodes
  one at most once in 300 frames. Render's Lua ms medians, the code as committed (noise about +-1 ms run to run):
  walking 330 yd 4.89, 4.94 -> 4.77, 4.27 (Stormwind), 6.74, 6.89 -> 7.77, 5.53 (Orgrimmar); 40 yd 5.96, 5.64 ->
  6.69, 5.96 and 6.26, 5.50 -> 5.62, 4.75; flying 10 yd a frame 6.35, 6.65 -> 6.94, 6.21 and 8.49, 9.52 -> 10.39,
  8.94. Garbage while walking 3.0 KB a frame both.
- [ ] **G7 Flying 20 yd a frame round the same blocks no slower.** ABANDON: G7 the stress run of `test_blockbuild.py`
  (three laps over the same 2,600 yd, 600 yd a second) is slower: busy-frame median 7.36, 6.82, 7.40, 7.79 ms before
  against 7.95, 7.81, 7.82, 8.36 after (four runs each). Cause measured: the blocks under you come back each lap and
  are more than the 16 held, so their corners and grid are decoded again (0.36 ms a frame mean, p90 1.1 ms, against
  0.02 before in laps 2-3); with `HOLD` 400 the difference goes (7.50, 7.30 ms) and so does the memory saved. At game
  speeds (at most about 1.3 yd a frame) a block under you changes every 50 frames or more. Garbage unchanged (busy
  median 29 KB, laps 2-3 19 KB; the palette's colour tables are kept in `pool.rest.pal.spare` for that).
- [x] **G8 The cursor's ground point no worse at its worst, and identical.** `ScreenToTerrain` (a wheel step zooms
  toward it, a left-press grabs it) asked `BlockHeight` of up to 14 blocks per ray; with 16 held that re-decoded
  (worst 16.9 ms with 8 held). Now it passes over a block without its triangles where the ray is more than a yard above
  the block's highest vertex and the grid there (the same answer: a block height is a mix of three vertices' heights).
  EVIDENCE: picks identical (dump); Stormwind first ask median 0.73 -> 1.27 ms, worst 10.4 -> 5.1, asked again
  0.48 -> 0.39 (14 -> 8 blocks asked at most); Orgrimmar 0.46 -> 0.51, worst 2.9 -> 3.75, again 0.45 -> 0.41.
- [x] **G9 Lua 5.1 limits.** Check: `python3 test_luac.py`. EVIDENCE: GPS3D.lua 195/200 main-chunk locals
  (unchanged: `BlockHeight` and `ScreenToTerrain` declared once, their helpers inside `do` blocks, new state on
  `pool.rest` and `ns.blockHold`), most upvalues 45/60; 3 of 3.
- [x] **G10 Suites.** EVIDENCE: test_world 62/62, test_terrain 5/5, test_blocks 8/8, test_models 50/50,
  test_camheight 9/9, test_globe 55/55, test_quests 37/37, test_look 35/35, test_luac 3/3, test_choice 8/8 (its
  corner read moved to `ns.BlockTris`), test_blockbuild 6/6 (with `BB_COMPARE`; its decode check through
  `ns.BlockTris`), test_blockmem 8/8 (with `BM_COMPARE`), test_ondemand 41/41, test_probe 31/31.
- [x] **G11 Docs.** AGENTS.md (the buildings paragraph and the test list), PERFORMANCE.md (Applied, A4, with the
  table), tools/sandbox/README.md (`test_blockmem.py`; `test_blockbuild.py`'s decode check). `check_decode.py`'s
  Lua side moved to `ns.BlockTris` too (it does not run here: its `build_detail` import path is missing).

10 of 11 gates met, 1 abandoned (G7, measured).

Needs the game: nothing new to look at (the same textures and calls). `/gps debug on`'s MEMORY lines in Stormwind
should sit lower than before after flying round the city at 330 yd; no Lua errors zooming with the wheel at a low
tilted view over the city (the cursor's ground point).
