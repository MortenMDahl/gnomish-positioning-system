-- GPS 3D: city buildings as closed shells with baked faces (proof of concept S1, branch poc-shells, 2026-10-24;
-- not for the shipped addon). The plan from the 2026-10-23 redesign: every building a small closed shell (4 to a few
-- dozen faces, made offline from the game's own model: testing/2026-10-24-poc-shells/sh_build2.py), each face a
-- picture of the real building rendered onto it (sh_bake.html), at three levels of detail. The shell is always drawn
-- whole, so nothing is ever see-through; the detail lives in the pictures, which cost nothing per frame.
--
-- Data: the city's load-on-demand addon (GPS3D_City_<name>, Shells_<name>.lua, written by sh_tolua.py), loaded when
-- the view comes within LOAD_NEAR yd of the city: units (buildings; the streets in 60-yd cells), each with one string
-- per level (four), decoded when the unit is first drawn at that level (DECODE_MS a frame at most, textures included) and
-- forgotten when unused for FORGET seconds. Pictures: Shells\L<level>_<page> (2048 x 2048).
--
-- Per frame: every unit in view is drawn, whole, at the level its size on screen asks for (PX: pixels per yard at
-- its nearest side; HYST keeps the last level near a threshold); a unit whose
-- level is not decoded yet shows a level it has, else waits a frame (a driver frame redraws). No budget.
-- Faces go through GPS3D.lua's triangle path (ns.ExtraMeshes: projection, back-face culling, painter's buckets) as
-- the proof-of-concept models did, drawn over the ground as building blocks are.
local _, ns = ...
local S = {}
ns.shells = S
S.LOAD_NEAR, S.KEEP, S.FORGET, S.DECODE_MS = 600, 5, 30, 6
S.PX, S.HYST = { 14, 7, 4.5 }, 1.15 -- pixels per yard on screen at a unit's near side: level 0 above PX[1], 1 above PX[2], 2 above PX[3], else 3
S.GROUND_BUCKETS = 256 -- with shells in view the ground keeps this many of the 1,024 depth buckets, the shells the rest
S.BLOCK_PX = 1.2 -- a whole 66.7-yd block below this many pixels per yard at its near side: drawn as one (level 4)
S.CITIES = { -- (cities with shell data: addon, name in ns.ShellData, map, box: west, east, south, north edge yd)
	{ addon = "GPS3D_City_Stormwind", name = "Stormwind", map = 0, box = { 16154, 16692, -26172, -25624 } },
}
if ns.dataState then
	for _, c in ipairs(S.CITIES) do
		local have = false
		for _, n in ipairs(ns.dataState.names) do if n == c.addon then have = true end end
		if not have then table.insert(ns.dataState.names, c.addon) end
	end
end
local sqrt, floor, min, max = math.sqrt, math.floor, math.min, math.max
local function Setting(key, default) local v = GPS3D_DB and GPS3D_DB[key]; if v == nil then return default end return v end
local function Store(key, v) GPS3D_DB = GPS3D_DB or {}; GPS3D_DB[key] = v; if ns.Redraw then ns.Redraw() end return v end
function S.Enabled() return Setting("shells", true) end
function S.Level() return Setting("shellsLevel", nil) end -- nil: by size on screen; 0, 1, 2: always that level

S.city = nil -- { units, map, boxes } once a city's data is in
local loaded = {}
local function Setup(c)
	local d = ns.ShellData and ns.ShellData[c.name]
	if not d then return end
	S.city = S.city or { units = {}, map = d.map, boxes = {} }
	local units = S.city.units
	local blocks, b0 = S.city.blocks or {}, #(S.city.blocks or {})
	S.city.blocks = blocks
	for _, e in ipairs(d.blocks or {}) do
		blocks[#blocks + 1] = { x = e[1], y = e[2], h = e[3], r = e[4], s = { false, false, false, false, e[5] }, mesh = {}, last = 0, path = d.path }
	end
	for _, e in ipairs(d.units) do
		units[#units + 1] = { x = e[1], y = e[2], h = e[3], r = e[4], s = { e[5], e[6], e[7], e[8] }, mesh = {}, lvl = nil, last = 0, path = d.path, block = e[9] > 0 and blocks[b0 + e[9]] or nil, street = e[10] == 1 }
	end
	S.city.boxes[#S.city.boxes + 1] = c.box
	c.ready = true
end
function S.Wanted()
	if not S.Enabled() then return false end
	local cam = ns.cam
	for _, c in ipairs(S.CITIES) do
		if not c.ready and c.map == cam.map and not loaded[c.addon] then
			local b = c.box
			local dx = cam.x < b[1] and b[1] - cam.x or (cam.x > b[2] and cam.x - b[2] or 0)
			local dy = cam.y < b[3] and b[3] - cam.y or (cam.y > b[4] and cam.y - b[4] or 0)
			if dx * dx + dy * dy < S.LOAD_NEAR * S.LOAD_NEAR then
				loaded[c.addon] = true
				if not ns.LoadDataAddon or ns.LoadDataAddon(c.addon, "the city's building shells") then Setup(c) end
			end
		end
	end
	return S.city ~= nil
end

-- decoding one level's string (layout: sh_tolua.py)
local VAL = {}
do local A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; for i = 1, 64 do VAL[A:byte(i)] = i - 1 end end
local byte = string.byte
local function Decode(u, lvl)
	local s, p = u.s[lvl + 1], 1
	local function N(n)
		local v = 0
		for i = p, p + n - 1 do v = v * 64 + VAL[byte(s, i)] end
		p = p + n
		return v
	end
	local nv, nf, w = N(3), N(3), N(1)
	local vx, vy, vh = {}, {}, {}
	local ox, oy, oh = u.x, u.y, u.h
	for k = 1, nv do vx[k], vy[k], vh[k] = (N(3) - 131072) / 32 + ox, (N(3) - 131072) / 32 + oy, (N(3) - 131072) / 32 + oh end
	local tris, page, uv = {}, {}, {}
	for k = 1, nf do
		local nc = N(1)
		local i1, i2, i3 = N(w), N(w), N(w)
		local i4 = nc == 4 and N(w) or nil
		page[k] = N(1)
		local o = (k - 1) * 8
		for j = 1, nc * 2 do uv[o + j] = N(2) / 4095 end
		tris[k] = { a = i1, b = i2, c = i3, d = i4, bucket = -1, frame = 1, shown = false }
	end
	local m = { detail = true, poc = true, map = S.city.map, vx = vx, vy = vy, vh = vh, px = {}, py = {}, pd = {}, tris = tris, ready = false, page = page, uv = uv, lvl = lvl, last = 0, path = u.path }
	for k = 1, nf do tris[k].mesh = m end
	return m
end
S.Decode = Decode -- (for tests)
local function Prepare(m) -- a texture for every face: its page, its corners in the page
	local u, path = m.uv, m.path
	for k, t in ipairs(m.tris) do
		local tex = ns.AcquireTex()
		local file = path:format(m.lvl, m.page[k])
		if tex.file ~= file then tex:SetTexture(file); tex.file = file end
		local o = (k - 1) * 8
		if t.d then -- corners a b c d: upper left, lower left, lower right, upper right
			tex:SetTexCoord(u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 7], u[o + 8], u[o + 5], u[o + 6])
		else
			tex:SetTexCoord(u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6], u[o + 5], u[o + 6])
			t.u1, t.v1, t.u2, t.v2, t.u3, t.v3 = u[o + 1], u[o + 2], u[o + 3], u[o + 4], u[o + 5], u[o + 6]
		end
		tex:SetVertexColor(1, 1, 1); tex.r, tex.g, tex.b = 1, 1, 1
		t.tex, t.bucket, t.frame, t.shown, t.x1, t.x2, t.x3, t.x4 = tex, -1, 1, false, nil, nil, nil, nil
	end
	m.ready = true
end
local function HideMesh(m)
	if m.hidden then return end
	for _, t in ipairs(m.tris) do if t.shown then t.shown = false; t.tex:Hide() end end
	m.hidden = true
end
local function Release(m)
	if not m.ready then return end
	for _, t in ipairs(m.tris) do if t.tex then t.tex:Hide(); t.tex.file = nil; ns.ReleaseTex(t.tex); t.tex = nil end; t.shown = false end
	m.ready = false
end
local function Forget(u)
	for l = 0, 4 do local m = u.mesh[l]; if m then HideMesh(m); Release(m); u.mesh[l] = nil end end
	u.lvl = nil
end
function S.SetEnabled(on)
	if not on and S.city then for _, u in ipairs(S.city.units) do Forget(u) end; for _, b in ipairs(S.city.blocks) do Forget(b) end end
	Store("shells", on and true or false)
end

-- the old building blocks give way inside a city with shells (GPS3D.lua asks ns.PocCovers)
local BLOCK = ns.BLOCK
local pocCovers = ns.PocCovers
ns.PocCovers = function(x, y)
	local C = S.city
	if C and C.map == ns.cam.map and S.Enabled() then
		local bx, by = (floor(x / BLOCK) + 0.5) * BLOCK, -(floor(-y / BLOCK) + 0.5) * BLOCK
		for _, b in ipairs(C.boxes) do
			if bx > b[1] + BLOCK / 2 and bx < b[2] - BLOCK / 2 and by > b[3] + BLOCK / 2 and by < b[4] - BLOCK / 2 then return true end
		end
	end
	return pocCovers and pocCovers(x, y) or false
end

local function LevelAt(p) local t = S.PX; return p > t[1] and 0 or (p > t[2] and 1 or (p > t[3] and 2 or 3)) end
local driver = CreateFrame("Frame")
driver:Hide()
driver:SetScript("OnUpdate", function(self) self:Hide(); if S.city then ns.Redraw() end end)
-- one unit or block: in view?, its level, decoded within the frame's time, handed to the renderer
local F, w, h, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, t0, now, frameNo_, act, nAct
local SR = { on = false, ground = S.GROUND_BUCKETS, kmin = 1, kmax = 2 } -- (the shells' range of horizontal distance this frame: GPS3D.lua's buckets)
ns.shellRange = SR
local function InView(u)
	local x, y, z = u.x - cx, u.y - cy, u.h - cz
	local d = x * fx + y * fy + z * fz
	local r = u.r
	if d <= -r then return false end
	if d > r then
		local s = F / d
		local sx, sy, rs = (x * rx + y * ry) * s, (x * ux + y * uy + z * uz) * s, r * F / (d - r)
		if sx - rs > w or sx + rs < -w or sy - rs > h or sy + rs < -h then return false end
	end
	u.hd = sqrt(x * x + y * y) -- (its horizontal distance from the camera: the range of the shells' buckets, Draw)
	return true, F / max(sqrt(x * x + y * y + z * z) - 0.7 * r, 5) -- (pixels per yard at its near side)
end
local function Draw(u, want, st)
	local m = u.mesh[want]
	if not (m and m.ready) then
		if debugprofilestop() - t0 < S.DECODE_MS then
			m = m or Decode(u, want); u.mesh[want] = m; Prepare(m); st.decoded = st.decoded + 1
		else
			st.waiting = st.waiting + 1; m = nil
			for l = 0, 4 do local o = u.mesh[l]; if o and o.ready then m = o; break end end
		end
	end
	if m then
		u.lvl = m.lvl; u.last = now
		m.active, m.hidden, m.last = frameNo_, false, now
		m.hk = true -- (the renderer orders shell faces by horizontal distance, in buckets above the ground's)
		local hd = u.hd
		if hd - u.r < SR.kmin then SR.kmin = max(1, hd - u.r) end
		if hd + u.r > SR.kmax then SR.kmax = hd + u.r end
		nAct = nAct + 1; act[nAct] = m
		st.units = st.units + 1; st.faces = st.faces + #m.tris; st.lv[m.lvl + 1] = st.lv[m.lvl + 1] + 1
	end
	return m
end
local function Tidy(u, use) -- hide the levels not drawn; give back what has been unused for a while
	for l = 0, 4 do
		local m = u.mesh[l]
		if m and m ~= use then
			HideMesh(m)
			if m.ready and now - m.last > S.KEEP then Release(m) end
		end
	end
	if not use and u.lvl and now - u.last > S.FORGET then Forget(u) end
end
local ST = { lv = { 0, 0, 0, 0, 0 } }
function S.Frame(active, n, frameNo)
	local C = S.city
	now, frameNo_, act, nAct = GetTime(), frameNo, active, n
	local units, blocks = C.units, C.blocks
	if C.map ~= ns.cam.map then
		SR.on = false
		for _, u in ipairs(units) do for l = 0, 4 do local m = u.mesh[l]; if m then HideMesh(m) end end end
		for _, u in ipairs(blocks) do local m = u.mesh[4]; if m then HideMesh(m) end end
		return n
	end
	fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
	F = ns.Focal()
	w, h = ns.canvas:GetSize(); w, h = w / 2, h / 2
	local fixed = S.Level()
	t0 = debugprofilestop()
	SR.on, SR.ground, SR.kmin, SR.kmax = false, S.GROUND_BUCKETS, 1e9, 0
	local st = ST
	st.units, st.faces, st.waiting, st.decoded, st.blocks = 0, 0, 0, 0, 0
	local lv = st.lv; lv[1], lv[2], lv[3], lv[4], lv[5] = 0, 0, 0, 0, 0
	-- blocks far enough away are drawn whole (their units are not)
	for _, b in ipairs(blocks) do
		local on, px = InView(b)
		local whole = false
		if fixed then whole = fixed == 4 and on
		elseif on then whole = px < (b.whole and S.BLOCK_PX * S.HYST or S.BLOCK_PX) end
		b.whole = whole
		local use = whole and Draw(b, 4, st) or nil
		if use then st.blocks = st.blocks + 1 end
		Tidy(b, use)
	end
	for _, u in ipairs(units) do
		local use
		if not (u.block and u.block.whole) then
			local on, px = InView(u)
			if on then
				local want = fixed and min(fixed, 3) or LevelAt(px)
				if not fixed and u.lvl and u.lvl <= 3 and want ~= u.lvl then -- (a change only once past the threshold by HYST)
					if LevelAt(want < u.lvl and px / S.HYST or px * S.HYST) == u.lvl then want = u.lvl end
				end
				use = Draw(u, want, st)
			end
		end
		Tidy(u, use)
	end
	if st.waiting > 0 then driver:Show() end
	SR.on = st.units > 0
	if SR.kmax <= SR.kmin then SR.kmax = SR.kmin + 1 end
	st.ms = debugprofilestop() - t0
	st.lv0, st.lv1, st.lv2, st.lv3, st.lv4 = lv[1], lv[2], lv[3], lv[4], lv[5]
	S.stats = st
	return nAct
end

local prev = ns.ExtraMeshes
ns.ExtraMeshes = function(active, n, frameNo)
	if S.Wanted() then n = S.Frame(active, n, frameNo)
	else
		SR.on = false
		if S.city then
			for _, u in ipairs(S.city.units) do for l = 0, 4 do local m = u.mesh[l]; if m then HideMesh(m) end end end
			for _, u in ipairs(S.city.blocks) do local m = u.mesh[4]; if m then HideMesh(m) end end
		end
	end
	if prev then n = prev(active, n, frameNo) end
	return n
end

function S.Status()
	if not S.Enabled() then return "shells off" end
	if not S.city then return "shells on (no city data near the view yet)" end
	local st = S.stats or {}
	return ("shells on: %d units, %d blocks; last frame %d drawn (%d / %d / %d / %d / %d at levels 0-4), %d faces, %d waiting; level %s"):format(#S.city.units, #S.city.blocks, st.units or 0,
		st.lv0 or 0, st.lv1 or 0, st.lv2 or 0, st.lv3 or 0, st.lv4 or 0, st.faces or 0, st.waiting or 0, S.Level() and tostring(S.Level()) or ("by size (%s px a yard; blocks under %s)"):format(table.concat(S.PX, " / "), S.BLOCK_PX))
end
function S.Command(arg)
	local cmd, rest = (arg or ""):match("^(%S*)%s*(.*)$")
	if cmd == "on" or cmd == "off" then S.SetEnabled(cmd == "on")
	elseif cmd == "level" then
		local v = tonumber(rest)
		if S.city then for _, u in ipairs(S.city.units) do u.lvl = nil end end
		Store("shellsLevel", v and max(0, min(4, floor(v))) or nil)
	elseif cmd == "px" then
		local a, b, c, d = rest:match("^(%S+)%s+(%S+)%s+(%S+)%s*(%S*)$")
		if tonumber(a) and tonumber(b) and tonumber(c) then S.PX = { tonumber(a), tonumber(b), tonumber(c) }; S.BLOCK_PX = tonumber(d) or S.BLOCK_PX; if ns.Redraw then ns.Redraw() end end
	end
	return S.Status()
end

-- the settings page
if GPS3D_API and GPS3D_API.settings then
	local list = GPS3D_API.settings
	list[#list + 1] = { kind = "header", name = "Building shells (proof of concept)" }
	list[#list + 1] = {
		kind = "check", key = "GPS3D_Shells", name = "Building shells",
		tooltip = "Cities' buildings as closed shells with pictures of the real buildings on them (Stormwind's Trade District for now), every building in view, finer near the camera (/gps3d shells on|off).",
		default = true,
		get = function() return GPS3D_DB and GPS3D_DB.shells end,
		set = function(v) S.SetEnabled(v) end,
	}
end
