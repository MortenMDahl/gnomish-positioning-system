-- Gnomish Positioning System: other addons' map markers in GPS's windows. Nothing of any other
-- addon is copied into GPS: while an addon is installed, GPS uses what it puts on Blizzard's world
-- map, or what it offers other addons, at run time.
--
-- 1. Map layers (all addons written the standard way: GatherMate2, HandyNotes and its plugins, and
--    any other that adds a data provider to Blizzard's world map). GPS watches
--    WorldMapFrame:AddDataProvider / RemoveDataProvider (hooksecurefunc: it only looks, Blizzard's
--    map is not changed) and puts a copy of every layer an addon adds onto GPS's traditional map,
--    which is Blizzard's own map canvas code. The addon's code then draws its own pins there, with
--    its own templates, tooltips and clicks. Left alone: Blizzard's own layers (the traditional map
--    has its own), and layers of pin libraries (HereBeDragons-Pins) whose icons are frames the addon
--    owns (one frame cannot be on two maps). Each copy is the addon's provider table with its own
--    map state (owningMap, registeredEvents and frames are not copied); its lifecycle calls are
--    guarded, so a layer that errors on GPS's map is switched off and noted in the debug log instead
--    of throwing errors. When the addon refreshes its layer (RefreshAllData, or a method named
--    Refresh... or Update... called on the original), the copy is refreshed too while it is shown.
-- 2. GatherMate2 on the 2D map and in the 3D view: its nodes for the zones of the map shown, through
--    GatherMate2's own functions (GetNodesForZone, DecodeLoc, GetNameForNode, Visible, nodeTextures,
--    its settings for scale, alpha and the world map), drawn with its pin template and its pin
--    mixin's handlers (tooltip, right-click menu); rebuilt when GatherMate2 updates its world map.
--
-- Setting: Options > AddOns > GPS > Other addons (db.addonMarkers, default on).
local addonName, ns = ...

local C = {}
ns.compat = C

local LIFECYCLE = {
	"OnAdded", "OnRemoved", "RemoveAllData", "RefreshAllData", "OnShow", "OnHide", "OnMapChanged", "OnEvent",
	"OnCanvasScaleChanged", "OnCanvasPanChanged", "OnCanvasSizeChanged", "OnGlobalAlphaChanged",
	"OnMapInsetSizeChanged", "OnMapInsetMouseEnter", "OnMapInsetMouseLeave",
}
local PIN_MIN_SCALE = 40   -- 2D: GatherMate2 nodes from this many pixels per tile (about a zone across the window)
local PIN_MAX_2D = 800     -- 2D: at most this many nodes drawn
local REBUILD_GAP = 1      -- seconds: GatherMate2's node list is rebuilt at most this often (it updates in bursts)
local EMPTY = {}

function C.Enabled() return not (ns.db and ns.db.addonMarkers == false) end

------------------------------------------------------------------------------------------------
-- 1. Map layers
------------------------------------------------------------------------------------------------
C.layers = {}   -- original provider -> { copy, owner, state = "on" | "off" | "failed" | "skipped", why }
C.order = {}    -- originals, in the order seen
C.blizzard = {} -- (without issecurevariable) the providers on Blizzard's map when GPS loaded
if WorldMapFrame and WorldMapFrame.dataProviders then
	for p in pairs(WorldMapFrame.dataProviders) do C.blizzard[p] = true end
end

-- Which addon made a provider (nil: Blizzard's own). The game knows who wrote each table field:
-- fields written by Blizzard's code are secure, an addon's are tainted by that addon's name.
local function Owner(p)
	if issecurevariable then
		local n = 0
		for k, v in pairs(p) do
			if type(v) == "function" and type(k) == "string" then
				local ok, secure, taint = pcall(issecurevariable, p, k)
				if ok and not secure then return taint or "an addon" end
				n = n + 1
				if n >= 8 then break end
			end
		end
		if n > 0 then return nil end
	end
	if C.blizzard[p] then return nil end
	return "an addon"
end

-- Providers of pin libraries (HereBeDragons-Pins and its copies inside other addons): their pins
-- carry the addon's own icon frames, which cannot be on two maps.
local function PinLibrary(p)
	if not (LibStub and LibStub.IterateLibraries) then return nil end
	for name, lib in LibStub:IterateLibraries() do
		if type(lib) == "table" and rawget(lib, "worldmapProvider") == p then return name end
	end
	return nil
end

local function Disable(entry, why)
	if entry.state == "failed" then return end
	entry.state, entry.why = "failed", why
	ns.Log("COMPAT", "layer of %s switched off on the traditional map: %s", tostring(entry.owner), tostring(why))
	local map = ns.mapWindow and ns.mapWindow.map
	if map and map.dataProviders and map.dataProviders[entry.copy] then
		entry.copy.gpsFailed = true
		pcall(map.RemoveDataProvider, map, entry.copy)
	end
end

local function Finish(copy, name, ok, ...)
	if ok then return ... end
	local entry = C.layers[copy.gpsOriginal]
	if entry and not copy.gpsFailed then Disable(entry, ("%s: %s"):format(name, tostring((...)))) end
end

-- The copy: the addon's provider with its own map state; lifecycle calls guarded.
local function Copy(p)
	local c = {}
	for k, v in pairs(p) do
		if k ~= "owningMap" and k ~= "registeredEvents" and not (type(v) == "table" and v.GetObjectType) then c[k] = v end
	end
	setmetatable(c, getmetatable(p))
	for _, name in ipairs(LIFECYCLE) do
		local f = c[name]
		if type(f) == "function" then
			c[name] = function(self, ...)
				if self.gpsFailed then return end
				return Finish(self, name, pcall(f, self, ...))
			end
		end
	end
	c.gpsOriginal = p
	return c
end

-- The addon refreshed its layer on Blizzard's map: refresh the copy too (only calls on the
-- original, so the copy's own calls are not repeated), while GPS's map shows it.
local function Replay(entry, name)
	hooksecurefunc(entry.original, name, function(self, ...)
		if self ~= entry.original or entry.state ~= "on" then return end
		local map = ns.mapWindow and ns.mapWindow.map
		if not (map and map:IsVisible() and map.dataProviders[entry.copy]) then return end
		local f = entry.copy[name]
		if name == "RefreshAllData" or name == "RemoveAllData" then f(entry.copy, ...)
		else Finish(entry.copy, name, pcall(f, entry.copy, ...)) end
	end)
end

-- Addon frame levels (pin layers they defined on Blizzard's map) the traditional map lacks.
local function CopyLevels(map)
	local from = WorldMapFrame and WorldMapFrame.GetPinFrameLevelsManager and WorldMapFrame:GetPinFrameLevelsManager()
	local to = map:GetPinFrameLevelsManager()
	if not (from and from.definitions and to and to.definitions) then return end
	for name, def in pairs(from.definitions) do
		if not to.definitions[name] and name ~= "PIN_FRAME_LEVEL_TOPMOST" then to:AddFrameLevel(name, def.range) end
	end
end

local function Attach(entry)
	local map = ns.mapWindow and ns.mapWindow.map
	if not map or entry.state ~= "on" or map.dataProviders[entry.copy] then return end
	CopyLevels(map)
	map:AddDataProvider(entry.copy)
	if map:IsVisible() and not entry.copy.gpsFailed then entry.copy:RefreshAllData() end
end

local function Detach(entry)
	local map = ns.mapWindow and ns.mapWindow.map
	if map and map.dataProviders[entry.copy] then pcall(map.RemoveDataProvider, map, entry.copy) end
end

-- A provider appeared on Blizzard's map.
function C.Seen(p)
	if type(p) ~= "table" then return end
	local known = C.layers[p]
	if known then
		-- an addon that took its layer off and puts it back (switched off and on again)
		if known.state == "removed" then
			known.state = C.Enabled() and "on" or "off"
			ns.Log("COMPAT", "layer of %s back on Blizzard's map: back on the traditional map", tostring(known.owner))
			Attach(known)
		end
		return
	end
	local owner = Owner(p)
	if not owner then return end -- Blizzard's own
	local entry = { original = p, owner = owner, state = "on" }
	C.layers[p] = entry
	C.order[#C.order + 1] = p
	local lib = PinLibrary(p)
	if lib then
		entry.state, entry.why = "skipped", "pins of " .. lib .. " (icon frames of its own)"
		ns.Log("COMPAT", "layer of %s left on Blizzard's map: %s", tostring(owner), entry.why)
		return
	end
	entry.copy = Copy(p)
	for k, v in pairs(p) do
		if type(k) == "string" and type(v) == "function" and (k == "RefreshAllData" or k:match("^Refresh") or k:match("^Update")) then Replay(entry, k) end
	end
	ns.Log("COMPAT", "layer of %s found on Blizzard's map: copied to the traditional map", tostring(owner))
	if C.Enabled() then Attach(entry) else entry.state = "off" end
end

function C.Gone(p)
	local entry = C.layers[p]
	if not entry or not entry.copy then return end
	Detach(entry)
	entry.state = "removed"
	ns.Log("COMPAT", "layer of %s removed from Blizzard's map: removed from the traditional map", tostring(entry.owner))
end

-- Every layer already on Blizzard's map (added before GPS loaded, or before its map was made).
function C.Scan()
	if not (WorldMapFrame and WorldMapFrame.dataProviders) then return end
	for p in pairs(WorldMapFrame.dataProviders) do C.Seen(p) end
end

-- The traditional map was made (MapWindow.lua): put the copies on it.
function C.MapMade(map)
	C.Scan()
	for _, p in ipairs(C.order) do
		local entry = C.layers[p]
		if entry.state == "on" then Attach(entry) end
	end
end

if WorldMapFrame and hooksecurefunc and WorldMapFrame.AddDataProvider then
	hooksecurefunc(WorldMapFrame, "AddDataProvider", function(_, p) C.Seen(p) end)
	hooksecurefunc(WorldMapFrame, "RemoveDataProvider", function(_, p) C.Gone(p) end)
end

------------------------------------------------------------------------------------------------
-- 2. GatherMate2 on the 2D map and in the 3D view
------------------------------------------------------------------------------------------------
local GM, Display = nil, nil
local function GatherMate()
	if GM == nil then
		local AA = LibStub and LibStub("AceAddon-3.0", true)
		local ok, gm = pcall(function() return AA and AA:GetAddon("GatherMate2", true) end)
		GM = ok and gm and gm.GetNodesForZone and gm.DecodeLoc and gm or false
		if GM then
			Display = GM.GetModule and select(2, pcall(GM.GetModule, GM, "Display", true)) or nil
			if type(Display) ~= "table" then Display = nil end
			-- GatherMate2 updates its world map when its filters, settings or professions change, and
			-- schedules a minimap update when it records a new node
			for _, name in ipairs({ "UpdateWorldMap", "ScheduleUpdate" }) do
				if Display and type(Display[name]) == "function" then hooksecurefunc(Display, name, function() C.NodesChanged() end) end
			end
			ns.Log("COMPAT", "GatherMate2 found (%s)", Display and "with its map display" or "without its map display")
		end
	end
	return GM or nil
end
C.GatherMate = GatherMate

local nodes = { instance = nil, list = EMPTY, byTile = {}, stamp = 0, dirty = true }
C.nodes = nodes

local function GMSettings()
	local db = GM and GM.db and GM.db.profile
	return db or EMPTY
end

-- GatherMate2's nodes on the zones of a GPS map: { gx, gy, zone, coord, nodeID, nodeType, title, texture }.
local function Rebuild(instance)
	local list, byTile = {}, {}
	nodes.instance, nodes.list, nodes.byTile, nodes.dirty = instance, list, byTile, false
	nodes.stamp = nodes.stamp + 1
	if not (C.Enabled() and GatherMate() and instance) then return end
	local db = GMSettings()
	if db.showWorldMap == false then return end
	if Display and Display.UpdateVisibility then pcall(Display.UpdateVisibility, Display) end
	local visible = GM.Visible or EMPTY
	local textures = GM.nodeTextures or EMPTY
	local replace = GM.nodeIDReplacementMap or EMPTY
	for _, zone in ipairs(ns.quests.ZonesOn(instance)) do
		local r = ns.quests.ZoneRect(zone)
		if r then
			local lookup = GM.phasing and GM.phasing[zone] or zone
			for _, nodeType in pairs(GM.db_types or EMPTY) do
				if visible[nodeType] then
					local ok, iter, state, init = pcall(GM.GetNodesForZone, GM, lookup, nodeType)
					if ok and iter then
						for coord, nodeID in iter, state, init do
							local x, y = GM:DecodeLoc(coord)
							local id = replace[nodeID] or nodeID
							local gx, gy = r[1] + x * (r[3] - r[1]), r[2] + y * (r[4] - r[2])
							local n = { gx = gx, gy = gy, zone = lookup, coord = coord, nodeID = id, nodeType = nodeType,
								title = GM.GetNameForNode and GM:GetNameForNode(nodeType, id), texture = textures[nodeType] and textures[nodeType][id] }
							list[#list + 1] = n
							local key = math.floor(gy) * 64 + math.floor(gx)
							local b = byTile[key]
							if not b then b = {}; byTile[key] = b end
							b[#b + 1] = n
						end
					end
				end
			end
		end
	end
end

-- Redraw the windows that show GatherMate2's nodes.
local function Redraw()
	if ns.frame and ns.frame:IsShown() and ns.LayoutAddonPins then ns.LayoutAddonPins() end
	if GPS3D_API and GPS3D_API.AddonPinsChanged then GPS3D_API.AddonPinsChanged() end
end

-- The nodes of a GPS map (for the 2D map and GPS3D through GPS_API). After a change the list is
-- rebuilt at once, then at most every REBUILD_GAP seconds (the rest of a burst a moment later).
function C.Nodes(instance)
	local now = GetTime()
	if nodes.instance ~= instance or (nodes.dirty and now - (nodes.builtAt or -1e9) >= REBUILD_GAP) then
		local t0 = debugprofilestop and debugprofilestop()
		Rebuild(instance)
		nodes.builtAt = now
		C.rebuildMs = t0 and debugprofilestop() - t0
		if GM then ns.Log("COMPAT", "GatherMate2: %d nodes on map %s (list made in %.1f ms)", #nodes.list, tostring(instance), C.rebuildMs or 0) end
	elseif nodes.dirty and not nodes.later then
		nodes.later = true
		C_Timer.After(REBUILD_GAP, function() nodes.later = nil; Redraw() end)
	end
	return nodes.list, nodes.byTile, nodes.stamp
end

function C.NodesChanged()
	nodes.dirty = true
	Redraw()
end

-- A pin: GatherMate2's own template and handlers where it has them (tooltip on hover, its
-- right-click menu), else a plain icon with the node's name as tooltip.
local function PinEnter(self)
	local mixin = GatherMate2WorldMapPinMixin
	if mixin and mixin.OnMouseEnter and self.gpsTemplate then return mixin.OnMouseEnter(self) end
	GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
	GameTooltip:SetText(self.title or "")
	GameTooltip:Show()
end
local function PinLeave(self)
	local mixin = GatherMate2WorldMapPinMixin
	if mixin and mixin.OnMouseLeave and self.gpsTemplate then return mixin.OnMouseLeave(self) end
	GameTooltip:Hide()
end
local function PinUp(self, button)
	local mixin = GatherMate2WorldMapPinMixin
	if mixin and mixin.OnClick and self.gpsTemplate and self:IsMouseOver() then mixin.OnClick(self, button) end
end

function C.NewPin(parent)
	local ok, pin = pcall(CreateFrame, "Frame", nil, parent, "GatherMate2WorldMapPinTemplate")
	if ok and pin and pin.texture then
		pin.gpsTemplate = true
	else
		pin = CreateFrame("Frame", nil, parent)
		pin.texture = pin:CreateTexture(nil, "OVERLAY")
		pin.texture:SetAllPoints()
	end
	pin:SetScript("OnEnter", PinEnter)
	pin:SetScript("OnLeave", PinLeave)
	pin:SetScript("OnMouseUp", PinUp)
	return pin
end

-- What GatherMate2's own world-map pin sets in OnAcquired (Display.lua), without the map position.
function C.SetupPin(pin, n)
	local db = GMSettings()
	pin.coords, pin.nodeID, pin.title, pin.zone, pin.nodeType, pin.worldmap = n.coord, n.nodeID, n.title, n.zone, n.nodeType, true
	local size = 12 * (db.scale or 1)
	pin:SetSize(size, size)
	pin:SetAlpha(db.alpha or 1)
	pin.texture:SetTexture(n.texture)
	pin.texture:SetTexCoord(0, 1, 0, 1)
	pin.texture:SetVertexColor(1, 1, 1, 1)
	pin:EnableMouse(db.worldMapIconsInteractive ~= false)
end

-- 2D: the nodes in view, once zoomed in to about a zone, on a layer under the quest markers.
local layer2D, pins2D = nil, {}
C.pins2D = pins2D
function ns.LayoutAddonPins()
	local view, canvas = ns.view, ns.canvas
	if not layer2D then
		layer2D = CreateFrame("Frame", nil, canvas)
		layer2D:SetAllPoints()
		layer2D:SetFrameLevel(canvas:GetFrameLevel() + 7)
		C.layer2D = layer2D
	end
	local n = 0
	if ns.frame:IsShown() and C.Enabled() and view.scale >= PIN_MIN_SCALE and GatherMate() then
		local _, byTile, stamp = C.Nodes(view.map)
		local w, h = canvas:GetSize()
		local x0, x1 = math.floor(view.cx - w / 2 / view.scale), math.floor(view.cx + w / 2 / view.scale)
		local y0, y1 = math.floor(view.cy - h / 2 / view.scale), math.floor(view.cy + h / 2 / view.scale)
		for ty = y0, y1 do
			for tx = x0, x1 do
				for _, node in ipairs(byTile[ty * 64 + tx] or EMPTY) do
					if n >= PIN_MAX_2D then break end
					local px, py = ns.GridToScreen(node.gx, node.gy)
					if px >= -8 and px <= w + 8 and py >= -8 and py <= h + 8 then
						n = n + 1
						local pin = pins2D[n]
						if not pin then pin = C.NewPin(layer2D); pins2D[n] = pin end
						if pin.gpsNode ~= node or pin.gpsStamp ~= stamp then C.SetupPin(pin, node); pin.gpsNode, pin.gpsStamp = node, stamp end
						pin:ClearAllPoints()
						pin:SetPoint("CENTER", canvas, "TOPLEFT", px, -py)
						pin:Show()
					end
				end
			end
		end
	end
	for i = n + 1, #pins2D do pins2D[i]:Hide() end
	C.shown2D = n
end

------------------------------------------------------------------------------------------------
-- Setting, start-up, self-test
------------------------------------------------------------------------------------------------
-- The setting changed: copies on or off, nodes rebuilt.
function C.SettingChanged()
	local on = C.Enabled()
	for _, p in ipairs(C.order) do
		local entry = C.layers[p]
		if on and entry.state == "off" then entry.state = "on"; Attach(entry)
		elseif not on and entry.state == "on" then entry.state = "off"; Detach(entry) end
	end
	C.NodesChanged()
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function()
	-- addons set up their layers when they are enabled (at login): look once that is done
	C_Timer.After(0, function()
		C.Scan()
		if ns.mapWindow and ns.mapWindow.map then C.MapMade(ns.mapWindow.map) end
		GatherMate()
	end)
end)

-- For GPS3D (the same nodes and pins in the 3D view)
GPS_API.AddonNodes = function(instance)
	if not (C.Enabled() and GatherMate()) then return nil end
	return C.Nodes(instance)
end
GPS_API.NewAddonPin, GPS_API.SetupAddonPin = C.NewPin, C.SetupPin

function C.SelfTest(Report)
	C.Scan()
	local on, other = {}, {}
	for _, p in ipairs(C.order) do
		local e = C.layers[p]
		if e.state == "on" then on[#on + 1] = tostring(e.owner)
		else other[#other + 1] = ("%s (%s%s)"):format(tostring(e.owner), e.state, e.why and (": " .. e.why) or "") end
	end
	Report("other addons: map layers on the traditional map: %s%s; setting %s", #on > 0 and table.concat(on, ", ") or "none found",
		#other > 0 and ("; not copied: " .. table.concat(other, "; ")) or "", C.Enabled() and "on" or "off")
	if GatherMate() then
		local list = C.Nodes(ns.view and ns.view.map)
		Report("other addons: GatherMate2: %d nodes on this map for the 2D map and the 3D view (list made in %.1f ms; drawn from %d px per tile, at most %d)", #list, C.rebuildMs or 0, PIN_MIN_SCALE, PIN_MAX_2D)
	else
		Report("other addons: GatherMate2 not installed")
	end
end
