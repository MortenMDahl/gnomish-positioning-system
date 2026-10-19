-- GPS 3D: the whole planet. Zoom out past the 3D view's old limit (14,000 yards) and the view straightens
-- to look straight down; past HANDOVER the planet view takes over from the ground: both continents on a
-- ball, placed as on Blizzard's world map, the sea, the Maelstrom, clouds and the glow of the air round its
-- edge, and your arrow. The ground bends from flat (at HANDOVER) to round (at ROUND) as you zoom out, so the
-- view never jumps: at HANDOVER the planet view draws the same flat ground the 3D view was drawing.
--
-- The plane: Blizzard's world map of Azeroth in yards, X east and Y north (u * SW, -v * SH, u and v the
-- world map's 0..1 coordinates). Each continent's yards reach it by a scale (within 0.3 % of 1) and an offset
-- (LAYOUT): from the game's world map (C_Map: each continent's rectangle on it and its corners in the world)
-- or, where the game does not give them, from FALLBACK (the classic world map's numbers, as HereBeDragons-2.0
-- ships them for classic).
-- The ball: the plane wrapped round a sphere of RADIUS yards by a stereographic projection from the point
-- between the continents (where the Maelstrom is drawn): shapes are kept (the projection is conformal); land
-- further from the middle comes out a little smaller (about 13 % at the far coasts).
-- Bending: at curvature t (0 flat .. 1 round) the sphere's radius is RADIUS / t, placed so that the point
-- looked at stays where it is and its east and north stay east and north.
--
-- Drawing: the sea is one disc texture (tinted; the shading over it is a second one), the land is one
-- textured triangle per half of a block of tiles (as the ground is), clouds and the Maelstrom are quads on
-- the sphere. Close to the hand-over the land shows GPS's overview images (as the ground did); once a tile is
-- small on screen, the planet's own pages (Globe\Land_*.tga, the open sea transparent), and then the sea
-- turns from the minimap's dark water to blue, the shading, the glow, the clouds and the Maelstrom fade in.
local addonName, ns = ...
local GPS = GPS_API
local cam, canvas, TILE = ns.cam, ns.canvas, ns.TILE
if not (cam and canvas and TILE) then return end -- GPS3D.lua did not load

local sin, cos, sqrt, abs, floor, min, max, log = math.sin, math.cos, math.sqrt, math.abs, math.floor, math.min, math.max, math.log
local rad, pi = math.rad, math.pi
local atan2 = math.atan2 or math.atan -- (Lua 5.1 in the game; the sandbox's 5.4 has math.atan(y, x))

local FLAT_MAX = ns.MAX_DIST or 14000 -- the 3D view's old zoom limit: closer than this nothing changes
local HANDOVER = 18000      -- the planet view draws from here out (the view straightens to look down before it)
local ROUND = 55000         -- fully round from here
local GLOBE_MAX = 110000    -- furthest zoom
local RADIUS = 22000        -- the planet's radius in yards
local SWAP_HI, SWAP_LO = 24, 18 -- land tiles shrinking on screen from SWAP_HI to SWAP_LO pixels cross-fade from GPS's
                                -- overview images (as the ground shows them) to the planet's own pages (16 px a tile)
local LAND_PX = 40          -- a land block is at most this many pixels across (larger blocks further out)
local CLOUD_H = 700         -- clouds' height above the sea (their shadows fall that far below them)
local MAEL_SIZE = 5000      -- the Maelstrom's whirlpool: half size (yards)
local MAEL_TURN, STORM_TURN = 0.14, 0.05 -- its water's and its storm's turn (radians per second)
local STORM_SIZE = 1.45 * MAEL_SIZE -- the storm over it, half size
local NEAR = 1
local MEDIA = "Interface\\AddOns\\" .. addonName .. "\\Globe\\"
local SEA = GPS.colors and GPS.colors.sea or { 8 / 255, 17 / 255, 16 / 255 }
local BLUE = { 0.10, 0.27, 0.56 }
local LIGHT = { -0.45 / 1.0, 0.55, 0.70 } -- normalised below: from the upper left, a little toward you
do local l = sqrt(LIGHT[1] ^ 2 + LIGHT[2] ^ 2 + LIGHT[3] ^ 2); LIGHT[1], LIGHT[2], LIGHT[3] = LIGHT[1] / l, LIGHT[2] / l, LIGHT[3] / l end

local function Smooth(x)
	if x <= 0 then return 0 elseif x >= 1 then return 1 end
	return x * x * (3 - 2 * x)
end

------------------------------------------------------------------------------------------------
-- Layout: where the continents are on Blizzard's world map
------------------------------------------------------------------------------------------------
-- (GPS's World.lua: the continents' places on Blizzard's world map, from the game's C_Map or the classic
-- numbers; shared with the 2D map since 2026-10-19)
local layout, layoutInfo, FALLBACK, GameLayout = GPS.WorldLayout, GPS.WorldLayoutInfo, GPS.WorldFallback, GPS.WorldGameLayout
if not layout then return end -- (an older GPS without World.lua)
local X0, Y0 = 0, 0   -- the projection's centre (the middle of the box round the continents)
local MX, MY = 0, 0   -- the Maelstrom: the middle of the sea between the westernmost continent and the next one east
local mapList = {}    -- continents on the planet, in GPS's map order

local function Centres()
	wipe(mapList)
	local bx0, by0, bx1, by1 = math.huge, math.huge, -math.huge, -math.huge
	for _, e in pairs(layout) do bx0, by0, bx1, by1 = min(bx0, e.x0), min(by0, e.y0), max(bx1, e.x1), max(by1, e.y1) end
	X0, Y0 = (bx0 + bx1) / 2, (by0 + by1) / 2
	MX, MY = X0, Y0
	local west, east
	for _, e in pairs(layout) do
		if not west or e.x0 < west.x0 then west = e end
	end
	for _, e in pairs(layout) do
		if e ~= west and e.x0 >= west.x1 and (not east or e.x0 < east.x0) then east = e end
	end
	if west and east then MX = (west.x1 + east.x0) / 2 end
	for _, id in ipairs(GPS.MapOrder or {}) do if layout[id] then mapList[#mapList + 1] = id end end
	for m in pairs(layout) do
		local found = false
		for _, id in ipairs(mapList) do if id == m then found = true end end
		if not found then mapList[#mapList + 1] = m end
	end
end
Centres()
ns.GlobeLayout, ns.GlobeLayoutInfo = layout, layoutInfo
ns.GlobeCentres = function() return X0, Y0, MX, MY end -- (for the tests)
ns.GlobeChooseLayout = function() GPS.ChooseWorldLayout(); Centres() end

local function ToPlane(m, x, y) local e = layout[m]; return x * e.ax + e.bx, y * e.ay + e.by end
local function FromPlane(m, X, Y) local e = layout[m]; return (X - e.bx) / e.ax, (Y - e.by) / e.ay end
ns.GlobeToPlane, ns.GlobeFromPlane = ToPlane, FromPlane

-- The continent nearest a plane point (0 inside its land box)
local function NearestMap(X, Y)
	local best, bd
	for _, m in ipairs(mapList) do
		local e = layout[m]
		local dx = X < e.x0 and e.x0 - X or (X > e.x1 and X - e.x1 or 0)
		local dy = Y < e.y0 and e.y0 - Y or (Y > e.y1 and Y - e.y1 or 0)
		local d = dx * dx + dy * dy
		if not bd or d < bd then best, bd = m, d end
	end
	return best
end

------------------------------------------------------------------------------------------------
-- The sphere
------------------------------------------------------------------------------------------------
-- The unit vector of a plane point on a sphere of radius rt (stereographic, pole at X0, Y0): x east, y north
-- and z out of the plane at the pole.
local function Unit(X, Y, rt)
	local qx, qy = (X - X0) / (2 * rt), (Y - Y0) / (2 * rt)
	local s = qx * qx + qy * qy
	local k = 1 / (1 + s)
	return 2 * qx * k, 2 * qy * k, (1 - s) * k
end
-- back from a unit vector to the plane
local function PlaneOf(vx, vy, vz, rt)
	local k = 2 * rt / max(1 + vz, 1e-9)
	return X0 + vx * k, Y0 + vy * k
end
ns.GlobeUnit, ns.GlobePlaneOf = Unit, PlaneOf

-- One frame's state: curvature, the sphere's radius, the point looked at in the plane, the sphere's east,
-- north and up there, the current continent's scale, and the camera.
local G = { t = 0, rt = math.huge, flat = true, XF = 0, YF = 0, ex = 1, ey = 0, ez = 0, nx = 0, ny = 1, nz = 0, ox = 0, oy = 0, oz = 1, ax = 1, ay = 1,
	fx = 0, fy = 0, fz = -1, rx = 1, ry = 0, ux = 0, uy = 1, uz = 0, cx = 0, cy = 0, cz = 1, F = 1, stats = {} }
ns.GlobeFrameState = G

-- Where the ground starts to bend, the sea to turn blue and the sky to fade in: once a land tile is SWAP_LO
-- pixels on screen (the overview images have faded out by then), at least a quarter past the hand-over and
-- at most 32,000 yards (very large windows: the planet's pages are then shown a little larger than they are)
local function CurveStart()
	return min(32000, max(1.25 * HANDOVER, TILE * ns.Focal() / SWAP_LO))
end
-- curvature for a camera distance: 0 (flat) up to CurveStart, 1 (round) from ROUND
local function Curvature(d)
	local cs = CurveStart()
	if d <= cs then return 0 end
	return Smooth(log(d / cs) / log(max(ROUND, 1.6 * cs) / cs))
end
ns.GlobeCurvature, ns.GlobeCurveStart = Curvature, CurveStart

-- Sets the sphere for the point looked at (cam.map, cam.x, cam.y) and curvature t.
local function SetSphere(t)
	local e = layout[cam.map]
	-- the drawing's scale between the continent's yards and the plane's: the continent's own while the ground
	-- is (nearly) flat, so the hand-over is exact; 1 once it bends, so both continents draw the same ball
	local w = Smooth(t / 0.2)
	G.ax, G.ay = e.ax + (1 - e.ax) * w, e.ay + (1 - e.ay) * w
	G.XF, G.YF = ToPlane(cam.map, cam.x, cam.y)
	G.t = t
	if t < 1e-6 then
		G.flat, G.rt = true, math.huge
		return
	end
	G.flat = false
	local rt = RADIUS / t
	G.rt = rt
	local qx, qy = (G.XF - X0) / (2 * rt), (G.YF - Y0) / (2 * rt)
	local s = qx * qx + qy * qy
	local k = 1 / (1 + s)
	G.ox, G.oy, G.oz = 2 * qx * k, 2 * qy * k, (1 - s) * k
	-- east and north on the sphere there: the projection's derivatives (orthogonal, of equal length)
	local ex, ey, ez = 2 * (1 + s) - 4 * qx * qx, -4 * qx * qy, -4 * qx
	local nx, ny, nz = -4 * qx * qy, 2 * (1 + s) - 4 * qy * qy, -4 * qy
	local le, ln = sqrt(ex * ex + ey * ey + ez * ez), sqrt(nx * nx + ny * ny + nz * nz)
	G.ex, G.ey, G.ez = ex / le, ey / le, ez / le
	G.nx, G.ny, G.nz = nx / ln, ny / ln, nz / ln
end

-- The camera: straight down (the tilt drawn, cam.vp) at cam.dist from the point looked at, as the 3D view
-- places it, its orbit height fading to sea level as the ground bends.
local function SetCamera()
	local yaw, p = rad(cam.yaw), rad(cam.vp or cam.pitch)
	local sy_, cy_, sp, cp = sin(yaw), cos(yaw), sin(p), cos(p)
	G.fx, G.fy, G.fz = sy_ * cp, cy_ * cp, -sp
	G.rx, G.ry = cy_, -sy_
	G.ux, G.uy, G.uz = sy_ * sp, cy_ * sp, cp
	local th = (cam.th + (ns.Lift and ns.Lift() or 0)) * (1 - G.t)
	G.cx, G.cy, G.cz = cam.x - G.fx * cam.dist, cam.y - G.fy * cam.dist, th - G.fz * cam.dist
	G.F = ns.Focal()
end

-- World position (cam.map's yards, height up) of a plane point at height h, for this frame.
local function WorldOf(X, Y, h)
	if G.flat then return cam.x + (X - G.XF) / G.ax, cam.y + (Y - G.YF) / G.ay, h end
	local vx, vy, vz = Unit(X, Y, G.rt)
	local r = G.rt + h
	return cam.x + (vx * G.ex + vy * G.ey + vz * G.ez) * r / G.ax, cam.y + (vx * G.nx + vy * G.ny + vz * G.nz) * r / G.ay, (vx * G.ox + vy * G.oy + vz * G.oz) * r - G.rt
end
-- the same for a unit vector already known
local function WorldOfUnit(vx, vy, vz, h)
	local r = G.rt + h
	return cam.x + (vx * G.ex + vy * G.ey + vz * G.ez) * r / G.ax, cam.y + (vx * G.nx + vy * G.ny + vz * G.nz) * r / G.ay, (vx * G.ox + vy * G.oy + vz * G.oz) * r - G.rt
end

-- Screen position (from the canvas centre, y up) and depth of a world point.
local function Project(x, y, h)
	local dx, dy, dz = x - G.cx, y - G.cy, h - G.cz
	local d = dx * G.fx + dy * G.fy + dz * G.fz
	if d <= NEAR then return nil end
	local s = G.F / d
	return (dx * G.rx + dy * G.ry) * s, (dx * G.ux + dy * G.uy + dz * G.uz) * s, d
end
ns.GlobeProject = function(X, Y, h) return Project(WorldOf(X, Y, h or 0)) end

-- The point of the sphere under a screen position (sea level) as a unit vector in the sphere's axes, or nil
-- off the planet (bent ground only).
local function PickUnit(px, py)
	local dxr = G.fx + G.rx * px / G.F + G.ux * py / G.F
	local dyr = G.fy + G.ry * px / G.F + G.uy * py / G.F
	local dzr = G.fz + G.uz * py / G.F
	-- the sphere: centre straight under the point looked at, radius rt (in the plane's yards; the world's
	-- yards differ from them by the continent's scale, which is within 0.3 % of 1 and is taken into account)
	local ox, oy, oz = (G.cx - cam.x) * G.ax, (G.cy - cam.y) * G.ay, G.cz + G.rt -- camera from the centre
	local dx, dy, dz = dxr * G.ax, dyr * G.ay, dzr
	local a = dx * dx + dy * dy + dz * dz
	local b = 2 * (ox * dx + oy * dy + oz * dz)
	local c = ox * ox + oy * oy + oz * oz - G.rt * G.rt
	local disc = b * b - 4 * a * c
	if disc < 0 then return nil end
	local s = (-b - sqrt(disc)) / (2 * a)
	if s <= 0 then return nil end
	local lx, ly, lz = (ox + dx * s) / G.rt, (oy + dy * s) / G.rt, (oz + dz * s) / G.rt -- on the unit sphere, in the local frame
	-- back to the sphere's own axes: local east, north and up are e, n and o
	local vx = lx * G.ex + ly * G.nx + lz * G.ox
	local vy = lx * G.ey + ly * G.ny + lz * G.oy
	local vz = lx * G.ez + ly * G.nz + lz * G.oz
	return vx, vy, vz
end
-- The plane point under a screen position (sea level), or nil off the planet.
local function PickPlane(px, py)
	if G.flat then
		local dxr = G.fx + G.rx * px / G.F + G.ux * py / G.F
		local dyr = G.fy + G.ry * px / G.F + G.uy * py / G.F
		local dzr = G.fz + G.uz * py / G.F
		if dzr >= -1e-6 then return nil end
		local s = -G.cz / dzr
		return G.XF + (G.cx + dxr * s - cam.x) * G.ax, G.YF + (G.cy + dyr * s - cam.y) * G.ay
	end
	local vx, vy, vz = PickUnit(px, py)
	if not vx then return nil end
	return PlaneOf(vx, vy, vz, G.rt)
end
ns.GlobePickPlane, ns.GlobePickUnit = PickPlane, PickUnit

------------------------------------------------------------------------------------------------
-- Frames and textures
------------------------------------------------------------------------------------------------
local base = canvas:GetFrameLevel()
local function Layer(level)
	local f = CreateFrame("Frame", nil, canvas)
	f:SetAllPoints(canvas)
	f:SetFrameLevel(base + level)
	f:Hide()
	return f
end
local oceanFrame, landFrame, atlasFrame, skyFrame, markFrame = Layer(1), Layer(2), Layer(3), Layer(4), Layer(5)
ns.globeFrames = { oceanFrame, landFrame, atlasFrame, skyFrame, markFrame }

local bg = oceanFrame:CreateTexture(nil, "BACKGROUND", nil, -8) -- space, or the sea where the planet fills the view
bg:SetAllPoints(canvas)
bg:SetColorTexture(SEA[1], SEA[2], SEA[3], 1)
local disc = oceanFrame:CreateTexture(nil, "BORDER")
disc:SetTexture(MEDIA .. "Disc")
local shade = oceanFrame:CreateTexture(nil, "ARTWORK")
shade:SetTexture(MEDIA .. "Shade")
local mael = oceanFrame:CreateTexture(nil, "OVERLAY")
mael:SetTexture(MEDIA .. "Maelstrom")
mael:SetSize(1, 1)
mael:SetPoint("CENTER", canvas, "CENTER", 0, 0)
local storm = skyFrame:CreateTexture(nil, "OVERLAY", nil, 1) -- the storm over the Maelstrom (over the clouds)
storm:SetTexture(MEDIA .. "MaelstromStorm")
storm:SetSize(1, 1)
storm:SetPoint("CENTER", canvas, "CENTER", 0, 0)
local bolt = skyFrame:CreateTexture(nil, "OVERLAY", nil, 2) -- a lightning flash in it
bolt:SetTexture(MEDIA .. "MaelstromBolt")
bolt:SetBlendMode("ADD")
bolt:SetSize(1, 1)
bolt:SetPoint("CENTER", canvas, "CENTER", 0, 0)
bolt:Hide()
local glow = skyFrame:CreateTexture(nil, "OVERLAY", nil, 7)
glow:SetTexture(MEDIA .. "Glow")
local arrow = markFrame:CreateTexture(nil, "OVERLAY")
arrow:SetTexture("Interface\\Minimap\\MinimapArrow")
arrow:SetSize(1, 1)
arrow:SetPoint("CENTER", canvas, "CENTER", 0, 0)
ns.globeTex = { bg = bg, disc = disc, shade = shade, mael = mael, storm = storm, bolt = bolt, glow = glow, arrow = arrow }

-- Puts a texture (whose image is a disc or ring centred in it) over a square of half size r centred at
-- (x, y) on the canvas, cut to the canvas so it never grows past it; hidden when off the canvas.
local function PlaceSquare(tex, x, y, r)
	local w, h = canvas:GetSize()
	local x0, x1, y0, y1 = max(x - r, -w / 2), min(x + r, w / 2), max(y - r, -h / 2), min(y + r, h / 2)
	if x1 <= x0 or y1 <= y0 or r <= 0 then tex:Hide() return false end
	tex:ClearAllPoints()
	tex:SetPoint("BOTTOMLEFT", canvas, "CENTER", x0, y0)
	tex:SetPoint("TOPRIGHT", canvas, "CENTER", x1, y1)
	local u0, u1 = (x0 - (x - r)) / (2 * r), (x1 - (x - r)) / (2 * r)
	local v0, v1 = ((y + r) - y1) / (2 * r), ((y + r) - y0) / (2 * r)
	tex:SetTexCoord(u0, u1, v0, v1)
	tex:Show()
	return true
end

-- Triangle and quad textures: pools per frame
local function Pool(frame, layer)
	local free, n = {}, 0
	local p = {}
	function p.Get()
		local tex
		if n > 0 then tex = free[n]; free[n] = nil; n = n - 1
		else
			tex = frame:CreateTexture(nil, layer)
			tex:SetSize(1, 1)
			tex:SetPoint("CENTER", canvas, "CENTER", 0, 0)
			p.made = (p.made or 0) + 1
		end
		tex:Hide()
		return tex
	end
	function p.Put(tex)
		tex:Hide()
		tex.file = nil
		n = n + 1; free[n] = tex
	end
	return p
end
local landPool, atlasPool, cloudPool = Pool(landFrame, "ARTWORK"), Pool(atlasFrame, "ARTWORK"), Pool(skyFrame, "ARTWORK")
local shadowPool = Pool(skyFrame, "BORDER") -- the clouds' shadows on the sea and the land, under the clouds

local SetVertexOffset = bg.SetVertexOffset
-- a texture's four corners at screen points (upper left, lower left, upper right, lower right)
local function Corners(tex, x1, y1, x2, y2, x3, y3, x4, y4)
	SetVertexOffset(tex, 1, x1 + 0.5, y1 - 0.5)
	SetVertexOffset(tex, 2, x2 + 0.5, y2 + 0.5)
	SetVertexOffset(tex, 3, x3 - 0.5, y3 - 0.5)
	SetVertexOffset(tex, 4, x4 - 0.5, y4 + 0.5)
end

------------------------------------------------------------------------------------------------
-- Land: blocks of n x n tiles per continent (n = 1, 2, 4, 8), two triangles each
------------------------------------------------------------------------------------------------
local LAYERS = { "BACKGROUND", "BORDER", "ARTWORK", "OVERLAY" }
local BUCKETS = 64
local levels = {} -- map * 100 + n * 2 + (atlas and 1 or 0) -> level
local landSet = {} -- map -> { [tile key] = true }
local function LandSet(m)
	local s = landSet[m]
	if not s then
		s = {}
		local d = ns.GlobeData and ns.GlobeData.maps and ns.GlobeData.maps[m]
		if d then for _, k in ipairs(d.tiles) do s[k] = true end end
		landSet[m] = s
	end
	return s
end

-- height at a tile corner (as the 3D view's ground has it at its coarsest level)
local function CornerHeight(m, i, j)
	local TH = ns.TileHeights
	local h = TH(m, i, j)
	if h then return h[1] end
	h = TH(m, i - 1, j); if h then return h[33] end
	h = TH(m, i, j - 1); if h then return h[32 * 33 + 1] end
	h = TH(m, i - 1, j - 1); if h then return h[33 * 33] end
	return 0
end

-- the overview atlas holding a tile, as the 3D view's ground uses it: file, u, v, du, dv
local function Atlas(m, tx, ty)
	local mt = GPS.Maps and GPS.Maps[m]
	if not mt then return nil end
	for _, a in ipairs(mt.atlases) do
		if tx >= a.x0 and tx < a.x0 + a.cols and ty >= a.y0 and ty < a.y0 + a.rows then
			local px = GPS.OverviewPx or 64
			return GPS.OverviewPath .. a.file .. "." .. (GPS.OverviewExt or "jpg"), (tx - a.x0) * px / a.w, (ty - a.y0) * px / a.h, px / a.w, px / a.h
		end
	end
end

local function BuildLevel(m, n, atlas)
	local land = LandSet(m)
	local e = layout[m]
	local lv = { m = m, n = n, atlas = atlas, X = {}, Y = {}, H = {}, vx = {}, vy = {}, vz = {}, px = {}, py = {}, pd = {}, tris = {}, rt = nil, active = false }
	local index = {} -- corner key -> vertex index
	local nv = 0
	local function V(i, j)
		local key = j * 65 + i
		local k = index[key]
		if k then return k end
		nv = nv + 1
		local x, y = i * TILE, -j * TILE
		lv.X[nv], lv.Y[nv] = x * e.ax + e.bx, y * e.ay + e.by
		lv.H[nv] = CornerHeight(m, i, j)
		index[key] = nv
		return nv
	end
	local PAGE = ns.GlobeData and ns.GlobeData.page or 32
	for by = 0, 63, n do
		for bx = 0, 63, n do
			local has = false
			for ty = by, by + n - 1 do
				for tx = bx, bx + n - 1 do
					if land[ty * 64 + tx] then has = true end
				end
			end
			if has then
				local file, u0, v0, u1, v1
				if atlas then
					local f, u, v, du, dv = Atlas(m, bx, by)
					if f then file, u0, v0, u1, v1 = f, u, v, u + du, v + dv end
				end
				if not file then
					local qx, qy = floor(bx / PAGE), floor(by / PAGE)
					file = MEDIA .. ("Land_%d_%d_%d"):format(m, qx, qy)
					u0, v0 = (bx - qx * PAGE) / PAGE, (by - qy * PAGE) / PAGE
					u1, v1 = (bx + n - qx * PAGE) / PAGE, (by + n - qy * PAGE) / PAGE
				end
				local a, b, c, d = V(bx, by), V(bx, by + n), V(bx + n, by + n), V(bx + n, by) -- NW, SW, SE, NE
				local tris = lv.tris
				tris[#tris + 1] = { a = a, b = b, c = c, file = file, ua = u0, va = v0, ub = u0, vb = v1, uc = u1, vc = v1 }
				tris[#tris + 1] = { a = a, b = c, c = d, file = file, ua = u0, va = v0, ub = u1, vb = v1, uc = u1, vc = v0 }
			end
		end
	end
	lv.nv = nv
	return lv
end

ns.GlobeLevels = function() return levels end -- (for the tests)
local function Level(m, n, atlas)
	local key = m * 100 + n * 2 + (atlas and 1 or 0)
	local lv = levels[key]
	if not lv then lv = BuildLevel(m, n, atlas); levels[key] = lv end
	return lv
end

-- A level gets its textures once and keeps them (hidden when not drawn), so zooming back and forth past the
-- hand-over never sets thousands of images again in one frame. Assign hands out up to `budget` of them (the
-- idle warm-up below does it a few hundred at a time before the planet is first needed).
local function Assign(lv, budget)
	local tris = lv.tris
	local i = lv.assignedTo or 0
	if i >= #tris then return true end
	local pool = lv.atlas and atlasPool or landPool
	local last = min(#tris, i + budget)
	for k = i + 1, last do
		local t = tris[k]
		local tex = pool.Get()
		t.tex = tex
		tex:SetTexture(t.file)
		tex:SetTexCoord(t.ua, t.va, t.ub, t.vb, t.uc, t.vc, t.uc, t.vc)
		t.shown, t.bucket, t.x1, t.x2, t.x3, t.col, t.alpha = false, nil, nil, nil, nil, nil, nil
	end
	lv.assignedTo = last
	return last >= #tris
end
local function Activate(lv)
	if lv.active then return end
	lv.active = true
	Assign(lv, math.huge)
end
local function Deactivate(lv)
	if not lv.active then return end
	lv.active = false
	for _, t in ipairs(lv.tris) do if t.shown then t.shown = false; t.tex:Hide() end end
end

-- Idle warm-up: zoomed out past 6,000 yd on a continent, the hand-over's land (the overview images and the
-- planet's pages, every continent) is built and given its images a few hundred a frame.
local warmed = false
local function WarmUp(budget)
	if warmed then return end
	for _, m in ipairs(mapList) do
		for _, atlas in ipairs({ true, false }) do
			local lv = Level(m, 1, atlas)
			if not Assign(lv, budget) then return end
		end
	end
	warmed = true
end
ns.GlobeWarmUp = WarmUp

local frameLevels = {} -- level -> true: drawn this frame

-- darkness of the planet's shading at a point of its disc (x, y from -1 to 1, y up), as Shade.tga has it
local function Darkness(x, y)
	local r2 = x * x + y * y
	local z = r2 < 1 and sqrt(1 - r2) or 0
	local lam = x * LIGHT[1] + y * LIGHT[2] + z * LIGHT[3]
	if lam < 0 then lam = 0 elseif lam > 1 then lam = 1 end
	local d = 1 - (0.22 + 0.9 * lam)
	if d < 0 then d = 0 elseif d > 0.82 then d = 0.82 end
	return d
end
ns.GlobeDarkness = Darkness

local visible, nVis = {}, 0
local function DrawLand(lv, alpha, shadeK, dcx, dcy, rp)
	local rt, flat = G.rt, G.flat
	local X, Y, H, vx, vy, vz, px, py, pd = lv.X, lv.Y, lv.H, lv.vx, lv.vy, lv.vz, lv.px, lv.py, lv.pd
	if not flat and lv.rt ~= rt then
		for k = 1, lv.nv do vx[k], vy[k], vz[k] = Unit(X[k], Y[k], rt) end
		lv.rt = rt
	end
	local ex, ey, ez, nx, ny, nz, ox, oy, oz = G.ex, G.ey, G.ez, G.nx, G.ny, G.nz, G.ox, G.oy, G.oz
	local ax, ay, XF, YF, camx, camy = G.ax, G.ay, G.XF, G.YF, cam.x, cam.y
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, F = G.fx, G.fy, G.fz, G.rx, G.ry, G.ux, G.uy, G.uz, G.cx, G.cy, G.cz, G.F
	for k = 1, lv.nv do
		local wx, wy, wz
		if flat then
			wx, wy, wz = camx + (X[k] - XF) / ax, camy + (Y[k] - YF) / ay, H[k]
		else
			local a, b, c = vx[k], vy[k], vz[k]
			local r = rt + H[k]
			wx = camx + (a * ex + b * ey + c * ez) * r / ax
			wy = camy + (a * nx + b * ny + c * nz) * r / ay
			wz = (a * ox + b * oy + c * oz) * r - rt
		end
		local dx, dy, dz = wx - cx, wy - cy, wz - cz
		local d = dx * fx + dy * fy + dz * fz
		pd[k] = d
		if d > NEAR then
			local s = F / d
			px[k], py[k] = (dx * rx + dy * ry) * s, (dx * ux + dy * uy + dz * uz) * s
		end
	end
	local w, h = canvas:GetSize()
	local hw, hh = w / 2 + 2, h / 2 + 2
	local shown, culled = 0, 0
	for _, t in ipairs(lv.tris) do
		local a, b, c = t.a, t.b, t.c
		local ok = pd[a] > NEAR and pd[b] > NEAR and pd[c] > NEAR
		local ax_, ay_, bx_, by_, cx_, cy_
		if ok then
			ax_, ay_, bx_, by_, cx_, cy_ = px[a], py[a], px[b], py[b], px[c], py[c]
			ok = (bx_ - ax_) * (cy_ - ay_) - (cx_ - ax_) * (by_ - ay_) > 0
			if ok then
				ok = not ((ax_ < -hw and bx_ < -hw and cx_ < -hw) or (ax_ > hw and bx_ > hw and cx_ > hw) or (ay_ < -hh and by_ < -hh and cy_ < -hh) or (ay_ > hh and by_ > hh and cy_ > hh))
			end
			if not ok then culled = culled + 1 end
		end
		local tex = t.tex
		if ok then
			if ax_ ~= t.x1 or ay_ ~= t.y1 then SetVertexOffset(tex, 1, ax_ + 0.5, ay_ - 0.5); t.x1, t.y1 = ax_, ay_ end
			if bx_ ~= t.x2 or by_ ~= t.y2 then SetVertexOffset(tex, 2, bx_ + 0.5, by_ + 0.5); t.x2, t.y2 = bx_, by_ end
			if cx_ ~= t.x3 or cy_ ~= t.y3 then
				SetVertexOffset(tex, 3, cx_ - 0.5, cy_ - 0.5)
				SetVertexOffset(tex, 4, cx_ - 0.5, cy_ + 0.5)
				t.x3, t.y3 = cx_, cy_
			end
			-- the planet's shading at the triangle's middle, and the continent's fade
			local col = 1
			if shadeK > 0 and rp then
				col = 1 - Darkness(((ax_ + bx_ + cx_) / 3 - dcx) / rp, ((ay_ + by_ + cy_) / 3 - dcy) / rp) * shadeK
			end
			col = floor(col * 64 + 0.5) / 64
			if col ~= t.col or alpha ~= t.alpha then tex:SetVertexColor(col, col, col, alpha); t.col, t.alpha = col, alpha end
			t.depth = (pd[a] + pd[b] + pd[c]) / 3
			nVis = nVis + 1
			visible[nVis] = t
			if not t.shown then t.shown = true; tex:Show() end
			shown = shown + 1
		elseif t.shown then
			t.shown = false; tex:Hide()
		end
	end
	return shown, culled
end

-- far to near in BUCKETS draw sublevels (mountains at the edge of the planet cover what is behind them)
local function SortVisible()
	local dmin, dmax = math.huge, -math.huge
	for i = 1, nVis do local d = visible[i].depth; if d < dmin then dmin = d end; if d > dmax then dmax = d end end
	local scale = (BUCKETS - 0.001) / max(dmax - dmin, 1e-6)
	for i = 1, nVis do
		local t = visible[i]
		local bk = floor((dmax - t.depth) * scale)
		if bk ~= t.bucket then
			t.bucket = bk
			t.tex:SetDrawLayer(LAYERS[floor(bk / 16) + 1], bk % 16 - 8)
		end
		visible[i] = nil
	end
	nVis = 0
end

------------------------------------------------------------------------------------------------
-- Clouds and the Maelstrom: quads on the sphere
------------------------------------------------------------------------------------------------
local clouds = {}
ns.globeClouds = clouds -- (for the tests)
-- The clouds, placed once (the same every time: a fixed seed), as weather on a planet places them: storms
-- (spirals, turning the way their hemisphere's storms turn) in the middle latitudes, each with a front
-- trailing toward the equator; fields of cumulus (clusters and cloud streets) along the equator and in the
-- storm belts; veils of cirrus. Over land fewer and fainter; none on the Maelstrom (its own storm is there).
-- Latitude and longitude are the planet's (its north the sphere's +y, longitude 0 the point between the
-- continents).
local function MakeClouds()
	local seed = 20261019
	local function R()
		seed = (seed * 1103515245 + 12345) % 2147483648
		return seed / 2147483648
	end
	local function Add(lat, lon, kind, size, aspect, rot, alpha)
		local cl = cos(lat)
		local X, Y = PlaneOf(cl * sin(lon), sin(lat), cl * cos(lon), RADIUS)
		local over = false
		for _, e in pairs(layout) do
			if X > e.x0 + 800 and X < e.x1 - 800 and Y > e.y0 + 800 and Y < e.y1 - 800 then over = true end
		end
		local keep = R() -- (drawn always, so the sequence does not depend on the layout)
		if over and kind ~= 6 and keep > 0.5 then return end
		local dmx, dmy = X - MX, Y - MY
		if dmx * dmx + dmy * dmy < (0.8 * STORM_SIZE + 0.5 * size) ^ 2 then return end
		clouds[#clouds + 1] = { X = X, Y = Y, size = size, size2 = size * aspect, rot = rot, kind = kind, file = MEDIA .. "Cloud" .. kind,
			alpha = alpha * (over and 0.7 or 1), mirror = kind == 4 and lat < 0 }
	end
	for i = 1, 5 do
		local hemi = i % 2 == 0 and -1 or 1
		local lat, lon = hemi * rad(32 + 22 * R()), 2 * pi * R()
		Add(lat, lon, 4, 6500 + 3500 * R(), 1, 2 * pi * R(), 0.95)
		Add(lat - hemi * rad(9 + 5 * R()), lon - rad(10 + 8 * R()) / cos(lat), 5, 5500 + 2500 * R(), 2.2, -hemi * (0.5 + 0.4 * R()), 0.9)
	end
	for _ = 1, 70 do
		local belt, lat = R(), nil
		if belt < 0.45 then lat = rad((2 * R() - 1) * 14)
		elseif belt < 0.85 then lat = (R() < 0.5 and -1 or 1) * rad(35 + 25 * R())
		else lat = rad((2 * R() - 1) * 70) end
		local kind = 1 + floor(R() * 3)
		local rot = kind == 3 and rad(-20 + 40 * R()) or 2 * pi * R() -- (streets lie along the wind, east-west)
		Add(lat, 2 * pi * R(), kind, 2600 + 3200 * R(), 1, rot, 0.92)
	end
	for _ = 1, 18 do
		Add(rad((2 * R() - 1) * 60), 2 * pi * R(), 6, 4500 + 4000 * R(), 1.4, rad(-15 + 30 * R()), 0.8)
	end
end

-- the four corners of a rectangle of half sizes s (along its x) and s2 (along its y; s if not given), in
-- yards on the sphere, its x turned by rot from the planet's east toward its north, centred on a plane
-- point, at height h: screen positions in the order upper left, lower left, upper right, lower right of the
-- texture, or nil when it faces away or is off screen
local qx_, qy_ = {}, {}
local SIGNS = { { -1, 1 }, { -1, -1 }, { 1, 1 }, { 1, -1 } } -- (along t1, along t2): upper left, lower left, upper right, lower right
local function QuadOnSphere(X, Y, s, rot, h, s2)
	local vx, vy, vz
	s2 = s2 or s
	if G.flat then
		-- flat: a rectangle in the plane (t1 east and t2 north, turned by rot)
		local c, sn = cos(rot), sin(rot)
		for i = 1, 4 do
			local a, b = SIGNS[i][1] * s, SIGNS[i][2] * s2
			local sx, sy = Project(WorldOf(X + a * c - b * sn, Y + a * sn + b * c, h))
			if not sx then return nil end
			qx_[i], qy_[i] = sx, sy
		end
	else
		vx, vy, vz = Unit(X, Y, G.rt)
		-- the planet's east and north there (east = its axis x the point), turned by rot
		local ax_, ay_, az_ = vz, 0, -vx
		local l = sqrt(ax_ * ax_ + az_ * az_)
		if l < 1e-9 then ax_, ay_, az_, l = 1, 0, 0, 1 end
		ax_, ay_, az_ = ax_ / l, ay_ / l, az_ / l
		local bx_, by_, bz_ = vy * az_ - vz * ay_, vz * ax_ - vx * az_, vx * ay_ - vy * ax_
		local c, sn = cos(rot), sin(rot)
		local t1x, t1y, t1z = ax_ * c + bx_ * sn, ay_ * c + by_ * sn, az_ * c + bz_ * sn
		local t2x, t2y, t2z = -ax_ * sn + bx_ * c, -ay_ * sn + by_ * c, -az_ * sn + bz_ * c
		local k, k2 = s / G.rt, s2 / G.rt
		for i = 1, 4 do
			local a, b = SIGNS[i][1] * k, SIGNS[i][2] * k2
			local px, py, pz = vx + t1x * a + t2x * b, vy + t1y * a + t2y * b, vz + t1z * a + t2z * b
			local l2 = sqrt(px * px + py * py + pz * pz)
			local wx, wy, wz = WorldOfUnit(px / l2, py / l2, pz / l2, h)
			local sx, sy = Project(wx, wy, wz)
			if not sx then return nil end
			qx_[i], qy_[i] = sx, sy
		end
	end
	-- facing: upper left, lower left, lower right counter-clockwise on screen (y up)
	local area = (qx_[2] - qx_[1]) * (qy_[4] - qy_[1]) - (qx_[4] - qx_[1]) * (qy_[2] - qy_[1])
	if not (area > 0) then return nil end
	local w, hh = canvas:GetSize()
	w, hh = w / 2, hh / 2
	local x0, x1, y0, y1 = math.huge, -math.huge, math.huge, -math.huge
	for i = 1, 4 do x0, x1, y0, y1 = min(x0, qx_[i]), max(x1, qx_[i]), min(y0, qy_[i]), max(y1, qy_[i]) end
	if x1 < -w or x0 > w or y1 < -hh or y0 > hh then return nil end
	return true, vx, vy, vz
end

local function FacingCamera(vx, vy, vz)
	-- how much a point of the sphere faces the camera (1 straight at it, 0 at the planet's edge)
	if not vx then return 1 end
	local wx, wy, wz = WorldOfUnit(vx, vy, vz, 0)
	local nxw = ((vx * G.ex + vy * G.ey + vz * G.ez) / G.ax)
	local nyw = ((vx * G.nx + vy * G.ny + vz * G.nz) / G.ay)
	local nzw = (vx * G.ox + vy * G.oy + vz * G.oz)
	local tx, ty, tz = G.cx - wx, G.cy - wy, G.cz - wz
	local l = sqrt(tx * tx + ty * ty + tz * tz)
	return (nxw * tx + nyw * ty + nzw * tz) / l
end

-- the planet's light at a screen point (1 lit, less on the side away from the light), as the land has it
local function LightAt(x, y, shadeK)
	if not (shadeK > 0 and G.rp) then return 1 end
	return 1 - Darkness((x - G.dcx) / G.rp, (y - G.dcy) / G.rp) * shadeK
end
-- the clouds' shadows fall away from the light (from the upper left, a little toward you): on screen, this
-- many times the cloud's height (in pixels) toward the lower right
local SHADOW_X, SHADOW_Y = -LIGHT[1] / LIGHT[3], -LIGHT[2] / LIGHT[3]

local function DrawClouds(alpha)
	local shown = 0
	if #clouds == 0 then MakeClouds() end
	for _, c in ipairs(clouds) do
		local ok, vx, vy, vz
		if alpha > 0.01 then ok, vx, vy, vz = QuadOnSphere(c.X, c.Y, c.size, c.rot, CLOUD_H, c.size2) end
		if ok then
			if not c.tex then
				c.tex, c.sh = cloudPool.Get(), shadowPool.Get()
				c.tex:SetTexture(c.file); c.sh:SetTexture(c.file)
				-- southern storms turn the other way: their spiral mirrored
				if c.mirror then c.tex:SetTexCoord(1, 0, 0, 1); c.sh:SetTexCoord(1, 0, 0, 1) end
			end
			Corners(c.tex, qx_[1], qy_[1], qx_[2], qy_[2], qx_[3], qy_[3], qx_[4], qy_[4])
			local face = Smooth(FacingCamera(vx, vy, vz) / 0.35)
			local mx, my = (qx_[1] + qx_[4]) / 2, (qy_[1] + qy_[4]) / 2
			local light = LightAt(mx, my, alpha)
			local a = alpha * c.alpha * face
			c.tex:SetVertexColor(light, light, light, a)
			c.tex:Show()
			-- the shadow: the same shape on the surface below, toward the lower right, faint, none at night
			local ppy = sqrt((qx_[3] - qx_[1]) ^ 2 + (qy_[3] - qy_[1]) ^ 2) / (2 * c.size) -- pixels per yard there
			local ox, oy = SHADOW_X * CLOUD_H * ppy, SHADOW_Y * CLOUD_H * ppy
			Corners(c.sh, qx_[1] + ox, qy_[1] + oy, qx_[2] + ox, qy_[2] + oy, qx_[3] + ox, qy_[3] + oy, qx_[4] + ox, qy_[4] + oy)
			c.sh:SetVertexColor(0, 0, 0, a * 0.3 * light)
			c.sh:Show()
			shown = shown + 1
		elseif c.tex then
			c.tex:Hide(); c.sh:Hide()
		end
	end
	return shown
end

-- The Maelstrom: the whirlpool turning in the sea, the storm over it turning slower (so they seem apart),
-- and now and then a flash of lightning in the storm, each faded with the sky and lit as the planet is.
local maelAngle, stormAngle = 0, 0
local flash = { at = -10, X = 0, Y = 0, rot = 0, size = 0, next = 2, seed = 4242 }
local function FlashRandom()
	flash.seed = (flash.seed * 1103515245 + 12345) % 2147483648
	return flash.seed / 2147483648
end
-- the flash's brightness, seconds after it started: a bright stroke, a dip, a second stroke, fading
local function FlashLevel(u)
	if u < 0 then return 0 elseif u < 0.05 then return 1 elseif u < 0.10 then return 0.25 elseif u < 0.16 then return 0.9 end
	return max(0, 0.9 * (1 - (u - 0.16) / 0.2))
end
local function DrawMaelstrom(alpha)
	if alpha <= 0.01 or not QuadOnSphere(MX, MY, MAEL_SIZE, maelAngle, 0) then
		mael:Hide(); storm:Hide(); bolt:Hide()
		return false
	end
	Corners(mael, qx_[1], qy_[1], qx_[2], qy_[2], qx_[3], qy_[3], qx_[4], qy_[4])
	local light = LightAt((qx_[1] + qx_[4]) / 2, (qy_[1] + qy_[4]) / 2, alpha)
	mael:SetVertexColor(light, light, light, alpha * 0.95)
	mael:Show()
	if QuadOnSphere(MX, MY, STORM_SIZE, stormAngle, CLOUD_H * 1.5) then
		Corners(storm, qx_[1], qy_[1], qx_[2], qy_[2], qx_[3], qy_[3], qx_[4], qy_[4])
		storm:SetVertexColor(light, light, light, alpha * 0.9)
		storm:Show()
	else
		storm:Hide()
	end
	local level = FlashLevel(GetTime() - flash.at) * alpha
	if level > 0.01 and QuadOnSphere(flash.X, flash.Y, flash.size, flash.rot, CLOUD_H * 1.6) then
		Corners(bolt, qx_[1], qy_[1], qx_[2], qy_[2], qx_[3], qy_[3], qx_[4], qy_[4])
		bolt:SetVertexColor(1, 1, 1, level)
		bolt:Show()
	else
		bolt:Hide()
	end
	return true
end
-- the Maelstrom's clock: turns it, and starts a flash every 1.5 to 5.5 seconds somewhere in the storm
local function MaelstromStep(elapsed)
	maelAngle = (maelAngle + elapsed * MAEL_TURN) % (2 * pi)
	stormAngle = (stormAngle + elapsed * STORM_TURN) % (2 * pi)
	local now = GetTime()
	if now >= flash.next then
		local a, r = 2 * pi * FlashRandom(), STORM_SIZE * (0.3 + 0.45 * FlashRandom())
		flash.X, flash.Y = MX + cos(a) * r, MY + sin(a) * r
		flash.rot, flash.size = 2 * pi * FlashRandom(), MAEL_SIZE * (0.22 + 0.15 * FlashRandom())
		flash.at, flash.next = now, now + 1.5 + 4 * FlashRandom()
	end
end
ns.GlobeFlash = flash -- (for the tests)

------------------------------------------------------------------------------------------------
-- You: the arrow on the planet, as the 3D view draws it on the ground (same size and place)
------------------------------------------------------------------------------------------------
local function DrawArrow()
	local p = ns.player
	if not (p and p.on and layout[p.map]) then arrow:Hide() return false end
	local s = max(3, cam.dist * 0.05)
	local f = p.facing
	local fwx, fwy = -sin(f), cos(f)
	local rtx, rty = cos(f), sin(f)
	local e = layout[p.map]
	local h = (p.h + 0.4) * (1 - G.t)
	for i = 1, 4 do
		-- corners as the 3D view's arrow has them: tip side left and right, back left and right (no table per frame)
		local a, b = (i == 1 or i == 3) and 1 or -1, (i <= 2) and -1 or 1
		local X, Y = (p.x + (a * fwx + b * rtx) * s) * e.ax + e.bx, (p.y + (a * fwy + b * rty) * s) * e.ay + e.by
		local sx, sy = Project(WorldOf(X, Y, h))
		if not sx then arrow:Hide() return false end
		qx_[i], qy_[i] = sx, sy
	end
	local area = (qx_[2] - qx_[1]) * (qy_[4] - qy_[1]) - (qx_[4] - qx_[1]) * (qy_[2] - qy_[1])
	if not (area > 0) then arrow:Hide() return false end
	Corners(arrow, qx_[1], qy_[1], qx_[2], qy_[2], qx_[3], qy_[3], qx_[4], qy_[4])
	arrow:Show()
	return true
end

------------------------------------------------------------------------------------------------
-- The frame
------------------------------------------------------------------------------------------------
local active = false
local function Available() return layout[cam.map] ~= nil and ns.GlobeData ~= nil end
ns.GlobeOn = function() return active end
ns.ZoomMax = function() return Available() and GLOBE_MAX or nil end
ns.GLOBE = { FLAT_MAX = FLAT_MAX, HANDOVER = HANDOVER, ROUND = ROUND, GLOBE_MAX = GLOBE_MAX, RADIUS = RADIUS, SWAP_HI = SWAP_HI, SWAP_LO = SWAP_LO }

local function Enter()
	active = true
	for _, f in ipairs(ns.bucketFrames or {}) do f:Hide() end
	if ns.decal then ns.decal:GetParent():Hide() end
	if ns.scene then ns.scene:Hide() end
	if ns.questLayer then ns.questLayer:Hide() end
	if ns.addonLayer then ns.addonLayer:Hide() end
	for _, f in ipairs(ns.globeFrames) do f:Show() end
	GPS.Log("3D", "planet view on (%.0f yd)", cam.dist)
end
local function Leave()
	active = false
	for _, f in ipairs(ns.globeFrames) do f:Hide() end
	for _, f in ipairs(ns.bucketFrames or {}) do f:Show() end
	if ns.decal then ns.decal:GetParent():Show() end
	if ns.scene then ns.scene:Show() end
	if ns.questLayer then ns.questLayer:Show() end
	if ns.addonLayer then ns.addonLayer:Show() end
	GPS.Log("3D", "planet view off (%.0f yd)", cam.dist)
end
ns.GlobeLeave = function() if active then Leave() end end

-- the view's tilt straightens between FLAT_MAX and HANDOVER; your character and the markers fade out
local function Straighten()
	local s = Available() and Smooth((cam.dist - FLAT_MAX) / (HANDOVER - FLAT_MAX)) or 0
	if s > 0 then cam.vp = cam.pitch + ((ns.MAX_PITCH or 89.9) - cam.pitch) * s else cam.vp = nil end
	local a = 1 - s
	if ns.questLayer and ns.questLayer:GetAlpha() ~= a then ns.questLayer:SetAlpha(a) end
	if ns.addonLayer and ns.addonLayer:GetAlpha() ~= a then ns.addonLayer:SetAlpha(a) end
	if ns.scene and ns.scene:GetAlpha() ~= a then ns.scene:SetAlpha(a) end
	return s
end

local function Draw()
	local st = G.stats
	local d = cam.dist
	local t = Curvature(d)
	SetSphere(t)
	SetCamera()
	local F = G.F
	-- what the sea, the land and the sky look like at this distance
	local tilePx = TILE * F / d
	-- the overview images (as the ground had them, at full strength at the hand-over) fade out over the
	-- planet's own pages as tiles shrink on screen; then the sea turns blue and the sky fades in
	local cs = CurveStart()
	local atlasA = max(Smooth((tilePx - SWAP_LO) / (SWAP_HI - SWAP_LO)), 1 - Smooth((d - HANDOVER) / (0.25 * HANDOVER)))
	local a0 = max(HANDOVER, 0.75 * cs)
	atlasA = min(atlasA, 1 - Smooth((d - a0) / max(cs - a0, 1))) -- gone by the time the ground bends (whole at the hand-over)
	local pagesA = atlasA < 0.999 -- (under a fully drawn overview layer the pages would not show)
	local k = Smooth((d - cs) / (0.6 * cs)) -- blue sea, shading, glow, clouds, Maelstrom
	-- the sea: a disc of the planet's size, or the whole view while the planet fills it
	local oc1, oc2, oc3 = SEA[1] + (BLUE[1] - SEA[1]) * k, SEA[2] + (BLUE[2] - SEA[2]) * k, SEA[3] + (BLUE[3] - SEA[3]) * k
	local dcx, dcy, rp
	if G.flat then
		bg:SetColorTexture(oc1, oc2, oc3, 1)
		disc:Hide(); shade:Hide(); glow:Hide()
	else
		local wx, wy, wz = cam.x, cam.y, -G.rt -- the sphere's centre
		local sx, sy = Project(wx, wy, wz)
		local dx, dy, dz = (wx - G.cx) * G.ax, (wy - G.cy) * G.ay, wz - G.cz
		local dc = sqrt(dx * dx + dy * dy + dz * dz)
		local q = G.rt / dc
		if sx and q < 1 then
			rp = F * q / sqrt(1 - q * q) -- tan(asin q)
			dcx, dcy = sx, sy
		end
		if rp and rp < 1e7 then
			bg:SetColorTexture(0, 0, 0, 1)
			disc:SetVertexColor(oc1, oc2, oc3, 1)
			PlaceSquare(disc, dcx, dcy, rp)
			if k > 0.01 then
				shade:SetVertexColor(1, 1, 1, k)
				PlaceSquare(shade, dcx, dcy, rp)
				glow:SetVertexColor(1, 1, 1, k)
				PlaceSquare(glow, dcx, dcy, rp / 0.80)
			else
				shade:Hide(); glow:Hide()
			end
		else
			bg:SetColorTexture(oc1, oc2, oc3, 1)
			disc:Hide(); shade:Hide(); glow:Hide()
			rp = nil
		end
	end
	G.dcx, G.dcy, G.rp = dcx, dcy, rp
	-- the land: per continent, a block size by how big a tile is on screen and how round the planet is
	local n = 1
	if atlasA <= 0 and t >= 0.15 then
		while n < 8 and 2 * n * tilePx <= LAND_PX and 2 * n * TILE <= 0.2 * (G.rt or math.huge) do n = n * 2 end
	end
	wipe(frameLevels)
	local fadeOthers = Smooth((d - HANDOVER) / (0.5 * HANDOVER))
	local shown, culled = 0, 0
	for _, m in ipairs(mapList) do
		local alpha = m == cam.map and 1 or fadeOthers
		if alpha > 0.005 and pagesA then
			local lv = Level(m, n, false)
			frameLevels[lv] = true
			Activate(lv)
			local s1, c1 = DrawLand(lv, alpha, k, dcx, dcy, rp)
			shown, culled = shown + s1, culled + c1
		end
		if alpha * atlasA > 0.005 then
			local lv = Level(m, 1, true)
			frameLevels[lv] = true
			Activate(lv)
			local s1, c1 = DrawLand(lv, alpha * atlasA, k, dcx, dcy, rp)
			shown, culled = shown + s1, culled + c1
		end
	end
	-- levels not drawn this frame give their textures back
	for _, lv in pairs(levels) do
		if lv.active and not frameLevels[lv] then Deactivate(lv) end
	end
	SortVisible()
	local nClouds = DrawClouds(k)
	local maelShown = DrawMaelstrom(k)
	local arrowShown = DrawArrow()
	st.t, st.rt, st.n, st.pages, st.atlas, st.k, st.rp, st.shown, st.culled, st.clouds, st.mael, st.arrow, st.tilePx =
		t, G.rt, n, pagesA, atlasA, k, rp or 0, shown, culled, nClouds, maelShown, arrowShown, tilePx
end

function ns.GlobeRender()
	Straighten()
	if not Available() or cam.dist <= HANDOVER then
		if active then Leave() end
		return false
	end
	if not active then Enter() end
	Draw()
	return true
end

-- Only you moved: the arrow (with the last frame's sphere and camera)
function ns.GlobeMarker()
	if not active then return false end
	DrawArrow()
	return true
end

------------------------------------------------------------------------------------------------
-- Mouse: drag turns the planet (the point grabbed stays under the cursor), the wheel zooms toward the
-- cursor, right-drag turns the view, double-click flies down to the spot.
------------------------------------------------------------------------------------------------
-- After the point looked at moved in the plane: the continent nearest it becomes the view's map.
local function SetFocus(X, Y)
	local m = NearestMap(X, Y)
	if m ~= cam.map then
		GPS.Log("3D", "planet: view map %s -> %s", tostring(cam.map), tostring(m))
		cam.map = m
	end
	cam.x, cam.y = FromPlane(cam.map, X, Y)
end
ns.GlobeSetFocus = SetFocus

-- On the planet: the view's map becomes another continent, the point looked at staying where it is (true)
function ns.GlobeSwitchMap(m)
	if not (active and layout[m] and layout[cam.map]) then return false end
	local X, Y = ToPlane(cam.map, cam.x, cam.y)
	cam.map = m
	cam.x, cam.y = FromPlane(m, X, Y)
	return true
end

-- The planet's north: toward its pole above the world map's north (the sphere's +y; the plane's north and
-- this agree at the point between the continents and along its meridian, and the plane's whirls round the
-- point opposite, on the far side, where this one is steady). NorthOffset: this north's angle from the
-- plane's at the point looked at, degrees from north toward east (0 on flat ground; the compass shows this
-- north on the planet, and dragging keeps the way the view faces measured from it).
local function NorthOffset()
	if G.flat then return 0 end
	local oy = G.oy
	local gx, gy, gz = -oy * G.ox, 1 - oy * oy, -oy * G.oz
	return atan2(gx * G.ex + gy * G.ey + gz * G.ez, gx * G.nx + gy * G.ny + gz * G.nz) / pi * 180
end
function ns.GlobeNorth()
	if not active then return 0 end
	return NorthOffset()
end

-- Vector a turned about the unit axis k by the angle whose cosine and sine are cs and sn (Rodrigues).
local function Turn(kx, ky, kz, cs, sn, ax, ay, az)
	local kd = kx * ax + ky * ay + kz * az
	local cx_, cy_, cz_ = ky * az - kz * ay, kz * ax - kx * az, kx * ay - ky * ax
	return ax * cs + cx_ * sn + kx * kd * (1 - cs), ay * cs + cy_ * sn + ky * kd * (1 - cs), az * cs + cz_ * sn + kz * kd * (1 - cs)
end

-- Moves the point looked at so that plane point (X, Y) is under screen point (px, py).
-- Flat ground: the point looked at moves in the plane, the view's turn (yaw) kept.
-- Bent ground: the view (the point looked at and the way it faces) turns round the sphere's centre by the
-- rotation that takes the point now under the cursor to the one held, so the planet turns under the cursor
-- in any direction and all the way round (in the plane the far side's middle is infinitely far, which is
-- where a drag in the plane got stuck until 2026-10-19). The way the view faces, measured from the planet's
-- north, is kept (the continents come back upright however often the planet is spun), except near its
-- poles, where that north whirls: there the view keeps the rotation's own (a free turn). The point looked
-- at is kept within 70 degrees of the equator by a drag (it stops there, as on a globe on its stand).
local POLE_LAT = math.sin(rad(70))
local function Hold(X, Y, px, py)
	local north -- the way the view faces, from the planet's north, before the move
	for _ = 1, 12 do
		SetSphere(G.t); SetCamera()
		if G.flat then
			local hx, hy = PickPlane(px, py)
			if not hx then return false end
			local mx, my = X - hx, Y - hy
			if abs(mx) + abs(my) < 0.05 then return true end
			SetFocus(G.XF + mx, G.YF + my)
		else
			local wx, wy, wz = PickUnit(px, py)
			if not wx then return false end
			local vx, vy, vz = Unit(X, Y, G.rt)
			-- the rotation taking w to v: axis w x v, angle between them (Rodrigues)
			local kx, ky, kz = wy * vz - wz * vy, wz * vx - wx * vz, wx * vy - wy * vx
			local sn, cs = sqrt(kx * kx + ky * ky + kz * kz), wx * vx + wy * vy + wz * vz
			if sn < 2e-7 and cs > 0 then return true end -- within about a yard on the round planet
			if sn < 1e-12 then return false end
			kx, ky, kz = kx / sn, ky / sn, kz / sn
			-- at most 0.2 radians a step (the rest in the next steps), so a fast drag cannot jump over a pole
			local ang = cs < 0.98 and 0.2 or atan2(sn, cs)
			-- not past 70 degrees from the equator (nor further than it already is): the planet stops there
			local lim, clamped = max(POLE_LAT, abs(G.oy))
			local ox, oy, oz = Turn(kx, ky, kz, cos(ang), sin(ang), G.ox, G.oy, G.oz)
			if abs(oy) > lim then
				local lo, hi = 0, ang
				for _ = 1, 10 do
					local mid = (lo + hi) / 2
					local _, my_ = Turn(kx, ky, kz, cos(mid), sin(mid), G.ox, G.oy, G.oz)
					if abs(my_) > lim then hi = mid else lo = mid end
				end
				ang, clamped = lo, true
				ox, oy, oz = Turn(kx, ky, kz, cos(ang), sin(ang), G.ox, G.oy, G.oz)
			end
			local l = sqrt(ox * ox + oy * oy + oz * oz)
			ox, oy, oz = ox / l, oy / l, oz / l
			-- the way the view faces there (along the ground), turned the same
			local yw = rad(cam.yaw)
			local hx_, hy_, hz_ = Turn(kx, ky, kz, cos(ang), sin(ang), sin(yw) * G.ex + cos(yw) * G.nx, sin(yw) * G.ey + cos(yw) * G.ny, sin(yw) * G.ez + cos(yw) * G.nz)
			north = north or cam.yaw - NorthOffset()
			SetFocus(PlaneOf(ox, oy, oz, G.rt))
			SetSphere(G.t)
			-- the free turn's yaw, and the yaw keeping the way the view faces from the planet's north: the
			-- second, except near the poles
			local free = atan2(hx_ * G.ex + hy_ * G.ey + hz_ * G.ez, hx_ * G.nx + hy_ * G.ny + hz_ * G.nz) / pi * 180
			local kept = north + NorthOffset()
			local w = 1 - Smooth((abs(G.oy) - 0.95) / 0.045) -- (latitude 72 to 84 degrees: only reached by zooming)
			cam.yaw = (free + w * ((kept - free + 540) % 360 - 180)) % 360
			if w < 1 then north = cam.yaw - NorthOffset() end
			if clamped then return true end
		end
	end
	return true
end
ns.GlobeHold = Hold

-- zooming in close to the hand-over, the point looked at is drawn onto the view's map (the 3D view's ground
-- ends there), so nothing jumps when the ground takes over
local function PullOntoMap(d)
	local e = layout[cam.map]
	if d >= 1.6 * HANDOVER then return end
	local f = 1 - Smooth((d - HANDOVER) / (0.6 * HANDOVER))
	local x0, x1 = e.tx0 * TILE, (e.tx1 + 1) * TILE
	local y0, y1 = -(e.ty1 + 1) * TILE, -e.ty0 * TILE
	local cx_, cy_ = min(x1, max(x0, cam.x)), min(y1, max(y0, cam.y))
	cam.x, cam.y = cam.x + (cx_ - cam.x) * f, cam.y + (cy_ - cam.y) * f
end

function ns.GlobeZoom(factor, px, py)
	if not (active and Available()) then return false end
	local d = cam.dist
	local nd = max(15, min(GLOBE_MAX, d * factor))
	if nd == d then return true end
	local following = ns.IsFollowing and ns.IsFollowing()
	local X, Y
	if px and not following then
		SetSphere(G.t); SetCamera()
		X, Y = PickPlane(px, py)
	end
	cam.dist = nd
	G.t = Curvature(nd)
	if X then Hold(X, Y, px, py) end
	if not following then PullOntoMap(nd) end
	ns.Render()
	return true
end

local gd -- a press on the planet: { button, startX, startY, lastX, lastY, moved, X, Y }
local lastClick = { time = 0, x = 0, y = 0 }
function ns.GlobeMouseDown(button)
	if not active then return false end
	local px, py = ns.CursorInCanvas()
	gd = { button = button, startX = px, startY = py, lastX = px, lastY = py, moved = false }
	if button == "LeftButton" then
		SetSphere(G.t); SetCamera()
		gd.X, gd.Y = PickPlane(px, py)
	end
	return true
end

local function FlyDown(X, Y)
	local m = NearestMap(X, Y)
	if m ~= cam.map then
		-- the point looked at, said on the other continent's yards: the flight starts where the view is
		local fx_, fy_ = ToPlane(cam.map, cam.x, cam.y)
		cam.map = m
		cam.x, cam.y = FromPlane(m, fx_, fy_)
	end
	local tx, ty = FromPlane(m, X, Y)
	if ns.SetCamMode then ns.SetCamMode("free") end
	local target = max(6000, min(cam.dist * 0.25, HANDOVER * 0.6))
	ns.FlyTo({ x = tx, y = ty, dist = target }, 1.4)
	GPS.Log("3D", "planet: fly down to %s at %.1f, %.1f", tostring(m), tx / TILE, -ty / TILE)
end
ns.GlobeFlyDown = FlyDown

function ns.GlobeMouseUp(button)
	if not gd then return false end
	local d = gd
	gd = nil
	if d.button == "LeftButton" and not d.moved then
		local now = GetTime()
		if now - lastClick.time < 0.35 and abs(d.startX - lastClick.x) < 4 and abs(d.startY - lastClick.y) < 4 then
			lastClick.time = 0
			SetSphere(G.t); SetCamera()
			local X, Y = PickPlane(d.startX, d.startY)
			if X then FlyDown(X, Y) end
		else
			lastClick.time, lastClick.x, lastClick.y = now, d.startX, d.startY
		end
	end
	return true
end

local function DragStep()
	if not gd then return false end
	if not active then gd = nil return false end
	local px, py = ns.CursorInCanvas()
	if not gd.moved and abs(px - gd.startX) < 4 and abs(py - gd.startY) < 4 then return false end
	gd.moved = true
	local dx, dy = px - gd.lastX, py - gd.lastY
	gd.lastX, gd.lastY = px, py
	if dx == 0 and dy == 0 then return false end
	if gd.button == "LeftButton" then
		if ns.IsFollowing and ns.IsFollowing() then ns.SetCamMode("free") end
		if gd.X then Hold(gd.X, gd.Y, px, py) end
	else
		cam.yaw = (cam.yaw - dx * 0.4) % 360
		if not (ns.IsTopDown and ns.IsTopDown()) then cam.pitch = max(45, min(ns.MAX_PITCH or 89.9, cam.pitch - dy * 0.3)) end
	end
	return true
end
ns.GlobeDragStep = DragStep

-- A flight on the planet (GPS3D's FlyTo): the point looked at travels along the great circle from where it
-- is to the target (as the sphere is when the flight starts), not along the plane's straight line, which
-- from the far side would stay there and then rush across. Returns the step (e from 0 to 1), or nil.
function ns.GlobeFlyPath(start, target)
	if not (active and start.x and target.x and not G.flat and G.t > 0.02) then return nil end
	local m, rt = cam.map, G.rt
	if not layout[m] then return nil end
	local sX, sY = ToPlane(m, start.x, start.y)
	local eX, eY = ToPlane(m, target.x, target.y)
	local ax, ay, az = Unit(sX, sY, rt)
	local bx, by, bz = Unit(eX, eY, rt)
	local c = max(-1, min(1, ax * bx + ay * by + az * bz))
	local om = math.acos(c)
	local so = sin(om)
	if om < 1e-6 or so < 1e-3 then return nil end -- the same point, or opposite points (the plane's line then)
	return function(e)
		local a, b = sin((1 - e) * om) / so, sin(e * om) / so
		cam.map = m
		cam.x, cam.y = FromPlane(m, PlaneOf(a * ax + b * bx, a * ay + b * by, a * az + b * bz, rt))
	end
end

-- < > on the planet: turn it to the next continent (keeping the distance)
function ns.GlobeCycle(step)
	if not active or #mapList < 2 then return false end
	local index = 1
	for i, m in ipairs(mapList) do if m == cam.map then index = i end end
	local m = mapList[(index - 1 + step) % #mapList + 1]
	local e = layout[m]
	-- the point looked at, said in the other continent's yards (the turn starts where the view is)
	local fx_, fy_ = ToPlane(cam.map, cam.x, cam.y)
	cam.map = m
	cam.x, cam.y = FromPlane(m, fx_, fy_)
	if ns.SetCamMode then ns.SetCamMode("free") end
	local tx, ty = FromPlane(m, (e.x0 + e.x1) / 2, (e.y0 + e.y1) / 2)
	ns.FlyTo({ x = tx, y = ty }, 1.2)
	GPS.Log("3D", "planet: turned to %s", e.name)
	return true
end

-- Drags, and the Maelstrom turning, each frame while the window is open
local driver = CreateFrame("Frame", nil, ns.frame)
driver:SetScript("OnUpdate", function(_, elapsed)
	if not warmed and not active and cam.dist > 6000 and Available() then WarmUp(400) end
	local dirty = DragStep()
	if active then
		MaelstromStep(elapsed)
		if not dirty and mael:IsShown() then DrawMaelstrom(G.stats.k or 0) end
	end
	if dirty then ns.Render() end
end)

------------------------------------------------------------------------------------------------
-- Self-test (/gps3d test) and the debug log
------------------------------------------------------------------------------------------------
function ns.GlobeState()
	local st = G.stats
	if not active then return ("planet: off (%s layout)"):format(layoutInfo.source) end
	return ("planet: on, curvature %.2f, radius %.0f yd, %s, blocks of %d tiles, %d land triangles shown, %d clouds, %s layout"):format(
		st.t or 0, st.rt or 0, (st.atlas or 0) >= 1 and "overview images" or ((st.atlas or 0) > 0 and "overview images fading into the planet's pages" or "the planet's pages"), st.n or 1, st.shown or 0, st.clouds or 0, layoutInfo.source)
end

function ns.GlobeSelfTest(Report)
	-- the layout: the game's world map against the fallback numbers
	local game, why = GameLayout()
	if game then
		local parts = {}
		for m, d in pairs(game) do
			local f = FALLBACK[m]
			parts[#parts + 1] = ("%s (uiMap %s): %.0f x %.0f yd, edges %.0f, %.0f; classic numbers %.0f x %.0f, %.0f, %.0f"):format(
				layout[m] and layout[m].name or m, tostring(layoutInfo["ui" .. m]), d[1], d[2], d[3], d[4], f[1], f[2], f[3], f[4])
		end
		Report("planet: world map %s from the game: %s; using the %s layout", tostring(layoutInfo.world), table.concat(parts, "; "), layoutInfo.source)
	else
		Report("planet: the game's world map gives no layout (%s): using the classic numbers", tostring(why))
	end
	-- a planet frame: time and what was drawn
	if not Available() then Report("planet: not on a continent here (map %s): no planet view", tostring(cam.map)) return end
	local saved = { cam.dist, cam.x, cam.y, cam.map }
	cam.dist = 60000
	local t0 = debugprofilestop()
	for _ = 1, 10 do cam.yaw = cam.yaw + 1; ns.Render() end
	local ms = (debugprofilestop() - t0) / 10
	cam.yaw = cam.yaw - 10
	local st = G.stats
	Report("planet: %.1f ms a frame at 60,000 yd; %d land triangles shown, %d clouds, Maelstrom %s, radius %.0f yd", ms, st.shown or 0, st.clouds or 0, st.mael and "shown" or "hidden", RADIUS)
	cam.dist, cam.x, cam.y, cam.map = saved[1], saved[2], saved[3], saved[4]
	ns.Render()
	C_Timer.After(2.5, function()
		local files, loaded = 0, 0
		for _, name in ipairs({ "Disc", "Shade", "Glow", "Cloud1", "Cloud6", "Maelstrom", "MaelstromStorm", "MaelstromBolt" }) do
			files = files + 1
			local probe = oceanFrame:CreateTexture(nil, "BACKGROUND")
			probe:SetTexture(MEDIA .. name)
			if probe.IsObjectLoaded and probe:IsObjectLoaded() then loaded = loaded + 1 end
			probe:Hide()
		end
		local pages = 0
		for _, m in ipairs(mapList) do
			local d = ns.GlobeData and ns.GlobeData.maps[m]
			for _, p in ipairs(d and d.pages or {}) do
				files = files + 1
				local probe = oceanFrame:CreateTexture(nil, "BACKGROUND")
				probe:SetTexture(MEDIA .. "Land_" .. m .. "_" .. p)
				if probe.IsObjectLoaded and probe:IsObjectLoaded() then pages = pages + 1; loaded = loaded + 1 end
				probe:Hide()
			end
		end
		Report("planet: %d of %d images (Globe\\*.tga) report loaded (%d land pages)", loaded, files, pages)
	end)
end
