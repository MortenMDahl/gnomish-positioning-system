# Gates: whole buildings at a distance + back sides skipped (2026-10-23)

Request: "Try the whole-building approach. Also ... the back side of that building does not really need to have a
texture. Is that something we can integrate?"

- [x] G1: the district split into buildings from the game's pieces (pieces touching within 0.6 yd join; streets and squares apart; very large joined structures split), counts and an overlay image checked
  CHECK: pb_buildings.py counts; overlay png viewed
  EVIDENCE: pb_buildings.py: 272 touching groups; 10 giants cut by spectral bisection of the contact graph (45 yd / 1,500 parts limits); 1,363 small bits merged into the unit they touch most -> 922 buildings (median 107 parts, 25.9 yd across; 90th percentile 694 parts, 55.4 yd; 48 under 10 parts) + 349 street cells; overlay pb_buildings.png viewed (dotted, hard to judge); in the shots one timber upper storey is a separate unit from its stone base (drawn without it at 8,000): the split is imperfect
- [x] G2: back sides: each building's pieces grouped by facing (8 compass sectors + up + down; two-sided parts apart); per frame a group facing away from the camera is skipped whole: no projection, no texture, no budget
  CHECK: count of parts skipped as back-facing per view; no visible holes in front faces (shots)
  EVIDENCE: pb_units.py: 6,829 facing groups in 1,271 units; 75,222 of 240,346 parts are seen from both sides (always drawn). units_check.py: back-facing parts skipped near / close / high: 4,146 / 6,795 / 8,924 (210 / 632 / 1,044 groups) = 7 / 6 / 5 % of the front-facing parts of all buildings on screen (52,293 / 106,164 / 164,350). Shots: no holes in front faces seen
- [x] G3: whole buildings: per frame the buildings on screen are ranked by on-screen size per part (front-facing parts only) and drawn whole until the parts budget; buildings beyond it are not drawn (map picture); streets after buildings
  CHECK: per view: buildings drawn whole / partly (must be 0 partly, apart from the size floor if set) / not drawn
  EVIDENCE: units_check.py, 4,000 / 8,000 parts: near 26 / 43 of 203 buildings drawn whole; close 27 / 41 of 532; high 42 / 69 of 920; partly drawn 0 in all six; parts used 3,998-4,000 / 7,997-8,000
- [x] G4: cost at near / close / high, today vs pieces version vs buildings version, fresh game per setting, 2 runs; texture objects in use
  CHECK: perf script
  EVIDENCE: perf_poc6.py (fresh game per setting), ms turning, 2 runs: today 6.3 / 4.7 / 8.9 (this session; earlier 7.5 / 5.3 / 10.4); whole buildings 4,000: 8.1, 7.7 / 10.1, 10.4 / 12.9, 13.1; 8,000: 14.0, 12.8 / 19.6, 18.1 / 27.8, 33.3 (near / close / high); pieces version (earlier today): 4,000 6.8-7.3 / 8.0-8.6 / 12.8-12.9. Texture objects in use: ABANDON - not counted separately (the drawn parts are the textures in use: 4,000 / 8,000)
- [x] G5: look: shots at 4,000 and 8,000 parts, compared with the pieces version and today, sent with the verdict
  EVIDENCE: outputs/models_whole_buildings.png (viewed)
