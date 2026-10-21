-- GPS 3D: the game's own models in the 3D view, in the ModelScene that already draws your character
-- (same camera as the terrain). Data/Models_<map>.lua (scripts/build_models.py) say where every
-- model of the map stands: props and trees (M2 doodads) and buildings (WMOs), with their rotation
-- and scale, from the game's own map files.
--
-- Which ones: around the middle of the view (Model distance), in view, at least Smallest model pixels
-- big on screen; buildings first (all of them that pass), then props and trees biggest on screen
-- first, up to Props and trees at most. Props hidden behind the ground (tilted view) are left out.
-- The choice is made again (at most 10 times a second) when the view has moved, turned or zoomed
-- enough to matter, not every frame; the actors stay where they are in the world, so between choices
-- only the scene's camera moves. Actors are pooled and keep their model when they can (an actor
-- showing the same model is reused before one has to load another), and at most SWAP_LIMIT actors
-- load a new model per choice (the rest follow a tenth of a second later).
--
-- Buildings: whether the game lets an addon's ModelScene draw a WMO is not in Blizzard's source, so
-- it is checked once per game build: the first time buildings are wanted their simplified shapes stay
-- drawn while the WMO actors load; once one reports loaded with a real bounding box the game's
-- buildings replace the simplified blocks inside Model distance (ns.ModelsCover), and if none has
-- loaded within WMO_WAIT seconds the simplified shapes stay (said once in chat and in the debug log).
-- The result is saved per build (GPS3D_DB.wmoCheck); /gps3d models wmo checks again.
-- Since 2026-10-21 the game's buildings are not the default (Buildings close up: simplified shapes): the
-- first time the 3D view opened in the game (Forever 1.60.1.70532, the Valley of Trials), the client
-- crashed (ACCESS_VIOLATION reading address 0x10, no Lua running) right where this check hands the game
-- its first WMO, the only model the 3D view gives the game when it opens with the defaults. A crash
-- cannot be caught from Lua, so the check only runs once someone picks the game's buildings.
--
-- Caves and mines (kind 2 in the data: WMOs whose rooms and rock shell lie in the ground, see
-- scripts/browser_underground.js) are buildings like the others when the game draws WMOs (since
-- 2026-10-18; /gps3d models caves off leaves them out, should their tunnels show through the ground:
-- the terrain is not in the scene's depth buffer, so only the cave's own rock hides them). With the
-- game's buildings refused they stay as simplified shapes of their outside parts.
--
-- Placement (build_models.py): position x east, y north, h up; rotation yaw, pitch, roll, applied
-- as Rz(yaw) Ry(pitch) Rx(roll), which is the actor's SetYaw / SetPitch / SetRoll; scale.
local addonName, ns = ...
local GPS = GPS_API
local TILE = ns.TILE
local floor, min, max, sqrt, abs, exp, pi = math.floor, math.min, math.max, math.sqrt, math.abs, math.exp, math.pi

local SELECT_GAP = 0.1   -- seconds between two choices at the least
local POLL_GAP = 0.5     -- loading states checked this often
local SWAP_LIMIT = 40    -- actors given a new model per choice
local WMO_WAIT = 8       -- seconds the building check waits for a WMO to load
local LOAD_WAIT = 10     -- a model not loaded after this long counts as failed
local POOL_LIMIT = 3000  -- actors at most
local UNDRAWN_REACH = 3500 -- buildings not drawn are listed this far round the view (past where building blocks are drawn)
local OFF = 131072
local WMO_PROBE, M2_PROBE = 106965, 189927 -- the Elwynn farmhouse (a building), an Elwynn tree

ns.modelDefaults = { buildingModels = "simple", props = false, caves = true, modelCount = 250, modelRange = 600, modelPx = 6 }
local function Get(key)
	local v = ns.DB()[key]
	if v == nil then return ns.modelDefaults[key] end
	return v
end
ns.ModelSetting = Get

local Num = ns.Num -- base64 numbers, as GPS3D.lua reads its own data

------------------------------------------------------------------------------------------------
-- Data: a map's models (palette) and a tile's placements, decoded when first needed
------------------------------------------------------------------------------------------------
local palettes = {}
local function Palette(map)
	local p = palettes[map]
	if p ~= nil then return p or nil end
	local s = ns.ModelFiles and ns.ModelFiles[map]
	if not s then palettes[map] = false return nil end
	p = { n = #s / 15, fdid = {}, wmo = {}, cave = {}, radius = {}, bottom = {}, top = {}, size = {}, mid = {} }
	for i = 0, p.n - 1 do
		local q = i * 15 + 1
		local r, lo, hi = Num(s, q + 6, 3) / 16, (Num(s, q + 9, 3) - OFF) / 16, (Num(s, q + 12, 3) - OFF) / 16
		local kind = Num(s, q + 5, 1) -- 0 prop or tree (M2), 1 building (WMO), 2 cave or mine (WMO)
		p.fdid[i], p.wmo[i], p.cave[i], p.radius[i], p.bottom[i], p.top[i] = Num(s, q, 5), kind >= 1, kind == 2, r, lo, hi
		p.size[i], p.mid[i] = max(r, (hi - lo) / 2), (lo + hi) / 2
	end
	palettes[map] = p
	return p
end

-- Placement sets ("sources"): arrays mi, x, y, h, yaw, pitch, roll, sc, size (yards: the model's
-- size times the scale), cz (height of the model's middle) and id (unique over every map: the
-- tile's map * 4096 + ty * 64 + tx, times 8192, plus the placement's place in the tile).
local function NewSource(n)
	return { n = n, id = {}, mi = {}, x = {}, y = {}, h = {}, yaw = {}, pitch = {}, roll = {}, sc = {}, size = {}, cz = {} }
end
-- Placement number i (1-based) of tile string s into dst[j]
local function Decode(dst, j, s, i, x0, y0, pal, idBase)
	local q = 6 + (i - 1) * 19
	local mi = Num(s, q, 2)
	local sc = exp((Num(s, q + 17, 2) - 2048) / 256)
	local h = (Num(s, q + 8, 3) - OFF) / 16
	dst.id[j], dst.mi[j], dst.x[j], dst.y[j], dst.h[j] = idBase + i, mi, x0 + Num(s, q + 2, 3) / 64, y0 - Num(s, q + 5, 3) / 64, h
	dst.yaw[j] = Num(s, q + 11, 2) / 4096 * 2 * pi - pi
	dst.pitch[j] = Num(s, q + 13, 2) / 4096 * 2 * pi - pi
	dst.roll[j] = Num(s, q + 15, 2) / 4096 * 2 * pi - pi
	dst.sc[j], dst.size[j], dst.cz[j] = sc, pal.size[mi] * sc, h + pal.mid[mi] * sc
end

local tiles, nTiles = {}, 0
-- A tile's placements, biggest first.
local function Tile(map, tx, ty)
	local k = map * 4096 + ty * 64 + tx
	local t = tiles[k]
	if t ~= nil then return t or nil end
	local m = ns.Models and ns.Models[map]
	local s = m and tx >= 0 and tx < 64 and ty >= 0 and ty < 64 and m[ty * 64 + tx]
	local pal = s and Palette(map)
	if not pal then tiles[k] = false return nil end
	local n = Num(s, 3, 3)
	t = NewSource(n)
	for i = 1, n do Decode(t, i, s, i, tx * TILE, -ty * TILE, pal, k * 8192) end
	if nTiles >= 200 then wipe(tiles); nTiles = 0 end
	tiles[k], nTiles = t, nTiles + 1
	return t
end

-- Every building of a map in one list (a few thousand at most), so that big ones whose middle is
-- far off are found too, without decoding the props of every tile in between.
local wmoLists = {}
local function WmoList(map)
	local w = wmoLists[map]
	if w then return w end
	local pal = Palette(map)
	w = NewSource(0)
	for key, s in pairs(ns.Models and ns.Models[map] or {}) do
		local tx, ty = key % 64, floor(key / 64)
		for i = 1, Num(s, 3, 3) do
			if pal.wmo[Num(s, 6 + (i - 1) * 19, 2)] then
				w.n = w.n + 1
				Decode(w, w.n, s, i, tx * TILE, -ty * TILE, pal, (map * 4096 + key) * 8192)
			end
		end
	end
	wmoLists[map] = w
	return w
end
ns.ModelTile, ns.ModelPalette, ns.ModelWmoList = Tile, Palette, WmoList

-- A model's size and kind by FileDataID (the sandbox draws its stand-ins with it): radius, bottom, top, isWMO
GPS3D_API.ModelInfo = function(fdid)
	for map in pairs(ns.ModelFiles or {}) do
		local p = Palette(map)
		for i = 0, p.n - 1 do
			if p.fdid[i] == fdid then return p.radius[i], p.bottom[i], p.top[i], p.wmo[i] end
		end
	end
end

------------------------------------------------------------------------------------------------
-- State
------------------------------------------------------------------------------------------------
local M = {
	pool = {}, byId = {}, bad = {}, stamp = 0, turn = 0, tilt = "normal", dirty = true, last = -1, poll = 0, version = 0,
	wmo = nil,          -- the building check: nil (not run this build), "testing", "yes", "no"
	shown = 0, shownWmo = 0, loading = 0, failed = 0, inRange = 0, pending = false,
	perf = { picks = 0, ms = 0, worst = 0, cands = 0, swaps = 0 },
}
ns.modelState = M
local candSrc, candIdx, candScore, candWmo, order, need = {}, {}, {}, {}, {}, {}
local bigX, bigY, bigR = {}, {}, {} -- (big buildings chosen this time, reaching past Model distance)
local function ByScore(a, b) return candScore[a] > candScore[b] end

local function BuildKey()
	local version, build = GetBuildInfo()
	return tostring(version) .. "." .. tostring(build)
end

local function BuildingsWanted()
	return ns.DB().detail ~= false and Get("buildingModels") == "game"
end
local function PropsWanted()
	return Get("props") and Get("modelCount") > 0
end

local function Release(e)
	if e.id then M.byId[e.id] = nil; e.id = nil end
	e.actor:Hide()
end
local function ReleaseAll()
	for _, e in ipairs(M.pool) do Release(e) end
	M.shown, M.shownWmo, M.loading = 0, 0, 0
	M.coverOn = false
end

-- Settings changed: choose again
ns.ModelsChanged = function()
	M.version, M.dirty = M.version + 1, true
	if ns.frame:IsShown() and ns.SelectModels then ns.SelectModels() end -- at once (what /gps3d models prints is then current)
end

------------------------------------------------------------------------------------------------
-- The building check
------------------------------------------------------------------------------------------------
local function Box(actor)
	local ok, lo, hi = pcall(actor.GetActiveBoundingBox, actor)
	if not (ok and lo and hi) then return nil end
	local function xyz(v)
		if type(v) == "table" then
			if v.GetXYZ then return v:GetXYZ() end
			return v.x, v.y, v.z
		end
	end
	local x0, y0, z0 = xyz(lo)
	local x1, y1, z1 = xyz(hi)
	if not (x0 and x1) then return nil end
	return x1 - x0, y1 - y0, z1 - z0
end
ns.ModelBox = Box

local function SetWmo(result, why)
	if M.wmo == result then return end
	M.wmo = result
	local db = ns.DB()
	if result == "yes" or result == "no" then
		db.wmoCheck, db.wmoBuild = result, BuildKey()
		GPS.Log("MODELS", "building check: %s (%s)", result, why or "")
		if result == "no" then
			print("|cff55ff55GPS3D|r: this game does not draw buildings (WMO models) in an addon's 3D view, so buildings stay as simplified shapes. Props and trees are the game's own models.")
		else
			print("|cff55ff55GPS3D|r: the game draws its own buildings in the 3D view; they replace the simplified shapes up to the model distance.")
		end
		M.dirty = true
	end
end

local function StartCheck()
	local db = ns.DB()
	if M.wmo == nil and db.wmoCheck and db.wmoBuild == BuildKey() then M.wmo = db.wmoCheck end
	if M.wmo == nil then
		M.wmo, M.wmoSince, M.wmoSets, M.wmoSetOK = "testing", GetTime(), 0, 0
		GPS.Log("MODELS", "building check started (build %s)", BuildKey())
	end
end

------------------------------------------------------------------------------------------------
-- Choosing the models
------------------------------------------------------------------------------------------------
local function Occluded(x, y, top, cx, cy, cz, map)
	for k = 1, 6 do
		local f = k / 7
		local g = ns.GridHeight(map, cx + (x - cx) * f, cy + (y - cy) * f)
		if g and g > cz + (top - cz) * f + 2 then return true end
	end
	return false
end

ns.ModelOccluded = Occluded
ns.modelConst = { SELECT_GAP = SELECT_GAP, SWAP_LIMIT = SWAP_LIMIT, WMO_WAIT = WMO_WAIT, LOAD_WAIT = LOAD_WAIT }

local function Place(e, t, i, pal, now)
	-- t: a source (Tile or WmoList), i: the placement in it
	local fdid = pal.fdid[t.mi[i]]
	local a = e.actor
	if e.fdid ~= fdid then
		local ok = a:SetModelByFileID(fdid)
		e.fdid, e.since, e.loaded, e.failed = fdid, now, false, false
		e.wmo = pal.wmo[t.mi[i]]
		M.perf.swaps = M.perf.swaps + 1
		if e.wmo and M.wmo == "testing" then
			M.wmoSets = M.wmoSets + 1
			if ok then M.wmoSetOK = M.wmoSetOK + 1 end
		end
	end
	a:SetPosition(t.x[i], t.y[i], t.h[i])
	-- fixes for the in-game check, if the game's actors turn the other way (/gps3d models turn, tilt)
	local tilt = M.tilt
	a:SetYaw(t.yaw[i] + M.turn)
	a:SetPitch(tilt == "off" and 0 or tilt == "flip" and -t.pitch[i] or t.pitch[i])
	a:SetRoll(tilt == "off" and 0 or tilt == "flip" and -t.roll[i] or t.roll[i])
	a:SetScale(t.sc[i])
	a:Show()
	e.id = t.id[i]
	e.x, e.y, e.r = t.x[i], t.y[i], pal.radius[t.mi[i]] * t.sc[i] -- (a building's footprint, for ModelsCover)
	M.byId[e.id] = e
end

local Holes -- (below)

local function NewEntry()
	if #M.pool >= POOL_LIMIT then return nil end
	local actor = ns.NewActor()
	if not actor then return nil end
	if actor.SetUseCenterForOrigin then actor:SetUseCenterForOrigin(false, false, false) end
	local e = { actor = actor }
	M.pool[#M.pool + 1] = e
	return e
end

local function Select()
	local t0 = debugprofilestop()
	local now = GetTime()
	local cam = ns.cam
	local map = cam.map
	local wantB, wantP = BuildingsWanted(), PropsWanted()
	if wantB then StartCheck() end
	local showB = wantB and M.wmo ~= "no"
	local pal = (showB or wantP) and Palette(map)
	M.dirty, M.last, M.pending = false, now, false
	M.turn, M.tilt = math.rad(ns.DB().modelTurn or 0), ns.DB().modelTilt or "normal"
	M.sel = { map = map, x = cam.x, y = cam.y, dist = cam.dist, yaw = cam.yaw, pitch = cam.pitch, version = M.version }
	M.sel.w, M.sel.h = ns.canvas:GetSize()
	if not pal then
		ReleaseAll()
		M.inRange = 0
		return
	end
	local F = ns.Focal()
	local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
	local hw, hh = M.sel.w / 2, M.sel.h / 2
	local R, minPx, count = Get("modelRange"), Get("modelPx"), wantP and Get("modelCount") or 0
	local bad = M.bad
	local badWmo = {}
	local n = 0
	-- one placement of source t: in range, in view, big enough? (wmo: a building; lim: how far its
	-- middle may be from the middle of the view)
	local function Consider(t, i, wmo, lim)
		local x, y = t.x[i], t.y[i]
		local ox, oy = x - cam.x, y - cam.y
		if ox * ox + oy * oy > lim * lim then return end
		local size = t.size[i]
		local dx, dy, dz = x - cx, y - cy, t.cz[i] - cz
		local d = dx * fx + dy * fy + dz * fz
		if d <= -size then return end -- behind the camera
		local dd = max(d, 1)
		local px = size * F / dd
		if px < minPx then return end
		local sx, sy = (dx * rx + dy * ry) * F / dd, (dx * ux + dy * uy + dz * uz) * F / dd
		if d > size and (abs(sx) > hw + px or abs(sy) > hh + px) then return end -- off the view (unless around the camera)
		if bad[pal.fdid[t.mi[i]]] then
			if wmo then badWmo[#badWmo + 1] = { x, y, pal.radius[t.mi[i]] * t.sc[i] } end -- its simplified shape stays (ModelsCover)
			return
		end
		n = n + 1
		candSrc[n], candIdx[n], candWmo[n] = t, i, wmo
		candScore[n] = wmo and px + 1e9 or px
		order[n] = n
	end
	local nb = 0 -- big buildings chosen reaching past Model distance (bigX, bigY, bigR)
	if showB then
		local w, caves = WmoList(map), Get("caves")
		for i = 1, w.n do
			if caves or not pal.cave[w.mi[i]] then Consider(w, i, true, R + pal.radius[w.mi[i]] * w.sc[i]) end
		end
		-- a big building chosen reaching past Model distance (Nordrassil on Mount Hyjal, Stormwind): the
		-- buildings standing on it further out are chosen too, so all of it is the game's there (its
		-- simplified shapes give way under it, ModelsCover) and nothing on it is left out (2026-10-19)
		for k = 1, n do
			if candWmo[k] then
				local t, i = candSrc[k], candIdx[k]
				local r = pal.radius[t.mi[i]] * t.sc[i]
				local ox, oy = t.x[i] - cam.x, t.y[i] - cam.y
				if ox * ox + oy * oy > (R - r) * (R - r) or r > R then nb = nb + 1; bigX[nb], bigY[nb], bigR[nb] = t.x[i], t.y[i], r end
			end
		end
		if nb > 0 then
			for i = 1, w.n do
				local r = pal.radius[w.mi[i]] * w.sc[i]
				local ox, oy = w.x[i] - cam.x, w.y[i] - cam.y
				if ox * ox + oy * oy > (R + r) * (R + r) and (caves or not pal.cave[w.mi[i]]) then
					for b = 1, nb do
						local dx, dy, rr = w.x[i] - bigX[b], w.y[i] - bigY[b], bigR[b] + r
						if dx * dx + dy * dy <= rr * rr then Consider(w, i, true, math.huge) break end
					end
				end
			end
		end
	end
	if wantP then
		for ty = floor(-(cam.y + R) / TILE), floor(-(cam.y - R) / TILE) do
			for tx = floor((cam.x - R) / TILE), floor((cam.x + R) / TILE) do
				local t = Tile(map, tx, ty)
				if t then
					-- nearest the tile gets to the camera across the ground: a placement too small even there ends the tile
					local nx, ny = min(max(cx, tx * TILE), (tx + 1) * TILE), min(max(cy, -(ty + 1) * TILE), -ty * TILE)
					local dmin = max(1, sqrt((nx - cx) ^ 2 + (ny - cy) ^ 2))
					for i = 1, t.n do
						if t.size[i] * F / dmin < minPx then break end
						if not pal.wmo[t.mi[i]] then Consider(t, i, false, R) end
					end
				end
			end
		end
	end
	for i = #order, n + 1, -1 do order[i] = nil end
	table.sort(order, ByScore)
	-- keep the chosen ones that already have an actor; list the others
	M.stamp = M.stamp + 1
	local stamp, nNeed, props, wmos = M.stamp, 0, 0, 0
	local tilted = cam.pitch < 80
	for k = 1, n do
		local c = order[k]
		local t, i, wmo = candSrc[c], candIdx[c], candWmo[c]
		local take = wmo
		if not wmo and props < count then
			take = not (tilted and Occluded(t.x[i], t.y[i], t.cz[i] + t.size[i], cx, cy, cz, map))
		end
		if take then
			if wmo then wmos = wmos + 1 else props = props + 1 end
			local e = M.byId[t.id[i]]
			if e then e.stamp = stamp else nNeed = nNeed + 1; need[nNeed] = c end
		end
	end
	-- actors not chosen again are free; one already showing the right model is reused first
	local free, freeAny = {}, {}
	for _, e in ipairs(M.pool) do
		if e.stamp ~= stamp then
			Release(e)
			e.taken = false
			if e.fdid then
				local l = free[e.fdid]
				if not l then l = {}; free[e.fdid] = l end
				l[#l + 1] = e
			end
			freeAny[#freeAny + 1] = e
		else
			e.taken = true
		end
	end
	local swaps, later = 0, 0
	local left = {}
	for k = 1, nNeed do
		local c = need[k]
		local t, i = candSrc[c], candIdx[c]
		local l = free[pal.fdid[t.mi[i]]]
		local e = l and l[#l]
		if e then l[#l] = nil; e.taken = true; Place(e, t, i, pal, now) else left[#left + 1] = c end
	end
	local fi = 1
	for _, c in ipairs(left) do
		if swaps >= SWAP_LIMIT then later = later + 1 else
			local e
			while fi <= #freeAny and freeAny[fi].taken do fi = fi + 1 end
			if fi <= #freeAny then e = freeAny[fi]; fi = fi + 1 else e = NewEntry() end
			if not e then later = later + 1 else
				e.taken = true
				local t, i = candSrc[c], candIdx[c]
				Place(e, t, i, pal, now)
				swaps = swaps + 1
			end
		end
	end
	if later > 0 then M.pending = true end
	M.badWmo = badWmo
	Holes()
	M.inRange, M.shownWmo, M.shown = n, wmos, wmos + props - later
	-- the simplified blocks give way inside Model distance once the game's buildings are known to load
	M.coverOn = showB and M.wmo == "yes"
	M.coverMap, M.coverX, M.coverY, M.coverR = map, cam.x, cam.y, R
	-- the buildings around the view the game is not drawing (further off than Model distance plus their
	-- radius): beyond Model distance, the simplified shapes they stand on stay even under a big building the
	-- game draws (ModelsCover; a big building's footprint is a circle of its radius round its origin, and
	-- Stormwind's, 853 yd, reaches Goldshire's farms)
	local undrawn = {}
	if M.coverOn then
		local w = WmoList(map)
		for i = 1, w.n do
			local r = pal.radius[w.mi[i]] * w.sc[i]
			local ox, oy, lim = w.x[i] - cam.x, w.y[i] - cam.y, UNDRAWN_REACH + r
			local d2 = ox * ox + oy * oy
			-- (left out for being too far; one left out for being tiny on screen or out of view goes, as inside Model distance)
			if d2 < lim * lim and d2 > (R + r) * (R + r) and not M.byId[w.id[i]] then
				-- (one on a big building was considered with it, and left out only for being tiny or out of view)
				local onBig = false
				for b = 1, nb do
					local dx, dy, rr = w.x[i] - bigX[b], w.y[i] - bigY[b], bigR[b] + r
					if dx * dx + dy * dy <= rr * rr then onBig = true break end
				end
				if not onBig then undrawn[#undrawn + 1] = { w.x[i], w.y[i], r } end
			end
		end
	end
	M.undrawn = undrawn
	local ms = debugprofilestop() - t0
	local p = M.perf
	p.picks, p.ms, p.cands = p.picks + 1, p.ms + ms, p.cands + n
	if ms > p.worst then p.worst = ms end
end
ns.SelectModels = Select

-- Where the simplified shapes must stay inside the model distance: buildings chosen but not loaded
-- (yet, or ever) and buildings that never load (left out of the choice): footprints { x, y, radius }.
-- And the footprints of the buildings the game is drawing (loaded): beyond the model distance the
-- simplified shapes under them give way too (M.drawn, ModelsCover).
Holes = function()
	local holes, drawn = {}, {}
	for _, e in ipairs(M.pool) do
		if e.id and e.wmo then
			if not e.loaded or e.failed then holes[#holes + 1] = { e.x, e.y, e.r } else drawn[#drawn + 1] = { e.x, e.y, e.r } end
		end
	end
	for _, h in ipairs(M.badWmo or {}) do holes[#holes + 1] = h end
	M.holes, M.drawn = holes, drawn
end

-- Loading states: what has loaded, what failed; the building check's answer.
local function Poll(now)
	local loading, failed, wmoLoaded, wmoBox = 0, 0, 0, nil
	for _, e in ipairs(M.pool) do
		if e.id then
			if not e.loaded then
				if e.actor:IsLoaded() then
					e.loaded = true
				elseif now - (e.since or now) > LOAD_WAIT then
					if not e.failed then e.failed = true; M.bad[e.fdid] = true; GPS.Log("MODELS", "model %s (%s) not loaded after %d s", tostring(e.fdid), e.wmo and "building" or "prop", LOAD_WAIT) end
				end
			end
			if e.failed then failed = failed + 1 elseif not e.loaded then loading = loading + 1 end
			if e.wmo and e.loaded and not wmoBox then
				local bx, by, bz = Box(e.actor)
				if bx and bx > 0.5 and by > 0.5 and bz > 0.5 then wmoLoaded, wmoBox = e.fdid, ("%.0f x %.0f x %.0f"):format(bx, by, bz) end
			end
		end
	end
	M.loading, M.failed = loading, failed
	Holes()
	if M.wmo == "testing" then
		if wmoBox then
			SetWmo("yes", ("building %s loaded, box %s"):format(tostring(wmoLoaded), wmoBox))
		elseif M.wmoSets > 0 and M.wmoSetOK == 0 then
			SetWmo("no", ("SetModelByFileID refused all %d buildings"):format(M.wmoSets))
		elseif M.wmoSets > 0 and now - M.wmoSince > WMO_WAIT then
			SetWmo("no", ("none of %d buildings loaded within %d s"):format(M.wmoSets, WMO_WAIT))
		end
	end
end

-- Called by Render every frame: only notes whether the view changed enough to choose again.
ns.UpdateModels = function()
	local s, cam = M.sel, ns.cam
	if M.dirty or not s then M.dirty = true return end
	if s.map ~= cam.map or s.version ~= M.version then M.dirty = true return end
	local R = Get("modelRange")
	if abs(cam.x - s.x) + abs(cam.y - s.y) > R * 0.04 or abs(cam.dist - s.dist) > s.dist * 0.05
		or abs((cam.yaw - s.yaw + 180) % 360 - 180) > 2 or abs(cam.pitch - s.pitch) > 2 then
		M.dirty = true
		return
	end
	local w, h = ns.canvas:GetSize()
	if w ~= s.w or h ~= s.h then M.dirty = true end
end

local driver = CreateFrame("Frame", nil, ns.frame)
driver:SetScript("OnUpdate", function()
	local now = GetTime()
	if (M.dirty or M.pending) and now - M.last >= SELECT_GAP then Select() end
	if now - M.poll >= POLL_GAP then M.poll = now; Poll(now) end
end)

-- Is a building block (x0 west edge, y1 north edge) inside the area where the game's buildings are
-- drawn instead? The whole block within Model distance of the middle of the last choice, or (since
-- 2026-10-19) its middle under a building the game is drawing and no building it is not drawing on it: a building is chosen out to Model
-- distance plus its own radius, so a big one (Nordrassil on Mount Hyjal: 559 yd across the ground,
-- 1,207 yd tall) was drawn by the game and as simplified shapes where it reached past Model distance.
-- Never where a building that is not drawn (loading, or never loads) stands.
ns.ModelsCover = function(x0, y1)
	if not M.coverOn or M.coverMap ~= ns.cam.map then return false end
	local B = ns.BLOCK
	for _, h in ipairs(M.holes or {}) do
		local nx, ny = min(max(h[1], x0), x0 + B), min(max(h[2], y1 - B), y1)
		if (nx - h[1]) ^ 2 + (ny - h[2]) ^ 2 <= h[3] * h[3] then return false end
	end
	local ex, ey = max(abs(x0 - M.coverX), abs(x0 + B - M.coverX)), max(abs(y1 - M.coverY), abs(y1 - B - M.coverY))
	if ex * ex + ey * ey <= M.coverR * M.coverR then return true end
	local mx, my = x0 + B / 2, y1 - B / 2
	for _, d in ipairs(M.drawn or {}) do
		if (mx - d[1]) ^ 2 + (my - d[2]) ^ 2 <= d[3] * d[3] then
			-- unless a building the game is not drawing stands on the block too
			for _, u in ipairs(M.undrawn or {}) do
				local nx, ny = min(max(u[1], x0), x0 + B), min(max(u[2], y1 - B), y1)
				if (nx - u[1]) ^ 2 + (ny - u[2]) ^ 2 <= u[3] * u[3] then return false end
			end
			return true
		end
	end
	return false
end

------------------------------------------------------------------------------------------------
-- Debug log and self-test
------------------------------------------------------------------------------------------------
local function WmoWords()
	if not BuildingsWanted() then return "simplified shapes (chosen)" end
	if M.wmo == "yes" then return "the game's (WMOs load)" end
	if M.wmo == "no" then return "simplified shapes (the game does not load WMOs here)" end
	if M.wmo == "testing" then return "checking whether the game loads WMOs" end
	return "the game's when they load (not checked yet)"
end

ns.ModelsState = function()
	local db = ns.DB()
	return ("models: buildings %s, caves and mines %s; props and trees %s (at most %d); distance %d yd, smallest %d px; %d shown (%d buildings), %d loading, %d failed, %d actors%s"):format(
		WmoWords(), Get("caves") and "on" or "off", PropsWanted() and "on" or "off", Get("modelCount"), Get("modelRange"), Get("modelPx"), M.shown, M.shownWmo, M.loading, M.failed, #M.pool,
		((db.modelTurn or 0) ~= 0 or (db.modelTilt or "normal") ~= "normal") and (", turned %s degrees, tilt %s"):format(tostring(db.modelTurn or 0), db.modelTilt or "normal") or "")
end

ns.TakeModelsPerf = function()
	local p = M.perf
	M.perf = { picks = 0, ms = 0, worst = 0, cands = 0, swaps = 0 }
	if p.picks == 0 and M.shown == 0 then return nil end
	return ("models: %d shown (%d buildings, %d props), %d loading, %d failed, %d actors; %d choices, %.2f ms average, %.2f ms worst, %d candidates average; %d model loads"):format(
		M.shown, M.shownWmo, M.shown - M.shownWmo, M.loading, M.failed, #M.pool, p.picks, p.picks > 0 and p.ms / p.picks or 0, p.worst, p.picks > 0 and floor(p.cands / p.picks + 0.5) or 0, p.swaps)
end

local probes = {}
ns.ModelsSelfTest = function(Report)
	local t0 = debugprofilestop()
	local maps, nTile, nPlace, nModels, nCaves = 0, 0, 0, 0, 0
	for map, m in pairs(ns.Models or {}) do
		maps = maps + 1
		local p = Palette(map)
		nModels = nModels + (p and p.n or 0)
		for i = 0, (p and p.n or 0) - 1 do if p.cave[i] then nCaves = nCaves + 1 end end
		for _, s in pairs(m) do nTile = nTile + 1; nPlace = nPlace + Num(s, 3, 3) end
	end
	Report("models data: %d maps, %d tiles, %d placements of %d models (%d of them caves and mines) (counted in %.0f ms)", maps, nTile, nPlace, nModels, nCaves, debugprofilestop() - t0)
	Report("%s", ns.ModelsState())
	-- probes: the biggest building and the biggest prop near the middle of the view (else the Elwynn
	-- farmhouse and an Elwynn tree), at the middle of the view
	local cam = ns.cam
	local wmoId, m2Id
	for dy = -1, 1 do
		for dx = -1, 1 do
			local t = Tile(cam.map, floor(cam.x / TILE) + dx, floor(-cam.y / TILE) + dy)
			local pal = t and Palette(cam.map)
			if t then
				for i = 1, t.n do
					local mi = t.mi[i]
					if pal.wmo[mi] then wmoId = wmoId or pal.fdid[mi] else m2Id = m2Id or pal.fdid[mi] end
					if wmoId and m2Id then break end
				end
			end
		end
	end
	wmoId, m2Id = wmoId or WMO_PROBE, m2Id or M2_PROBE
	local h = ns.GroundHeight(cam.x, cam.y)
	for k, id in ipairs({ wmoId, m2Id }) do
		local e = probes[k]
		if not e then
			local actor = ns.NewActor()
			e = actor and { actor = actor }
			probes[k] = e
		end
		if e then
			e.fdid, e.set = id, e.actor:SetModelByFileID(id)
			e.actor:SetPosition(cam.x, cam.y, h)
			e.actor:SetScale(1)
			e.actor:Show()
		end
	end
end

ns.ModelsSelfTestLate = function(Report)
	for k, e in ipairs(probes) do
		local bx, by, bz = Box(e.actor)
		Report("models: %s probe fileID %s: set=%s loaded=%s box %s", k == 1 and "building (WMO)" or "prop (M2)", tostring(e.fdid), tostring(e.set), tostring((e.actor:IsLoaded())),
			bx and ("%.1f x %.1f x %.1f yd"):format(bx, by, bz) or "none")
		e.actor:ClearModel()
		e.actor:Hide()
	end
	Report("%s", ns.ModelsState())
end

------------------------------------------------------------------------------------------------
-- Settings (GPS's page shows GPS3D_API.settings) and /gps3d models
------------------------------------------------------------------------------------------------
local function Set(key, v)
	ns.DB()[key] = v
	ns.ModelsChanged()
end

local CONTROLS = {
	{
		kind = "choice", key = "GPS3D_BuildingModels", name = "Buildings close up",
		tooltip = "GPS's simplified shapes (the default), or the game's own building models within the model distance, where the game lets an addon draw them (checked once per game version; GPS3D says in chat what it found). Trying the game's models crashed the game once (Forever, October 2026): save your work first. Further away, buildings are always the simplified shapes (/gps3d models buildings).",
		default = ns.modelDefaults.buildingModels,
		choices = function() return { { "simple", "Simplified shapes" }, { "game", "The game's models (may crash the game)" } } end,
		get = function() return GPS3D_DB and GPS3D_DB.buildingModels end,
		set = function(v) Set("buildingModels", v) end,
	},
	{
		kind = "check", key = "GPS3D_Props", name = "Props and trees",
		tooltip = "The game's own models of trees, rocks, fences, lamps, carts and the like, where they stand in the world (/gps3d models props).",
		default = ns.modelDefaults.props,
		get = function() return GPS3D_DB and GPS3D_DB.props end,
		set = function(v) Set("props", v) end,
	},
	{
		kind = "slider", key = "GPS3D_ModelCount", name = "Props and trees at most",
		tooltip = "How many props and trees are drawn at once, the biggest on screen first. Lower is faster (/gps3d models count).",
		default = ns.modelDefaults.modelCount, min = 50, max = 1500, step = 50,
		format = function(v) return ("%d"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.modelCount end,
		set = function(v) Set("modelCount", v) end,
	},
	{
		kind = "slider", key = "GPS3D_ModelRange", name = "Model distance",
		tooltip = "How far from the middle of the view the game's models are drawn, in yards (/gps3d models range).",
		default = ns.modelDefaults.modelRange, min = 200, max = 2000, step = 100,
		format = function(v) return ("%d yd"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.modelRange end,
		set = function(v) Set("modelRange", v) end,
	},
	{
		kind = "slider", key = "GPS3D_ModelPx", name = "Smallest model",
		tooltip = "Models smaller than this on screen (pixels) are left out. Higher is faster (/gps3d models px).",
		default = ns.modelDefaults.modelPx, min = 2, max = 40, step = 1,
		format = function(v) return ("%d px"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.modelPx end,
		set = function(v) Set("modelPx", v) end,
	},
}
do -- after "Building detail" on the 3D view's part of the settings page
	local list, at = GPS3D_API.settings, nil
	for i, d in ipairs(list) do if d.key == "GPS3D_BuildingBudget" then at = i + 1 end end
	at = at or #list + 1
	for k, d in ipairs(CONTROLS) do table.insert(list, at + k - 1, d) end
end

-- /gps3d models                       what is shown (and the settings)
-- /gps3d models buildings game|simple the game's buildings close up, or the simplified shapes
-- /gps3d models props on|off          props and trees
-- /gps3d models caves on|off          caves and mines among the game's buildings (on by default)
-- /gps3d models count <n>             props and trees at most
-- /gps3d models range <yd>            how far from the middle of the view
-- /gps3d models px <n>                smallest model on screen
-- /gps3d models wmo                   check again whether the game draws buildings (WMOs)
-- /gps3d models turn <deg>            turn every model by this much (only if they all face the wrong way in game)
-- /gps3d models tilt normal|flip|off  how leaning models lean: as exported, the other way, or upright
local slash = SlashCmdList.GPS3D
SlashCmdList.GPS3D = function(msg)
	local cmd, rest = strtrim(msg or ""):match("^(%S*)%s*(.-)$")
	if cmd:lower() ~= "models" then return slash(msg) end
	GPS.Log("SLASH", "/gps3d %s", msg or "")
	local what, arg = rest:match("^(%S*)%s*(.-)$")
	what = what:lower()
	local n = tonumber(arg)
	if what == "buildings" and (arg == "game" or arg == "simple") then
		Set("buildingModels", arg)
		if arg == "game" then print("|cff55ff55GPS3D|r: trying the game's own buildings. This crashed the game once (Forever, October 2026); /gps3d models buildings simple goes back.") end
	elseif what == "props" and (arg == "on" or arg == "off") then Set("props", arg == "on")
	elseif what == "caves" and (arg == "on" or arg == "off") then Set("caves", arg == "on")
	elseif what == "count" and n then Set("modelCount", max(0, floor(n)))
	elseif what == "range" and n then Set("modelRange", max(50, floor(n)))
	elseif what == "px" and n then Set("modelPx", max(1, n))
	elseif what == "turn" and n then
		ns.DB().modelTurn = n
		for _, e in ipairs(M.pool) do Release(e) end -- placed again with the new turn
		ns.ModelsChanged()
	elseif what == "tilt" and (arg == "normal" or arg == "flip" or arg == "off") then
		ns.DB().modelTilt = arg
		for _, e in ipairs(M.pool) do Release(e) end
		ns.ModelsChanged()
	elseif what == "wmo" then
		local db = ns.DB()
		db.wmoCheck, db.wmoBuild, M.wmo = nil, nil, nil
		for _, e in ipairs(M.pool) do if e.wmo then e.fdid = nil; Release(e) end end -- load them again
		ns.ModelsChanged()
	end
	print("|cff55ff55GPS3D|r " .. ns.ModelsState())
end
