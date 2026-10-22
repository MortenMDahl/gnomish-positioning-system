-- GPS 3D as the minimap (since 2026-10-22): "Use GPS as minimap" on GPS's settings page (off by default),
-- /gps minimap on|off.
--
-- How (Forever's UI source, Gethe/wow-ui-source branch forever): the game's own HybridMinimap
-- (Blizzard_HybridMinimap.xml / .lua) is a map Blizzard draws in the minimap's place: a frame that is a child of
-- Minimap, in the BACKGROUND strata (under Minimap, which is LOW with MinimapCluster), with
-- C_Minimap.SetDrawGroundTextures(false) while it shows, so the minimap's own ground art is left out and
-- everything else the Minimap widget draws (your arrow, party members, tracking and gathering blips, quest
-- icons and areas, the ping) stays on top of it. GPS does the same: its host frame is a child of Minimap in the
-- BACKGROUND strata, GPS3D's canvas is moved into it, and the ground art is switched off. Nothing of Blizzard's
-- is replaced, hooked or written: Minimap, its zoom buttons, the mouse (a click pings, the wheel zooms), the
-- cluster's buttons (tracking, calendar, mail, zone text) stay Blizzard's, and turning the setting off switches
-- the ground art back on and hides the host: the minimap is exactly as it was.
--
-- The view: tilted (MM.tilt, default 35 degrees from straight down; the setting "Minimap tilt"), centred on you
-- at your height, north up or turned with your facing as the game's "Rotate Minimap" option says (the CVar
-- rotateMinimap, read every frame, as Blizzard's minimap follows it), and at the scale of Blizzard's minimap:
-- its rim is C_Minimap.GetViewRadius() yards away (what HybridMinimap reads), so the minimap's zoom buttons
-- and wheel (Blizzard's own code) zoom it. So that Blizzard's blips, drawn flat by the game, stay on the spot
-- they mark: a narrow lens (MM.FOV, 12 degrees, the camera far back) and the screen's up stretched by
-- 1 / sin(elevation) (cam.stretch, GPS3D.lua's CameraBasis), which gives the ground at your height the flat
-- minimap's proportions while hills and buildings stand up out of it (tools/sandbox/test_minimap.py, tilted 35:
-- a point on the ground at your height within 0.4 px of its blip a quarter of the way out, 1.5 px halfway, 5.7 px
-- near the rim; without the stretch 10 and 22 px with this lens, 14 and 35 px with the 3D window's 50-degree one).
--
-- One renderer: GPS3D has one camera, one canvas and one texture pool. The minimap borrows them while the 3D
-- window is closed (the camera, the budgets and the canvas's place, levels and strata are kept and put back);
-- while the 3D window is open Blizzard's minimap is back (GPS3D.lua's Open calls MinimapYield first). The
-- minimap draws only the ground and the building blocks (GPS3D's RenderWorld) at its own budgets (MM.GRID,
-- MM.DETAIL), and only when you moved, turned, the zoom or the size changed, or blocks wait to be made.
-- Your arrow, the quest markers and areas, other addons' markers and the game's models are the minimap's own
-- (Blizzard's, drawn on top), so GPS's are hidden there.
--
-- Shape: Forever's minimap is round (Camelot's Minimap.lua masks it with ui-hud-minimap-frame-generic-mask in
-- both modes, and MinimapMixin:OnClick pings only inside the circle): every texture GPS draws there gets a
-- round mask (the one HybridMinimap uses, TempPortraitAlphaMask, 3 px inside the minimap's edge), unless an
-- addon says the minimap is square (the GetMinimapShape convention).
--
-- Falls back to Blizzard's minimap by itself where GPS cannot show you (no position, a map without GPS3D's
-- terrain), in instances and indoors (Blizzard's minimap has the inside's layout there, GPS only the roof),
-- while Blizzard's own HybridMinimap shows, and while the minimap is hidden; back when that ends.
-- Combat: nothing here is refused in combat (GPS's own frames, a C_Minimap call without restrictions), so it
-- works the same in a fight; only the buildings' data waits for the end of combat (OnDemand.lua).
local _, ns = ...
local GPS = GPS_API
local cam, canvas, frame = ns.cam, ns.canvas, ns.frame
local floor, min, max, abs, rad, deg, sin, tan = math.floor, math.min, math.max, math.abs, math.rad, math.deg, math.sin, math.tan

local MM = {
	on = false,        -- the setting
	active = false,    -- GPS3D's canvas is in the minimap now
	why = "off",       -- why not (for /gps minimap and the debug log)
	tilt = 35,         -- degrees from straight down (the setting "Minimap tilt")
	TILT_DEFAULT = 35, TILT_MAX = 45,
	FOV = 12,          -- the lens, degrees top to bottom: narrow, so the blips line up (see above)
	GRID = 1200,       -- ground triangles a frame (the 3D window: 3,200 by default)
	DETAIL = 1500,     -- building triangles a frame (the 3D window: 4,000)
	LEVEL = 100,       -- the host's frame level in the BACKGROUND strata (HybridMinimap's)
	INSET = 3,         -- the round mask's inset from the minimap's edge (HybridMinimap's)
	MASK = "Interface\\CharacterFrame\\TempPortraitAlphaMask",
	RADIUS = 200,      -- yards to the rim when C_Minimap.GetViewRadius is missing
	saved = nil,       -- what the 3D window had (camera, budgets, the canvas's place)
	last = {},         -- the camera last drawn
	draws = 0, frames = 0, ms = 0, -- redraws, frames looked at and the last redraw's Lua ms
	dirty = true,
	indoor = false,    -- instance or indoors (from the zone events)
}
ns.minimap = MM

local CAM_KEYS = { "map", "x", "y", "th", "dist", "yaw", "pitch", "fov", "vp", "stretch" }

local function DB() GPS3D_DB = GPS3D_DB or {} return GPS3D_DB end

local function Log(fmt, ...) if GPS.Log then GPS.Log("MINIMAP", fmt, ...) end end

------------------------------------------------------------------------------------------------
-- The host: a child of Minimap under it (HybridMinimap's place), and the round mask
------------------------------------------------------------------------------------------------
local function Host()
	if MM.host then return MM.host end
	local mm = Minimap
	if not (mm and mm.GetObjectType) then return nil end
	local h = CreateFrame("Frame", nil, mm)
	h:SetAllPoints(mm)
	h:SetFrameStrata("BACKGROUND")
	if h.SetFixedFrameStrata then h:SetFixedFrameStrata(true) end
	h:SetFrameLevel(MM.LEVEL)
	if h.SetFixedFrameLevel then h:SetFixedFrameLevel(true) end
	h:EnableMouse(false) -- (the clicks, the wheel and the blips' tooltips stay Blizzard's Minimap's)
	h:Hide()
	local mask = h.CreateMaskTexture and h:CreateMaskTexture()
	if mask then
		mask:SetTexture(MM.MASK, "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
		mask:SetPoint("TOPLEFT", h, "TOPLEFT", MM.INSET, -MM.INSET)
		mask:SetPoint("BOTTOMRIGHT", h, "BOTTOMRIGHT", -MM.INSET, MM.INSET)
	end
	MM.host, MM.mask = h, mask
	return h
end

local function Round()
	-- an addon that makes the minimap square says so through the global GetMinimapShape (a convention of the
	-- minimap button libraries); Forever's own is round
	local shape = type(GetMinimapShape) == "function" and GetMinimapShape()
	return not (shape and shape ~= "ROUND")
end

-- every frame under f, parents before children
local function Walk(f, list)
	for _, c in ipairs({ f:GetChildren() }) do
		list[#list + 1] = c
		Walk(c, list)
	end
	return list
end

local function Mask(tex, on)
	if on and not tex.gpsMask then tex:AddMaskTexture(MM.mask); tex.gpsMask = true
	elseif not on and tex.gpsMask then tex:RemoveMaskTexture(MM.mask); tex.gpsMask = nil end
end
-- the ground's textures (in the bucket frames) and the sea behind them
local function MaskAll(on)
	if not MM.mask then return end
	for _, r in ipairs({ canvas:GetRegions() }) do if r.AddMaskTexture then Mask(r, on) end end
	for _, f in ipairs(ns.bucketFrames) do
		for _, r in ipairs({ f:GetRegions() }) do if r.AddMaskTexture then Mask(r, on) end end
	end
	ns.miniMask = on and MM.mask or nil -- (textures made from now on: GPS3D.lua's AcquireTex)
	MM.masked = on
end

------------------------------------------------------------------------------------------------
-- Taking GPS3D's canvas and camera, and giving them back
------------------------------------------------------------------------------------------------
local function Take()
	local host = Host()
	if not host or MM.active then return false end
	if ns.GlobeLeave then ns.GlobeLeave() end -- (the 3D window was left on the planet: its frames hidden, the ground's shown)
	local s = { cam = {}, points = {}, frames = {}, hidden = {} }
	for _, k in ipairs(CAM_KEYS) do s.cam[k] = cam[k] end
	s.grid, s.detail = ns.Budgets()
	s.parent = canvas:GetParent()
	for i = 1, canvas:GetNumPoints() do s.points[i] = { canvas:GetPoint(i) } end
	s.strata, s.level = canvas:GetFrameStrata(), canvas:GetFrameLevel()
	s.mouse, s.wheel = canvas:IsMouseEnabled(), canvas:IsMouseWheelEnabled()
	for i, f in ipairs(Walk(canvas, {})) do s.frames[i] = { f, f:GetFrameStrata(), f:GetFrameLevel() } end
	MM.saved = s
	-- the canvas into the host, at the host's strata, its frames' levels kept relative to it
	host:Show()
	canvas:SetParent(host)
	canvas:ClearAllPoints()
	canvas:SetAllPoints(host)
	canvas:SetFrameStrata("BACKGROUND")
	canvas:SetFrameLevel(MM.LEVEL + 1)
	for _, e in ipairs(s.frames) do
		e[1]:SetFrameStrata("BACKGROUND")
		e[1]:SetFrameLevel(MM.LEVEL + 1 + e[3] - s.level)
	end
	canvas:EnableMouse(false)
	canvas:EnableMouseWheel(false)
	-- only the ground: your arrow, the models and the markers are Blizzard's minimap's own
	local buckets = {}
	for _, f in ipairs(ns.bucketFrames) do buckets[f] = true; f:Show() end
	for _, f in ipairs({ canvas:GetChildren() }) do
		if not buckets[f] and f:IsShown() then s.hidden[#s.hidden + 1] = f; f:Hide() end
	end
	canvas:Show()
	if Round() then MaskAll(true) end
	-- the minimap's ground art off: GPS's view shows under Blizzard's blips (HybridMinimap's OnShow does this)
	MM.groundWas = C_Minimap and C_Minimap.GetDrawGroundTextures and C_Minimap.GetDrawGroundTextures()
	if C_Minimap and C_Minimap.SetDrawGroundTextures then C_Minimap.SetDrawGroundTextures(false) end
	MM.active, MM.dirty = true, true
	wipe(MM.last)
	if ns.choice then ns.choice.ok = false end
	if ns.Lod then ns.Lod.map = -1 end -- (the level of detail starts afresh: another view)
	Log("on: GPS's view in the minimap")
	return true
end

local function Give(why)
	if not MM.active then return end
	local s = MM.saved
	MM.active = false
	if MM.masked then MaskAll(false) end
	-- Blizzard's ground art back, unless Blizzard's HybridMinimap (which turns it off itself) is showing
	if C_Minimap and C_Minimap.SetDrawGroundTextures and not (HybridMinimap and HybridMinimap:IsShown()) then
		C_Minimap.SetDrawGroundTextures(MM.groundWas ~= false)
	end
	for _, f in ipairs(s.hidden) do f:Show() end
	canvas:SetParent(s.parent)
	canvas:ClearAllPoints()
	for _, p in ipairs(s.points) do canvas:SetPoint(p[1], p[2], p[3], p[4], p[5]) end
	canvas:SetFrameStrata(s.strata)
	canvas:SetFrameLevel(s.level)
	local known = {}
	for _, e in ipairs(s.frames) do
		known[e[1]] = true
		e[1]:SetFrameStrata(e[2])
		e[1]:SetFrameLevel(e[3])
	end
	for _, f in ipairs(Walk(canvas, {})) do -- (frames made while the minimap had it)
		if not known[f] then
			f:SetFrameStrata(s.strata)
			f:SetFrameLevel(s.level + f:GetFrameLevel() - MM.LEVEL - 1)
		end
	end
	canvas:EnableMouse(s.mouse)
	canvas:EnableMouseWheel(s.wheel)
	for _, k in ipairs(CAM_KEYS) do cam[k] = s.cam[k] end
	ns.SetBudgets(s.grid, s.detail)
	if ns.choice then ns.choice.ok = false end
	if ns.Lod then ns.Lod.map = -1 end
	if ns.SnapLift then ns.SnapLift() end
	MM.host:Hide()
	MM.saved = nil
	MM.why = why or MM.why
	Log("off (%s): Blizzard's minimap", tostring(why))
end

-- The 3D window opens: Blizzard's minimap is back while it is open (GPS3D.lua's Open, before anything else)
ns.MinimapYield = function() Give("the 3D window is open") end

------------------------------------------------------------------------------------------------
-- Drawing
------------------------------------------------------------------------------------------------
local function Rotating()
	if not (GetCVarBool and GetCVarBool("rotateMinimap")) then return false end
	return not (C_Minimap and C_Minimap.IsRotateMinimapIgnored and C_Minimap.IsRotateMinimapIgnored())
end

-- The camera for the minimap as it is now; true when it differs from the one last drawn.
local function Aim()
	local p = ns.player
	local w, h = canvas:GetSize()
	if not (w and w > 0 and h and h > 0) then return false end
	local R = C_Minimap and C_Minimap.GetViewRadius and C_Minimap.GetViewRadius() or MM.RADIUS
	if not R or R <= 0 then R = MM.RADIUS end
	local fov = rad(MM.FOV)
	local pitch = 90 - MM.tilt
	local F = (h / 2) / tan(fov / 2)
	cam.map, cam.x, cam.y, cam.th = p.map, p.x, p.y, p.h
	cam.yaw = Rotating() and (-deg(p.facing)) % 360 or 0
	cam.pitch, cam.vp, cam.fov = pitch, nil, fov
	cam.stretch = 1 / sin(rad(pitch))
	cam.dist = F / ((w / 2) / R) -- the rim R yards from you, as Blizzard's minimap draws its blips
	local l = MM.last
	if MM.dirty or l.map ~= cam.map or abs(cam.x - l.x) > 0.01 or abs(cam.y - l.y) > 0.01 or abs(cam.th - l.th) > 0.05
		or abs((cam.yaw - l.yaw + 180) % 360 - 180) > 0.01 or l.dist ~= cam.dist or l.pitch ~= pitch or l.w ~= w or l.h ~= h then
		l.map, l.x, l.y, l.th, l.yaw, l.dist, l.pitch, l.w, l.h = cam.map, cam.x, cam.y, cam.th, cam.yaw, cam.dist, pitch, w, h
		return true
	end
	return false
end

local function Draw()
	local t0 = debugprofilestop()
	ns.SetBudgets(MM.GRID, MM.DETAIL)
	if ns.SnapLift then ns.SnapLift() end -- (far above you: no lift; nothing left over from the 3D window)
	if ns.WantData then ns.WantData() end -- the buildings near you, loaded on demand (OnDemand.lua)
	ns.RenderWorld(ns.Focal(), ns.CameraBasis())
	MM.dirty = false
	MM.draws = MM.draws + 1
	MM.ms = debugprofilestop() - t0
end
MM.Draw = Draw

-- Why GPS cannot be the minimap now (nil: it can); your position is read here (every frame, as the 3D window does)
local function WhyNot()
	if not MM.on then return "off" end
	if frame:IsShown() then return "the 3D window is open" end -- (which reads your position itself)
	if not (Minimap and Minimap:IsVisible()) then return "the minimap is hidden" end
	if HybridMinimap and HybridMinimap:IsShown() then return "Blizzard's hybrid minimap shows" end
	if MM.indoor then return MM.indoor end
	local p = ns.player
	ns.ReadPlayer()
	if not p.on then return p.why == "nodata" and "no 3D terrain for this map" or "your position is not available" end
	return nil
end

-- One frame: Blizzard's minimap or GPS's, and GPS's redrawn when the camera moved or blocks wait to be made
local function Step()
	MM.frames = MM.frames + 1
	local why = WhyNot()
	if why then
		if MM.active then Give(why) elseif MM.why ~= why then MM.why = why; Log("Blizzard's minimap: %s", why) end
		return
	end
	if not MM.active and not Take() then return end
	MM.why = nil
	if Aim() or ns.stats.detailPending > 0 then Draw() end
end
local driver = CreateFrame("Frame")
driver:Hide()
MM.driver = driver
driver:SetScript("OnUpdate", Step)

-- instance or indoors: from the zone events (and once now)
local function CheckPlace()
	local inst, kind = false, nil
	if IsInInstance then inst, kind = IsInInstance() end
	if inst and kind ~= "none" then MM.indoor = "in an instance"
	elseif IsIndoors and IsIndoors() then MM.indoor = "indoors"
	else MM.indoor = false end
end
driver:RegisterEvent("PLAYER_ENTERING_WORLD")
driver:RegisterEvent("ZONE_CHANGED")
driver:RegisterEvent("ZONE_CHANGED_INDOORS")
driver:RegisterEvent("ZONE_CHANGED_NEW_AREA")
driver:SetScript("OnEvent", function() CheckPlace(); MM.dirty = true end)

-- buildings that arrived (OnDemand.lua): draw again
do
	local arrived = ns.DataArrived
	ns.DataArrived = function(...)
		arrived(...)
		MM.dirty = true
	end
end

------------------------------------------------------------------------------------------------
-- The setting
------------------------------------------------------------------------------------------------
function MM.Set(on, quiet)
	on = not not on
	DB().minimap = on
	MM.on = on
	if on then
		CheckPlace()
		MM.why = nil
		driver:Show()
		Step() -- (at once, not on the next frame)
	else
		Give("off")
		MM.why = "off"
		driver:Hide()
	end
	if not quiet then Log("setting: %s", on and "on" or "off") end
end

function MM.SetTilt(v)
	v = max(0, min(MM.TILT_MAX, tonumber(v) or MM.TILT_DEFAULT))
	DB().minimapTilt = v
	MM.tilt, MM.dirty = v, true
end

function MM.State()
	if not MM.on then return "off" end
	if MM.active then
		return ("on: GPS's view in the minimap, tilted %d, %s, %.0f yd to the rim, %d redraws (last %.1f ms)"):format(MM.tilt,
			Rotating() and "turning with you" or "north up", C_Minimap and C_Minimap.GetViewRadius and C_Minimap.GetViewRadius() or MM.RADIUS, MM.draws, MM.ms)
	end
	return "on, Blizzard's minimap for now: " .. tostring(MM.why or "starting")
end

-- /gps minimap [on|off] (GPS's slash command hands it over)
GPS3D_API.Minimap = function(arg)
	arg = strtrim(arg or ""):lower()
	if arg == "on" or arg == "off" then MM.Set(arg == "on") end
	print("|cff55ff55GPS3D|r minimap: " .. MM.State())
end
GPS3D_API.MinimapState = MM.State

-- restored at login (saved variables are read by then)
do
	local f = CreateFrame("Frame")
	f:RegisterEvent("PLAYER_LOGIN")
	f:SetScript("OnEvent", function()
		local db = DB()
		MM.tilt = max(0, min(MM.TILT_MAX, tonumber(db.minimapTilt) or MM.TILT_DEFAULT))
		if db.minimap then MM.Set(true, true) end
	end)
end

-- GPS's settings page (Settings.lua shows GPS3D_API.settings)
if GPS3D_API.settings then
	local list = GPS3D_API.settings
	list[#list + 1] = { kind = "header", name = "Minimap" }
	list[#list + 1] = {
		kind = "check", key = "GPS3D_Minimap", name = "Use GPS as minimap",
		tooltip = "Show GPS's tilted 3D view in the minimap's place, under the minimap's own arrow, blips and buttons (/gps minimap). Blizzard's minimap comes back by itself indoors, in instances and while the 3D window is open.",
		default = false,
		get = function() return GPS3D_DB and GPS3D_DB.minimap or false end,
		set = function(v) MM.Set(v) end,
	}
	list[#list + 1] = {
		kind = "slider", key = "GPS3D_MinimapTilt", name = "Minimap tilt",
		tooltip = "How far the minimap's view leans from straight down (0: straight down).",
		default = MM.TILT_DEFAULT, min = 0, max = MM.TILT_MAX, step = 5,
		format = function(v) return ("%d\194\176"):format(v) end,
		get = function() return GPS3D_DB and GPS3D_DB.minimapTilt end,
		set = function(v) MM.SetTilt(v) end,
	}
end
