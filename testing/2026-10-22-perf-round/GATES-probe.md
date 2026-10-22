# GATES: step "probe" of the perf round (2026-10-22): `/gps3d probe`

The in-game checks of the J9 review's section 2 as one command, so Morten can run them in one go. Branch `perf`,
worktree `/home/claude/wt/P`. Sandbox numbers: Lua 5.4 through lupa, Stormwind Trade District, 330 yd straight
down, 30 fps fixed (the sandbox's frame times are constant; only the game can give real ones).

Scenario used before and after: `tools/sandbox/perf_focus.py` (12 scenes: Stormwind, Northshire, Westfall,
turning, still, walking, running) for normal frames; `tools/sandbox/test_probe.py` for the probe itself.

## Gates

- [x] **G1 The command.** `/gps3d probe` (and `/gps3d probe stop`) exists, with a line in the slash help; it says
  how long it runs and not to touch the mouse; runs to the end and prints all five parts.
  Check: `test_probe.py` checks 2-4. EVIDENCE: "starting: about 61 s. Do not touch the mouse or the keys ..."; ran
  54 s simulated (planned 61 s, the settling ended early); `1/5:3 2/5:1 3/5:1 4/5:1 5/5:1`. On the code before
  the step (`PROBE_ADDON=<d8cee5c's GPS3D files>`): "0 of 2 checks passed" (no `ns.probe`, `/gps3d probe` only
  toggles the window).
- [x] **G2 Part 1, cost per texture and per call.** Six settings (ground 800/3,200/6,400 with buildings 0; buildings
  2,000/4,000/8,000 with ground 3,200), each settled, then still / redrawn / turning by itself (20 deg/s): frame ms
  (median time between OnUpdates, and GetFramerate), GPS3D's Lua ms (Render's debugprofilestop), textures, calls a
  frame; a least-squares estimate per texture and per call; written to chat, the debug log (PROBE) and
  `GPS3D_DB.probe`. Check: `test_probe.py` checks 5-8 and 15. EVIDENCE (sandbox): textures 375 / 1,239 / 4,121 and
  3,005 / 4,488 / 4,750; turning 1,701 / 4,470 / 13,838 / 11,514 / 18,557 / 19,000 calls, redrawn 0 in all six;
  "1/5 estimate from 6 settings"; 15 lines in `GPS3D_DB.probe`, 15 PROBE lines in the debug log.
- [x] **G3 The calls are counted right.** Counted from what Render changed (P.Snapshot / P.Diff: corners,
  buckets, frames, shown, hidden, cut triangles), not by hooking the game's texture methods. Check: against the
  engine's exact count (Texture methods wrapped in the test), 5 frames each. EVIDENCE: turning 3 deg/frame 19,877
  counted vs 20,059 exact; 0.33 deg/frame 18,534 vs 18,570; redrawn 0 vs 5 (the marker); moved 0.25 yd 18,646 vs
  18,652 (all within 3 % + 20; mutation "corner 3 counted once" fails three of them).
- [x] **G4 Part 2, the fold.** Two squares of a test picture (`Media\Probe`: 4x4 checker, red diagonal = corners
  1-4, blue = 2-3), corner 1 lifted in one and corner 3 in the other, labelled on screen and in chat; the
  straight diagonal is the fold. Check: `scn_probe.py` in the page. EVIDENCE: `tools/sandbox/shots/probe_picture.png`
  (the page's renderer folds 1-4: red straight in both squares, blue kinked). The game's answer needs the game.
- [x] **G5 Part 3, RotateTextures.** A bent triangle beside the same in a frame turned by `RotateTextures(0.5)`,
  with a white ghost where it was; reports called / missing / error. EVIDENCE: bare engine "3/5 RotateTextures:
  missing"; stand-in: called once with 0.5; raising stand-in: "3/5 RotateTextures: error: ... refused (stand-in)".
- [x] **G6 Part 4, SetPointsOffset.** Textures anchored to their depth frame; the fullest frame shifted every frame
  (frame time vs none); then all eight shifted as the camera glides 35 px with a red cross and your arrow drawn for
  the moved camera; the real redraw at the end; ClearPointsOffset and the anchors back. EVIDENCE: bare engine
  "missing ... part 4 skipped"; stand-in: 4,635 textures anchored, 90 glide frames all eight frames shifted alike and
  the textures moving with them, the vertex nearest the cross 0.06 px from where the shift put it after the real
  redraw (mutation with the shift's sign flipped: 69.94 px, fails); raising stand-in: "4/5 SetPointsOffset: error".
- [x] **G7 Part 5, OffScreenFrame.** pcall CreateFrame, the methods there and missing, TakeSnapshot hidden and shown,
  ApplySnapshot, IsSnapshotValid, never left shown. EVIDENCE: bare engine "made; methods there: none"; stand-in
  "TakeSnapshot hidden -> 7, shown -> 7; ApplySnapshot -> true", shown only during that call (`[False, True]`),
  hidden after; raising stand-in "missing (CreateFrame: ... Unknown frame type ...)".
- [x] **G8 Always put back.** Settings (live and saved, nil kept), camera (mode, place, yaw), the ground's
  level-of-detail controller and the blocks' levels, anchors and frame offsets: at the end, on errors, on
  `/gps3d probe stop`, combat and the window closing. EVIDENCE: test_probe checks "settings, camera mode and view put
  back exactly", "(run 2)", "after the errors", three "stopped part way" checks; mutations "settings not put back"
  (6 checks fail), "anchors not put back" (5 fail), "no LOD/blocks restore" (1 fails), "combat not watched" (2 fail).
- [x] **G9 Nothing left shown.** Every frame the probe made hidden (driver, panel, cross, OffScreenFrame and its
  holder). EVIDENCE: `made_hidden()` true after every run and every stop.
- [x] **G10 Not in combat.** EVIDENCE: "in combat it refuses and says so; nothing changes": "not in combat: it
  changes the 3D view's settings and frames for about a minute; run it again after the fight".
- [x] **G11 Normal frames unchanged.** The driver frame is hidden until asked; `GPS3D.lua` gained `ns.Budgets`,
  `ns.RenderMarker`, `ns.BlockLevels` and a slash branch only. Check: `perf_focus.py before|after`. EVIDENCE: C calls
  and garbage identical in all 12 scenes (e.g. Stormwind turning with buildings 18,744 calls / 53 KB both, still 5 /
  3 KB both, running 20 yd/frame 19,560 / 194 KB both); ms within the sandbox's noise (7.0 -> 7.3, 3.6 -> 3.6, 18.4
  -> 17.0, 6.7 -> 5.9).
- [x] **G12 No loss of detail.** The view the probe leaves is the one it found. Check: every triangle drawn on the
  canvas matched one to one with the view before (same depth bucket, every corner within VO_EPS 0.25 px).
  EVIDENCE: 1,939 of 1,939 matched, worst corner 0.000 px (and with the triangles off the canvas included, in a
  separate run, 2,224 of 2,224);
  per single setting and for all six in `scratchpad/probe_step/dbg4.py`: 1,916 of 1,916 each, worst 0.0-0.25 px.
  Found on the way: without putting back `Lod.kappa`/`target` and the blocks' levels the view came back with other
  levels (2,148 of 4,526 triangles the same after a budget-only run): the controller's dead band and the blocks'
  hysteresis keep some past; now put back.
- [x] **G13 Suites.** test_world 62/62, test_terrain 5/5, test_blocks 8/8, test_models 50/50, test_camheight 9/9,
  test_globe 55/55, test_quests 37/37, test_look 35/35, test_probe 31/31, test_luac 3/3 (GPS3D.lua 195/200 main-chunk
  locals, unchanged; Probe.lua 54/200, 27 upvalues).
- [x] **G14 Docs.** AGENTS.md (Probe.lua bullet with the numbers, Media, test list), PERFORMANCE.md (Applied section
  with before/after, How to measure), TESTING.md (section 15 and the list at the top), tools/sandbox/README.md.

## Not answerable here (needs the game)

All of the probe's answers: the client's frame times per texture and per call, the fold diagonal, whether
RotateTextures turns the geometry, SetPointsOffset's cost and pixel snapping on a frame with thousands of textures,
whether OffScreenFrame exists for addons and snapshots. Also: whether anchoring ~4,600 textures to their depth frames
and back (part 4, about 18,000 calls once each way) causes a visible hitch (it should be one frame).
