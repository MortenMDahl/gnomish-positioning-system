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
- `test_engine.py`, `test_world.py`, `test_look.py`: run engine + addons in Lua 5.4 (lupa) without a browser; `test_world.py` checks the 3D view across the world, buildings included (52 checks); `test_look.py` checks the window look, "minimap rings" (27 checks: what each window shows, the rings and what they do, tooltips, layout at the smallest window size); `check_decode.py` compares the Lua and Python decoders of every building block; `perf_buildings.py` measures frame times with and without buildings.
- `run_page.py <scenario> [w h]`: serves `site/` and drives it in headless Chromium (`scn_*.py`; `DSF=2` for sharper screenshots; `scn_look.py` takes close-ups of both windows). It needs `site/wasmoon/index.js` and `fengari-web.js` (wasmoon 1.16.0 and fengari-web 0.1.4 from npm, not kept in the repository).
  `CSP="..." python run_page.py csp` checks the fallback under a strict content security policy.

- `site/minimap/`: 131 of the game's minimap images (Elwynn, Stormwind, Westfall, Redridge, Duskwood; exported from MapExplorer with `minimapThumbnails`, JPEG 85 %); other tiles show their part of the overview image, so they look blurrier than in the game.
- `make_standins.py`: draws stand-ins in `site/ui/` for game art the sandbox has no copy of (the dark disc behind the rings, the hover glow, the red close-button atlases). They only approximate the game's art: judge layout in the sandbox, the art in the game. GPS's own icons come from `scripts/make_media.py`.
- Engine: `Texture:SetAtlas` and the button atlas setters draw `atlas:<name>` (mapped to images in the page's `UI_FILES`); strings sent to the page now escape backslashes, so texture paths such as `Media\Needle` arrive intact.
