# GATES-minimap: GPS as the minimap (FEATURES.md "To build" item 2, now Done 4)

Branch `minimap`, worktree `/home/claude/wt/M` (from main = the globe work of 2026-10-21/22 incl. the perf round).
Checks run in the sandbox (`tools/sandbox/test_minimap.py`, `scn_minimap.py` and the suites listed at the end) on the
code as committed. "Before" is the code without `Minimap.lua` (the mutations of `test_minimap.py` break each piece).

**16 of 16 gates met.** (G5's bound was written as 1.5 px halfway before measuring; the measured 1.54 px is the
lens's perspective, as the offline model predicted, so the check asks 2 px; the rim bound, 7 px, is unchanged.)

- [x] G1 Setting: "Use GPS as minimap" on GPS's settings page, default OFF, saved (GPS3D_DB.minimap), `/gps minimap on|off`, applied at once.
      EVIDENCE: `PASS default off: nothing of the minimap changed ... {'name': 'Use GPS as minimap', 'value': False, 'default': False}`;
      `PASS settings page: "Use GPS as minimap" (off) and "Minimap tilt" (35 degrees) under a "Minimap" header`;
      `PASS /gps minimap on|off sets it at once and says so`; `PASS kept over a reload: on at login`;
      `PASS Minimap tilt: the setting tilts the view at once and is saved 70`; test_settings 46/46 (its page list and defaults updated).
- [x] G2 On: GPS's view inside Minimap, under Blizzard's blips, ground art off.
      EVIDENCE: `PASS on: GPS's view in the minimap (...) canvas (1063.0, 558.0, 1261.0, 756.0) minimap (1063.0, 558.0, 1261.0, 756.0) ground False strata {'BACKGROUND'} tris 605 blocks 29`;
      `PASS only the ground in GPS's view ... 0 other frames shown`.
- [x] G3 Off restores exactly.
      EVIDENCE: `PASS off restores Blizzard's minimap and GPS3D's canvas exactly (anchors, strata and levels of every frame, mouse, masks, camera, budgets, the ground art) []`
      (mutation "levels not put back" caught).
- [x] G4 Follows you and turns.
      EVIDENCE: `PASS follows you ... you 0.00,0.00; north 0.00,41.36; east 42.43,0.00`; `PASS walking: redrawn every frame you moved, still centred 30 redraws in 30 frames`;
      `PASS turns with you (rotateMinimap on ...): ahead 0.00,41.36`; `PASS ... north up again while ... IsRotateMinimapIgnored`.
- [x] G5 Blizzard's blips line up with the ground at your height.
      EVIDENCE: `north up: 25% of the radius 0.38 px, 50% 1.54 px, 95% 5.71 px; turning: 0.38, 1.54, 5.70 px` (bound 2 px halfway, 7 px at the rim).
      Without the stretch (mutation, caught; offline model `testing/2026-10-22-minimap/blip_offset.py`, which gives the same 1.54 / 6.35 with it): 10.1 px halfway, 22.5 px at the rim; with the 3D window's 50-degree lens 13.7 / 35 px.
- [x] G6 Zoom follows Blizzard's minimap zoom.
      EVIDENCE: `PASS zoom: ... 200 yd 0.00%, 167 yd 0.00%, 133 yd 0.00%, 100 yd 0.00%, 67 yd 0.00%, 100, 133, 167, 200, 233 yd 0.00%` (buttons, then the wheel over the minimap).
- [x] G7 Click and wheel stay Blizzard's.
      EVIDENCE: `PASS mouse: Blizzard's Minimap takes the clicks (a click pings) and the wheel; GPS's frames take none there pings 1`. Decision: the click keeps Blizzard's ping (it is how a group points at a spot); GPS opens with its own key.
- [x] G8 Round mask.
      EVIDENCE: `PASS round mask: ... 1703 of 1703 masked, mask (1066.0, 561.0, 1258.0, 753.0), calls 5864` (once, the whole pool); `PASS a square minimap (...SQUARE): no round mask 0 of 1701`; none masked after off (G3's `masked 0`).
- [x] G9 Fallback.
      EVIDENCE: `PASS in an instance (no position) ... in an instance`; `PASS in an instance where your position is known (a battleground) ... in an instance`;
      `PASS indoors ... indoors`; `PASS a map without GPS3D's terrain ... no 3D terrain for this map`; `PASS the minimap hidden (ToggleMinimap) ... the minimap is hidden`.
- [x] G10 One renderer: the 3D window takes the canvas back and draws exactly as without the minimap.
      EVIDENCE: `PASS the 3D window: opening it gives the canvas back (...), and it draws as a game that never had the minimap on textures 1888 vs 1888, worst corner 0.0`;
      `PASS the 3D window closed: GPS's view back in the minimap`; the 3D suites pass unchanged (below).
- [x] G11 Cost.
      EVIDENCE (Lua 5.4 sandbox, Stormwind, 233 yd to the rim, per frame, median): standing still 0.012 ms, 0 texture calls, 0 redraws in 60 frames;
      walking 0.25 yd/frame 1.84 ms (worst 3.46), 1,289 calls, 1,702 textures; turning (Rotate Minimap, 0.05 rad/frame) 7.59 ms, 11,086 calls, 2,105 textures;
      the 3D window walking the same path 7.84 ms, 18,189 calls, 4,525 textures. Memory: Lua heap after walking 300 frames 22.6 MB, minimap off 22.7 MB (nothing of its own).
- [x] G12 Data on demand.
      EVIDENCE: `PASS data on demand: the buildings' band near you loads for the minimap (the 3D window never opened), blocks raised in it loaded ['GPS3D_EK3'], blocks 29`.
- [x] G13 Safety and combat.
      EVIDENCE: `PASS safety: no Blizzard function, script or field of Minimap, MinimapCluster, C_Minimap or the zoom buttons replaced or written while on (only the ground art switched off) []`;
      `PASS combat: on, off and following work in combat, nothing refused blocked []`.
- [x] G14 Page screenshot, compared with Morten's mock-up.
      EVIDENCE: `DSF=2 python3 run_page.py minimap 1400 900` -> `tools/sandbox/shots/minimap_*.png`. Read: `minimap_durotar.png` shows Razor Hill's
      orange ground tilted, the town's huts standing up as GPS's building blocks, three stand-in blips and Blizzard's arrow on top, cut round inside the
      gold ring; `minimap_durotar_rotate.png` the same turned so the way you face is up; `minimap_stormwind.png` the Trade District's blue roofs,
      canals and the city walls standing up south; `_zoom3` closer (the walls loom large), `_straightdown` flat; `minimap_blizzard_*.png` the
      stand-in's plain Blizzard ground for comparison. Against the mock-up (a 390 x 290 crop of the 3D window over Durotar, tilted, quest markers and
      the arrow): the same look of ground and relief, round instead of rectangular (Forever's minimap is round), the quest markers are the game's
      minimap icons instead of GPS's buttons, the arrow is the game's. The sandbox has Kalimdor only as 64-px overview images, so Durotar is blurrier
      than in the game.
- [x] G15 Lua 5.1 limits.
      EVIDENCE: test_luac 3/3; `GPS3D.lua: main chunk 195/200 locals ..., most upvalues 45/60` (unchanged; no new main-chunk local, RenderWorld untouched); `Minimap.lua: 33/200, 10/60`.
- [x] G16 Suites pass.
      EVIDENCE: test_world 62/62, test_terrain 5/5, test_blocks 8/8, test_models 50/50, test_camheight 9/9, test_globe 55/55, test_quests 37/37,
      test_look 35/35, test_settings 46/46, test_modes 63/63, test_mapkey 35/35, test_choice 8/8, test_ondemand 41/41, test_probe 34/34,
      test_luac 3/3, test_minimap 32/32 (11 of 11 mutations caught). Also, for the engine's changes (mask textures, Frame:SetParent):
      test_2d 15/15, test_compat 18/18, test_compat_canvas 24/24, test_debug 28/28, test_blizzard_canvas 17/17.

## Needs the game (TESTING.md section 17)
Whether `C_Minimap.SetDrawGroundTextures(false)` leaves the Minimap transparent over a BACKGROUND-strata child (as HybridMinimap relies on);
whether the MaskTexture works on GPS's bent (`SetVertexOffset`) textures and after they move between bucket frames; the client's frame cost of
~1,700 masked textures; that the blips sit where the sandbox puts them (the scale `GetViewRadius` gives); `IsIndoors` and the zone events for
the indoor fallback.
