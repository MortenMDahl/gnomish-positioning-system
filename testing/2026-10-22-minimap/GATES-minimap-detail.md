# Gates: separate detail settings for the minimap (2026-10-22)

Request: "Have individual settings for each in the settings menu" (the minimap's ground and building detail, separate from the 3D window's).

- [x] G1: GPS's settings page, Minimap section: "Minimap ground detail" (default 1,200) and "Minimap building detail" (default 1,500) sliders
  CHECK: python3 tools/sandbox/test_minimap.py (check "settings page: ... detail")
  EXPECT: PASS
  EVIDENCE: test_minimap.py PASS "settings page: Minimap ground detail (1,200, 400 to 3,200) and Minimap building detail (1,500, 500 to 4,000)"; test_settings 46/46 (page order includes both sliders)
- [x] G2: changing either applies to the minimap at once (redrawn, triangles within the new budget) and is saved over a reload
  CHECK: test_minimap.py checks "Minimap ground/building detail"
  EXPECT: PASS
  EVIDENCE: PASS ground: budgets in the draw 1200 1500 -> 600 1500, ground triangles 605 -> 540, 3D window budgets 3200 4000 after the draw; PASS buildings: 600 750, 694 building triangles; PASS reload: 600 750
- [x] G3: independent: the minimap's settings leave the 3D window's budgets alone and the 3D window's leave the minimap's alone
  CHECK: test_minimap.py check "independent"
  EXPECT: PASS
  EVIDENCE: PASS independent: the 3D window at its defaults 3200 4000; minimap draws at 600 750 / 600 750, the 3D window at 2400 3000
- [x] G4: /gps minimap ground <n> and /gps minimap buildings <n> set them (clamped) and say so
  CHECK: test_minimap.py check "/gps minimap ground|buildings"
  EXPECT: PASS
  EVIDENCE: PASS: '/gps minimap ground 900' -> 1000, 'buildings 99999' -> 4000, 'ground' alone -> '400 to 3200; now 1000'
- [x] G5: suites pass: test_minimap (all, with a new mutation caught), test_settings, test_luac, test_modes
  CHECK: run each
  EXPECT: all pass
  EVIDENCE: test_minimap 38 of 38 (13 mutations caught, incl. 2 new); test_settings 46/46; test_luac 3 of 3 (Minimap.lua 34/200 locals, 10/60 upvalues); test_modes 63 of 63
- [x] G6: docs: AGENTS.md minimap paragraph, TESTING.md section 17, FEATURES.md
  CHECK: grep "Minimap ground detail" in each
  EXPECT: found in all three
  EVIDENCE: grep 'Minimap ground detail': AGENTS.md 1, TESTING.md 1, FEATURES.md 1
- [x] G7: sandbox page republished with the new Minimap.lua
  CHECK: Artifact list files, Minimap.lua size equals local
  EXPECT: equal
  EVIDENCE: Version 9; published addons/GPS3D/Minimap.lua sha256 459380bb8ca64c54... equals local
- [ ] G8: device repo synced (hashes equal), installed in _forever_ and _classic_beta_, committed and pushed to main as MortenMDahl
  CHECK: devhash vs local; apply_sync "differ 0"; origin/main == HEAD, author
  EXPECT: all equal, differ 0, MortenMDahl
  EVIDENCE: checked after the push (hashes, install, origin/main); the result is in the session report, since this file is part of that commit

Note: measured in the sandbox (Stormwind, Orgrimmar; rim 233 and 133 yd): the building slider maps almost one to one to building triangles drawn (500 -> 469-500, 4,000 -> 2,814-3,979); the ground slider changes little above 800 (Stormwind 233 yd: 400 -> 381, 800 -> 445, 1,200-3,200 -> 509), since the small view rarely needs more.
