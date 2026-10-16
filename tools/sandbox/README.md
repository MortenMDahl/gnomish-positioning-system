# GPS sandbox

A browser page that runs the addon files unchanged in a Lua VM (wasmoon, Lua 5.4 in WebAssembly;
Fengari as a fallback where WebAssembly is blocked), on a small imitation of the WoW UI engine.
Published privately as the "GPS Sandbox" artifact.

- `site/engine.lua`: the WoW UI engine (frames, anchors, layers, input, timers, slash commands,
  SavedVariables, GameTooltip, ModelScene with stand-in models). It returns a draw list per frame.
- `index.src.html`: the page (WebGL renderer, simulated player, chat). `python build.py` inlines the
  patched Fengari and writes `site/index.html`.
- `site/addons/` is filled at publish time with copies of `Interface/AddOns/GnomishPositioningSystem`
  (Core.lua, Data/MapTiles.lua) and `prototypes/GPS3D` (GPS3D.lua and every file in its Data folder, as listed in GPS3D.toc);
  `site/overview/` with the addon's Overview images.
- `site/minimap/`: 25 real minimap tiles (Eastern Kingdoms 30..34 x 46..50) from the game files, via MapExplorer.
- `test_engine.py`, `test_world.py`: run engine + addons in Lua 5.4 (lupa) without a browser; `test_world.py` checks the 3D view across the world, buildings included (32 checks); `check_decode.py` compares the Lua and Python decoders of every building block; `perf_buildings.py` measures frame times with and without buildings.
- `run_page.py <scenario> [w h]`: serves `site/` and drives it in headless Chromium (`scn_*.py`).
  `CSP="..." python run_page.py csp` checks the fallback under a strict content security policy.

- `site/minimap/`: 131 of the game's minimap images (Elwynn, Stormwind, Westfall, Redridge, Duskwood; exported from MapExplorer with `minimapThumbnails`, JPEG 85 %); other tiles show their part of the overview image, so they look blurrier than in the game.
