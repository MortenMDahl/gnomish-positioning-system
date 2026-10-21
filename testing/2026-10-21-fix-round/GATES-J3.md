# Gates for J3: camera height in cities

Measured with `tools/sandbox/test_camheight.py` (run from `tools/sandbox/`; `--file <old GPS3D.lua>` runs the
same on the baseline 8131b6d, `--fast` draws fewer triangles, which the camera does not read, `--only
zoom|pan|ease` one part). Frames are sandbox ticks at 30 fps; zoom is 2 % per frame (`Zoom(0.98)`) from
1,500 yd to the minimum (or until the camera stops); cities: Orgrimmar (Valley of Strength), Stormwind
(cathedral, Trade District), Thunder Bluff; straight down and tilted 45; Free (toward the cursor, centre and
off-centre) and Follow (24 zooms). Pans: a left-drag of 12 px a frame for 150 frames at 30 yd (straight
down) and 45 yd (tilted 45) over the same four places. "Height jump" = the largest per-frame change of the
camera's height not explained by the zoom (or pan) step; "view jump" = the largest per-frame screen motion
of fixed ground points (a 7 x 5 grid over the view) not explained by it. All numbers from the code as
committed (49ccdd8).

- [x] G1 Zoom in over the three cities: worst height jump and view jump before and after; after clearly smaller.
  EVIDENCE: before 7.13 yd, 141.4 px (Orgrimmar and Thunder Bluff, Follow, tilted 45); after 0.73 yd, 31.4 px.
  Free mode before 0.50 yd a frame in most runs (the 0.5 yd a step could lift, applied at once), after 0.36.
- [x] G2 Slow pan across the three cities at a low height: worst height jump and view jump before and after; after clearly smaller.
  EVIDENCE: before 37.78 yd, 869.5 px; after 6.30 yd, 98.9 px (the worst is an eased climb of about 80 yd up
  a cliff in Orgrimmar; Stormwind and Thunder Bluff at most 3.0 yd, 36.7 px).
- [x] G3 The camera never ends below the ground/roof surface, and reaches the clearance within the ease (ease time stated).
  EVIDENCE: lowest 8.94 yd (pans) and 9.40 yd (zooms) above the surface right under the camera in every frame;
  teleported 162 yd from the street onto the cathedral roof: 2.00 yd above it in the first frame (the floor,
  GAP 2), within 0.5 yd of the clearance after 0.35-0.37 s at 20, 30 and 60 fps, no overshoot, the same
  height at 0.2 s at all three (6.149 yd). Ease: critically damped, RATE 12/s, 95 % of any change in 0.4 s,
  99 % in 0.55 s.
- [x] G4 Zoom still stops at the clearance; the point under the cursor stays under the cursor (test_world wheel check).
  EVIDENCE: all 24 zooms end at least 8.00 yd above the ground and roofs within 25 yd once the wheel stops
  (while it still turns, at most LAG 2 yd inside: lowest 6.31); test_world "wheel (Free): ground under the
  cursor stays put" PASS, "zoom in on a peak", "tilted 30 deg toward a slope", "straight down" PASS
  unchanged, "zoom onto the cathedral roof" PASS with its bound changed to 2.5 yd inside while zooming and
  0.5 yd once settled (it was 0.5 yd while zooming).
- [x] G5 New checks fail on the old code (baseline) or a mutation and pass on the new.
  EVIDENCE: baseline fails the 4 jump checks (7.13 yd, 141.4 px, 37.78 yd, 869.5 px). Mutations of the new code:
  no floor -> "never under a roof" FAIL (-48.6 yd) and "clearance within the ease" FAIL (0.57-0.6 s);
  floor not applied at once -> "never under" FAIL and "same at 20, 30, 60 fps" FAIL (5.22 / 5.56 / 5.87);
  no LAG cap (`allowed = now + 0.5`) -> "at most 2 yd inside while zooming" FAIL (5.75). The previous
  agent's half-done zoom rule (`allowed = (following and target or 0) + 0.5`) left Free zooms stuck above
  roofs until the frame cap (found, replaced).
- [x] G6 Suites pass: test_world, test_globe, test_look, test_luac (locals and upvalues within the limits).
  EVIDENCE: test_camheight 9/9, test_world 60/60, test_globe 54/54, test_look 35/35, test_luac 3/3 (GPS3D.lua
  197/200 locals, 58/60 upvalues, unchanged); also test_models 50/50, test_modes 63/63, test_quests 25/25,
  test_compat 18/18.
- [x] G7 Frame times before and after (same scenario).
  EVIDENCE: full budgets, median of 60 frames, tilted 45 at 120 yd: idle 0.05-0.07 ms -> 0.04-0.05 ms with
  the same Lua garbage per frame (1.1 KB, the sandbox's own); panning 20-56 -> 20-27 ms and zooming 15-31 ->
  16-28 ms (Stormwind cathedral, Trade District, Thunder Bluff; sandbox noise dominates). StepLift is a cache
  check when nothing moves and makes no tables; while the lift eases (up to about 0.5 s after a move) the
  view is redrawn each frame.
