# Gates: proof of concept, simplified 3D building models drawn by GPS3D's own renderer

- [x] G1: real geometry exported from Morten's game files (MapExplorer's reader): Stormwind Trade District and Orgrimmar Valley of Strength, 520 x 520 yd each, with UVs and texture IDs
  EVIDENCE: tools/gps_poc_export.ts on the device: Stormwind 348,206 triangles (147 groups of WMO 7962574), 115 textures; Orgrimmar 263,723 (82 groups of WMO 7964229, 136 of 138 groups flagged interior), 77 textures
- [x] G2: hidden geometry removed by a visibility pass from above
  EVIDENCE: ID renders from 25 sky directions at 3072 px with the terrain as occluder: Stormwind 170,288 kept (seen by 2+ px), Orgrimmar 128,351
- [x] G3: simplified to several sizes with flat colours from the game's textures
  EVIDENCE: MeshLab quadric decimation to exactly 3,000 / 8,000 / 20,000 per city; colours = texture averages (vertex colours dropped: a quarter of outdoor faces near black)
- [x] G4: drawn by GPS3D's own renderer in the sandbox (RenderWorld's triangle path through ns.ExtraMeshes), old blocks off, screenshots
  EVIDENCE: branch poc-models (ad6f86a, local only): shots/poc_{sw,org}_{high,close}_*.png; grey check pocdbg_grey.png matches a z-buffer render of the same data (pv_swtex_grey.png)
- [x] G5: textured variant with the game's own textures by file ID
  EVIDENCE: 25,397 (Stormwind) / 17,791 (Orgrimmar) original triangles within 80 yd, game UVs, REPEAT wrap; 20 of 115 textures carry alpha that is not transparency (made opaque here; in the game: SetBlendMode("DISABLE"))
- [x] G6: cost and data size measured
  EVIDENCE: measure.txt (Render Lua ms while turning, Lua 5.4 in WebAssembly, textures shown): Stormwind close today 9.5 ms / 3,019; 8,000 16.5 / 5,021; 20,000 47 / 11,920; textured 66 / 16,064. Orgrimmar close today 14.5 / 3,765; 8,000 19.5 / 5,996; 20,000 65 / 13,451; textured 64 / 13,168. Data (compact estimate): 8,000 triangles ~125 KB per 520-yd square, textured ~0.6-0.9 MB per 160-yd circle
- [x] G7: depth-order problems looked for
  EVIDENCE: grey textured close-up drawn correctly by the painter's buckets (pocdbg_grey.png vs pv_swtex_grey.png); big floor triangles split to 10 yd changed only 929 of 24,468; the ground grid had to be drawn behind the models (30 yd, as for blocks); some decimation shards at 3,000-8,000; intersecting parts can still sort wrongly at some angles (not seen at these views)
- [x] G8: results sent with what is real, what is a stand-in, and what needs the game
  EVIDENCE: models3d_sw_close.png, models3d_sw_high.png, models3d_org_close.png, models3d_org_high.png sent
