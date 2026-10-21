-- Gnomish Positioning System: which map the game's map key (Blizzard's "Toggle World Map" binding,
-- M by default) opens: GPS or Blizzard's own map ("Map & Quest Log"). Since 2026-10-21.
--
-- The choice (db.mapKey, "gps" or "blizzard"; Blizzard's map by default) is set by a globe button
-- in the top right of every GPS window (ApplyChrome's ui.globe: click for Blizzard's map) and one on
-- Blizzard's map, left of its maximize button (click for GPS), by the settings page and by
-- /gps mapkey gps|blizzard. Either globe switches at once: the window open closes and the other map
-- opens (GPS on the place Blizzard's map showed, when that is a zone GPS has).
--
-- How the key is taken (the game's own way for an addon to rebind a key, nothing of Blizzard's
-- replaced): with the choice on GPS, every key bound to TOGGLEWORLDMAP gets an override binding to
-- GPS's own GPS_TOGGLE (SetOverrideBinding(owner, false, key, "GPS_TOGGLE")); with the choice on
-- Blizzard's map there are none (ClearOverrideBindings(owner)), so nothing of Blizzard's changes.
-- Override bindings sit over the player's bindings without changing them (nothing is saved to the
-- bindings file, and they are gone when GPS is not loaded), and the key then runs GPS's binding,
-- never Blizzard's ToggleWorldMap, so Blizzard's map code is not run from GPS's (tainted) code. The
-- game refuses binding changes in combat, so a change in combat waits for PLAYER_REGEN_ENABLED;
-- UPDATE_BINDINGS (the player rebinds the map key, or the bindings load at login) applies the
-- choice again to the keys bound then. The quest log key (TOGGLEQUESTLOG) is left alone.
-- In Forever's source (Gethe/wow-ui-source, branch forever): Bindings_Standard.xml and
-- Bindings_Camelot.xml bind TOGGLEWORLDMAP to ToggleWorldMap(); Blizzard_WorldMap.lua's
-- ToggleWorldMap calls WorldMapFrame:HandleUserActionToggleSelf (QuestLogOwnerMixin), which shows
-- and hides the map with ShowUIPanel / HideUIPanel; those refuse callers outside Blizzard's code in
-- combat (UIParentPanelManager.lua, CheckProtectedFunctionsAllowed), so GPS opens or closes
-- Blizzard's map only out of combat.
--
-- What is attached to Blizzard's map: one button, a child of WorldMapFrame.BorderFrame anchored
-- to the left of BorderFrame.MaximizeMinimizeFrame (Blizzard_WorldMap.xml); no field of Blizzard's
-- frames is written and no Blizzard function is replaced or hooked.
local addonName, ns = ...

local COMMAND = "TOGGLEWORLDMAP"       -- Blizzard's map key
local GPS_COMMAND = "GPS_TOGGLE"       -- GPS's own binding (Bindings.xml)
local WORLDMAP_GLOBE = 28              -- the globe ring on Blizzard's map, the size of its maximize button (Camelot)
local ZONE = Enum and Enum.UIMapType and Enum.UIMapType.Zone or 3

local mk = { applied = {} }            -- applied: the keys overridden now
ns.mapkey = mk
local owner = CreateFrame("Frame")     -- owns the override bindings: ClearOverrideBindings(owner) removes only GPS's

local function Say(text) print("|cff33ff99GPS|r: " .. text) end
local function InCombat() return InCombatLockdown ~= nil and InCombatLockdown() == true end

function mk.Choice()
	return ns.db and ns.db.mapKey == "gps" and "gps" or "blizzard"
end

-- The keys bound to Blizzard's map key (the player's bindings, not the overrides).
local function Keys()
	if not GetBindingKey then return {} end
	return { GetBindingKey(COMMAND) }
end
mk.Keys = Keys

local function KeyText(list)
	if #list == 0 then return "no key" end
	return table.concat(list, ", ")
end

------------------------------------------------------------------------------------------------
-- The override bindings
------------------------------------------------------------------------------------------------
-- Puts the choice into effect: with GPS, an override on each map key; with Blizzard's map, none.
-- In combat (the game refuses SetOverrideBinding there) it waits for the end of combat.
function mk.Apply()
	if not ns.db then return end
	local want = mk.Choice() == "gps" and Keys() or {}
	local same = #want == #mk.applied
	for i = 1, #want do if want[i] ~= mk.applied[i] then same = false end end
	if same then
		if mk.pending then owner:UnregisterEvent("PLAYER_REGEN_ENABLED") end
		mk.pending = nil
		return
	end
	if InCombat() then
		if not mk.pending then ns.Log("MAPKEY", "in combat: the map key's binding changes when combat ends") end
		mk.pending = true
		owner:RegisterEvent("PLAYER_REGEN_ENABLED")
		return
	end
	if not (ClearOverrideBindings and SetOverrideBinding) then return end
	mk.busy = true -- (the game may answer each change with UPDATE_BINDINGS; that one is ours)
	ClearOverrideBindings(owner)
	for _, key in ipairs(want) do SetOverrideBinding(owner, false, key, GPS_COMMAND) end
	mk.busy = nil
	mk.applied = want
	if mk.pending then owner:UnregisterEvent("PLAYER_REGEN_ENABLED") end
	mk.pending = nil
	ns.Log("MAPKEY", "map key opens %s; overridden: %s", mk.Choice() == "gps" and "GPS" or "Blizzard's map", KeyText(want))
end

owner:RegisterEvent("PLAYER_LOGIN")
owner:RegisterEvent("UPDATE_BINDINGS")
owner:RegisterEvent("ADDON_LOADED")
owner:SetScript("OnEvent", function(self, event, name)
	if event == "ADDON_LOADED" then
		if name == "Blizzard_WorldMap" then mk.MakeWorldMapButton() end
		return
	end
	if event == "UPDATE_BINDINGS" and mk.busy then return end
	if event == "PLAYER_LOGIN" then mk.MakeWorldMapButton() end
	mk.Apply()
end)

------------------------------------------------------------------------------------------------
-- Choosing, and switching between the two maps
------------------------------------------------------------------------------------------------
function mk.Set(choice)
	if not ns.db then return end
	choice = choice == "gps" and "gps" or "blizzard"
	if choice ~= ns.db.mapKey then ns.Log("MAPKEY", "choice: %s", choice) end
	ns.db.mapKey = choice
	mk.Apply()
	ns.UpdateChromes()
	mk.UpdateWorldMapButton()
end

-- With the map key on GPS, Blizzard's map (opened through the quest log key or the minimap) closes
-- as GPS opens. Never in combat, where the game refuses it.
function mk.CloseBlizzard()
	if mk.Choice() ~= "gps" or InCombat() then return end
	if WorldMapFrame and WorldMapFrame:IsShown() and HideUIPanel then HideUIPanel(WorldMapFrame) end
end

-- Where Blizzard's map looks, for GPS: "you" while it shows your map, the middle of its view on a
-- zone (or a dungeon, micro or orphan map), or nil (a continent or the world: GPS opens as last time).
function mk.BlizzardFocus()
	local map = WorldMapFrame
	local id = map and map.GetMapID and map:GetMapID()
	if not id then return nil end
	local mine = MapUtil and MapUtil.GetDisplayableMapForPlayer and MapUtil.GetDisplayableMapForPlayer() or C_Map.GetBestMapForUnit("player")
	if id == mine then return "you" end
	local info = C_Map.GetMapInfo(id)
	if not (info and info.mapType and info.mapType >= ZONE and CreateVector2D) then return nil end
	local x, y = 0.5, 0.5
	local rect = map.GetViewRect and map:GetViewRect()
	if rect and rect.GetCenter then x, y = rect:GetCenter() end
	local continent, world = C_Map.GetWorldPosFromMapPos(id, CreateVector2D(x, y))
	if not (continent and world) then return nil end
	local gx, gy = ns.WorldToGrid(world:GetXY())
	return { map = continent, gx = gx, gy = gy }
end

-- The globe on Blizzard's map: the map key opens GPS, and GPS opens now in place of Blizzard's map.
function mk.UseGPS()
	mk.Set("gps")
	if InCombat() then
		Say("the map key opens GPS when combat ends (the game allows no binding changes, and no closing of Blizzard's map by an addon, in combat).")
		return
	end
	local focus = mk.BlizzardFocus()
	ns.Log("MAPKEY", "switch to GPS, focus %s", ns.LogValue(focus))
	if WorldMapFrame and WorldMapFrame:IsShown() and HideUIPanel then HideUIPanel(WorldMapFrame) end
	if not ns.ShownMode() then ns.OpenDefault(focus) end
end

-- The globe in GPS's windows: the map key opens Blizzard's map, and it opens now in place of GPS.
function mk.UseBlizzard()
	mk.Set("blizzard")
	if InCombat() then
		Say("the map key opens Blizzard's map when combat ends (the game allows no binding changes, and no opening of Blizzard's map by an addon, in combat).")
		return
	end
	ns.Log("MAPKEY", "switch to Blizzard's map")
	local _, m = ns.ShownMode()
	if m then m.Frame():Hide() end
	if WorldMapFrame and not WorldMapFrame:IsShown() and ToggleWorldMap then ToggleWorldMap() end
end

-- The globes' tooltip: onBlizzard, the one on Blizzard's map.
function mk.Tooltip(onBlizzard)
	local keys = KeyText(Keys())
	local opens = mk.Choice() == "gps" and "GPS" or "Blizzard's map"
	local tip = { "Map key: " .. opens, ("The map key (%s) opens %s."):format(keys, opens) }
	if onBlizzard then
		tip[3] = "Click: open GPS here, and the map key opens GPS from now on."
	else
		tip[3] = "Click: open Blizzard's map, and the map key opens Blizzard's map from now on."
	end
	if mk.pending then tip[#tip + 1] = "(Waiting for the end of combat to change the key.)" end
	return tip
end

------------------------------------------------------------------------------------------------
-- The globe on Blizzard's map
------------------------------------------------------------------------------------------------
function mk.MakeWorldMapButton()
	if mk.wmButton or not (WorldMapFrame and ns.RingButton) then return end
	local border = WorldMapFrame.BorderFrame or WorldMapFrame
	-- only real frames count as anchors (a map built differently may have a method or nothing under these names)
	local function Frame(x) return type(x) == "table" and type(x.GetObjectType) == "function" and x or nil end
	local anchor = Frame(border.MaximizeMinimizeFrame) or Frame(border.CloseButton) or Frame(WorldMapFrame.CloseButton)
	local b = ns.RingButton(border, function() return mk.Tooltip(true) end, WORLDMAP_GLOBE)
	b:SetIcon(ns.MEDIA .. "Globe", 0.62)
	if anchor then
		b:SetPoint("RIGHT", anchor, "LEFT", -1, 0)
		b:SetFrameLevel(anchor:GetFrameLevel())
	else
		b:SetPoint("TOPRIGHT", border, "TOPRIGHT", -64, -2)
	end
	b:SetScript("OnClick", function() mk.UseGPS() end)
	mk.wmButton = b
	mk.UpdateWorldMapButton()
	ns.Log("MAPKEY", "globe on Blizzard's map, left of its %s", anchor == border.MaximizeMinimizeFrame and "maximize button" or anchor and "close button" or "top right corner")
end

function mk.UpdateWorldMapButton()
	if mk.wmButton then mk.wmButton:SetActive(mk.Choice() == "gps") end
end

------------------------------------------------------------------------------------------------
-- /gps mapkey, /gps test
------------------------------------------------------------------------------------------------
function mk.Command(arg)
	arg = (arg or ""):lower()
	if arg == "gps" or arg == "blizzard" then mk.Set(arg)
	elseif arg ~= "" then Say("/gps mapkey gps|blizzard") return end
	Say(("the map key (%s) opens %s%s."):format(KeyText(Keys()), mk.Choice() == "gps" and "GPS" or "Blizzard's map", mk.pending and " once combat ends" or ""))
end

function mk.SelfTest(Report)
	local keys = Keys()
	local took = {}
	for _, key in ipairs(mk.applied) do
		local action = GetBindingAction and GetBindingAction(key, true)
		took[#took + 1] = ("%s -> %s"):format(key, tostring(action))
	end
	Report("map key: opens %s; Blizzard's map key (%s): %s; overridden: %s%s; globe on Blizzard's map: %s",
		mk.Choice() == "gps" and "GPS" or "Blizzard's map", COMMAND, KeyText(keys),
		#took > 0 and table.concat(took, ", ") or "none", mk.pending and " (waiting for the end of combat)" or "",
		mk.wmButton and "yes" or "no (WorldMapFrame not found)")
end
