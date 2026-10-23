-- Proof of concept (branch poc-models, 2026-10-22; not for the shipped addon): simplified 3D building models
-- made offline from the game's own models (scripts in the session's scratchpad: export with MapExplorer's reader,
-- hidden parts removed, MeshLab's quadric simplification), drawn by GPS3D's own triangle path (RenderWorld's
-- projection, painter's buckets, back-face culling) through the ns.ExtraMeshes hook.
-- /gps3d poc <name> <triangles> [flat|roof]  (roof: faces looking up show the minimap image, the rest flat colours)
-- /gps3d poc off
local _, ns = ...
local P = { mesh = nil, name = nil, size = nil, mode = "flat" }
ns.poc = P
local TILE = 1600 / 3
local function Clear()
	local m = P.mesh
	if m then for _, t in ipairs(m.tris) do t.tex:Hide(); t.shown = false; t.tex.file = nil; ns.ReleaseTex(t.tex) end end
	P.mesh = nil
end
local function Build(name, size, mode)
	Clear()
	local d = ns.PocData and ns.PocData[name] and ns.PocData[name][size == 0 and "tex" or size]
	if not d then return false end
	local vx, vy, vh = {}, {}, {}
	local v = d.v
	for k = 1, #v / 3 do vx[k], vy[k], vh[k] = v[k * 3 - 2], v[k * 3 - 1], v[k * 3] end
	local mesh = { detail = true, poc = true, map = d.map, vx = vx, vy = vy, vh = vh, px = {}, py = {}, pd = {}, tris = {}, nv = #vx }
	local t3, c = d.t, d.c
	local S = ns.SUN
	for k = 1, #t3 / 3 do
		local a, b, cc = t3[k * 3 - 2], t3[k * 3 - 1], t3[k * 3]
		local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
		local ex2, eh2, ez2 = vx[cc] - vx[a], vh[cc] - vh[a], -(vy[cc] - vy[a])
		local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
		local l = math.sqrt(nx * nx + nh * nh + nz * nz); if l > 0 then nx, nh, nz = nx / l, nh / l, nz / l end
		local t = { a = a, b = b, c = cc, tex = ns.AcquireTex(), bucket = -1, frame = 1, shown = false, mesh = mesh }
		local file = mode == "roof" and nh > 0.5 and ns.MinimapFile(d.map, math.floor((vx[a] + vx[b] + vx[cc]) / 3 / TILE), math.floor(-(vy[a] + vy[b] + vy[cc]) / 3 / TILE))
		if d.uv and (mode == "grey" or mode == "diag") then
			local shade = 0.45 + 0.55 * math.abs(nx * S[1] + nh * S[2] + nz * S[3])
			if mode == "diag" then ns.SetTriColour(t, shade, 0, shade) else ns.SetTriColour(t, shade, shade, shade) end
		elseif d.uv then -- the game's own texture by file ID, repeating, with the model's UVs
			local u = d.uv; local o = (k - 1) * 6
			local tex = t.tex
			if tex.file ~= d.f[k] then tex:SetTexture(d.f[k], "REPEAT", "REPEAT"); tex.file = d.f[k] end
			tex:SetTexCoord(u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6], u[o + 5], u[o + 6])
			t.u1, t.v1, t.u2, t.v2, t.u3, t.v3 = u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6]
			local shade = 0.55 + 0.45 * math.abs(nx * S[1] + nh * S[2] + nz * S[3])
			tex:SetVertexColor(shade, shade, shade); tex.r, tex.g, tex.b = shade, shade, shade
		elseif file then
			local tx, ty = math.floor((vx[a] + vx[b] + vx[cc]) / 3 / TILE), math.floor(-(vy[a] + vy[b] + vy[cc]) / 3 / TILE)
			local function uv(i) return (vx[i] - tx * TILE) / TILE, (-vy[i] - ty * TILE) / TILE end
			local ua, va = uv(a); local ub, vb = uv(b); local uc, vc = uv(cc)
			ns.SetTriTexture(t, file, ua, va, ub, vb, uc, vc)
		else
			local shade = 0.45 + 0.55 * math.abs(nx * S[1] + nh * S[2] + nz * S[3])
			ns.SetTriColour(t, c[k * 3 - 2] * shade, c[k * 3 - 1] * shade, c[k * 3] * shade)
		end
		if d.b and d.b[k] == 1 then t.both = true end -- (seen from both sides: drawn from both)
		mesh.tris[k] = t
	end
	mesh.twoSided = P.twoSided
	P.mesh, P.name, P.size, P.mode = mesh, name, size, mode
	return true
end
ns.ExtraMeshes = function(active, n, frameNo)
	if P.CityWanted() then return P.CityFrame(active, n, frameNo) end
	local m = P.mesh
	if not m then return n end
	if m.map ~= ns.cam.map then
		if not m.hidden then for _, t in ipairs(m.tris) do if t.shown then t.shown = false; t.tex:Hide() end end; m.hidden = true end
		return n
	end
	m.active = frameNo; m.hidden = false
	n = n + 1; active[n] = m
	return n
end
function P.Command(arg)
	local cmd, rest = arg:match("^(%S+)%s*(.*)$")
	if cmd == "city" then
		P.SetCity(rest ~= "off")
		return P.CityStatus()
	elseif cmd == "target" then
		local v = tonumber(rest)
		local t = v and P.SetTarget(v) or P.Target()
		return t > 0 and ("about %.1f ms a frame: the parts budget follows it (at most the parts-per-frame setting)"):format(t) or "a fixed parts budget (the parts-per-frame setting)"
	elseif cmd == "radius" then
		local v = tonumber(rest)
		return ("the game's models within %d yd of where you look (today's buildings beyond)"):format(v and P.SetRadius(v) or P.Radius())
	elseif cmd == "budget" then
		local v = tonumber(rest)
		return ("at most %d parts per frame"):format(v and P.SetBudget(v) or P.Budget())
	elseif cmd == "min" then
		local v = tonumber(rest)
		if not v then return ("smallest part %s sq yd at %d yd (0 = every part)"):format(P.MinArea(), P.REF_D) end
		return ("smallest part %s sq yd at %d yd"):format(P.SetMinArea(v), P.REF_D)
	end
	if arg == "both on" or arg == "both off" then P.twoSided = arg == "both on"; if P.mesh then P.mesh.twoSided = P.twoSided end; ns.Redraw(); return "both sides " .. (P.twoSided and "on" or "off") end
	local name, size, mode = arg:match("^(%S+)%s*(%d*)%s*(%a*)")
	if not name or name == "off" then Clear(); P.SetCity(false); return "off" end
	local tex, texN = arg:match("^%S+%s+(tex)(%w*)")
	local grey = arg:match("^%S+%s+(grey)") or arg:match("^%S+%s+(diag)")
	local key = (texN and texN ~= "") and ("tex" .. texN) or ((tex or grey) and 0) or tonumber(size) or 8000
	local ok = Build(name, key, grey or tex and "tex" or (mode ~= "" and mode or "flat"))
	ns.Redraw()
	return ok and ("%s %d triangles (%s)"):format(name, #P.mesh.tris, P.mode) or "no such model"
end

-- The game's own buildings (performance round 1, 2026-10-23), the default 3D buildings of this branch (the old
-- building blocks are off unless switched on: Buildings / /gps3d detail).
--
-- Data: one load-on-demand addon per city (GPS3D_City_<name>, written by the session's pb_city2.py), loaded when
-- the view comes within LOAD_NEAR yd of the city: buildings, each with its parts in facing groups; a group's
-- geometry is one string, decoded when the building is first drawn (DECODE_MS a frame at most) and forgotten
-- (tables and textures given back) when unused for FORGET seconds. Parts have 3 or 4 corners (wall rectangles are
-- one texture). Per frame:
--   * buildings off screen, and facing groups facing away from the camera, are skipped before any work;
--   * the buildings on screen are ranked by on-screen size per front-facing part (streets after buildings) and
--     drawn whole, best first, while the parts budget lasts (the rest show the map picture);
--   * the budget follows the frame's time (Target: Render's own ms, the last frame's), at most the slider; while
--     the view stands still and there is time, it is raised a step a frame until the slider's value (redrawn by
--     a small driver frame, only while it still rises);
--   * the size floor (smallest part, sq yd at REF_D yd, x (distance / REF_D)^2) is applied inside a group.
P.REF_D, P.KEEP, P.FORGET, P.DECODE_MS, P.LOAD_NEAR = 200, 5, 30, 4, 600
P.MIN_DEFAULT, P.MIN_MAX, P.MIN_STEP = 0, 50, 0.5
P.BUDGET_DEFAULT, P.BUDGET_MIN, P.BUDGET_MAX, P.BUDGET_STEP = 8000, 1000, 30000, 500
P.TARGET_DEFAULT, P.TARGET_MAX, P.TARGET_STEP = 10, 40, 1
P.RADIUS_DEFAULT, P.RADIUS_MAX, P.RADIUS_STEP = 400, 400, 10
P.CITIES = { -- (the cities with data: addon, name in ns.PocCityData, map, box: west, east, south, north edge yd)
	{ addon = "GPS3D_City_Stormwind", name = "Stormwind", map = 0, box = { 16164.2, 16687.3, -26163.0, -25635.6 } },
}
if ns.dataState then for _, c in ipairs(P.CITIES) do table.insert(ns.dataState.names, c.addon) end end -- (/gps3d test lists them)
local sqrt, floor, min, max, asin, sin, pi2 = math.sqrt, math.floor, math.min, math.max, math.asin, math.sin, math.pi / 2
local function Setting(key, default) local v = GPS3D_DB and GPS3D_DB[key]; if v == nil then return default end return v end
local function Store(key, v) GPS3D_DB = GPS3D_DB or {}; GPS3D_DB[key] = v; if ns.Redraw then ns.Redraw() end return v end
local function Step(v, lo, hi, step) return max(lo, min(hi, floor(v / step + 0.5) * step)) end
function P.MinArea() return Setting("pocMin", P.MIN_DEFAULT) end
function P.SetMinArea(v) return Store("pocMin", Step(v, 0, P.MIN_MAX, P.MIN_STEP)) end
function P.Budget() return Setting("pocBudget", P.BUDGET_DEFAULT) end
function P.SetBudget(v) P.eff = nil; return Store("pocBudget", Step(v, P.BUDGET_MIN, P.BUDGET_MAX, P.BUDGET_STEP)) end
function P.Target() return Setting("pocTarget", P.TARGET_DEFAULT) end
function P.SetTarget(v) P.eff = nil; return Store("pocTarget", Step(v, 0, P.TARGET_MAX, P.TARGET_STEP)) end
function P.Radius() return Setting("pocRadius", P.RADIUS_DEFAULT) end
function P.SetRadius(v) return Store("pocRadius", Step(v, 0, P.RADIUS_MAX, P.RADIUS_STEP)) end
function P.CityEnabled() return Setting("pocCity", true) end

-- city data: loaded near the city (OnDemand.lua's loader), buildings set up when it arrives
P.city = nil -- { units = all cities' buildings, map = ..., box = ... } once any city's data is in
local loaded = {}
local function Setup(c)
	local d = ns.PocCityData and ns.PocCityData[c.name]
	if not d then return end
	P.city = P.city or { units = {}, map = d.map, boxes = {} }
	local units = P.city.units
	for _, e in ipairs(d.units) do
		local u = { x = e[1], y = e[2], h = e[3], r = e[4], street = e[5] == 1, groups = {}, parts = 0, last = 0, decoded = false }
		for j, g in ipairs(e[6]) do
			local both = g[4] > 1.5
			u.groups[j] = { ax = g[1], ay = g[2], az = g[3], both = both, alpha = both and pi2 or asin(min(g[4], 1)), A = g[5], n = g[6], s = g[7] }
			u.parts = u.parts + g[6]
		end
		units[#units + 1] = u
	end
	P.city.boxes[#P.city.boxes + 1] = c.box
	P.city.box = c.box -- (the radius setting's block check: one city for now)
	c.ready = true
end
function P.CityWanted()
	if not P.CityEnabled() then return false end
	local cam = ns.cam
	for _, c in ipairs(P.CITIES) do
		if not c.ready and c.map == cam.map then
			local b = c.box
			local dx = cam.x < b[1] and b[1] - cam.x or (cam.x > b[2] and cam.x - b[2] or 0)
			local dy = cam.y < b[3] and b[3] - cam.y or (cam.y > b[4] and cam.y - b[4] or 0)
			if dx * dx + dy * dy < P.LOAD_NEAR * P.LOAD_NEAR and not loaded[c.addon] then
				loaded[c.addon] = true
				if (not ns.LoadDataAddon or ns.LoadDataAddon(c.addon, "the game's buildings")) then Setup(c) end
			end
		end
	end
	return P.city ~= nil
end

-- decoding a facing group's string (layout: pb_city2.py)
local VAL = {}
do local A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; for i = 1, 64 do VAL[A:byte(i)] = i - 1 end end
local byte = string.byte
local function DecodeGroup(g, u)
	local s, p = g.s, 1
	local function N(n)
		local v = 0
		for i = p, p + n - 1 do v = v * 64 + VAL[byte(s, i)] end
		p = p + n
		return v
	end
	local nv, np, w, npal = N(3), N(3), N(1), N(2)
	local pal = {}
	for i = 1, npal do pal[i] = N(4) end
	local vx, vy, vh = {}, {}, {}
	local ox, oy, oh = u.x, u.y, u.h
	for k = 1, nv do vx[k], vy[k], vh[k] = (N(3) - 131072) / 32 + ox, (N(3) - 131072) / 32 + oy, (N(3) - 131072) / 32 + oh end
	local tris, uv, f, a, vm, hi = {}, {}, {}, {}, {}, 0
	for k = 1, np do
		local nc = N(1)
		local i1, i2, i3 = N(w), N(w), N(w)
		local i4 = nc == 4 and N(w) or nil
		f[k] = pal[N(2)]
		local r = N(2) / 32; a[k] = r * r
		local o = (k - 1) * 8
		for j = 1, nc * 2 do uv[o + j] = (N(3) - 131072) / 1024 end
		if hi < i1 then hi = i1 end; if hi < i2 then hi = i2 end; if hi < i3 then hi = i3 end; if i4 and hi < i4 then hi = i4 end
		vm[k] = hi
		tris[k] = { a = i1, b = i2, c = i3, d = i4, bucket = -1, frame = 1, shown = false, both = g.both }
	end
	local m = { detail = true, poc = true, map = P.city.map, vx = vx, vy = vy, vh = vh, px = {}, py = {}, pd = {}, tris = tris, nv = 0, nt = 0, ready = 0, vm = vm, uv = uv, f = f, a = a, last = 0 }
	for k = 1, np do tris[k].mesh = m end
	return m
end
P.DecodeGroup = DecodeGroup -- (for tests)
local function Decode(u)
	for _, g in ipairs(u.groups) do g.mesh = DecodeGroup(g, u) end
	u.decoded = true
end
local function Prepare(m, upto) -- textures for parts ready+1 .. upto
	local vx, vy, vh, S, u, fd = m.vx, m.vy, m.vh, ns.SUN, m.uv, m.f
	for k = m.ready + 1, upto do
		local t = m.tris[k]
		local a, b, cc = t.a, t.b, t.c
		local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
		local ex2, eh2, ez2 = vx[cc] - vx[a], vh[cc] - vh[a], -(vy[cc] - vy[a])
		local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
		local l = sqrt(nx * nx + nh * nh + nz * nz); if l > 0 then nx, nh, nz = nx / l, nh / l, nz / l end
		local tex = ns.AcquireTex()
		if tex.file ~= fd[k] then tex:SetTexture(fd[k], "REPEAT", "REPEAT"); tex.file = fd[k] end
		local o = (k - 1) * 8
		if t.d then -- corners a b c d: upper left, lower left, lower right, upper right
			tex:SetTexCoord(u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 7], u[o + 8], u[o + 5], u[o + 6])
		else
			tex:SetTexCoord(u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6], u[o + 5], u[o + 6])
			t.u1, t.v1, t.u2, t.v2, t.u3, t.v3 = u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6]
		end
		local shade = 0.55 + 0.45 * math.abs(nx * S[1] + nh * S[2] + nz * S[3])
		tex:SetVertexColor(shade, shade, shade); tex.r, tex.g, tex.b = shade, shade, shade
		t.tex, t.bucket, t.frame, t.shown, t.x1, t.x2, t.x3, t.x4 = tex, -1, 1, false, nil, nil, nil, nil
	end
	if upto > m.ready then m.ready = upto end
end
local function Release(m)
	for k = 1, m.ready do local t = m.tris[k]; t.tex:Hide(); t.tex.file = nil; ns.ReleaseTex(t.tex); t.tex = nil; t.shown = false end
	m.ready, m.nt, m.nv, m.ntPrev = 0, 0, 0, 0
end
local function HideMesh(m)
	if m.ntPrev and m.ntPrev > 0 then for k = 1, m.ntPrev do local t = m.tris[k]; if t.shown then t.shown = false; t.tex:Hide() end end end
	m.ntPrev, m.nt = 0, 0
end
local function Forget(u) -- tables and textures given back; the strings stay
	for _, g in ipairs(u.groups) do if g.mesh then HideMesh(g.mesh); Release(g.mesh); g.mesh = nil end end
	u.decoded = false
end
function P.SetCity(on)
	if not on and P.city then for _, u in ipairs(P.city.units) do Forget(u) end end
	Store("pocCity", on and true or false)
end
function P.CityStatus()
	if not P.CityEnabled() then return "the game's buildings off" end
	if not P.city then return "the game's buildings on (no city data near the view yet)" end
	local n, dec = 0, 0
	for _, u in ipairs(P.city.units) do n = n + u.parts; if u.decoded then dec = dec + 1 end end
	return ("the game's buildings on: %d buildings, %d parts (%d decoded); at most %d parts a frame, %s"):format(#P.city.units, n, dec, P.Budget(),
		P.Target() > 0 and ("following %.0f ms a frame (now %d)"):format(P.Target(), floor(P.eff or P.Budget())) or "a fixed budget")
end
-- a covered block: drawn with the game's models (the old blocks skip it, GPS3D.lua asks)
local BLOCK = ns.BLOCK
local function Covered(x, y)
	local C = P.city
	if not C or C.map ~= ns.cam.map or not P.CityEnabled() then return false end
	local bx, by = (floor(x / BLOCK) + 0.5) * BLOCK, -(floor(-y / BLOCK) + 0.5) * BLOCK
	for _, b in ipairs(C.boxes) do
		if bx > b[1] + BLOCK / 2 and bx < b[2] - BLOCK / 2 and by > b[3] + BLOCK / 2 and by < b[4] - BLOCK / 2 then
			local R = P.Radius()
			if R >= P.RADIUS_MAX then return true end
			local dx, dy = bx - ns.cam.x, by - ns.cam.y
			return dx * dx + dy * dy < R * R
		end
	end
	return false
end
ns.PocCovers = Covered

local vis = {}
local function Count(a, thr) -- parts of at least thr (areas biggest first)
	local lo, hi = 0, #a
	while lo < hi do local mid = floor((lo + hi + 1) / 2); if a[mid] >= thr then lo = mid else hi = mid - 1 end end
	return lo
end
local function ByValue(a, b) return a.val > b.val end
local driver = CreateFrame("Frame")
driver:Hide()
driver:SetScript("OnUpdate", function(self) self:Hide(); if P.city then ns.Redraw() end end)
function P.CityFrame(active, n, frameNo)
	local C = P.city
	local now = GetTime()
	local units = C.units
	if C.map ~= ns.cam.map then
		for _, u in ipairs(units) do
			if u.decoded then for _, g in ipairs(u.groups) do HideMesh(g.mesh) end; if now - u.last > P.FORGET then Forget(u) end end
		end
		return n
	end
	-- the budget: follows last frame's Render time towards the target, never above the slider
	local maxB, target = P.Budget(), P.Target()
	local eff = P.eff or maxB
	local last = ns.stats and ns.stats.ms
	local rising = false
	if target > 0 and last and last > 0 then
		local r = target / max(last - (P.decodeMs or 0), 0.1) -- (last frame's decoding is a one-off: not counted)
		if r > 1.15 then r = 1.15 elseif r < 0.8 then r = 0.8 end
		local e2 = max(P.BUDGET_MIN, min(maxB, eff * r))
		rising = e2 > eff + 1
		eff = e2
	elseif target <= 0 then
		eff = maxB
	end
	P.eff, P.lastFrame = eff, frameNo
	local budget = floor(eff)
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
	local F = ns.Focal()
	local w, h = ns.canvas:GetSize(); w, h = w / 2, h / 2
	local floorK = P.MinArea() / (P.REF_D * P.REF_D)
	local nv, backParts = 0, 0
	for _, u in ipairs(units) do
		local x, y, z = u.x - cx, u.y - cy, u.h - cz
		local d = x * fx + y * fy + z * fz
		local r = u.r
		local on = d > -r and Covered(u.x, u.y)
		if on and d > r then
			local s = F / d
			local sx, sy, rs = (x * rx + y * ry) * s, (x * ux + y * uy + z * uz) * s, r * F / (d - r)
			if sx - rs > w or sx + rs < -w or sy - rs > h or sy + rs < -h then on = false end
		end
		u.drawn = false
		if on then
			local dist2 = x * x + y * y + z * z
			local dist = sqrt(dist2)
			local tx, ty, tz = -x / dist, -y / dist, -z / dist -- (towards the camera)
			local ar = dist > r and asin(r / dist) or pi2
			local dd = dist - r; if dd < 1 then dd = 1 end
			local thr = floorK * dd * dd
			local parts, area = 0, 0
			for _, g in ipairs(u.groups) do
				local lim = g.alpha + ar
				if g.both or lim >= pi2 or g.ax * tx + g.ay * ty + g.az * tz >= -sin(lim) then
					local nt = (thr > 0 and g.mesh) and Count(g.mesh.a, thr) or g.n
					g.want = nt; parts = parts + nt; area = area + g.A
				else
					g.want = 0; backParts = backParts + g.n
				end
			end
			if parts > 0 then
				u.fparts = parts
				u.val = area / dist2 / parts * (u.street and 0.1 or 1)
				nv = nv + 1; vis[nv] = u
			end
		end
	end
	for i = nv + 1, #vis do vis[i] = nil end
	table.sort(vis, ByValue)
	local used, drawn, skipped, waiting, decodedNow = 0, 0, 0, 0, 0
	local t0 = debugprofilestop()
	for i = 1, nv do
		local u = vis[i]
		if used + u.fparts <= budget then
			if not u.decoded then
				if debugprofilestop() - t0 < P.DECODE_MS then Decode(u); decodedNow = decodedNow + 1 else waiting = waiting + 1 end
			end
			if u.decoded then
				used = used + u.fparts; drawn = drawn + 1; u.drawn = true; u.last = now
				for _, g in ipairs(u.groups) do
					local m, nt = g.mesh, g.want
					if nt > 0 then
						if nt > m.ready then Prepare(m, nt) end
						m.nt, m.nv = nt, m.vm[nt]
						m.active, m.hidden, m.last = frameNo, false, now
						n = n + 1; active[n] = m
					end
				end
			end
		else
			skipped = skipped + 1
		end
	end
	for _, u in ipairs(units) do
		if u.decoded then
			for _, g in ipairs(u.groups) do local m = g.mesh; if m.active ~= frameNo then HideMesh(m); if m.ready > 0 and now - m.last > P.KEEP then Release(m) end end end
			if not u.drawn and now - u.last > P.FORGET then Forget(u) end
		end
	end
	-- more to do while the view stands still: buildings still to decode, or a budget still rising
	P.decodeMs = decodedNow > 0 and (debugprofilestop() - t0) or 0
	if waiting > 0 or (rising and eff < maxB) then driver:Show() end
	P.stats = { parts = used, buildings = drawn, skipped = skipped, onScreen = nv, backParts = backParts, waiting = waiting, decoded = decodedNow, budget = budget, cells = drawn, at200 = 0 }
	return n
end

-- the settings page
if GPS3D_API and GPS3D_API.settings then
	local list = GPS3D_API.settings
	list[#list + 1] = { kind = "header", name = "The game's buildings (proof of concept)" }
	list[#list + 1] = {
		kind = "check", key = "GPS3D_PocCity", name = "The game's buildings",
		tooltip = "The game's own building models where GPS has them (Stormwind's Trade District for now): drawn whole, the biggest on screen first (/gps3d poc city on|off).",
		default = true,
		get = function() return GPS3D_DB and GPS3D_DB.pocCity end,
		set = function(v) P.SetCity(v) end,
	}
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_PocBudget", name = "Building parts per frame",
		tooltip = "At most this many parts of the game's buildings are drawn: whole buildings, the biggest on screen first. Lower is faster (/gps3d poc budget <n>).",
		default = P.BUDGET_DEFAULT, min = P.BUDGET_MIN, max = P.BUDGET_MAX, step = P.BUDGET_STEP,
		format = function(v) return ("%d"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.pocBudget end,
		set = function(v) P.SetBudget(v) end,
	}
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_PocTarget", name = "Time for the 3D view",
		tooltip = "The 3D view's own time a frame it aims at: when a frame takes longer (turning), fewer building parts are drawn; when there is time, more, up to Building parts per frame. 0: always that many (/gps3d poc target <ms>).",
		default = P.TARGET_DEFAULT, min = 0, max = P.TARGET_MAX, step = P.TARGET_STEP,
		format = function(v) return v == 0 and "off" or ("%d ms"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.pocTarget end,
		set = function(v) P.SetTarget(v) end,
	}
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_PocMinArea", name = "Smallest building part",
		tooltip = "Parts of the game's buildings smaller than this (square yards, 200 yd from the camera; farther away a part must be bigger, nearer it may be smaller) are left out. 0 draws every part (/gps3d poc min <n>).",
		default = P.MIN_DEFAULT, min = 0, max = P.MIN_MAX, step = P.MIN_STEP,
		format = function(v) return v == 0 and "every part" or ("%.1f sq yd"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.pocMin end,
		set = function(v) P.SetMinArea(v) end,
	}
end
