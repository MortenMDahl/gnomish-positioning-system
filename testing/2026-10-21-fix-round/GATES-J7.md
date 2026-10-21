# GATES J7: the sea in the 3D view and its hand-over to the planet

Views (page sandbox, `SANDBOX_PORT=8797 SV_NOCLOUDS=1 SV_2D=1 SV_TAG=<tag> python3 run_page.py seaview 1400 900`, then
`python3 measure_sea.py <tag>`): Kalimdor north (Teldrassil, Hyjal) at 9,000 yd straight down and tilted 45, 12,000 yd
straight down; NE of Azshara at 6,000 and 10,000 yd straight down, 9,000 yd tilted 45; NE Azshara at 14,000, 17,000,
19,000, 22,000, 26,000 and 30,000 yd (the hand-over); the 2D map over Kalimdor's north at 24 px a tile. "Before" is
the baseline's addon files and data in the same (fixed) sandbox page; "after" this branch. Shots kept:
`tools/sandbox/shots/sv_{before,after}_{teld_down,azs_down,ho_19000,map2d}.png` and `sv_{before,after}.json`.

Causes (measured):
1. Triangles: the game's minimap images (and so the overview atlases made from them) draw the open sea in two tones,
   #081110 and #080d10 (8, 13, 16), split along diagonals (42 % of the open sea inside Kalimdor's tiles, 38 % in the
   Eastern Kingdoms'; the sandbox's 131 real minimap images show the same, e.g. 0_26_46 is 99.7 % the darker tone).
   Morten's Teldrassil screenshot: (8, 17, 16) 402,286 px and (8, 13, 16) 115,806 px, exactly the images' values.
2. The L line: in the minimap images of Kalimdor tiles 45, 46, 47 of row 20 (atlas 1_2_1.jpg, px 832-1024 x 256-263,
   and the east side of tile 47, px 1018-1024 x 256-320): a 4-5 px tan line (70-78, 71-73, 42-55) along the sides with
   no tile next to them; also on the planet's page Land_1_1_0 (alpha 178 there). The same kind of line (magenta) runs
   round Kalimdor's test squares at tile 0, 0.
3. The boundary: in Morten's NE Azshara screenshot the background is exactly #081110 (111,965 px) while the ground's
   tiles there (about 100 px a tile: their minimap images) are #050708, #050705, #050505 in diagonal bands: the game
   draws those images' sea darker than the images hold. Open-sea tiles drew those images (or the overview's two
   tones), so the edge of the map's tiles showed. In the planet's hand-over the overview's two tones and the line
   showed the same way (sandbox, 19,000 yd: darker tone 1.1 % of the open sea, line 44 levels off the sea round it).
   Not a cause: the planet's sea colour (Globe.lua), the same #081110 until the ground bends, and the overview images
   reaching the hand-over already faded (edge pairs at 26,000-30,000 yd within 1 level, before and after).
   Sandbox artefact found and fixed: the page's WebGL blending made the canvas partly transparent under half-faded
   layers (lighter rectangles round coasts at 19,000 yd that the game cannot have); `blendFuncSeparate` keeps it opaque.

- [x] G1 Sea evenness. Check: `measure_sea.py`: open-sea pixels (6 px or more from anything else): share of the darker
      tone, spread from the most common colour (99.9th percentile, share over 2 levels). Expected: darker tone 0 %,
      spread within 2 levels in the flat views.
      EVIDENCE: darker tone before / after: teld_down 14.3 % / 0, teld_tilt 12.4 % / 0, teld_far 12.2 % / 0, azs_down
      19.3 % / 0, azs_far 15.7 % / 0, azs_tilt 13.3 % / 0, ho_14000 14.4 % / 0, ho_17000 12.2 % / 0, ho_19000 1.1 % / 0.
      Pixels over 2 levels off: teld_down 14.6 % -> 0.05 %, azs_far 15.9 % -> 0.04 %, ho_14000 14.6 % -> 0.04 %,
      ho_19000 1.1 % -> 0.01 %; p99.9 4-7 -> 0-2 in every flat view except azs_down (7 -> 7, 0.34 % of pixels: coastal
      shading within 6 px of the coast). (26,000 and 30,000 yd: spread 8-12 before and after: the planet's shading,
      which fades in there by design.) Overview images: darker-tone pixels in the open sea at most 9 in an image
      (JPEG noise) against up to 112,240 before (test_world check).
- [x] G2 The L-shaped line. Check: largest difference along it (40 points on the line) from the sea 0.4 tile further
      out, in each NE Azshara view; the atlas pixels and the planet page's alpha there.
      EVIDENCE: before / after: azs_down 68 / 0, azs_far 57 / 0, azs_tilt 52 / 0, ho_14000 50 / 0, ho_17000 50 / 0,
      ho_19000 44 / 0, ho_22000 34 / 0, ho_26000 32 / 1, ho_30000 27 / 0. Atlas 1_2_1 along the line: 71 levels off
      #081110 before, 0 after; page Land_1_1_0 alpha there 182 before, 0 after (test_world check). Tiles 44-47 of row 20
      and 47 of row 21 left the planet's list of tiles with land (671 -> 666 on Kalimdor).
- [x] G3 The boundary between the ground's sea and the sea beyond. Check: 3 x 3 px colours on either side of six edges
      NE of Azshara (the last tiles of rows 20 and 23 against the sea beyond, tile 47 against 48, a coastal tile's sea
      against the open-sea tile next to it), in flat views and through the hand-over; largest channel difference.
      EVIDENCE: before / after: azs_down 4.0 / 0, azs_far 4.0 / 0, azs_tilt 4.0 / 0, ho_14000 4.0 / 0, ho_17000 4.0 / 0,
      ho_19000 3.0 / 0, ho_22000 0 / 0, ho_26000 1.0 / 1.0, ho_30000 0 / 0 (levels). In the game the step there was
      (3, 10, 11) levels (#050708 against #081110): open-sea tiles no longer use those images (G4).
- [x] G4 Open-sea tiles drawn in the background's colour in the 3D view, at every zoom. Check: test_world
      "open sea NE of Azshara drawn in the background's colour ...", at 2,500 yd straight down (tiles 170 px: minimap
      images); fails on the baseline and on a mutation (`OpenSeaTile` returning false).
      EVIDENCE: after: 384 minimap triangles (0 on open-sea tiles), 448 flat #081110, Kalimdor 313 of 988 tiles open
      sea; baseline: 832 minimap triangles (288 on open-sea tiles), 0 flat (FAIL); mutation: 448 on open-sea tiles,
      0 flat (FAIL). Overview check (second new test_world check): baseline FAIL (112,240 darker-tone px, line 71
      levels, page alpha 182), after PASS (9, 0, 0).
- [x] G5 The 2D map's sea consistently improved (it shares the images and the colour). Check: test_2d and test_look
      (backgrounds); the 2D map over Kalimdor's north at 24 px a tile.
      EVIDENCE: test_2d 15 of 15, test_look 35 of 35; map2d darker tone 14.1 % -> 0, pixels over 2 levels off
      14.2 % -> 0.04 %, p99.9 4 -> 1. Its live minimap tiles (from 80 px a tile) are unchanged (game images).
- [x] G6 Suites. EVIDENCE: test_world 62 of 62 (60 + 2 new), test_globe 54 of 54, check_globezoom 8 of 8 (small
      window worst step 1.79 at 14,600 yd, baseline 1.78 at the same step), test_2d 15 of 15, test_look 35 of 35,
      test_models 50 of 50, test_luac 3 of 3 (GPS3D.lua 197/200 locals, 58/60 upvalues: unchanged).
- [x] G7 Frame times (lupa, Kalimdor, 40 frames turning 1 degree each; min of two runs, the machine shared):
      EVIDENCE: before / after (ms, min): NE Azshara 2,500 yd 2.12 / 1.88-1.98, NE Azshara 6,000 yd 2.23-2.44 / 2.07-2.23,
      Teldrassil 9,000 yd tilted 3.90-3.92 / 3.80-3.96, Kalimdor north 12,000 yd 2.67-2.73 / 2.54-2.68; same triangle
      counts. The change is in mesh building only (no per-frame tables or calls).
