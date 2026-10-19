-- Where the continents are on Blizzard's world map of Azeroth, for the 2D map (both continents side by side
-- when zoomed out) and GPS3D's planet view (Globe.lua), through GPS_API.WorldLayout.
--
-- The plane: Blizzard's world map in yards, X east and Y north (u * SW, -v * SH, u and v the world map's
-- 0..1 coordinates). Each continent's yards (x = gx * TILE east, y = -gy * TILE north on its ADT grid)
-- reach it by a scale (within 0.3 % of 1) and an offset: X = x * ax + bx, Y = y * ay + by. The numbers come
-- from the game's world map (C_Map: each continent's rectangle on it and the world positions of its
-- corners) or, where the game does not give them, from FALLBACK (the classic world map's numbers, as
-- HereBeDragons-2.0 ships them for classic). Moved here from Globe.lua on 2026-10-19 (the 2D map uses it).
local addonName, ns = ...
local TILE = 1600 / 3
local min, max = math.min, math.max

-- per continent: W, H = yards across the world map (east-west, north-south) in that continent's own yards;
-- L, T = the world map's left and top edges as world Y (west) and world X (north). u = (L - worldY) / W,
-- v = (T - worldX) / H. Classic world map numbers (HereBeDragons-2.0, its classic branch).
local FALLBACK = {
	[0] = { 44688.53, 29795.11, 32601.04, 9894.93 },  -- Eastern Kingdoms
	[1] = { 44878.66, 29916.10, 8723.96, 14824.53 },  -- Kalimdor
}
local layout = {}     -- map -> { ax, bx, ay, by, x0, y0, x1, y1 (land box in the plane), tx0, ty0, tx1, ty1 (in tiles), name, data }
local info = { source = "none" }

local function Build(data, source)
	wipe(layout)
	local sw, sh, n = 0, 0, 0
	for _, d in pairs(data) do sw, sh, n = sw + d[1], sh + d[2], n + 1 end
	if n == 0 then info.source = "none" return end
	sw, sh = sw / n, sh / n
	for m, d in pairs(data) do
		local ax, ay = sw / d[1], sh / d[2]
		local e = { ax = ax, bx = (d[3] - 32 * TILE) * ax, ay = ay, by = (32 * TILE - d[4]) * ay, data = d }
		local mt = ns.Maps and ns.Maps[m]
		local gx0, gy0, gx1, gy1 = 0, 0, 63, 63
		if mt then gx0, gy0, gx1, gy1 = mt.fitMinX or mt.minX, mt.fitMinY or mt.minY, mt.fitMaxX or mt.maxX, mt.fitMaxY or mt.maxY end
		e.name = mt and mt.name or ("Map " .. m)
		e.x0, e.x1 = gx0 * TILE * ax + e.bx, (gx1 + 1) * TILE * ax + e.bx
		e.y0, e.y1 = -(gy1 + 1) * TILE * ay + e.by, -gy0 * TILE * ay + e.by
		e.tx0, e.ty0, e.tx1, e.ty1 = gx0, gy0, gx1, gy1
		layout[m] = e
	end
	info.source = source
end

-- The same numbers from the game's own world map: each continent's rectangle on it (GetMapRectOnMap) and
-- the world positions of its corners (GetWorldPosFromMapPos). nil and a reason where the game cannot say.
local function ContinentUiMaps(instance)
	local m = ns.Maps and ns.Maps[instance]
	if not (m and C_Map and C_Map.GetMapPosFromWorldPos and C_Map.GetMapInfo and CreateVector2D) then return nil, "no C_Map" end
	local CONTINENT = Enum and Enum.UIMapType and Enum.UIMapType.Continent or 2
	local WORLD = Enum and Enum.UIMapType and Enum.UIMapType.World or 1
	local gx0, gy0, gx1, gy1 = m.fitMinX or m.minX, m.fitMinY or m.minY, m.fitMaxX or m.maxX, m.fitMaxY or m.maxY
	for _, f in ipairs({ { 0.5, 0.5 }, { 0.35, 0.35 }, { 0.65, 0.65 }, { 0.35, 0.65 }, { 0.65, 0.35 }, { 0.5, 0.3 }, { 0.5, 0.7 } }) do
		local gx, gy = gx0 + (gx1 + 1 - gx0) * f[1], gy0 + (gy1 + 1 - gy0) * f[2]
		local ok, ui = pcall(C_Map.GetMapPosFromWorldPos, instance, CreateVector2D((32 - gy) * TILE, (32 - gx) * TILE))
		local mi = ok and ui and C_Map.GetMapInfo(ui)
		local guard = 0
		while mi and guard < 10 do
			guard = guard + 1
			if mi.mapType == CONTINENT then
				local parent = mi.parentMapID and mi.parentMapID > 0 and C_Map.GetMapInfo(mi.parentMapID)
				if parent and parent.mapType == WORLD then return mi.mapID, parent.mapID end
				return nil, "continent " .. tostring(mi.mapID) .. " has no world map above it"
			end
			mi = mi.parentMapID and mi.parentMapID > 0 and C_Map.GetMapInfo(mi.parentMapID)
		end
	end
	return nil, "no continent map found on map " .. tostring(instance)
end

local function GameLayout()
	if not (C_Map and C_Map.GetMapRectOnMap and C_Map.GetWorldPosFromMapPos and CreateVector2D) then return nil, "C_Map.GetMapRectOnMap missing" end
	local out, world = {}, nil
	for m in pairs(FALLBACK) do
		local cont, w = ContinentUiMaps(m)
		if not cont then return nil, w end
		if world and w ~= world then return nil, "the continents are on different world maps" end
		world = w
		local ok, left, right, top, bottom = pcall(C_Map.GetMapRectOnMap, cont, world)
		if not (ok and left and right and top and bottom) or right - left <= 0 or bottom - top <= 0 then return nil, "no rectangle for continent " .. cont end
		local _, p0 = C_Map.GetWorldPosFromMapPos(cont, CreateVector2D(0, 0))
		local _, p1 = C_Map.GetWorldPosFromMapPos(cont, CreateVector2D(1, 1))
		if not (p0 and p1) then return nil, "no world corners for continent " .. cont end
		local xa, ya = p0:GetXY() -- world X (north), world Y (west) of the map's top left
		local xb, yb = p1:GetXY()
		local U = GPS_API.Usable
		if not (U(xa) and U(ya) and U(xb) and U(yb)) then return nil, "world corners hidden from addons" end
		local W, H = (ya - yb) / (right - left), (xa - xb) / (bottom - top)
		local d = { W, H, ya + left * W, xa + top * H }
		if not (W > 1000 and H > 1000 and W / H > 1.2 and W / H < 1.8) then return nil, ("continent %d: implausible size %.0f x %.0f"):format(cont, W, H) end
		out[m] = d
		info["ui" .. m] = cont
	end
	info.world = world
	return out
end

local function Choose()
	local data, why = GameLayout()
	if data then
		-- the continents must not overlap
		Build(data, "game")
		local a, b = layout[0], layout[1]
		if a and b and a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1 then
			why = "the game's world map puts the continents over each other"
			data = nil
		end
	end
	if not data then
		Build(FALLBACK, "fallback")
		info.why = why
	else
		info.why = nil
	end
	if ns.Log then ns.Log("MAP", "world layout: %s%s", info.source, info.why and (" (" .. info.why .. ")") or "") end
end
Choose()

-- A grid point of map `from` said in map `to`'s grid (both on the world map), or nil.
local function GridOn(from, gx, gy, to)
	local a, b = layout[from], layout[to]
	if not (a and b) then return nil end
	local X, Y = gx * TILE * a.ax + a.bx, -gy * TILE * a.ay + a.by
	return (X - b.bx) / (b.ax * TILE), -(Y - b.by) / (b.ay * TILE)
end
-- The continent on the world map nearest a grid point of map m (m itself inside its land box).
local function NearestTo(m, gx, gy)
	local a = layout[m]
	if not a then return m end
	local X, Y = gx * TILE * a.ax + a.bx, -gy * TILE * a.ay + a.by
	local best, bd = m, nil
	for id, e in pairs(layout) do
		local dx = X < e.x0 and e.x0 - X or (X > e.x1 and X - e.x1 or 0)
		local dy = Y < e.y0 and e.y0 - Y or (Y > e.y1 and Y - e.y1 or 0)
		local d = dx * dx + dy * dy
		if not bd or d < bd or (d == bd and id == m) then best, bd = id, d end
	end
	return best
end

ns.WorldLayout, ns.WorldLayoutInfo, ns.ChooseWorldLayout, ns.WorldGridOn, ns.WorldNearest = layout, info, Choose, GridOn, NearestTo
GPS_API.WorldLayout, GPS_API.WorldLayoutInfo, GPS_API.ChooseWorldLayout, GPS_API.WorldFallback = layout, info, Choose, FALLBACK
GPS_API.WorldGridOn, GPS_API.WorldNearest, GPS_API.WorldGameLayout = GridOn, NearestTo, GameLayout
