-- GPS 3D: city buildings as closed shells with baked faces (proof of concept S1, branch poc-shells, 2026-10-24;
-- not for the shipped addon). The plan from the 2026-10-23 redesign: every building a small closed shell (4 to a few
-- dozen faces, made offline from the game's own model: testing/2026-10-24-poc-shells/sh_build2.py), each face a
-- picture of the real building rendered onto it (sh_bake.html), at three levels of detail. The shell is always drawn
-- whole, so nothing is ever see-through; the detail lives in the pictures, which cost nothing per frame.
--
-- Data: the city's load-on-demand addon (GPS3D_City_<name>, Shells_<name>.lua, written by sh_tolua_sets.py), loaded
-- when the view comes within LOAD_NEAR yd of the city: baked sets (a set: one shell level's shape, 0 finest to 3, or
-- the 66.7-yd blocks, with its pictures at some density), units (buildings; the streets in 60-yd cells), each with one
-- string per unit set, decoded when the unit is first drawn in that set (DECODE_MS a frame at most, textures included)
-- and forgotten when unused for FORGET seconds; blocks with the block set's string. Pictures: Shells\S<set>_<page>.jpg.
--
-- Levels of detail (since 2026-10-24): five, each from a distance (yd from the camera to a unit's near side) with a
-- set (S.lod, the data's defaults, GPS3D_DB.shellsLod; sliders on the settings page, /gps3d shells lod). Per frame
-- every unit in view is drawn, whole, in its level's set (HYST keeps the last level near a threshold); a block whose
-- level's set is the block set is drawn whole instead of its units. A unit whose set is not decoded yet shows one it
-- has, else waits a frame (a driver frame redraws). No budget.
-- Faces go through GPS3D.lua's triangle path (ns.ExtraMeshes: projection, back-face culling, painter's buckets) as
-- the proof-of-concept models did, drawn over the ground as building blocks are.
local _, ns = ...
local S = {}
ns.shells = S
S.LOAD_NEAR, S.KEEP, S.FORGET, S.DECODE_MS = 600, 5, 30, 6
S.HYST = 1.3 -- (since S1e) a unit goes to a coarser level only once its distance is past the threshold by this factor; to a finer one at the threshold
-- the face budget (S1e, 2026-10-24): when the units in view would draw more faces than this at their levels, every
-- distance is taken BIAS times longer (all thresholds pulled in), BIAS in steps of BIAS_STEP up to BIAS_MAX; it steps
-- back only when the faces one step back are predicted to stay within 0.95 of the budget (no limit cycle when many
-- units sit at the same distance). Faces counted from the data (each set's string says its face count), so decoding
-- lag does not matter. GPS3D_DB.shellsBudget; 0 = no budget.
S.FACE_BUDGET, S.BIAS_STEP, S.BIAS_MAX = 6000, 1.08, 4
S.UNDER = 1.0 -- (yd: how far a shell may reach below the drawn ground; Decode)
S.bias = 1
S.LEVELS = 5 -- levels of detail
S.lod = nil -- { { start yd, set }, ... } in use (the data's defaults, or GPS3D_DB.shellsLod)
S.CITIES = { -- (cities with shell data: addon, name in ns.ShellData, map, box: west, east, south, north edge yd)
	{ addon = "GPS3D_City_Stormwind", name = "Stormwind", map = 0, box = { 16154, 16692, -26172, -25624 } },
}
if ns.dataState then
	for _, a in ipairs({ "GPS3D_Shells0", "GPS3D_Shells1" }) do
		local have = false
		for _, n in ipairs(ns.dataState.names) do if n == a then have = true end end
		if not have then table.insert(ns.dataState.names, a) end
	end
	for _, c in ipairs(S.CITIES) do
		local have = false
		for _, n in ipairs(ns.dataState.names) do if n == c.addon then have = true end end
		if not have then table.insert(ns.dataState.names, c.addon) end
	end
end
local sqrt, floor, min, max, abs = math.sqrt, math.floor, math.min, math.max, math.abs
local function Setting(key, default) local v = GPS3D_DB and GPS3D_DB[key]; if v == nil then return default end return v end
local function Store(key, v) GPS3D_DB = GPS3D_DB or {}; GPS3D_DB[key] = v; if ns.Redraw then ns.Redraw() end return v end
function S.Enabled() return Setting("shells", true) end
function S.Level() return Setting("shellsSet", nil) end -- nil: by distance (the levels of detail); a set: always that set

S.city = nil -- { units, map, boxes } once a city's data is in
local loaded = {}
local function Setup(c)
	local d = ns.ShellData and ns.ShellData[c.name]
	if not d then return end
	S.city = S.city or { units = {}, map = d.map, boxes = {} }
	S.city.sets = d.sets
	S.city.blockSet = #d.sets -- (the last set: the blocks)
	S.city.lodDefault = d.lod
	local units = S.city.units
	local blocks, b0 = S.city.blocks or {}, #(S.city.blocks or {})
	S.city.blocks = blocks
	local nb = #d.sets
	for _, e in ipairs(d.blocks or {}) do
		local s = {}
		s[nb] = e[5]
		blocks[#blocks + 1] = { x = e[1], y = e[2], h = e[3], r = e[4], s = s, mesh = {}, last = 0, path = d.path }
	end
	for _, e in ipairs(d.units) do
		local s = {}
		for k = 1, nb - 1 do s[k] = e[6 + k] end
		units[#units + 1] = { x = e[1], y = e[2], h = e[3], r = e[4], s = s, mesh = {}, set = nil, last = 0, path = d.path, block = e[5] > 0 and blocks[b0 + e[5]] or nil, street = e[6] == 1 }
	end
	for _, u in ipairs(units) do local b = u.block; if b then b.nu = (b.nu or 0) + 1 end end
	S.LoadLod()
	S.city.boxes[#S.city.boxes + 1] = c.box
	-- the ground grid's cells under the shells' tops (keys gy * 4096 + gx of 16.7-yd cells): GPS3D.lua sorts the ground
	-- there as the city's floor, a little behind the shells
	if ns.shellRange and d.floor then
		local f = ns.shellRange.floor or {}
		for _, k in ipairs(d.floor) do f[k] = true end
		ns.shellRange.floor = f
		ns.shellRange.fstamp = (ns.shellRange.fstamp or 0) + 1 -- (GPS3D.lua works each triangle's floor out again)
	end
	-- the ground's own picture round and under the shells (sh_floorimg.py): the minimap's has the buildings drawn
	-- from above, a second, flat copy of them on the ground beside and under their shells (a bridge's on the water)
	if d.floorImage then
		local f = d.floorImage
		S.floorImg = { map = d.map, file = f.file, x0 = f.x0, x1 = f.x1, y0 = f.y0, y1 = f.y1, su = 1 / (f.x1 - f.x0), sv = 1 / (f.y1 - f.y0) }
	end
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
	-- (the ground's tiles under the city take the city's floor picture while the shells are on: GPS3D.lua
	-- BuildGridMesh; a new stamp builds them again)
	local fi = S.Enabled() and not S.noFloorImg and S.floorImg or nil
	if ns.floorImage ~= fi then ns.floorImage = fi; ns.floorImageStamp = (ns.floorImageStamp or 0) + 1 end
	return S.city ~= nil
end

-- decoding one level's string (layout: sh_tolua.py)
local VAL = {}
do local A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; for i = 1, 64 do VAL[A:byte(i)] = i - 1 end end
local byte = string.byte
local function Decode(u, set)
	local s, p = u.s[set] or "", 1
	if s == "" then -- (no faces in this set: a small unit only the finer sets keep)
		return { detail = true, poc = true, map = S.city.map, vx = {}, vy = {}, vh = {}, px = {}, py = {}, pd = {}, tris = {}, ready = false, page = {}, uv = {}, set = set, last = 0, path = u.path }
	end
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
	-- (S1e) corners more than UNDER yd below the ground the 3D view draws are lifted to that depth: a wall's foot
	-- under the drawn ground can only show through it (the painter's order has no depth test), as the gate's towers
	-- did over the fields outside Stormwind; the face's picture is cut there too (below)
	local low, map, grid = nil, S.city.map, ns.GridHeight
	if grid then
		for k = 1, nv do
			local g = grid(map, vx[k], vy[k])
			if g and vh[k] < g - S.UNDER then low = low or {}; low[k] = vh[k]; vh[k] = g - S.UNDER end
		end
	end
	local tris, page, uv = {}, {}, {}
	for k = 1, nf do
		local nc = N(1)
		local i1, i2, i3 = N(w), N(w), N(w)
		local i4 = nc == 4 and N(w) or nil
		page[k] = N(u.pw or 1)
		local o = (k - 1) * 8
		for j = 1, nc * 2 do uv[o + j] = N(2) / 4095 end
		if low then -- a lifted corner's picture point moves toward the corner above it in the face (same place, higher)
			local ids = { i1, i2, i3, i4 }
			for c = 1, nc do
				local k0 = ids[c]
				local h0 = low[k0]
				if h0 then
					for c2 = 1, nc do
						local k2 = ids[c2]
						local h2 = low[k2] or vh[k2]
						if c2 ~= c and abs(vx[k2] - vx[k0]) < 0.05 and abs(vy[k2] - vy[k0]) < 0.05 and h2 > vh[k0] then
							local f = (vh[k0] - h0) / (h2 - h0)
							local a, b = o + c * 2 - 1, o + c2 * 2 - 1
							uv[a], uv[a + 1] = uv[a] + (uv[b] - uv[a]) * f, uv[a + 1] + (uv[b + 1] - uv[a + 1]) * f
							break
						end
					end
				end
			end
		end
		local mx, my -- (its middle, for the renderer's order by horizontal distance; GPS3D.lua's draw loop)
		if i4 then mx, my = (vx[i1] + vx[i2] + vx[i3] + vx[i4]) / 4, (vy[i1] + vy[i2] + vy[i3] + vy[i4]) / 4
		else mx, my = (vx[i1] + vx[i2] + vx[i3]) / 3, (vy[i1] + vy[i2] + vy[i3]) / 3 end
		tris[k] = { a = i1, b = i2, c = i3, d = i4, bucket = -1, frame = 1, shown = false, mx = mx, my = my }
	end
	local m = { detail = true, poc = true, map = S.city.map, vx = vx, vy = vy, vh = vh, px = {}, py = {}, pd = {}, tris = tris, ready = false, page = page, uv = uv, set = set, last = 0, path = u.path }
	for k = 1, nf do tris[k].mesh = m end
	return m
end
S.Decode = Decode -- (for tests)
local function Prepare(m) -- a texture for every face: its page, its corners in the page
	local u, path = m.uv, m.path
	for k, t in ipairs(m.tris) do
		local tex = ns.AcquireTex()
		local file = path:format(m.set, m.page[k])
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
	for set, m in pairs(u.mesh) do HideMesh(m); Release(m); u.mesh[set] = nil end
	u.set, u.want = nil, nil
end
function S.SetEnabled(on)
	if not on and S.city then for _, u in ipairs(S.city.units) do Forget(u) end; for _, b in ipairs(S.city.blocks) do Forget(b) end end
	Store("shells", on and true or false)
end

-- the old building blocks give way inside a city with shells (GPS3D.lua asks ns.PocCovers)
local BLOCK = ns.BLOCK
local pocCovers = ns.PocCovers
ns.PocCovers = function(x, y)
	local cov = S.covered -- (the squares whole-block shells drew last frame: TilesFrame)
	local k = cov and cov[floor(x / BLOCK) * 1024 + floor(-y / BLOCK)]
	if k and S.frameNo and k >= S.frameNo - 1 and S.Enabled() then return true end
	local C = S.city
	if C and C.map == ns.cam.map and S.Enabled() then
		local bx, by = (floor(x / BLOCK) + 0.5) * BLOCK, -(floor(-y / BLOCK) + 0.5) * BLOCK
		for _, b in ipairs(C.boxes) do
			if bx > b[1] + BLOCK / 2 and bx < b[2] - BLOCK / 2 and by > b[3] + BLOCK / 2 and by < b[4] - BLOCK / 2 then return true end
		end
	end
	return pocCovers and pocCovers(x, y) or false
end

-- the levels of detail: the data's defaults, or the ones saved (GPS3D_DB.shellsLod), sorted by distance
function S.LoadLod()
	local C = S.city
	if not C then return end
	local def, saved, nset = C.lodDefault or {}, Setting("shellsLod", nil), #C.sets
	local lod = {}
	for i = 1, S.LEVELS do
		local d = def[i] or def[#def] or { 0, nset }
		local v = saved and saved[i]
		local start = v and tonumber(v[1]) or d[1]
		local set = v and tonumber(v[2]) or d[2]
		if i == 1 then start = 0 end
		lod[i] = { max(0, start), max(1, min(nset, floor(set))) }
	end
	for i = 2, S.LEVELS do if lod[i][1] < lod[i - 1][1] then lod[i][1] = lod[i - 1][1] end end -- (each starts no nearer than the one before)
	S.lod = lod
	for _, u in ipairs(C.units) do u.want = nil end
end
-- the level of detail at a distance (yd to the near side)
local function LevelAt(d)
	d = d * S.bias
	local lod, l = S.lod, 1
	for i = 2, #lod do if d >= lod[i][1] then l = i end end
	return l
end
-- the set a unit draws at a level: the level's, or, if that is the block set and the unit is drawn anyway (its block
-- is not drawn whole: the block's middle further than the unit), the nearest finer level's unit set
local function UnitSet(l)
	local lod, bs = S.lod, S.city.blockSet
	for i = l, 1, -1 do if lod[i][2] ~= bs then return lod[i][2] end end
	return 1
end
local driver = CreateFrame("Frame")
driver:Hide()
driver:SetScript("OnUpdate", function(self) self:Hide(); if S.city then ns.Redraw() end end)
-- one unit or block: in view?, its level, decoded within the frame's time, handed to the renderer
local F, w, h, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, t0, now, frameNo_, act, nAct
local SR = { on = false, kmin = 1, kmax = 2 } -- (the shells' range of horizontal distance this frame: GPS3D.lua's buckets)
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
	return true, max(sqrt(x * x + y * y + z * z) - 0.7 * r, 5) -- (its distance, to its near side)
end
local function Draw(u, want, st)
	local m = u.mesh[want]
	if not (m and m.ready) then
		if debugprofilestop() - t0 < S.DECODE_MS then
			m = m or Decode(u, want); u.mesh[want] = m; Prepare(m); st.decoded = st.decoded + 1
		else
			st.waiting = st.waiting + 1; m = nil
			for _, o in pairs(u.mesh) do if o.ready then m = o; break end end
		end
	end
	if m then
		u.set = m.set; u.last = now
		m.active, m.hidden, m.last = frameNo_, false, now
		m.hk = true -- (the renderer orders shell faces by horizontal distance, in buckets above the ground's)
		local hd = u.hd
		if hd - u.r < SR.kmin then SR.kmin = max(1, hd - u.r) end
		if hd + u.r > SR.kmax then SR.kmax = hd + u.r end
		nAct = nAct + 1; act[nAct] = m
		st.units = st.units + 1; st.faces = st.faces + #m.tris; st.sets[m.set] = (st.sets[m.set] or 0) + 1
	end
	return m
end
local function Tidy(u, use) -- hide the sets not drawn; give back what has been unused for a while
	for _, m in pairs(u.mesh) do
		if m ~= use then
			HideMesh(m)
			if m.ready and now - m.last > S.KEEP then Release(m) end
		end
	end
	if not use and u.set and now - u.last > S.FORGET then Forget(u) end
end
-- the units in view this frame and their distances (a unit in a whole block: the block's), for the face budget
local inU, inD, nIn = {}, {}, 0
local function FacesOf(u, set) -- a unit's face count in a set, from its string's header (cached)
	local nf = u.nf
	if not nf then nf = {}; u.nf = nf end
	local v = nf[set]
	if not v then
		local s = u.s[set] or ""
		v = #s >= 6 and (VAL[byte(s, 4)] * 64 + VAL[byte(s, 5)]) * 64 + VAL[byte(s, 6)] or 0
		nf[set] = v
	end
	return v
end
-- the faces the units in view would draw with all distances times bias
local function Predict(bias)
	local C, lod = S.city, S.lod
	local bs, keep, total = C.blockSet, S.bias, 0
	S.bias = bias
	local hyst = S.HYST
	for i = 1, nIn do
		local u = inU[i]
		local d = inD[i]
		local l, last = LevelAt(d), u.want
		if last and l > last and LevelAt(d / hyst) == last then l = last end -- (as the frame keeps it: hysteresis)
		if lod[l][2] == bs and u.block then total = total + FacesOf(u.block, bs) / (u.block.nu or 1)
		else total = total + FacesOf(u, UnitSet(l)) end
	end
	S.bias = keep
	return total
end
function S.Budget(n)
	local budget = Setting("shellsBudget", S.FACE_BUDGET)
	if not budget or budget <= 0 then S.bias = 1; return end
	local b, step = S.bias, S.BIAS_STEP
	if Predict(b) > budget and b * step <= S.BIAS_MAX + 1e-6 then S.bias = b * step
	elseif b > 1 + 1e-6 then
		local back = max(1, b / step)
		if Predict(back) <= 0.95 * budget then S.bias = back end
	end
	if b ~= S.bias then driver:Show() end -- (another frame to settle)
end
local ST = { lv = { 0, 0, 0, 0, 0 }, sets = {} }
local function HideAll(list) for _, u in ipairs(list) do for _, m in pairs(u.mesh) do HideMesh(m) end end end
local function CityFrame(st)
	local C = S.city
	local units, blocks = C.units, C.blocks
	local fixed = S.Level()
	local lv = st.lv; lv[1], lv[2], lv[3], lv[4], lv[5] = 0, 0, 0, 0, 0
	local sets = st.sets; for k in pairs(sets) do sets[k] = 0 end
	local bs, lod, hyst = C.blockSet, S.lod, S.HYST
	nIn = 0
	-- blocks whose level's set is the block set are drawn whole (their units are not)
	for _, b in ipairs(blocks) do
		local on, d = InView(b)
		local whole = false
		if fixed then whole = fixed == bs and on
		elseif on then
			local l = LevelAt(b.whole and d or d / hyst) -- (a block becomes whole once past the threshold by HYST; back at the threshold)
			whole = lod[l][2] == bs
			b.d = d
		end
		b.whole = whole; b.on = on
		local use = whole and Draw(b, bs, st) or nil
		if use then st.blocks = st.blocks + 1; lv[S.LEVELS] = lv[S.LEVELS] + 1 end
		Tidy(b, use)
	end
	for _, u in ipairs(units) do
		local use
		if u.block and u.block.whole then nIn = nIn + 1; inU[nIn], inD[nIn] = u, u.block.d
		else
			local on, d = InView(u)
			if on then
				nIn = nIn + 1; inU[nIn], inD[nIn] = u, d
				local set
				if fixed then set = fixed < bs and fixed or UnitSet(S.LEVELS)
				else
					local want = LevelAt(d)
					-- (a change only once past the threshold by HYST; against the level wanted last, not the one drawn:
					-- a unit drawn in a coarser set while its own waited to be decoded must not keep it)
					local last = u.want
					if last and want > last and LevelAt(d / hyst) == last then want = last end
					u.want = want
					lv[want] = lv[want] + 1
					set = UnitSet(want)
				end
				use = Draw(u, set, st)
			end
		end
		Tidy(u, use)
	end
	if not fixed then S.Budget(nIn) end
	st.bias = S.bias
	st.lv1, st.lv2, st.lv3, st.lv4, st.lv5 = lv[1], lv[2], lv[3], lv[4], lv[5]
end

-- every building of the map as whole-block shells (phase 1 of ALL_BUILDINGS.md, S1e): data addons GPS3D_Shells<map>
-- (ab_collect.py), loaded when the 3D view is on that map with shells on. Blocks within TILE_REACH yd of the camera
-- and in view, nearest first, while their faces fit TILE_BUDGET; the old simplified blocks give way in the 66.7-yd
-- squares drawn last frame (ns.PocCovers), so beyond the budget or the reach the old ones are still there.
S.TILE_ADDONS = { [0] = "GPS3D_Shells0", [1] = "GPS3D_Shells1" }
S.TILE_REACH, S.TILE_BUDGET = 1500, 5000
local TILE = 1600 / 3
local tileObjs, liveT, coveredT, cand = {}, {}, {}, {}
local function TileList(D, map, key) -- a tile's block objects, made when first needed
	local mt = tileObjs[map]
	if not mt then mt = {}; tileObjs[map] = mt end
	local l = mt[key]
	if l == nil then
		local src = D.tiles[key]
		l = false
		if src then
			l = {}
			for i, e in ipairs(src) do
				l[i] = { x = e[1], y = e[2], h = e[3], r = e[4], key = e[5] * 1024 + e[6], s = { [map] = e[7] }, mesh = {}, last = 0, path = D.path, pw = D.pw, ts = map }
			end
		end
		mt[key] = l
	end
	return l
end
function S.TilesWanted()
	if not S.Enabled() then return false end
	local map = ns.cam.map
	local addon = S.TILE_ADDONS[map]
	-- (loaded once the camera comes within reach of the ground it looks at: never for a far view or the planet)
	if addon and not loaded[addon] and (ns.cam.dist or 1e9) < S.TILE_REACH + 1000 then
		loaded[addon] = true
		if ns.LoadDataAddon then ns.LoadDataAddon(addon, "the buildings' shells") end
	end
	return ns.ShellTiles ~= nil and ns.ShellTiles[map] ~= nil
end
local function bydist(a, b) return a.d < b.d end
local function TilesFrame(st)
	local map = ns.cam.map
	local D = ns.ShellTiles and ns.ShellTiles[map]
	local nc = 0
	if D and S.Enabled() then
		local R = S.TILE_REACH
		for ty = floor((-cy - R) / TILE), floor((-cy + R) / TILE) do
			for tx = floor((cx - R) / TILE), floor((cx + R) / TILE) do
				local l = TileList(D, map, ty * 64 + tx)
				if l then
					for _, b in ipairs(l) do
						local dx, dy, rr = b.x - cx, b.y - cy, R + b.r
						if dx * dx + dy * dy < rr * rr then
							local on, d = InView(b)
							if on then nc = nc + 1; cand[nc] = b; b.d = d end
						end
					end
				end
			end
		end
	end
	for i = nc + 1, #cand do cand[i] = nil end
	if nc > 1 then table.sort(cand, bydist) end
	local budget, used = Setting("shellsTiles", S.TILE_BUDGET) or 0, 0
	for i = 1, nc do
		local b = cand[i]
		local f = FacesOf(b, b.ts)
		if used + f <= budget then
			local m = Draw(b, b.ts, st)
			if m then used = used + f; b.drawn = frameNo_; coveredT[b.key] = frameNo_; liveT[b] = true; st.tiles = st.tiles + 1 end
		end
	end
	for b in pairs(liveT) do
		if b.drawn == frameNo_ then Tidy(b, b.mesh[b.ts])
		else Tidy(b, nil); if not next(b.mesh) then liveT[b] = nil end end
	end
	st.tfaces = used
end
S.covered = coveredT -- (for tests)
function S.Frame(active, n, frameNo)
	local C = S.city
	now, frameNo_, act, nAct = GetTime(), frameNo, active, n
	S.frameNo = frameNo
	fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
	F = ns.Focal()
	w, h = ns.canvas:GetSize(); w, h = w / 2, h / 2
	t0 = debugprofilestop()
	SR.on, SR.kmin, SR.kmax = false, 1e9, 0
	local st = ST
	st.units, st.faces, st.waiting, st.decoded, st.blocks, st.tiles = 0, 0, 0, 0, 0, 0
	if C and C.map == ns.cam.map then CityFrame(st)
	else
		st.lv1, st.lv2, st.lv3, st.lv4, st.lv5, st.bias = 0, 0, 0, 0, 0, 1; S.bias = 1
		if C then HideAll(C.units); HideAll(C.blocks) end
	end
	TilesFrame(st)
	if st.waiting > 0 then driver:Show() end
	SR.on = st.units > 0
	if SR.kmax <= SR.kmin then SR.kmax = SR.kmin + 1 end
	st.ms = debugprofilestop() - t0
	S.stats = st
	return nAct
end

local prev = ns.ExtraMeshes
ns.ExtraMeshes = function(active, n, frameNo)
	local cw, tw = S.Wanted(), S.TilesWanted()
	if cw or tw then n = S.Frame(active, n, frameNo)
	else
		SR.on = false
		if S.city then HideAll(S.city.units); HideAll(S.city.blocks) end
		for b in pairs(liveT) do HideAll({ b }) end
	end
	if prev then n = prev(active, n, frameNo) end
	return n
end

-- a set's description: its shape (the level's simplification) and its pictures' density
function S.SetName(set)
	local C = S.city
	local d = C and C.sets[set]
	if not d then return tostring(set) end
	if d.lvl == 4 then return ("%d: whole blocks, %g px/yd"):format(set, d.ppy) end
	return ("%d: shape %g yd, %g px/yd"):format(set, d.shape, d.ppy)
end
function S.LodText()
	local lod, out = S.lod, {}
	if not lod then return "no city data yet" end
	for i, l in ipairs(lod) do out[#out + 1] = ("%d) from %d yd: set %s"):format(i, l[1], S.SetName(l[2])) end
	return table.concat(out, "; ")
end
function S.Status()
	if not S.Enabled() then return "shells off" end
	if not S.city then local st = S.stats or {}; return ("shells on (no city data near the view yet); %d whole-block shells of the map drawn, %d faces"):format(st.tiles or 0, st.tfaces or 0) end
	local st = S.stats or {}
	return ("shells on: %d units, %d blocks; last frame %d drawn (%d / %d / %d / %d / %d at levels 1-5; %d whole-block shells of the map, %d faces), %d faces, %d waiting; face budget %d, distances x%.2f; %s"):format(#S.city.units, #S.city.blocks, st.units or 0,
		st.lv1 or 0, st.lv2 or 0, st.lv3 or 0, st.lv4 or 0, st.lv5 or 0, st.tiles or 0, st.tfaces or 0, st.faces or 0, st.waiting or 0, Setting("shellsBudget", S.FACE_BUDGET) or 0, S.bias,
		S.Level() and ("always set " .. S.SetName(S.Level())) or ("levels: " .. S.LodText()))
end
-- one level's start (yd) and set; nil keeps that part (saved in GPS3D_DB.shellsLod)
function S.SetLod(i, start, set)
	if not S.lod or not S.lod[i] then return end
	GPS3D_DB = GPS3D_DB or {}
	local saved = GPS3D_DB.shellsLod or {}
	for k = 1, S.LEVELS do saved[k] = saved[k] or { S.lod[k][1], S.lod[k][2] } end
	if start then saved[i][1] = start end
	if set then saved[i][2] = set end
	GPS3D_DB.shellsLod = saved
	S.LoadLod()
	if ns.Redraw then ns.Redraw() end
end
function S.ResetLod()
	if GPS3D_DB then GPS3D_DB.shellsLod = nil end
	S.LoadLod()
	if ns.Redraw then ns.Redraw() end
end
function S.Command(arg)
	local cmd, rest = (arg or ""):match("^(%S*)%s*(.*)$")
	if cmd == "on" or cmd == "off" then S.SetEnabled(cmd == "on")
	elseif cmd == "set" or cmd == "level" then -- (always one set; no number: by distance again)
		local v = tonumber(rest)
		local n = S.city and #S.city.sets or 9
		if S.city then for _, u in ipairs(S.city.units) do u.set, u.want = nil, nil end end
		Store("shellsSet", v and max(1, min(n, floor(v))) or nil)
	elseif cmd == "budget" then -- (faces; 0: none)
		local v = tonumber(rest)
		if v then Store("shellsBudget", max(0, floor(v))) end
		return ("Shells face budget %d (0: none)"):format(Setting("shellsBudget", S.FACE_BUDGET))
	elseif cmd == "tiles" then -- (the whole-block shells' faces; 0: none drawn)
		local v = tonumber(rest)
		if v then Store("shellsTiles", max(0, floor(v))) end
		return ("Whole-block shells: face budget %d, within %d yd"):format(Setting("shellsTiles", S.TILE_BUDGET), S.TILE_REACH)
	elseif cmd == "floor" then -- (the city's floor picture under the shells, or the minimap's: to compare)
		S.noFloorImg = rest == "off"
		if ns.Redraw then ns.Redraw() end
		return "City floor picture " .. (S.noFloorImg and "off (the minimap)" or "on")
	elseif cmd == "lod" then
		local a, b, c = rest:match("^(%S*)%s*(%S*)%s*(%S*)$")
		if a == "reset" then S.ResetLod()
		elseif tonumber(a) then S.SetLod(floor(tonumber(a)), tonumber(b), tonumber(c)) end
		local sets = {}
		if S.city then for k = 1, #S.city.sets do sets[#sets + 1] = S.SetName(k) end end
		return S.LodText() .. ". Sets: " .. table.concat(sets, "; ")
	end
	return S.Status()
end

-- the settings page: on, and the five levels of detail (from a distance, a set)
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
	local SETS = 9 -- (the sliders' range; the sets of the data loaded, Stormwind's: 9)
	local DEF = { { 0, 3 }, { 250, 5 }, { 350, 6 }, { 500, 8 }, { 2600, 9 } } -- (the data's defaults, for the page before the data loads)
	for i = 1, S.LEVELS do
		if i > 1 then
			list[#list + 1] = {
				kind = "slider", key = "GPS3D_ShellsStart" .. i, name = ("Shells level %d from"):format(i),
				tooltip = ("How far from the camera (yards, to a building's near side) level %d begins; level %d is used nearer (/gps3d shells lod %d <yd> <set>)."):format(i, i - 1, i),
				default = DEF[i][1], min = 0, max = 2000, step = 5,
				format = function(v) return ("%d yd"):format(v) end,
				get = function() return S.lod and S.lod[i][1] or DEF[i][1] end,
				set = function(v) S.SetLod(i, v, nil) end,
			}
		end
		list[#list + 1] = {
			kind = "slider", key = "GPS3D_ShellsSet" .. i, name = ("Shells level %d detail"):format(i),
			tooltip = "Which baked set this level draws: 1 is the finest shape with the sharpest pictures, then coarser shapes and softer pictures; the last is whole 66.7-yd blocks. The value shows the shape's simplification (yd) and the pictures' density (pixels a yard).",
			default = DEF[i][2], min = 1, max = SETS, step = 1,
			format = function(v) return S.city and S.SetName(v) or tostring(v) end,
			get = function() return S.lod and S.lod[i][2] or DEF[i][2] end,
			set = function(v) S.SetLod(i, nil, v) end,
		}
	end
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_ShellsBudget", name = "Shells face budget",
		tooltip = "The most faces the shells may draw: with more buildings in view, every level begins nearer until they fit (up to 4 times nearer). 0: no limit (/gps3d shells budget <n>).",
		default = S.FACE_BUDGET, min = 0, max = 20000, step = 250,
		format = function(v) return v > 0 and ("%d faces"):format(v) or "no limit" end,
		get = function() return Setting("shellsBudget", S.FACE_BUDGET) end,
		set = function(v) Store("shellsBudget", v) end,
	}
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_ShellsTiles", name = "Whole-block shells budget",
		tooltip = "Every other building of the map as 66.7-yard block shells with pictures: the most faces they may draw, nearest first (within 1,500 yards); further out the simple blocks stay. 0: none (/gps3d shells tiles <n>).",
		default = S.TILE_BUDGET, min = 0, max = 20000, step = 250,
		format = function(v) return v > 0 and ("%d faces"):format(v) or "none" end,
		get = function() return Setting("shellsTiles", S.TILE_BUDGET) end,
		set = function(v) Store("shellsTiles", v) end,
	}
	list[#list + 1] = { kind = "button", key = "GPS3D_ShellsReset", name = "Shells levels", text = "Defaults", tooltip = "The levels of detail as the city's data sets them (/gps3d shells lod reset).", click = function() S.ResetLod() end }
end
