-- Gnomish Positioning System: a zoomable top-down map of the real world, built from the game's
-- own minimap images (one 512 px image per 533-yard ADT tile, drawn by FileDataID) with small
-- bundled overview images for zoomed-out views.
--
-- Coordinates: the "grid" is the 64x64 ADT tile grid. Tile (x, y) covers grid [x, x+1] x [y, y+1];
-- x grows east and y grows south. World coordinates (X north, Y west, yards) map to it as
--   gx = 32 - Y / TILE,  gy = 32 - X / TILE      (the same convention as MapExplorer's tileOf)
-- UnitPosition("player") returns X (north) first and Y (west) second.
local addonName, ns = ...
-- the debug log (Debug.lua, loaded before this file); without it, logging does nothing
ns.Log = ns.Log or function() end
ns.LogValue = ns.LogValue or tostring
ns.DebugCommand = ns.DebugCommand or function() print("|cff33ff99GPS|r: the debug log (Debug.lua) is not loaded.") end

local TILE = 1600 / 3                -- yards per ADT tile
local ADDON_PATH = "Interface\\AddOns\\" .. addonName .. "\\"
local LIVE_MIN_SCALE = 80            -- px per tile from which the live minimap tiles are drawn
local MIN_SCALE, MAX_SCALE = 4, 2048 -- px per tile
local SEA = { 8 / 255, 17 / 255, 16 / 255 } -- #081110, open sea in the game's minimap images (and the overview images' empty tiles), so the sea runs on past a map's last tiles
local UPDATE_INTERVAL = 0.2          -- seconds between title, footer and Me-ring updates (your position: every frame)

local floor, ceil, min, max = math.floor, math.ceil, math.min, math.max
local Maps = ns.Maps or {}
local OverviewPx = ns.OverviewPx or 64

local defaults = { point = { "CENTER", "CENTER", 0, 0 }, width = 900, height = 650, map = 0, follow = true, scale = 128, mode = "2D", autoTraditional = true, quests = true, addonMarkers = true }
ns.defaults = defaults

-- Values the game may hide from addons in some situations (Forever carries Midnight's "secret values").
local function Usable(v)
	if v == nil then return false end
	if issecretvalue and issecretvalue(v) then return false end
	return true
end

function ns.WorldToGrid(X, Y)
	return 32 - Y / TILE, 32 - X / TILE
end

function ns.GridToWorld(gx, gy)
	return (32 - gy) * TILE, (32 - gx) * TILE
end

-- The player's map, grid position, facing and height (UnitPosition's Z, unchecked), or nil where the
-- game does not give them (instances). The one place the game's position becomes GPS's: the 3D view
-- reads it too (GPS_API.PlayerPosition), so /gps swapaxes and flipfacing apply to both.
function ns.PlayerPosition()
	local X, Y, Z, instanceID = UnitPosition("player")
	if not (Usable(X) and Usable(Y) and Usable(instanceID)) then return nil end
	if ns.db and ns.db.swapAxes then X, Y = Y, X end -- /gps swapaxes, if the self-test reports SWAPPED
	local gx, gy = ns.WorldToGrid(X, Y)
	local facing = GetPlayerFacing and GetPlayerFacing()
	if not Usable(facing) then facing = nil end
	if facing and ns.db and ns.db.flipFacing then facing = -facing end -- /gps flipfacing, if the arrow turns the wrong way
	return instanceID, gx, gy, facing, Z
end

-- Maps in browsing order: continents, then Forever's open-world maps, then the rest by name.
local mapOrder = {}
do
	local rank = { continent = 1, other = 2, dungeon = 3, raid = 4, battleground = 5 }
	for id in pairs(Maps) do mapOrder[#mapOrder + 1] = id end
	table.sort(mapOrder, function(a, b)
		local ra, rb = rank[Maps[a].category] or 9, rank[Maps[b].category] or 9
		if ra ~= rb then return ra < rb end
		return Maps[a].name < Maps[b].name
	end)
	ns.mapOrder = mapOrder
end

------------------------------------------------------------------------------------------------
-- Look: "minimap rings" (option B of the look study, 2026-10-16). A frameless map with a thin
-- black edge, the title and map switch at the top left, the window's controls as round buttons in
-- the minimap's gold ring down the right edge, smaller rings with + and - at the bottom right, and
-- where you are at the bottom left. Built only from art Forever's own interface uses
-- (MiniMap-TrackingBorder, UI-Minimap-Background, UI-Minimap-ZoomButton-Highlight, the RedButton-*
-- atlases) plus a few small icons in Media\.
-- Shared with GPS3D through GPS_API.ApplyChrome / GPS_API.RingButton so both windows look and
-- behave the same.
------------------------------------------------------------------------------------------------
local GOLD, GREY, DIM = { 1, 0.82, 0 }, { 0.8, 0.8, 0.8 }, { 0.45, 0.45, 0.45 }
local BRASS = { 0.79, 0.64, 0.29 }   -- ring labels and icons at rest (muted, like old brass)
ns.colors = { gold = GOLD, grey = GREY, dim = DIM, brass = BRASS, sea = SEA }
local MEDIA = ADDON_PATH .. "Media\\"
ns.MEDIA = MEDIA
local RING = 30                      -- ring button size in px
local RING_GAP = 3

-- Tooltip for a button: a title and optional extra lines (grey).
local function ShowTooltip(self)
	local tip = self.tooltip
	if not tip then return end
	GameTooltip:SetOwner(self, "ANCHOR_LEFT")
	if type(tip) == "function" then tip = tip(self) end
	if type(tip) == "table" then
		GameTooltip:SetText(tip[1], 1, 1, 1)
		for i = 2, #tip do GameTooltip:AddLine(tip[i], GREY[1], GREY[2], GREY[3], true) end
	else
		GameTooltip:SetText(tip, 1, 1, 1)
	end
	GameTooltip:Show()
end

-- A plain text button: grey, white on hover, gold when active.
local function TextButton(parent, text, font, tooltip)
	local b = CreateFrame("Button", nil, parent)
	local fs = b:CreateFontString(nil, "OVERLAY", font or "GameFontHighlightSmall")
	fs:SetPoint("CENTER")
	b.label = fs
	b.color = GREY
	function b:SetLabel(t)
		fs:SetText(t)
		self:SetSize((fs:GetStringWidth() or 8) + 10, 18)
	end
	function b:SetColor(c)
		self.color = c
		fs:SetTextColor(c[1], c[2], c[3])
	end
	b:SetLabel(text)
	b:SetColor(GREY)
	b:SetScript("OnEnter", function(self)
		fs:SetTextColor(1, 1, 1)
		ShowTooltip(self)
	end)
	b:SetScript("OnLeave", function(self)
		self:SetColor(self.color)
		GameTooltip_Hide()
	end)
	b.tooltip = tooltip
	return b
end
ns.TextButton = TextButton

-- A round button in the minimap's gold ring (the look of the minimap's tracking button): a dark
-- disc, the ring, and either a short label or a small icon in the middle. Brass at rest, gold when
-- active (SetActive), lit by the minimap zoom buttons' highlight on hover.
-- The ring texture (64x64) holds the ring in its top-left corner: gold from texel 4 to 34 across
-- and 4 to 33 down. Cropping texels 0..39 puts it in the middle of the button across and half a
-- texel above the middle, so the disc, label and icon sit that much (centreY) above the centre.
local RING_TC = 39 / 64
local LABEL_FIT = 0.40               -- a label is shrunk to fit this share of the ring's width
-- size: the ring's size in px (RING unless given).
local function RingButton(parent, tooltip, size)
	local RING = size or RING
	local b = CreateFrame("Button", nil, parent)
	b:SetSize(RING, RING)
	b:RegisterForClicks("LeftButtonUp")
	local up = RING * 0.5 / 39
	local disc = b:CreateTexture(nil, "BACKGROUND")
	disc:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
	disc:SetVertexColor(0.55, 0.55, 0.55)
	disc:SetSize(RING * 0.66, RING * 0.66)
	disc:SetPoint("CENTER", 0, up)
	local ring = b:CreateTexture(nil, "OVERLAY")
	ring:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
	ring:SetTexCoord(0, RING_TC, 0, RING_TC)
	ring:SetAllPoints()
	local glow = b:CreateTexture(nil, "HIGHLIGHT")
	glow:SetTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
	glow:SetBlendMode("ADD")
	glow:SetSize(RING * 0.8, RING * 0.8)
	glow:SetPoint("CENTER", 0, up)
	local fs = b:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	fs:SetPoint("CENTER", 0, up)
	fs:SetShadowOffset(1, -1)
	fs:SetShadowColor(0, 0, 0, 1)
	local icon = b:CreateTexture(nil, "ARTWORK")
	icon:SetSize(RING * 0.5, RING * 0.5)
	icon:SetPoint("CENTER", 0, up)
	icon:Hide()
	b.label, b.icon, b.disc, b.ring = fs, icon, disc, ring
	b.centreY = up
	function b:SetLabel(t)
		fs:SetText(t)
		-- shrink a wide label (such as 90 degrees) to sit inside the ring's hole
		fs:SetTextScale(1)
		local w = fs:GetStringWidth() or 0
		fs:SetTextScale(w > RING * LABEL_FIT and RING * LABEL_FIT / w or 1)
		fs:Show()
		icon:Hide()
	end
	-- dx, dy (px): a nudge for an image whose drawing is not centred in it
	function b:SetIcon(file, size, dx, dy)
		icon:SetTexture(file)
		icon:SetSize(RING * (size or 0.5), RING * (size or 0.5))
		icon:ClearAllPoints()
		icon:SetPoint("CENTER", dx or 0, up + (dy or 0))
		icon:Show()
		fs:Hide()
	end
	function b:SetActive(on)
		self.active = on and true or false
		local c = self.active and GOLD or BRASS
		fs:SetTextColor(c[1], c[2], c[3])
		icon:SetVertexColor(c[1], c[2], c[3])
	end
	b:SetScript("OnEnter", ShowTooltip)
	b:SetScript("OnLeave", function() GameTooltip_Hide() end)
	b.tooltip = tooltip
	b:SetActive(false)
	return b
end
ns.RingButton = RingButton

-- A zoom button: a ring like the others with a small plus or minus drawn in brass with a black edge
-- (the minimap's own zoom-button art has its sign drawn in, too big for this look). The sign shifts
-- a pixel while pressed.
local ZOOM, SIGN = RING, 9           -- ring size, and the sign's length, in px
local function ZoomButton(parent, dir, tooltip)
	local b = RingButton(parent, tooltip, ZOOM)
	local len, thick = SIGN, 2
	local bars = {}
	local function Bar(w, h, layer, sub, color)
		local t = b:CreateTexture(nil, layer, nil, sub)
		t:SetTexture("Interface\\Buttons\\WHITE8X8")
		t:SetVertexColor(color[1], color[2], color[3], color[4] or 1)
		t:SetSize(w, h)
		bars[#bars + 1] = t
		return t
	end
	local black = { 0, 0, 0, 0.9 }
	Bar(len + 2, thick + 2, "ARTWORK", 0, black)
	if dir == "in" then Bar(thick + 2, len + 2, "ARTWORK", 0, black) end
	Bar(len, thick, "ARTWORK", 1, BRASS)
	if dir == "in" then Bar(thick, len, "ARTWORK", 1, BRASS) end
	local function Place(dx, dy)
		for _, t in ipairs(bars) do
			t:ClearAllPoints()
			t:SetPoint("CENTER", dx, b.centreY + dy)
		end
	end
	Place(0, 0)
	b:HookScript("OnMouseDown", function() Place(1, -1) end)
	b:HookScript("OnMouseUp", function() Place(0, 0) end)
	b.bars = bars
	return b
end

local function Shade(parent, top, height)
	local t = parent:CreateTexture(nil, "BACKGROUND")
	t:SetTexture("Interface\\Buttons\\WHITE8X8")
	t:SetPoint(top and "TOPLEFT" or "BOTTOMLEFT")
	t:SetPoint(top and "TOPRIGHT" or "BOTTOMRIGHT")
	t:SetHeight(height)
	-- vertical gradients run from the bottom (first colour) to the top (second)
	if top then
		t:SetGradient("VERTICAL", CreateColor(0, 0, 0, 0), CreateColor(0, 0, 0, 0.65))
	else
		t:SetGradient("VERTICAL", CreateColor(0, 0, 0, 0.65), CreateColor(0, 0, 0, 0))
	end
	return t
end

-- The three ways GPS shows the world, one window each, shown one at a time at the same place and
-- size: the 2D map (this file), the 3D view (GPS3D) and the traditional map (Blizzard's own map art,
-- MapWindow.lua). The mode ring steps through them in this order; ns.modes holds how to open each.
ns.modeOrder = { "2D", "3D", "Map" }
ns.modeNames = { ["2D"] = "2D map", ["3D"] = "3D view", Map = "Traditional map" }
ns.modes = {}

-- The modes that can open here (3D needs GPS3D; the traditional map needs Blizzard's map canvas).
function ns.AvailableModes()
	local list = {}
	for _, name in ipairs(ns.modeOrder) do
		local m = ns.modes[name]
		if m and (not m.available or m.available()) then list[#list + 1] = name end
	end
	return list
end

-- The mode after (step 1) or before (step -1) this one.
function ns.NextMode(name, step)
	local list = ns.AvailableModes()
	if #list == 0 then return name end
	local index = 1
	for i, m in ipairs(list) do if m == name then index = i break end end
	return list[(index - 1 + (step or 1)) % #list + 1]
end

-- Dresses a window (a BackdropTemplate frame) and its map canvas in the GPS look and returns its
-- controls: title, subtitle with prev/next, close, footer text, zoom in/out, the compass, the mode
-- ring (modeSwitch, showing the mode the window is: "2D", "3D" or a folded map; click for the next
-- mode, right-click for the one before) and the Me ring, plus ui.SetRings(list) to lay out the column
-- of rings down the right edge (top to bottom; GPS3D adds its own after these three).
-- opts.mode is "2D", "3D" or "Map"; opts.onMoved / opts.onSized are called after the user moves or
-- resizes the window; opts.chromeLevel puts the controls at that frame level (the traditional map's
-- pins sit up to level 9000, so its window puts them above).
function ns.ApplyChrome(frame, canvas, opts)
	opts = opts or {}
	frame:SetBackdrop({
		bgFile = "Interface\\Buttons\\WHITE8X8",
		edgeFile = "Interface\\Buttons\\WHITE8X8",
		edgeSize = 1,
		insets = { left = 1, right = 1, top = 1, bottom = 1 },
	})
	frame:SetBackdropColor(0, 0, 0, 1)
	frame:SetBackdropBorderColor(0, 0, 0, 1)
	canvas:ClearAllPoints()
	canvas:SetPoint("TOPLEFT", frame, "TOPLEFT", 1, -1)
	canvas:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", -1, 1)

	local ui = {}
	local chrome = CreateFrame("Frame", nil, frame)
	chrome:SetAllPoints(canvas)
	chrome:SetFrameLevel(opts.chromeLevel or canvas:GetFrameLevel() + 40)
	ui.chrome = chrome
	Shade(chrome, true, 56)
	Shade(chrome, false, 36)

	-- Top band: drag to move the window; holds the title and the map switch.
	local band = CreateFrame("Frame", nil, chrome)
	band:SetPoint("TOPLEFT")
	band:SetPoint("TOPRIGHT", -40, 0) -- leaves the close button and the rings their clicks
	band:SetHeight(46)
	band:EnableMouse(true)
	band:RegisterForDrag("LeftButton")
	band:SetScript("OnDragStart", function() frame:StartMoving() end)
	band:SetScript("OnDragStop", function() frame:StopMovingOrSizing(); if opts.onMoved then opts.onMoved() end end)
	ui.band = band

	ui.title = band:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
	ui.title:SetPoint("TOPLEFT", 10, -8)
	ui.title:SetJustifyH("LEFT")
	ui.title:SetShadowOffset(1, -1)
	ui.prev = TextButton(band, "<", nil, "Previous map")
	ui.prev:SetPoint("TOPLEFT", 4, -26)
	ui.subtitle = band:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	ui.subtitle:SetPoint("LEFT", ui.prev, "RIGHT", 0, 0)
	ui.subtitle:SetTextColor(GREY[1], GREY[2], GREY[3])
	ui.subtitle:SetShadowOffset(1, -1)
	ui.next = TextButton(band, ">", nil, "Next map")
	ui.next:SetPoint("LEFT", ui.subtitle, "RIGHT", 0, 0)

	-- Close: Blizzard's own red close button art.
	local close = CreateFrame("Button", nil, chrome)
	close:SetSize(24, 24)
	close:SetPoint("TOPRIGHT", -6, -6)
	close:SetNormalAtlas("RedButton-Exit")
	close:SetPushedAtlas("RedButton-exit-pressed")
	close:SetHighlightAtlas("RedButton-Highlight", "ADD")
	close:SetScript("OnClick", function() frame:Hide() end)
	close:SetScript("OnEnter", ShowTooltip)
	close:SetScript("OnLeave", function() GameTooltip_Hide() end)
	close.tooltip = "Close"
	ui.close = close

	-- The rings down the right edge, under the close button. Every window starts the column with the
	-- same three, compass, mode and Me, so they stay under the mouse when you switch modes; the 3D
	-- view adds its own below them. The compass needle keeps its own red and grey; the 2D map and the
	-- traditional map are always north-up, so there it just points up (GPS3D turns it and gives it a click).
	ui.compass = RingButton(chrome, { "Compass", "North is up" })
	ui.compass:SetIcon(MEDIA .. "Needle", 0.72)
	ui.compass.icon:SetVertexColor(1, 1, 1)
	local mode = opts.mode or "2D"
	ui.modeSwitch = RingButton(chrome, function()
		local nextMode, prevMode = ns.NextMode(mode, 1), ns.NextMode(mode, -1)
		if nextMode == mode then return ns.modeNames[mode] end
		local tip = { ns.modeNames[mode], "Click: " .. ns.modeNames[nextMode] .. " of the same place" }
		if prevMode ~= nextMode then tip[3] = "Right-click: " .. ns.modeNames[prevMode] end
		return tip
	end)
	ui.modeSwitch:RegisterForClicks("LeftButtonUp", "RightButtonUp")
	if mode == "Map" then
		ui.modeSwitch:SetIcon(MEDIA .. "Map", 0.62)
	else
		ui.modeSwitch:SetLabel(mode)
	end
	ui.modeSwitch:SetScript("OnClick", function(_, button)
		ns.StepMode(mode, button == "RightButton" and -1 or 1)
	end)
	ui.me = RingButton(chrome)
	ui.me:SetIcon("Interface\\Minimap\\MinimapArrow", 0.72)
	ui.me.tooltip = { "Me", "Centre on you and follow" }
	function ui.SetRings(list)
		local above
		for _, b in ipairs(list) do
			b:ClearAllPoints()
			if above then
				b:SetPoint("TOP", above, "BOTTOM", 0, -RING_GAP)
			else
				b:SetPoint("TOPRIGHT", chrome, "TOPRIGHT", -6, -36)
			end
			b:Show()
			above = b
		end
		ui.rings = list
	end
	ui.SetRings({ ui.compass, ui.modeSwitch, ui.me })

	-- Bottom: where you are on the left, the minimap's zoom buttons on the right.
	ui.footer = chrome:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	ui.footer:SetPoint("BOTTOMLEFT", 10, 9)
	ui.footer:SetJustifyH("LEFT")
	ui.footer:SetTextColor(GREY[1], GREY[2], GREY[3])
	ui.footer:SetShadowOffset(1, -1)
	ui.zoomOut = ZoomButton(chrome, "out", "Zoom out")
	ui.zoomOut:SetPoint("BOTTOMRIGHT", -6, 12) -- under the rings, clear of the resize grip
	ui.zoomIn = ZoomButton(chrome, "in", "Zoom in")
	ui.zoomIn:SetPoint("BOTTOM", ui.zoomOut, "TOP", 0, RING_GAP)
	ui.footer:SetPoint("RIGHT", ui.zoomOut, "LEFT", -12, 0)
	ui.footer:SetWordWrap(false)

	local grip = CreateFrame("Button", nil, chrome)
	grip:SetSize(12, 12)
	grip:SetPoint("BOTTOMRIGHT", 0, 0)
	grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
	grip:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
	grip:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
	grip:SetScript("OnMouseDown", function() frame:StartSizing("BOTTOMRIGHT") end)
	grip:SetScript("OnMouseUp", function() frame:StopMovingOrSizing(); if opts.onSized then opts.onSized() end end)
	ui.grip = grip
	return ui
end

-- Puts a window where another one is, at the same size (for switching between 2D and 3D).
function ns.CopyGeometry(to, from)
	local point, rel, relPoint, x, y = from:GetPoint(1)
	to:ClearAllPoints()
	to:SetPoint(point or "CENTER", rel or UIParent, relPoint or "CENTER", x or 0, y or 0)
	to:SetSize(from:GetSize())
end

------------------------------------------------------------------------------------------------
-- Frame
------------------------------------------------------------------------------------------------
local frame = CreateFrame("Frame", "GPS_MapFrame", UIParent, "BackdropTemplate")
frame:SetFrameStrata("HIGH")
frame:SetClampedToScreen(true)
frame:SetMovable(true)
frame:SetResizable(true)
if frame.SetResizeBounds then frame:SetResizeBounds(400, 300, 4000, 3000) end
frame:EnableMouse(true)
frame:EnableMouseWheel(true)
frame:Hide()
tinsert(UISpecialFrames, "GPS_MapFrame") -- Escape closes it
ns.frame = frame

local canvas = CreateFrame("Frame", nil, frame)
canvas:SetClipsChildren(true)
canvas:EnableMouse(true)
ns.canvas = canvas

local sea = canvas:CreateTexture(nil, "BACKGROUND", nil, -8)
sea:SetAllPoints()
sea:SetColorTexture(SEA[1], SEA[2], SEA[3], 1)

-- The player: an arrow above the tiles.
local overlay = CreateFrame("Frame", nil, canvas)
overlay:SetAllPoints()
overlay:SetFrameLevel(canvas:GetFrameLevel() + 10)
local arrow = overlay:CreateTexture(nil, "OVERLAY")
arrow:SetTexture("Interface\\Minimap\\MinimapArrow")
arrow:SetSize(32, 32)
arrow:Hide()
ns.arrow = arrow

local ui = ns.ApplyChrome(frame, canvas, {
	mode = "2D",
	onMoved = function() ns.SaveFrame() end,
	onSized = function() ns.SaveFrame(); ns.Layout() end,
})
ns.ui = ui
local footer = ui.footer

------------------------------------------------------------------------------------------------
-- View state and drawing
------------------------------------------------------------------------------------------------
local view = { map = 0, cx = 32, cy = 32, scale = 128, follow = true }
ns.view = view

local liveTiles = {}   -- key (y * 64 + x) -> texture currently showing that tile
local livePool = {}    -- unused live tile textures
local atlasTextures = {} -- per atlas of the current map
ns.liveTiles = liveTiles
ns.LIVE_MIN_SCALE = LIVE_MIN_SCALE -- for the tests

local function AcquireLive()
	local t = next(livePool)
	if t then livePool[t] = nil return t end
	t = canvas:CreateTexture(nil, "ARTWORK", nil, 1)
	return t
end

local function ReleaseLive(key)
	local t = liveTiles[key]
	if not t then return end
	t:Hide()
	t:ClearAllPoints()
	liveTiles[key] = nil
	livePool[t] = true
end

local function ReleaseAllLive()
	for key in pairs(liveTiles) do ReleaseLive(key) end
end

-- Screen position (from the canvas's top-left, y down) of a grid point.
function ns.GridToScreen(gx, gy)
	local w, h = canvas:GetSize()
	return (gx - view.cx) * view.scale + w / 2, (gy - view.cy) * view.scale + h / 2
end

function ns.ScreenToGrid(px, py)
	local w, h = canvas:GetSize()
	return view.cx + (px - w / 2) / view.scale, view.cy + (py - h / 2) / view.scale
end

local function PlaceRegion(region, gx, gy, gw, gh)
	local px, py = ns.GridToScreen(gx, gy)
	region:ClearAllPoints()
	region:SetPoint("TOPLEFT", canvas, "TOPLEFT", px, -py)
	region:SetSize(gw * view.scale, gh * view.scale)
end

local function SetupAtlases()
	for _, t in ipairs(atlasTextures) do t:Hide() end
	local m = Maps[view.map]
	if not m then return end
	for i, a in ipairs(m.atlases) do
		local t = atlasTextures[i]
		if not t then
			t = canvas:CreateTexture(nil, "ARTWORK", nil, 0)
			atlasTextures[i] = t
		end
		t:SetTexture(ADDON_PATH .. "Overview\\" .. a.file .. "." .. (ns.OverviewExt or "jpg"))
		t:SetTexCoord(0, a.cols * OverviewPx / a.w, 0, a.rows * OverviewPx / a.h)
		t.atlas = a
		t:Show()
	end
end

-- Debug grid (/gps grid): each tile's x_y in its top-left corner, to compare with MapExplorer's "tile x_y".
local labels, labelPool = {}, {}
ns.debugGrid = false
function ns.DrawGrid()
	for _, fs in ipairs(labels) do fs:Hide(); labelPool[#labelPool + 1] = fs end
	wipe(labels)
	local m = Maps[view.map]
	if not ns.debugGrid or not m or view.scale < 24 then return end
	local w, h = canvas:GetSize()
	for y = max(m.minY, floor(view.cy - h / 2 / view.scale)), min(m.maxY, floor(view.cy + h / 2 / view.scale)) do
		for x = max(m.minX, floor(view.cx - w / 2 / view.scale)), min(m.maxX, floor(view.cx + w / 2 / view.scale)) do
			if m.tiles[y * 64 + x] then
				local fs = table.remove(labelPool) or overlay:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
				local px, py = ns.GridToScreen(x, y)
				fs:ClearAllPoints()
				fs:SetPoint("TOPLEFT", canvas, "TOPLEFT", px + 3, -py - 3)
				fs:SetText(x .. "_" .. y)
				fs:Show()
				labels[#labels + 1] = fs
			end
		end
	end
end

function ns.Layout()
	local m = Maps[view.map]
	if not m then return end
	-- Overview atlases: always drawn, under the live tiles, so nothing is ever blank while those load.
	for _, t in ipairs(atlasTextures) do
		local a = t.atlas
		if t:IsShown() and a then PlaceRegion(t, a.x0, a.y0, a.cols, a.rows) end
	end
	-- Live minimap tiles by FileDataID for the tiles in view, once they are big enough to need them.
	local w, h = canvas:GetSize()
	local wanted = {}
	if view.scale >= LIVE_MIN_SCALE then
		local x0 = max(m.minX, floor(view.cx - w / 2 / view.scale))
		local x1 = min(m.maxX, floor(view.cx + w / 2 / view.scale))
		local y0 = max(m.minY, floor(view.cy - h / 2 / view.scale))
		local y1 = min(m.maxY, floor(view.cy + h / 2 / view.scale))
		for y = y0, y1 do
			for x = x0, x1 do
				local key = y * 64 + x
				local fdid = m.tiles[key]
				if fdid then
					wanted[key] = true
					local t = liveTiles[key]
					if not t then
						t = AcquireLive()
						t:SetTexture(fdid)
						t:SetTexCoord(0, 1, 0, 1)
						liveTiles[key] = t
					end
					PlaceRegion(t, x, y, 1, 1)
					t:Show()
				end
			end
		end
	end
	for key in pairs(liveTiles) do
		if not wanted[key] then ReleaseLive(key) end
	end
	ns.DrawGrid()
	if ns.LayoutAddonPins then ns.LayoutAddonPins() end -- other addons' markers (Compat.lua)
	if ns.LayoutQuests then ns.LayoutQuests() end -- your quests (Quests.lua)
	ns.UpdatePlayer()
end

-- With the debug log on: how long each layout takes (Debug.lua reports it every 5 s).
do
	local Layout = ns.Layout
	function ns.Layout()
		local p = ns.perf2D
		if not p then return Layout() end
		local t0 = debugprofilestop()
		Layout()
		local ms = debugprofilestop() - t0
		p.n, p.sum = p.n + 1, p.sum + ms
		if ms > p.max then p.max = ms end
	end
end

local arrowAt = {} -- where the arrow was last put (screen x, y, facing): it is only moved when that changes
function ns.UpdatePlayer()
	local mapID, gx, gy, facing = ns.PlayerPosition()
	-- following you onto another map (a boat, a portal): the map goes with you
	if view.follow and mapID ~= nil and mapID ~= view.map and Maps[mapID] then return ns.ShowMap(mapID, true) end
	if mapID ~= nil and mapID == view.map then
		if view.follow then
			if math.abs(gx - view.cx) > 1e-6 or math.abs(gy - view.cy) > 1e-6 then
				view.cx, view.cy = gx, gy
				return ns.Layout() -- Layout calls back here with the view centred
			end
		end
		local px, py = ns.GridToScreen(gx, gy)
		if px ~= arrowAt[1] or py ~= arrowAt[2] then
			arrow:ClearAllPoints()
			arrow:SetPoint("CENTER", canvas, "TOPLEFT", px, -py)
			arrowAt[1], arrowAt[2] = px, py
		end
		if facing and facing ~= arrowAt[3] then arrow:SetRotation(facing); arrowAt[3] = facing end
		arrow:Show()
	else
		arrow:Hide()
	end
end

-- The name of the zone at a grid point of a GPS map: the game's map there (C_Map), or the zone a
-- dungeon or other small map there belongs to; nil over the sea, between zones, or where the game has
-- no map. Cached per eighth of a tile (66 yards).
local MAPTYPE_ZONE = Enum and Enum.UIMapType and Enum.UIMapType.Zone or 3
local zoneNames = {}
function ns.ZoneNameAt(instance, gx, gy)
	if not (gx and gy and C_Map and C_Map.GetMapPosFromWorldPos and CreateVector2D) then return nil end
	local key = instance .. ":" .. floor(gx * 8) .. ":" .. floor(gy * 8)
	local name = zoneNames[key]
	if name == nil then
		local X, Y = ns.GridToWorld(gx, gy)
		local id = C_Map.GetMapPosFromWorldPos(instance, CreateVector2D(X, Y))
		local info = id and C_Map.GetMapInfo(id)
		while info and info.mapType and info.mapType > MAPTYPE_ZONE and info.parentMapID and info.parentMapID > 0 do
			local parent = C_Map.GetMapInfo(info.parentMapID)
			if not parent then break end
			info = parent
		end
		-- a continent or the world map there means no zone (the sea, or between zones)
		name = info and (info.mapType == nil or info.mapType >= MAPTYPE_ZONE) and info.name or false
		zoneNames[key] = name
	end
	return name or nil
end

-- Title: the zone in the middle of the view (where you are while following you), else the map's
-- name; subtitle: the map's name. Where you are is in the footer.
local function UpdateTitle()
	local m = Maps[view.map]
	local zone = ns.ZoneNameAt(view.map, view.cx, view.cy)
	if not zone and view.follow and ns.PlayerPosition() == view.map and GetZoneText then zone = GetZoneText() end
	ui.title:SetText((zone and zone ~= "") and zone or (m and m.name) or ("Map " .. tostring(view.map)))
	ui.subtitle:SetText(m and m.name or "")
end
ns.UpdateTitle = UpdateTitle

function ns.FitMap()
	local m = Maps[view.map]
	if not m then return end
	local w, h = canvas:GetSize()
	-- The main land only: some maps have small detached test areas far from it.
	local x0, y0, x1, y1 = m.fitMinX or m.minX, m.fitMinY or m.minY, m.fitMaxX or m.maxX, m.fitMaxY or m.maxY
	view.cx = (x0 + x1 + 1) / 2
	view.cy = (y0 + y1 + 1) / 2
	view.scale = max(MIN_SCALE, min(MAX_SCALE, min(w / (x1 - x0 + 1), h / (y1 - y0 + 1))))
end

function ns.ShowMap(mapID, keepView)
	if not Maps[mapID] then ns.Log("MAP", "ShowMap %s: not in GPS data", tostring(mapID)) return end
	if mapID ~= view.map then ns.Log("MAP", "2D map %s -> %s (%s)", tostring(view.map), tostring(mapID), Maps[mapID].name) end
	if mapID ~= view.map then ReleaseAllLive() end
	view.map = mapID
	ns.db.map = mapID
	SetupAtlases()
	UpdateTitle()
	if not keepView then ns.FitMap() end
	ns.Layout()
end

function ns.CycleMap(step)
	local index = 1
	for i, id in ipairs(mapOrder) do if id == view.map then index = i break end end
	index = (index - 1 + step) % #mapOrder + 1
	view.follow = false
	ns.ShowMap(mapOrder[index])
end

function ns.FollowPlayer()
	local mapID, gx, gy = ns.PlayerPosition()
	if not (mapID and Maps[mapID]) then
		ns.Log("MAP", "Me: no position on a GPS map (map %s)", tostring(mapID))
		print("|cff33ff99GPS|r: your position is not available here.")
		return
	end
	ns.Log("MAP", "2D follows you: map %s at %.2f, %.2f", tostring(mapID), gx, gy)
	view.follow = true
	ns.db.follow = true
	if view.scale < LIVE_MIN_SCALE then view.scale = 128 end -- close enough to see the real tiles
	view.cx, view.cy = gx, gy
	ns.ShowMap(mapID, true)
end

ui.prev:SetScript("OnClick", function() ns.CycleMap(-1) end)
ui.next:SetScript("OnClick", function() ns.CycleMap(1) end)
ui.me:SetScript("OnClick", function() ns.FollowPlayer() end)
ns.buttons = { prev = ui.prev, next = ui.next, me = ui.me }

------------------------------------------------------------------------------------------------
-- Input: left drag pans, the wheel zooms around the cursor
------------------------------------------------------------------------------------------------
local function CursorInCanvas()
	local x, y = GetCursorPosition()
	local s = canvas:GetEffectiveScale()
	return x / s - canvas:GetLeft(), canvas:GetTop() - y / s
end

canvas:SetScript("OnMouseDown", function(self, button)
	if button ~= "LeftButton" then return end
	local lx, ly = CursorInCanvas()
	view.follow = false
	ns.db.follow = false
	self:SetScript("OnUpdate", function()
		local x, y = CursorInCanvas()
		if x ~= lx or y ~= ly then
			view.cx = view.cx - (x - lx) / view.scale
			view.cy = view.cy - (y - ly) / view.scale
			lx, ly = x, y
			ns.Layout()
		end
	end)
end)
canvas:SetScript("OnMouseUp", function(self) self:SetScript("OnUpdate", nil) end)
canvas:SetScript("OnHide", function(self) self:SetScript("OnUpdate", nil) end)

function ns.ZoomAt(px, py, factor)
	local gx, gy = ns.ScreenToGrid(px, py)
	view.scale = max(MIN_SCALE, min(MAX_SCALE, view.scale * factor))
	if not view.follow then
		local w, h = canvas:GetSize()
		view.cx = gx - (px - w / 2) / view.scale
		view.cy = gy - (py - h / 2) / view.scale
	end
	ns.db.scale = view.scale
	ns.Layout()
end

frame:SetScript("OnMouseWheel", function(_, delta)
	local px, py = CursorInCanvas()
	ns.ZoomAt(px, py, delta > 0 and 1.25 or 0.8)
end)
ui.zoomIn:SetScript("OnClick", function() local w, h = canvas:GetSize(); ns.ZoomAt(w / 2, h / 2, 1.25) end)
ui.zoomOut:SetScript("OnClick", function() local w, h = canvas:GetSize(); ns.ZoomAt(w / 2, h / 2, 0.8) end)

-- Where you are, for the footers: subzone (or zone) and the usual map coordinates.
function ns.WhereText()
	local sub = (GetSubZoneText and GetSubZoneText()) or ""
	if sub == "" then sub = (GetZoneText and GetZoneText()) or "" end
	local uiMap = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
	local pos = uiMap and C_Map.GetPlayerMapPosition(uiMap, "player")
	if pos and Usable(pos.x) and Usable(pos.y) then
		return ("%s   %.1f, %.1f"):format(sub, pos.x * 100, pos.y * 100)
	end
	return sub
end

-- Footer: what is under the cursor, in tiles and world yards (handy for checking alignment).
-- Your position and the Me ring every frame (a map following you moves smoothly); the title and
-- footer text on a timer (UPDATE_INTERVAL), and at once when the window opens.
local elapsedSince = 0
frame:SetScript("OnUpdate", function(_, elapsed)
	ns.UpdatePlayer()
	if ui.me.active ~= view.follow then ui.me:SetActive(view.follow) end -- the Me ring is gold while following you
	elapsedSince = elapsedSince + elapsed
	if elapsedSince < UPDATE_INTERVAL then return end
	elapsedSince = 0
	UpdateTitle()
	if canvas:IsMouseOver() and ns.debugGrid then
		-- with /gps grid on: what is under the cursor, in tiles and world yards
		local gx, gy = ns.ScreenToGrid(CursorInCanvas())
		local X, Y = ns.GridToWorld(gx, gy)
		footer:SetFormattedText("tile %d_%d   world %.0f, %.0f   %d px per tile%s", floor(gx), floor(gy), X, Y, view.scale, view.scale >= LIVE_MIN_SCALE and "" or "  (overview)")
	else
		-- where you are: subzone and the usual map coordinates
		local mapID = ns.PlayerPosition()
		footer:SetText(mapID == view.map and ns.WhereText() or "")
	end
end)

frame:SetScript("OnSizeChanged", function() if frame:IsShown() then ns.Layout() end end)
frame:SetScript("OnShow", function()
	elapsedSince = UPDATE_INTERVAL -- the footer's text on the first frame
	UpdateTitle()
	local mapID = ns.PlayerPosition()
	if view.follow and mapID and Maps[mapID] then
		ns.FollowPlayer()
	else
		ns.ShowMap(view.map, view.scale >= MIN_SCALE and Maps[view.map] ~= nil and view.cx ~= nil)
	end
end)

function ns.SaveFrame()
	local point, _, relPoint, x, y = frame:GetPoint(1)
	ns.db.point = { point, relPoint, x, y }
	ns.db.width, ns.db.height = frame:GetSize()
end

------------------------------------------------------------------------------------------------
-- Start-up, slash command and key binding
------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------
-- Modes: which window opens, and switching between them
------------------------------------------------------------------------------------------------
-- ns.modes[name] = { Frame = function() return the window end, open = function(from, focus),
--   focus = function() return { map, gx, gy } the window looks at, or nil while it shows you end,
--   available = function() return true when it can open end }
-- from: a window whose place and size to take; focus: { map, gx, gy } to look at, "you" to show
-- you (the window being left was showing you), or nil to open as it was last time.

-- True where GPS can show you: the game gives your position and GPS has that map.
function ns.PlayerOnGPSMap()
	local mapID = ns.PlayerPosition()
	return mapID ~= nil and Maps[mapID] ~= nil
end

local function Available(name)
	local m = ns.modes[name]
	return m ~= nil and (not m.available or m.available())
end

-- The window shown now, if any: its mode and that mode's entry.
function ns.ShownMode()
	for _, name in ipairs(ns.modeOrder) do
		local m = ns.modes[name]
		local f = m and m.Frame()
		if f and f:IsShown() then return name, m end
	end
end

-- Opens a mode, taking the place and size of the window `from` (hidden afterwards).
function ns.OpenMode(name, from, focus)
	local m = ns.modes[name]
	if not (m and Available(name)) then return false end
	local target = m.Frame()
	if m.open(from ~= target and from or nil, focus) == false then ns.Log("MODE", "open %s failed", name) return false end
	if from and from ~= target then from:Hide() end
	ns.Log("MODE", "opened %s, focus %s", name, ns.LogValue(focus))
	return true
end

-- The mode ring: the next (step 1) or previous (step -1) mode, looking at the same place. A mode
-- chosen here is remembered for opening next time.
function ns.StepMode(name, step)
	local target = ns.NextMode(name, step)
	if target == name then
		if name ~= "3D" and not Available("3D") then print("|cff33ff99GPS|r: the 3D view needs the GPS3D addon (prototypes/GPS3D).") end
		return
	end
	local m = ns.modes[name]
	local focus = m and m.focus and m.focus() or "you"
	ns.Log("MODE", "mode ring: %s -> %s", name, target)
	if ns.OpenMode(target, m and m.Frame(), focus) then
		ns.db.mode = target
		ns.autoMap = nil
	end
end

-- What opening shows: the mode you last chose, except the traditional map where GPS cannot show you
-- (dungeons, raids and other places where the game gives no position). Second value: true when that
-- exception applied.
function ns.DefaultMode()
	local chosen = ns.db and ns.db.mode or "2D"
	if not Available(chosen) then chosen = "2D" end
	if chosen ~= "Map" and ns.db and ns.db.autoTraditional and Available("Map") and not ns.PlayerOnGPSMap() then return "Map", true end
	return chosen, false
end

-- After a loading screen or a zone change, when that changed whether GPS can show you: a 2D or 3D
-- window that was showing you switches to the traditional map where GPS cannot show you, and back
-- to your mode once it can again (only when that switch was automatic). A mode you pick with the
-- ring stays until the next such change.
function ns.CheckAutoMode()
	local onMap = ns.PlayerOnGPSMap()
	local changed = onMap ~= ns.lastOnMap
	ns.lastOnMap = onMap
	local name, m = ns.ShownMode()
	if not (name and changed) then return end
	ns.Log("MODE", "GPS can show you: %s (window %s, switched automatically: %s)", tostring(onMap), name, tostring(ns.autoMap))
	if name ~= "Map" and not onMap and ns.db.autoTraditional and Available("Map") and not (m.focus and m.focus()) then
		if ns.OpenMode("Map", m.Frame(), "you") then ns.autoMap = true end
	elseif name == "Map" and ns.autoMap and onMap then
		local back = ns.db and ns.db.mode or "2D"
		if back == "Map" or not Available(back) then back = "2D" end
		if ns.OpenMode(back, m.Frame(), "you") then ns.autoMap = nil end
	end
end

-- Opens a mode by name (and remembers it), in place of whichever window is open: /gps 2d|3d|map, and
-- GPS3D's /gps3d commands. Already open: nothing changes.
function ns.OpenNamed(name)
	local shown, m = ns.ShownMode()
	if shown == name then return true end
	if ns.OpenMode(name, m and m.Frame() or frame, nil) then
		ns.db.mode = name
		ns.autoMap = nil
		return true
	end
	print("|cff33ff99GPS|r: " .. ns.modeNames[name] .. " is not available here.")
	return false
end

-- Puts the window back in the middle at its first size (/gps reset, and the button in the settings),
-- whichever mode is open.
function ns.ResetWindow()
	ns.Log("WINDOW", "reset to the middle at %dx%d", defaults.width, defaults.height)
	ns.db.point, ns.db.width, ns.db.height = defaults.point, defaults.width, defaults.height
	frame:SetSize(ns.db.width, ns.db.height)
	frame:ClearAllPoints()
	frame:SetPoint("CENTER")
	local name, m = ns.ShownMode()
	if name and name ~= "2D" then ns.CopyGeometry(m.Frame(), frame) end
end

-- Keeps the place and size of another mode's window as the saved one (held by the 2D window).
function ns.SaveGeometry(from)
	if not (from and ns.db) then return end
	ns.CopyGeometry(frame, from)
	ns.SaveFrame()
end

ns.modes["2D"] = {
	Frame = function() return frame end,
	open = function(from, focus)
		if focus == "you" then
			-- the window being left was showing you: follow you here too, where GPS can
			if ns.PlayerOnGPSMap() then view.follow = true; ns.db.follow = true end
			focus = nil
		end
		GPS_API.Show(from, focus)
	end,
	focus = function() return not view.follow and { map = view.map, gx = view.cx, gy = view.cy } or nil end,
}
ns.modes["3D"] = {
	Frame = function() return GPS3D_API and GPS3D_API.frame end,
	available = function() return GPS3D_API ~= nil and GPS3D_API.Show ~= nil end,
	open = function(from, focus) GPS3D_API.Show(from, type(focus) == "table" and focus or nil) end,
	focus = function() return GPS3D_API.Focus and GPS3D_API.Focus() or nil end,
}

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("ZONE_CHANGED_NEW_AREA")
events:SetScript("OnEvent", function(self, event, name)
	if event ~= "ADDON_LOADED" then
		-- the position can arrive a moment after the event: check now and again shortly
		if not ns.db then return end
		ns.CheckAutoMode()
		C_Timer.After(1, ns.CheckAutoMode)
		return
	end
	if name ~= addonName then return end
	self:UnregisterEvent("ADDON_LOADED")
	GnomishPositioningSystemDB = GnomishPositioningSystemDB or {}
	local db = GnomishPositioningSystemDB
	for k, v in pairs(defaults) do if db[k] == nil then db[k] = v end end
	ns.db = db
	frame:SetSize(db.width, db.height)
	frame:ClearAllPoints()
	frame:SetPoint(db.point[1], UIParent, db.point[2], db.point[3], db.point[4])
	view.map = Maps[db.map] and db.map or (mapOrder[1] or 0)
	view.follow = db.follow
	view.scale = db.scale
	SetupAtlases()
	UpdateTitle()
	ns.FitMap()
	view.scale = db.scale
end)

-- The key binding and /gps: close whichever window is open, or open the one that fits (DefaultMode)
-- at the saved place and size.
function GPS_Toggle()
	local _, m = ns.ShownMode()
	if m then m.Frame():Hide() return end
	local mode, auto = ns.DefaultMode()
	ns.Log("MODE", "toggle: opening %s%s", mode, auto and " (GPS cannot show you here)" or "")
	if not ns.OpenMode(mode, frame, nil) then
		mode, auto = "2D", false
		ns.OpenMode(mode, frame, nil)
	end
	ns.autoMap = auto or nil
end

-- For the GPS3D window: the shared look, and switching back to 2D at the same place and size.
GPS_API = {
	ApplyChrome = ns.ApplyChrome,
	TextButton = ns.TextButton,
	RingButton = ns.RingButton,
	MEDIA = ns.MEDIA,
	WhereText = ns.WhereText,
	CopyGeometry = ns.CopyGeometry,
	colors = ns.colors,
	-- from: a window whose place and size to take; focus: { map, gx, gy } to look at (nil: as before)
	Show = function(from, focus)
		if from then ns.CopyGeometry(frame, from) end
		if focus and Maps[focus.map] then
			view.follow = false
			if ns.db then ns.db.follow = false end
			view.map = focus.map
			view.cx, view.cy = focus.gx, focus.gy
			if view.scale < LIVE_MIN_SCALE then view.scale = 128 end
		end
		frame:Show()
		if focus and Maps[focus.map] then ns.ShowMap(focus.map, true) end
		if ns.db then ns.SaveFrame() end
	end,
	frame = frame,
	-- modes: the mode ring's step (name, 1 or -1), and opening a mode by name
	StepMode = function(name, step) ns.StepMode(name, step) end,
	OpenMode = function(name, from, focus) return ns.OpenMode(name, from, focus) end,
	OpenNamed = function(name) return ns.OpenNamed(name) end,
	-- keep a window's place and size as the saved one (the 3D window calls it after a move or resize)
	SaveGeometry = function(from) ns.SaveGeometry(from) end,
	-- your map, grid position, facing and height (see ns.PlayerPosition)
	PlayerPosition = function() return ns.PlayerPosition() end,
	-- the debug log (Debug.lua): Log(category, format, ...), and whether it is on
	Log = function(...) return ns.Log(...) end,
	DebugOn = function() return ns.debugOn end,
	-- the zone at a grid point (see ns.ZoneNameAt): the 3D view's title
	ZoneNameAt = function(instance, gx, gy) return ns.ZoneNameAt(instance, gx, gy) end,
	-- map data for the 3D view's textures
	Maps = Maps,
	OverviewPath = ADDON_PATH .. "Overview\\",
	OverviewPx = OverviewPx,
	OverviewExt = ns.OverviewExt or "jpg",
}
BINDING_HEADER_GPS = "Gnomish Positioning System"
BINDING_NAME_GPS_TOGGLE = "Toggle the map"

------------------------------------------------------------------------------------------------
-- Self-test (/gps test): prints a report to copy back (see TESTING.md)
------------------------------------------------------------------------------------------------
local function Report(fmt, ...)
	local text = fmt:format(...)
	print("|cff33ff99GPS test|r " .. text)
	ns.Log("TEST", "%s", text)
end

function ns.SelfTest()
	local openMode, auto = ns.DefaultMode()
	local shownName, shown = ns.ShownMode()
	if shown and shownName ~= "2D" then ns.OpenMode("2D", shown.Frame(), nil) end
	frame:Show()
	local nMaps, nTiles = 0, 0
	for _, m in pairs(Maps) do
		nMaps = nMaps + 1
		for _ in pairs(m.tiles) do nTiles = nTiles + 1 end
	end
	Report("data: %d maps, %d tiles, overview %d px per tile (.%s), interface %s", nMaps, nTiles, OverviewPx, ns.OverviewExt or "jpg", tostring((select(4, GetBuildInfo()))))
	Report("modes: %s; opening here picks %s%s", table.concat(ns.AvailableModes(), ", "), ns.modeNames[openMode] or openMode, auto and " (GPS cannot show you here)" or "")
	if ns.MapSelfTest then ns.MapSelfTest(Report) end
	if ns.quests then ns.quests.SelfTest(Report) end
	if ns.compat then ns.compat.SelfTest(Report) end
	-- Position and axis order: UnitPosition against the world position Blizzard's map API gives.
	local X, Y, Z, instanceID = UnitPosition("player")
	Report("UnitPosition: %s, %s, %s, map %s", tostring(X), tostring(Y), tostring(Z), tostring(instanceID))
	local mapID, gx, gy, facing = ns.PlayerPosition()
	if mapID then
		Report("GPS position: map %s (%s), tile %d_%d (%.2f, %.2f), facing %s", tostring(mapID), Maps[mapID] and Maps[mapID].name or "NOT IN GPS DATA", floor(gx), floor(gy), gx, gy, tostring(facing))
	else
		Report("GPS position: not available here (instance, or hidden by the game)")
	end
	local ui = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
	local pos = ui and C_Map.GetPlayerMapPosition(ui, "player")
	if pos then
		local continent, world = C_Map.GetWorldPosFromMapPos(ui, pos)
		if world then
			local wx, wy = world:GetXY()
			Report("C_Map: uiMap %d at %.4f, %.4f -> map %s, world %.1f, %.1f", ui, pos.x, pos.y, tostring(continent), wx, wy)
			if Usable(X) and Usable(Y) then
				local same = math.abs(wx - X) < 5 and math.abs(wy - Y) < 5
				local swapped = math.abs(wx - Y) < 5 and math.abs(wy - X) < 5
				Report("axis check: %s", same and "PASS (UnitPosition gives world x, y)" or swapped and "SWAPPED (UnitPosition gives y first)" or "MISMATCH (see the numbers above)")
			end
		end
	else
		Report("C_Map: no map position here")
	end
	-- Show real tiles: on yourself if possible, else zoom in where the map is.
	if mapID and Maps[mapID] then
		ns.FollowPlayer()
	else
		view.scale = max(view.scale, 128)
		ns.Layout()
	end
	local t0 = debugprofilestop()
	for _ = 1, 20 do ns.Layout() end
	local live = 0
	for _ in pairs(liveTiles) do live = live + 1 end
	Report("layout: %.2f ms per redraw at %d px per tile with %d live tiles; window %dx%d, UI scale %.2f", (debugprofilestop() - t0) / 20, view.scale, live, canvas:GetWidth(), canvas:GetHeight(), frame:GetEffectiveScale())
	-- Loading, checked after a moment.
	C_Timer.After(2, function()
		local n, loaded, wrong = 0, 0, 0
		local m = Maps[view.map]
		for key, t in pairs(liveTiles) do
			n = n + 1
			if t.IsObjectLoaded and t:IsObjectLoaded() then loaded = loaded + 1 end
			if t.GetTextureFileID and t:GetTextureFileID() ~= m.tiles[key] then wrong = wrong + 1 end
		end
		Report("live minimap tiles: %d of %d report loaded%s", loaded, n, wrong > 0 and (", " .. wrong .. " show an unexpected file ID") or "")
		local shown, ok = 0, 0
		for _, t in ipairs(atlasTextures) do
			if t:IsShown() then
				shown = shown + 1
				if t.IsObjectLoaded and t:IsObjectLoaded() then ok = ok + 1 end
			end
		end
		Report("overview images: %d of %d report loaded", ok, shown)
		-- the look borrows the game's art: does each piece load?
		local u = ns.ui -- (ui is the map ID in this function)
		local parts = { "close", u.close:GetNormalTexture(), "ring", u.me.ring, "disc", u.me.disc, "arrow", u.me.icon }
		local bad = {}
		for i = 1, #parts, 2 do
			local t = parts[i + 1]
			if not (t and t.IsObjectLoaded and t:IsObjectLoaded()) then bad[#bad + 1] = parts[i] end
		end
		Report("look: %s", #bad == 0 and "close, ring, disc and arrow art loaded" or ("NOT loaded: " .. table.concat(bad, ", ")))
		Report("done. Now look: real terrain on screen, arrow where you stand (/gps grid shows tile numbers)")
	end)
end

SLASH_GPS1 = "/gps"
SlashCmdList.GPS = function(msg)
	local cmd = strtrim(msg or ""):lower()
	ns.Log("SLASH", "/gps %s", msg or "")
	if cmd == "debug" or cmd:match("^debug%s") then
		ns.DebugCommand(strtrim(msg or ""):match("^%S+%s*(.-)$"))
	elseif cmd == "where" then
		local X, Y, Z, instanceID = UnitPosition("player")
		local mapID, gx, gy, facing = ns.PlayerPosition()
		print(("|cff33ff99GPS|r: UnitPosition %s, %s, %s, instance %s"):format(tostring(X), tostring(Y), tostring(Z), tostring(instanceID)))
		if mapID then
			print(("|cff33ff99GPS|r: map %s (%s), tile %d_%d, facing %s"):format(tostring(mapID), Maps[mapID] and Maps[mapID].name or "not in GPS data", floor(gx), floor(gy), tostring(facing)))
		end
	elseif cmd == "test" then
		ns.SelfTest()
	elseif cmd == "grid" then
		-- The numbers are drawn on the 2D map only. Turning them on from another window switches that
		-- window to the 2D map, looking at the same place (the mode you chose is kept); turning them off
		-- never opens a window. Until 2026-10-18 both showed the 2D map over the 3D view.
		ns.debugGrid = not ns.debugGrid
		local shown, m = ns.ShownMode()
		if ns.debugGrid and shown ~= "2D" then
			if shown then ns.OpenMode("2D", m.Frame(), m.focus and m.focus() or "you") else frame:Show() end
		end
		if frame:IsShown() then ns.Layout() end
		print("|cff33ff99GPS|r: tile numbers " .. (ns.debugGrid and "on" or "off") .. (ns.debugGrid and shown and shown ~= "2D" and " (on the 2D map)" or ""))
	elseif cmd == "swapaxes" or cmd == "flipfacing" then
		local key = cmd == "swapaxes" and "swapAxes" or "flipFacing"
		ns.db[key] = not ns.db[key]
		print(("|cff33ff99GPS|r: %s %s"):format(key, ns.db[key] and "on" or "off"))
		if frame:IsShown() then ns.Layout() end
	elseif cmd == "2d" or cmd == "3d" or cmd == "map" then
		ns.OpenNamed(cmd == "map" and "Map" or cmd:upper())
	elseif cmd == "reset" then
		ns.ResetWindow()
	elseif cmd == "options" or cmd == "settings" or cmd == "config" then
		ns.OpenSettings()
	else
		GPS_Toggle()
	end
end
