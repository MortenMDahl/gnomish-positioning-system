-- GPS's page in the game's Options > AddOns (Blizzard's Settings panel, vertical list): how the map
-- opens, the 3D view's settings (GPS3D hands them over as GPS3D_API.settings) and the position fixes.
-- /gps options opens it. Every control reads and writes the saved settings directly and applies at
-- once, the same as the slash commands; "Defaults" on the panel gives a fresh install's values.
--
-- A control is a plain table, so GPS3D can describe its own without the Settings API:
--   { kind = "header", name }
--   { kind = "check", key, name, tooltip, default, get, set }
--   { kind = "choice", key, name, tooltip, default, choices = function() return { { value, label }, ... } end, get, set }
--   { kind = "slider", key, name, tooltip, default, min, max, step, format = function(value) -> text, get, set }
--   { kind = "button", name, text, tooltip, click }
-- key: a name unique among all addons (the panel looks settings up by it).
local addonName, ns = ...

local function DB() return ns.db end

ns.settings = {
	{ kind = "header", name = "Map window" },
	{
		kind = "choice", key = "GPS_OpenAs", name = "Opens as",
		tooltip = "What /gps and the key binding open. Picking a mode with the mode ring changes this too.",
		default = ns.defaults.mode,
		choices = function()
			local list = {}
			for _, name in ipairs(ns.AvailableModes()) do list[#list + 1] = { name, ns.modeNames[name] } end
			return list
		end,
		get = function()
			for _, name in ipairs(ns.AvailableModes()) do if name == DB().mode then return name end end
			return "2D" -- the chosen mode is not here (GPS3D turned off)
		end,
		set = function(v) DB().mode = v; ns.autoMap = nil end,
	},
	{
		kind = "check", key = "GPS_AutoTraditional", name = "Traditional map where GPS can't show you",
		tooltip = "In dungeons, raids and other places where the game gives no position, open (and switch to) the traditional map, and back to your mode outside. Off: the map stays in the mode you chose.",
		default = ns.defaults.autoTraditional,
		get = function() return DB().autoTraditional end,
		set = function(v) DB().autoTraditional = v end,
	},
	{
		kind = "button", name = "Window", text = "Reset",
		tooltip = "Put the map window back in the middle of the screen at its first size (/gps reset).",
		click = function() ns.ResetWindow() end,
	},
	{ kind = "header", name = "Quests" },
	{
		kind = "check", key = "GPS_Quests", name = "Your quests on the 2D map and in the 3D view",
		tooltip = "A marker for each quest in your log (click one to track it) and the tracked quest's objective area. Blizzard's own option to show quest objectives on the map turns them off too. The traditional map shows quests as Blizzard's map does.",
		default = ns.defaults.quests,
		get = function() return DB().quests end,
		set = function(v) DB().quests = v; ns.quests.Changed() end,
	},
	{ kind = "header", name = "Other addons" },
	{
		kind = "check", key = "GPS_AddonMarkers", name = "Other addons' map markers",
		tooltip = "Markers other addons put on Blizzard's world map, in GPS's windows: the map layers of GatherMate2, HandyNotes (and its plugins) and other addons on the traditional map, and GatherMate2's nodes on the 2D map and in the 3D view. GPS uses those addons' own markers while they are installed. Off: GPS's windows show only its own.",
		default = ns.defaults.addonMarkers,
		get = function() return DB().addonMarkers end,
		set = function(v) DB().addonMarkers = v; ns.compat.SettingChanged() end,
	},
}

ns.settingsFixes = {
	{ kind = "header", name = "Position fixes" },
	{
		kind = "check", key = "GPS_SwapAxes", name = "Swap the map's axes",
		tooltip = "Only if /gps test reports SWAPPED: your arrow stands on the wrong spot (/gps swapaxes).",
		default = false,
		get = function() return DB().swapAxes and true or false end,
		set = function(v) DB().swapAxes = v; if ns.frame and ns.frame:IsShown() then ns.Layout() end end,
	},
	{
		kind = "check", key = "GPS_FlipFacing", name = "Turn the arrow the other way",
		tooltip = "Only if your arrow turns the opposite way to you (/gps flipfacing).",
		default = false,
		get = function() return DB().flipFacing and true or false end,
		set = function(v) DB().flipFacing = v; if ns.frame and ns.frame:IsShown() then ns.Layout() end end,
	},
	{ kind = "header", name = "Debug log" },
	{
		kind = "check", key = "GPS_DebugLog", name = "Keep a debug log",
		tooltip = "GPS writes what it does (windows, maps, your position, quests, settings, frame times, errors) to a log that the game saves on /reload or logout, in WTF\\Account\\<account>\\SavedVariables\\GnomishPositioningSystem.lua: the file to hand over when something is wrong (/gps debug).",
		default = false,
		get = function() return ns.debugOn end,
		set = function(v) ns.DebugCommand(v and "on" or "off") end,
	},
	{
		kind = "button", name = "Debug log", text = "Show",
		tooltip = "The newest lines of the debug log in a window, to copy (Ctrl+A, Ctrl+C) (/gps debug show).",
		click = function() ns.DebugCommand("show") end,
	},
}

-- Adds one control to the category; returns the setting (nil for headers and buttons).
local function Add(category, layout, d)
	if d.kind == "header" then
		layout:AddInitializer(CreateSettingsListSectionHeaderInitializer(d.name, d.tooltip))
		return
	elseif d.kind == "button" then
		layout:AddInitializer(CreateSettingsButtonInitializer(d.name, d.text, function(...) ns.Log("SETTING", "%s: %s clicked", d.name, d.text); return d.click(...) end, d.tooltip, true))
		return
	end
	local varType = d.kind == "check" and Settings.VarType.Boolean or d.kind == "slider" and Settings.VarType.Number or Settings.VarType.String
	local function get()
		local v = d.get()
		if v == nil then return d.default end
		return v
	end
	local function set(v)
		ns.Log("SETTING", "%s = %s", d.key, tostring(v))
		d.set(v)
	end
	local setting = Settings.RegisterProxySetting(category, d.key, varType, d.name, d.default, get, set)
	if d.kind == "check" then
		Settings.CreateCheckbox(category, setting, d.tooltip)
	elseif d.kind == "slider" then
		local options = Settings.CreateSliderOptions(d.min, d.max, d.step)
		options:SetLabelFormatter(MinimalSliderWithSteppersMixin.Label.Right, d.format)
		Settings.CreateSlider(category, setting, options, d.tooltip)
	else
		local function options()
			local container = Settings.CreateControlTextContainer()
			for _, c in ipairs(d.choices()) do container:Add(c[1], c[2]) end
			return container:GetData()
		end
		Settings.CreateDropdown(category, setting, options, d.tooltip)
	end
	return setting
end

-- Builds the page once every addon has loaded (GPS3D's controls go in the middle). Without the
-- Settings API (an older client) there is no page; the slash commands still work.
function ns.RegisterSettings()
	if ns.settingsCategory or not (Settings and Settings.RegisterVerticalLayoutCategory) then return end
	local category, layout = Settings.RegisterVerticalLayoutCategory("Gnomish Positioning System")
	local lists = { ns.settings, GPS3D_API and GPS3D_API.settings, ns.settingsFixes }
	for i = 1, 3 do
		for _, d in ipairs(lists[i] or {}) do Add(category, layout, d) end
	end
	Settings.RegisterAddOnCategory(category)
	ns.settingsCategory = category
	ns.Log("SETTING", "settings page registered (category %s)", tostring(category.GetID and category:GetID()))
end

-- /gps options
function ns.OpenSettings()
	if ns.settingsCategory then
		Settings.OpenToCategory(ns.settingsCategory:GetID())
	else
		print("|cff33ff99GPS|r: the game's Settings panel is not available here; /gps reset, swapaxes and flipfacing still work.")
	end
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function(self)
	self:UnregisterEvent("PLAYER_LOGIN")
	ns.RegisterSettings()
end)
