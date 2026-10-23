# Gates: drop whole pieces, not single triangles (2026-10-23)

Request: "Go ahead with your proposed next step" (join triangles into whole walls, roofs and beams, so far buildings
drop whole pieces instead of breaking into shards; keep the 4,000-part cap).

- [x] G1: pieces built from the game's triangles: neighbours sharing an edge, the same texture and facing within 30 degrees join one piece; each part ranks by its whole piece's area
  CHECK: counts (pieces, triangles per piece, biggest piece); PocCity.lua rebuilt
  EVIDENCE: 38,694 pieces from 208,286 game triangles (median 2 triangles, biggest 2,018 triangles / 15,807 sq yd: a street). Ranking changed twice after looking: by piece area the streets took the budget (shots poccP_*: almost no buildings); now each piece ranks by its area per part, streets and squares (86 flat pieces over 300 sq yd, 14,673 of 240,346 parts) after the buildings; a piece's parts all sit in the cell of its middle. PocCity.lua rebuilt (24,723,115 bytes)
- [x] G2: drawn in the addon (sandbox), no Lua errors, budget still holds
  CHECK: sandbox shots at 4,000 and 8,000 parts; parts drawn <= budget
  EVIDENCE: sandbox shots poccV_sw_{near,close,high}_b{4000,8000}.png, no Lua errors; parts drawn 3,560-3,959 at 4,000 and 7,251-7,737 at 8,000 (perf_poc6)
- [x] G3: fewer shards than the triangle version, measured: how many drawn triangles have a dropped neighbour of the same piece (piece-partial), triangle vs piece version, same views and budget
  CHECK: count from the drawn set in the sandbox (Lua)
  EVIDENCE: shards.py (on-screen cells only): parts in partly drawn pieces, triangle version 35.3 / 61.3 / 63.9 % at 4,000 and 44.5 / 49.1 / 59.1 % at 8,000 (near / close / high); piece version 0.0 % in all six. (By construction: a piece is now kept or dropped whole.)
- [x] G4: cost at near / close / high, today vs triangle vs piece version, fresh game per setting, 2 runs
  CHECK: perf_poc6.py
  EVIDENCE: perf_poc6.py, ms turning: today near 7.6, close 5.3, high 10.4; triangles 4,000: 9.6 / 7.6 / 14.0 (earlier runs 8.8-8.9 / 7.4-7.9 / 13.3-14.0); pieces 4,000: 6.8, 7.3 / 8.0, 8.6 / 12.8, 12.9; pieces 8,000: 12.1, 14.3 / 17.1, 18.1 / 26.8, 27.5
- [x] G5: side-by-side images (triangle version vs piece version vs today) sent with the verdict
  EVIDENCE: outputs/models_whole_pieces.png (viewed); close-view crop checked: torn surfaces gone, but buildings far away are still incomplete (walls without roofs as loose panels)
