# GPS × MapExplorer — integration plan

Analysis of 2026-10-13, updated the same day for the target flavour: **WoW Forever** (launches 2026-11-04; beta interface 16001). That suits MapExplorer, whose default product `wow_classic_beta` *is* Forever and whose client-database field layouts are numbered as Forever has them. Sources: this repo, [ClassicWowMapExplorer](https://github.com/Coldensjo/ClassicWowMapExplorer) @ `4eddd68` (MIT), the WoW API docs on warcraft.wiki.gg, and Carbonite/HereBeDragons source as precedent.

## Status (2026-10-13)

Steps 1 and 2 are done but untested in game. The tile list and overview images were exported from the Forever client through MapExplorer in the browser: 48 maps with terrain tiles, 3,322 tiles (Eastern Kingdoms 736, Kalimdor 988, Zephras Isle 72, plus Forever's other maps and instances), 63 overview atlases. The addon was rewritten as a 2D map that draws the game's own minimap images by FileDataID with the bundled overviews underneath, and shrank from about 600 MB to 3.3 MB. It was checked outside the game against a stubbed WoW API with the real data: panning, zooming around the cursor, the switch between overview and live tiles, map switching, following the player, the arrow's position, and that overview and live tiles land on the same spot. Step 3 is done but untested in game too: the GPS3D prototype now draws the real Northshire tile (1-yard mesh, 7,262 triangles, minimap-textured ground, coloured walls, back-face culling, 512 depth buckets) with models on top. Checked outside the game: its triangles, rasterised from the addon's own vertex offsets and texcoords, reproduce the browser render's abbey and orientation, and models line up with the terrain to 0.0 px. Both addons have self-tests (`/gps test`, `/gps3d test`), and `TESTING.md` is the step-by-step in-game test. In-game testing is waiting for access to the game. Next after testing: the full 3D export (step 4).

## Bottom line

The 3D rendering cannot be brought into the game. An addon can only draw 2D textures, text and single M2 models in model frames; it has no file or network access, no terrain/WMO meshes and no shaders. MapExplorer is a browser app (TypeScript, three.js/WebGL) that reads the game's CASC storage directly, so its renderer has no in-game equivalent.

What *can* be inherited is its data pipeline, and that is where the big win is. GPS's 600 MB of tiles are re-encoded copies of the game's own minimap images (checked visually: `Tiles/1415_30_12.tga`, `1945_10_10.tga` are minimap renders). MapExplorer already knows, for every 533-yard ADT tile, the FileDataID of that minimap image (WDT `MAID` chunk, `src/formats/wdt.ts`). An addon can draw any game texture by FileDataID with `Texture:SetTexture(fileID)`, which is exactly how Carbonite drew its terrain "detail map" (`NxMap.lua`, `f.texture:SetTexture(txname)` with IDs from `NxMapData.lua` `KalMapBlks`). So GPS can ship a small Lua table of IDs instead of the images: roughly 600 MB → well under 5 MB (estimate; tile counts not yet measured on your client).

## GPS today

The addon is a standalone frame (`/gps`) that tiles three pre-cut continent images. There are 3,116 uncompressed 24-bit TGA tiles of 196,652 bytes each, 593.6 MB deployed (`deploy_log.txt`), 823 MB in the working tree with the source PNGs. The Eastern Kingdoms and Kalimdor sources are both exactly 7000×12000, so they were resampled and no longer sit on the world grid; Outland is 5632×5632 = 22×256, which looks native. Because nothing is tied to world coordinates, GPS cannot show the player or line up with Blizzard's maps.

Issues found while reading the code:

| Where | Issue |
|---|---|
| `GnomishPositioningSystem.toc:1` | `## Interface: 110007, 110100` is retail. For Forever use the Forever interface number (16001 in beta; confirm at launch). The deploy path in `AGENTS.md` points at `_anniversary_`, which will need to change to Forever's folder. |
| `Core.lua:121-132` | While panning, `OnUpdate` calls `UpdateTiles()` every frame, which releases every tile and calls `SetTexture` again on all visible ones. Pan by moving one canvas frame instead, and re-acquire tiles only when the visible set changes. |
| `Core.lua:175-206` | No level of detail: at zoom 1.0 every tile of a continent (up to 1,316 textures) is drawn at once. |
| `Core.lua:107` | Wheel zoom is around the frame centre, not the cursor. |
| `Core.lua:73` / `:77` | `OnMouseUp` is set twice; the first handler is dead. |
| `scripts/map_processor.py:9-10` | Duplicate `"Kalimdor_HighRes.png"` key (harmless, last wins). |
| `AGENTS.md:19-22` | Describes a `hooksecurefunc(WorldMapFrame, "OnMapChanged")` hook that the code does not have. |

## How the two fit together

**Offline step (Bun/Node, reusing MapExplorer code).** A new script, e.g. `tools/exportGps.ts`, opens your install with MapExplorer's `CascStorage` + `NodeSource` (product `wow_classic_beta`, which is Forever), parses each continent's WDT and writes `MapTiles.lua`: per continent the minimap FileDataID of every tile, keyed `y*64+x`. WDT FileDataIDs: Azeroth `775971`, Kalimdor `782779` (both in MapExplorer's `KNOWN_MAPS`); Forever's new zones (e.g. Zephras Isle) need their WDTs looked up in Map.db2, which MapExplorer's own comment already plans for. Outland is out of scope for Forever, so the 484 Outland tiles and `MapData.lua [1945]` can go. The same run bakes a small zoomed-out overview from `MapExplorer.minimapThumbnails(..., 32)`, the routine `tools/probe.ts` already uses for overview mosaics, and saves it as a few BLP/TGA atlases. IDs must come from your client's own WDTs; the retail listfile IDs for Eastern Kingdoms will not match Forever terrain.

**In-game.** Tiles live on the ADT grid, so placing things is arithmetic: a tile is 533⅓ yards, and with world x north and y west, `tx = floor(32 - y/533.33)`, `ty = floor(32 - x/533.33)` (MapExplorer `tileOf`, `tests/coordinates.test.ts`). The player comes from `UnitPosition("player")`, which works outdoors only (nil in dungeons, raids, battlegrounds). Blizzard's maps line up through `C_Map.GetWorldPosFromMapPos(uiMapID, pos)`, available in Forever 1.60.1, which gives the world corners of any UiMap (1414, 1415 and every zone). HereBeDragons does the same and can be embedded instead of rewriting it.

**Where to draw it.** Two options. Keep the standalone frame and fix its renderer, or register a data provider on `WorldMapFrame` (the MapCanvas map, also used in Classic flavours; HereBeDragons-Pins calls `WorldMapFrame:AddDataProvider` on every flavour). The second makes GPS a terrain layer under Blizzard's own map, with zoom, pan, quest/flight pins and other addons' pins for free. I recommend the data provider as the target, keeping the standalone frame only if you want a separate full-screen view.

**Level of detail.** Zoomed out, draw the baked overview atlas (a handful of textures). Zoomed in, draw live tiles by FileDataID only for the visible grid cells, from a pooled set of about 30–60 textures. The game handles mip levels of the minimap BLPs itself.

## Measured in the Forever client (2026-10-13)

Read through MapExplorer in the browser, against the `_classic_beta_` (Forever 1.60.1) install. Eastern Kingdoms has 736 ADT tiles and Kalimdor 988, each with a minimap image, a map texture and its normal map; Forever's own maps have their own WDTs (Zephras Isle 2991: WDT 7198644, 72 tiles). Minimap images are **512×512** per tile (about 1 px per yard), twice what older clients ship, and minimap FileDataIDs match the community listfile (Elwynn 32_48 is 204493). Map textures are 512×512 too, but show terrain only, without buildings or baked shadows, so the minimap stays the better 2D layer.

Per tile, MapExplorer also gives a 129×129 height grid (about 4 yards apart), holes, water surfaces, area IDs, and every placement: the Northshire tile (32_48) has 785 M2 doodads (76 distinct models), 8 WMOs, 289 creature and 50 object spawns. WMOs are far too detailed to draw in an addon (Northshire Abbey is 30,119 triangles; one Forever WMO on that tile is 957,754).

What works well: baking the WMOs into the height grid, a "surface model", so buildings rise out of the terrain as blocks while the minimap image paints their roofs. Rendered in the browser with the same perspective method the addon uses, the abbey reads clearly at 129×129 and still at 65×65 (4,096 quads per tile). Baking trees the same way does not work: canopies turn the forest into lumpy hills. Trees should either stay painted on the minimap or be real models in a ModelScene near the camera. Better still for buildings near the camera: real but simplified building meshes. For Northshire Abbey, rendering it from 26 directions and keeping only the triangles seen from outside left 12,316 of 30,119 (the rest are interiors); simplifying that shell with meshoptimizer to 1,467 triangles gave a shape very close to the full model, while simplifying the whole mesh to 572 gave a lumpy blob. Each triangle is one addon texture with two corners pinned together; flat-coloured (roofs from the minimap, walls from the average colour of the WMO's own texture) it already reads well, and `SetTexCoord`'s per-corner form could put the WMO's real textures on it. So the plan for buildings is levels of detail: baked into the heights from far away, the simplified shell (a few hundred to ~1,500 triangles) for the few buildings near the camera. WMOs probably cannot go into a ModelScene (`/gps3d model 106965` tests it); M2 props and trees can, as real models near the camera.

**Chosen approach for buildings (and any other model): a fine height map turned into an adaptive mesh.** For each tile, take the terrain heights at 1-yard spacing (534×534), raster every WMO into it from above keeping the highest point, then turn that grid into a mesh and simplify it with meshoptimizer to a maximum height error (absolute). Flat ground collapses into a few big triangles; walls and roof edges keep many small ones. On the Northshire tile the whole tile, abbey included, is 7,262 triangles at 1-yard error, 13,706 at 0.5 and 4,358 at 2 (each simplification ~0.3 s in the browser). Flat-ish triangles are draped with the minimap (which already shows the roofs); steep ones are walls, coloured with that building's wall colour (area-weighted average of its steep faces' textures) and sun-shaded. It needs no per-model work, so it handles every model the same way. Limits: overhangs, arches and the space under bridges fill in solid, and the triangle count means tiles near the camera use the fine version while distant tiles use coarser error levels (precomputed per tile, e.g. 0.5 / 2 / 8 yards).

**Shape error setting.** Compared on the Northshire tile (whole tile, abbey close up): 0.1 yd = 61,764 triangles, no visible gain over 0.5 and it shows the 1-yard sampling as stripes; 0.5 yd = 13,706, practically identical to the unsimplified grid; **1 yd = 7,262, the agreed starting point**; 2 yd = 4,358, walls facet and wall bases get jagged close up, but it is indistinguishable from 1 yd further away. The values are the defaults of `tile()` in `scripts/browser_export_detail.js` (`maxError = 1` near buildings, `groundError = 4` elsewhere, `coarseError` and `farError` for the coarser levels); pass others to `gpsDetail.start` to change them. (A `scripts/export_settings.json` with these values, never read by any script, was removed on 2026-10-17.)

Rough data budget (estimate): 65×65 heights per tile at one byte each with a per-tile offset and scale is about 4 KB a tile, about 7 MB for both continents, best split into a load-on-demand addon per continent.

## What else to bring over, ranked

1. **Terrain layer from minimap FileDataIDs.** The core of the change; removes almost all bundled assets.
2. **Zone and subzone under the cursor.** MapExplorer's `regions.json` holds the area of every map chunk (64×16 per continent, about 33 yards). Exported run-length encoded, it gives a cursor tooltip with subzone, faction and level range.
3. **Flight network, boats and zeppelins.** From the client's TaxiNodes/TaxiPath/TaxiPathNode (`tools/buildRegions.ts`), so it matches your client version.
4. **Town and landmark labels** from AreaPOI (`src/explorer/places.ts`).
5. **NPC and object spawns, patrol paths, dungeon entrances** (`public/spawns`). This is VMaNGOS 1.12 data (GPL-2.0), so it does not cover Forever's new zones, dungeons or changed spawns. It is large, so it belongs in a LoadOnDemand sub-addon.
6. **Elevation** from the WDL low-detail heightmap (`src/formats/wdl.ts`): height readout or a hillshade layer. Low priority.
7. **Map textures** (MAID slot `mapTexture`): a possibly higher-resolution, terrain-only image per tile. Worth a `bun run probe` to see whether the Forever client ships them and at what size.

## 3D mode (2D/3D toggle)

Addons do get real GPU 3D, but only for models. A `ModelScene` frame (in Forever 1.60.1's API docs) is a small 3D scene with its own camera (position, yaw/pitch/roll, field of view, near/far clip), lights, fog, `Project3DPointTo2D`, and any number of actors loaded by FileDataID, creature display ID or unit (`SetModelByFileID`, `SetModelByCreatureDisplayID`, `SetModelByUnit`), each placed with `SetPosition`/`SetYaw`/`SetScale`. That covers M2 files: characters, creatures, trees, rocks, lamp posts and other props. What it cannot load is terrain (ADT has no model API at all) and, as far as the docs and community threads show, buildings (WMO); `/gps3d model 106965` tests the WMO case directly. The 3D view-capable `MapScene` widget exists too, but only on the character-select (glue) screen, where addons do not run.

So the 3D mode is a hybrid. The terrain is software 3D, described below, and real M2 models sit on top in a ModelScene whose camera is driven from the same orbit camera. MapExplorer already reads every tile's doodad placements (`src/explorer/objects.ts`, MDDF: M2 FileDataID, position, rotation, scale) and WMO placements (MODF), and has creature spawns with display IDs, so trees, props and NPCs can be exported and placed where they stand in the world.

The terrain cannot be a model, but software 3D works. `Texture:SetVertexOffset` (available in Forever 1.60.1) moves each corner of a texture independently, so a texture can be bent into any projected quadrilateral. A terrain mesh then becomes a grid of textures: project every height-grid vertex with an orbit camera in Lua, push each quad's four corners to the projected spots, give each quad its slice of the minimap tile with `SetTexCoord`, and draw far-to-near by sorting quads into 64 depth buckets (4 draw layers × 16 sublevels). 2D and 3D are the same renderer: 2D is the camera looking straight down with heights flattened, so the toggle is an animated camera move.

Heights come from MapExplorer: the WDL low-detail heightmap (17×17 per tile, about 33 yards) for a cheap mesh, or the full ADT height grid (`tileHeightGrid`) downsampled, exported to Lua next to the tile IDs.

Since 2026-10-17 this is built (`prototypes/GPS3D/Models.lua`): every M2 and WMO placement of the 16 maps with terrain (415,011, from the game files of build 1.60.1.70450 through MapExplorer's reader) is in `Data/Models_*.lua`, and the 3D view draws the game's own props and trees around the middle of the view, chosen by size on screen within a count and a distance the player sets. Buildings (WMOs) go in the same ModelScene when the game loads them there: an in-game check per game build decides, and until it says yes (or for good if it says no) buildings stay as the simplified meshes described above. AGENTS.md has the details, TESTING.md section 10 the in-game check.

Limits to accept: no depth buffer, so very steep terrain can show sorting glitches; models are always drawn over the terrain, so a model behind a hill shows through it unless it is culled; buildings stay painted on the minimap image unless WMOs turn out to load; and the quad budget is a few thousand (the prototype uses 1,600), so 3D covers a window around the player while zoomed-out views stay 2D. Character or creature models could be placed on top with a `ModelScene`, but terrain and buildings cannot be loaded as models.

`prototypes/GPS3D/` is a working test of this, with the camera model the real map will use: a perspective camera orbiting a ground target, where left-drag pans the target across the world, the wheel changes the camera's distance (so zooming changes the perspective, not just the scale), and right-drag turns and tilts. The 2D/3D button animates between straight-down with flat terrain and a 35° tilt. The quad window follows the target and coarsens with distance (cell size 2–256 units, powers of two so no quad straddles a tile), and its far edge fades out. The world is split into 256-unit tiles with a `TileTexture(tx, ty)` hook, which is where the real version returns each ADT's minimap FileDataID. Commands: `/gps3d`, `/gps3d drape [fileID or path]`, `/gps3d flat`, `/gps3d me`, `/gps3d model [id]` (default Elwynn tree 189927; 106965 is the Elwynn farmhouse WMO), `/gps3d trees`, `/gps3d clear`, `/gps3d cam`, `/gps3d fov [radians]`. Checked outside the game with stubbed API calls and a software rasteriser: draped tiles keep their orientation in 2D and perspective 3D, panning moves the camera the expected way, and models line up with the terrain to 0.0000 px (assuming the scene FOV is vertical radians). In game, the open questions are frame time, that FOV assumption, and WMO loading.

What does not transfer: 3D terrain, buildings, lighting, particles, audio and the free camera. A live link between MapExplorer and the running game is not possible either; addons have no sockets, and SavedVariables only reach disk on `/reload` or logout.

## Risks and unknowns

How far the 2D map can zoom before it gets blurry is set by the minimap images: 512 px per 533-yard tile in Forever (measured), about 1 px per yard. Beyond that GPS can only magnify.

The main one is whether `SetTexture(fileID)` loads minimap BLPs on the Forever client. The precedent (Carbonite) is retail, 2021. Forever also carries Midnight's addon restrictions ("secret values"); player position and minimap rotation may be hidden during encounters, which is acceptable for a map. MapExplorer's DB2 layouts are written for Forever (`src/explorer/db2Layouts.ts`), so the taxi, UiMap and AreaPOI exports should work as they are. The minimap images are about 0.48 px per yard (256 px per tile), so the terrain layer cannot be sharper than today's tiles unless the map-texture layer turns out larger. MapExplorer is MIT, so copied code only needs its licence notice.

## Tests (in game, Forever beta or live)

1. Copy `prototypes/GPS3D` into `Interface/AddOns`, `/reload`, then `/gps3d`. Drag to orbit, press 2D/3D, and read the frame time in the title.
2. `/gps3d drape` drapes a map icon by path, which checks that textures survive the vertex offsets.
3. After the export step, `/gps3d drape <minimap FileDataID>` checks that minimap images load by FileDataID. The Outland IDs from the earlier version of this plan do not apply to Forever.

## Next steps

1. Run the GPS3D prototype tests 1–2.
2. Set the TOC to Forever's interface number and drop the Outland tiles.
3. Write `tools/exportGps.ts` against your install (product `wow_classic_beta`): minimap FileDataIDs, overview atlas, and heights. Running it needs read access to `C:\Program Files (x86)\World of Warcraft` (from a Claude session, or `bun` locally).
4. Rebuild the renderer: data provider on `WorldMapFrame`, grid-aligned tiles, LOD, player arrow; then the 3D window around the player, fed by the exported heights.
5. Add the data layers in the order above.
