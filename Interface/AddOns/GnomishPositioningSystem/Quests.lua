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
-- The 3D view draws the same markers (GPS3D, through GPS_API); its areas wait on the in-game check
-- (/gps test, "quests:" lines, TESTING.md).
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
	Q.hovered = id
	if POIButtonHighlightManager and POIButtonHighlightManager.SetHighlight then POIButtonHighlightManager:SetHighlight(id) end
	Q.Changed(true)
end
local function PinLeave(self)
	if GameTooltip:GetOwner() == self then GameTooltip:Hide() end
	if Q.hovered == self.gpsQuestID then
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
		local pin = pins2D[i]
		if not pin then pin = Q.NewPin(pinLayer); pins2D[i] = pin end
		if pin.gpsQ ~= q or pin.gpsStamp ~= stamp then
			Q.SetupPin(pin, q)
			pin:SetFrameLevel(pinLayer:GetFrameLevel() + (q.tracked and 2 or 1))
			pin.gpsQ, pin.gpsStamp = q, stamp
		end
		local px, py = ns.GridToScreen(q.gx, q.gy)
		pin:ClearAllPoints()
		pin:SetPoint("CENTER", canvas, "TOPLEFT", px, -py)
		pin:Show()
	end
	for i = #list + 1, #pins2D do pins2D[i]:Hide() end
	-- objective areas: one frame per zone with an area to draw
	local want = {}
	for _, q in ipairs(list == EMPTY and EMPTY or Q.AreaQuests(view.map)) do
		want[q.zone] = want[q.zone] or {}
		table.insert(want[q.zone], q.questID)
	end
	for zone, f in pairs(areas2D) do
		if f and not want[zone] then f.quests, f.key = nil, nil; f:DrawNone(); f:Hide() end
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
