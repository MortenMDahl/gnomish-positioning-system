-- Gnomish Positioning System: a zoomable top-down map of the real world, built from the game's
-- own minimap images (one 512 px image per 533-yard ADT tile, drawn by FileDataID) with small
-- bundled overview images for zoomed-out views.
--
-- Coordinates: the "grid" is the 64x64 ADT tile grid. Tile (x, y) covers grid [x, x+1] x [y, y+1];
-- x grows east and y grows south. World coordinates (X north, Y west, yards) map to it as
--   gx = 32 - Y / TILE,  gy = 32 - X / TILE      (the same convention as MapExplorer's tileOf)
-- UnitPosition("player") returns X (north) first and Y (west) second.
local addonName, ns = ...

local TILE = 1600 / 3                -- yards per ADT tile
local ADDON_PATH = "Interface\\AddOns\\" .. addonName .. "\\"
local LIVE_MIN_SCALE = 80            -- px per tile from which the live minimap tiles are drawn
local MIN_SCALE, MAX_SCALE = 4, 2048 -- px per tile
local SEA = { 0.059, 0.141, 0.204 }  -- #0f2434, the same as the overview images' empty tiles
local UPDATE_INTERVAL = 0.05         -- seconds between player position updates

local floor, ceil, min, max = math.floor, math.ceil, math.min, math.max
local Maps = ns.Maps or {}
local OverviewPx = ns.OverviewPx or 64

local defaults = { point = { "CENTER", "CENTER", 0, 0 }, width = 900, height = 650, map = 0, follow = true, scale = 128 }

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

-- The player's map, grid position and facing, or nil where the game does not give them (instances).
function ns.PlayerPosition()
	local X, Y, _, instanceID = UnitPosition("player")
	if not (Usable(X) and Usable(Y) and Usable(instanceID)) then return nil end
	if ns.db and ns.db.swapAxes then X, Y = Y, X end -- /gps swapaxes, if the self-test reports SWAPPED
	local gx, gy = ns.WorldToGrid(X, Y)
	local facing = GetPlayerFacing and GetPlayerFacing()
	if not Usable(facing) then facing = nil end
	if facing and ns.db and ns.db.flipFacing then facing = -facing end -- /gps flipfacing, if the arrow turns the wrong way
	return instanceID, gx, gy, facing
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
-- Look: "tooltip slim" (design/gps-style-2d-3d.png, option 2). Shared with GPS3D through
-- GPS_API.ApplyChrome so both windows look and behave the same.
------------------------------------------------------------------------------------------------
local GOLD, GREY, DIM = { 1, 0.82, 0 }, { 0.8, 0.8, 0.8 }, { 0.45, 0.45, 0.45 }
ns.colors = { gold = GOLD, grey = GREY, dim = DIM }

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
		if self.tooltip then
			GameTooltip:SetOwner(self, "ANCHOR_BOTTOM")
			GameTooltip:SetText(self.tooltip)
			GameTooltip:Show()
		end
	end)
	b:SetScript("OnLeave", function(self)
		self:SetColor(self.color)
		GameTooltip_Hide()
	end)
	b.tooltip = tooltip
	return b
end
ns.TextButton = TextButton

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

-- Dresses a window (a BackdropTemplate frame) and its map canvas in the GPS look and returns its
-- controls: title, subtitle with prev/next, 2D/3D switch, close, footer text, zoom -/+ and Me.
-- opts.onMoved / opts.onSized are called after the user moves or resizes the window.
function ns.ApplyChrome(frame, canvas, opts)
	opts = opts or {}
	frame:SetBackdrop({
		bgFile = "Interface\\Buttons\\WHITE8X8",
		edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
		edgeSize = 14,
		insets = { left = 3, right = 3, top = 3, bottom = 3 },
	})
	frame:SetBackdropColor(0, 0, 0, 0.85)
	frame:SetBackdropBorderColor(0.8, 0.8, 0.8, 1)
	canvas:ClearAllPoints()
	canvas:SetPoint("TOPLEFT", frame, "TOPLEFT", 5, -5)
	canvas:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", -5, 5)

	local ui = {}
	local chrome = CreateFrame("Frame", nil, frame)
	chrome:SetAllPoints(canvas)
	chrome:SetFrameLevel(canvas:GetFrameLevel() + 40)
	ui.chrome = chrome
	Shade(chrome, true, 56)
	Shade(chrome, false, 36)

	-- Top band: drag to move the window; holds the title and the top controls.
	local band = CreateFrame("Frame", nil, chrome)
	band:SetPoint("TOPLEFT")
	band:SetPoint("TOPRIGHT")
	band:SetHeight(46)
	band:EnableMouse(true)
	band:RegisterForDrag("LeftButton")
	band:SetScript("OnDragStart", function() frame:StartMoving() end)
	band:SetScript("OnDragStop", function() frame:StopMovingOrSizing(); if opts.onMoved then opts.onMoved() end end)
	ui.band = band

	ui.title = band:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
	ui.title:SetPoint("TOPLEFT", 10, -8)
	ui.title:SetJustifyH("LEFT")
	ui.prev = TextButton(band, "<", nil, "Previous map")
	ui.prev:SetPoint("TOPLEFT", 4, -26)
	ui.subtitle = band:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	ui.subtitle:SetPoint("LEFT", ui.prev, "RIGHT", 0, 0)
	ui.subtitle:SetTextColor(GREY[1], GREY[2], GREY[3])
	ui.next = TextButton(band, ">", nil, "Next map")
	ui.next:SetPoint("LEFT", ui.subtitle, "RIGHT", 0, 0)

	ui.close = TextButton(band, "\195\151", "GameFontHighlight", "Close") -- multiplication sign
	ui.close:SetPoint("TOPRIGHT", -4, -5)
	ui.close:SetScript("OnClick", function() frame:Hide() end)
	ui.mode3D = TextButton(band, "3D", nil, "3D perspective view")
	ui.mode3D:SetPoint("RIGHT", ui.close, "LEFT", -6, 0)
	ui.dot = band:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	ui.dot:SetText("\194\183") -- middle dot
	ui.dot:SetTextColor(DIM[1], DIM[2], DIM[3])
	ui.dot:SetPoint("RIGHT", ui.mode3D, "LEFT", 0, 0)
	ui.mode2D = TextButton(band, "2D", nil, "Top-down map")
	ui.mode2D:SetPoint("RIGHT", ui.dot, "LEFT", 0, 0)

	-- Bottom: status text on the left, zoom and Me on the right.
	ui.footer = chrome:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	ui.footer:SetPoint("BOTTOMLEFT", 10, 9)
	ui.footer:SetJustifyH("LEFT")
	ui.footer:SetTextColor(GREY[1], GREY[2], GREY[3])
	ui.me = TextButton(chrome, "Me", nil, "Centre on you and follow")
	ui.me:SetPoint("BOTTOMRIGHT", -16, 5)
	ui.zoomIn = TextButton(chrome, "+", nil, "Zoom in")
	ui.zoomIn:SetPoint("RIGHT", ui.me, "LEFT", -2, 0)
	ui.zoomOut = TextButton(chrome, "-", nil, "Zoom out")
	ui.zoomOut:SetPoint("RIGHT", ui.zoomIn, "LEFT", -2, 0)

	local grip = CreateFrame("Button", nil, chrome)
	grip:SetSize(12, 12)
	grip:SetPoint("BOTTOMRIGHT", 3, -3)
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
	ns.UpdatePlayer()
end

function ns.UpdatePlayer()
	local mapID, gx, gy, facing = ns.PlayerPosition()
	if mapID ~= nil and mapID == view.map then
		if view.follow then
			if math.abs(gx - view.cx) > 1e-6 or math.abs(gy - view.cy) > 1e-6 then
				view.cx, view.cy = gx, gy
				return ns.Layout() -- Layout calls back here with the view centred
			end
		end
		local px, py = ns.GridToScreen(gx, gy)
		arrow:ClearAllPoints()
		arrow:SetPoint("CENTER", canvas, "TOPLEFT", px, -py)
		if facing then arrow:SetRotation(facing) end
		arrow:Show()
	else
		arrow:Hide()
	end
end

local function UpdateTitle()
	local m = Maps[view.map]
	local mapID = ns.PlayerPosition()
	local zone = (mapID == view.map) and GetZoneText and GetZoneText() or nil
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
	if not Maps[mapID] then return end
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
		print("|cff33ff99GPS|r: your position is not available here.")
		return
	end
	view.follow = true
	ns.db.follow = true
	if view.scale < LIVE_MIN_SCALE then view.scale = 128 end -- close enough to see the real tiles
	view.cx, view.cy = gx, gy
	ns.ShowMap(mapID, true)
end

ui.prev:SetScript("OnClick", function() ns.CycleMap(-1) end)
ui.next:SetScript("OnClick", function() ns.CycleMap(1) end)
ui.me:SetScript("OnClick", function() ns.FollowPlayer() end)
ui.mode2D:SetColor(GOLD)
ui.mode3D:SetScript("OnClick", function()
	if GPS3D_API and GPS3D_API.Show then
		-- the 3D view opens where this map looks (or on you, when following)
		GPS3D_API.Show(frame, not view.follow and { map = view.map, gx = view.cx, gy = view.cy } or nil)
		frame:Hide()
	else
		print("|cff33ff99GPS|r: the 3D view needs the GPS3D addon (prototypes/GPS3D).")
	end
end)
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

-- Footer: what is under the cursor, in tiles and world yards (handy for checking alignment).
local elapsedSince = 0
frame:SetScript("OnUpdate", function(_, elapsed)
	elapsedSince = elapsedSince + elapsed
	if elapsedSince < UPDATE_INTERVAL then return end
	elapsedSince = 0
	ns.UpdatePlayer()
	UpdateTitle()
	if canvas:IsMouseOver() and ns.debugGrid then
		-- with /gps grid on: what is under the cursor, in tiles and world yards
		local gx, gy = ns.ScreenToGrid(CursorInCanvas())
		local X, Y = ns.GridToWorld(gx, gy)
		footer:SetFormattedText("tile %d_%d   world %.0f, %.0f   %d px per tile%s", floor(gx), floor(gy), X, Y, view.scale, view.scale >= LIVE_MIN_SCALE and "" or "  (overview)")
	else
		-- where you are: subzone and the usual map coordinates
		local mapID = ns.PlayerPosition()
		local text = ""
		if mapID == view.map then
			local sub = (GetSubZoneText and GetSubZoneText()) or ""
			if sub == "" then sub = (GetZoneText and GetZoneText()) or "" end
			local ui_ = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
			local pos = ui_ and C_Map.GetPlayerMapPosition(ui_, "player")
			if pos and Usable(pos.x) then
				text = ("%s   %.1f, %.1f"):format(sub, pos.x * 100, pos.y * 100)
			else
				text = sub
			end
		end
		footer:SetText(text)
	end
end)

frame:SetScript("OnSizeChanged", function() if frame:IsShown() then ns.Layout() end end)
frame:SetScript("OnShow", function()
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
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function(self, event, name)
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

function GPS_Toggle()
	if GPS3D_Frame and GPS3D_Frame:IsShown() then GPS3D_Frame:Hide() return end
	frame:SetShown(not frame:IsShown())
end

-- For the GPS3D window: the shared look, and switching back to 2D at the same place and size.
GPS_API = {
	ApplyChrome = ns.ApplyChrome,
	TextButton = ns.TextButton,
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
	print("|cff33ff99GPS test|r " .. fmt:format(...))
end

function ns.SelfTest()
	frame:Show()
	local nMaps, nTiles = 0, 0
	for _, m in pairs(Maps) do
		nMaps = nMaps + 1
		for _ in pairs(m.tiles) do nTiles = nTiles + 1 end
	end
	Report("data: %d maps, %d tiles, overview %d px per tile (.%s), interface %s", nMaps, nTiles, OverviewPx, ns.OverviewExt or "jpg", tostring((select(4, GetBuildInfo()))))
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
		Report("done. Now look: real terrain on screen, arrow where you stand (/gps grid shows tile numbers)")
	end)
end

SLASH_GPS1 = "/gps"
SlashCmdList.GPS = function(msg)
	local cmd = strtrim(msg or ""):lower()
	if cmd == "where" then
		local X, Y, Z, instanceID = UnitPosition("player")
		local mapID, gx, gy, facing = ns.PlayerPosition()
		print(("|cff33ff99GPS|r: UnitPosition %s, %s, %s, instance %s"):format(tostring(X), tostring(Y), tostring(Z), tostring(instanceID)))
		if mapID then
			print(("|cff33ff99GPS|r: map %s (%s), tile %d_%d, facing %s"):format(tostring(mapID), Maps[mapID] and Maps[mapID].name or "not in GPS data", floor(gx), floor(gy), tostring(facing)))
		end
	elseif cmd == "test" then
		ns.SelfTest()
	elseif cmd == "grid" then
		ns.debugGrid = not ns.debugGrid
		frame:Show()
		ns.Layout()
		print("|cff33ff99GPS|r: tile numbers " .. (ns.debugGrid and "on" or "off"))
	elseif cmd == "swapaxes" or cmd == "flipfacing" then
		local key = cmd == "swapaxes" and "swapAxes" or "flipFacing"
		ns.db[key] = not ns.db[key]
		print(("|cff33ff99GPS|r: %s %s"):format(key, ns.db[key] and "on" or "off"))
		if frame:IsShown() then ns.Layout() end
	elseif cmd == "reset" then
		ns.db.point, ns.db.width, ns.db.height = defaults.point, defaults.width, defaults.height
		frame:SetSize(ns.db.width, ns.db.height)
		frame:ClearAllPoints()
		frame:SetPoint("CENTER")
	else
		GPS_Toggle()
	end
end
