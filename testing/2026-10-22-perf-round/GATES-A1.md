# GATES: step A1 of the perf round (2026-10-22): keep the tile and block choice between frames

The J9 review's A1: `ChooseTiles` (with the ground's level-of-detail controller) and `ns.ChooseBlocks` ran every
frame. Now a frame keeps the last full choice while the view stays inside the 40 px margin it was made for, and
chooses afresh at once on a resize, another map, a setting or a data change. Branch `perf`, worktree
`/home/claude/wt/P`. Sandbox: Lua 5.4 through lupa, 900 x 650 window (canvas 898 x 648), real data.

Scenario before and after: `tools/sandbox/test_choice.py`, a scripted path of 19 segments, 1,105 frames: walking,
panning, turning, tilting, zooming and still redraws over Stormwind's Trade District (330 yd, straight down and
tilted 45), Orgrimmar's Valley of Strength (150 yd tilted 45), Mount Hyjal from 5,000 yd and the Eastern Kingdoms
from 12,000 yd. The code before is `prototypes/GPS3D/GPS3D.lua` at 2cce3ea, loaded with `GPS3D_LUA=<file>`.
Milliseconds: processor time, best of 3 runs each; another agent's tests ran on the same two cores part of the
time (step A5, worktree P5), so single milliseconds are noisy; calls and garbage are exact.

## Gates

- [x] **G1 Reproduced and measured before.** The choice's share of a frame on the path, code before.
  Check: `GPS3D_LUA=<before> python3 test_choice.py` (time pass, 3 runs). EVIDENCE: Stormwind walking 0.56 ms of
  4.37 (13 %), still redrawn 0.46 of 2.44 (19 %); Orgrimmar walking 0.38 of 3.89 (10 %); Hyjal 5,000 yd turning
  1.18 of 3.40 (35 %), still 1.11 of 2.24 (50 %); Eastern Kingdoms 12,000 yd turning 2.10 of 5.07 (41 %), still
  1.95 of 3.64 (54 %). (The review: 6-18 % in cities, 40-50 % far out.)
- [x] **G2 The bound.** A frame keeps the choice only while every point that can show on the canvas (2 px round
  it, where triangles are cut) lay inside the view grown by 40 px that the choice was made for: the view's
  pyramid between depth dn (nearer than that everything is in the kept choice: nothing drawn is that near, or
  every tile and block reaching in there was chosen) and Dmax (past the range, a tile's corner and any height) is
  convex, so its 8 corners inside the grown view suffice; tiles just past the range that may be in view, and a
  range shift over 5 % (at least a quarter tile) choose afresh. Moving, turning, tilting and zooming are one test.
  Check: the camera moved until `Inside` fails. EVIDENCE: Stormwind 330 yd: 18 yd, 4.75 degrees of turn straight
  down (2.25 tilted), 8 % of zooming out (zooming in brings nothing new into view); Hyjal 5,000 yd: 160 yd,
  2.25 degrees, 4.75 %.
- [x] **G3 No ground missing at the canvas edge.** Every frame of the path against a full choice made again from
  the same state (the controller held; all put back): no tile whose ground the full choice draws, and no block it
  raises, reaching the canvas (its drawn triangles, cut at the near plane, back faces left out) may be missing.
  Check: `test_choice.py` check 3. EVIDENCE: 1,105 frames, missing tiles 0, blocks 0. With the choice kept as long
  as the bound alone allows (`CHOICE_KEEP=1000`): 0 and 0. Mutation, the bound 10 x too loose (`CHOICE_MUT=loose`):
  1,588 tile-frames and 165 block-frames missing, the check fails.
- [x] **G4 Same levels, or a change at most one full choice later.** On every frame that chooses afresh the kept
  choice is the full one (tiles, levels, minimap/overview image, blocks, block levels), and a difference on the
  canvas lasts at most KEEP - 1 = 3 frames. Check: `test_choice.py` check 4. EVIDENCE: 492 fresh frames,
  differences there 0; on kept frames tile levels differing 0 tile-frames and images 0 (both worked out per frame
  for the camera as it is), blocks 331 block-frames of which 92 on the canvas (blocks at the budget's far end
  raised or flat a frame or three late), longest 3 frames.
- [x] **G5 Corners within VO_EPS.** Every corner drawn of a mesh at the full choice's level within 0.25 px of its
  vertex's exact projection (with this frame's morphing). Check: `test_choice.py` check 5. EVIDENCE: 10,150,770
  corners, worst 0.2500 px.
- [x] **G6 The ground moves as before while zooming; the far views as before.** The controller (Lod.kappa)
  steps only in a full choice, and a frame is kept only while it rests and the kept levels stay within its target
  and the budget. Check: `test_terrain.py` before and after. EVIDENCE: zoom sweeps, max jump at fixed points
  before / after: Hyjal 2.63 / 2.63 and 1.96 / 1.96 px, Durotar 5.84 / 5.68 and 2.74 / 2.85 px, Elwynn 2.41 / 2.41
  and 2.05 / 2.01 px; the five far views the same triangles (1,205 / 2,607 / 1,033 / 2,143 / 2,099) and the same
  height error on screen. (A first version let the controller take the skipped frames' steps at once at the next
  full choice, as the review proposed: Durotar's zoom jumped up to 14.35 px, test_terrain failed; and with one step
  per full choice only, the controller fell behind: 453 instead of 2,107 ground triangles there. Both dropped.)
- [x] **G7 Never over the budget.** Check: `test_choice.py` check 6. EVIDENCE: at most 3,196 of 3,200 ground
  triangles on the path.
- [x] **G8 Choose afresh at once on a change.** A resize, another map, the ground's or the buildings' budget,
  buildings switched off, the game's buildings standing in for blocks (`ns.coverStamp`, bumped by `Models.lua` when
  where they cover changes), the probe putting block levels back. Check: `test_choice.py` check 8. EVIDENCE: 7 of 7.
- [x] **G9 Near the camera.** Where something tall stands near the camera (Orgrimmar's cliffs and towers), the
  choice is kept only while every block reaching into the view there is in it. Check: `test_choice.py` check 7.
  EVIDENCE: kept with the blocks, afresh without them; the mutation "nothing near the camera looked at" fails it.
- [x] **G10 The Lua time saved.** Check: `test_choice.py` time pass, before and after, best of 3, and check 2
  (a kept frame's choice under a quarter of a full one). EVIDENCE: kept frames 0.148 ms, full choices 0.867 ms.
  Saved share of the frame: Stormwind walking 8-9 %, panning 6 %, turning 1 deg 8 %, still redrawn 16 %;
  Orgrimmar walking 6 %, panning 4 %; Hyjal 5,000 yd turning 12 %, panning 14 %, tilting 13 %, still 49 %;
  Eastern Kingdoms 12,000 yd turning 18 %, still 49 %. Zooming and turning 3 degrees a frame tilted save 0-2 %
  (the controller works every frame there, or the view leaves the margin every frame). Table in PERFORMANCE.md.
- [x] **G11 No change in C calls or garbage.** Check: `CHOICE_PASS=calls`, before and after. EVIDENCE: calls a
  frame within 3 % in every segment (Stormwind walking 18,241 -> 18,250; Orgrimmar turning 14,515 -> 14,994, its
  blocks' levels a frame or three late); garbage the same or less (Hyjal turning 28.2 -> 16.7 KB, Stormwind
  turning 3 deg 103.8 -> 70.9 KB); nothing made per kept frame.
- [x] **G12 Checks fail on the code before.** Check: `GPS3D_LUA=<before> python3 test_choice.py`. EVIDENCE:
  "0 of 3 checks passed" (nothing kept: 0 % on every segment; the shadow checks need `ns.choice`).
- [x] **G13 Suites pass.** EVIDENCE: test_world 62/62, test_terrain 5/5, test_blocks 8/8, test_models 50/50,
  test_camheight 9/9, test_globe 55/55, test_quests 37/37, test_look 35/35, test_probe 31/31, test_debug 28/28
  (the PERF line gained "(n kept the tile choice)"), test_choice 8/8, test_luac 3/3. test_blocks' two "in view"
  checks now count blocks reaching the canvas: a block only in the 40 px margin may wait for the next full choice
  (counted with the margin, as before, the new code failed 2 of 8: Stormwind 300 / 40 / 150 yd had one such block
  each, none on the canvas; zooming, 2-3 a sweep, none on the canvas).
- [x] **G14 Lua 5.1 limits.** Check: `test_luac.py`. EVIDENCE: GPS3D.lua main chunk 195/200 (unchanged, no new
  main-chunk local: the wrapper reassigns `ChooseTiles` inside a `do` block, state on `ns.choice`), most upvalues
  45/60 (RenderWorld unchanged); Models.lua 68/200.
- [x] **G15 Docs.** AGENTS.md (per-frame savings and the test list), PERFORMANCE.md (Applied, before/after),
  tools/sandbox/README.md (test_choice.py, test_blocks.py), TESTING.md (section 16).

## Needs the game

How much the client's frame time drops: the sandbox measures only the Lua side; no C call changes. TESTING.md
section 16: the PERF line's "kept the tile choice" count while walking and turning, and a look at the window's
edges for ground or buildings appearing late (none expected: nothing on the canvas waits, by the check above).
