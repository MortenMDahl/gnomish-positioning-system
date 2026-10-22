# GATES-A5: building and model data load on demand (perf round, review J9 item A5)

Branch `perf-a5`, worktree `/home/claude/wt/P5`. Same scenario before and after: the shipped data, Lua 5.1 on this
machine (2 cores, another agent's tests running alongside) through `testing/2026-10-22-perf-round/a5_loadtime.lua`
(the review's `loadtime.lua` method: each data file parsed and run as the client would, the Lua heap after a full
collection, the fastest of 5 runs), and the sandbox (`tools/sandbox/test_ondemand.py`, `perf_buildings.py`,
`run_page.py buildings`). "Before" is the commit this branch starts from (d8cee5c), extracted with `git archive`.

**14 of 14 gates met.**

- [x] G1 Login: no `Detail_*` / `Models_*` file is loaded at login. Check: `a5_loadtime.lua 5 prototypes/GPS3D/GPS3D.toc`.
      Expect about 30 ms and 5 MB.
      EVIDENCE: before `69 files 60.5 MB on disk 224 ms 59.3 MB heap`; after `34 files 6.2 MB on disk 24 ms 4.8 MB heap`
      (the review measured 238 ms / 59.6 MB before). Sandbox (Lua 5.4): GPS3D with everything 592-704 ms, +59.9 MB;
      on demand 53-71 ms, +5.4 MB. The page's boot: 1,292 ms -> 329-391 ms.
- [x] G2 First-use hitch: every data addon loads within 50 ms in Lua 5.1. Check: `a5_loadtime.lua` per data addon TOC.
      EVIDENCE (parse + run, MB on disk / heap): EK1 21 ms (6.0/6.0), EK2 21 ms (5.9/5.9), EK3 21 ms (6.0/6.0),
      EK4 8 ms (2.3/2.4), Kalimdor1 21 ms (5.8/5.9), Kalimdor2 22 ms (6.0/6.0), Kalimdor3 17 ms (4.8/4.8),
      Instances 35 ms (9.9/9.9, 13 files), Models 28 ms (7.7/7.8, 16 files). One addon per continent instead, measured
      the same way: Eastern Kingdoms 73 ms (20.2 MB), Kalimdor 60 ms (16.6 MB): hence one addon per band (nine folders,
      all named `GPS3D_*`, so "copy every GPS3D folder" is the one instruction). Sandbox (Lua 5.4): EK3 58-63 ms;
      in the page (WebAssembly) 35-188 ms per band.
- [x] G3 Only what the view needs. Check: test_ondemand.py.
      EVIDENCE: `PASS login: no data addon loaded, no building or model data in memory loaded [], Eastern Kingdoms tiles
      with buildings 0, models no`; `PASS opening the view at Stormwind loads only the band(s) within a tile of the
      building reach there, before the first frame loaded ['GPS3D_EK3'], expected ['GPS3D_EK3']; first frame 57 blocks
      raised`; `PASS the game's models (GPS3D_Models) never loaded with the default settings`; `PASS props on and the
      game's buildings chosen: the models load with the view loaded ['GPS3D_Models', 'GPS3D_EK3']`; `PASS the Eastern
      Kingdoms from 12,000 yd, tilted 55, turning round: no band loaded while turning (none is drawn) ... equal over 36
      views`.
- [x] G4 No loss of detail: the drawn view equals the full path. Check: test_ondemand.py (the whole draw state: every
      shown texture's frame, layer, sublevel, image, 8 corner offsets, 8 texture coordinates, colour, alpha, every text,
      and every model actor's model, position, turn and scale, compared as sorted lists against a game that loaded every
      data file into GPS3D at login), also with the full path from the code before the change (`A5_FULL=<old GPS3D>`).
      EVIDENCE: 41 of 41 with the new code as the full path, 41 of 41 with the old code as the full path. Views: Stormwind
      as the view opens (4,529 textures and actors, equal); the tile with the most building data of every data addon (EK1 31,31,
      EK2 29,35, EK3 30,48, EK4 35,54, Kalimdor1 27,13, Kalimdor2 40,28, Kalimdor3 29,48, and maps 30, 309, 509 of the
      instances) straight down and tilted 45, 20 views, every one `equal`, with 26 to 77 blocks and 2,895 to 3,998
      building triangles raised and 3,849 to 5,377 textures; Goldshire (255 model actors) and Orgrimmar with the game's models on, `equal`;
      the 36 far views of G3 `equal`; the heights read where no band was loaded `146.79 vs 146.79 yd`. The index's
      highest building point per tile (which TileTop now reads) against the strings: `859 tiles, 0 different`.
      Page (`run_page.py buildings`, SANDBOX_PORT=8799, 12 views): 0 pixels differ between before and after outside the
      status bar and the 3D window's title and footer bands; those bands' fade differs between two runs of the same code
      too (stormwind base/base2 6.593 %, new/new2 6.593 %; in the last run the bands differed in a different shot).
      perf_buildings.py: every row's textures shown, blocks and building triangles the same before and after.
- [x] G5 Ahead of need. Check: test_ondemand.py flights at 120 yd a frame, 330 yd straight down, along the rows with
      buildings from 3,000 yd north of the first, both continents; every frame compared with the full path.
      EVIDENCE: `PASS flight over the Eastern Kingdoms (311 frames ...): ... then in this order ['GPS3D_EK1', 'GPS3D_EK2',
      'GPS3D_EK4'], the nearest tile of each [1413, 1467, 1511] yd away when it loaded (late: [])`; Kalimdor (607 frames)
      `[1511, 1514] yd`; `PASS ... every frame the same blocks raised, triangles and pending blocks as with everything
      loaded at login` (3,004 and 17,028 blocks raised over the flights). Mutation: the reach without the tile of
      look-ahead (`R = DETAIL_RANGE`) fails both flight checks (`[933, 978, 978] yd`, `[982, 942] yd`).
- [x] G6 Not loaded yet (combat). Check: test_ondemand.py, `SANDBOX_COMBAT(true)` before the view opens.
      EVIDENCE: `PASS in combat: nothing loaded, the view drawn exactly as with buildings off, no Lua error loaded [];
      1261 textures; equal`; `PASS /gps3d test in combat says the buildings wait for combat to end ... EK3 waits for
      combat to end`; `PASS combat over: the band loads and the view is drawn exactly as with everything loaded loaded
      ['GPS3D_EK3']; equal`. Whether the game would allow LoadAddOn in combat is not known; the code does not try.
- [x] G7 Missing folder. Check: test_ondemand.py with the four EK bands refused as MISSING, 60 frames moving.
      EVIDENCE: `PASS a band not installed: said once in chat per band, LoadAddOn not asked again every frame ... 2 chat
      lines, 2 LoadAddOn calls over 60 frames`; `PASS /gps3d test names the missing folders ... data missing: GPS3D_EK3,
      GPS3D_EK4; copy every GPS3D folder into Interface\AddOns and /reload`.
- [x] G8 Per-frame cost. Check: test_ondemand.py; perf_buildings.py three runs each, before and after, interleaved.
      EVIDENCE: `PASS the check run before every frame makes no garbage (10,000 calls, the camera still) 0.06 KB; 1.49 us
      a call (sandbox)`. Stormwind Trade District, buildings 4,000, turning 3 deg/frame: before 5.2 / 6.0 / 7.7 ms,
      after 6.0 / 5.9 / 6.0 ms; Orgrimmar 5.1 / 5.1 / 5.9 vs 5.3 / 5.4 / 5.2 ms; buildings off 1.4-1.5 vs 1.5-1.6 ms
      (noise; same counts in every row). The camera's floor now reads the ground under the camera only when that tile's
      highest point could hold it up (exactly the same floor; one GroundHeight call fewer per camera move far out).
- [x] G9 New checks fail on the code before. Check: `A5_OLD=<GPS3D folder of d8cee5c> python3 test_ondemand.py`.
      EVIDENCE: `28 of 41 checks passed`: the 13 that fail are the login (2), the opening, the garbage check, both
      flights, models loading with the view, a height loading its band, combat (2), the combat self-test line, and the
      missing folder (2); the 28 that pass there are the drawing-equality checks (the old code loads everything). Two
      more mutations of the new code, each caught: the camera floor without its TileTop gate fails the far-view check
      (`loaded ['GPS3D_EK3', 'GPS3D_EK2', 'GPS3D_EK1']` while turning); the reach without its tile of look-ahead fails
      both flights.
- [x] G10 Generators. Check: the shipped Detail strings turned back into the export's JSON (scratchpad), then
      `build_detail.py ... --root <empty folder>` and `build_models.py data/models.json --root <folder>`, `cmp` against
      the moved files; then both run into `prototypes/`.
      EVIDENCE: `20 identical` (Detail), `16 identical` (Models); run into `prototypes/` git shows every data file as a
      pure rename (72 renames, no content change); the TOCs, `Link.lua` files and `Data/DetailParts.lua` are the
      generators' output; GPS3D.toc's Detail and Models lines replaced by `Data\DetailParts.lua` (+ `OnDemand.lua`).
- [x] G11 The page. Check: `python3 build.py`, `SANDBOX_PORT=8799 python3 run_page.py buildings` on before and after.
      EVIDENCE: build.py writes the addon list from the TOCs (`GPS3D_EK1 (on demand)` ...); boot `both addons loaded in
      329-391 ms` (before 1,292 ms); `/gps3d test` in the page lists `EK1 loaded (111 ms), ...`; screenshots as in G4.
- [x] G12 Lua 5.1 limits. Check: test_luac.py.
      EVIDENCE: `PASS every shipped file compiles with Lua 5.1 (14 code files, 81 data files)`; GPS3D.lua `main chunk
      195/200 locals`, `most upvalues 45/60` (both unchanged); OnDemand.lua 16/200, 9/60. No new main-chunk local in
      GPS3D.lua (the hooks are on `ns`).
- [x] G13 Suites (from tools/sandbox, the code as committed). EVIDENCE: test_world 62 of 62, test_terrain 5 of 5 (its
      numbers identical to the code before: 7,700 morphing tiles, 15,646 edges, 728 tiles at the hand-over), test_blocks
      8 of 8 (output identical to the code before but for the milliseconds), test_models 50 of 50, test_camheight 9 of 9,
      test_globe 55 of 55, test_quests 37 of 37, test_look 35 of 35, test_luac 3 of 3, test_ondemand 41 of 41.
      test_terrain first failed 2 of 5 here: its views put the camera somewhere new by setting the camera's fields
      and reading the height there before any frame (the buildings not yet loaded, so the orbit height came from the
      ground grid instead of the roofs); fixed in the code, not the test: a tile's buildings now load the moment anything
      reads them (`TileBlocks` -> `ns.DetailFor`), so every reader gets what it got with everything loaded at login.
- [x] G14 Docs. EVIDENCE: AGENTS.md (the buildings and models paragraphs, a *Data on demand* paragraph with the
      numbers, the generators, deploy: copy every `prototypes/GPS3D*` folder, test_ondemand in the list); PERFORMANCE.md
      ("Applied (2026-10-22, perf round A5)" with the before/after table; removed from "Ideas looked at and not done");
      TESTING.md (section 0: the folders to copy; section 6: the `world data`, `data on demand`, `models data` rows;
      section 7 item 7: what to look at in the game; a row in the risks table); tools/sandbox/README.md (build.py,
      site/addons, the engine's LoadAddOn, test_ondemand).

## Needs the game

- The client's own cost of `C_AddOns.LoadAddOn` on a 6 MB data file (expected near the Lua 5.1 parse above, 20-40 ms
  on a gaming PC) and whether it shows as a stutter (TESTING.md section 7 item 7).
- That the client loads a load-on-demand addon whose TOC says `## Dependencies: GPS3D` and that `Link.lua`'s
  `select(2, ...)` gets the addon's namespace (as for any addon file).
- Whether `LoadAddOn` would work in combat (the code never tries; the buildings wait for combat to end).
- How the AddOns list shows the nine "GPS 3D data: ..." entries.
