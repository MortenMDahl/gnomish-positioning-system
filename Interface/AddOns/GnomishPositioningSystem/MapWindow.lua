-- Gnomish Positioning System: the traditional map, GPS's third mode next to the 2D map and the 3D
-- view. Blizzard's own map art (zones, continents, dungeon floors) with Blizzard's pins and player
-- arrow, in the GPS window. It is what opens where GPS cannot show you: in dungeons, raids and other
-- places the game gives addons no position, Blizzard's map still draws you (its player arrow is a
-- UnitPositionFrame, drawn by the game itself).
--
-- Built the way Blizzard builds its second map (Blizzard_BattlefieldMap, the zone map): a frame with
-- MapCanvasMixin and a MapCanvasFrameScrollContainerTemplate scroll frame, plus Blizzard's shared map
-- data providers, the quest ones included (as on Blizzard's world map). Made on first use, from Blizzard_WorldMap's code (which loads at login and brings
-- Blizzard_MapCanvas and Blizzard_SharedMapDataProviders); Blizzard's WorldMapFrame is not touched.
--
-- Mouse (Blizzard's): click a zone to open it, right-click for the map above, wheel zooms, drag pans
-- when zoomed in. Rings: mode, Me (the map you are on). < > switch floors on maps with several.
local addonName, ns = ...

local CHROME_LEVEL = 9500   -- the window's controls sit above the map's pins (Blizzard keeps those at 0..9000)
local AREA_LABEL_Y = -58    -- the hovered zone's name, under the title band
local UPDATE_INTERVAL = 0.2 -- seconds between footer and Me-ring updates

-- The data providers: those Blizzard gives its zone map (Blizzard_BattlefieldMap), plus the quest
-- layers of its world map (since 2026-10-17: quest givers, bonus objectives, the objective area of
-- the tracked or hovered quest, your quests' markers, your map pin and the tracked quest's waypoint)
-- and the hovered zone's name (AreaLabel), in the order Blizzard's world map adds them; GroupMembers
-- draws you and your group. A provider this client does not have is skipped.
local PROVIDERS = {
	"MapExplorationDataProviderMixin", "MapHighlightDataProviderMixin", "QuestOfferDataProviderMixin",
	"BattlefieldFlagDataProviderMixin", "BonusObjectiveDataProviderMixin", "VehicleDataProviderMixin",
	"FogOfWarDataProviderMixin", "DeathMapDataProviderMixin", "QuestBlobDataProviderMixin",
	"ScenarioDataProviderMixin", "VignetteDataProviderMixin", "QuestDataProviderMixin",
	"GossipDataProviderMixin", "FlightPointDataProviderMixin", "PetTamerDataProviderMixin",
	"DigSiteDataProviderMixin", "DungeonEntranceDataProviderMixin", "MapLinkDataProviderMixin",
	"SelectableGraveyardDataProviderMixin", "AreaPOIDataProviderMixin", "AreaPOIEventDataProviderMixin",
	"QuestSessionDataProviderMixin", "WaypointLocationDataProviderMixin", "SuperTrackWaypointDataProviderMixin",
	"EncounterJournalDataProviderMixin", "AreaLabelDataProviderMixin", "GroupMembersDataProviderMixin",
}
-- The pin frame levels, bottom to top, as Blizzard's world map defines them (Blizzard_WorldMap.lua,
-- AddStandardDataProviders): { name, range }; a function range is read when the map is made.
local PIN_LEVELS = {
	{ "PIN_FRAME_LEVEL_MAP_EXPLORATION" }, { "PIN_FRAME_LEVEL_PLUNDERSTORM_CIRCLE" }, { "PIN_FRAME_LEVEL_FOG_OF_WAR" },
	{ "PIN_FRAME_LEVEL_QUEST_BLOB" }, { "PIN_FRAME_LEVEL_SCENARIO_BLOB" }, { "PIN_FRAME_LEVEL_MAP_HIGHLIGHT" },
	{ "PIN_FRAME_LEVEL_DEBUG", 4 }, { "PIN_FRAME_LEVEL_DIG_SITE" }, { "PIN_FRAME_LEVEL_DUNGEON_ENTRANCE" },
	{ "PIN_FRAME_LEVEL_FLIGHT_POINT" }, { "PIN_FRAME_LEVEL_PET_TAMER" }, { "PIN_FRAME_LEVEL_SELECTABLE_GRAVEYARD" },
	{ "PIN_FRAME_LEVEL_AREA_POI" }, { "PIN_FRAME_LEVEL_GOSSIP" }, { "PIN_FRAME_LEVEL_DEBUG" },
	{ "PIN_FRAME_LEVEL_MAP_LINK" }, { "PIN_FRAME_LEVEL_ENCOUNTER" }, { "PIN_FRAME_LEVEL_VIGNETTE", 200 },
	{ "PIN_FRAME_LEVEL_QUEST_OFFER", function() return QuestOfferDataProviderMixin and QuestOfferDataProviderMixin.PIN_LEVEL_RANGE end },
	{ "PIN_FRAME_LEVEL_SCENARIO" }, { "PIN_FRAME_LEVEL_BONUS_OBJECTIVE" }, { "PIN_FRAME_LEVEL_AREA_POI_EVENT" },
	{ "PIN_FRAME_LEVEL_QUEST_PING" },
	{ "PIN_FRAME_LEVEL_ACTIVE_QUEST", function() return C_QuestLog and C_QuestLog.GetMaxNumQuests and C_QuestLog.GetMaxNumQuests() end },
	{ "PIN_FRAME_LEVEL_SUPER_TRACKED_CONTENT" }, { "PIN_FRAME_LEVEL_SUPER_TRACKED_QUEST" },
	{ "PIN_FRAME_LEVEL_VEHICLE_BELOW_GROUP_MEMBER" }, { "PIN_FRAME_LEVEL_BATTLEFIELD_FLAG" },
	{ "PIN_FRAME_LEVEL_WAYPOINT_LOCATION" }, { "PIN_FRAME_LEVEL_GROUP_MEMBER" },
	{ "PIN_FRAME_LEVEL_VEHICLE_ABOVE_GROUP_MEMBER" }, { "PIN_FRAME_LEVEL_CORPSE" },
}
ns.MAP_PROVIDERS, ns.MAP_PIN_LEVELS = PROVIDERS, PIN_LEVELS -- for the tests

------------------------------------------------------------------------------------------------
-- The window (GPS's look); the map canvas inside it is made on first use
------------------------------------------------------------------------------------------------
local win = CreateFrame("Frame", "GPS_WorldMapFrame", UIParent, "BackdropTemplate")
win:SetSize(900, 650)
win:SetPoint("CENTER")
win:SetFrameStrata("HIGH")
win:SetClampedToScreen(true)
win:SetMovable(true)
win:SetResizable(true)
if win.SetResizeBounds then win:SetResizeBounds(400, 300, 4000, 3000) end
win:EnableMouse(true)
win:Hide()
tinsert(UISpecialFrames, "GPS_WorldMapFrame") -- Escape closes it

local holder = CreateFrame("Frame", nil, win) -- the map canvas goes in here
holder:SetClipsChildren(true)

local function KeepGeometry() ns.SaveGeometry(win) end
local ui = ns.ApplyChrome(win, holder, { mode = "Map", chromeLevel = CHROME_LEVEL, onMoved = KeepGeometry, onSized = KeepGeometry })
ui.subtitle:ClearAllPoints()
ui.subtitle:SetPoint("TOPLEFT", 10, -28)
ui.prev.tooltip = "Previous floor"
ui.next.tooltip = "Next floor"
ui.me.tooltip = { "Me", "Show the map you are on" }
ui.prev:Hide()
ui.next:Hide()
local mw = { win = win, ui = ui, follow = true } -- the map canvas (mw.map) once made; follow: showing your map
ns.mapWindow = mw

-- The map Blizzard's map would open for you (the nearest map with art above where you are).
local function PlayerMap()
	if MapUtil and MapUtil.GetDisplayableMapForPlayer then return MapUtil.GetDisplayableMapForPlayer() end
	return C_Map.GetBestMapForUnit("player")
end

------------------------------------------------------------------------------------------------
-- Title, floors, follow
------------------------------------------------------------------------------------------------
-- Title: the map's name. Subtitle: the floor and < > on maps with several floors, else the map it
-- belongs to.
function mw.UpdateTitle()
	local map = mw.map
	local id = map and map:GetMapID()
	local info = id and C_Map.GetMapInfo(id)
	ui.title:SetText(info and info.name or ns.modeNames.Map)
	mw.floors, mw.floor = nil, nil
	local group = id and C_Map.GetMapGroupID and C_Map.GetMapGroupID(id)
	local members = group and C_Map.GetMapGroupMembersInfo(group)
	if members and #members > 1 then
		table.sort(members, function(a, b) return a.relativeHeightIndex < b.relativeHeightIndex end)
		for i, f in ipairs(members) do if f.mapID == id then mw.floor = i end end
		mw.floors = members
	end
	ui.subtitle:ClearAllPoints()
	if mw.floor then
		ui.subtitle:SetPoint("LEFT", ui.prev, "RIGHT", 0, 0)
		ui.subtitle:SetText(("%s  (%d of %d)"):format(mw.floors[mw.floor].name, mw.floor, #mw.floors))
		ui.prev:Show()
		ui.next:Show()
	else
		local parent = info and info.parentMapID and info.parentMapID > 0 and C_Map.GetMapInfo(info.parentMapID)
		ui.subtitle:SetPoint("TOPLEFT", 10, -28)
		ui.subtitle:SetText(parent and parent.name or "")
		ui.prev:Hide()
		ui.next:Hide()
	end
end

function mw.StepFloor(step)
	if not (mw.floors and mw.floor) then return end
	local i = (mw.floor - 1 + step) % #mw.floors + 1
	mw.map:SetMapID(mw.floors[i].mapID)
end
ui.prev:SetScript("OnClick", function() mw.StepFloor(-1) end)
ui.next:SetScript("OnClick", function() mw.StepFloor(1) end)

-- Shows a map; follow (the map changes with you as you move between zones and floors) holds while
-- the map shown is yours.
function mw.SetMap(id)
	if not (mw.map and id) then return end
	mw.map:SetMapID(id)
	mw.follow = id == PlayerMap()
	mw.UpdateTitle()
	ns.Log("MAPWIN", "map %s (%s), follow %s", tostring(id), tostring(ui.title:GetText()), tostring(mw.follow))
end

-- Me: your map, and you in the middle of it when zoomed in.
function mw.ShowMe()
	if not mw.map then return end
	local id = PlayerMap()
	mw.SetMap(id)
	mw.follow = true
	local pos = C_Map.GetPlayerMapPosition(id, "player")
	if pos and mw.map:GetCanvasZoomPercent() > 0 then mw.map:PanTo(pos.x, pos.y) end
end
ui.me:SetScript("OnClick", function() mw.ShowMe() end)
ui.zoomIn:SetScript("OnClick", function() if mw.map then mw.map:ZoomIn() end end)
ui.zoomOut:SetScript("OnClick", function() if mw.map then mw.map:ZoomOut() end end)

------------------------------------------------------------------------------------------------
-- The map canvas (Blizzard's), made on first use
------------------------------------------------------------------------------------------------
function mw.Make()
	if mw.map then return mw.map end
	if not MapCanvasMixin and C_AddOns and C_AddOns.LoadAddOn then C_AddOns.LoadAddOn("Blizzard_WorldMap") end
	if not (MapCanvasMixin and Mixin and CreateFromMixins) then ns.Log("MAPWIN", "Blizzard's map canvas is not available") return nil end
	local map = CreateFrame("Frame", nil, holder)
	map:SetAllPoints(holder)
	Mixin(map, MapCanvasMixin)
	-- MapCanvasMixin.OnLoad needs the frame's two children (in Blizzard's XML they are made first):
	-- the scroll container, and a BorderFrame that blocks the mouse while the map is locked
	-- (EvaluateLockReasons); ours draws nothing, the GPS window has its own edge
	local scroll = CreateFrame("ScrollFrame", nil, map, "MapCanvasFrameScrollContainerTemplate")
	scroll:ClearAllPoints()
	scroll:SetAllPoints(map)
	map.ScrollContainer = scroll
	local border = CreateFrame("Frame", nil, map)
	border:SetAllPoints(map)
	border:SetFrameLevel(CHROME_LEVEL - 100) -- over the pins, under the GPS controls
	map.BorderFrame = border
	map:OnLoad()
	for _, script in ipairs({ "OnShow", "OnHide", "OnUpdate", "OnEvent" }) do map:SetScript(script, map[script]) end
	map:SetScript("OnSizeChanged", function(self) if self.mapID then self:OnFrameSizeChanged() end end)
	-- Blizzard's world map behaviour: click a zone to open it, right-click for the map above
	map:SetShouldZoomInOnClick(false)
	map:SetShouldPanOnClick(false)
	map:SetShouldNavigateOnClick(true)
	map:SetShouldZoomInstantly(true)
	for _, name in ipairs(PROVIDERS) do
		local mixin = _G[name]
		if mixin then
			local provider = CreateFromMixins(mixin)
			if name == "AreaLabelDataProviderMixin" then provider:SetOffsetY(AREA_LABEL_Y) end
			map:AddDataProvider(provider)
		end
	end
	local levels = map:GetPinFrameLevelsManager()
	for _, level in ipairs(PIN_LEVELS) do
		local range = level[2]
		if type(range) == "function" then range = range() end
		levels:AddFrameLevel(level[1], range)
	end
	-- every map change (yours, a click on a zone, right-click, a floor) updates the title and follow
	local OnMapChanged = map.OnMapChanged
	function map:OnMapChanged()
		OnMapChanged(self)
		mw.follow = self:GetMapID() == PlayerMap()
		mw.UpdateTitle()
	end
	mw.map = map
	if ns.compat then ns.compat.MapMade(map) end -- other addons' map layers (Compat.lua)
	if ns.debugOn then
		local n, missing = 0, {}
		for _, name in ipairs(PROVIDERS) do if _G[name] then n = n + 1 else missing[#missing + 1] = name end end
		ns.Log("MAPWIN", "map canvas made: %d of %d data providers%s, pins up to level %s", n, #PROVIDERS,
			#missing > 0 and (" (missing " .. table.concat(missing, ", ") .. ")") or "", tostring(levels.maxLevel))
	end
	return map
end

-- Where the map looks, for the other modes: the middle of the view on the 2D grid, or nil while it
-- shows your map (they then open on you), or where that place has no GPS map.
function mw.Focus()
	local map = mw.map
	if not map or mw.follow or not win:IsShown() then return nil end
	local id = map:GetMapID()
	local x, y = 0.5, 0.5
	local rect = map.GetViewRect and map:GetViewRect()
	if rect and rect.GetCenter then x, y = rect:GetCenter() end
	local continent, world = C_Map.GetWorldPosFromMapPos(id, CreateVector2D(x, y))
	if not (continent and world) then return nil end
	local wx, wy = world:GetXY()
	local gx, gy = ns.WorldToGrid(wx, wy)
	return { map = continent, gx = gx, gy = gy }
end

-- The zone map of a place on the 2D grid (focus from another mode; "you" or nil: none).
local function MapAt(focus)
	if not (type(focus) == "table" and C_Map.GetMapPosFromWorldPos and CreateVector2D) then return nil end
	local X, Y = ns.GridToWorld(focus.gx, focus.gy)
	local id = C_Map.GetMapPosFromWorldPos(focus.map, CreateVector2D(X, Y))
	return id
end

-- Opens the window: at the place and size of `from`, on the map of `focus` (else on yours).
function mw.Open(from, focus)
	if not mw.Make() then
		print("|cff33ff99GPS|r: Blizzard's map is not available.")
		return false
	end
	if from then ns.CopyGeometry(win, from) end
	local id = MapAt(focus)
	mw.SetMap(id or PlayerMap())
	if not id then mw.follow = true end
	win:Show()
	return true
end

ns.modes.Map = {
	Frame = function() return win end,
	available = function() return MapCanvasMixin ~= nil or (C_AddOns ~= nil and C_AddOns.LoadAddOn ~= nil) end,
	open = mw.Open,
	focus = mw.Focus,
}

------------------------------------------------------------------------------------------------
-- Following you, the footer, the Me ring
------------------------------------------------------------------------------------------------
-- After a zone or floor change, a map showing you moves on with you.
function mw.FollowUpdate()
	if not (mw.map and win:IsShown() and mw.follow) then return end
	local id = PlayerMap()
	if id and id ~= mw.map:GetMapID() then ns.Log("MAPWIN", "following you to map %s", tostring(id)); mw.SetMap(id) end
end
local events = CreateFrame("Frame")
for _, e in ipairs({ "PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA", "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "NEW_WMO_CHUNK" }) do
	events:RegisterEvent(e)
end
events:SetScript("OnEvent", function() mw.FollowUpdate() end)

local since = 0
win:SetScript("OnUpdate", function(_, elapsed)
	since = since + elapsed
	if since < UPDATE_INTERVAL then return end
	since = 0
	ui.footer:SetText(ns.WhereText())
	if ui.me.active ~= mw.follow then ui.me:SetActive(mw.follow) end -- gold while showing your map
end)
win:SetScript("OnShow", function()
	since = UPDATE_INTERVAL
	mw.FollowUpdate()
end)
win:SetScript("OnHide", function() KeepGeometry() end)

------------------------------------------------------------------------------------------------
-- Self-test lines (/gps test)
------------------------------------------------------------------------------------------------
function ns.MapSelfTest(Report)
	local map = mw.Make()
	if not map then
		Report("traditional map: Blizzard's map canvas (MapCanvasMixin) NOT available")
		return
	end
	local id = PlayerMap()
	local info = id and C_Map.GetMapInfo(id)
	local layers = id and C_Map.GetMapArtLayers and C_Map.GetMapArtLayers(id)
	local providers = 0
	for _ in pairs(map.dataProviders or {}) do providers = providers + 1 end
	local levels = map:GetPinFrameLevelsManager()
	Report("traditional map: your map %s (%s), %d art layer(s), %d data providers, controls at level %d above pins (up to %s)",
		tostring(id), info and info.name or "?", layers and #layers or 0, providers, ui.close:GetFrameLevel(), tostring(levels and levels.maxLevel or "?"))
end
