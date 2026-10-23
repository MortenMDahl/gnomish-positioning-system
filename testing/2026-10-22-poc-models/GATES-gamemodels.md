# Gates: the game's own models rebuilt in the addon: cost and look (2026-10-22)

Request: "Is it possible to rebuild them in the addon? What would the performance and in game look like then?"

- [x] G1: finer hidden-part pass over the close Stormwind view's 80-yd circle (the area the textured data covers)
  CHECK: pb_vis.py counts
  EVIDENCE: 145 directions, 3,072 px over 220 yd: 75,403 game triangles in the 170-yd box, 41,788 seen; in the 80-yd circle 63,208 game triangles (pbv80_vis.npz)
- [x] G2: two versions as addon data with the game's triangles, UVs, textures (back-seen flipped, both-sides flagged, cut to 10 yd): all visible (texfine) and visible minus pieces under 1 yd2 (texfine1)
  CHECK: counts written; PocData.lua loads in the sandbox
  EVIDENCE: texfine 32,875 game triangles (33,875 after the 10-yd cut; 7,779 flipped, 6,803 both sides); texfine1 18,475 (19,397; 3,049 flipped, 5,252 both); sandbox chat: 'stormwind 33875 triangles', 'stormwind 19397 triangles'
- [x] G3: native Lua cost at the close Stormwind view, turning and still: today / old full detail (tex) / texfine / texfine1
  CHECK: perf script (same method as perf_poc3: Render's Lua ms, texture calls)
  EVIDENCE: perf_poc4.py, 3 runs, ms per frame turning: today 5.36 / 5.22 / 5.42 (2,966 shown, 14,675 calls); old full detail 63.99 / 67.57 / 64.39 (20,548 shown); texfine 124.13 / 127.19 / 130.89 (26,964 shown, 133,360 calls); texfine1 66.72 / 67.22 / 79.44 (16,248 shown, 81,174 calls)
- [x] G4: in-addon screenshots (sandbox) of today / texfine / texfine1 at the close view
  EVIDENCE: shots/poc_sw_{close,near}_{today,texfine,texfine1}.png -> outputs/game_models_in_addon.png (viewed)
- [x] G5: data size measured (per 80-yd circle) and a labelled estimate for all of Stormwind
  EVIDENCE: Lua text for the 80-yd circle: texfine 3,259,548 bytes, texfine1 1,906,762 bytes. Estimate (unverified): the 520-yd export square ~101k triangles after the same filter (29% of 348,206) -> ~10 MB at 98 bytes per triangle
- [x] G6: answer sent with numbers and what differs in the real game
  EVIDENCE: reply with the numbers and what differs in the real game
