-- Gnomish Positioning System: your quests on the 2D map and in the 3D view (the traditional map
-- shows them with Blizzard's own quest layers, MapWindow.lua).
--
-- Markers: every quest in your log that the game gives a point on a zone of the map shown
-- (C_QuestLog.GetQuestsOnMap per zone), at that point's world position (C_Map.GetWorldPosFromMapPos,
-- the same conversion as the traditional map's focus), drawn with Blizzard's quest button
-- (POIButtonTemplate, as in the objective tracker): click tracks the quest, as on Blizzard's map.
-- Objective areas (2D): the tracked quest's area, and the hovered marker's, drawn by the game's
-- quest-area frame (QuestPOIFrame, the frame Blizzard's map uses) set to the quest's zone and laid
-- exactly over that zone's rectangle on the 2D map: a zone's map coordinates and GPS's 2D map are
-- both straight-line projections of the world, so the area lands where Blizzard draws it.
-- The 3D view draws the same markers (GPS3D, through GPS_API) and the same areas, whose shape is
-- learned here from the quest-area frame's hit-test (Q.AreaShapes, below) and drawn on the ground
-- by GPS3D's QuestAreas.lua.
local addonName, ns = ...

local Q = {}
ns.quests = Q

local MAPTYPE_CONTINENT = Enum and Enum.UIMapType and Enum.UIMapType.Continent or 2
local MAPTYPE_ZONE = Enum and Enum.UIMapType and Enum.UIMapType.Zone or 3
local REFRESH_DELAY = 0.25 -- quest events come in bursts: the list is rebuilt once they settle
local BLOB_FILL, BLOB_BORDER = "Interface\\WorldMap\\UI-QuestBlob-Inside", "Interface\\WorldMap\\UI-QuestBlob-Outside"
local EMPTY = {}

local cache = { instance = nil, list = {}, dirty = true, stamp = 0 }
local zonesOf = {}   -- instance -> { uiMapID, ... } (the zones of that GPS map; they do not change)
local zoneRect = {}  -- uiMapID -> { gx0, gy0, gx1, gy1 } (its top-left and bottom-right on the grid)
Q.cache, Q.zonesOf = cache, zonesOf

-- Shown at all: the setting (Options > AddOns), Blizzard's "quest objectives on the map" option
-- (cvar questPOI), and the game functions this needs.
function Q.Enabled()
	if ns.db and ns.db.quests == false then return false end
	if GetCVarBool and GetCVarBool("questPOI") == false then return false end
	return C_QuestLog ~= nil and C_QuestLog.GetQuestsOnMap ~= nil and C_Map ~= nil and C_Map.GetWorldPosFromMapPos ~= nil and CreateVector2D ~= nil
end

-- A point of a uiMap (x, y from 0 to 1) on GPS's grid: the GPS map (instance) it is on, gx, gy.
function Q.ToGrid(uiMap, x, y)
	local continent, world = C_Map.GetWorldPosFromMapPos(uiMap, CreateVector2D(x, y))
	if not (continent and world) then return nil end
	local wx, wy = world:GetXY()
	local gx, gy = ns.WorldToGrid(wx, wy)
	return continent, gx, gy
end

-- The zones of a GPS map: the uiMap at a point on it, up to its continent (or the highest map of
-- that instance), then every zone under that map which lies on this instance.
local function UiMapAt(instance, gx, gy)
	if not (gx and C_Map.GetMapPosFromWorldPos) then return nil end
	local X, Y = ns.GridToWorld(gx, gy)
	return (C_Map.GetMapPosFromWorldPos(instance, CreateVector2D(X, Y)))
end
local function ZonesOn(instance)
	if zonesOf[instance] then return zonesOf[instance] end
	local m = GPS_API.Maps[instance]
	local ui = UiMapAt(instance, ns.view and ns.view.map == instance and ns.view.cx, ns.view and ns.view.cy)
	if not ui and m and m.fitMinX then ui = UiMapAt(instance, (m.fitMinX + m.fitMaxX + 1) / 2, (m.fitMinY + m.fitMaxY + 1) / 2) end
	if not ui then
		local pm, pgx, pgy = ns.PlayerPosition()
		if pm == instance then ui = UiMapAt(instance, pgx, pgy) end
	end
	if not ui then ns.Log("QUEST", "map %s: no zone map found at the points tried", tostring(instance)) return EMPTY end -- not cached: a later call may find a point on land
	local root, info = ui, C_Map.GetMapInfo(ui)
	while info and info.mapType ~= MAPTYPE_CONTINENT and info.parentMapID and info.parentMapID > 0 do
		local parent = C_Map.GetMapInfo(info.parentMapID)
		if not parent or (parent.mapType or 0) < MAPTYPE_CONTINENT then break end
		if Q.ToGrid(info.parentMapID, 0.5, 0.5) ~= instance then break end
		root, info = info.parentMapID, parent
	end
	local zones = {}
	local candidates = { { mapID = root, mapType = info and info.mapType } }
	for _, child in ipairs(C_Map.GetMapChildrenInfo and C_Map.GetMapChildrenInfo(root, nil, true) or EMPTY) do candidates[#candidates + 1] = child end
	for _, c in ipairs(candidates) do
		if c.mapType == MAPTYPE_ZONE and Q.ToGrid(c.mapID, 0.5, 0.5) == instance then zones[#zones + 1] = c.mapID end
	end
	zonesOf[instance] = zones
	ns.Log("QUEST", "map %s: %d zones under uiMap %s (found from uiMap %s)", tostring(instance), #zones, tostring(root), tostring(ui))
	return zones
end
Q.ZonesOn = ZonesOn

local function Rebuild(instance)
	local list = {}
	local seen = {}
	local tracked = C_SuperTrack and C_SuperTrack.GetSuperTrackedQuestID and C_SuperTrack.GetSuperTrackedQuestID()
	for _, zone in ipairs(ZonesOn(instance)) do
		for _, info in ipairs(C_QuestLog.GetQuestsOnMap(zone) or EMPTY) do
			local id = info.questID
			if id and not seen[id] then
				local on, gx, gy = Q.ToGrid(zone, info.x, info.y)
				if on == instance then
					seen[id] = true
					list[#list + 1] = { questID = id, zone = zone, x = info.x, y = info.y, gx = gx, gy = gy, tracked = id == tracked }
				end
			end
		end
	end
	-- the tracked quest last, so it is drawn on top
	table.sort(list, function(a, b) if a.tracked ~= b.tracked then return b.tracked end return a.questID < b.questID end)
	cache.instance, cache.list, cache.dirty = instance, list, false
	cache.stamp = cache.stamp + 1
	if ns.debugOn then
		local ids = {}
		for _, q in ipairs(list) do ids[#ids + 1] = q.questID .. (q.tracked and "*" or "") .. "@" .. q.zone end
		ns.Log("QUEST", "map %s: %d quests with a point (* tracked): %s", tostring(instance), #list, table.concat(ids, " "))
	end
end

-- Your quests on a GPS map: { questID, zone, x, y, gx, gy, tracked }, the tracked one last.
function Q.List(instance)
	if not (instance and Q.Enabled()) then return EMPTY end
	if cache.dirty or cache.instance ~= instance then Rebuild(instance) end
	return cache.list
end
function Q.Stamp() return cache.stamp end

-- The quests whose objective area is drawn: the tracked one and the hovered marker's.
function Q.AreaQuests(instance)
	local out = {}
	for _, q in ipairs(Q.List(instance)) do
		if q.tracked or q.questID == Q.hovered then out[#out + 1] = q end
	end
	return out
end

-- Something changed (quests, tracking, hover, the setting): redraw the windows that show quests.
function Q.Changed(keepList)
	if not keepList then cache.dirty = true end
	if ns.frame and ns.frame:IsShown() and ns.LayoutQuests then ns.LayoutQuests() end
	if GPS3D_API and GPS3D_API.QuestsChanged then GPS3D_API.QuestsChanged() end
end

------------------------------------------------------------------------------------------------
-- Markers: Blizzard's quest button, shared with the 3D view
------------------------------------------------------------------------------------------------
local function PinEnter(self)
	local id = self.gpsQuestID
	if not id then return end
	GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
	GameTooltip:SetText(C_QuestLog.GetTitleForQuestID and C_QuestLog.GetTitleForQuestID(id) or ("Quest " .. id))
	local objectives = C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(id)
	local index = not objectives and C_QuestLog.GetLogIndexForQuestID and C_QuestLog.GetLogIndexForQuestID(id)
	for _, o in ipairs(objectives or EMPTY) do
		if o.text and not o.finished then GameTooltip:AddLine("- " .. o.text, 1, 1, 1, true) end
	end
	if index and GetNumQuestLeaderBoards and GetQuestLogLeaderBoard then
		for i = 1, GetNumQuestLeaderBoards(index) or 0 do
			local text, _, finished = GetQuestLogLeaderBoard(i, index)
			if text and not finished then GameTooltip:AddLine("- " .. text, 1, 1, 1, true) end
		end
	end
	GameTooltip:AddLine(self.gpsTracked and "Click: stop tracking" or "Click: track this quest", 0.5, 0.5, 0.5)
	GameTooltip:Show()
	Q.hovered, self.gpsHoverID = id, id
	if POIButtonHighlightManager and POIButtonHighlightManager.SetHighlight then POIButtonHighlightManager:SetHighlight(id) end
	Q.Changed(true)
end
local function PinLeave(self)
	if GameTooltip:GetOwner() == self then GameTooltip:Hide() end
	-- the quest hovered when the mouse came in: a click in between re-sorts the list, and this button
	-- may show another quest by now (the hovered area then stayed drawn, until 2026-10-21)
	local id = self.gpsHoverID
	self.gpsHoverID = nil
	if id and Q.hovered == id then
		Q.hovered = nil
		if POIButtonHighlightManager and POIButtonHighlightManager.ClearHighlight then POIButtonHighlightManager:ClearHighlight() end
		Q.Changed(true)
	end
end
local function FallbackClick(self)
	if not (C_SuperTrack and self.gpsQuestID) then return end
	if self.gpsTracked then C_SuperTrack.ClearAllSuperTracked() else C_SuperTrack.SetSuperTrackedQuestID(self.gpsQuestID) end
end

-- A marker button on `parent`: Blizzard's POIButtonTemplate (its click tracks the quest), or a plain
-- quest-mark button where that template is missing.
function Q.NewPin(parent)
	local ok, pin = pcall(CreateFrame, "Button", nil, parent, "POIButtonTemplate")
	if not (ok and pin and pin.SetQuestID) then
		pin = CreateFrame("Button", nil, parent)
		pin:SetSize(20, 20)
		pin:SetNormalAtlas("QuestNormal")
		pin:SetScript("OnClick", FallbackClick)
	end
	pin:SetScript("OnEnter", PinEnter)
	pin:SetScript("OnLeave", PinLeave)
	pin:HookScript("OnClick", function(self, button) ns.Log("QUEST", "marker %s clicked (%s); it was tracked: %s", tostring(self.gpsQuestID), tostring(button), tostring(self.gpsTracked)) end)
	return pin
end

-- Shows quest q on a marker, styled as Blizzard's map styles it (QuestDataProviderMixin.AddQuest).
function Q.SetupPin(pin, q)
	pin.gpsQuestID, pin.gpsTracked = q.questID, q.tracked
	if pin.SetQuestID then
		pin:SetQuestID(q.questID)
		pin:SetSelected(q.tracked)
		if POIButtonUtil and POIButtonUtil.GetStyle then pin:SetStyle(POIButtonUtil.GetStyle(q.questID)) end
		pin:UpdateButtonStyle()
		if pin.EvaluateManagedHighlight then pin:EvaluateManagedHighlight() end
	end
	pin:Show()
end

------------------------------------------------------------------------------------------------
-- The 2D map
------------------------------------------------------------------------------------------------
local canvas = ns.canvas
local areaLayer = CreateFrame("Frame", nil, canvas) -- objective areas: over the tiles, under markers and arrow
areaLayer:SetAllPoints()
areaLayer:SetFrameLevel(canvas:GetFrameLevel() + 5)
local pinLayer = CreateFrame("Frame", nil, canvas)  -- markers: under your arrow (level + 10)
pinLayer:SetAllPoints()
pinLayer:SetFrameLevel(canvas:GetFrameLevel() + 8)
local pins2D, areas2D = {}, {} -- marker buttons; zone -> quest-area frame
Q.pins2D, Q.areas2D = pins2D, areas2D
-- (the tracked quest's marker sits over the others)
function Q.SetupPin2D(pin, q)
	Q.SetupPin(pin, q)
	pin:SetFrameLevel(pinLayer:GetFrameLevel() + (q.tracked and 2 or 1))
end

-- A zone's rectangle on the grid, from its corners (0, 0) and (1, 1).
local function ZoneRect(zone)
	local r = zoneRect[zone]
	if r == nil then
		local _, gx0, gy0 = Q.ToGrid(zone, 0, 0)
		local _, gx1, gy1 = Q.ToGrid(zone, 1, 1)
		r = gx0 and gx1 and { gx0, gy0, gx1, gy1 } or false
		zoneRect[zone] = r
	end
	return r or nil
end
Q.ZoneRect = ZoneRect

-- The game's quest-area frame for a zone (nil where this client cannot make one).
local function AreaFrame(zone)
	local f = areas2D[zone]
	if f == nil then
		local ok, made = pcall(CreateFrame, "QuestPOIFrame", nil, areaLayer)
		f = ok and made and made.DrawBlob and made or false
		ns.Log("QUEST", "quest-area frame for zone %s: %s", tostring(zone), f and "made" or ("NOT made: " .. tostring(made)))
		if f then
			f:SetFillTexture(BLOB_FILL)
			f:SetBorderTexture(BLOB_BORDER)
			f:SetFillAlpha(128)
			f:SetBorderAlpha(192)
			f:SetBorderScalar(1.0)
			f:EnableMouse(false)
			f:SetMapID(zone)
			-- the area is laid out for the frame's size: drawn again after a size change (at the end of
			-- the frame, as Blizzard's map does)
			f:SetScript("OnSizeChanged", function(self) self.redraw = true end)
			f:SetScript("OnUpdate", function(self) if self.redraw then self.redraw = nil; Q.DrawAreas(self) end end)
		end
		areas2D[zone] = f
	end
	return f or nil
end
function Q.DrawAreas(f)
	ns.Log("QUEST", "areas drawn in zone %s: %s (frame %.0fx%.0f)", tostring(f:GetMapID()), table.concat(f.quests or EMPTY, ", "), f:GetWidth(), f:GetHeight())
	f:DrawNone()
	for _, id in ipairs(f.quests or EMPTY) do f:DrawBlob(id, true) end
end

function ns.LayoutQuests()
	local view = ns.view
	local list = ns.frame:IsShown() and Q.List(view.map) or EMPTY
	local stamp = cache.stamp
	-- markers
	for i, q in ipairs(list) do
		local px, py = ns.GridToScreen(q.gx, q.gy)
		ns.PlacePin(pins2D, i, q, stamp, Q.NewPin, Q.SetupPin2D, pinLayer, canvas, "TOPLEFT", px, -py)
	end
	ns.HidePins(pins2D, #list)
	-- objective areas: one frame per zone with an area to draw
	local want = {}
	for _, q in ipairs(list == EMPTY and EMPTY or Q.AreaQuests(view.map)) do
		want[q.zone] = want[q.zone] or {}
		table.insert(want[q.zone], q.questID)
	end
	for zone, f in pairs(areas2D) do
		if f and not want[zone] and f:IsShown() then f.quests, f.key = nil, nil; f:DrawNone(); f:Hide() end
	end
	for zone, ids in pairs(want) do
		local f, r = AreaFrame(zone), ZoneRect(zone)
		if f and r then
			local x0, y0 = ns.GridToScreen(r[1], r[2])
			local x1, y1 = ns.GridToScreen(r[3], r[4])
			f:ClearAllPoints()
			f:SetPoint("TOPLEFT", canvas, "TOPLEFT", x0, -y0)
			f:SetPoint("BOTTOMRIGHT", canvas, "TOPLEFT", x1, -y1)
			local key = table.concat(ids, ",")
			if key ~= f.key then f.quests, f.key = ids, key; Q.DrawAreas(f) end
			f:Show()
		end
	end
end

-- Quest events: the list is rebuilt once a burst of them has settled.
local pending
local function Later()
	pending = nil
	Q.Changed()
end
local events = CreateFrame("Frame")
for _, e in ipairs({ "QUEST_LOG_UPDATE", "QUEST_POI_UPDATE", "SUPER_TRACKING_CHANGED", "QUEST_WATCH_LIST_CHANGED", "QUEST_ACCEPTED", "QUEST_REMOVED", "CVAR_UPDATE" }) do
	pcall(events.RegisterEvent, events, e)
end
events:SetScript("OnEvent", function(_, event, name)
	if event == "CVAR_UPDATE" and name ~= "questPOI" then return end
	cache.dirty = true
	if not pending then
		pending = true
		C_Timer.After(REFRESH_DELAY, Later)
	end
end)

------------------------------------------------------------------------------------------------
-- Objective areas for the 3D view: the area's shape, learned from the game's quest-area frame.
--
-- What an addon can learn about an area (Forever's UI source, build 1.60.1.70425): no function returns
-- its outline (C_QuestLog has GetQuestsOnMap, GetNextWaypoint..., C_QuestPOI does not exist, and the
-- old QuestPOIGetIconInfo / blob-point calls are gone); the QuestPOIFrame widget only draws it
-- (FrameAPIBlob: SetMapID, DrawBlob, DrawNone, ...) and hit-tests it (FrameAPIQuestPOI:
-- UpdateMouseOverTooltip(x, y) -> questID, numObjectives, with x and y from 0 to 1 over the frame's
-- map; Blizzard's QuestBlobPinMixin:UpdateTooltip passes the map canvas's normalised cursor
-- position). So the shape is found by asking that hit-test which quest's area lies under points of a
-- grid: a frame of our own (never the 2D map's) set to the quest's zone with only that quest drawn.
-- The source cannot say whether the hit-test answers while the frame is not drawn, so three ways are
-- tried in turn until one finds an area, and the one that did is kept for the session: the frame
-- hidden; shown at alpha 0; shown behind the 3D view's ground (inside its window, under its opaque
-- background). A way that finds nothing for this quest is not proof (some quests have no area), so a
-- quest is only "without area" once every way has found nothing.
-- Search: 32 x 32 points over 2,000 yd round the quest's point (and the point itself), widened while
-- the area reaches the window's edge, the whole zone (48 x 48) if nothing is found; then a grid of at
-- most 24 cells (at least 6 yd) across the box round the hits plus one coarse cell, and each grid edge
-- whose ends differ bisected 3 times. Marching squares turns that into pieces of at most 4 corners (the
-- fill) and closed outlines (the border), in GPS grid coordinates. At most 400 hit-tests and 2 ms per
-- frame; redone after the quest log changes (the old shape stays drawn until the new one is ready).
------------------------------------------------------------------------------------------------
local AREA_REACH, AREA_COARSE, AREA_WHOLE, AREA_FINE, AREA_MIN_CELL, AREA_BISECT = 1000, 32, 48, 24, 6, 3
local AREA_CALLS, AREA_MS = 400, 2
local TILE_YD = 1600 / 3
local WAYS = { "hidden", "invisible", "behind" }
local WAY_TEXT = { hidden = "frame hidden", invisible = "frame shown at alpha 0", behind = "frame shown behind the 3D view's ground" }
local areaShapes, areaJobs, areaOut = {}, {}, {}
Q.areaShapes, Q.areaJobs, Q.WAY_TEXT = areaShapes, areaJobs, WAY_TEXT
Q.area = { way = nil, broken = nil, last = nil } -- the way that works, why none can, the last result (for /gps3d test)

-- The window that hides the "behind" way's frame (GPS3D's): frame level and size from it.
function Q.SetAreaHost(host, canvas) Q.areaHost, Q.areaHostCanvas = host, canvas end

-- Our own quest-area frame, set up for one way, zone and quest; nil (and Q.area.broken) when the game
-- has none or it has no hit-test.
local function Sampler(way, zone, questID)
	local f = Q.sampler
	if f == nil then
		local ok, made = pcall(CreateFrame, "QuestPOIFrame", nil, UIParent)
		if not (ok and made and made.DrawBlob and made.SetMapID) then
			Q.area.broken = "the game's quest-area frame (QuestPOIFrame) cannot be made here (" .. tostring(made) .. ")"
		elseif not made.UpdateMouseOverTooltip then
			Q.area.broken = "the quest-area frame has no hit-test (UpdateMouseOverTooltip)"
			made:Hide()
		else
			made:SetFillTexture(BLOB_FILL)
			made:SetBorderTexture(BLOB_BORDER)
			made:EnableMouse(false)
			f = made
		end
		Q.sampler = f or false
		if not f then ns.Log("QUEST", "3D areas: %s", Q.area.broken) return nil end
	end
	if not f then return nil end
	local host = way == "behind" and Q.areaHost
	local parent = host or UIParent
	if f:GetParent() ~= parent then f:SetParent(parent) end
	local r = ZoneRect(zone)
	local w, h = math.abs(r[3] - r[1]), math.abs(r[4] - r[2])
	local size = 512
	if host then
		local cw, ch = Q.areaHostCanvas:GetSize()
		size = math.max(16, math.min(size, (cw or 0) - 8, (ch or 0) - 8))
	end
	local k = size / math.max(w, h, 1e-6)
	f:ClearAllPoints()
	f:SetSize(math.max(1, w * k), math.max(1, h * k))
	f:SetPoint("CENTER", host and Q.areaHostCanvas or UIParent, "CENTER")
	if host then f:SetFrameStrata(host:GetFrameStrata()); f:SetFrameLevel(host:GetFrameLevel()) else f:SetFrameStrata("BACKGROUND") end
	f:SetAlpha(way == "behind" and 1 or 0)
	f:SetMapID(zone)
	f:DrawNone()
	f:DrawBlob(questID, true)
	if way == "hidden" then f:Hide() else f:Show() end
	return f
end

local function NextWay(job)
	local i = job.wayIndex + 1
	if Q.area.way then return nil end -- a known way found nothing: this quest has no area
	while WAYS[i] == "behind" and not Q.areaHost do i = i + 1 end
	return WAYS[i] and i or nil
end

-- Edge ids of a grid of nx x ny cells: across (i, j)-(i+1, j), then down (i, j)-(i, j+1).
local function EdgeH(job, i, j) return j * job.nx + i + 1 end
local function EdgeV(job, i, j) return job.nx * (job.ny + 1) + j * (job.nx + 1) + i + 1 end

-- Marching squares: pieces (p1..p4, a triangle repeats its last corner) and closed outlines (lv, from
-- ls[k] to le[k]), corners in GPS grid coordinates (gx, gy).
local function BuildShape(job)
	local nx, ny, inside, cross, r = job.nx, job.ny, job.inside, job.cross, job.rect
	local s = { questID = job.questID, zone = job.zone, map = job.map, stamp = job.stamp, way = WAYS[job.wayIndex],
		cell = job.cell, nx = nx, ny = ny, calls = job.n, frames = job.frames, ms = job.ms,
		gx = {}, gy = {}, p1 = {}, p2 = {}, p3 = {}, p4 = {}, lv = {}, ls = {}, le = {}, np = 0, nv = 0, inside = 0 }
	local gridV, edgeV = {}, {}
	local W, Hh = r[3] - r[1], r[4] - r[2]
	local function Corner(i, j)
		local k = j * (nx + 1) + i
		local v = gridV[k]
		if not v then
			s.nv = s.nv + 1; v = s.nv
			s.gx[v], s.gy[v] = r[1] + (job.fu0 + i * job.du) * W, r[2] + (job.fv0 + j * job.dv) * Hh
			gridV[k] = v
		end
		return v
	end
	local function EdgePoint(e, i0, j0, i1, j1)
		local v = edgeV[e]
		if not v then
			local t = cross[e]
			s.nv = s.nv + 1; v = s.nv
			local u0, v0 = job.fu0 + i0 * job.du, job.fv0 + j0 * job.dv
			local u1, v1 = job.fu0 + i1 * job.du, job.fv0 + j1 * job.dv
			s.gx[v], s.gy[v] = r[1] + (u0 + (u1 - u0) * t) * W, r[2] + (v0 + (v1 - v0) * t) * Hh
			edgeV[e] = v
		end
		return v
	end
	local function Add(a, b, c, d)
		s.np = s.np + 1
		s.p1[s.np], s.p2[s.np], s.p3[s.np], s.p4[s.np] = a, b, c, d
	end
	local nextOf, order = {}, {}
	local poly, isEdge, ci, cj = {}, {}, { 0, 1, 1, 0 }, { 0, 0, 1, 1 }
	local function Emit(n)
		-- outline: consecutive edge points of the piece are where the edge passes through the cell
		for m = 1, n do
			local a, b = poly[m], poly[m % n + 1]
			if isEdge[a] and isEdge[b] then nextOf[a] = b; order[#order + 1] = a end
		end
		if n == 3 then Add(poly[1], poly[2], poly[3], poly[3])
		elseif n == 4 then Add(poly[1], poly[2], poly[3], poly[4])
		elseif n == 5 then Add(poly[1], poly[2], poly[3], poly[4]); Add(poly[1], poly[4], poly[5], poly[5]) end
	end
	for j = 0, ny - 1 do
		for i = 0, nx - 1 do
			local c1, c2 = inside[j * (nx + 1) + i], inside[j * (nx + 1) + i + 1]
			local c3, c4 = inside[(j + 1) * (nx + 1) + i + 1], inside[(j + 1) * (nx + 1) + i]
			local ins = c1 + c2 + c3 + c4
			if ins > 0 then
				local inn = { c1, c2, c3, c4 }
				local e = { EdgeH(job, i, j), EdgeV(job, i + 1, j), EdgeH(job, i, j + 1), EdgeV(job, i, j) }
				local ends = { { i, j, i + 1, j }, { i + 1, j, i + 1, j + 1 }, { i, j + 1, i + 1, j + 1 }, { i, j, i, j + 1 } }
				local function EP(m) local q = ends[m]; local v = EdgePoint(e[m], q[1], q[2], q[3], q[4]); isEdge[v] = true; return v end
				if ins == 2 and c1 == c3 then
					-- a saddle: two corners across from each other, taken as two separate pieces
					for m = 1, 4 do
						if inn[m] == 1 then
							poly[1], poly[2], poly[3] = EP((m + 2) % 4 + 1), Corner(i + ci[m], j + cj[m]), EP(m)
							Emit(3)
						end
					end
				else
					local n = 0
					for m = 1, 4 do
						if inn[m] == 1 then n = n + 1; poly[n] = Corner(i + ci[m], j + cj[m]) end
						if inn[m] ~= inn[m % 4 + 1] then n = n + 1; poly[n] = EP(m) end
					end
					Emit(n)
				end
				s.inside = s.inside + (ins == 4 and 1 or 0)
			end
		end
	end
	-- chain the outline's pieces into closed loops
	local done = {}
	for _, a in ipairs(order) do
		if not done[a] then
			s.ls[#s.ls + 1] = #s.lv + 1
			local v = a
			while v and not done[v] do done[v] = true; s.lv[#s.lv + 1] = v; v = nextOf[v] end
			s.le[#s.le + 1] = #s.lv
		end
	end
	s.x0, s.x1, s.y0, s.y1 = math.huge, -math.huge, math.huge, -math.huge
	for v = 1, s.nv do
		s.x0, s.x1 = math.min(s.x0, s.gx[v]), math.max(s.x1, s.gx[v])
		s.y0, s.y1 = math.min(s.y0, s.gy[v]), math.max(s.y1, s.gy[v])
	end
	return s
end
Q.BuildShape = BuildShape

local function Finish(job, shape, why)
	table.remove(areaJobs, 1)
	if Q.sampler then Q.sampler:DrawNone(); Q.sampler:Hide() end
	if shape then
		if not Q.area.way then Q.area.way = shape.way end
		areaShapes[job.key] = shape
		Q.area.last = ("quest %d in zone %d: %s; %d pieces, %d outline(s), cells of %.1f yd; %d hit-tests in %.1f ms over %d frames"):format(
			job.questID, job.zone, WAY_TEXT[shape.way], shape.np, #shape.ls, shape.cell, job.n, job.ms, job.frames)
	else
		areaShapes[job.key] = { none = true, stamp = job.stamp }
		Q.area.last = ("quest %d in zone %d: no area found (%s); %d hit-tests in %.1f ms over %d frames"):format(job.questID, job.zone, tostring(why), job.n, job.ms, job.frames)
	end
	ns.Log("QUEST", "3D area of %s", Q.area.last)
	Q.Changed(true)
end

-- The coarse search's window: job.reach yards round the quest's point, within the zone.
local function CoarseWindow(job)
	local hu, hv = job.reach / job.wyd, job.reach / job.hyd
	job.cu0, job.cu1 = math.max(0, job.x - hu), math.min(1, job.x + hu)
	job.cv0, job.cv1 = math.max(0, job.y - hv), math.min(1, job.y + hv)
	job.i0, job.i1, job.j0, job.j1 = math.huge, -math.huge, math.huge, -math.huge
	job.k = -1
end

local function Hit(job, u, v)
	job.n = job.n + 1
	return Q.sampler:UpdateMouseOverTooltip(u, v) == job.questID
end

-- The coarse search is through: a wider window, the whole zone, the next way, nothing, or the fine
-- grid over the box round the hits (one coarse cell more each side). True: this frame's share is over.
local function CoarseDone(job)
	local n = job.cn
	local whole = job.cu0 <= 0 and job.cu1 >= 1 and job.cv0 <= 0 and job.cv1 >= 1
	local hits = job.i0 <= job.i1
	local su, sv = (job.cu1 - job.cu0) / n, (job.cv1 - job.cv0) / n
	if hits and not whole and ((job.i0 == 0 and job.cu0 > 0) or (job.i1 == n - 1 and job.cu1 < 1) or (job.j0 == 0 and job.cv0 > 0) or (job.j1 == n - 1 and job.cv1 < 1)) then
		job.reach = job.reach * 2 -- the area reaches the window's edge
		CoarseWindow(job)
		return false
	end
	if not (hits or job.mhit) then
		if not whole then
			job.reach, job.cn = 1e9, AREA_WHOLE
			CoarseWindow(job)
			return false
		end
		local i = NextWay(job)
		if not i then
			Finish(job, nil, Q.area.way and ("asked with the " .. WAY_TEXT[Q.area.way]) or "asked with the frame hidden, at alpha 0 and behind the 3D view")
		else
			job.wayIndex, job.phase = i, "set"
		end
		return true
	end
	local u0, u1, v0, v1 = job.x - su, job.x + su, job.y - sv, job.y + sv -- round the quest's point, if that is all
	if hits then
		local a0, a1 = job.cu0 + (job.i0 - 1) * su, job.cu0 + (job.i1 + 2) * su
		local b0, b1 = job.cv0 + (job.j0 - 1) * sv, job.cv0 + (job.j1 + 2) * sv
		if job.mhit then u0, u1, v0, v1 = math.min(u0, a0), math.max(u1, a1), math.min(v0, b0), math.max(v1, b1)
		else u0, u1, v0, v1 = a0, a1, b0, b1 end
	end
	u0, u1, v0, v1 = math.max(0, u0), math.min(1, u1), math.max(0, v0), math.min(1, v1)
	local fw, fh = (u1 - u0) * job.wyd, (v1 - v0) * job.hyd
	local cell = math.max(AREA_MIN_CELL, math.max(fw, fh) / AREA_FINE)
	job.nx, job.ny = math.max(2, math.ceil(fw / cell)), math.max(2, math.ceil(fh / cell))
	job.fu0, job.fv0, job.du, job.dv = u0, v0, (u1 - u0) / job.nx, (v1 - v0) / job.ny
	job.cell = math.max(job.du * job.wyd, job.dv * job.hyd)
	job.inside, job.cross, job.phase, job.k = {}, {}, "fine", 0
	return false
end

-- One frame's share of a job. Phases: set (draw the quest on the sampler, then wait 2 frames so it
-- has been drawn once), coarse (find the area), fine (the grid's corners), edges (where the edge
-- crosses each grid edge), then the shape is built.
local function Step(job, t0)
	if job.phase == "set" then
		if not Sampler(WAYS[job.wayIndex], job.zone, job.questID) then return Finish(job, nil, Q.area.broken) end
		job.phase, job.wait = "wait", 2
		job.reach, job.cn = AREA_REACH, AREA_COARSE
		CoarseWindow(job)
		return
	elseif job.phase == "wait" then
		job.wait = job.wait - 1
		if job.wait <= 0 then job.phase = "coarse" end
		return
	end
	local start = job.n
	while job.n - start < AREA_CALLS and debugprofilestop() - t0 < AREA_MS do
		if job.phase == "coarse" then
			local n, k = job.cn, job.k
			if k < 0 then
				job.mhit = Hit(job, job.x, job.y) -- the quest's own point first: a small area round it is not missed
			elseif k < n * n then
				local i, j = k % n, math.floor(k / n)
				if Hit(job, job.cu0 + (i + 0.5) * (job.cu1 - job.cu0) / n, job.cv0 + (j + 0.5) * (job.cv1 - job.cv0) / n) then
					job.i0, job.i1 = math.min(job.i0, i), math.max(job.i1, i)
					job.j0, job.j1 = math.min(job.j0, j), math.max(job.j1, j)
				end
			elseif CoarseDone(job) then
				break
			end
			if job.phase == "coarse" and k == job.k then job.k = k + 1 end
		elseif job.phase == "fine" then
			local nx, k = job.nx, job.k
			if k < (nx + 1) * (job.ny + 1) then
				local i, j = k % (nx + 1), math.floor(k / (nx + 1))
				-- the grid's border counts as outside, so every outline closes
				job.inside[k] = (i > 0 and j > 0 and i < nx and j < job.ny and Hit(job, job.fu0 + i * job.du, job.fv0 + j * job.dv)) and 1 or 0
				job.k = k + 1
			else
				job.phase, job.k = "edges", 1
			end
		else -- edges
			local nx, ny, e = job.nx, job.ny, job.k
			local nh = nx * (ny + 1)
			if e > nh + ny * (nx + 1) then
				job.ms, job.frames = job.ms + debugprofilestop() - t0, job.frames + 1
				return Finish(job, BuildShape(job))
			end
			local i0, j0, i1, j1
			if e <= nh then
				i0, j0 = (e - 1) % nx, math.floor((e - 1) / nx); i1, j1 = i0 + 1, j0
			else
				local q = e - nh - 1
				i0, j0 = q % (nx + 1), math.floor(q / (nx + 1)); i1, j1 = i0, j0 + 1
			end
			local a = job.inside[j0 * (nx + 1) + i0]
			if a ~= job.inside[j1 * (nx + 1) + i1] then
				-- bisected between the inside end and the outside end; t is measured from the first end
				local lo, hi = a == 1 and 0 or 1, a == 1 and 1 or 0
				local u0, v0 = job.fu0 + i0 * job.du, job.fv0 + j0 * job.dv
				local du, dv = (i1 - i0) * job.du, (j1 - j0) * job.dv
				for _ = 1, AREA_BISECT do
					local m = (lo + hi) / 2
					if Hit(job, u0 + du * m, v0 + dv * m) then lo = m else hi = m end
				end
				job.cross[e] = (lo + hi) / 2
			end
			job.k = e + 1
		end
	end
	job.ms, job.frames = job.ms + debugprofilestop() - t0, job.frames + 1
end

local areaDriver = CreateFrame("Frame")
local function RunJobs()
	local job = areaJobs[1]
	if not job then areaDriver:SetScript("OnUpdate", nil) return end
	if Q.areaHost and not Q.areaHost:IsShown() then return end -- the 3D view closed: wait (its "behind" way needs it shown)
	local t0 = debugprofilestop()
	local ok, err = pcall(Step, job, t0)
	if not ok then
		Q.area.broken = "the hit-test failed: " .. tostring(err)
		if areaJobs[1] == job then Finish(job, nil, Q.area.broken) end
	end
end

local function Queue(q, key, instance)
	for _, job in ipairs(areaJobs) do if job.key == key then return end end
	local r = ZoneRect(q.zone)
	if not r then return end
	local job = { key = key, questID = q.questID, zone = q.zone, map = instance, x = q.x, y = q.y, stamp = cache.stamp, rect = r,
		wyd = math.max(1, math.abs(r[3] - r[1]) * TILE_YD), hyd = math.max(1, math.abs(r[4] - r[2]) * TILE_YD),
		wayIndex = 1, phase = "set", n = 0, frames = 0, ms = 0 }
	for i, way in ipairs(WAYS) do if way == Q.area.way then job.wayIndex = i end end
	areaJobs[#areaJobs + 1] = job
	areaDriver:SetScript("OnUpdate", RunJobs)
end

-- The shapes to draw in the 3D view of a GPS map: the tracked quest's and the hovered marker's areas
-- that are ready (a reused list: called every frame the view is drawn). Starts finding the ones not
-- known yet, or known from before the quest log last changed.
function Q.AreaShapes(instance)
	local n = 0
	if instance and Q.Enabled() and not Q.area.broken then
		for _, q in ipairs(Q.List(instance)) do
			if q.tracked or q.questID == Q.hovered then
				local key = q.questID * 100000 + q.zone
				local s = areaShapes[key]
				if not s or s.stamp ~= cache.stamp then Queue(q, key, instance) end
				if s and not s.none then n = n + 1; areaOut[n] = s end
			end
		end
	end
	for i = n + 1, #areaOut do areaOut[i] = nil end
	return areaOut
end

-- For /gps3d test: how the 3D view gets its areas, or why it cannot.
function Q.AreaStatus()
	if Q.area.broken then return "none: " .. Q.area.broken end
	if not Q.Enabled() then return "off (the Quests setting, Blizzard's quest objectives option, or the quest API)" end
	return ("from the quest-area frame's hit-test (UpdateMouseOverTooltip), %s; last: %s"):format(
		Q.area.way and WAY_TEXT[Q.area.way] or "way not known yet (no area found with the frame hidden, at alpha 0 or behind the 3D view)",
		Q.area.last or "none asked yet (track a quest with an area on this map)")
end

------------------------------------------------------------------------------------------------
-- In-game check (/gps test, "quests:" lines): what only the game can answer (TESTING.md)
------------------------------------------------------------------------------------------------
function Q.SelfTest(Report)
	local mapID = ns.PlayerPosition()
	local instance = mapID or ns.view.map
	local zones = ZonesOn(instance)
	local list = Q.Enabled() and Q.List(instance) or EMPTY
	local tracked
	for _, q in ipairs(list) do if q.tracked then tracked = q end end
	Report("quests: %d zones on this map, %d of your quests with a point on them%s; shown: %s", #zones, #list,
		tracked and (", tracking " .. tracked.questID .. " in zone " .. tracked.zone) or ", none tracked",
		Q.Enabled() and "yes" or "no (setting off, questPOI off, or quest API missing)")
	local ok, pin = pcall(CreateFrame, "Button", nil, UIParent, "POIButtonTemplate")
	Report("quests: 1. Blizzard's quest button (POIButtonTemplate): %s", ok and pin and pin.SetQuestID and "made" or ("NOT made (" .. tostring(pin) .. ")"))
	if ok and pin then pin:Hide() end
	local made, f = pcall(CreateFrame, "QuestPOIFrame", nil, UIParent)
	if not (made and f and f.DrawBlob) then
		Report("quests: 2. quest-area frame (QuestPOIFrame): NOT made (%s): no areas in 2D or 3D", tostring(f))
		return
	end
	Report("quests: 2. quest-area frame (QuestPOIFrame): made")
	if not tracked then
		Report("quests: 3./4. need a tracked quest with an area on this map: track one (click its marker) and run /gps test again")
		f:Hide()
		return
	end
	-- one frame drawn three ways: shown, shown at alpha 0, hidden; each asked "which quest's area is
	-- here?" on a 24 x 24 grid over the zone, a moment after drawing
	f:SetFillTexture(BLOB_FILL)
	f:SetBorderTexture(BLOB_BORDER)
	f:SetMapID(tracked.zone)
	f:SetSize(400, 400)
	f:SetPoint("CENTER", UIParent, "CENTER")
	f:SetFrameStrata("BACKGROUND")
	f:DrawNone()
	f:DrawBlob(tracked.questID, true)
	local function Hits()
		local n = 0
		for i = 0, 23 do
			for j = 0, 23 do
				local id = f:UpdateMouseOverTooltip((i + 0.5) / 24, (j + 0.5) / 24)
				if id == tracked.questID then n = n + 1 end
			end
		end
		return n
	end
	C_Timer.After(0.3, function()
		local shownHits = Hits()
		f:SetAlpha(0)
		local alphaHits = Hits()
		f:Hide()
		local hiddenHits = Hits()
		Report("quests: 3. area hit-test for quest %d (cells of 576 inside): shown %d, invisible (alpha 0) %d, hidden %d -> 3D areas %s",
			tracked.questID, shownHits, alphaHits, hiddenHits,
			shownHits == 0 and "UNKNOWN (no area found: does this quest have one on the map?)" or (alphaHits == shownHits or hiddenHits == shownHits) and "POSSIBLE" or "NOT possible this way")
		Report("quests: 4. look: on the 2D map, zoom all the way in on the tracked quest's area: it stays drawn, lines up with Blizzard's map, and stops at the window edge")
	end)
end

-- For the 3D view (GPS3D): the same quests and markers.
GPS_API.QuestList = function(instance) return Q.List(instance) end
GPS_API.QuestStamp = function() return cache.stamp end
GPS_API.NewQuestPin = function(parent) return Q.NewPin(parent) end
GPS_API.SetupQuestPin = function(pin, q) Q.SetupPin(pin, q) end
GPS_API.QuestAreas = function(instance) return Q.AreaShapes(instance) end
GPS_API.QuestAreaStatus = function() return Q.AreaStatus() end
GPS_API.SetQuestAreaHost = function(host, canvas) Q.SetAreaHost(host, canvas) end
