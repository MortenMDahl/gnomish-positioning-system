# Gates: distance-based detail for the game's own models, with a size slider (2026-10-22)

Request: "Yes, try the distance-based detail. Can the lowering of details be to have a filter to ignore larger and
larger parts ... can that go up and up? And is it possible to add a slider to the game to adjust the details based on sq yd?"

- [x] G1: the game's models (finer hidden-part pass) over the whole exported Stormwind square, not just 80 yd
  CHECK: 9 tiles of the pass done; triangle count written to the data
  EVIDENCE: 9 tiles done with the canals' water (95 yd) as an occluder: 208,286 of 347,235 game triangles kept; 240,346 pieces after the 10-yd cut in 425 cells; PocCity.lua 23,942,195 bytes (each cell its own function for WoW's Lua 5.1 constant limit)
- [x] G2: renderer: models in cells, each cell's parts sorted biggest first; per frame the smallest part drawn grows
  with distance (slider value up to 40 yd, then x (d/40)^2: same size on screen); cells off screen skipped;
  textures taken only when a part is first drawn and given back when unused
  CHECK: sandbox loads it; counts per frame change with the slider and with distance; no Lua errors
  EVIDENCE: PocModels.lua CityFrame + GPS3D.lua (nv/nt prefix, hiding parts no longer drawn, ns.PocCovers for blocks); sandbox shots load and draw it, no Lua errors in any run; slider changes the count (6,000 -> 2,000 budget: 5,666 -> 1,935 parts drawn). Added beyond the ask: a parts-per-frame budget (the size slider alone costs 6-67 ms depending on the view) and a distance slider (models near, today's buildings beyond)
- [x] G3: a settings slider "3D models: smallest part (sq yd)" + /gps3d poc min <n>, saved over a reload
  CHECK: slider on the settings page; value applied (drawn count changes); saved value restored
  EVIDENCE: settings list: GPS3D_PocMinArea '3D models: smallest part' [0..50], GPS3D_PocBudget '3D models: parts per frame' [1000..30000], GPS3D_PocRadius '3D models: distance' [0..400]; set 7.3/6200/95 -> 7.5/6000/100 (steps); after a reload (SANDBOX_SAVE -> new game): 7.5 2000 100; /gps3d poc min|budget|radius
- [x] G4: cost measured (native Lua, turning) at the close / near / high Stormwind views for several slider values,
  against today
  CHECK: perf script, 3 runs where it decides
  EVIDENCE: perf_poc6.py (fresh game per setting), ms turning, 2 runs: today near 7.5/7.5, close 5.4/5.3, high 10.9/10.4; 4,000 parts everywhere 8.8/8.9, 7.4/7.9, 14.0/13.3; 8,000: 15.2/16.5, 19.3/20.4, 31.2/31.5; within 70 yd + today beyond, 4,000: 15.5/16.6, 15.9/16.1, 21.8/22.3; 8,000: 22.1/23.2, 23.2/23.3, 33.7/33.3; every part within 70 yd: 35.2/35.0, 59.6/60.1, 101.3/98.9. Size slider alone (1 run): 10 sq yd 52.4 / 67.1 / 34.2; 30: 29.5 / 25.4 / 6.1; 60: 24.0 / 16.8 / 4.4. Lua memory: 87 MB -> 183 MB with the city's cells built -> 196 MB drawing 8,000 parts. (The first perf_poc5 runs in one game were higher and noisy: earlier settings' textures crowded the pool; superseded.)
- [x] G5: look: in-addon screenshots at the same slider values, and how much of the frame changes against all parts
  CHECK: sandbox shots; pixel difference against slider 0
  EVIDENCE: outputs/models_smallest_parts.png, outputs/models_near_far.png (viewed). Pixel difference against every part: ABANDON - rendering every part in the sandbox (240k parts) per view is too slow in WebAssembly; judged by eye instead
- [x] G6: answer with the recommendation (which value is near today's cost, how it looks)
  EVIDENCE: reply
