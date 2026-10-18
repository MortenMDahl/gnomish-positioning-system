-- GPS 3D: the whole game world in perspective, as GPS's 3D view. It shares GPS's look
-- (GPS_API.ApplyChrome) and switches with the 2D map and the traditional map at the same place and size.
--
-- Terrain: Data/World_*.lua hold, for every ADT tile of every map with terrain, a 33 x 33 grid of
-- heights (16.7 yards apart; ground or water surface, whichever is higher). Around the camera the
-- tiles are turned into triangles at a level of detail that depends on their distance (a cell
-- 16.7 to 533 yards wide), within a triangle budget, with tile edges matched to coarser neighbours
-- so there are no cracks. Each triangle is one texture bent into place with SetVertexOffset (two
-- corners pinned together) showing its part of the tile's minimap image (near) or of GPS's
-- overview image (far). Back faces and tiles outside the view are skipped; the rest are drawn far
-- to near in 512 buckets.
--
-- Buildings: Data/Detail_*.lua hold, for every tile with buildings, meshes of 66.7-yard blocks with
-- the buildings raised into the ground (walls coloured like their texture). Blocks near the view's
-- centre are drawn on top of the grid, nearest first, within a triangle budget; the grid stays under
-- them so the seams never show the background.
--
-- You: an arrow lying on the ground under you, drawn in the same perspective as the terrain, and
-- your own character model standing on it (ModelScene, same camera).
--
-- Camera: orbits a point on the ground, in one of three modes (the camera ring on the right steps
-- Follow -> Behind -> Free; Me locks back onto you):
--   Free     look around: left drag grabs the ground and moves it, wheel zooms toward the cursor
--   Follow   you stay in the middle; you turn the view yourself
--   Behind   you stay in the middle and the view turns with you, looking the way you face
-- In every mode: right drag turns and tilts (45 degrees from straight down at most), the
-- wheel zooms, double-click flies to a spot (Free), the compass ring turns back to north, and the
-- bottom ring (a grid seen from above, or in perspective) locks the view straight down or frees the tilt. Left drag while following switches to Free.
--
-- World coordinates here: x east, y north, h up, in yards; x = gx * TILE, y = -gy * TILE on the
-- ADT grid (gx east, gy south), so tile (tx, ty) covers x in [tx, tx+1] * TILE, y in [-(ty+1), -ty] * TILE.
local addonName, ns = ...
local GPS = GPS_API
if not GPS.Log then GPS.Log, GPS.DebugOn = function() end, function() return false end end -- an older GPS: no debug log

local TILE = 1600 / 3
local GRID = 33                    -- heights per tile side
local CELLS = GRID - 1             -- 32 cells per tile side at full detail
local CELL = TILE / CELLS          -- 16.7 yards
local BLOCKS = 8                   -- building blocks per tile side
local BLOCK = TILE / BLOCKS        -- 66.7 yards
local STEP = TILE / 512            -- vertex spacing of the building meshes (1.04 yards)
local WHITE = "Interface\\Buttons\\WHITE8X8"
local LAYERS = { "BACKGROUND", "BORDER", "ARTWORK", "OVERLAY" }
local LAYER_BUCKETS = #LAYERS * 16 -- draw order buckets within one frame (layer x sublevel -8..7)
local BUCKET_FRAMES = 8            -- frames stacked by level: 8 x 64 = 512 depth buckets
local FOV = math.rad(50)           -- vertical field of view
local NEAR = 1
local WALL_STEEPNESS = 0.45        -- |normal up| below this: a wall, not ground
local MIN_DIST, MAX_DIST = 15, 14000
local CLEARANCE = 8                -- the camera stays at least this high above the ground (and roofs) below it
                                   -- ... than the ground or roofs anywhere within 25 yards of it (GroundUnder)
local AHEAD, AHEAD_CLEAR = 1.2, 4      -- tilted: how much of the view line must clear the ground, and by how much (LiftFor)
local AHEAD_STEP, AHEAD_SAMPLES = 6, 48 -- ... checked every 6 yards, at most 48 times
local MIN_PITCH, MAX_PITCH = 45, 89.9 -- tilt: 45 degrees above the ground (45 from straight down) to straight down (89.9 keeps the model camera exact)
local MODEL_YAW = math.pi / 2      -- character models face +x at yaw 0; WoW facing 0 is north (+y)
local CLICK_TIME, CLICK_SLOP = 0.35, 4
local TRI_BUDGET = 3200            -- grid triangles per frame (buildings come on top)
local CELL_PX = 26                 -- wanted on-screen size of a grid cell, before the budget
local MINIMAP_PX = 80              -- tiles bigger than this on screen use the 512 px minimap image, smaller ones
                                   -- the 64 px overview (chosen by size on screen, not by the mesh's level of detail)
local DETAIL_BUDGET = 4000         -- building-mesh triangles per frame, blocks nearest the view's centre first
local DETAIL_RANGE = 1000          -- building blocks are drawn this close to the view's centre (yards) ...
local DETAIL_DIST = 2500           -- ... while the camera is no further away than this
-- level of a block by how big its vertex spacing looks on screen: the coarsest level whose spacing
-- (fine 1 yd, coarse 4.2 yd, far 8.3 yd) stays under LEVEL_PX pixels; blocks that do not fit in the
-- budget at that level are left flat (never shown coarser than that, which looks broken up close)
local LEVEL_STEP = { TILE / 512, TILE / 128, TILE / 64 }
local LEVEL_PX = 10
local DETAIL_BIAS = 30             -- grid triangles under a drawn building block are drawn as if this much further
local BUILD_LIMIT = 1500           -- building triangles made into textures per frame (more blocks follow next frames)
local GEO_LIMIT = 400              -- decoded building blocks kept (a busy frame touches up to about 115; 1500 until 2026-10-18: up to 80 MB)
local KEEP_SECONDS = 3             -- unused tile meshes are kept this long before their textures are reused
local TEX_LIMIT = 16000            -- above this many terrain textures, unused meshes give theirs back at once

local sin, cos, rad, deg, floor, ceil, min, max, sqrt, abs = math.sin, math.cos, math.rad, math.deg, math.floor, math.ceil, math.min, math.max, math.sqrt, math.abs

local Usable = GPS.Usable -- nil, or a value the game hides from addons (secret): not usable

------------------------------------------------------------------------------------------------
-- Frame (GPS's look)
------------------------------------------------------------------------------------------------
local frame = CreateFrame("Frame", "GPS3D_Frame", UIParent, "BackdropTemplate")
frame:SetSize(900, 650)
frame:SetPoint("CENTER")
frame:SetFrameStrata("HIGH")
frame:SetMovable(true)
frame:SetResizable(true)
if frame.SetResizeBounds then frame:SetResizeBounds(400, 300, 4000, 3000) end
frame:EnableMouse(true)
frame:EnableMouseWheel(true)
frame:SetClampedToScreen(true)
frame:Hide()
tinsert(UISpecialFrames, "GPS3D_Frame")

local canvas = CreateFrame("Frame", nil, frame)
canvas:SetClipsChildren(true)
canvas:EnableMouse(true)
ns.canvas = canvas

-- Behind the terrain: open sea in the colour of the game's minimap images (GPS's colors.sea, the 2D
-- map's background too), so the world past a map's last tiles looks like more sea. The view never
-- tilts above 45 degrees from straight down and sees 25 degrees either side of its middle, so the
-- horizon is never in view and there is no sky to draw (until 2026-10-17 this was a sky gradient,
-- which made the sea turn pale blue where the map's tiles ended).
local sea = canvas:CreateTexture(nil, "BACKGROUND", nil, -8)
sea:SetAllPoints()
sea:SetColorTexture(GPS.colors.sea[1], GPS.colors.sea[2], GPS.colors.sea[3], 1)

-- Terrain: frames stacked by frame level, each holding 64 draw-order buckets.
local bucketFrames = {}
for k = 1, BUCKET_FRAMES do
	local f = CreateFrame("Frame", nil, canvas)
	f:SetAllPoints(canvas)
	f:SetFrameLevel(canvas:GetFrameLevel() + k)
	bucketFrames[k] = f
end

-- You, on the ground: the minimap arrow bent into perspective like the terrain, above it.
local decalFrame = CreateFrame("Frame", nil, canvas)
decalFrame:SetAllPoints(canvas)
decalFrame:SetFrameLevel(canvas:GetFrameLevel() + BUCKET_FRAMES + 1)
local decal = decalFrame:CreateTexture(nil, "ARTWORK")
decal:SetTexture("Interface\\Minimap\\MinimapArrow")
decal:SetSize(1, 1)
decal:SetPoint("CENTER", canvas, "CENTER", 0, 0)
decal:Hide()
ns.decal = decal

-- Real 3D models on top: a ModelScene with the same camera.
local scene = CreateFrame("ModelScene", nil, canvas)
scene:SetAllPoints(canvas)
scene:SetFrameLevel(canvas:GetFrameLevel() + BUCKET_FRAMES + 3)
scene:EnableMouse(false)
scene:SetCameraNearClip(NEAR)
scene:SetCameraFarClip(40000)
scene:SetLightVisible(true)
scene:SetLightDirection(0.5, -0.5, -0.7)
local defaultFov = scene:GetCameraFieldOfView()
local actors = {} -- extra models: { actor, x, y, h }
ns.scene, ns.actors = scene, actors

local function NewActor()
	local ok, actor = pcall(scene.CreateActor, scene)
	if not ok or not actor then ok, actor = pcall(scene.CreateActor, scene, nil, "ModelSceneActorTemplate") end
	return ok and actor or nil
end
ns.NewActor, ns.frame, ns.TILE, ns.BLOCK = NewActor, frame, TILE, BLOCK

-- after a move or resize, its place and size become the saved one (GPS keeps it for every mode)
local ui = GPS.ApplyChrome(frame, canvas, {
	mode = "3D",
	onMoved = function() if GPS.SaveGeometry then GPS.SaveGeometry(frame) end end,
	onSized = function() if GPS.SaveGeometry then GPS.SaveGeometry(frame) end end,
})
ns.ui = ui

-- The rings down the right edge (GPS's look): compass, mode (3D), Me, as in every GPS window and at
-- the same places (so switching modes keeps them under the mouse), then camera mode and straight
-- down / tilted. (Lua 5.1 allows 200 local variables in the main chunk and this file is close: the
-- helpers below live in blocks or on the buttons.)
-- Compass (GPS's, from ApplyChrome): here the needle turns with the view; click to turn north up.
local compass = ui.compass
compass.tooltip = { "Compass", "Click: turn north up" }
ns.compass = compass

-- Straight down or tilted: the ring shows a little 2x2 grid of ground the way the camera sees it,
-- turned with the view like the compass, square when looking straight down and in perspective when
-- tilted (four Media\Cell squares bent with SetVertexOffset); gold while straight down is locked.
-- Click to switch. Straight down, locked, is the default; the choice is remembered.
local topButton = GPS.RingButton(ui.chrome, function()
	if ns.IsTopDown() then return { "Looking straight down", "Click: tilt freely (right-drag tilts)" } end
	return { "Tilting freely", "Click: look straight down again" }
end)
topButton.cells = {}
for i = 1, 4 do
	local t = topButton:CreateTexture(nil, "ARTWORK")
	t:SetTexture(GPS.MEDIA .. "Cell")
	t:SetSize(1, 1)
	t:SetPoint("CENTER", topButton, "CENTER", 0, topButton.centreY)
	topButton.cells[i] = t
end
do
	local SetActive = topButton.SetActive
	function topButton:SetActive(on)
		SetActive(self, on)
		local c = self.active and GPS.colors.gold or GPS.colors.brass
		for _, t in ipairs(self.cells) do t:SetVertexColor(c[1], c[2], c[3]) end
	end
end
topButton:SetActive(false)
ns.topButton = topButton

-- Camera mode: one ring that steps Follow -> Behind -> Free, showing the mode it is in (a dot with
-- the view circling it, your arrow with the view's cone behind it, four arrows); gold while it is
-- locked onto you.
local camButton
do
	local CAMERA_TIPS = {
		follow = { "Camera: following you", "Click: behind you", "Right-drag: turn and tilt   Wheel: zoom   Drag: look around" },
		behind = { "Camera: behind you", "Click: free camera", "Right-drag: look aside and tilt   Wheel: zoom   Drag: look around" },
		free = { "Camera: free", "Click: follow you", "Drag: move   Right-drag: turn and tilt   Wheel: zoom   Double-click: go there" },
	}
	camButton = GPS.RingButton(ui.chrome, function() return CAMERA_TIPS[ns.CamMode()] end)
end
camButton.icons = { follow = GPS.MEDIA .. "CamFollow", behind = GPS.MEDIA .. "CamBehind", free = GPS.MEDIA .. "CamFree" }
camButton:SetIcon(camButton.icons.free, 0.62)
ns.camButton = camButton

ui.me.tooltip = { "Me", "Centre on you and follow (Follow or Behind, as you last chose)" }
ui.SetRings({ compass, ui.modeSwitch, ui.me, camButton, topButton })

------------------------------------------------------------------------------------------------
-- World data: heights per tile, decoded when first needed
------------------------------------------------------------------------------------------------
ns.World = ns.World or {}
local B64 = {}
do
	local chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	for i = 1, 64 do B64[chars:byte(i)] = i - 1 end
end

-- A tile's heights: h[i] (1-based, row by row from the north-west) is read from the tile's string when
-- asked for, nothing is decoded in advance; h.lo and h.hi are its lowest and highest height. The
-- string is a 3-character base (the lowest height), 33 x 33 heights of 2 characters, and, since
-- 2026-10-17, 2 characters for the highest (build_world.py); older strings are scanned once for it.
-- (Until then every tile in view was decoded into a table and kept: zoomed out over a continent that
-- was about 90-160 ms in one frame and 20-30 MB that stayed.)
local heightCache = {} -- map * 4096 + key -> { s, base, lo, hi } with the heights behind __index, or false
local TileHeights
do
	local FULL = 3 + GRID * GRID * 2
	local heightsOf = { __index = function(t, i)
		local a, b = t.s:byte(i * 2 + 2, i * 2 + 3)
		return (t.base + B64[a] * 64 + B64[b]) * 0.5
	end }
	function TileHeights(map, tx, ty)
		if tx < 0 or tx > 63 or ty < 0 or ty > 63 then return nil end
		local key = ty * 64 + tx
		local ck = map * 4096 + key
		local h = heightCache[ck]
		if h ~= nil then return h or nil end
		local m = ns.World[map]
		local s = m and m[key]
		if not s then heightCache[ck] = false return nil end
		local b1, b2, b3 = s:byte(1, 3)
		local base = ((B64[b1] * 64 + B64[b2]) * 64 + B64[b3]) - 131072
		local top = 0 -- highest height above the base
		if #s >= FULL + 2 then
			local c1, c2 = s:byte(FULL + 1, FULL + 2)
			top = B64[c1] * 64 + B64[c2]
		else
			for i = 1, GRID * GRID do
				local a, b = s:byte(i * 2 + 2, i * 2 + 3)
				local d = B64[a] * 64 + B64[b]
				if d > top then top = d end
			end
		end
		h = setmetatable({ s = s, base = base, lo = base * 0.5, hi = (base + top) * 0.5 }, heightsOf)
		heightCache[ck] = h
		return h
	end
end
ns.TileHeights = TileHeights

-- Map extents in tiles, from the data
local mapBounds = {}
local function Bounds(map)
	local b = mapBounds[map]
	if b == nil then
		local m = ns.World[map]
		if not m then mapBounds[map] = false return nil end
		local x0, y0, x1, y1 = 64, 64, -1, -1
		for key in pairs(m) do
			local x, y = key % 64, floor(key / 64)
			if x < x0 then x0 = x end
			if x > x1 then x1 = x end
			if y < y0 then y0 = y end
			if y > y1 then y1 = y end
		end
		b = { x0 = x0, y0 = y0, x1 = x1, y1 = y1 }
		mapBounds[map] = b
	end
	return b or nil
end

-- Height of the grid surface (as drawn at full detail) at a world point
local function GridHeight(map, x, y)
	local gx, gy = x / TILE, -y / TILE
	local tx, ty = floor(gx), floor(gy)
	local h = TileHeights(map, tx, ty)
	if not h then return nil end
	local fx, fy = (gx - tx) * CELLS, (gy - ty) * CELLS
	local i, j = min(CELLS - 1, floor(fx)), min(CELLS - 1, floor(fy))
	local u, v = fx - i, fy - j
	local r0, r1 = j * GRID + i + 1, (j + 1) * GRID + i + 1
	local h00, h10, h01, h11 = h[r0], h[r0 + 1], h[r1], h[r1 + 1]
	-- each cell is split along its north-west to south-east diagonal
	if u >= v then return h00 + (h10 - h00) * u + (h11 - h10) * v end
	return h00 + (h11 - h01) * u + (h01 - h00) * v
end

ns.GridHeight = GridHeight

-- Image for a tile: its minimap (by FileDataID) or its square of the overview atlas.
local function MinimapFile(map, tx, ty)
	local m = GPS.Maps and GPS.Maps[map]
	return m and m.tiles[ty * 64 + tx]
end
local function OverviewOf(map, tx, ty)
	local m = GPS.Maps and GPS.Maps[map]
	if not m then return nil end
	for _, a in ipairs(m.atlases) do
		if tx >= a.x0 and tx < a.x0 + a.cols and ty >= a.y0 and ty < a.y0 + a.rows then
			local px = GPS.OverviewPx or 64
			return GPS.OverviewPath .. a.file .. "." .. (GPS.OverviewExt or "jpg"), (tx - a.x0) * px / a.w, (ty - a.y0) * px / a.h, px / a.w, px / a.h
		end
	end
end

------------------------------------------------------------------------------------------------
-- Texture pool (one texture per drawn triangle)
------------------------------------------------------------------------------------------------
local pool, poolN, poolMade = {}, 0, 0
local function AcquireTex()
	local tex
	if poolN > 0 then
		tex = pool[poolN]
		pool[poolN] = nil
		poolN = poolN - 1 -- already hidden by ReleaseTex
	else
		tex = bucketFrames[1]:CreateTexture(nil, "ARTWORK")
		tex:SetSize(1, 1)
		tex:SetPoint("CENTER", canvas, "CENTER", 0, 0)
		tex:Hide()
		poolMade = poolMade + 1
	end
	return tex
end
local function ReleaseTex(tex)
	tex:Hide()
	poolN = poolN + 1
	pool[poolN] = tex
end

------------------------------------------------------------------------------------------------
-- Meshes: grid meshes per tile and level of detail, and detailed meshes where they exist
------------------------------------------------------------------------------------------------
-- mesh = { vx, vy, vh, n = vertex count, tris = { { a, b, c, tex, bucket, frame, shown } }, ... }
local meshes = {} -- key -> mesh (grid: map:key:step; detail: "d:" .. key)
local stats = { shown = 0, culled = 0, behind = 0, ms = 0, tiles = 0, tris = 0, detail = 0, detailTris = 0, detailSkipped = 0, detailPending = 0, detailLevels = { 0, 0, 0 }, detailReach = 0, steps = {} }
ns.stats = stats

-- A texture remembers its file and colour (tex.file, tex.r/g/b) so pooled textures skip calls that
-- would not change anything.
local function SetTriTexture(t, file, ua, va, ub, vb, uc, vc)
	local tex = t.tex
	if tex.file ~= file then tex:SetTexture(file); tex.file = file end
	tex:SetTexCoord(ua, va, ub, vb, uc, vc, uc, vc)
	t.u1, t.v1, t.u2, t.v2, t.u3, t.v3 = ua, va, ub, vb, uc, vc -- kept for cutting it at the near plane
	if tex.r ~= 1 or tex.g ~= 1 or tex.b ~= 1 then tex:SetVertexColor(1, 1, 1); tex.r, tex.g, tex.b = 1, 1, 1 end
end

local function SetTriColour(t, r, g, b)
	local tex = t.tex
	t.u1 = nil
	if tex.file ~= WHITE then tex:SetTexture(WHITE); tex.file = WHITE; tex:SetTexCoord(0, 1, 0, 1) end
	if tex.r ~= r or tex.g ~= g or tex.b ~= b then tex:SetVertexColor(r, g, b); tex.r, tex.g, tex.b = r, g, b end
end

local function BuildGridMesh(map, tx, ty, step, sharp)
	local h = TileHeights(map, tx, ty)
	if not h then return nil end
	local n = CELLS / step
	local x0, y0 = tx * TILE, -ty * TILE
	local vx, vy, vh, fixed = {}, {}, {}, {}
	local k = 0
	for j = 0, n do
		for i = 0, n do
			k = k + 1
			vx[k] = x0 + i * step * CELL
			vy[k] = y0 - j * step * CELL
			vh[k] = h[(j * step) * GRID + i * step + 1]
			-- vertices on the tile's edge are shared with neighbours (and T-junctions): always drawn exactly
			if i == 0 or j == 0 or i == n or j == n then fixed[k] = true end
		end
	end
	local file, au, av, aw, ah
	if sharp then file = MinimapFile(map, tx, ty) end
	if file then au, av, aw, ah = 0, 0, 1, 1 else file, au, av, aw, ah = OverviewOf(map, tx, ty) end
	local tris, nTris = {}, 0
	local row = n + 1
	local mesh = { map = map, tx = tx, ty = ty, tkey = ty * 64 + tx, step = step, n = n, vx = vx, vy = vy, vh = vh, h = h, tris = tris, px = {}, py = {}, pd = {}, edges = -1, fixed = fixed }
	local uScale, vScale = aw / TILE, ah / TILE
	for j = 0, n - 1 do
		for i = 0, n - 1 do
			local v00 = j * row + i + 1
			local v10, v01, v11 = v00 + 1, v00 + row, v00 + row + 1
			-- (00, 01, 11) and (00, 11, 10): front faces seen from above
			for q = 1, 2 do
				local a, b, c
				if q == 1 then a, b, c = v00, v01, v11 else a, b, c = v00, v11, v10 end
				local t = { a = a, b = b, c = c, tex = AcquireTex(), bucket = -1, frame = 1, shown = false, mesh = mesh }
				-- building block under the triangle's centre (it is drawn behind a building block there)
				local ex = (vx[a] + vx[b] + vx[c]) / 3 - x0
				local sy = y0 - (vy[a] + vy[b] + vy[c]) / 3
				t.blk = min(BLOCKS - 1, floor(sy / BLOCK)) * BLOCKS + min(BLOCKS - 1, floor(ex / BLOCK))
				if file then
					SetTriTexture(t, file, au + (vx[a] - x0) * uScale, av + (y0 - vy[a]) * vScale, au + (vx[b] - x0) * uScale, av + (y0 - vy[b]) * vScale, au + (vx[c] - x0) * uScale, av + (y0 - vy[c]) * vScale)
				else
					SetTriColour(t, 0.35, 0.42, 0.3)
				end
				nTris = nTris + 1
				tris[nTris] = t
			end
		end
	end
	return mesh
end

-- Matches the mesh's edge heights to coarser neighbours (steps given per side) so there are no cracks.
local function FixEdges(mesh, sN, sE, sS, sW)
	local sig = ((sN * 64 + sE) * 64 + sS) * 64 + sW -- steps are at most 32
	if mesh.edges == sig then return end
	mesh.edges = sig
	local step, n, h, vh = mesh.step, mesh.n, mesh.h, mesh.vh
	local row = n + 1
	for side = 1, 4 do -- N, E, S, W: height index = p * hStride + hBase + 1, mesh vertex = k * vStride + vBase + 1
		local coarse, hStride, hBase, vStride, vBase
		if side == 1 then coarse, hStride, hBase, vStride, vBase = sN, 1, 0, 1, 0
		elseif side == 2 then coarse, hStride, hBase, vStride, vBase = sE, GRID, CELLS, row, n
		elseif side == 3 then coarse, hStride, hBase, vStride, vBase = sS, 1, CELLS * GRID, 1, n * row
		else coarse, hStride, hBase, vStride, vBase = sW, GRID, 0, row, 0 end
		for k = 0, n do
			local e = k * step -- position along the edge in grid units
			local value = h[e * hStride + hBase + 1]
			if coarse > step then
				local e0 = floor(e / coarse) * coarse
				local e1 = min(CELLS, e0 + coarse)
				local f = (e - e0) / coarse
				local h0 = h[e0 * hStride + hBase + 1]
				value = h0 + (h[e1 * hStride + hBase + 1] - h0) * f
			end
			vh[k * vStride + vBase + 1] = value
		end
	end
end

local function ReleaseMesh(key)
	local m = meshes[key]
	if not m then return end
	for _, t in ipairs(m.tris) do t.shown = false; ReleaseTex(t.tex) end
	meshes[key] = nil
end

------------------------------------------------------------------------------------------------
-- Buildings: Data/Detail_<map>.lua, ns.Detail[map][ty * 64 + tx] = one string per tile with buildings,
-- holding meshes of 66.7-yard blocks (8 x 8 per tile; see scripts/browser_export_detail.js):
--   "D2", block count (2 chars), then per block: index (1: by * 8 + bx), base (3: lowest height in
--   quarter yards + 131072), vertices (3), triangles (3), palette size (1), palette (3 per colour),
--   vertices (6: x 7 bits | y 7 | quarter yards above base 16 | colour 6, 0 = ground), corners (2
--   chars each, 3 when the block has more than 4095 vertices). x east, y south in 1.04-yard steps.
-- ns.DetailLow and ns.DetailFar hold the same blocks coarser (vertices 4.2 and 8.3 yards apart), for
-- blocks further away. Blocks are decoded when first needed; the strings stay as they are.
------------------------------------------------------------------------------------------------
ns.Detail, ns.DetailLow, ns.DetailFar = ns.Detail or {}, ns.DetailLow or {}, ns.DetailFar or {}
local LEVEL_DATA = { "Detail", "DetailLow", "DetailFar" }

local function Num(s, pos, n)
	local v = 0
	for i = pos, pos + n - 1 do v = v * 64 + B64[s:byte(i)] end
	return v
end
ns.B64, ns.Num = B64, Num -- (Models.lua reads its data with them)

-- A tile's blocks: { s = string, n = count, [block index] = position of the block in s }, or nil
local blockIndex = {}
local function TileBlocks(map, tx, ty, level)
	if tx < 0 or tx > 63 or ty < 0 or ty > 63 then return nil end
	level = level or 1
	local ck = (map * 4096 + ty * 64 + tx) * 4 + level
	local b = blockIndex[ck]
	if b ~= nil then return b or nil end
	local m = ns[LEVEL_DATA[level]][map]
	local s = m and m[ty * 64 + tx]
	if not s or s:sub(1, 2) ~= "D2" then blockIndex[ck] = false return nil end
	local nts = {} -- block index -> triangle count (known without decoding the block)
	b = { s = s, n = 0, nt = nts }
	local pos = 5
	for _ = 1, Num(s, 3, 2) do
		local nv, nt, np = Num(s, pos + 4, 3), Num(s, pos + 7, 3), Num(s, pos + 10, 1)
		local bi = Num(s, pos, 1)
		b[bi] = pos
		nts[bi] = nt
		b.n = b.n + 1
		pos = pos + 11 + np * 3 + nv * 6 + nt * 3 * (nv > 4095 and 3 or 2)
	end
	blockIndex[ck] = b
	return b
end
ns.TileBlocks = TileBlocks

-- Decoded block: vertices (world x, y, h, colour index), palette, triangle corners (1-based).
local geoCache, geoCount, geoClock = {}, 0, 0
local function BlockGeo(map, tx, ty, bi, level)
	level = level or 1
	local key = ((map * 4096 + ty * 64 + tx) * 64 + bi) * 4 + level -- a number: no string built per call
	geoClock = geoClock + 1
	local g = geoCache[key]
	if g then g.used = geoClock return g end
	local tb = TileBlocks(map, tx, ty, level)
	local pos = tb and tb[bi]
	if not pos then return nil end
	local s = tb.s
	local base = (Num(s, pos + 1, 3) - 131072) * 0.25
	local nv, nt, np = Num(s, pos + 4, 3), Num(s, pos + 7, 3), Num(s, pos + 10, 1)
	local p = pos + 11
	local pal = {}
	for k = 1, np do
		local r, gg, b = s:byte(p, p + 2)
		pal[k] = { B64[r] / 63, B64[gg] / 63, B64[b] / 63 }
		p = p + 3
	end
	local x0 = tx * TILE + (bi % BLOCKS) * BLOCK         -- north-west corner of the block
	local y0 = -ty * TILE - floor(bi / BLOCKS) * BLOCK
	local vx, vy, vh, vc = {}, {}, {}, {}
	local lo, hi = math.huge, -math.huge
	for k = 1, nv do
		local c1, c2, c3, c4, c5, c6 = s:byte(p, p + 5)
		local v = ((((B64[c1] * 64 + B64[c2]) * 64 + B64[c3]) * 64 + B64[c4]) * 64 + B64[c5]) * 64 + B64[c6]
		local col = v % 64
		v = (v - col) / 64
		local dh = v % 65536
		v = (v - dh) / 65536
		local sy = v % 128
		vx[k] = x0 + (v - sy) / 128 * STEP
		vy[k] = y0 - sy * STEP
		local h = base + dh * 0.25
		vh[k] = h
		vc[k] = col
		if h < lo then lo = h end
		if h > hi then hi = h end
		p = p + 6
	end
	local idx = {}
	if nv > 4095 then
		for k = 1, nt * 3 do
			local a, b, c = s:byte(p, p + 2)
			idx[k] = (B64[a] * 64 + B64[b]) * 64 + B64[c] + 1
			p = p + 3
		end
	else
		for k = 1, nt * 3 do
			local a, b = s:byte(p, p + 1)
			idx[k] = B64[a] * 64 + B64[b] + 1
			p = p + 2
		end
	end
	g = { key = key, map = map, tx = tx, ty = ty, bi = bi, level = level, x0 = x0, y0 = y0, vx = vx, vy = vy, vh = vh, vc = vc,
		pal = pal, idx = idx, nt = nt, lo = lo, hi = hi, used = geoClock }
	geoCache[key] = g
	geoCount = geoCount + 1
	if geoCount > GEO_LIMIT then -- forget the least recently used quarter
		local list = {}
		for k2, g2 in pairs(geoCache) do list[#list + 1] = g2 end
		table.sort(list, function(a, b) return a.used < b.used end)
		for i = 1, floor(#list / 4) do geoCache[list[i].key] = nil; geoCount = geoCount - 1 end
	end
	return g
end
ns.BlockGeo = BlockGeo

-- Height of a block's surface at (x, y), or nil outside it (triangles found through an 8 x 8 grid)
local function BlockHeight(g, x, y)
	local cs = BLOCK / 8
	local vx, vy, vh, idx = g.vx, g.vy, g.vh, g.idx
	if not g.cells then
		local cells = {}
		for q = 0, 63 do cells[q] = {} end
		for k = 1, g.nt do
			local a, b, c = idx[k * 3 - 2], idx[k * 3 - 1], idx[k * 3]
			local c0 = max(0, floor((min(vx[a], vx[b], vx[c]) - g.x0) / cs))
			local c1 = min(7, floor((max(vx[a], vx[b], vx[c]) - g.x0) / cs))
			local r0 = max(0, floor((g.y0 - max(vy[a], vy[b], vy[c])) / cs))
			local r1 = min(7, floor((g.y0 - min(vy[a], vy[b], vy[c])) / cs))
			for r = r0, r1 do for col = c0, c1 do local list = cells[r * 8 + col]; list[#list + 1] = k end end
		end
		g.cells = cells
	end
	local col, row = floor((x - g.x0) / cs), floor((g.y0 - y) / cs)
	if col < 0 or col > 7 or row < 0 or row > 7 then return nil end
	local best
	for _, k in ipairs(g.cells[row * 8 + col]) do
		local a, b, c = idx[k * 3 - 2], idx[k * 3 - 1], idx[k * 3]
		local ax, ay, bx, by, cx, cy = vx[a], vy[a], vx[b], vy[b], vx[c], vy[c]
		local den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
		if den ~= 0 then
			local w1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
			local w2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
			local w3 = 1 - w1 - w2
			if w1 >= -1e-6 and w2 >= -1e-6 and w3 >= -1e-6 then
				local h = w1 * vh[a] + w2 * vh[b] + w3 * vh[c]
				if not best or h > best then best = h end
			end
		end
	end
	return best
end

-- A block's triangles as textures: walls (steep, by a building's vertex) flat-coloured and shaded,
-- everything else the tile's minimap image.
local SUN = { -0.4, 0.8, -0.35 } -- east, up, south
do local l = sqrt(SUN[1] ^ 2 + SUN[2] ^ 2 + SUN[3] ^ 2) SUN[1], SUN[2], SUN[3] = SUN[1] / l, SUN[2] / l, SUN[3] / l end
local function BuildBlockMesh(g)
	local file = MinimapFile(g.map, g.tx, g.ty)
	local au, av, aw, ah = 0, 0, 1, 1
	if not file then file, au, av, aw, ah = OverviewOf(g.map, g.tx, g.ty) end
	local tx0, ty0 = g.tx * TILE, -g.ty * TILE
	local vx, vy, vh, vc, pal, idx = g.vx, g.vy, g.vh, g.vc, g.pal, g.idx
	local tris, walls = {}, 0
	local mesh = { detail = true, map = g.map, tx = g.tx, ty = g.ty, bi = g.bi, vx = vx, vy = vy, vh = vh, tris = tris, walls = walls, px = {}, py = {}, pd = {} }
	local uScale, vScale = aw / TILE, ah / TILE
	local s1, s2, s3 = SUN[1], SUN[2], SUN[3]
	for k = 1, g.nt do
		local a, b, c = idx[k * 3 - 2], idx[k * 3 - 1], idx[k * 3]
		local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
		local ex2, eh2, ez2 = vx[c] - vx[a], vh[c] - vh[a], -(vy[c] - vy[a])
		local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
		local l = sqrt(nx * nx + nh * nh + nz * nz)
		if l > 0 then nx, nh, nz = nx / l, nh / l, nz / l end
		local t = { a = a, b = b, c = c, tex = AcquireTex(), bucket = -1, frame = 1, shown = false, mesh = mesh }
		-- a wall: steep, and its highest corner is on a wall (has a colour); steep roofs show the minimap
		local wallVertex
		if abs(nh) < WALL_STEEPNESS then
			local top = a
			if vh[b] > vh[top] then top = b end
			if vh[c] > vh[top] then top = c end
			if vc[top] > 0 then wallVertex = top end
		end
		if wallVertex then
			local shade = 0.45 + 0.55 * abs(nx * s1 + nh * s2 + nz * s3)
			local col = pal[vc[wallVertex]] or pal[1]
			SetTriColour(t, col[1] * shade, col[2] * shade, col[3] * shade)
			walls = walls + 1
		elseif file then
			SetTriTexture(t, file, au + (vx[a] - tx0) * uScale, av + (ty0 - vy[a]) * vScale, au + (vx[b] - tx0) * uScale, av + (ty0 - vy[b]) * vScale, au + (vx[c] - tx0) * uScale, av + (ty0 - vy[c]) * vScale)
		else
			SetTriColour(t, 0.35, 0.42, 0.3)
		end
		tris[k] = t
	end
	mesh.walls = walls
	return mesh
end

local useDetail = true

-- Ground height at a world point: the building mesh where there is one, else the grid, else 0.
local function GroundHeight(map, x, y)
	if useDetail then
		local tx, ty = floor(x / TILE), floor(-y / TILE)
		local tb = TileBlocks(map, tx, ty)
		if tb then
			local bx = min(BLOCKS - 1, max(0, floor((x - tx * TILE) / BLOCK)))
			local by = min(BLOCKS - 1, max(0, floor((-ty * TILE - y) / BLOCK)))
			if tb[by * BLOCKS + bx] then
				local g = BlockGeo(map, tx, ty, by * BLOCKS + bx)
				local h = g and BlockHeight(g, x, y)
				if h then return h end
			end
		end
	end
	return GridHeight(map, x, y) or 0
end
ns.GroundHeight = function(x, y, map) return GroundHeight(map or ns.cam.map, x, y) end

-- Highest point of a tile, ground and buildings (0 where there is no terrain), read once from the block
-- strings without decoding them: lets the camera skip its ground checks when it is clearly above it all.
local tileTop = {}
local function TileTop(map, tx, ty)
	local ck = map * 4096 + ty * 64 + tx
	local top = tileTop[ck]
	if top then return top end
	local h = TileHeights(map, tx, ty)
	top = h and h.hi or 0
	local tb = useDetail and TileBlocks(map, tx, ty)
	if tb then
		local str = tb.s
		for bi = 0, BLOCKS * BLOCKS - 1 do
			local pos = tb[bi]
			if pos then
				local base = (Num(str, pos + 1, 3) - 131072) * 0.25
				local nv, np = Num(str, pos + 4, 3), Num(str, pos + 10, 1)
				local p, best = pos + 11 + np * 3, 0
				for _ = 1, nv do
					-- a vertex is x 7 bits | y 7 | height above base 16 | colour 6 in 6 characters
					local c3, c4, c5 = str:byte(p + 2, p + 4)
					local dh = (B64[c3] % 16) * 4096 + B64[c4] * 64 + B64[c5]
					if dh > best then best = dh end
					p = p + 6
				end
				if base + best * 0.25 > top then top = base + best * 0.25 end
			end
		end
	end
	tileTop[ck] = top
	return top
end
local function AreaTop(map, x0, x1, y0, y1) -- highest TileTop over the tiles under x0..x1 east, y0..y1 north
	local top = -math.huge
	for ty = floor(-y1 / TILE), floor(-y0 / TILE) do
		for tx = floor(x0 / TILE), floor(x1 / TILE) do
			local v = TileTop(map, tx, ty)
			if v > top then top = v end
		end
	end
	return top
end

------------------------------------------------------------------------------------------------
-- You
------------------------------------------------------------------------------------------------
local player = { on = false, map = nil, x = 0, y = 0, h = 0, facing = 0, hx = nil, hy = nil, surface = 0, z = nil, why = nil }
ns.player = player
ns.fake = nil -- /gps3d pretend: { angle } walks a circle round Northshire Abbey
local FAKE_X, FAKE_Y, FAKE_R = 32 * TILE + 178, -48 * TILE - 364, 70 -- outside the abbey walls all the way round
local Z_TRUST = 40 -- use the game's own height for you when it is this close to the map's surface

-- Reads your position into world coordinates; returns true when something changed.
local function ReadPlayer()
	local x, y, facing, z, map
	if ns.fake then
		local a = ns.fake.angle
		map, x, y = 0, FAKE_X + FAKE_R * cos(a), FAKE_Y + FAKE_R * sin(a)
		facing = a -- moving counter-clockwise: heading = angle (0 = north)
	else
		-- GPS's own reading (GPS_API.PlayerPosition): one rule for both views, swapaxes and flipfacing included
		local m, gx, gy, f, Z = GPS.PlayerPosition()
		if not m then
			local changed = player.on or player.why ~= "nopos"
			player.on, player.why = false, "nopos"
			return changed
		end
		if not ns.World[m] then
			local changed = player.on or player.why ~= "nodata"
			player.on, player.why, player.map = false, "nodata", m
			return changed
		end
		map = m
		x, y = gx * TILE, -gy * TILE
		facing = f or player.facing
		if Usable(Z) and Z ~= 0 then z = Z end
	end
	if map ~= player.map or not player.hx or abs(x - player.hx) > 0.5 or abs(y - player.hy) > 0.5 then
		player.surface, player.hx, player.hy = GroundHeight(map, x, y), x, y
	end
	-- The map has one surface per spot (roofs, not the floors under them). When the game gives your
	-- height and it is near that surface, use it: indoors the arrow then sits on the floor you are on.
	local h = player.surface
	if z and abs(z - h) < Z_TRUST then h = z end
	local changed = not player.on or map ~= player.map or abs(x - player.x) > 0.02 or abs(y - player.y) > 0.02 or abs(facing - player.facing) > 0.005 or abs(h - player.h) > 0.05
	player.on, player.why, player.map, player.x, player.y, player.facing, player.h, player.z = true, nil, map, x, y, facing, h, z
	return changed
end
ns.ReadPlayer = ReadPlayer

local playerActor
local markerMode = "both" -- arrow | model | both

------------------------------------------------------------------------------------------------
-- Camera
------------------------------------------------------------------------------------------------
local cam = { map = 0, x = 32 * TILE + 173, y = -48 * TILE - 385, th = 80, dist = 330, yaw = 20, pitch = 45 }
local topDown = false -- the straight-down ring: tilt locked straight down
ns.cam = cam
local camMode = "free" -- free | follow | behind
local yawOffset = 0     -- Behind: how far you turned the view away from your facing (right-drag)
local function Following() return camMode ~= "free" end
local anim -- camera flight in progress

local function Focal()
	local _, h = canvas:GetSize()
	return (h / 2) / math.tan((cam.fov or FOV) / 2)
end
ns.Focal = Focal

-- Height: the camera keeps the altitude you gave it (panning over a mountain does not raise it);
-- cam.th is the height of the orbit point, the camera sits cam.dist away from it along the view.
-- Only where the ground (or a roof) under the camera comes within CLEARANCE is the camera lifted, as
-- far as needed and only while it is there (Lift); zooming in stops at that height (Zoom).
-- The highest ground (or roof) within 25 yards of a point: the point itself and four rings round it
local RINGS = { 6, 6, 12, 10, 18, 14, 25, 18 } -- radius, samples per ring (each ring turned a little against the last)
local RING_C, RING_S = {}, {}
do
	local k = 0
	for r = 1, #RINGS, 2 do
		for i = 0, RINGS[r + 1] - 1 do
			k = k + 1
			local a = (i + 0.37 * (r - 1) / 2) / RINGS[r + 1] * 2 * math.pi
			RING_C[k], RING_S[k] = RINGS[r] * cos(a), RINGS[r] * sin(a)
		end
	end
end
local function GroundUnder(x, y)
	local m = cam.map
	local g = GroundHeight(m, x, y)
	for k = 1, #RING_C do
		local h = GroundHeight(m, x + RING_C[k], y + RING_S[k])
		if h > g then g = h end
	end
	return g
end

-- How far the camera must rise to clear the ground, for a camera state (0 if it is clear)
local function LiftFor(x, y, th, dist, yaw, pitch)
	local yr, p = rad(yaw), rad(pitch)
	local cp, sp = cos(p), sin(p)
	local hx, hy = sin(yr), cos(yr) -- the view's direction on the ground
	local ex, ey, ez = x - hx * cp * dist, y - hy * cp * dist, th + sp * dist
	local m = cam.map
	-- the ground within 25 yd, unless the camera is clearly above everything in the tiles round it
	local need = -math.huge
	if ez - CLEARANCE < AreaTop(m, ex - 25, ex + 25, ey - 25, ey + 25) then need = GroundUnder(ex, ey) + CLEARANCE - ez end
	-- tilted, the view ahead must be clear too: the line of sight passes over the ground for the first
	-- AHEAD x cos(tilt)^2 of the way to the point looked at (by AHEAD_CLEAR, less toward its end), so a
	-- hill in front lifts the camera over it instead of filling the view. The cos^2 makes this fade out
	-- toward straight down, where the camera keeps its height until the ground itself comes close.
	local clearLen = AHEAD * dist * cp * cp
	local lx, ly = ex + hx * cp * clearLen, ey + hy * cp * clearLen -- where the checked part of the view ends
	if clearLen > 1 and (cp * clearLen > 4 * TILE or ez - sp * clearLen - AHEAD_CLEAR < AreaTop(m, min(ex, lx), max(ex, lx), min(ey, ly), max(ey, ly))) then
		local ns_ = min(AHEAD_SAMPLES, ceil(clearLen / AHEAD_STEP))
		for k = 1, ns_ do
			local f = k / ns_
			local t = clearLen * f
			local n = GroundHeight(m, ex + hx * cp * t, ey + hy * cp * t) + AHEAD_CLEAR * (1 - f) - (ez - sp * t)
			if n > need then need = n end
		end
	end
	return max(0, need)
end

local liftKey = {}
local function Lift()
	local k = liftKey
	if k.map ~= cam.map or k.x ~= cam.x or k.y ~= cam.y or k.th ~= cam.th or k.dist ~= cam.dist or k.yaw ~= cam.yaw or k.pitch ~= cam.pitch then
		k.map, k.x, k.y, k.th, k.dist, k.yaw, k.pitch = cam.map, cam.x, cam.y, cam.th, cam.dist, cam.yaw, cam.pitch
		k.lift = LiftFor(cam.x, cam.y, cam.th, cam.dist, cam.yaw, cam.pitch)
	end
	return k.lift
end
ns.Lift = Lift
local function ForgetLift() liftKey.map = nil; wipe(tileTop) end -- the ground changed (buildings switched on/off)
ns.ForgetLift = ForgetLift

-- forward (fx, fy, fz), right (rx, ry, 0), up (ux, uy, uz) and the camera position
local function CameraBasis()
	local yaw, p = rad(cam.yaw), rad(cam.pitch)
	local sy_, cy_, sp, cp = sin(yaw), cos(yaw), sin(p), cos(p)
	local fx, fy, fz = sy_ * cp, cy_ * cp, -sp
	local rx, ry = cy_, -sy_
	local ux, uy, uz = sy_ * sp, cy_ * sp, cp
	local cx, cy, cz = cam.x - fx * cam.dist, cam.y - fy * cam.dist, cam.th + Lift() - fz * cam.dist
	return fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz
end
ns.CameraBasis = CameraBasis

-- Screen position (from the canvas centre, y up) and depth of a world point.
local function Project(x, y, h)
	local F = Focal()
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = CameraBasis()
	local dx, dy, dz = x - cx, y - cy, h - cz
	local d = dx * fx + dy * fy + dz * fz
	if d <= NEAR then return nil end
	return (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d, d
end
ns.Project = Project

-- The view ray through a screen position: camera position and direction (not normalised)
local function ScreenRay(px, py)
	local F = Focal()
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = CameraBasis()
	return cx, cy, cz, fx + rx * px / F + ux * py / F, fy + ry * px / F + uy * py / F, fz + uz * py / F
end

-- The point at height h (default: the orbit point's) under a screen position.
local function ScreenToGround(px, py, h)
	local cx, cy, cz, dx, dy, dz = ScreenRay(px, py)
	if dz >= -1e-4 then return nil end -- at or above the horizon
	local t = ((h or cam.th + Lift()) - cz) / dz
	return cx + dx * t, cy + dy * t
end
ns.ScreenToGround = ScreenToGround

-- The ground (or roof) point under a screen position: x, y, height. Walks along the ray in growing
-- steps, then halves the last one; without a hit, the point at the orbit point's height.
local function ScreenToTerrain(px, py)
	local cx, cy, cz, dx, dy, dz = ScreenRay(px, py)
	local len = sqrt(dx * dx + dy * dy + dz * dz)
	dx, dy, dz = dx / len, dy / len, dz / len
	local m = cam.map
	local t0, t = 0, 2
	while t < 20000 do
		local x, y, z = cx + dx * t, cy + dy * t, cz + dz * t
		if z <= GroundHeight(m, x, y) then
			for _ = 1, 12 do
				local tm = (t0 + t) / 2
				local xm, ym = cx + dx * tm, cy + dy * tm
				if cz + dz * tm <= GroundHeight(m, xm, ym) then t = tm else t0 = tm end
			end
			local x2, y2 = cx + dx * t, cy + dy * t
			return x2, y2, cz + dz * t
		end
		if dz >= 0 and z > 5000 then break end
		t0 = t
		t = t + max(2, t * 0.03)
	end
	local gx, gy = ScreenToGround(px, py)
	if gx then return gx, gy, cam.th + Lift() end
	return nil
end
ns.ScreenToTerrain = ScreenToTerrain

local function ClampTarget()
	local b = Bounds(cam.map)
	if not b then return end
	cam.x = min((b.x1 + 1) * TILE, max(b.x0 * TILE, cam.x))
	cam.y = min(-b.y0 * TILE, max(-(b.y1 + 1) * TILE, cam.y))
end

------------------------------------------------------------------------------------------------
-- Choosing what to draw
------------------------------------------------------------------------------------------------
local lastUse = {} -- mesh key -> time last drawn
local active, nActive = {}, 0 -- meshes drawn this frame (mesh.active == frameNo marks them)
local stepOf = {}  -- tile key -> step this frame (for edge matching)
local activeBlocks = {} -- tile key -> { frame = frameNo, [block index] = true } for building blocks drawn this frame
local frameNo = 0
local VO_EPS = 0.25 -- a vertex that moved less than this many pixels keeps the screen position last sent
local NOFIXED = {}  -- building meshes: every vertex may keep its position
local TOTAL_BUCKETS = BUCKET_FRAMES * LAYER_BUCKETS
local SetVertexOffset = sea.SetVertexOffset -- the method itself: no lookup per call
local sort, HUGE = table.sort, math.huge

-- A triangle crossing the near plane is cut CLIP_D in front of the camera and its front part drawn
-- (3 or 4 corners: the texture's fourth corner takes the extra one), so ground right in front of a
-- low camera never shows holes. Returns its depth for sorting, or nil when it faces away.
local CLIP_D = NEAR + 0.5
local clipI, clipU, clipV = {}, {}, {}
local qx, qy, qd, qu, qv = {}, {}, {}, {}, {}
local clipW, clipH = 1e9, 1e9 -- half the canvas (set per frame): cut parts wholly off screen are skipped
local function DrawClipped(t, vx, vy, vh, pd, F, rx, ry, ux, uy, uz, cx, cy, cz)
	local a, b, c = t.a, t.b, t.c
	-- quick reject: all three corners beyond the same side of the view (most of these triangles are
	-- off to the side, where the near plane cuts through a whole row of ground)
	local kx, ky = clipW / F, clipH / F
	local ax_, bx_, cx2 = vx[a] - cx, vx[b] - cx, vx[c] - cx
	local ay_, by_, cy2 = vy[a] - cy, vy[b] - cy, vy[c] - cy
	local Xa, Xb, Xc = ax_ * rx + ay_ * ry, bx_ * rx + by_ * ry, cx2 * rx + cy2 * ry
	local da, db, dc = pd[a] * kx, pd[b] * kx, pd[c] * kx
	if (Xa > da and Xb > db and Xc > dc) or (Xa < -da and Xb < -db and Xc < -dc) then return nil end
	local Ya = ax_ * ux + ay_ * uy + (vh[a] - cz) * uz
	local Yb = bx_ * ux + by_ * uy + (vh[b] - cz) * uz
	local Yc = cx2 * ux + cy2 * uy + (vh[c] - cz) * uz
	da, db, dc = pd[a] * ky, pd[b] * ky, pd[c] * ky
	if (Ya > da and Yb > db and Yc > dc) or (Ya < -da and Yb < -db and Yc < -dc) then return nil end
	clipI[1], clipI[2], clipI[3] = a, b, c
	local uvs = t.u1
	if uvs then clipU[1], clipV[1], clipU[2], clipV[2], clipU[3], clipV[3] = t.u1, t.v1, t.u2, t.v2, t.u3, t.v3 end
	local n = 0
	for e = 1, 3 do
		local f = e % 3 + 1
		local i, j = clipI[e], clipI[f]
		local di, dj = pd[i], pd[j]
		local x, y, h, d
		if di > CLIP_D then
			n = n + 1
			x, y, h, d = vx[i], vy[i], vh[i], di
			qd[n] = d
			if uvs then qu[n], qv[n] = clipU[e], clipV[e] end
			local dx, dy, dz = x - cx, y - cy, h - cz
			qx[n], qy[n] = (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d
		end
		if (di > CLIP_D) ~= (dj > CLIP_D) then
			local s = (CLIP_D - di) / (dj - di)
			n = n + 1
			x, y, h = vx[i] + (vx[j] - vx[i]) * s, vy[i] + (vy[j] - vy[i]) * s, vh[i] + (vh[j] - vh[i]) * s
			qd[n] = CLIP_D
			if uvs then qu[n], qv[n] = clipU[e] + (clipU[f] - clipU[e]) * s, clipV[e] + (clipV[f] - clipV[e]) * s end
			local dx, dy, dz = x - cx, y - cy, h - cz
			qx[n], qy[n] = (dx * rx + dy * ry) * F / CLIP_D, (dx * ux + dy * uy + dz * uz) * F / CLIP_D
		end
	end
	-- facing: twice the polygon's area, same sign rule as whole triangles
	local area = (qx[2] - qx[1]) * (qy[3] - qy[1]) - (qx[3] - qx[1]) * (qy[2] - qy[1])
	if n == 4 then area = area + (qx[3] - qx[1]) * (qy[4] - qy[1]) - (qx[4] - qx[1]) * (qy[3] - qy[1]) end
	if not (area > 0) then return nil end
	local x0, x1, y0, y1 = qx[1], qx[1], qy[1], qy[1]
	for k = 2, n do
		local x, y = qx[k], qy[k]
		if x < x0 then x0 = x elseif x > x1 then x1 = x end
		if y < y0 then y0 = y elseif y > y1 then y1 = y end
	end
	if x1 < -clipW or x0 > clipW or y1 < -clipH or y0 > clipH then return nil end
	local tex = t.tex
	-- corners in order round the polygon: upper left, lower left, lower right, upper right
	local k3, k4 = 3, n == 4 and 4 or 3
	SetVertexOffset(tex, 1, qx[1] + 0.5, qy[1] - 0.5)
	SetVertexOffset(tex, 2, qx[2] + 0.5, qy[2] + 0.5)
	SetVertexOffset(tex, 4, qx[k3] - 0.5, qy[k3] + 0.5)
	SetVertexOffset(tex, 3, qx[k4] - 0.5, qy[k4] - 0.5)
	if uvs then tex:SetTexCoord(qu[1], qv[1], qu[2], qv[2], qu[k4], qv[k4], qu[k3], qv[k3]) end
	t.x1, t.x2, t.x3 = nil, nil, nil -- every corner is sent again once it is whole
	t.clipped = true
	local sum = qd[1] + qd[2] + qd[3] + (n == 4 and qd[4] or 0)
	return sum / n
end

-- Per-frame work tables, reused (no garbage): tile candidates, building-block candidates, budget per level
local cands = {}  -- cands[i] = { tx, ty, key, d, toTarget, step }
local blist, bpool = {}, {}  -- blist[i] = { c, bi, d, x0, y1 } (the tables live in bpool; blist is the sorted view)
local function ByDistance(p, q) return p.d < q.d end

-- Does a box (x0..x1 east, y0..y1 north, lo..hi up) reach into the view?
local function BoxInView(x0, x1, y0, y1, lo, hi, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, halfW, halfH)
	local inFront, left, right, below, above = false, true, true, true, true
	for c = 0, 7 do
		local px_ = (c % 2 == 0) and x0 or x1
		local py_ = (c % 4 < 2) and y0 or y1
		local ph = (c < 4) and lo or hi
		local dx, dy, dz = px_ - cx, py_ - cy, ph - cz
		local d = dx * fx + dy * fy + dz * fz
		if d > NEAR then
			inFront = true
			local s = F / d
			local sx = (dx * rx + dy * ry) * s
			local sy = (dx * ux + dy * uy + dz * uz) * s
			if sx > -halfW then left = false end
			if sx < halfW then right = false end
			if sy > -halfH then below = false end
			if sy < halfH then above = false end
		else
			-- behind the camera: can still stretch across the screen
			left, right, below, above = false, false, false, false
		end
	end
	return inFront and not (left or right or below or above)
end

-- Tiles in view with a level of detail each, within the triangle budget: fills cands, returns how many.
local function ChooseTiles(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
	local map = cam.map
	local m = ns.World[map]
	if not m then return 0 end
	local w, hgt = canvas:GetSize()
	local halfW, halfH = w / 2 + 40, hgt / 2 + 40
	-- how far to look: the view's footprint, at most a few times the camera distance
	local range = min(30000, max(1500, cam.dist * 7 + 1200))
	local tgx, tgy = cx / TILE, -cy / TILE
	local r = ceil(range / TILE)
	local n = 0
	local camx, camy, halfDist = cam.x, cam.y, cam.dist * 0.5
	for ty = max(0, floor(tgy) - r), min(63, floor(tgy) + r) do
		for tx = max(0, floor(tgx) - r), min(63, floor(tgx) + r) do
			local key = ty * 64 + tx
			if m[key] then
				local x0, x1, y1, y0 = tx * TILE, (tx + 1) * TILE, -ty * TILE, -(ty + 1) * TILE
				local nx, ny = min(x1, max(x0, cx)), min(y1, max(y0, cy))
				local d2 = (nx - cx) ^ 2 + (ny - cy) ^ 2
				if d2 <= range * range then
					local h = TileHeights(map, tx, ty)
					if BoxInView(x0, x1, y0, y1, h.lo, h.hi, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, halfW, halfH) then
						-- distance to the ground at the tile's nearest point; never less than half the
						-- camera distance (the camera may hang inside a tall tile's box)
						local dz = cz - (GridHeight(map, nx, ny) or h.lo)
						local tdx, tdy = min(x1, max(x0, camx)), min(y1, max(y0, camy))
						n = n + 1
						local c = cands[n]
						if not c then c = {}; cands[n] = c end
						c.tx, c.ty, c.key = tx, ty, key
						c.d = max(sqrt(d2 + dz * dz), halfDist)
						c.toTarget = sqrt((tdx - camx) ^ 2 + (tdy - camy) ^ 2)
					end
				end
			end
		end
	end
	-- level of detail: cells about CELL_PX on screen, coarser until within the budget
	local px = CELL_PX
	for _ = 1, 12 do
		local tris = 0
		for i = 1, n do
			local c = cands[i]
			local want = px * max(c.d, 1) / F
			local step = 1
			while step < CELLS and step * CELL < want do step = step * 2 end
			c.step = step
			local nn = CELLS / step
			tris = tris + 2 * nn * nn
		end
		if tris <= TRI_BUDGET then break end
		px = px * 1.3
	end
	return n
end

local function RenderWorld(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
	local now = GetTime()
	local map = cam.map
	frameNo = frameNo + 1
	local nCands = ChooseTiles(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
	wipe(stepOf)
	for i = 1, nCands do local c = cands[i]; stepOf[c.key] = c.step end
	nActive = 0
	stats.tiles, stats.tris = nCands, 0
	wipe(stats.steps)
	local mapKey = map * 4096
	for i = 1, nCands do
		local c = cands[i]
		local tx, ty, step = c.tx, c.ty, c.step
		-- the sharp minimap image whenever the tile is big on screen at its nearest point
		local sharp = TILE * F / max(c.d, 1) > MINIMAP_PX
		local key = ((mapKey + c.key) * 64 + step) * 2 + (sharp and 1 or 0) -- grid meshes: a positive number
		local mesh = meshes[key]
		if not mesh then mesh = BuildGridMesh(map, tx, ty, step, sharp); meshes[key] = mesh end
		if mesh then
			FixEdges(mesh, stepOf[(ty - 1) * 64 + tx] or step, stepOf[ty * 64 + tx + 1] or step, stepOf[(ty + 1) * 64 + tx] or step, stepOf[ty * 64 + tx - 1] or step)
			mesh.key = key
			mesh.active = frameNo
			nActive = nActive + 1
			active[nActive] = mesh
			lastUse[key] = now
			stats.tris = stats.tris + #mesh.tris
			stats.steps[step] = (stats.steps[step] or 0) + 1
		end
	end
	-- buildings: blocks near the view's centre, nearest first, within the budget, on top of the grid
	stats.detail, stats.detailTris, stats.detailSkipped, stats.detailPending, stats.detailReach = 0, 0, 0, 0, 0
	local levels = stats.detailLevels
	levels[1], levels[2], levels[3] = 0, 0, 0
	if useDetail and cam.dist < DETAIL_DIST then
		local w, hgt = canvas:GetSize()
		local halfW, halfH = w / 2 + 40, hgt / 2 + 40
		local camx, camy = cam.x, cam.y
		local nBlocks = 0
		for i = 1, nCands do
			local c = cands[i]
			local tb = c.toTarget < DETAIL_RANGE and TileBlocks(map, c.tx, c.ty)
			if tb then
				local tx0, ty0 = c.tx * TILE, -c.ty * TILE
				for bi = 0, BLOCKS * BLOCKS - 1 do
					if tb[bi] then
						local x0 = tx0 + (bi % BLOCKS) * BLOCK
						local y1 = ty0 - floor(bi / BLOCKS) * BLOCK
						local nx, ny = min(x0 + BLOCK, max(x0, camx)), min(y1, max(y1 - BLOCK, camy))
						local d = sqrt((nx - camx) ^ 2 + (ny - camy) ^ 2)
						-- (where the game's own buildings are shown, Models.lua, the block is left out)
						if d < DETAIL_RANGE and not (ns.ModelsCover and ns.ModelsCover(x0, y1)) then
							nBlocks = nBlocks + 1
							local e = bpool[nBlocks]
							if not e then e = {}; bpool[nBlocks] = e end
							e.c, e.bi, e.d, e.x0, e.y1 = c, bi, d, x0, y1
							blist[nBlocks] = e
						end
					end
				end
			end
		end
		for i = #blist, nBlocks + 1, -1 do blist[i] = nil end
		sort(blist, ByDistance)
		local used, built, drawn = 0, 0, 0
		local budget = DETAIL_BUDGET
		for i = 1, nBlocks do
			local e = blist[i]
			if used >= budget - 20 then stats.detailSkipped = stats.detailSkipped + 1 else
			-- on screen at all? (the tile's ground heights, plus room for buildings)
			local c, bi = e.c, e.bi
			local h = TileHeights(map, c.tx, c.ty)
			if BoxInView(e.x0, e.x0 + BLOCK, e.y1 - BLOCK, e.y1, h.lo, h.hi + 150, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, halfW, halfH) then
				-- level by distance from the camera, coarser while the wanted one's share is used up
				-- (triangle counts come from the tile index: only the level drawn is decoded)
				local bx_, by_ = e.x0 + BLOCK / 2, e.y1 - BLOCK / 2
				local dc = sqrt((bx_ - cx) ^ 2 + (by_ - cy) ^ 2 + ((h.lo + h.hi) / 2 - cz) ^ 2)
				local ppy = F / max(dc, 1)
				local want = (LEVEL_STEP[3] * ppy <= LEVEL_PX and 3) or (LEVEL_STEP[2] * ppy <= LEVEL_PX and 2) or 1
				local g
				local tb = TileBlocks(map, c.tx, c.ty, want)
				local nt = tb and tb.nt[bi]
				if nt and used + nt <= budget then g = BlockGeo(map, c.tx, c.ty, bi, want) end
				if not g then
					stats.detailSkipped = stats.detailSkipped + 1
				else
					local key = -g.key -- detail meshes: a negative number
					local mesh = meshes[key]
					if not mesh and built > 0 and built + g.nt > BUILD_LIMIT then
						stats.detailPending = stats.detailPending + 1 -- made in a later frame; the grid shows meanwhile
					else
						if not mesh then mesh = BuildBlockMesh(g); meshes[key] = mesh; built = built + g.nt end
						mesh.key = key
						mesh.active = frameNo
						nActive = nActive + 1
						active[nActive] = mesh
						lastUse[key] = now
						drawn = drawn + g.nt
						levels[g.level] = levels[g.level] + 1
						if e.d > stats.detailReach then stats.detailReach = e.d end
						local ab = activeBlocks[c.key]
						if not ab then ab = {}; activeBlocks[c.key] = ab end
						if ab.frame ~= frameNo then wipe(ab); ab.frame = frameNo end
						ab[bi] = true
						stats.detail = stats.detail + 1
					end
					-- a pending block keeps its place in the budget
					used = used + g.nt
				end
			end
			end
		end
		stats.detailTris = drawn
	end
	-- hide what is not drawn this frame; give back textures of meshes unused for a while
	local crowded = poolMade - poolN > TEX_LIMIT
	for key, mesh in pairs(meshes) do
		if mesh.active ~= frameNo then
			if not mesh.hidden then
				local tris = mesh.tris
				for k = 1, #tris do local t = tris[k]; if t.shown then t.shown = false; t.tex:Hide() end end
				mesh.hidden = true
			end
			if crowded or now - (lastUse[key] or 0) > KEEP_SECONDS or mesh.map ~= map then ReleaseMesh(key); lastUse[key] = nil end
		end
	end
	-- project the vertices; the depth range (for the buckets) from the vertices in front of the camera
	local dmin, dmax = HUGE, -HUGE
	for i = 1, nActive do
		local mesh = active[i]
		mesh.hidden = false
		local vxs, vys, vhs, px, py, pd = mesh.vx, mesh.vy, mesh.vh, mesh.px, mesh.py, mesh.pd
		local fixed = mesh.fixed or NOFIXED
		local lo, hi = HUGE, -HUGE
		for k = 1, #vxs do
			local x, y, z = vxs[k] - cx, vys[k] - cy, vhs[k] - cz
			local d = x * fx + y * fy + z * fz
			pd[k] = d
			if d > NEAR then
				local s = F / d
				local nx, ny = (x * rx + y * ry) * s, (x * ux + y * uy + z * uz) * s
				-- moved less than VO_EPS px since last drawn: keep the old position (the mesh stays
				-- consistent, and triangles whose corners all kept still need no SetVertexOffset);
				-- not for vertices shared with other meshes, which would open hairline cracks
				local ox, oy = px[k], py[k]
				if not (ox and not fixed[k] and nx - ox <= VO_EPS and ox - nx <= VO_EPS and ny - oy <= VO_EPS and oy - ny <= VO_EPS) then
					px[k], py[k] = nx, ny
				end
				if d < lo then lo = d end
				if d > hi then hi = d end
			end
		end
		local under = not mesh.detail and activeBlocks[mesh.tkey] -- building blocks drawn on this tile
		if under and under.frame ~= frameNo then under = nil end
		mesh.under = under or false
		if under then hi = hi + DETAIL_BIAS end
		if lo < dmin then dmin = lo end
		if hi > dmax then dmax = hi end
	end
	-- cull, sort into buckets and draw: one pass over the triangles
	local scale = (TOTAL_BUCKETS - 0.001) / max(dmax - dmin, 1e-6)
	do local w, h = canvas:GetSize(); clipW, clipH = w / 2 + 2, h / 2 + 2 end
	local visible, nVisible, culled, behind, cut = stats.visible or {}, 0, 0, 0, 0
	stats.visible = visible
	for i = 1, nActive do
		local mesh = active[i]
		local px, py, pd, under, tris = mesh.px, mesh.py, mesh.pd, mesh.under, mesh.tris
		for k = 1, #tris do
			local t = tris[k]
			local a, b, c = t.a, t.b, t.c
			local da, db, dc = pd[a], pd[b], pd[c]
			local depth
			if da > CLIP_D and db > CLIP_D and dc > CLIP_D then
				local ax, ay, bx, by, cx_, cy_ = px[a], py[a], px[b], py[b], px[c], py[c]
				if (bx - ax) * (cy_ - ay) - (cx_ - ax) * (by - ay) > 0 then
					local tex = t.tex
					if t.clipped then
						t.clipped = false
						if t.u1 then tex:SetTexCoord(t.u1, t.v1, t.u2, t.v2, t.u3, t.v3, t.u3, t.v3) end
					end
					-- a corner whose vertex kept its screen position needs no SetVertexOffset
					if ax ~= t.x1 or ay ~= t.y1 then
						SetVertexOffset(tex, 1, ax + 0.5, ay - 0.5) -- upper left  = a
						t.x1, t.y1 = ax, ay
					end
					if bx ~= t.x2 or by ~= t.y2 then
						SetVertexOffset(tex, 2, bx + 0.5, by + 0.5) -- lower left  = b
						t.x2, t.y2 = bx, by
					end
					if cx_ ~= t.x3 or cy_ ~= t.y3 then
						SetVertexOffset(tex, 3, cx_ - 0.5, cy_ - 0.5) -- upper right = c
						SetVertexOffset(tex, 4, cx_ - 0.5, cy_ + 0.5) -- lower right pinned onto c
						t.x3, t.y3 = cx_, cy_
					end
					depth = (da + db + dc) / 3
				else
					culled = culled + 1
				end
			elseif da > CLIP_D or db > CLIP_D or dc > CLIP_D then
				-- crosses the near plane: cut, not hidden
				depth = DrawClipped(t, mesh.vx, mesh.vy, mesh.vh, pd, F, rx, ry, ux, uy, uz, cx, cy, cz)
				if depth then cut = cut + 1 else culled = culled + 1 end
			else
				behind = behind + 1
			end
			if depth then
				nVisible = nVisible + 1
				visible[nVisible] = t
				local tex = t.tex
				if under and under[t.blk] then depth = depth + DETAIL_BIAS end
				local bucket = floor((dmax - depth) * scale)
				if bucket < 0 then bucket = 0 elseif bucket >= TOTAL_BUCKETS then bucket = TOTAL_BUCKETS - 1 end
				if bucket ~= t.bucket or tex.bucketFrame ~= t.frame then
					t.bucket = bucket
					local f = floor(bucket / LAYER_BUCKETS) + 1
					local inner = bucket % LAYER_BUCKETS
					if f ~= tex.bucketFrame then tex:SetParent(bucketFrames[f]); tex.bucketFrame = f end
					t.frame = f
					tex:SetDrawLayer(LAYERS[floor(inner / 16) + 1], inner % 16 - 8)
				end
				if not t.shown then t.shown = true; tex:Show() end
			elseif t.shown then
				t.shown = false; t.tex:Hide()
			end
		end
	end
	for n = nVisible + 1, #visible do visible[n] = nil end
	stats.shown, stats.culled, stats.behind, stats.cut = nVisible, culled, behind, cut
end

-- The arrow under you: a square on the ground, pointing where you face, drawn in perspective.
local function DecalCorners()
	local s = max(3, cam.dist * 0.05)                       -- half size in yards; readable when zoomed out
	local f = player.facing
	local fwx, fwy = -sin(f), cos(f)                        -- forward on the ground (facing 0 = north)
	local rtx, rty = cos(f), sin(f)                         -- to the right of forward
	local h = player.h + 0.4
	local x, y = player.x, player.y
	return {
		{ x + (fwx - rtx) * s, y + (fwy - rty) * s, h }, -- upper left  (tip side, left)
		{ x + (-fwx - rtx) * s, y + (-fwy - rty) * s, h }, -- lower left
		{ x + (fwx + rtx) * s, y + (fwy + rty) * s, h }, -- upper right
		{ x + (-fwx + rtx) * s, y + (-fwy + rty) * s, h }, -- lower right
	}
end
ns.DecalCorners = DecalCorners

local function MarkerVisible() return player.on and player.map == cam.map end

local function UpdateMarker()
	if not MarkerVisible() then
		decal:Hide()
		if playerActor then playerActor:Hide() end
		return
	end
	if markerMode ~= "model" then
		-- the four corners of DecalCorners(), projected with one camera basis and no tables
		local s = max(3, cam.dist * 0.05)
		local f = player.facing
		local fwx, fwy = -sin(f), cos(f)
		local rtx, rty = cos(f), sin(f)
		local x, y, h = player.x, player.y, player.h + 0.4
		local F = Focal()
		local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = CameraBasis()
		local ok = true
		for k = 1, 4 do
			local px_, py_
			if k == 1 then px_, py_ = x + (fwx - rtx) * s, y + (fwy - rty) * s
			elseif k == 2 then px_, py_ = x + (-fwx - rtx) * s, y + (-fwy - rty) * s
			elseif k == 3 then px_, py_ = x + (fwx + rtx) * s, y + (fwy + rty) * s
			else px_, py_ = x + (-fwx + rtx) * s, y + (-fwy + rty) * s end
			local dx, dy, dz = px_ - cx, py_ - cy, h - cz
			local d = dx * fx + dy * fy + dz * fz
			if d <= NEAR then ok = false break end
			local sx, sy = (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d
			decal:SetVertexOffset(k, sx + (k <= 2 and 0.5 or -0.5), sy + ((k == 1 or k == 3) and -0.5 or 0.5))
		end
		if ok then decal:Show() else decal:Hide() end
	else
		decal:Hide()
	end
	if markerMode ~= "arrow" then
		if not playerActor then
			playerActor = NewActor()
			if playerActor then playerActor:SetModelByUnit("player") end
		end
		if playerActor then
			playerActor:SetPosition(player.x, player.y, player.h)
			playerActor:SetYaw(player.facing + (GPS3D_DB and GPS3D_DB.modelYaw or MODEL_YAW))
			playerActor:SetScale(max(1, cam.dist / 150)) -- stays visible when zoomed out
			playerActor:Show()
		end
	elseif playerActor then
		playerActor:Hide()
	end
end

local compassYaw
-- The grid in the straight-down ring: ground squares u (east) and v (north) from -1 to 1, turned
-- anticlockwise by the yaw like the needle, then seen from GRID_D squares away at the camera's tilt.
local UpdateGrid
do -- (in a block: the main chunk is near Lua 5.1's limit of 200 local variables)
	local GRID_D = 4            -- viewing distance in grid squares: how strong the perspective is
	local GRID_E = 1 / 6        -- the cell texture's inset (1/8 of it each side), in grid squares
	local GRID_R = 0.22         -- the grid stays within this share of the ring's width from its centre (0.3 until 2026-10-18: it reached the ring in the game)
	local gridFit = {}          -- tilt (tenths of a degree) -> px per grid square
	local CELLS = { { -1, -1 }, { 0, -1 }, { -1, 0 }, { 0, 0 } }
	local function GridPoint(u, v, ct, st, sp, cp, scale)
		local x, f = u * ct - v * st, u * st + v * ct -- right, and forward (away from the camera)
		local k = GRID_D / (GRID_D + f * cp)
		return x * k * scale, f * sp * k * scale
	end
	function UpdateGrid()
		local p, t = rad(cam.pitch), rad(cam.yaw)
		local sp, cp, ct, st = sin(p), cos(p), cos(t), sin(t)
		local key = floor(cam.pitch * 10 + 0.5)
		local scale = gridFit[key]
		if not scale then
			-- the furthest a grid corner gets from the centre at this tilt, over every turn
			local worst = 0
			for i = 0, 63 do
				local a = i * math.pi / 32
				local x, y = GridPoint(1.4143 * cos(a), 1.4143 * sin(a), 1, 0, sp, cp, 1)
				worst = max(worst, sqrt(x * x + y * y))
			end
			scale = topButton:GetWidth() * GRID_R / worst
			gridFit[key] = scale
		end
		local lo, hi = -GRID_E, 1 + GRID_E
		for i, c in ipairs(CELLS) do
			local tex, u0, v0 = topButton.cells[i], c[1], c[2]
			-- corners: 1 upper left (far left), 2 lower left, 3 upper right, 4 lower right; the
			-- texture is 1x1 at the ring's centre, so each offset is the corner's place minus (-+0.5, +-0.5)
			local x, y = GridPoint(u0 + lo, v0 + hi, ct, st, sp, cp, scale); SetVertexOffset(tex, 1, x + 0.5, y - 0.5)
			x, y = GridPoint(u0 + lo, v0 + lo, ct, st, sp, cp, scale); SetVertexOffset(tex, 2, x + 0.5, y + 0.5)
			x, y = GridPoint(u0 + hi, v0 + hi, ct, st, sp, cp, scale); SetVertexOffset(tex, 3, x - 0.5, y - 0.5)
			x, y = GridPoint(u0 + hi, v0 + lo, ct, st, sp, cp, scale); SetVertexOffset(tex, 4, x - 0.5, y + 0.5)
		end
	end

end
ns.UpdateGrid = UpdateGrid

local function UpdateCompass()
	-- north on screen: the direction +y points to, seen from above the orbit point
	if cam.yaw == compassYaw and cam.pitch == compass.pitch then return end
	compassYaw, compass.pitch = cam.yaw, cam.pitch
	-- north on screen is at (-sin yaw, cos yaw): the needle (drawn pointing up) turned anticlockwise by yaw
	compass.icon:SetRotation(rad(cam.yaw))
	UpdateGrid()
end

local function MapName(map)
	local m = GPS.Maps and GPS.Maps[map]
	return m and m.name or ("Map " .. tostring(map))
end

local titleText, subtitleMap
local function UpdateTitle()
	-- the zone in the middle of the view (GPS's ZoneNameAt), else where you are, else the map
	local zone = GPS.ZoneNameAt and GPS.ZoneNameAt(cam.map, cam.x / TILE, -cam.y / TILE)
	if not zone and Following() and player.on and player.map == cam.map and not ns.fake and GetZoneText then zone = GetZoneText() end
	local text = (zone and zone ~= "") and zone or MapName(cam.map)
	if text ~= titleText then ui.title:SetText(text); titleText = text end
	if cam.map ~= subtitleMap then ui.subtitle:SetText(MapName(cam.map)); subtitleMap = cam.map end
end

local UpdateFooter
do
	local CAMERA_WORDS = { follow = "Following", behind = "Behind you", free = "Free camera" }
	function UpdateFooter()
		if not player.on then
			if player.why == "nodata" then
				ui.footer:SetText(("No 3D terrain for %s (only maps with outdoor terrain have it)"):format(MapName(player.map)))
			else
				ui.footer:SetText("Your position is not available here.   /gps3d pretend shows a stand-in")
			end
		elseif player.map ~= cam.map then
			ui.footer:SetText("You are on another map.   Me brings the view to you")
		else
			-- where you are, and the camera mode in brass (the controls are in the rings' tooltips)
			local where = (not ns.fake and GPS.WhereText) and GPS.WhereText() or ""
			ui.footer:SetText(("%s%s|cffc9a24a%s|r"):format(where, where ~= "" and "   " or "", CAMERA_WORDS[camMode] or ""))
		end
	end
end

local function Render()
	if not frame:IsShown() then return end
	local t0 = debugprofilestop()
	local F = Focal()
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = CameraBasis()
	RenderWorld(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
	-- the models' camera: the same pose in Blizzard's terms (forward = cosP cosY, cosP sinY, -sinP)
	scene:SetCameraPosition(cx, cy, cz)
	scene:SetCameraOrientationByYawPitchRoll(rad(90 - cam.yaw), rad(min(cam.pitch, 89.9)), 0)
	scene:SetCameraFieldOfView(cam.fov or FOV)
	if ns.UpdateModels then ns.UpdateModels(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz) end -- the game's models (Models.lua)
	for _, a in ipairs(actors) do
		if a.map == cam.map then a.actor:SetPosition(a.x, a.y, a.h); a.actor:Show() else a.actor:Hide() end
	end
	UpdateMarker()
	if ns.UpdateQuestPins then ns.UpdateQuestPins() end
	if ns.UpdateAddonPins then ns.UpdateAddonPins() end -- other addons' markers (GPS's Compat.lua)
	UpdateCompass()
	UpdateTitle()
	stats.ms = debugprofilestop() - t0
	local p = ns.perf -- the debug log's frame-time sums (GPS3D_API.TakePerf)
	if p then
		p.n, p.sum, p.tris = p.n + 1, p.sum + stats.ms, p.tris + stats.tris + stats.detailTris
		if stats.ms > p.max then p.max = stats.ms end
	end
end
ns.Render = Render

-- Only you moved (the camera did not): just the marker, not the world.
local function RenderMarker()
	if not frame:IsShown() then return end
	UpdateMarker()
	UpdateTitle()
end

------------------------------------------------------------------------------------------------
-- Camera movement
------------------------------------------------------------------------------------------------
local function ShortYaw(from, to) return from + ((to - from + 540) % 360 - 180) end

-- The view that looks the way you face: camera yaw for your facing (facing 0 = north = yaw 0;
-- facing grows counter-clockwise, yaw clockwise).
local function BehindYaw() return (-deg(player.facing) + yawOffset) % 360 end

local function SetCamMode(mode)
	if mode ~= camMode then GPS.Log("3D", "camera %s -> %s", tostring(camMode), mode) end
	camMode = mode
	camButton:SetIcon(camButton.icons[mode], 0.62)
	camButton:SetActive(mode ~= "free") -- gold while locked onto you
	ui.me:SetActive(mode ~= "free")
	if mode ~= "free" then
		GPS3D_DB = GPS3D_DB or {}
		GPS3D_DB.camMode = mode -- the way you like to be followed, used when the window opens
	end
	UpdateFooter()
end
ns.CamMode = function() return camMode end
ns.SetCamMode = SetCamMode
ns.IsFollowing = Following

-- Smoothly moves the camera to new values (x, y, th, dist, yaw, pitch).
local function FlyTo(target, duration, onDone)
	local start = {}
	for k in pairs(target) do start[k] = cam[k] end
	if target.yaw then target.yaw = ShortYaw(start.yaw, target.yaw) end
	anim = { t = 0, d = duration or 0.4, start = start, target = target, done = onDone }
end
ns.FlyTo = FlyTo

-- Locks the view straight down, or gives back the tilt it had before.
local function SetTopDown(on, instant)
	if (on and true or false) ~= topDown then GPS.Log("3D", "straight down %s", tostring(on and true or false)) end
	topDown = on and true or false
	topButton:SetActive(topDown)
	GPS3D_DB = GPS3D_DB or {}
	GPS3D_DB.topDown = topDown -- false is remembered too (straight down is the default)
	local want
	if topDown then
		if cam.pitch < MAX_PITCH - 0.01 then cam.tiltBefore = cam.pitch end
		want = MAX_PITCH
	else
		want = cam.tiltBefore or 45
	end
	if instant then cam.pitch = want else FlyTo({ pitch = want }, 0.4) end
end
ns.SetTopDown = SetTopDown
ns.IsTopDown = function() return topDown end
topButton:SetScript("OnClick", function() SetTopDown(not topDown) end)

local function StepAnimation(elapsed)
	if not anim then return false end
	anim.t = anim.t + elapsed
	local u = min(1, anim.t / anim.d)
	local e = u * u * (3 - 2 * u)
	for k, v in pairs(anim.target) do cam[k] = anim.start[k] + (v - anim.start[k]) * e end
	if u >= 1 then
		cam.yaw = cam.yaw % 360
		local done = anim.done
		anim = nil
		if done then done() end
	end
	return true
end

-- Puts the view on another map (camera jumps; no flight between maps).
local function SetMap(map, x, y)
	if cam.map ~= map then
		GPS.Log("3D", "view map %s -> %s (%s)", tostring(cam.map), tostring(map), MapName(map))
		cam.map = map
		anim = nil
	end
	if x then cam.x, cam.y = x, y end
	ClampTarget()
	cam.th = GroundHeight(cam.map, cam.x, cam.y)
	UpdateFooter()
end

-- Locks the camera onto you (mode "follow" or "behind") and flies there.
local function FollowMe(mode)
	mode = mode or (camMode ~= "free" and camMode) or (GPS3D_DB and GPS3D_DB.camMode) or "follow"
	ReadPlayer()
	if not player.on then
		GPS.Log("3D", "Me: cannot follow you (%s, map %s)", tostring(player.why), tostring(player.map))
		SetCamMode("free")
		if player.why == "nodata" then
			print(("|cff55ff55GPS3D|r: no 3D terrain for %s"):format(MapName(player.map)))
		else
			print("|cff55ff55GPS3D|r: your position is not available here (/gps3d pretend shows a stand-in)")
		end
		return
	end
	yawOffset = 0 -- straight behind you again
	SetCamMode(mode)
	if player.map ~= cam.map then SetMap(player.map, player.x, player.y) end
	local target = { x = player.x, y = player.y, th = player.h }
	if mode == "behind" then target.yaw = BehindYaw() end
	FlyTo(target, 0.5)
end
ns.FollowMe = FollowMe

local function CursorInCanvas()
	local x, y = GetCursorPosition()
	local s = canvas:GetEffectiveScale()
	local w, h = canvas:GetSize()
	return x / s - canvas:GetLeft() - w / 2, y / s - (canvas:GetTop() - h / 2) -- from the centre, y up
end
ns.CursorInCanvas = CursorInCanvas

local drag -- { button, startX, startY, lastX, lastY, moved, grabX, grabY }
local lastClick = { time = 0, x = 0, y = 0 }

canvas:SetScript("OnMouseDown", function(self, button)
	local px, py = CursorInCanvas()
	drag = { button = button, startX = px, startY = py, lastX = px, lastY = py, moved = false }
	if button == "LeftButton" then
		-- grabbing the ground ends any flight; turning keeps a flight to you going
		anim = nil
		drag.grabX, drag.grabY, drag.grabH = ScreenToTerrain(px, py)
	end
end)

canvas:SetScript("OnMouseUp", function(self, button)
	if not drag then return end
	local d = drag
	drag = nil
	if d.button == "LeftButton" then
		if not d.moved then
			-- a click: double-click flies there
			local px, py = d.startX, d.startY
			local now = GetTime()
			if now - lastClick.time < CLICK_TIME and abs(px - lastClick.x) < CLICK_SLOP and abs(py - lastClick.y) < CLICK_SLOP then
				local gx, gy, gh = ScreenToTerrain(px, py)
				if gx then
					SetCamMode("free")
					-- the orbit point on the view line through the clicked point, at the same height as now:
					-- the point ends up in the middle and the camera keeps its altitude
					local yr, p = rad(cam.yaw), rad(cam.pitch)
					local s = (gh - cam.th) / sin(p)
					gx, gy = gx + sin(yr) * cos(p) * s, gy + cos(yr) * cos(p) * s
					local b = Bounds(cam.map)
					if b then
						gx = min((b.x1 + 1) * TILE, max(b.x0 * TILE, gx))
						gy = min(-b.y0 * TILE, max(-(b.y1 + 1) * TILE, gy))
					end
					FlyTo({ x = gx, y = gy }, 0.45)
				end
				lastClick.time = 0
			else
				lastClick.time, lastClick.x, lastClick.y = now, px, py
			end
		end
	end
end)
canvas:SetScript("OnHide", function() drag = nil end)

local function DragUpdate()
	if not drag then return false end
	local px, py = CursorInCanvas()
	if not drag.moved and abs(px - drag.startX) < CLICK_SLOP and abs(py - drag.startY) < CLICK_SLOP then return false end
	drag.moved = true
	local dx, dy = px - drag.lastX, py - drag.lastY
	drag.lastX, drag.lastY = px, py
	if dx == 0 and dy == 0 then return false end
	if drag.button == "LeftButton" then
		-- grab the ground: the point first clicked stays under the cursor
		if Following() then SetCamMode("free") end
		if drag.grabX then
			-- (again when the move changed the camera's lift over the ground, so the point stays put)
			for _ = 1, 3 do
				local gx, gy = ScreenToGround(px, py, drag.grabH)
				if not gx then break end
				local mx, my = drag.grabX - gx, drag.grabY - gy
				cam.x, cam.y = cam.x + mx, cam.y + my
				ClampTarget()
				if abs(mx) + abs(my) < 0.01 then break end
			end
		end
	else
		-- turn and tilt around the orbit point (keeps following; Behind remembers the turn)
		local turn = -dx * 0.4
		cam.yaw = (cam.yaw + turn) % 360
		if anim and anim.target.yaw then anim.target.yaw = anim.target.yaw + turn; anim.start.yaw = anim.start.yaw + turn end
		if camMode == "behind" then yawOffset = (yawOffset + turn + 180) % 360 - 180 end
		if not topDown then cam.pitch = max(MIN_PITCH, min(MAX_PITCH, cam.pitch - dy * 0.3)) end
	end
	return true
end
ns.DragUpdate = DragUpdate

-- Zooms by factor (< 1: in) toward the ground point under the cursor (free mode) or the orbit point.
-- Zooming in stops where the camera would come closer than CLEARANCE to the ground or a roof below it.
-- In free mode the height you see is kept from then on (a lift over a hill becomes your altitude).
local function Zoom(factor, px, py)
	local newDist = max(MIN_DIST, min(MAX_DIST, cam.dist * factor))
	local k = newDist / cam.dist
	if k == 1 then return end
	local following = Following()
	local lift = Lift()
	local ox, oy, oz = cam.x, cam.y, following and cam.th or cam.th + lift
	local zx, zy, zz = ox, oy, oz -- the point zoomed toward; it stays where it is on screen
	if not following and px then
		anim = nil
		local gx, gy, gh = ScreenToTerrain(px, py)
		if gx then zx, zy, zz = gx, gy, gh end
	end
	local function LiftAt(kk)
		return LiftFor(zx + (ox - zx) * kk, zy + (oy - zy) * kk, zz + (oz - zz) * kk, cam.dist * kk, cam.yaw, cam.pitch)
	end
	if k < 1 then
		local allowed = (following and lift or 0) + 0.5
		if LiftAt(k) > allowed then
			-- as far as the ground lets it: the smallest step that still clears it
			local lo, hi = k, 1
			for _ = 1, 14 do
				local mid = (lo + hi) / 2
				if LiftAt(mid) > allowed then lo = mid else hi = mid end
			end
			k = hi
			if k > 0.999 then Render() return end -- at the ground already
		end
	end
	cam.x, cam.y, cam.th = zx + (ox - zx) * k, zy + (oy - zy) * k, following and cam.th or zz + (oz - zz) * k
	if not following then ClampTarget() end
	cam.dist = cam.dist * k
	if anim and anim.target.dist then anim.target.dist = cam.dist end
	Render()
end
ns.Zoom = Zoom

frame:SetScript("OnMouseWheel", function(_, delta)
	local px, py = CursorInCanvas()
	Zoom(delta > 0 and 0.85 or 1 / 0.85, px, py)
end)
ui.zoomIn:SetScript("OnClick", function() Zoom(0.8) end)
ui.zoomOut:SetScript("OnClick", function() Zoom(1.25) end)
-- the camera ring steps Follow -> Behind -> Free -> Follow
camButton:SetScript("OnClick", function(self)
	if camMode == "follow" then FollowMe("behind")
	elseif camMode == "behind" then SetCamMode("free")
	else FollowMe("follow") end
	if GameTooltip:IsOwned(self) then self:GetScript("OnEnter")(self) end -- the tip follows the mode
end)
ui.me:SetScript("OnClick", function() FollowMe() end)
compass:SetScript("OnClick", function()
	if camMode == "behind" then SetCamMode("follow") end -- north up means no longer turning with you
	FlyTo({ yaw = 0 }, 0.4)
end)

-- Keeps the camera on you while following: moves with you, and in Behind turns with you.
local function FollowStep(elapsed)
	if not (Following() and player.on) then return false end
	local moved = false
	if player.map ~= cam.map then SetMap(player.map, player.x, player.y); moved = true end
	local target = anim and anim.target
	if target and target.x then
		target.x, target.y, target.th = player.x, player.y, player.h -- a flight to you keeps aiming at you
	elseif cam.x ~= player.x or cam.y ~= player.y or cam.th ~= player.h then
		cam.x, cam.y, cam.th = player.x, player.y, player.h
		moved = true
	end
	if camMode == "behind" then
		local want = BehindYaw()
		if target and target.yaw then
			target.yaw = ShortYaw(anim.start.yaw, want)
		elseif not (drag and drag.button ~= "LeftButton" and drag.moved) then
			local d = (want - cam.yaw + 540) % 360 - 180
			if abs(d) > 0.01 then
				-- ease round behind you rather than snapping with every turn
				cam.yaw = (cam.yaw + (abs(d) < 0.05 and d or d * min(1, elapsed * 6))) % 360
				moved = true
			end
		end
	end
	return moved
end
ns.FollowStep = FollowStep

-- One update loop: drags, flights, following you, re-rendering only when something changed.
local sinceRead = 0 -- seconds since the footer was last updated
frame:SetScript("OnUpdate", function(_, elapsed)
	local dirty, moved = DragUpdate(), false
	if ns.fake then ns.fake.angle = (ns.fake.angle + elapsed * 0.25) % (2 * math.pi) end
	-- your position every frame (following moves smoothly); the footer's text 5 times a second, and at
	-- once when your position comes or goes (no position here, no 3D terrain here)
	if ReadPlayer() then
		moved = true
		if player.why ~= ns.footerWhy then ns.footerWhy = player.why; sinceRead = 1 end
	end
	sinceRead = sinceRead + elapsed
	if sinceRead >= 0.2 then
		sinceRead = 0
		UpdateFooter()
	end
	if FollowStep(elapsed) then dirty = true end
	if StepAnimation(elapsed) then dirty = true end
	if stats.detailPending > 0 then dirty = true end -- building blocks still to be made
	if dirty then Render() elseif moved then RenderMarker() end -- you moved but the view did not: only the marker
end)

frame:SetScript("OnSizeChanged", function() Render() end)

------------------------------------------------------------------------------------------------
-- Showing the window
------------------------------------------------------------------------------------------------
local pendingFocus -- { map, gx, gy } from the 2D map: open there instead of on you

local function Open()
	GPS3D_DB = GPS3D_DB or {}
	markerMode = GPS3D_DB.marker or markerMode
	if GPS3D_DB.detail ~= nil then useDetail = GPS3D_DB.detail end
	if GPS3D_DB.buildings then DETAIL_BUDGET = GPS3D_DB.buildings end
	if GPS3D_DB.grid then TRI_BUDGET = GPS3D_DB.grid end
	anim = nil
	cam.pitch = max(MIN_PITCH, min(MAX_PITCH, cam.pitch))
	if GPS3D_DB.topDown ~= false then SetTopDown(true, true) else topButton:SetActive(false) end -- straight down unless turned off
	ReadPlayer()
	local focus = pendingFocus
	pendingFocus = nil
	if focus and ns.World[focus.map] then
		-- the 2D map was looking somewhere else: start there
		SetCamMode("free")
		SetMap(focus.map, focus.gx * TILE, -focus.gy * TILE)
	elseif player.on then
		-- open locked onto you, the way you last chose (Follow or Behind)
		SetCamMode(GPS3D_DB.camMode or "follow")
		SetMap(player.map, player.x, player.y)
		cam.th = player.h
		if camMode == "behind" then cam.yaw = BehindYaw() end
	else
		SetCamMode("free")
		SetMap(ns.World[cam.map] and cam.map or 0)
	end
	UpdateFooter()
	Render()
	return true
end

frame:SetScript("OnShow", function() Open() end)

-- The mode ring (GPS's ApplyChrome) steps to the next mode, the traditional map, or back to the 2D
-- map with a right-click, at the same place and size, looking where the 3D view looks (Focus).
GPS3D_API = {
	-- from: a window whose place and size to take; focus: { map, gx, gy } to look at (nil: follow you)
	Show = function(from, focus)
		if from and GPS.CopyGeometry then GPS.CopyGeometry(frame, from) end
		pendingFocus = focus
		if frame:IsShown() then Open() else frame:Show() end
	end,
	-- open the 3D window the way the mode ring does (in place of the window that is open, at its place
	-- and size, remembered as your mode): /gps3d and its test commands
	Open = function()
		if frame:IsShown() then return end
		if not (GPS.OpenNamed and GPS.OpenNamed("3D")) then frame:Show() end
	end,
	-- where the view looks, for the other modes: nil while it is locked onto you
	Focus = function()
		if Following() then return nil end
		return { map = cam.map, gx = cam.x / TILE, gy = -cam.y / TILE }
	end,
	frame = frame,
}

-- < and > around the map's name (as on GPS's 2D map): the previous or next map that has terrain, in
-- GPS's order, its main land seen whole from above, the camera freed from you.
function ns.CycleMap(step)
	local list = {}
	for _, id in ipairs(GPS.MapOrder or {}) do if ns.World[id] then list[#list + 1] = id end end
	if #list == 0 then return end
	local index
	for i, id in ipairs(list) do if id == cam.map then index = i break end end
	local map = index and list[(index - 1 + step) % #list + 1] or (step > 0 and list[1] or list[#list])
	local m = GPS.Maps and GPS.Maps[map]
	SetCamMode("free")
	if m then
		local x0, y0, x1, y1 = m.fitMinX or m.minX, m.fitMinY or m.minY, m.fitMaxX or m.maxX, m.fitMaxY or m.maxY
		SetMap(map, (x0 + x1 + 1) / 2 * TILE, -(y0 + y1 + 1) / 2 * TILE)
		cam.dist = max(MIN_DIST, min(MAX_DIST, max(x1 - x0 + 1, y1 - y0 + 1) * TILE * 0.9))
	else
		SetMap(map)
	end
	GPS.Log("3D", "map arrows: %s", MapName(map))
	Render()
end
ui.prev:SetScript("OnClick", function() ns.CycleMap(-1) end)
ui.next:SetScript("OnClick", function() ns.CycleMap(1) end)

------------------------------------------------------------------------------------------------
-- Extra models (tests)
------------------------------------------------------------------------------------------------
local function Place(what, x, y, scale, yaw, quiet)
	local actor = NewActor()
	if not actor then print("|cffff5555GPS3D|r could not create a ModelScene actor") return end
	local ok = actor:SetModelByFileID(what)
	actor:SetScale(scale or 1)
	actor:SetYaw(yaw or 0)
	actors[#actors + 1] = { actor = actor, map = cam.map, x = x, y = y, h = GroundHeight(cam.map, x, y), what = what }
	if quiet then return actor end
	Render()
	C_Timer.After(1.5, function()
		print(("|cff55ff55GPS3D|r model %s: set=%s loaded=%s fileID=%s"):format(tostring(what), tostring(ok), tostring((actor:IsLoaded())), tostring((actor:GetModelFileID()))))
	end)
	return actor
end
ns.Place = Place

local function ClearModels()
	for _, a in ipairs(actors) do a.actor:ClearModel(); a.actor:Hide() end
	wipe(actors)
end

------------------------------------------------------------------------------------------------
-- Self-test: prints a report to copy back (see TESTING.md)
------------------------------------------------------------------------------------------------
local function Report(fmt, ...)
	local text = fmt:format(...)
	print("|cff55ff55GPS3D test|r " .. text)
	GPS.Log("TEST", "3D %s", text)
end

local function SelfTest()
	GPS3D_API.Open()
	local nMaps, nTiles = 0, 0
	for _, m in pairs(ns.World) do
		nMaps = nMaps + 1
		for _ in pairs(m) do nTiles = nTiles + 1 end
	end
	local t0 = debugprofilestop()
	local bMaps, bTiles, bBlocks = 0, 0, 0
	for map, m in pairs(ns.Detail) do
		bMaps = bMaps + 1
		for key in pairs(m) do
			local tb = TileBlocks(map, key % 64, floor(key / 64))
			if tb then bTiles = bTiles + 1; bBlocks = bBlocks + tb.n end
		end
	end
	Report("world data: %d maps, %d tiles; buildings: %d maps, %d tiles, %d blocks (indexed in %.0f ms), %s",
		nMaps, nTiles, bMaps, bTiles, bBlocks, debugprofilestop() - t0, useDetail and "on" or "off")
	ReadPlayer()
	if player.on then
		Report("you: map %d (%s) at %.1f, %.1f (height %.1f), facing %.2f", player.map, MapName(player.map), player.x, player.y, player.h, player.facing)
		Report("height: game Z %s, map surface %.1f -> using %.1f (Z is used when within %d yd)", tostring(player.z), player.surface, player.h, Z_TRUST)
	else
		Report("you: %s", player.why == "nodata" and ("no 3D terrain for " .. MapName(player.map)) or "position not available (use /gps3d pretend to test the marker)")
	end
	local total, worst = 0, 0
	local yaw0 = cam.yaw
	for k = 1, 36 do
		cam.yaw = (yaw0 + k * 10) % 360
		Render()
		total = total + stats.ms
		worst = max(worst, stats.ms)
	end
	cam.yaw = yaw0
	Render()
	local steps = {}
	for s, nT in pairs(stats.steps) do steps[#steps + 1] = s * 1000 + nT end
	table.sort(steps)
	for i, v in ipairs(steps) do steps[i] = ("%dx%d"):format(v % 1000, floor(v / 1000)) end
	local lv = stats.detailLevels or { 0, 0, 0 }
	Report("render: %.1f ms average, %.1f ms worst over 36 orbit steps; %d tiles (%s cells of 16.7 yd); buildings: %d blocks (%d fine, %d coarse, %d far) out to %.0f yd, %d triangles (%d blocks over budget); %d triangles shown, %d culled; %d textures made",
		total / 36, worst, stats.tiles, table.concat(steps, " "), stats.detail, lv[1], lv[2], lv[3], stats.detailReach or 0, stats.detailTris, stats.detailSkipped, stats.shown, stats.culled, poolMade)
	local fx, fy, fz = CameraBasis()
	local gx, gy, gz = scene:GetCameraForward()
	if gx then
		Report("scene forward %.3f %.3f %.3f vs ours %.3f %.3f %.3f (should match)", gx, gy, gz, fx, fy, fz)
		local rx, ry, rz = scene:GetCameraRight()
		Report("scene right %.3f %.3f %.3f (ours: %.3f %.3f 0, or its negative)", rx or 0, ry or 0, rz or 0, cos(rad(cam.yaw)), -sin(rad(cam.yaw)))
	else
		Report("scene forward unavailable")
	end
	Report("scene fov %s (we set %.3f)", tostring(scene:GetCameraFieldOfView()), cam.fov or FOV)
	if ns.ModelsSelfTest then ns.ModelsSelfTest(Report) end -- the game's models: data, and whether buildings (WMOs) load
	C_Timer.After(3, function()
		local loaded, checked, files = 0, 0, {}
		for _, t in ipairs(stats.visible) do
			local f = t.tex.file
			if f and not files[f] then
				files[f] = true
				checked = checked + 1
				if t.tex.IsObjectLoaded and t.tex:IsObjectLoaded() then loaded = loaded + 1 end
			end
		end
		Report("images: %d of %d different terrain images in view report loaded", loaded, checked)
		local icons = (compass.icon:IsObjectLoaded() and 1 or 0) + (camButton.icon:IsObjectLoaded() and 1 or 0) + (topButton.cells[1]:IsObjectLoaded() and 1 or 0)
		Report("icons: %d of 3 (compass needle, camera mode, grid square from Media\\) loaded", icons)
		Report("marker (%s): arrow %s, character model %s; camera %s", markerMode, decal:IsShown() and "shown" or "hidden", playerActor and ("loaded=" .. tostring((playerActor:IsLoaded()))) or "not created", camMode)
		if ns.ModelsSelfTestLate then ns.ModelsSelfTestLate(Report) end
		Report("done")
	end)
end

------------------------------------------------------------------------------------------------
-- Your quests (GPS's Quests.lua finds them; the same markers as the 2D map): each at its point on
-- the ground, projected like your marker, redrawn with the view. On ns: this chunk is at Lua 5.1's
-- limit of locals.
------------------------------------------------------------------------------------------------
ns.questLayer = CreateFrame("Frame", nil, canvas)
ns.questLayer:SetAllPoints(canvas)
ns.questLayer:SetFrameLevel(canvas:GetFrameLevel() + BUCKET_FRAMES + 5) -- over the ground, the arrow and models
ns.questPins = {}
ns.UpdateQuestPins = function()
	local pins, n = ns.questPins, 0
	local list = GPS.QuestList and frame:IsShown() and GPS.QuestList(cam.map)
	if list then
		local stamp = GPS.QuestStamp()
		local hw, hh = canvas:GetWidth() / 2 + 16, canvas:GetHeight() / 2 + 16
		for _, q in ipairs(list) do
			local x, y = q.gx * TILE, -q.gy * TILE
			if q.h3d == nil then q.h3d = GroundHeight(cam.map, x, y) end -- q is rebuilt when quests change
			local sx, sy = Project(x, y, q.h3d)
			if sx and abs(sx) < hw and abs(sy) < hh then
				n = n + 1
				GPS.PlacePin(pins, n, q, stamp, GPS.NewQuestPin, ns.SetupQuestPin, ns.questLayer, canvas, "CENTER", sx, sy)
			end
		end
	end
	GPS.HidePins(pins, n)
end
-- (the tracked quest's marker sits over the others)
ns.SetupQuestPin = function(pin, q)
	GPS.SetupQuestPin(pin, q)
	pin:SetFrameLevel(ns.questLayer:GetFrameLevel() + (q.tracked and 2 or 1))
end
GPS3D_API.QuestsChanged = function() if frame:IsShown() then Render() end end

-- Other addons' markers (GatherMate2's nodes, from GPS's Compat.lua): on the ground like your
-- quests, within ADDON_RANGE yards of the middle of the view, while the camera is closer than
-- ADDON_DIST, at most ADDON_MAX; under the quest markers.
ns.addonLayer = CreateFrame("Frame", nil, canvas)
ns.addonLayer:SetAllPoints(canvas)
ns.addonLayer:SetFrameLevel(canvas:GetFrameLevel() + BUCKET_FRAMES + 4)
ns.addonPins = {}
ns.ADDON_RANGE, ns.ADDON_DIST, ns.ADDON_MAX = 700, 2000, 400
ns.UpdateAddonPins = function()
	local pins, n = ns.addonPins, 0
	local list, byTile, stamp
	if GPS.AddonNodes and frame:IsShown() and cam.dist < ns.ADDON_DIST then list, byTile, stamp = GPS.AddonNodes(cam.map) end
	if byTile then
		local R = ns.ADDON_RANGE
		local hw, hh = canvas:GetWidth() / 2 + 10, canvas:GetHeight() / 2 + 10
		local gx0, gx1 = floor((cam.x - R) / TILE), floor((cam.x + R) / TILE)
		local gy0, gy1 = floor(-(cam.y + R) / TILE), floor(-(cam.y - R) / TILE)
		for ty = gy0, gy1 do
			for tx = gx0, gx1 do
				local b = byTile[ty * 64 + tx]
				if b then
					for _, node in ipairs(b) do
						if n >= ns.ADDON_MAX then break end
						local x, y = node.gx * TILE, -node.gy * TILE
						if (x - cam.x) ^ 2 + (y - cam.y) ^ 2 <= R * R then
							if node.h3d == nil then node.h3d = GroundHeight(cam.map, x, y) end
							local sx, sy = Project(x, y, node.h3d)
							if sx and abs(sx) < hw and abs(sy) < hh then
								n = n + 1
								GPS.PlacePin(pins, n, node, stamp, GPS.NewAddonPin, GPS.SetupAddonPin, ns.addonLayer, canvas, "CENTER", sx, sy)
							end
						end
					end
				end
			end
		end
	end
	GPS.HidePins(pins, n)
	ns.addonShown = n
end
GPS3D_API.AddonPinsChanged = function() if frame:IsShown() then Render() end end

------------------------------------------------------------------------------------------------
-- The debug log (GPS's Debug.lua): what the view shows, and frame times since the last call
------------------------------------------------------------------------------------------------
GPS3D_API.DebugState = function()
	return ("3D map %s looking at %.2f, %.2f from %.0f yd, yaw %.0f, tilt %.1f, camera %s, straight down %s; you: %s; title %s; %d tiles, %d triangles, %d building blocks"):format(
		tostring(cam.map), cam.x / TILE, -cam.y / TILE, cam.dist, cam.yaw, cam.pitch, camMode, tostring(topDown),
		player.on and ("on the map at %.2f, %.2f, height %.1f"):format(player.x / TILE, -player.y / TILE, player.h) or ("not shown (" .. tostring(player.why) .. ")"),
		tostring(ui.title:GetText()), stats.tiles or 0, stats.tris or 0, stats.detail or 0) .. (ns.ModelsState and ("; " .. ns.ModelsState()) or "")
end
GPS3D_API.TakePerf = function()
	local on = GPS.DebugOn and GPS.DebugOn()
	local p = ns.perf
	if not on then ns.perf = nil return nil end
	ns.perf = { n = 0, sum = 0, max = 0, tris = 0 }
	local models = ns.TakeModelsPerf and ns.TakeModelsPerf() -- Models.lua: models shown, loading, picking times
	if not (p and p.n > 0) then return models end
	return ("3D: %d frames drawn, %.2f ms average, %.2f ms worst, %.0f triangles average"):format(p.n, p.sum / p.n, p.max, p.tris / p.n) .. (models and ("; " .. models) or "")
end

------------------------------------------------------------------------------------------------
-- Settings: the 3D view's part of GPS's page in Options > AddOns (GPS's Settings.lua shows them),
-- the same changes as the slash commands. On ns, not as locals: this chunk is at Lua 5.1's limit.
------------------------------------------------------------------------------------------------
ns.DB = function() GPS3D_DB = GPS3D_DB or {} return GPS3D_DB end
ns.Redraw = function() if frame:IsShown() then Render() end end
ns.SetMarker = function(v) markerMode = v; ns.DB().marker = v; ns.Redraw() end
ns.SetDetail = function(on)
	useDetail = on
	ForgetLift()
	ns.DB().detail = on
	player.hx = nil
	if ns.ModelsChanged then ns.ModelsChanged() end -- the game's buildings go with them (Models.lua)
	ns.Redraw()
end
ns.SetBuildingBudget = function(n) DETAIL_BUDGET = n; ns.DB().buildings = n; ns.Redraw() end
ns.SetGridBudget = function(n) TRI_BUDGET = n; ns.DB().grid = n; ns.Redraw() end
ns.SetModelYaw = function(degrees) ns.DB().modelYaw = rad(degrees); ns.Redraw() end

GPS3D_API.settings = {
	{ kind = "header", name = "3D view" },
	{
		kind = "choice", key = "GPS3D_Marker", name = "You are shown as",
		tooltip = "The arrow on the ground, your character, or both (/gps3d marker).",
		default = "both",
		choices = function() return { { "arrow", "Arrow" }, { "model", "Character" }, { "both", "Arrow and character" } } end,
		get = function() return GPS3D_DB and GPS3D_DB.marker end,
		set = function(v) ns.SetMarker(v) end,
	},
	{
		kind = "choice", key = "GPS3D_Camera", name = "Camera on you",
		tooltip = "How the view follows you when it opens and when you click Me: from above as it is turned, or from behind, looking your way (the ring under Me).",
		default = "follow",
		choices = function() return { { "follow", "Follow" }, { "behind", "Behind you" } } end,
		get = function() return GPS3D_DB and GPS3D_DB.camMode end,
		set = function(v)
			ns.DB().camMode = v
			if frame:IsShown() and Following() then FollowMe(v) end
		end,
	},
	{
		kind = "check", key = "GPS3D_TopDown", name = "Look straight down",
		tooltip = "Lock the view straight down (the bottom ring). Off: right-drag tilts it.",
		default = true,
		get = function() return not (GPS3D_DB and GPS3D_DB.topDown == false) end,
		set = function(v) SetTopDown(v, not frame:IsShown()) end,
	},
	{
		kind = "check", key = "GPS3D_Buildings", name = "Buildings",
		tooltip = "Buildings, bridges and walls close up. Off: the ground only (/gps3d detail).",
		default = true,
		get = function() return GPS3D_DB and GPS3D_DB.detail end,
		set = function(v) ns.SetDetail(v) end,
	},
	{
		kind = "slider", key = "GPS3D_BuildingBudget", name = "Building detail",
		tooltip = "Building triangles drawn per frame, nearest the middle of the view first. Lower is faster (/gps3d buildings).",
		default = 4000, min = 1000, max = 8000, step = 500,
		format = function(v) return ("%d"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.buildings end,
		set = function(v) ns.SetBuildingBudget(v) end,
	},
	{
		kind = "slider", key = "GPS3D_GridBudget", name = "Ground detail",
		tooltip = "Ground triangles drawn per frame; far ground gets coarser to stay within it. Lower is faster (/gps3d budget).",
		default = 3200, min = 1600, max = 6400, step = 400,
		format = function(v) return ("%d"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.grid end,
		set = function(v) ns.SetGridBudget(v) end,
	},
	{
		kind = "slider", key = "GPS3D_ModelYaw", name = "Turn your character",
		tooltip = "Only if your character faces the wrong way in the 3D view (/gps3d modelyaw).",
		default = 90, min = 0, max = 345, step = 15,
		format = function(v) return ("%d\194\176"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.modelYaw and floor(deg(GPS3D_DB.modelYaw) + 0.5) % 360 end,
		set = function(v) ns.SetModelYaw(v) end,
	},
}

------------------------------------------------------------------------------------------------
-- Slash command
------------------------------------------------------------------------------------------------
-- /gps3d                  open or close the 3D view
-- /gps3d test             self-test (copy the output back)
-- /gps3d pretend          a stand-in walks round Northshire Abbey, to try the marker anywhere
-- /gps3d marker <arrow|model|both>
-- /gps3d modelyaw <deg>   turn the character model if it faces the wrong way (default 90)
-- /gps3d detail <on|off>  buildings close up, or the grid everywhere
-- /gps3d budget <n>       ground (grid) triangles per frame (default 3200)
-- /gps3d buildings <n>    building triangles per frame (default 4000)
-- /gps3d top              look straight down (locked), or tilt freely again (the straight-down ring)
-- /gps3d model [id]       any model by FileDataID at the centre (default: an Elwynn tree, 189927;
--                         106965 is the Elwynn farmhouse WMO, to see whether buildings load)
-- /gps3d trees            scatter 40 trees around the centre
-- /gps3d clear            remove the extra models
-- /gps3d fov [rad]        override the models' field of view (no value: automatic)
-- /gps3d cam              print the scene camera's vectors
SLASH_GPS3D1 = "/gps3d"
SlashCmdList.GPS3D = function(msg)
	GPS.Log("SLASH", "/gps3d %s", msg or "")
	local cmd, arg = strtrim(msg or ""):match("^(%S*)%s*(.-)$")
	cmd = cmd:lower()
	if cmd == "test" then
		SelfTest()
	elseif cmd == "pretend" then
		ns.fake = not ns.fake and { angle = 0 } or nil
		print("|cff55ff55GPS3D|r: stand-in " .. (ns.fake and "on" or "off"))
		GPS3D_API.Open()
		if ns.fake then FollowMe() else ReadPlayer(); UpdateFooter(); Render() end
	elseif cmd == "marker" then
		if arg == "arrow" or arg == "model" or arg == "both" then ns.SetMarker(arg) end
		print("|cff55ff55GPS3D|r: marker " .. markerMode)
	elseif cmd == "detail" then
		if arg == "on" or arg == "off" then ns.SetDetail(arg == "on") end
		print("|cff55ff55GPS3D|r: buildings " .. (useDetail and "on" or "off"))
	elseif cmd == "top" then
		GPS3D_API.Open()
		SetTopDown(not topDown)
		print("|cff55ff55GPS3D|r: " .. (topDown and "looking straight down" or "tilt free"))
	elseif cmd == "buildings" then
		ns.SetBuildingBudget(tonumber(arg) or DETAIL_BUDGET)
		print(("|cff55ff55GPS3D|r: %d building triangles per frame"):format(DETAIL_BUDGET))
	elseif cmd == "budget" then
		ns.SetGridBudget(tonumber(arg) or TRI_BUDGET)
		print(("|cff55ff55GPS3D|r: %d grid triangles per frame"):format(TRI_BUDGET))
	elseif cmd == "modelyaw" then
		ns.SetModelYaw(tonumber(arg) or 90)
		print(("|cff55ff55GPS3D|r: model yaw %.0f degrees"):format(deg(GPS3D_DB.modelYaw)))
	elseif cmd == "model" then
		GPS3D_API.Open()
		Place(tonumber(arg) or 189927, cam.x, cam.y, 1, 0)
	elseif cmd == "trees" then
		GPS3D_API.Open()
		local placed, seed = 0, 7
		for _ = 1, 40 do
			seed = (seed * 1103515245 + 12345) % 2147483648
			local x = cam.x + (seed % 10000) / 10000 * 150 - 75
			seed = (seed * 1103515245 + 12345) % 2147483648
			local y = cam.y + (seed % 10000) / 10000 * 150 - 75
			Place(189927, x, y, 0.8 + (seed % 5) / 10, (seed % 628) / 100, true)
			placed = placed + 1
		end
		print(("|cff55ff55GPS3D|r placed %d trees"):format(placed))
		Render()
	elseif cmd == "clear" then
		ClearModels()
		Render()
	elseif cmd == "fov" then
		cam.fov = tonumber(arg)
		print(("|cff55ff55GPS3D|r fov %s (scene default was %s)"):format(tostring(cam.fov or "auto"), tostring(defaultFov)))
		Render()
	elseif cmd == "cam" then
		print("|cff55ff55GPS3D|r forward", scene:GetCameraForward())
		print("|cff55ff55GPS3D|r right", scene:GetCameraRight())
		print("|cff55ff55GPS3D|r up", scene:GetCameraUp())
		print("|cff55ff55GPS3D|r fov", scene:GetCameraFieldOfView(), "projected target", scene:Project3DPointTo2D(cam.x, cam.y, cam.th + Lift()))
	else
		if frame:IsShown() then frame:Hide() else GPS3D_API.Open() end
	end
end
