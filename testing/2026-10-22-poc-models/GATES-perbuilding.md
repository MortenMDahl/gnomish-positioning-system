# Gates: per-building simplification (last bounded try, Stormwind Trade District)

Request: "Try it" (per-building simplification at 3k-8k so roofs stay closed); then mid-turn: "Maybe try one model first
and see how it goes" (simplify one model with its textures until it looks reasonably good with as few vertices as possible).

- [x] G1: the area split into buildings + street level, counts stated, overlay image
  EVIDENCE: whole-district split failed: pb_segment.py gave 29 parts, one of them 105,738 yd2 (streets beside the
  canals counted as "raised"); stormwind_pb_seg.png. Replaced, as Morten suggested, by ONE house first: footprint drawn
  from a top view (pb_poly.json), 353 of the game's triangles.
  ABANDON (for now): whole-district split. Reason: Morten asked for one model first; the one-model result (G3) makes it moot.
- [x] G2: the house gets a closed shell built from its own geometry (no visibility filter)
  CHECK: pymeshlab topological measures on pb_house.npz
  EVIDENCE: boundary_edges 0, two-manifold, 1 component, 62,988 triangles before simplifying
- [x] G3: simplified step by step with the game's textures; fewest triangles that still look right
  EVIDENCE: 2,492 / 1,080 / 545 / 299 / 245 triangles (pb_house_levels.png, house_test_simplified.png). Looks right
  only at 1,080 and above; at 545 and below it falls apart. The game's own model of the house is 353 triangles, so
  simplifying it saves nothing: the shell needs 3x the original to look right.
- [x] G4: the roof of the house in Morten's crop
  EVIDENCE: the opening is in the game's own model: column probes over it (tools/gps_poc_column.ts) find nothing in any
  of the WMO's 289 groups (no group filter); 15 doodads within 14 yd, highest at 112.5 yd, roof at 123-131 yd
  (tools/gps_poc_doodads.ts); terrain under it at 59.5 yd. The old filter ALSO dropped roof pieces: of the house's 353
  triangles it kept 217, the finer pass keeps 295.
- [x] G5: holes measured against a z-buffer render of every original triangle (90 x 90 yd area, 4 views)
  EVIDENCE: share of frame different from the full model: old filter 0.09 / 0.16 / 0.13 / 0.14 %; finer filter
  (145 directions, 2,048 px over 140 yd, seen >= 1 px) 0.00 / 0.00 / 0.04 / 0.02 %; finer filter with triangles under
  1 yd2 dropped 0.33 / 0.83 / - / 0.62 % (views a, b, c, d; c not rendered for that one)
  Triangles in the area: all 21,236; old filter 7,506; finer 10,715; finer minus < 1 yd2 5,438; minus < 2 yd2 3,526
- [ ] G6: cost measured in the addon
  ABANDON (for now): needs the whole-district data built with the finer filter; waiting on Morten's go. Only triangle
  counts above (estimates for the 80-yd close view, by the area ratio, unverified: finer ~35k, minus < 1 yd2 ~17.7k,
  vs the old full detail's 24,468 at 68 ms).
- [x] G7: comparison sent with an honest verdict
  EVIDENCE: house_test_simplified.png, house_test_filters.png in outputs
