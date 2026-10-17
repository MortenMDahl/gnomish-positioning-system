# Rolling back the game's models in the 3D view

Saved on 2026-10-17, just before the 3D view started drawing the game's own models (props, trees and buildings) on top of the simplified building shapes. These are the files as they were before that change, so the change can be undone later.

## What changed

- `prototypes/GPS3D/Models.lua` (new): picks and places the game's own models.
- `prototypes/GPS3D/Data/Models_*.lua` (16 new files, 8.1 MB): where every model stands.
- `prototypes/GPS3D/GPS3D.lua`: small hooks only. It hands a few of its functions to `Models.lua` (on `ns`), calls `ns.UpdateModels` from `Render`, lets `ns.ModelsCover` skip building blocks, adds the models' lines to `/gps3d test` and to the debug log, and tells the models when *Buildings* is switched (`SetDetail`). These are the 20 changed lines of a diff against the saved copy.
- `prototypes/GPS3D/GPS3D.toc`: the 16 `Data\Models_*.lua` lines and `Models.lua`.
- New scripts: `scripts/browser_export_models.js`, `scripts/export_models_node.ts`, `scripts/build_models.py`. The raw export is `data/models.json`.
- Sandbox: `tools/sandbox/site/engine.lua` gained stand-ins for the models (boxes, load timing, `SANDBOX_WMO`). These additions are harmless to the old code. Also changed: `index.src.html` and `site/index.html` (file list, buttons, notes), `test_settings.py` (five more controls), plus the new `test_models.py`, `perf_models.py` and `scn_models*.py`.
- Docs: AGENTS.md, TESTING.md (section 10 and the known risks), PERFORMANCE.md (last section), INTEGRATION_PLAN.md (one paragraph), tools/sandbox/README.md.

## Way 1: switch it off, without touching any files

Open Options, then AddOns, then Gnomish Positioning System, then *3D view*. Set:

- *Buildings close up* to **Simplified shapes**
- *Props and trees* **off**

You can also type `/gps3d models buildings simple` and `/gps3d models props off`.

The 3D view then draws exactly what it drew before. No models are chosen, and no building block gives way. What still remains:

- the 8 MB of model data loaded at login;
- an empty check each frame;
- the `models` lines in `/gps3d test`.

## Way 2: put the old files back

1. Copy `GPS3D.lua` and `GPS3D.toc` from this folder over `prototypes/GPS3D/GPS3D.lua` and `prototypes/GPS3D/GPS3D.toc`. Then delete the line `Data\Detail_1_4.lua` from that TOC: since caves and mines are left out of the building meshes (later on 2026-10-17), map 1's meshes fit in three files and that fourth one is gone.
2. Delete `prototypes/GPS3D/Models.lua` and `prototypes/GPS3D/Data/Models_*.lua`. Because the old TOC no longer lists them, leaving them in place does no harm, but they would still be copied into the game folder.
3. Copy the GPS3D folder into the game's AddOns folder again and `/reload`.

The checksums of the saved files, as they were on your computer before the change (SHA-256, first 16 characters):

- `GPS3D.lua` 79c296b8b146ea9c
- `GPS3D.toc` c1eb1a537760ef1c

The scripts, the sandbox files and the docs can stay. Nothing else reads them, and the sandbox's stand-ins do nothing without `Models.lua`. Taking them out too would leave the sandbox tests `test_models.py` and `test_settings.py` (the five model controls) to remove or revert.

If the repository has been committed since then, `git log -- prototypes/GPS3D/Models.lua` finds the commit that added the models, and `git revert` of that commit is the cleaner way.
