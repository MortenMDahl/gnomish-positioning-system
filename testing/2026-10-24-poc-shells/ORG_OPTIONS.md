# S1f: Orgrimmar, both options tried (2026-10-24)

Orgrimmar is one building model (fdid 7964229) that holds the canyon walls, the canyon floor and every building. The
S1e whole-block shells made a rock lid over the city, so S1e skips that model and leaves Orgrimmar to the old blocks.
Two ways round it were tried on its 7 tiles (1_39_28, 1_39_29, 1_40_27, 1_40_28, 1_40_29, 1_41_27, 1_41_28):

- **Option 1, buildings only:** the model's cliff and floor textures dropped (`OPTION1="7964229:0,8250846,8250845,8253979"`),
  so only the buildings get shells. 3,190 faces in 119 units on the 7 tiles.
- **Option 2, two layers:** the whole model as before, plus an underside (facing down) under every region more than
  3 yd above the ground, and a second layer of shells built and baked from the triangles under those regions
  (`LAYERS=2`). Top layer 6,107 faces (1,278 of them undersides), lower layer 1,472 faces in 93 units.

Both runs used `TEX0_FILL=1`: triangles the reader gives no texture (40 % of the model's area) take the model's
texture with the most area in the tile, instead of baking grey. It is off by default, so a rebuild without it gives
the shipped S1e data.

Kalimdor totals after collecting: base (Orgrimmar skipped) 3,346 blocks / 52,197 faces / 7.7 MB pages; option 1
3,451 / 55,301 / 8.3 MB; option 2 3,567 / 59,690 / 8.6 MB.

## Pictures

`tools/sandbox/shots/org3_*.png`, three columns: old blocks (today) | option 1 | option 2.
Views: otop (straight down, 500 yd), o450 / o330 (tilted, 450 / 330 yd), ostreet / ostreet2 (from the streets).

- **Option 1:** the buildings come out as scattered shards. A block shell (shape simplified to 6 yd, pictures 0.75 px/yd) can't hold the shape of a hut or
  a tower. Without the cliffs, the canyon falls back to the raised ground, so the city loses its walls.
- **Option 2:** the rock lid is still there from above (the top layer is what you see from above, as before). Where it
  breaks up, the lower layer shows through in patches.
- **Street views:** the same in all three (no shells in view) or worse (grey planes).
- **Old blocks:** they read best. The huts, the towers and the canyon are all recognisable.

## Numbers (sandbox; 2 rounds alternating; Lua ms is the mean of the two)

| view | | old blocks | option 1 | option 2 |
|---|---|---|---|---|
| otop | ms turning | 10.9 | 8.4 | 11.1 |
| | C calls | 22,993 | 15,511 | 17,494 |
| | shell faces | 0 | 1,780 | 3,972 |
| | order errors: all / with a shell | 17.5 % / 0 | 6.2 % / 1.2 % | 8.9 % / 8.6 % |
| o450 | ms turning | 16.1 | 12.3 | 17.6 |
| | C calls | 25,574 | 18,168 | 22,029 |
| | shell faces | 0 | 2,263 | 4,989 |
| | order errors: all / with a shell | 14.5 % / 0 | 8.2 % / 1.1 % | 7.1 % / 7.1 % |
| o330 | ms turning | 12.3 | 11.1 | 15.0 |
| | C calls | 22,645 | 15,089 | 17,090 |
| | shell faces | 0 | 1,816 | 4,533 |
| | order errors: all / with a shell | 16.1 % / 0 | 4.3 % / 0.2 % | 1.8 % / 1.1 % |

- Order errors are the share of screen pixels drawn in the wrong order (order_all.py).
- "With a shell" = shell over nearer ground + ground over nearer shell + shell over shell.
- The old blocks' errors are all ground-ground: the old blocks count as ground in this measure.

## Verdict

- **Performance:** option 1 is the cheapest (−10 to −24 % Lua ms, about −30 % calls). Option 2 costs about the same
  as the old blocks (+2 to +22 % ms) with fewer calls.
- **Looks:** both look worse than the old blocks, so the shipped default stays as it is (Orgrimmar on the old
  blocks).
- **Why:** block-level shells (66.7-yd blocks, shape simplified to 6 yd, 0.75 px/yd) are too coarse for a city like Orgrimmar.
- **What would work:** the capital-city pipeline that made Stormwind (per-building units, sharper pictures), with
  option 2's lower layer for the parts under the overhangs.
