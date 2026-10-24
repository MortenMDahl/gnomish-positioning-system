# After the in-game test: what to do next (shells and renderer speed, 2026-10-24)

Written after the performance sparring with a Fable agent on 2026-10-24 (findings checked against the code and
re-measured in the sandbox). Everything below the line "Waits for the game" needs a number or a picture only the
game can give. Each item says where in the code it goes, what it should gain, what could go wrong, and how to test it.
Sandbox numbers are Lua 5.4 under lupa (`tools/sandbox`), views as `perf_shells.py` (orbit height 117.5, Stormwind's
Trade District): closeup 45 yd, near 90, close 200, high 420, far 2,000.

## Where the time goes today (sandbox, turning 1 degree a frame)

- About 80 % of the C calls are `SetVertexOffset`: 4 per texture whose corners moved (quad: one per corner; triangle:
  one each for a and b, two for c, since corner 4 is pinned onto c; `GPS3D.lua`, draw loop after `-- cull, sort into
  buckets and draw`). Turning moves every vertex, so `VO_EPS` saves nothing then.
- Most of the rest is `SetDrawLayer` (a texture's depth bucket changed) and a few `SetParent` (it crossed one of the
  16 bucket frames). This churn is real motion, not noise: making the bucket ranges sticky saved 0.1-2.4 %.
- Shells.lua's own choice of levels (`S.Frame`) is 0.3-1.0 ms; the cull-and-draw loop 65-75 % of Render.
- Textures shown (ground + shells): closeup 1,245 + 2,667, near 63 + 2,721, close 253 + 2,415, high 1,983 + 3,339,
  far 2,502 + 1,293. At closeup 982 ground triangles lie wholly under the city's shells.

## 0. Getting the shells into the game for the test

1. Branch `poc-shells`. Copy `prototypes/GPS3D` and `prototypes/GPS3D_City_Stormwind` (with its `Shells` folder) to
   the game's AddOns folder, as AGENTS.md "Deploying and testing" says for the other GPS3D folders.
2. `GPS3D_City_Stormwind\Shells\S<set>_<page>.jpg` (since S1d: 45 pages of the 9 sets, 51 MB) and `Floor.jpg`
   (the city's floor picture, 1 MB). They are not in git (`.gitignore`); copied into the repository folder on
   Morten's PC with each data change (the old `L<level>_<page>.jpg` pages are no longer used). To make them again:
   `testing/2026-10-24-poc-shells/sh_sets.sh` (writes them to `tools/sandbox/site/shells/` and `Floor.jpg` to the
   addon folder), then copy the pages into `prototypes/GPS3D_City_Stormwind/Shells/`.
3. The data names the pages `.jpg`, the way GPS loads its overview images. If the self-test says the overview images
   do not load (JPEG refused by the client), the shells will be blank too: then the pages must become BLP (DXT1)
   or TGA, and `sh_tolua.py`'s path changes to that extension (see 3.1).
4. In the game: `/gps3d probe stormwind` moves the 3D view to the Trade District by itself (no need to travel there
   on a Horde character); the shells load when the view comes within 600 yd of the square (`S.LOAD_NEAR`).
   `/gps3d shells` prints the shells' state (units drawn per level, faces, waiting).

## 1. What the in-game test must answer, and what each answer decides

Run `/gps3d probe stormwind` with the 3D window open, take the screenshot it asks for, then `/reload` and send
`WTF\Account\<account>\SavedVariables\GPS3D.lua` (or the chat lines). The lines and what they decide:

| Probe line | What it measures | Decides |
|---|---|---|
| `1/5 ... per texture shown ..., per C call` | the client's cost of a texture on screen and of one C call | whether to cut calls (2.2) or textures (2.1, 2.3) first |
| `2/5 fold` (the screenshot) | the diagonal the client folds a bent 4-corner texture along | 2.3: ground pairs are exact only along a fixed diagonal |
| `4/5 one-call move` (new 2026-10-24) | ms per 1,000 calls: `SetVertexOffset`, `SetPoint`, `AdjustPointsOffset` (or `missing`); whether a 0.3 px `SetPoint` moved `GetCenter` by 0.30 | 2.2: worth it if one move costs less than 3 `SetVertexOffset` and is not snapped to whole pixels |
| `4/5 SetPointsOffset` | the old glide test | (unchanged) |

Also look, with your own eyes, at the shells at 45, 90, 200 and 420 yd, still and turning:
- pictures there at all (blank faces: see 0.3); sharpness against the sandbox; shimmering far away (JPEG pages may
  get no mipmaps in the client; BLP with mipmaps would fix it);
- anything see-through, faces flickering in front of each other (draw order), buildings popping when they change level;
- frame rate with the 3D window open over Stormwind against the same view with `/gps3d shells off`;
- the client's memory (`/gps3d test`, or the game's addon memory): a JPEG page is probably held uncompressed,
  2048 x 2048 x 4 bytes = 16.8 MB each, up to 15 pages at closeup (about 250 MB) where DXT1 BLP would be 2.8 MB each.
  If memory or the frame rate suffers, BLP comes first (3.1).

## 2. Speed-ups, in order of gain for the effort

### 2.1 Do not draw the ground under the city's shells (needs no game; two prerequisites first)

- Since S1d (2026-10-24) the ground under the city is raised to the buildings' floor and drawn round and under the
  shells, so this gain is now larger: the floor costs closeup / near / close about +1,800 / +5,500 / +3,000 calls a
  frame against the code before S1d (earlier alternating run, `GATES.md` S1d-G4). The cells wholly under shell tops
  in every set: `sh_solidcells.py` (127 cells) — a start for the gap list.

- Gain (sandbox, measured on a patched copy and re-run): closeup 17,489 -> 12,943 calls a frame (-26 %), the other
  views -1 to -2 % (the shells cover little of the ground there or it is not in view). Lua ms about the same (the
  ground's vertices are still projected).
- Where: flag at mesh build, `BuildGridMesh` in `GPS3D.lua` next to `t.blk`: `t.city = true` when all three corners
  lie inside the city data's `box` (`ns.ShellData[name].box`, inset 1 yd) and, if a gap list is used, none of the
  ground cells under it is marked. In the draw loop, before the triangle path: `elseif t.city and skl then culled`.
  Only while shells are drawn this frame (`skl` set) and none is waiting (`st.waiting == 0`), so the ground is never
  missing while a unit's level is still being decoded.
- Prerequisite 1, the gaps: where the shells' tops do not cover ground the game covers, today the ground shows; it
  would show the background. Measured (`sh_gapcells.py`, 0.5-yd raster, levels 1-4 OR-ed): 414 of 961 ground cells
  (16.7 yd) inside the square have some gap (43 %; 36 % with more than 1 yd2; levels 1-3 only: 39 %; level 4 alone
  misses 3,955 yd2). A gap list would therefore keep the ground in about 40 % of the cells and lose about 40 % of
  the gain. Better: close the gaps in the data. In `sh_build3.py` let the street layer (`street` units) cover every
  cell of the street floor raster that no unit's top covers at that level, so each level's tops cover all the
  ground the game covers; check with `sh_cover.py <level>` (missing should be 0) and `sh_gapcells.py` (0 cells).
- Prerequisite 2, 4-corner faces at the near plane: a quad that crosses the near plane is not drawn at all
  (`GPS3D.lua`, `-- (one crossing the near plane is not drawn: no cutting of 4-corner parts yet)`); triangles are cut
  (`DrawClipped`). Measured: 287-354 shell quads a frame cross it at 45 / 25 / 15 yd, none of them reaching the
  canvas today (their front parts are all off screen), so nothing is missing now; with the ground gone such a case
  would show background. Generalise `DrawClipped` to 4 corners (`for e = 1, n` round a, b, c, d; the shell's 8
  texture coordinates from `t.mesh.uv` at `(k - 1) * 8`, corner order a b c d; the quad path then restores them
  with `SetTexCoord` when the face is whole again, as triangles do with `t.u1`). One plane cuts a quad into at most
  5 corners and a texture has 4: design the 5-corner case before coding it (dropping one cut point can lose a wedge
  that reaches the screen; options: split the face into its two triangles while it is cut, which needs a second
  texture from the pool, or move the near plane for that face). Cost when nothing reaches the canvas: the side test
  only (about 0.02 ms for 300 faces).
- Tests: a sandbox check that no background pixel shows inside the square at the five views and over a turning /
  zooming path (page shots against `/gps3d shells off` + ground), `order_shells.py`, `perf_shells.py`.

### 2.2 Move a texture with one call when its corners all moved alike (needs the probe's 4/5 one-call move)

- Idea: when all four corners of a texture moved by the same amount (within `VO_EPS`, 0.25 px, of their mean),
  move the texture by one call instead of four `SetVertexOffset`, keeping the corner offsets.
- Gain (measured share, estimated calls): textures that qualify while turning: 14 / 24 / 40 / 48 / 60 %
  (closeup .. far); if one move costs about one `SetVertexOffset`, calls -7 / -15 / -27 / -31 / -34 %. At a 0.1 px
  tolerance only 3-29 % qualify.
- Where: the quad and triangle paths of the draw loop. Every pool texture has one anchor,
  `SetPoint("CENTER", canvas, "CENTER", 0, 0)` (`AcquireTex`), and `SetParent` keeps it, so the move is
  `tex:SetPoint("CENTER", canvas, "CENTER", ax, ay)` (one call, it replaces the point) or `AdjustPointsOffset(dx, dy)`
  if the client has it. Store the anchor on the triangle (`t.ax, t.ay`) and send corners relative to it; put it back
  to (0, 0) when the texture is cut (`DrawClipped` sends absolute corners), returned to the pool (`ReleaseTex`),
  and in the probe's `Unanchor`.
- Risks: neighbours sharing a vertex may now disagree by up to 0.5 px (today's rule is per vertex): hairlines between
  faces; the 0.5-px outset the corners already get should hide them, the game test will show. Pixel snapping of
  anchors (the probe says whether 0.3 px is kept; `SetSnapToPixelGrid(false)` / `SetTexelSnappingBias(0)`, which
  `GPS3D.lua` already calls where the game has them; search for `SetSnapToPixelGrid`).
- Tests: sandbox: every corner on screen within 0.5 px of where the old code puts it over the paths of
  `test_choice.py`; calls before / after.

### 2.3 Draw ground triangles in pairs, one texture per pair (needs the probe's fold picture)

- Idea: two neighbouring ground triangles of a tile (siblings of the bintree in `Terrain.lua`'s `Lod.NewMesh` share
  the median edge; hypotenuse neighbours make diamonds) drawn as one 4-corner texture.
- Gain (measured pairing of shown, nearly coplanar triangles, normals' dot over 0.9): ground textures -36 to -42 %
  (a sibling-first pairing should come near -50 %); estimated calls: far -22 %, high -14 %, little at closeup once 2.1
  is in.
- Exact only if the client folds a bent 4-corner texture along a fixed diagonal and the pair's shared edge is put on
  that diagonal (the fold picture says which). Keep pairs only with the same `t.blk` (the seam bias under building
  blocks) and not in the tiles nearest the camera (4-corner faces crossing the near plane are not cut, 2.1).
- Tests: `test_terrain.py` (no cracks, the movement checks), page shots before / after pixel-compared.

## 3. Not speed, but needed before shells can ship

1. BLP pages: DXT1 with mipmaps (about 2.8 MB a page instead of 16.8 MB in memory, and no shimmer far away).
   Needs a BLP2 writer with DXT1 (not Pillow's palette BLP); `sh_tolua.py`'s path extension follows.
2. The data for the rest of Stormwind (and other cities), within a size budget: the pictures are 66 M px for this
   520 x 520 yd square (README "Open problems").
3. Up close (45 yd) the pictures are still soft (magnification about 4): the game's own textures, tiled, laid over
   the picture is the untested idea that costs no data (README "Sharper near buildings").

## Tried and measured negative (do not redo)

- Shells.lua: skipping the units of blocks out of view and running `Tidy` only over units holding meshes:
  `S.Frame` 15 % slower (most units hold meshes in these views; the extra bookkeeping costs more than it saves).
  Built and reverted on 2026-10-24.
- Sticky bucket ranges (ground and shells, 10 % margin): -0.1 to -2.4 % calls. 32 bucket frames instead of 16:
  `SetDrawLayer` +20-30 %.
- Merging shell triangles into quads: about 1 % of faces have a coplanar neighbour left (`join_quads` already pairs).
- Hiding faces behind the 40-200 biggest nearer faces: catches 0-6 % of faces and costs 4-36 ms of Lua.
- Dropping faces under 1 px2: at most 2 % of calls, and it changes the picture.

## Done on 2026-10-24 (this round; sandbox)

- Shell faces' middles worked out once when a level is decoded (`Shells.lua` `Decode`, `t.mx, t.my`) instead of every
  frame in the draw loop, and `math.log` and `sr.kmin` read once per frame: Render 6.3-6.4 -> 6.0-6.1 ms at 200 yd,
  7.2-7.7 -> 7.1-7.3 at 90 yd (3 runs each), the other views within the noise. Calls unchanged; every shell face's
  bucket and corners identical over 35 snapshots (5 views and turning, zooming and panning paths) with the level
  hysteresis held at 1.
- Level hysteresis against the level wanted last (`u.want`), not the one drawn: a unit drawn at a coarser level while
  its own was still being decoded (`S.DECODE_MS`) kept that coarser level until it left the hysteresis band; which
  units did depended on the machine's speed. Now the level depends only on the view's history.
- `/gps3d probe`: part 4's one-call move (above, section 1); `test_probe.py` checks it (35 checks). The glide check
  now follows a ground vertex: a city shell can change level at the moved camera and leave its old faces hidden,
  which made that check fail on this branch since the shells came (35 px, it passes with shells off).
- The shells' data names its pages `.jpg` and the sandbox's loader accepts the extension, so the same data runs in
  the game (section 0).

## Done on 2026-10-24 (S1d; sandbox)

- The ground raised to the cities' floors (`scripts/build_city_floor.py`, all maps) and its levels of detail rebuilt
  with the error under the shells weighted 0.15 (`scripts/build_terrain_lod.py`).
- Everything, ground included, ordered by distance while shells are in view; the city's floor cells behind the shells
  on them (no shells through mountains).
- Five levels of detail by distance with sliders (*Shells level N from / detail*), nine baked sets to choose from.
- The city's floor picture instead of the minimap's under and round the shells (no flat copy of the buildings on the
  ground); `/gps3d shells floor off` to compare.
- `ALL_BUILDINGS.md`: what every building in the game would weigh and the order to build it.
- In the game, check: the floor picture loads as `.jpg` like the pages; the ground at the square's edges (raised
  floor against unraised hills); the sliders' defaults against the frame time.

## Done on 2026-10-24 (S1e; sandbox)

- Levels of detail recalculated with a Sonnet agent (README), with a face budget and asymmetric hysteresis.
- Shell corners under the drawn ground are lifted to 1 yd under it; the export cut's empty walls are gone.
- Every building on both continents as whole-block shells (`ALL_BUILDINGS.md`, phase 1).
- In the game, check:
  - the two new data addons load (`/gps3d test` lists them);
  - the old blocks give way without flicker where the shells are drawn;
  - the frame time at a capital seen from 800-2,000 yd with the new ladder (the budget slider trades it).
