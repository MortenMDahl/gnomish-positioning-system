-- GPS 3D: the building and model data, loaded when the 3D view first needs them (since 2026-10-22, perf round A5).
--
-- Until then every data file was in GPS3D.toc, so each login parsed 60 MB of Lua and kept it: 224 ms and 59.3 MB
-- of Lua heap in Lua 5.1 (the game's Lua, measured on the shipped data), whether the 3D view was opened or not;
-- the buildings were 46.7 MB of it, the game's models 8 MB. Now they are load-on-demand addons next to GPS3D
-- (C_AddOns.LoadAddOn; written by scripts/build_detail.py and scripts/build_models.py), and only the terrain
-- (World_*, Lod_*), the planet and the index of the buildings (Data/DetailParts.lua) load at login: 24 ms, 4.8 MB.
--   GPS3D_EK1 ... GPS3D_EK4        the Eastern Kingdoms' buildings, in four bands of tile rows north to south
--   GPS3D_Kalimdor1 ... 3          Kalimdor's, in three
--   GPS3D_Instances                the dungeons', raids' and battlegrounds' (13 maps, 9.9 MB)
--   GPS3D_Models                   where the game's props, trees and buildings stand (Models.lua), every map
-- Each costs one hitch the first time it is needed in a session (Lua 5.1: 8-22 ms per band, 35 ms the
-- instances, 28 ms the models; one folder per continent would be 60-73 ms; see
-- testing/2026-10-22-perf-round/GATES-A5.md). A band is loaded when the view's centre comes within a tile
-- (533 yd) of the reach where blocks are drawn (DETAIL_RANGE round the view's centre, the camera at most
-- DETAIL_DIST away), so the hitch comes a tile before its buildings can show; and at once when anything reads
-- buildings that are not in memory (GPS3D.lua's TileBlocks asks ns.DetailFor: the view put somewhere new, your
-- height), so whatever reads them gets what it got with everything loaded at login. The models load the first
-- time they are wanted (props and trees on, or the game's buildings chosen): never with the default settings.
-- Drawn: exactly what was drawn with everything loaded at login (tools/sandbox/test_ondemand.py compares the
-- whole draw state, every texture and model actor).
--
-- In combat nothing is loaded (a hitch in a fight, and whether the game allows it then is not known): the view
-- draws the ground without those buildings until combat ends, then loads. A data addon the game will not load
-- (folder not copied, disabled, out of date) is said once in chat and not asked for again this session;
-- /gps3d test lists every data addon's state and what each load cost.
--
-- A data addon's files get the addon's own namespace from the game; its first file (Link.lua) hands that to
-- GPS3D_API.LinkData, which makes what they write land in GPS3D's namespace, as when GPS3D.toc listed them.
local _, ns = ...
local GPS = GPS_API
local floor, min, max = math.floor, math.min, math.max
local TILE = ns.TILE
local MODELS = "GPS3D_Models"
local RECHECK = 50 -- yards the view's centre moves before the bands within reach are looked up again

-- state: name -> nil (not asked for), "loaded", "combat" (waits for combat to end), "failed" (with reason)
local D = { state = {}, reason = {}, ms = {}, why = {}, names = {}, map = nil, x = 0, y = 0, dirty = true, calls = 0 }
ns.dataState = D

GPS3D_API.LinkData = function(dataNs)
	setmetatable(dataNs, { __index = ns, __newindex = ns })
end

-- every data addon, in a fixed order (the continents' bands first, as the index lists them), for /gps3d test
do
	local maps, seen = {}, {}
	for map in pairs(ns.DetailParts or {}) do maps[#maps + 1] = map end
	table.sort(maps)
	for _, map in ipairs(maps) do
		for _, name in ipairs(ns.DetailParts[map]) do
			if not seen[name] then seen[name] = true; D.names[#D.names + 1] = name end
		end
	end
	D.names[#D.names + 1] = MODELS
end

local function Load(name, why)
	local st = D.state[name]
	if st == "loaded" then return true end
	if st == "failed" then return false end
	if C_AddOns.IsAddOnLoaded(name) then D.state[name] = "loaded"; return true end
	if InCombatLockdown() then
		if st ~= "combat" then GPS.Log("PERF", "3D data %s wanted for %s: waits for combat to end", name, why) end
		D.state[name] = "combat"
		return false
	end
	local t0 = debugprofilestop()
	D.calls = D.calls + 1
	local ok, reason = C_AddOns.LoadAddOn(name)
	local ms = debugprofilestop() - t0
	if ok then
		D.state[name], D.ms[name], D.why[name] = "loaded", ms, why
		GPS.Log("PERF", "3D data %s loaded for %s in %.0f ms", name, why, ms)
		return true
	end
	D.state[name], D.reason[name] = "failed", tostring(reason or "?")
	GPS.Log("PERF", "3D data %s not loaded (%s), wanted for %s", name, D.reason[name], why)
	print(("|cff55ff55GPS3D|r: could not load %s (%s), so %s are not drawn. Copy every GPS3D folder (GPS3D, GPS3D_EK1 ... GPS3D_Models) into Interface\\AddOns, then /reload."):format(name, D.reason[name], why))
	return false
end

-- Called by Render before each frame of the world (not the planet): loads what the view is about to need.
-- Makes no tables; when the view's centre has moved less than RECHECK yards it only compares numbers.
ns.WantData = function()
	local cam = ns.cam
	if D.state[MODELS] ~= "loaded" and ns.ModelsWanted and ns.ModelsWanted() then
		if Load(MODELS, "the game's models") and ns.ModelDataArrived then ns.ModelDataArrived() end
	end
	local map = cam.map
	local parts = ns.DetailParts and ns.DetailParts[map]
	if not parts or (GPS3D_DB and GPS3D_DB.detail == false) or cam.dist > ns.DETAIL_DIST + TILE then
		D.dirty = true -- (looked up again as soon as buildings can be drawn)
		return
	end
	local cx, cy = cam.x, cam.y
	if not D.dirty and map == D.map and math.abs(cx - D.x) + math.abs(cy - D.y) < RECHECK then return end
	D.map, D.x, D.y, D.dirty = map, cx, cy, false
	local R = ns.DETAIL_RANGE + TILE
	local tiles, got = parts.tiles, false
	for ty = max(0, floor(-(cy + R) / TILE)), min(63, floor(-(cy - R) / TILE)) do
		for tx = max(0, floor((cx - R) / TILE)), min(63, floor((cx + R) / TILE)) do
			local p = tiles[ty * 64 + tx]
			local name = p and parts[p]
			if name and D.state[name] ~= "loaded" then
				local nx = min(max(cx, tx * TILE), (tx + 1) * TILE) -- the tile's nearest point to the view's centre
				local ny = min(max(cy, -(ty + 1) * TILE), -ty * TILE)
				if (nx - cx) * (nx - cx) + (ny - cy) * (ny - cy) < R * R and Load(name, "buildings") then got = true end
			end
		end
	end
	if got then ns.DataArrived() end
end

-- Called by GPS3D.lua's TileBlocks when a tile's buildings are asked for and not in memory (the view put
-- somewhere new: opened, another map, a flight; the height under you or under the camera): its data addon is
-- loaded at once, so whatever reads them gets what it got with everything loaded at login. True when they are
-- there now.
ns.DetailFor = function(map, key)
	local parts = ns.DetailParts and ns.DetailParts[map]
	local p = parts and parts.tiles[key]
	local name = p and parts[p]
	if not name or D.state[name] == "loaded" or (GPS3D_DB and GPS3D_DB.detail == false) then return false end
	if Load(name, "buildings") then ns.DataArrived() return true end
	return false
end

-- combat over: what waited for it is asked for again with the next frame
local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_REGEN_ENABLED")
events:SetScript("OnEvent", function()
	local waited = false
	for name, st in pairs(D.state) do
		if st == "combat" then D.state[name] = nil; waited = true end
	end
	if waited then D.dirty = true; ns.Redraw() end
end)

-- /gps3d test: each data addon's state, and what its load cost
ns.DataSelfTest = function(Report)
	local parts, missing = {}, {}
	for _, name in ipairs(D.names) do
		local st = D.state[name]
		local short = name:gsub("^GPS3D_", "")
		if st == "loaded" then
			parts[#parts + 1] = D.ms[name] and ("%s loaded (%.0f ms)"):format(short, D.ms[name]) or (short .. " loaded")
		elseif st == "combat" then
			parts[#parts + 1] = short .. " waits for combat to end"
		elseif st == "failed" then
			parts[#parts + 1] = ("%s NOT LOADED (%s)"):format(short, D.reason[name])
			missing[#missing + 1] = name
		elseif name == MODELS then
			parts[#parts + 1] = short .. " not needed (props and trees off, buildings simplified)"
		else
			parts[#parts + 1] = short .. " not needed yet"
		end
	end
	Report("data on demand (buildings within a tile of the view, models when switched on; never in combat%s): %s",
		InCombatLockdown() and ", which you are in now" or "", table.concat(parts, ", "))
	if #missing > 0 then
		Report("data missing: %s; copy every GPS3D folder into Interface\\AddOns and /reload (until then the view draws without them)", table.concat(missing, ", "))
	end
end
