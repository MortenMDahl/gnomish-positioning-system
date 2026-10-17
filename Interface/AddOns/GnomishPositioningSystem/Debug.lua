-- Gnomish Positioning System: debug log (/gps debug). Off by default, and then it costs one check
-- per log call. On, GPS (and GPS3D, through GPS_API.Log) writes what it does to a log kept in its
-- saved variables (GnomishPositioningSystemLog): the game writes it to disk on /reload, logout or
-- quitting (not on a crash), as WTF\Account\<account>\SavedVariables\GnomishPositioningSystem.lua.
-- Addons cannot write any other file. That file is what to hand over (TESTING.md, "Debug log").
--
-- Size: at most about 1 MB, whatever happens (MAX_BYTES below): the oldest lines go first.
--
-- Logged: a header (game build, versions, screen, settings) at each login or reload and when
-- turned on; window and mode changes; map, zone and floor changes; your position about once a
-- second while you move; the view (2D, 3D, traditional map) when it changes; quest lookups;
-- settings changes; slash commands; self-test lines; 3D and 2D frame times every 5 seconds; memory
-- every 30 seconds; game events that matter (loading screens, zones, combat, UI scale, blocked
-- actions, which point to taint); and every Lua error that mentions GPS, with its stack.
--
-- /gps debug on | off | clear | show (a window to copy from) | mark <text> (a note in the log)
local addonName, ns = ...

-- The log never grows past MAX_BYTES of text (about 1 MB on disk, some 10,000 lines: two to three
-- hours of play with the log on, more when you stand still): past it, the oldest lines are dropped
-- down to KEEP_BYTES, so a log left on by accident stays that size for good. A line is cut at
-- MAX_LINE characters (a long error message keeps its start; its stack is one line per frame).
local MAX_BYTES, KEEP_BYTES = 1000000, 800000
local MAX_LINE = 400
local SHOW_LINES = 1500                  -- lines in the copy window (all of them are in the file)
local SAMPLE = 1                         -- seconds between position and view checks
local PERF_EVERY, MEMORY_EVERY = 5, 30   -- seconds between frame-time and memory lines

ns.debugOn = false
local log -- GnomishPositioningSystemLog: { on, lines = { ... } }

local function Stamp()
	return (date and date("%H:%M:%S") or "--:--:--") .. (" %9.3f"):format(GetTime and GetTime() or 0)
end

local function Add(line)
	if #line > MAX_LINE then line = line:sub(1, MAX_LINE - 3) .. "..." end
	local lines = log.lines
	lines[#lines + 1] = line
	log.bytes = (log.bytes or 0) + #line + 1
	if log.bytes > MAX_BYTES then
		-- drop the oldest lines down to KEEP_BYTES (one new table, not a remove per line)
		local bytes, first = log.bytes, 1
		while bytes > KEEP_BYTES and first < #lines do
			bytes = bytes - #lines[first] - 1
			first = first + 1
		end
		local keep = { ("%s %-8s (older lines dropped: the log keeps its newest %d KB)"):format(Stamp(), "SESSION", KEEP_BYTES / 1000) }
		bytes = bytes + #keep[1] + 1
		for i = first, #lines do keep[#keep + 1] = lines[i] end
		log.lines, log.bytes = keep, bytes
	end
end

-- ns.Log(category, format, ...): one line, when the debug log is on. Arguments are formatted with
-- %s / %d / %.2f as usual; nil and other values are safe with %s.
function ns.Log(cat, fmt, ...)
	if not ns.debugOn then return end
	local ok, msg = pcall(string.format, fmt, ...)
	if not ok then
		local parts = { tostring(fmt) }
		for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
		msg = table.concat(parts, " ")
	end
	Add(("%s %-8s %s"):format(Stamp(), cat, msg))
end

-- Values for the log: tables as k=v lists (one level), numbers short.
local function Show(v)
	local t = type(v)
	if t == "number" then return (math.floor(v) == v) and tostring(v) or ("%.3f"):format(v) end
	if t ~= "table" then return tostring(v) end
	local parts = {}
	for k, x in pairs(v) do parts[#parts + 1] = tostring(k) .. "=" .. (type(x) == "table" and "{...}" or Show(x)) end
	table.sort(parts)
	return "{" .. table.concat(parts, ", ") .. "}"
end
ns.LogValue = Show

------------------------------------------------------------------------------------------------
-- The header: what an agent needs to know about this session
------------------------------------------------------------------------------------------------
local function Meta(addon, key)
	local f = (C_AddOns and C_AddOns.GetAddOnMetadata) or GetAddOnMetadata
	return f and f(addon, key) or "?"
end
function ns.LogHeader(why)
	if not ns.debugOn then return end
	local version, build, buildDate, interface = GetBuildInfo()
	ns.Log("SESSION", "---- %s ----", why)
	ns.Log("SESSION", "game %s (build %s, %s), interface %s, locale %s", tostring(version), tostring(build), tostring(buildDate), tostring(interface), GetLocale and GetLocale() or "?")
	local loaded = C_AddOns and C_AddOns.IsAddOnLoaded or IsAddOnLoaded
	ns.Log("SESSION", "GPS %s; GPS3D %s", Meta(addonName, "Version"), loaded and loaded("GPS3D") and Meta("GPS3D", "Version") or "not loaded")
	ns.Log("SESSION", "screen %sx%s, UI scale %s, map window effective scale %s", Show(GetScreenWidth()), Show(GetScreenHeight()),
		Show(UIParent:GetScale()), ns.frame and Show(ns.frame:GetEffectiveScale()) or "?")
	local nMaps = 0
	for _ in pairs(ns.Maps or {}) do nMaps = nMaps + 1 end
	ns.Log("SESSION", "data: %d maps; APIs: Settings %s, quests %s, map canvas %s, error hook %s", nMaps,
		tostring(Settings ~= nil), tostring(C_QuestLog ~= nil and C_QuestLog.GetQuestsOnMap ~= nil), tostring(MapCanvasMixin ~= nil),
		tostring(seterrorhandler ~= nil))
	if ns.quests then
		local known = {}
		for map, zones in pairs(ns.quests.zonesOf or {}) do known[#known + 1] = ("map %s: %d zones"):format(tostring(map), #zones) end
		ns.Log("SESSION", "quests: shown %s; %d in the list; zones known: %s", tostring(ns.quests.Enabled()), #(ns.quests.cache.list or {}),
			#known > 0 and table.concat(known, ", ") or "none yet")
	end
	ns.Log("SESSION", "settings GPS %s", Show(ns.db or {}))
	ns.Log("SESSION", "settings GPS3D %s", Show(GPS3D_DB or {}))
	local X, Y, Z, instance = UnitPosition("player")
	ns.Log("SESSION", "UnitPosition %s, %s, %s, map %s; zone %s / %s; in instance %s", Show(X), Show(Y), Show(Z), Show(instance),
		tostring(GetZoneText and GetZoneText()), tostring(GetSubZoneText and GetSubZoneText()), tostring(IsInInstance and IsInInstance()))
end

------------------------------------------------------------------------------------------------
-- Errors: every Lua error that mentions GPS's files, with its stack (the game's own handler still runs)
------------------------------------------------------------------------------------------------
local previousHandler, ourHandler
local function Mine(text) return text and (text:find("GnomishPositioningSystem", 1, true) or text:find("GPS3D", 1, true)) end
local function InstallErrors()
	if ourHandler or not (seterrorhandler and geterrorhandler) then return end
	previousHandler = geterrorhandler()
	ourHandler = function(msg, ...)
		local text = tostring(msg)
		local stack = debugstack and debugstack(2) or ""
		if ns.debugOn and (Mine(text) or Mine(stack)) then
			for line in text:gmatch("[^\n]+") do pcall(ns.Log, "ERROR", "%s", line) end -- one log line per line of text
			for line in (stack or ""):gmatch("[^\n]+") do pcall(ns.Log, "ERROR", "  %s", line) end
		end
		if previousHandler then return previousHandler(msg, ...) end
	end
	seterrorhandler(ourHandler)
end
local function RemoveErrors()
	if ourHandler and geterrorhandler() == ourHandler then seterrorhandler(previousHandler) end
	ourHandler, previousHandler = nil, nil
end

------------------------------------------------------------------------------------------------
-- Game events worth a line
------------------------------------------------------------------------------------------------
local EVENTS = {
	"PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA", "ZONE_CHANGED", "ZONE_CHANGED_INDOORS",
	"PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED", "UI_SCALE_CHANGED", "DISPLAY_SIZE_CHANGED",
	"SUPER_TRACKING_CHANGED", "ADDON_ACTION_BLOCKED", "ADDON_ACTION_FORBIDDEN", "LUA_WARNING", "PLAYER_LOGOUT",
}
local events = CreateFrame("Frame")
events:SetScript("OnEvent", function(_, event, ...)
	if event == "PLAYER_LOGOUT" then ns.Log("EVENT", "PLAYER_LOGOUT (the log is written now)") return end
	local args = {}
	for i = 1, select("#", ...) do args[#args + 1] = tostring((select(i, ...))) end
	local cat = (event == "ADDON_ACTION_BLOCKED" or event == "ADDON_ACTION_FORBIDDEN") and "TAINT" or "EVENT"
	ns.Log(cat, "%s %s", event, table.concat(args, ", "))
end)

------------------------------------------------------------------------------------------------
-- Sampling: position, the view of each window, frame times, memory
------------------------------------------------------------------------------------------------
local sampler = CreateFrame("Frame")
sampler:Hide()
local last = { pos = nil, view = nil, view3 = nil, map = nil, mode = nil, t = 0, perf = 0, mem = 0, quiet = 0 }
ns.perf2D = nil -- { n, sum, max } of ns.Layout times while on (Core.lua)

local function WindowState()
	local name = ns.ShownMode and ns.ShownMode()
	return name or "none"
end

local function Sample()
	-- your position: when you moved more than 2 yards or turned, else every 10 s
	local map, gx, gy, facing, z = ns.PlayerPosition()
	local pos
	if map then
		pos = ("map %s at %.2f, %.2f (tile %d_%d), facing %.2f, height %s; %s / %s"):format(tostring(map), gx, gy, math.floor(gx), math.floor(gy),
			facing or -1, Show(z), tostring(GetZoneText()), tostring(GetSubZoneText()))
	else
		pos = ("no position (%s / %s, in instance %s)"):format(tostring(GetZoneText()), tostring(GetSubZoneText()), tostring(IsInInstance and IsInInstance()))
	end
	last.quiet = last.quiet + SAMPLE
	if map and last.gx then
		local moved = math.abs(gx - last.gx) + math.abs(gy - last.gy) > 2 / (1600 / 3) or math.abs((facing or 0) - (last.facing or 0)) > 0.2
		if moved or last.quiet >= 10 then ns.Log("POS", "%s", pos); last.quiet = 0 end
	elseif pos ~= last.pos then
		ns.Log("POS", "%s", pos); last.quiet = 0
	end
	last.pos, last.gx, last.gy, last.facing = pos, map and gx, map and gy, facing
	-- which window, and what it shows, when that changes
	local mode = WindowState()
	if mode ~= last.mode then ns.Log("WINDOW", "shown: %s", mode); last.mode = mode end
	local v = ns.view
	if mode == "2D" and v then
		local s = ("2D map %s centre %.2f, %.2f scale %.0f px/tile, follow %s; title %s"):format(tostring(v.map), v.cx or 0, v.cy or 0, v.scale or 0,
			tostring(v.follow), ns.ui and tostring(ns.ui.title:GetText()) or "?")
		if s ~= last.view then ns.Log("VIEW", "%s", s); last.view = s end
	elseif mode == "3D" and GPS3D_API and GPS3D_API.DebugState then
		local s = GPS3D_API.DebugState()
		if s ~= last.view3 then ns.Log("VIEW", "%s", s); last.view3 = s end
	elseif mode == "Map" and ns.mapWindow and ns.mapWindow.map then
		local mw = ns.mapWindow
		local s = ("traditional map %s (%s), follow %s, zoom %.2f"):format(tostring(mw.map:GetMapID()), tostring(mw.ui.title:GetText()), tostring(mw.follow),
			mw.map.GetCanvasZoomPercent and mw.map:GetCanvasZoomPercent() or -1)
		if s ~= last.map then ns.Log("VIEW", "%s", s); last.map = s end
	end
end

local function Perf()
	local p = ns.perf2D
	if p and p.n > 0 then
		ns.Log("PERF", "2D: %d layouts, %.2f ms average, %.2f ms worst", p.n, p.sum / p.n, p.max)
		p.n, p.sum, p.max = 0, 0, 0
	end
	local q = GPS3D_API and GPS3D_API.TakePerf and GPS3D_API.TakePerf()
	if q then ns.Log("PERF", "%s", q) end
	if GetFramerate then ns.Log("PERF", "game %.0f fps", GetFramerate()) end
end

local function Memory()
	local kb = collectgarbage("count")
	local gps, gps3d
	if UpdateAddOnMemoryUsage and GetAddOnMemoryUsage then
		UpdateAddOnMemoryUsage()
		gps, gps3d = GetAddOnMemoryUsage(addonName), GetAddOnMemoryUsage("GPS3D")
	end
	ns.Log("MEMORY", "Lua %.1f MB in all%s", kb / 1024, (gps or 0) > 0 and (", GPS %.1f MB, GPS3D %.1f MB"):format(gps / 1024, (gps3d or 0) / 1024) or "")
end

sampler:SetScript("OnUpdate", function(_, elapsed)
	last.t, last.perf, last.mem = last.t + elapsed, last.perf + elapsed, last.mem + elapsed
	if last.t >= SAMPLE then last.t = 0; local ok, err = pcall(Sample); if not ok then ns.Log("ERROR", "sampler: %s", err) end end
	if last.perf >= PERF_EVERY then last.perf = 0; pcall(Perf) end
	if last.mem >= MEMORY_EVERY then last.mem = 0; pcall(Memory) end
end)

------------------------------------------------------------------------------------------------
-- On and off
------------------------------------------------------------------------------------------------
local function Start(why)
	ns.debugOn = true
	log.on = true
	ns.perf2D = { n = 0, sum = 0, max = 0 }
	for _, e in ipairs(EVENTS) do pcall(events.RegisterEvent, events, e) end
	InstallErrors()
	last.pos, last.view, last.view3, last.map, last.mode, last.gx = nil, nil, nil, nil, nil, nil
	sampler:Show()
	ns.LogHeader(why)
end
local function Stop()
	ns.Log("SESSION", "debug log off")
	ns.debugOn = false
	log.on = false
	ns.perf2D = nil
	events:UnregisterAllEvents()
	RemoveErrors()
	sampler:Hide()
end

-- The copy window: the newest lines in a text box (Ctrl+A, Ctrl+C).
local window
local function ShowWindow()
	if not window then
		window = CreateFrame("Frame", "GPS_DebugFrame", UIParent, "BackdropTemplate")
		window:SetSize(760, 480)
		window:SetPoint("CENTER")
		window:SetFrameStrata("DIALOG")
		window:SetMovable(true)
		window:EnableMouse(true)
		window:RegisterForDrag("LeftButton")
		window:SetScript("OnDragStart", window.StartMoving)
		window:SetScript("OnDragStop", window.StopMovingOrSizing)
		window:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
		window:SetBackdropColor(0.04, 0.05, 0.06, 0.96)
		window:SetBackdropBorderColor(0, 0, 0, 1)
		tinsert(UISpecialFrames, "GPS_DebugFrame")
		local title = window:CreateFontString(nil, "OVERLAY", "GameFontNormal")
		title:SetPoint("TOPLEFT", 12, -10)
		window.title = title
		local close = CreateFrame("Button", nil, window)
		close:SetSize(22, 22)
		close:SetPoint("TOPRIGHT", -6, -6)
		close:SetNormalAtlas("RedButton-Exit")
		close:SetPushedAtlas("RedButton-exit-pressed")
		close:SetHighlightAtlas("RedButton-Highlight", "ADD")
		close:SetScript("OnClick", function() window:Hide() end)
		local scroll = CreateFrame("ScrollFrame", nil, window, "UIPanelScrollFrameTemplate")
		scroll:SetPoint("TOPLEFT", 12, -34)
		scroll:SetPoint("BOTTOMRIGHT", -32, 12)
		local box = CreateFrame("EditBox", nil, scroll)
		box:SetMultiLine(true)
		box:SetAutoFocus(false)
		box:SetFontObject("GameFontHighlightSmall")
		box:SetWidth(700)
		box:SetScript("OnEscapePressed", function() window:Hide() end)
		scroll:SetScrollChild(box)
		window.box = box
	end
	local lines = log.lines
	local from = math.max(1, #lines - SHOW_LINES + 1)
	window.title:SetText(("GPS debug log: %d lines (the newest %d here; Ctrl+A, Ctrl+C to copy). All of them are written on /reload."):format(#lines, #lines - from + 1))
	window.box:SetText(table.concat(lines, "\n", from, #lines))
	window:Show()
	window.box:SetFocus()
	window.box:HighlightText()
end

-- /gps debug ...
function ns.DebugCommand(rest)
	local cmd, arg = strtrim(rest or ""):match("^(%S*)%s*(.-)$")
	cmd = (cmd or ""):lower()
	if cmd == "on" then
		if not ns.debugOn then Start("debug log on") end
		print("|cff33ff99GPS|r: debug log on. /reload (or log out) writes it to WTF\\Account\\<account>\\SavedVariables\\GnomishPositioningSystem.lua; /gps debug show to copy it here.")
	elseif cmd == "off" then
		if ns.debugOn then Stop() end
		print("|cff33ff99GPS|r: debug log off (the lines so far stay until /gps debug clear).")
	elseif cmd == "clear" then
		log.lines, log.bytes = {}, 0
		ns.Log("SESSION", "log cleared")
		print("|cff33ff99GPS|r: debug log cleared.")
	elseif cmd == "show" then
		ShowWindow()
	elseif cmd == "mark" then
		if not ns.debugOn then Start("debug log on (for a mark)") end
		ns.Log("MARK", "%s", arg ~= "" and arg or "(mark)")
		print("|cff33ff99GPS|r: noted in the debug log.")
	else
		print(("|cff33ff99GPS|r: debug log %s, %d lines, %d KB (it keeps at most %d KB). /gps debug on | off | clear | show | mark <note>"):format(ns.debugOn and "ON" or "off", #log.lines, (log.bytes or 0) / 1000, MAX_BYTES / 1000))
	end
end

-- Saved variables arrive before ADDON_LOADED; the log goes on again after a /reload if it was on.
local loader = CreateFrame("Frame")
loader:RegisterEvent("ADDON_LOADED")
loader:RegisterEvent("PLAYER_LOGIN")
loader:SetScript("OnEvent", function(self, event, name)
	if event == "ADDON_LOADED" then
		if name ~= addonName then return end
		GnomishPositioningSystemLog = GnomishPositioningSystemLog or {}
		log = GnomishPositioningSystemLog
		log.lines = log.lines or {}
		local bytes = 0
		for _, l in ipairs(log.lines) do bytes = bytes + #l + 1 end
		log.bytes = bytes
		ns.debugLog = log
		if log.on then ns.debugOn = true end -- logging from the start; the header follows at login
		return
	end
	self:UnregisterEvent("PLAYER_LOGIN")
	if log and log.on then
		Start("login or /reload")
		-- so a log left on is noticed (it stays under 1 MB either way)
		print(("|cff33ff99GPS|r: debug log is on (%d lines, %d KB of at most %d). /gps debug off to stop it."):format(#log.lines, log.bytes / 1000, MAX_BYTES / 1000))
	end
end)

ns.DEBUG_MAX_BYTES, ns.DEBUG_KEEP_BYTES, ns.DEBUG_MAX_LINE = MAX_BYTES, KEEP_BYTES, MAX_LINE -- for the tests
