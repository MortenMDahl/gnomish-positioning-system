# GATES-J5: quest areas in the 3D view

Job: the tracked quest's objective area, and the hovered marker's, drawn on the ground in the 3D view
(Morten: "Quest area is visible in 2D mode, but not in 3D mode"). Checks run from `tools/sandbox/`.

Approach (from Forever's UI source, branch `forever`): no API returns an area's outline. The quest-area
frame only draws it (`FrameAPIBlob`: SetMapID, DrawBlob, DrawNone, ...,
https://github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated/FrameAPIBlobDocumentation.lua)
and hit-tests it (`FrameAPIQuestPOI`: `UpdateMouseOverTooltip(x, y) -> questID, numObjectives`,
GetNumTooltips, GetTooltipIndex,
https://github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated/FrameAPIQuestPOIDocumentation.lua);
Blizzard's `QuestBlobPinMixin:UpdateTooltip` passes the map canvas's normalised cursor position
(https://github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_SharedMapDataProviders/QuestBlobDataProvider.lua).
So GPS samples that hit-test over a grid on a frame of its own (spread over frames, cached per quest and
quest-log change), turns the grid into pieces and outlines (marching squares, edges bisected), and draws
them as ground pieces projected like the terrain. The docs cannot say whether the hit-test answers a
frame that is not drawn, so three ways are tried and the one that works is kept: frame hidden, shown at
alpha 0, shown behind the 3D view's opaque ground.

- [x] G0 Reproduced: on the baseline the 3D view draws no area for the tracked quest.
  Check: the new `test_quests.py` on the baseline code (8131b6d, `git archive` into scratchpad/j5baseroot).
  EVIDENCE: `FAIL 3D area: the remaining area checks ran TypeError: 'NoneType' object is not subscriptable`
  (no `questAreas` in GPS3D), 25 of 26.
- [x] G1 Shape covered: the tracked quest's 3D area (stand-in: two overlapping ellipses, a waisted shape)
  covers every probe point more than one cell inside the true edge and none more than 1/8 cell outside.
  EVIDENCE: `PASS 3D area: covers the true shape ... straight down 477 of 477 deep points covered, 0 of 871
  outside points covered; 214 of 214 pieces drawn, cell 18.2 yd`; one closed border, 124 border pieces.
- [x] G2 On the ground: every drawn corner at `GroundHeight` under it and where the view projects it.
  EVIDENCE: `PASS ... worst 0.0000 yd, 0.000 px`; tilted 40 degrees and turned: `worst 0.0000 yd, 0.000 px;
  213 of 214 pieces face the camera, 477 of 477 deep points covered`.
- [x] G3 Under the markers, over the ground. EVIDENCE: `PASS ... area 11 (draw layer 2), ground up to 10,
  your arrow 11 (draw layer 3), models 13, markers 15`.
- [x] G4 Hovered marker draws its area, leaving removes it. EVIDENCE: `PASS ... hovered [38] (674 of 674
  deep, 0 spills), after [], areas 1`; plus `PASS hover, click, leave: the hovered quest is cleared even
  when the button shows another quest by then` (a stale-hover bug in PinLeave found on the way, fixed).
- [x] G5 Hidden with the setting off, questPOI off, on the planet view. EVIDENCE: `214 -> setting off 0,
  questPOI off 0, back 214; planet: hidden True`.
- [x] G6 API missing: nothing drawn, no error, `/gps3d test` and the debug log say why. EVIDENCE: `PASS ...
  0, 0; one: the quest-area frame has no hit-test (UpdateMouseOverTooltip); drawn now: 0 area(s) ... |
  ...cannot be made here (... unknown frame type QuestPOIFrame); drawn now: 0 area(s)`; `PASS no Lua errors`.
- [x] G7 Fallback ways. EVIDENCE: `only while shown: found at alpha 0; only while drawn: behind the 3D view;
  never: none drawn; the sampler hidden after` each; `/gps3d test` line: `quest areas: from the quest-area
  frame's hit-test (UpdateMouseOverTooltip), frame hidden; last: quest 33 in zone 1429: ...`.
- [x] G8 Sampling cost. EVIDENCE: `SAMPLING quest 33: 1671 hit-tests, 2.3 ms over 5 frames, grid 24x21 cells
  of 18.2 yd` (at most 400 hit-tests and 2 ms a frame; only when the tracked/hovered quest or the quest log
  changes).
- [x] G9 Frame cost. EVIDENCE: the area's own share `0.182 ms per frame` (213 fill + 124 border pieces,
  sandbox Lua 5.4), 0 bytes of garbage per frame (500 calls, collector stopped). Render (stats.ms, 120
  turns, scratchpad/j5_perf.py), three runs each, before (8131b6d) / after: straight down 900 yd
  10.27, 9.49, 9.34 / 10.86, 9.35, 8.61 ms; tilted 45 at 650 yd 23.11, 24.05, 23.18 / 26.01, 22.62, 26.33 ms:
  the difference is within the run-to-run noise.
- [x] G10 Screenshot. EVIDENCE: `shots/quests_3d_area.png` (straight down) and `quests_3d_area_tilted.png`
  (48 degrees, turned 35): the waisted blue-violet area with a brighter rim on the ground round quest 33's
  marker, the marker over it, the terrain visible through it; scenario prints `1 areas, 214 fill, 124
  border pieces`.
- [x] G11 Mutations caught (scratchpad/j5_mutate.py, each in a copy): heights +3 (2 FAIL), layer = markers'
  (1), layer = canvas (2, incl. planet), old pieces left shown (5), stale hover (2), edge points outside (3),
  no fallback way (1), no hit-test check (1), corner order (2), quest setting ignored (3, incl. the 3D
  area check). 10 of 10 caught.
- [x] G12 Suites: test_quests 37 of 37, test_world 60 of 60, test_modes 63 of 63, test_look 35 of 35,
  test_globe 54 of 54 (run alone; one timing check missed while five suites ran at once), test_luac 3 of 3
  (GPS3D.lua main chunk 197/200 locals, most upvalues 58/60, unchanged; QuestAreas.lua 38/200, 17/60).

12 of 12 gates (plus G0) met.
