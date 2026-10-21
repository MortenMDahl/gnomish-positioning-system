# Gates for J4, planet clouds

Morten's report: zoomed far out, clouds next to and over the continents look as if they lie under the land, and
clouds toward the planet's edge look smeared and faint, as if under the surface.

- [x] G1 Cause found and measured on the old code (draw order, the cards' geometry, shadows, fades), numbers in EVIDENCE.
- [x] G2 A check in test_globe: every visible cloud and the Maelstrom's storm drawn above every land triangle and the sea, by frame level, draw layer and sublevel as the sandbox engine orders them, at several views including one like the reported one; it fails on the old code.
- [x] G3 Screenshots before/after of a view like Morten's (scn_globeviews.py through run_page.py), looked at, difference described.
- [x] G4 Frame time of a planet frame not worse than +10 % (same scenario before and after).
- [x] G5 Suites: test_globe (all checks and mutations), check_globezoom (through run_page.py), test_luac pass.
- [x] G6 AGENTS.md and tools/sandbox/README.md updated (test counts).

## EVIDENCE

G1. Draw order on the old code was right: in every one of the 18 views of the new check the clouds, their shadows
and the storm come after every land triangle and the sea's textures (the sky's frame is canvas level + 4, the land's
+ 2 and + 3, the sea's + 1). The fault is where they are drawn: each cloud was one flat card through its four
corners at 700 yd, a chord whose middle lies inside the planet (radius 22,000 yd), mapped without perspective. Old
code at the reported view (Maelstrom in the middle, 90,000 yd): of 1,554 image points 649 drawn where points under
the sea would be (42 %), down to 4,087 yd under it, 35 behind the planet's edge; over all 18 views 446 to 649 per
view below the sea, down to 5,755 yd. Toward the edge each card was also faded out whole (`FacingCamera`), and clouds
over land were at 0.7 alpha so the land showed through. The shadow (black, 0.3, offset by 700 yd) is not the cause:
it sits under its cloud in the same frame.

G2. `python3 only.py <sandbox> above` (scratchpad j4) on the old Globe.lua: `FAIL ... 18 views, 18 wrong` (0 of 1);
on the new: `PASS ... 18 views, 0 wrong`, heights 490 to 1,683 yd, 0 below the sea, 0 hidden, at most 1.6 px off.
Four mutations for it, all caught (one flat card per cloud, corners not lifted, back-facing pieces drawn, the sky's
frame under the land's).

G3. scn_globeviews.py through run_page.py, window 1300 x 1000, views `reported` (62,000 yd, Maelstrom in the middle)
and `edge` (a continent near the edge), old and new code (scratchpad j4/shots_final/gv_old_*.png, gv_new_*.png;
side by side j4/cmp2_reported.png, j4/crop2_reported.png, j4/crop2_edge.png). Old: the band of cloud off the
Eastern Kingdoms' west coast is pulled in onto the land and washed out (the land shows through it), the storm
north-west of it sits well inside the planet's rim, smeared, and clouds near the rim are faint. New: the same
clouds sit out toward the rim where they belong and follow its curve, the one over the coast is solid white over
the land, the rim clouds are as bright as the others (the glow tints them a little blue); the rest of the look
is unchanged.

G4. perf3.py (old and new Globe.lua in one process, interleaved, best of 30 x 60 frames, native Lua), final code:
reported 90,000 yd 0.384 -> 0.376 ms (-2.1 %); 65,000 yd 0.493 -> 0.472 (-4.2 %); Eastern Kingdoms 60,000 yd
0.475 -> 0.466 (-2.0 %); 110,000 yd 0.386 -> 0.384 (-0.6 %); sum 1.739 -> 1.698 ms (-2.3 %). (Before taking
acos out of the per-cloud edge test the sum was +6.1 %, one view +12.9 %.) Textures placed per frame at the
reported view: 73 cards -> 276 pieces with their shadows.

G5. test_globe 55 of 55 (22 of 22 mutations caught; one run beside the zoom check gave 54: the first-crossing timing check, which fails as often on the old code, 2 of 4 runs each); check_globezoom 8 of 8; test_luac 3 of 3 (Globe.lua 147/200
locals, 34/60 upvalues; GPS3D.lua untouched, 197/200 and 58/60).

G6. AGENTS.md (the planet's clouds paragraph, test_globe 55 checks) and tools/sandbox/README.md (55 checks,
twenty-two mutations, the new scn_globeviews options).
