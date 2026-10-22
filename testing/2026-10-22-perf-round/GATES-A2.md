# GATES: step A2 of the perf round (2026-10-22): pooled building tables, block building spread

The J9 review's A2: a frame that makes new building blocks allocated a table per new triangle (`BuildBlockMesh`) and
new arrays per decoded block (`BlockGeo`); the ground's triangle tables are pooled since J8, the blocks' were not.
Pool them the same way, give them back in `ReleaseMesh`, and lower `BUILD_LIMIT` (1,500 new triangles a frame) to
about 500 if that halves the hitch without blocks arriving visibly late. Branch `perf`, worktree `/home/claude/wt/P`.

Scenario before and after: `tools/sandbox/test_blockbuild.py` (new), Lua 5.4 through lupa, real data, 1280 x 800,
buildings 4,000 (default): you run 20 yd a frame (30 fps) three laps round Stormwind (2,600 yd a lap, 4.3 s, longer
than unused meshes are kept, 3 s, so every lap makes its blocks again), the camera following at 330 yd straight
down, 369 frames, then stand still. The code before is `prototypes/GPS3D/GPS3D.lua` at 15bb3e4, loaded with
`GPS3D_LUA=<file>`. Garbage: Lua allocation during the frame, GC stopped (the sandbox's stand-ins for SetTexCoord
and SetVertexColor fill their tables in place in this test, so only the addon's allocation counts). Milliseconds:
processor time without the sandbox's own SetParent (a linear search through thousands of textures; one C call in
the game); two sequential runs each, this agent alone on the two cores. Calls and garbage are exact.

## Gates

- [x] **G1 Reproduced and measured before.** Check: `GPS3D_LUA=<before> MEASURE=1 python3 test_blockbuild.py`.
  EVIDENCE: 220 of 369 frames make blocks; a busy frame allocates 142 KB (median; laps 2-3: 112 KB; quiet frames
  6 KB); making blocks (BlockGeo + BuildBlockMesh) 0.40-0.42 ms median, worst 8.0-8.5 ms in a frame; Lua ms busy
  median 6.9-7.0, worst frame 19.7-25.7; C calls busy median 19,014, worst 36,658. Where the allocation went
  (busy frames of a first, shorter route, wrapped functions): `BuildBlockMesh` 15.0 MB of 35.6 MB (a table per
  triangle), the ground's new tile meshes 7.5 MB (`Lod.NewMesh`'s arrays, not this step), `BlockGeo` 4.3 MB.
  (The review's 183 KB was `perf_focus.py`'s run with the engine's tables counted.)
- [x] **G2 Pooled.** Block triangle tables come from and go back to `pool.tris` (shared with the ground, every field
  set again); a released block mesh's `px`, `py`, `pd` and `tris` arrays go to `pool.sets` (screen positions
  emptied, the tail of `tris` cleared); a decoded block the cache forgets gives its `vx`, `vy`, `vh`, `vc`, `idx`
  and palette to `pool.geo`, or, while a mesh still draws its vertices, when `ReleaseMesh` gives that mesh back.
  Check: `test_blockbuild.py` check *pool*. EVIDENCE: during the run 33,484 block triangles made on a given-back
  table (12,635 new; before: 0 and 46,119), 490 block meshes on given-back arrays; releasing every mesh gives back
  all 9,341 block triangles (before: 2,146 tables back, the ground's only); 900 blocks decoded round the Trade
  District (more than `GEO_LIMIT` 400 keeps), 531 into a forgotten block's arrays, 0 wrong. Fails on the code before.
- [x] **G3 Garbage of a busy frame.** Check: check *garbage* (under half of before). EVIDENCE: 142 -> 29-30 KB
  median (-79 %), laps 2-3 112 -> 19 KB, quiet frames 6 -> 3 KB. The worst frame's 2.7 MB is unchanged: it makes
  new ground tile meshes (`Lod.NewMesh`), outside this step. Fails on the code before (142 KB).
- [x] **G4 Nothing drawn differently.** (a) Every frame of the run, every triangle of every block mesh drawn is
  compared with an independent decode and build of its block in the test (corners, vertex positions and counts,
  image or colour, texture coordinates, the remembered state), its corners on screen are where its vertices are
  drawn (the engine's vertex offsets) and within `VO_EPS` of their exact projection, and no texture or triangle
  table is in two places. (b) The drawn view (every texture shown: image, coordinates, colour, corners, layer, depth
  frame) at three views after the run, against the code before (`BB_DUMP` / `BB_COMPARE`). Check: checks *exact*
  and *same as the compared dump*. EVIDENCE: (a) 1,345,630 triangles and 3,201,690 corners, 0 wrong; (b) Trade
  District 330 yd straight down 3,632 textures, Mage Quarter 330 yd tilted 5,618, Cathedral 150 yd
  tilted 2,979: identical (sha1 f84a99a553a1, 0fcffaccba1d, 1129c9e3c3d1 both). C calls identical (busy median
  19,014, worst 36,658, quiet 17,933, `BB_PASS=calls`).
- [x] **G5 The checks catch broken pooling (mutations).** EVIDENCE: corner screen state not reset on a reused table
  -> *exact* fails (corners on screen); `tris` tail not cleared -> the addon errors in Render (test exits 1); a
  forgotten block's array tails not cleared -> *pool* fails (decode lengths); a forgotten block's arrays reused while
  its mesh still draws them -> *exact* fails (118 triangles: counts and vertices). Not cleared screen positions on a
  reused mesh change nothing measurable (`VO_EPS` bounds a kept position; every check passes): the arrays are emptied
  anyway so a reused mesh starts exactly as a new one.
- [ ] **G6 BUILD_LIMIT about 500.** ABANDON: G6 lower BUILD_LIMIT to 500. Measured with the pools (same scenario,
  two runs): making blocks worst 8.4-8.5 -> 4.1-4.8 ms a frame (halved), but the worst frame only 22.0-29.5 ->
  19.2-21.7 ms (its worst frames make ground tiles and few blocks), and blocks arrive visibly late: 23 block-frames
  flat on the canvas while chosen (before 0), 48 waiting, 35 waits of 1.34 frames mean, one block 4 frames (133 ms)
  flat, one left the view before it was made. 750 (one run): 2 block-frames flat on the canvas, worst block-making
  frame not halved. BUILD_LIMIT stays 1,500; check *cap* and *late* guard it (no block flat on the canvas while
  running, all drawn at their level the frame after stopping).
- [x] **G7 Frame time.** Check: `MEASURE=1` before / after, two sequential runs each. EVIDENCE: Lua ms busy median
  6.9-7.0 -> 7.3-7.6, quiet median 5.2-5.3 -> 5.8-5.9 (quiet frames run none of the changed code: the runs' noise,
  about +0.5 ms); making blocks 0.40-0.42 -> 0.36-0.37 ms median; worst frame 19.7-25.7 -> 22.0-29.5 (noise; the
  worst frames are not block frames). In the game the saving is the collector's work for 110 KB a busy frame.
- [x] **G8 Lua 5.1 limits.** Check: `python3 test_luac.py`. EVIDENCE: GPS3D.lua 195/200 main-chunk locals
  (unchanged: new state on `pool`, `mesh.geo`, `g.mesh`), most upvalues 45/60; 3 of 3.
- [x] **G9 Suites.** EVIDENCE: test_world 62/62, test_terrain 5/5, test_blocks 8/8, test_models 50/50,
  test_camheight 9/9, test_globe 55/55, test_quests 37/37, test_look 35/35, test_luac 3/3, test_choice 8/8,
  test_ondemand 41/41, test_probe 31/31, test_blockbuild 6/6 (with `BB_COMPARE`; 5/5 without).

8 of 9 gates met, 1 abandoned (G6, measured).

Needs the game: nothing new to look at (the same textures and calls). If anything, flying fast over a city with
`/gps debug on` should show no Lua errors and the MEMORY lines should climb less while flying.
