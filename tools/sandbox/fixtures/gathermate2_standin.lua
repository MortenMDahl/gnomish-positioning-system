-- A stand-in for GatherMate2 in the sandbox tests: written for the tests, not GatherMate2's code. It
-- offers what GPS's Compat.lua uses of GatherMate2, with the same names and behaviour as GatherMate2
-- (checked against its source, github.com/Nevcairiel/GatherMate2, 2026-10-13):
--   LibStub("AceAddon-3.0"):GetAddon("GatherMate2") with GetNodesForZone(zone, type) (an iterator
--   over coord -> nodeID, filtered), DecodeLoc / EncodeLoc (the same packing), GetNameForNode,
--   db_types, Visible, nodeTextures, nodeIDReplacementMap, phasing, db.profile (scale, alpha,
--   showWorldMap, worldMapIconsInteractive), GetModule("Display") with UpdateWorldMap,
--   ScheduleUpdate, UpdateVisibility and WorldMapDataProvider (a MapCanvas data provider that acquires one
--   "GatherMate2WorldMapPinTemplate" pin per visible node of the map shown), and the global
--   GatherMate2WorldMapPinMixin (OnLoad, OnAcquired, OnMouseEnter, OnMouseLeave, OnClick).
-- The test registers the pin template (S.xmlTemplates) and adds the provider to WorldMapFrame the way
-- GatherMate2's Display:OnEnable does. Calls the stand-in receives are counted in GM_STANDIN.calls.
local floor = math.floor

GM_STANDIN = { calls = { enter = 0, leave = 0, click = {} } }

local libs = rawget(_G, "LibStub") and LibStub.libs or {}
if not rawget(_G, "LibStub") then
	LibStub = setmetatable({ libs = libs }, { __call = function(self, name, silent)
		local l = self.libs[name]
		if not l and not silent then error("LibStub: no library " .. tostring(name)) end
		return l
	end })
	function LibStub:NewLibrary(name) local l = {}; self.libs[name] = l; return l end
	function LibStub:IterateLibraries() return pairs(self.libs) end
end
local AceAddon = LibStub("AceAddon-3.0", true) or LibStub:NewLibrary("AceAddon-3.0")
AceAddon.addons = AceAddon.addons or {}
function AceAddon:GetAddon(name, silent)
	local a = self.addons[name]
	if not a and not silent then error("AceAddon: no addon " .. name) end
	return a
end

local GM = { modules = {} }
AceAddon.addons.GatherMate2 = GM
GM_STANDIN.GM = GM
function GM:GetModule(name, silent)
	local m = self.modules[name]
	if not m and not silent then error("no module " .. name) end
	return m
end

GM.db_types = { "Mining", "Herb Gathering", "Fishing" }
GM.Visible = {}
GM.show = { Mining = "always", ["Herb Gathering"] = "always", Fishing = "never" } -- (GatherMate2's db.show)
GM.db = { profile = { scale = 1.0, alpha = 1, showWorldMap = true, worldMapIconsInteractive = true } }
GM.phasing = {}
GM.nodeIDReplacementMap = { [299] = 201 } -- an old node ID shown as a newer one
GM.names = { Mining = { [201] = "Copper Vein", [202] = "Tin Vein" }, ["Herb Gathering"] = { [401] = "Peacebloom", [402] = "Silverleaf" }, Fishing = { [501] = "Floating Debris" } }
GM.nodeTextures = {
	Mining = { [201] = "Interface\\GPSSandbox\\GM_Copper", [202] = "Interface\\GPSSandbox\\GM_Tin" },
	["Herb Gathering"] = { [401] = "Interface\\GPSSandbox\\GM_Peacebloom", [402] = "Interface\\GPSSandbox\\GM_Silverleaf" },
	Fishing = { [501] = "Interface\\GPSSandbox\\GM_Debris" },
}
GM.gmdbs = { Mining = {}, ["Herb Gathering"] = {}, Fishing = {} }
GM.filter = { Mining = { [201] = true, [202] = true, [299] = true }, ["Herb Gathering"] = { [401] = true, [402] = true }, Fishing = { [501] = true } }

function GM:EncodeLoc(x, y)
	if x > 0.9999 then x = 0.9999 end
	if y > 0.9999 then y = 0.9999 end
	return floor(x * 10000 + 0.5) * 1000000 + floor(y * 10000 + 0.5) * 100
end
function GM:DecodeLoc(id) return floor(id / 1000000) / 10000, floor(id % 1000000 / 100) / 10000 end
function GM:GetNameForNode(nodeType, nodeID) return self.names[nodeType] and self.names[nodeType][nodeID] end
function GM:GetNodesForZone(zone, nodeType, ignoreFilter)
	local data = self.gmdbs[nodeType][zone] or {}
	local filter = self.filter[nodeType]
	return function(_, prev)
		local k, v = next(data, prev)
		while k and not ignoreFilter and not filter[v] do k, v = next(data, k) end
		return k, v
	end, nil, nil
end
-- (tests) a node at zone coordinates x, y
function GM_STANDIN.AddNode(zone, nodeType, nodeID, x, y)
	local db = GM.gmdbs[nodeType]
	db[zone] = db[zone] or {}
	db[zone][GM:EncodeLoc(x, y)] = nodeID
end

local Display = { worldmapPins = {} }
GM.modules.Display = Display
function Display:UpdateVisibility()
	for _, t in ipairs(GM.db_types) do GM.Visible[t] = GM.show[t] == "always" end
end
Display.WorldMapDataProvider = CreateFromMixins(MapCanvasDataProviderMixin or {})
-- (in the game the provider is always on Blizzard's world map; in the sandbox without one it does nothing)
function Display.WorldMapDataProvider:RemoveAllData()
	if not (self.GetMap and self:GetMap()) then return end
	self:GetMap():RemoveAllPinsByTemplate("GatherMate2WorldMapPinTemplate")
	wipe(Display.worldmapPins)
end
function Display.WorldMapDataProvider:RefreshAllData()
	if not (self.GetMap and self:GetMap()) then return end
	self:RemoveAllData()
	if not GM.db.profile.showWorldMap then return end
	Display:UpdateVisibility()
	local map = self:GetMap()
	local uiMapID = map:GetMapID()
	if not uiMapID then return end
	if GM.phasing[uiMapID] then uiMapID = GM.phasing[uiMapID] end
	for _, t in ipairs(GM.db_types) do
		if GM.Visible[t] then
			for coord, nodeID in GM:GetNodesForZone(uiMapID, t) do
				table.insert(Display.worldmapPins, map:AcquirePin("GatherMate2WorldMapPinTemplate", coord, nodeID, t, uiMapID))
			end
		end
	end
end
function Display:UpdateWorldMap() self.WorldMapDataProvider:RefreshAllData() end
function Display:ScheduleUpdate() GM_STANDIN.scheduled = (GM_STANDIN.scheduled or 0) + 1 end -- (GatherMate2: marks its minimap for an update after a new node)

GatherMate2WorldMapPinMixin = CreateFromMixins(MapCanvasPinMixin or {})
function GatherMate2WorldMapPinMixin:OnLoad()
	self:UseFrameLevelType("PIN_FRAME_LEVEL_AREA_POI")
	self:SetScalingLimits(1, 1.0, 1.2)
end
function GatherMate2WorldMapPinMixin:OnAcquired(coord, nodeID, nodeType, pinZone)
	local x, y = GM:DecodeLoc(coord)
	self:SetPosition(x, y)
	self.coords, self.nodeID = coord, GM.nodeIDReplacementMap[nodeID] or nodeID
	self.title, self.zone, self.nodeType, self.worldmap = GM:GetNameForNode(nodeType, self.nodeID), pinZone, nodeType, true
	self:SetSize(12 * GM.db.profile.scale, 12 * GM.db.profile.scale)
	self:SetAlpha(GM.db.profile.alpha)
	self.texture:SetTexture(GM.nodeTextures[nodeType][self.nodeID])
end
function GatherMate2WorldMapPinMixin:OnMouseEnter()
	GM_STANDIN.calls.enter = GM_STANDIN.calls.enter + 1
	GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
	GameTooltip:SetText(self.title or "?")
	GameTooltip:Show()
end
function GatherMate2WorldMapPinMixin:OnMouseLeave()
	GM_STANDIN.calls.leave = GM_STANDIN.calls.leave + 1
	GameTooltip:Hide()
end
function GatherMate2WorldMapPinMixin:OnClick(button)
	table.insert(GM_STANDIN.calls.click, { button = button, title = self.title, zone = self.zone, coords = self.coords, worldmap = self.worldmap })
end
GatherMate2WorldMapPinMixin.SetPassThroughButtons = function() end

-- The pin template (GatherMate2.xml: a 12 x 12 frame with the mixin and an OVERLAY texture "texture")
SANDBOX.xmlTemplates = SANDBOX.xmlTemplates or {}
SANDBOX.xmlTemplates.GatherMate2WorldMapPinTemplate = function(f)
	Mixin(f, GatherMate2WorldMapPinMixin)
	f:SetSize(12, 12)
	f.texture = f:CreateTexture(nil, "OVERLAY")
	f.texture:SetAllPoints()
	f:EnableMouse(true)
	f:Hide()
end
