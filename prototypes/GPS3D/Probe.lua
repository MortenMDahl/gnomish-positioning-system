-- GPS3D: /gps3d probe, the in-game checks of the performance review of 2026-10-22 (its section 2), in one
-- go, so the numbers and pictures only the game can give come back in one message:
--   1. cost per texture and per call: at the current view, the ground budget 800 / 3,200 / 6,400 (no
--      buildings) and the building budget 2,000 / 4,000 / 8,000 (ground 3,200), each held with the
--      camera still (the game only draws), redrawn (GPS3D's Lua runs, no C calls), and turning by itself
--      (every corner sent): the game's frame time (time between OnUpdates, and GetFramerate), GPS3D's Lua
--      ms for the frame (debugprofilestop, Render's own stats.ms), textures shown and the C calls made
--      (counted from what the frame changed: corners, draw layers, frames, shown and hidden). Frame time
--      minus Lua against textures and calls gives the client's cost per texture and per call.
--   2. the fold: two squares of a test picture (Media\Probe: a red diagonal for corners 1-4, a blue one
--      for corners 2-3), each with one corner lifted by SetVertexOffset; the diagonal the client folds
--      along stays straight, the other kinks.
--   3. RotateTextures: a bent triangle as the ground draws it, beside the same in a frame turned by
--      RotateTextures(0.5), with a white ghost where it was: on the ghost, only the image turned.
--   4. SetPointsOffset: the ground's textures anchored to their depth frame, one frame shifted a few
--      pixels every frame (frame time against none), then all eight shifted as the camera glides,
--      with a red cross and your arrow drawn fresh for the moved camera: they should stay on the ground,
--      and the real redraw at the end should not jump.
--   5. OffScreenFrame: made or not, its methods, TakeSnapshot on a small test frame (nothing shown).
-- Each part runs under pcall (one failing does not stop the others; a missing API is reported as
-- "missing"); the settings, the camera and every anchor are put back at the end, on /gps3d probe stop,
-- when the window closes and when combat starts; it does not start in combat. Results: chat, the debug
-- log (category PROBE) and GPS3D_DB.probe (written to SavedVariables\GPS3D.lua on /reload).
-- Nothing here runs unless the probe does: the normal frame is unchanged.
local _, ns = ...
local GPS = GPS_API
local floor, max, min, abs, sin, cos, pi, sqrt = math.floor, math.max, math.min, math.abs, math.sin, math.cos, math.pi, math.sqrt

local P = {
	SETTINGS = { { 800, 0 }, { 3200, 0 }, { 6400, 0 }, { 3200, 2000 }, { 3200, 4000 }, { 3200, 8000 } }, -- ground, buildings
	-- seconds: settling after a change (until no building block is waiting), each phase, the pictures
	T = { settle = 0.6, settleMax = 3, still = 2, redraw = 2, turn = 2.5, picture = 10, base = 2, shiftOne = 2, glide = 3, hold = 1.5 },
	scale = 1,     -- (the tests shorten every duration)
	TURN = 20,     -- degrees a second, turning by itself
	DROP = 3,      -- first frames of a phase not timed (the change itself)
	COUNT = 3,     -- frames after those whose calls are counted (and the frames after them not timed)
	SHIFT_PX = 35, -- how far the ground glides on screen in part 4
	running = false,
}
ns.probe = P

local function Say(fmt, ...)
	local ok, msg = pcall(string.format, fmt, ...)
	if not ok then msg = tostring(fmt) end
	print("|cff55ff55GPS3D probe|r " .. msg)
	if GPS and GPS.Log then GPS.Log("PROBE", "%s", msg) end
	local lines = P.lines
	if lines and #lines < 80 then lines[#lines + 1] = msg end
end
P.Say = Say

-- Whether an object has a method. (The sandbox answers a method it lacks with a new do-nothing stub
-- at each look-up, so a method that is not the same function twice counts as missing there; in the
-- game a method is always the same function.)
local function Has(obj, name)
	local a = obj[name]
	return a ~= nil and a == obj[name]
end
P.Has = Has

------------------------------------------------------------------------------------------------
-- C calls made by one Render, counted from what it changed: the triangles drawn before it are noted
-- (their corners, depth bucket and frame), and after it every corner that differs was a SetVertexOffset
-- (the third two: the fourth is pinned onto it), a new bucket a SetDrawLayer, a new frame a SetParent,
-- a triangle cut at the near plane four corners and its texture coordinates, a triangle not drawn
-- before a Show and its four corners, one no longer drawn a Hide. Meshes made in that frame (their
-- SetTexture / SetTexCoord) and the marker's few calls are not counted.
------------------------------------------------------------------------------------------------
local snap = { idx = {}, n = 0, x1 = {}, y1 = {}, x2 = {}, y2 = {}, x3 = {}, y3 = {}, b = {}, f = {}, cl = {} }
function P.Snapshot()
	local st = ns.stats
	local vis, idx = st.visible or {}, snap.idx
	wipe(idx)
	local n = st.shown or 0
	local x1, y1, x2, y2, x3, y3, b, f, cl = snap.x1, snap.y1, snap.x2, snap.y2, snap.x3, snap.y3, snap.b, snap.f, snap.cl
	for i = 1, n do
		local t = vis[i]
		idx[t] = i
		x1[i], y1[i], x2[i], y2[i], x3[i], y3[i] = t.x1, t.y1, t.x2, t.y2, t.x3, t.y3
		b[i], f[i], cl[i] = t.bucket, t.tex.bucketFrame, t.clipped or false
	end
	snap.n = n
end
local counted = { svo = 0, layer = 0, parent = 0, show = 0, hide = 0, coord = 0, total = 0, new = 0 }
P.counted = counted
function P.Diff()
	local st = ns.stats
	local vis, idx = st.visible or {}, snap.idx
	local svo, layer, parent, show, coord, seen, new = 0, 0, 0, 0, 0, 0, 0
	local x1, y1, x2, y2, x3, y3, b, f, cl = snap.x1, snap.y1, snap.x2, snap.y2, snap.x3, snap.y3, snap.b, snap.f, snap.cl
	for i = 1, st.shown or 0 do
		local t = vis[i]
		local j = idx[t]
		if j then idx[t] = false; seen = seen + 1 end
		if not j then
			show, new = show + 1, new + 1
			svo, layer = svo + 4, layer + 1
			if t.clipped and t.u1 then coord = coord + 1 end
		elseif t.clipped then
			svo = svo + 4
			if t.u1 then coord = coord + 1 end
			if t.bucket ~= b[j] then layer = layer + 1 end
			if t.tex.bucketFrame ~= f[j] then parent = parent + 1 end
		else
			if t.x1 ~= x1[j] or t.y1 ~= y1[j] then svo = svo + 1 end
			if t.x2 ~= x2[j] or t.y2 ~= y2[j] then svo = svo + 1 end
			if t.x3 ~= x3[j] or t.y3 ~= y3[j] then svo = svo + 2 end
			if cl[j] and t.u1 then coord = coord + 1 end
			if t.bucket ~= b[j] then layer = layer + 1 end
			if t.tex.bucketFrame ~= f[j] then parent = parent + 1 end
		end
	end
	local hide = snap.n - seen
	counted.svo, counted.layer, counted.parent, counted.show, counted.hide, counted.coord, counted.new = svo, layer, parent, show, hide, coord, new
	counted.total = svo + layer + parent + show + hide + coord
	return counted
end

------------------------------------------------------------------------------------------------
-- Frames the probe makes (made once, kept hidden between runs)
------------------------------------------------------------------------------------------------
local driver = CreateFrame("Frame")
driver:Hide()
P.driver = driver
P.made = { driver } -- every frame the probe made: all hidden at the end (the tests check)

local function Label(parent, text, x, y, r, g, b)
	local fs = parent:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	fs:SetPoint("CENTER", parent, "CENTER", x, y)
	fs:SetText(text)
	if r then fs:SetTextColor(r, g, b) end
	return fs
end

local function Panel()
	if P.panel then return P.panel end
	local panel = CreateFrame("Frame", nil, ns.frame)
	panel:SetFrameLevel(ns.canvas:GetFrameLevel() + 40) -- over the ground, the models and the markers
	panel:SetSize(640, 300)
	panel:SetPoint("CENTER", ns.canvas, "CENTER", 0, 0)
	panel:Hide()
	local bg = panel:CreateTexture(nil, "BACKGROUND")
	bg:SetAllPoints()
	bg:SetColorTexture(0, 0, 0, 0.92)
	P.panel = panel
	P.made[#P.made + 1] = panel
	return panel
end

local function Cross()
	if P.cross then return P.cross end
	local f = CreateFrame("Frame", nil, ns.canvas)
	f:SetAllPoints(ns.canvas)
	f:SetFrameLevel(ns.canvas:GetFrameLevel() + 30)
	f:Hide()
	f.h = f:CreateTexture(nil, "OVERLAY"); f.h:SetSize(21, 3)
	f.v = f:CreateTexture(nil, "OVERLAY"); f.v:SetSize(3, 21)
	f.h:SetColorTexture(1, 0.1, 0.1, 1); f.v:SetColorTexture(1, 0.1, 0.1, 1)
	P.cross = f
	P.made[#P.made + 1] = f
	return f
end
local function PlaceCross(x, y)
	local f = P.cross
	f.h:ClearAllPoints(); f.h:SetPoint("CENTER", ns.canvas, "CENTER", x, y)
	f.v:ClearAllPoints(); f.v:SetPoint("CENTER", ns.canvas, "CENTER", x, y)
end

------------------------------------------------------------------------------------------------
-- Timing
------------------------------------------------------------------------------------------------
local times = {} -- elapsed seconds of the timed frames of the phase running (reused)
local function Median(a, n)
	if n == 0 then return 0 end
	local s = {}
	for i = 1, n do s[i] = a[i] end
	table.sort(s)
	return n % 2 == 1 and s[(n + 1) / 2] or (s[n / 2] + s[n / 2 + 1]) / 2
end

-- One timed phase (still, redrawn, turning, ...): its frames timed, its Lua ms summed, its calls counted on a few frames
local function NewPhase(name)
	return { name = name, frames = 0, n = 0, lua = 0, luaN = 0, calls = 0, svo = 0, callsN = 0, new = 0 }
end
local function PhaseFrame(ph, elapsed, render, count)
	ph.frames = ph.frames + 1
	local k = ph.frames
	-- (the elapsed of frame k is the time since frame k-1: the change, and the counting, show up one later)
	if k > P.DROP and not (count and k <= P.DROP + P.COUNT + 1) then
		ph.n = ph.n + 1
		times[ph.n] = elapsed
	end
	if render then
		local counting = count and k > P.DROP and k <= P.DROP + P.COUNT
		if counting then P.Snapshot() end
		render()
		local st = ns.stats
		if counting then
			local c = P.Diff()
			ph.calls, ph.svo, ph.new, ph.callsN = ph.calls + c.total, ph.svo + c.svo, ph.new + c.new, ph.callsN + 1
		elseif k > P.DROP then
			ph.lua, ph.luaN = ph.lua + (st.ms or 0), ph.luaN + 1
		end
	end
end
local function PhaseEnd(ph)
	local sum = 0
	for i = 1, ph.n do sum = sum + times[i] end
	ph.med = Median(times, ph.n) * 1000
	ph.mean = ph.n > 0 and sum / ph.n * 1000 or 0
	ph.fps = GetFramerate and GetFramerate() or 0
	ph.luaMs = ph.luaN > 0 and ph.lua / ph.luaN or 0
	ph.callsAvg = ph.callsN > 0 and floor(ph.calls / ph.callsN + 0.5) or 0
	ph.svoAvg = ph.callsN > 0 and floor(ph.svo / ph.callsN + 0.5) or 0
	ph.tex = ns.stats.shown or 0
	return ph
end

------------------------------------------------------------------------------------------------
-- Where it measures: a fixed view, so you can run it from anywhere without moving (Morten plays Horde)
------------------------------------------------------------------------------------------------
-- name -> map, tile x, tile y (the middle of the view), what to call it; straight down from 330 yd, north up
P.PLACES = {
	orgrimmar = { 1, 40.21, 28.94, "Orgrimmar, Valley of Strength" },
	stormwind = { 0, 30.80, 48.56, "Stormwind, Trade District" },
}
P.DEFAULT_PLACE = "orgrimmar"

local function GoTo(place)
	local cam, T = ns.cam, ns.TILE
	cam.map, cam.x, cam.y = place[1], place[2] * T, -place[3] * T
	cam.dist, cam.yaw = 330, 0
	ns.SetTopDown(true, true)
	cam.th = ns.GroundHeight(cam.x, cam.y, cam.map) or cam.th
	if ns.SnapLift then ns.SnapLift() end
	ns.Redraw()
end

------------------------------------------------------------------------------------------------
-- Saving and putting back
------------------------------------------------------------------------------------------------
local function Save()
	local cam = ns.cam
	local g, b, d = ns.Budgets()
	local db = ns.DB()
	P.saved = {
		grid = g, buildings = b, detail = d, dbGrid = db.grid, dbBuildings = db.buildings, dbDetail = db.detail,
		x = cam.x, y = cam.y, th = cam.th, yaw = cam.yaw, map = cam.map, mode = ns.CamMode(),
		dist = cam.dist, pitch = cam.pitch, tiltBefore = cam.tiltBefore, topDown = ns.IsTopDown(), dbTopDown = (GPS3D_DB or {}).topDown,
		-- (the ground's level-of-detail controller: it has a dead band, so after the budgets and the turns it
		-- would settle on a slightly different tolerance; put back with the blocks' levels, the view is drawn
		-- as before)
		kappa = ns.Lod.kappa, target = ns.Lod.target, lodMap = ns.Lod.map,
		blocks = ns.BlockLevels(), -- (and the building blocks' levels, which keep last frame's within a margin)
	}
	P.settingsBack, P.cameraBack = false, false
end

local function RestoreSettings()
	local s = P.saved
	if not s or P.settingsBack then return end
	P.settingsBack = true
	local g, b, d = ns.Budgets()
	if g ~= s.grid then ns.SetGridBudget(s.grid) end
	if b ~= s.buildings then ns.SetBuildingBudget(s.buildings) end
	if d ~= s.detail then ns.SetDetail(s.detail) end
	local db = ns.DB()
	db.grid, db.buildings, db.detail = s.dbGrid, s.dbBuildings, s.dbDetail -- (the setters save; put back what was saved, nil included)
end

local function RestoreCamera()
	local s = P.saved
	if not s or P.cameraBack then return end
	P.cameraBack = true
	local cam = ns.cam
	cam.map, cam.x, cam.y, cam.th = s.map, s.x, s.y, s.th -- (the probe may have moved the view to a city)
	cam.dist, cam.yaw = s.dist, s.yaw
	if ns.IsTopDown() ~= s.topDown then ns.SetTopDown(s.topDown, true) end
	cam.pitch, cam.tiltBefore = s.pitch, s.tiltBefore
	if GPS3D_DB then GPS3D_DB.topDown = s.dbTopDown end
	if ns.SnapLift then ns.SnapLift() end
	if s.mode ~= ns.CamMode() then ns.SetCamMode(s.mode) end
	if ns.Lod.map == s.lodMap then ns.Lod.kappa, ns.Lod.target = s.kappa, s.target end
	ns.BlockLevels(s.blocks)
end

-- Part 4's anchors: the ground's textures anchored to their depth frame instead of the canvas (the
-- same place while the frame is not shifted), and back.
local anchored = {}
P.anchored = anchored
local function Unanchor()
	local bf = ns.bucketFrames
	for k = 1, #bf do
		if Has(bf[k], "ClearPointsOffset") then pcall(bf[k].ClearPointsOffset, bf[k]) end
	end
	for i = 1, #anchored do
		local tex = anchored[i]
		tex:ClearAllPoints()
		tex:SetPoint("CENTER", ns.canvas, "CENTER", 0, 0)
		anchored[i] = nil
	end
end

------------------------------------------------------------------------------------------------
-- The steps: { part, dur (seconds; nil: until frame returns true), start, frame(elapsed, t), done }
------------------------------------------------------------------------------------------------
local steps = {}
local cleanups = {} -- part -> function, run once when the part ends (or the probe stops)

local function Step(part, dur, start, frame, done)
	steps[#steps + 1] = { part = part, dur = dur, start = start, frame = frame, done = done }
end

-- Part 1 --------------------------------------------------------------------------------------
local rows = {}
P.rows = rows
local function Row(g, b)
	local row = { g = g, b = b }
	rows[#rows + 1] = row
	local still, redraw, turn
	Step(1, nil, function()
		row.t = 0
		ns.SetGridBudget(g)
		ns.SetBuildingBudget(b)
		row.calm = 0
	end, function(elapsed)
		-- settled: no building block waiting, and three redraws in a row that change (almost) nothing (the
		-- ground's level of detail eases to a new budget over a few dozen frames)
		row.t = row.t + elapsed
		P.Snapshot()
		ns.Render()
		local c = P.Diff()
		row.calm = (c.total <= 50 and (ns.stats.detailPending or 0) == 0) and row.calm + 1 or 0
		return row.t >= P.T.settleMax * P.scale or (row.t >= P.T.settle * P.scale and row.calm >= 3)
	end)
	Step(1, P.T.still, function() still = NewPhase("still") end, function(elapsed) PhaseFrame(still, elapsed, nil, false) end,
		function() row.still = PhaseEnd(still) end)
	Step(1, P.T.redraw, function() redraw = NewPhase("redraw") end, function(elapsed) PhaseFrame(redraw, elapsed, ns.Render, true) end,
		function() row.redraw = PhaseEnd(redraw) end)
	Step(1, P.T.turn, function() turn = NewPhase("turn") end, function(elapsed)
		ns.cam.yaw = (ns.cam.yaw + P.TURN * elapsed) % 360
		PhaseFrame(turn, elapsed, ns.Render, true)
	end, function() row.turn = PhaseEnd(turn) end)
end

-- least squares slope of y against x over the rows (nil when x does not vary)
local function Slope(xs, ys, n)
	local sx, sy, sxx, sxy = 0, 0, 0, 0
	for i = 1, n do sx, sy, sxx, sxy = sx + xs[i], sy + ys[i], sxx + xs[i] * xs[i], sxy + xs[i] * ys[i] end
	local den = n * sxx - sx * sx
	if n < 2 or abs(den) < 1e-9 then return nil end
	return (n * sxy - sx * sy) / den
end

local function Part1Report()
	local xs, ys, cs, ds, n = {}, {}, {}, {}, 0
	for _, r in ipairs(rows) do
		if r.still and r.redraw and r.turn then
			Say("ground %d, buildings %d: %d textures | still %.1f ms (%.0f fps) | redraw %.1f ms, Lua %.1f, %d calls | turn %.1f ms, Lua %.1f, %d calls (%d SetVertexOffset)",
				r.g, r.b, r.turn.tex, r.still.med, r.still.fps, r.redraw.med, r.redraw.luaMs, r.redraw.callsAvg,
				r.turn.med, r.turn.luaMs, r.turn.callsAvg, r.turn.svoAvg)
			n = n + 1
			xs[n], ys[n] = r.still.tex, r.still.med
			cs[n], ds[n] = r.turn.callsAvg, r.turn.med - r.turn.luaMs - r.still.med
		end
	end
	local perTex, perCall = Slope(xs, ys, n), Slope(cs, ds, n)
	Say("1/5 estimate from %d settings: %s per texture shown (still frame against textures), %s per C call (turning frame minus Lua minus still, against calls)",
		n, perTex and ("%.2f us"):format(perTex * 1000) or "n/a", perCall and ("%.3f us"):format(perCall * 1000) or "n/a")
	P.perTex, P.perCall = perTex, perCall
end

-- Parts 2 and 3: one picture --------------------------------------------------------------------
local function BuildFold(panel)
	local file = GPS.MEDIA .. "Probe"
	P.fold = P.fold or {}
	for k, corner in ipairs({ 1, 3 }) do
		local t = P.fold[k]
		if not t then t = panel:CreateTexture(nil, "ARTWORK"); P.fold[k] = t end
		t:SetTexture(file)
		t:SetSize(110, 110)
		t:ClearAllPoints()
		t:SetPoint("CENTER", panel, "CENTER", -235 + (k - 1) * 145, -20)
		if Has(t, "ClearVertexOffsets") then t:ClearVertexOffsets() end
		t:SetVertexOffset(corner, 0, 45) -- that corner lifted 45 px
		t:Show()
	end
	if not P.foldLabels then
		P.foldLabels = true
		Label(panel, "2/5 fold: which diagonal stays straight?", -162, 128, 1, 0.82, 0)
		Label(panel, "red straight = corners 1-4", -162, 110, 1, 0.35, 0.35)
		Label(panel, "blue straight = corners 2-3", -162, 96, 0.45, 0.6, 1)
		Label(panel, "corner 1 lifted", -235, -100)
		Label(panel, "corner 3 lifted", -90, -100)
	end
	return "shown"
end

local function BuildRotate(panel)
	local file = GPS.MEDIA .. "Probe"
	local function Tri(holder, ghost)
		local t = holder:CreateTexture(nil, ghost and "OVERLAY" or "ARTWORK")
		if ghost then t:SetColorTexture(1, 1, 1, 0.35) else t:SetTexture(file); t:SetTexCoord(0, 0, 0, 1, 1, 0, 1, 0) end
		t:SetSize(110, 110)
		t:SetPoint("CENTER", holder, "CENTER", 0, 0)
		-- a triangle as the ground draws one: upper left, lower left moved in, upper right moved down,
		-- the lower right pinned onto the upper right
		t:SetVertexOffset(2, 25, 0)
		t:SetVertexOffset(3, 0, -30)
		t:SetVertexOffset(4, 0, 80)
		return t
	end
	if not P.rot then
		local rot = {}
		for k, x in ipairs({ 105, 250 }) do
			local h = CreateFrame("Frame", nil, panel)
			h:SetSize(110, 110)
			h:SetPoint("CENTER", panel, "CENTER", x, -20)
			rot[k] = h
			h.tri = Tri(h)
		end
		local g = CreateFrame("Frame", nil, panel) -- the ghost: where the turned one was, not turned
		g:SetSize(110, 110)
		g:SetPoint("CENTER", panel, "CENTER", 250, -20)
		g:SetFrameLevel(rot[2]:GetFrameLevel() + 2)
		g.tri = Tri(g, true)
		rot.ghost = g
		P.rot = rot
		Label(panel, "3/5 RotateTextures(0.5)", 178, 128, 1, 0.82, 0)
		Label(panel, "triangle on the white ghost: only the image turned", 178, 110)
		Label(panel, "triangle turned off it: the geometry turned", 178, 96)
		Label(panel, "as drawn", 105, -100)
		Label(panel, "turned (white: where it was)", 250, -100)
	end
	local h = P.rot[2]
	if not Has(h, "RotateTextures") then return "missing" end
	local ok, err = pcall(h.RotateTextures, h, 0.5)
	if not ok then return "error: " .. tostring(err) end
	local r = Has(h.tri, "GetRotation") and select(2, pcall(h.tri.GetRotation, h.tri))
	return "called" .. (type(r) == "number" and (", the texture's GetRotation now %.2f"):format(r) or "")
end

-- Part 4 ----------------------------------------------------------------------------------------
local p4 = {}
P.p4 = p4

local function Part4Start()
	local bf = ns.bucketFrames
	p4.skip = nil
	if not Has(bf[1], "SetPointsOffset") then
		Say("4/5 SetPointsOffset: missing (Frame.SetPointsOffset is not there); part 4 skipped")
		p4.skip = true
		return
	end
	-- the fullest depth frame, and every texture drawn anchored to its own depth frame
	local count = {}
	for k = 1, #bf do count[k] = 0 end
	local vis = ns.stats.visible or {}
	for i = 1, ns.stats.shown or 0 do
		local tex = vis[i].tex
		local f = tex.bucketFrame or 1
		count[f] = count[f] + 1
		tex:ClearAllPoints()
		tex:SetPoint("CENTER", bf[f], "CENTER", 0, 0)
		anchored[#anchored + 1] = tex
	end
	local best = 1
	for k = 2, #bf do if count[k] > count[best] then best = k end end
	p4.frame, p4.count, p4.total = bf[best], count[best], ns.stats.shown or 0
	p4.base = NewPhase("base")
end

local function Part4ShiftStart()
	if p4.skip then return end
	p4.one = NewPhase("one")
	local f = p4.frame
	-- does it error? and is a fraction of a pixel kept (a texture's centre before and after 0.3 px)?
	local tex = anchored[1]
	local x0, y0
	if tex then x0, y0 = tex:GetCenter() end
	local ok, err = pcall(f.SetPointsOffset, f, 0.3, 0.3)
	p4.err = not ok and tostring(err) or nil
	if ok and tex and x0 then
		local x1, y1 = tex:GetCenter()
		p4.moved = x1 and (x1 - x0) or nil
	end
	if not ok then
		Say("4/5 SetPointsOffset: error: %s; part 4 skipped", p4.err)
		p4.skip = true
	end
end

local function Part4GlideStart()
	if p4.skip then return end
	if Has(p4.frame, "ClearPointsOffset") then pcall(p4.frame.ClearPointsOffset, p4.frame) end
	local cam = ns.cam
	p4.x0, p4.y0 = cam.x, cam.y
	p4.h = ns.GroundHeight(cam.x, cam.y)
	local sx, sy, d = ns.Project(cam.x, cam.y, p4.h)
	if not sx then p4.skip = true; Say("4/5 glide: the middle of the view is not in front of the camera; skipped"); return end
	p4.sx0, p4.sy0 = sx, sy
	local _, _, _, rx, ry = ns.CameraBasis()
	p4.dx, p4.dy = rx * P.SHIFT_PX * d / ns.Focal(), ry * P.SHIFT_PX * d / ns.Focal() -- yards: the ground slides SHIFT_PX left
	p4.glide = NewPhase("glide")
	Cross():Show()
	PlaceCross(sx, sy)
	p4.t = 0
	Say("4/5 watch the red cross and your arrow: the ground slides %d px without being redrawn; both should stay on the same spot of the ground (near the cross: tilted, further ground slides a little against it); at the end the ground is redrawn for real and should not jump", P.SHIFT_PX)
end

local function Part4GlideFrame(elapsed)
	if p4.skip then return true end
	p4.t = p4.t + elapsed
	local frac = min(1, p4.t / (P.T.glide * P.scale))
	local cam = ns.cam
	PhaseFrame(p4.glide, elapsed, nil, false)
	if frac >= 1 then
		-- the end: the camera stays where the last shifted frame showed it and the ground is drawn for
		-- real in this frame: if the shifted ground was right, nothing moves
		cam.x, cam.y = p4.x0 + p4.dx * (p4.frac or 0), p4.y0 + p4.dy * (p4.frac or 0)
		Unanchor()
		P.cross:Hide()
		ns.Render()
		return true
	end
	p4.frac = frac
	cam.x, cam.y = p4.x0 + p4.dx * frac, p4.y0 + p4.dy * frac
	local sx, sy = ns.Project(p4.x0, p4.y0, p4.h)
	if ns.RenderMarker then ns.RenderMarker() end
	local _, _, _, _, _, _, _, _, cx, cy, cz = ns.CameraBasis()
	if ns.scene and Has(ns.scene, "SetCameraPosition") then ns.scene:SetCameraPosition(cx, cy, cz) end
	cam.x, cam.y = p4.x0, p4.y0 -- (the 3D view's own update sees the camera unmoved: it redraws nothing)
	if sx then
		local bf = ns.bucketFrames
		for k = 1, #bf do bf[k]:SetPointsOffset(sx - p4.sx0, sy - p4.sy0) end
		PlaceCross(sx, sy)
	end
end

local function Part4Report()
	if p4.skip then return end
	Say("4/5 SetPointsOffset: no error; %d textures anchored to their depth frames, the fullest holds %d; frame time: none shifted %.1f ms, that one shifted every frame %.1f ms, all eight shifted (the glide) %.1f ms; a 0.30 px shift moved a texture's GetCenter by %s",
		p4.total or 0, p4.count or 0, p4.base and p4.base.med or 0, p4.one and p4.one.med or 0, p4.glide and p4.glide.med or 0,
		p4.moved and ("%.2f"):format(p4.moved) or "?")
end

-- Part 5 ----------------------------------------------------------------------------------------
local OFF_METHODS = { "TakeSnapshot", "ApplySnapshot", "IsSnapshotValid", "GetMaxSnapshots", "SetMaxSnapshots", "Flush", "UsesNPOT" }
local function Part5()
	local f = P.off
	if not f then
		local ok, made = pcall(CreateFrame, "OffScreenFrame", nil, UIParent)
		if not ok or not made then
			Say("5/5 OffScreenFrame: missing (CreateFrame: %s)", tostring(made))
			return
		end
		f = made
		f:Hide()
		f:SetSize(64, 64)
		f:SetPoint("CENTER")
		local c = CreateFrame("Frame", nil, f)
		c:SetAllPoints(f)
		local t = c:CreateTexture(nil, "ARTWORK")
		t:SetAllPoints(c)
		t:SetTexture(GPS.MEDIA .. "Probe")
		local hold = CreateFrame("Frame", nil, UIParent) -- a hidden frame for the texture a snapshot is applied to
		hold:Hide()
		f.target = hold:CreateTexture(nil, "ARTWORK")
		P.off = f
		P.made[#P.made + 1] = f
		P.made[#P.made + 1] = hold
	end
	local have, lack = {}, {}
	for _, m in ipairs(OFF_METHODS) do
		if Has(f, m) then have[#have + 1] = m else lack[#lack + 1] = m end
	end
	local function Call(m, ...)
		if not Has(f, m) then return "missing" end
		local r = { pcall(f[m], f, ...) }
		if not r[1] then return "error: " .. tostring(r[2]) end
		return tostring(r[2])
	end
	local hidden = Call("TakeSnapshot")
	f:Show() -- shown only for this call, hidden again before the frame is drawn
	local shown = Call("TakeSnapshot")
	f:Hide()
	local id = tonumber(shown) or tonumber(hidden)
	local applied = id and Call("ApplySnapshot", f.target, id) or "no snapshot"
	local valid = id and Call("IsSnapshotValid", id) or "-"
	Say("5/5 OffScreenFrame: made; methods there: %s; missing: %s; TakeSnapshot hidden -> %s, shown -> %s; ApplySnapshot -> %s; IsSnapshotValid -> %s; GetMaxSnapshots -> %s; UsesNPOT -> %s",
		#have > 0 and table.concat(have, " ") or "none", #lack > 0 and table.concat(lack, " ") or "none",
		hidden, shown, applied, valid, Call("GetMaxSnapshots"), Call("UsesNPOT"))
end

------------------------------------------------------------------------------------------------
-- The plan
------------------------------------------------------------------------------------------------
local function Plan()
	wipe(steps); wipe(rows); wipe(cleanups)
	-- 1
	if P.place then
		Step(1, 3, function()
			ns.SetCamMode("free")
			GoTo(P.place)
			Say("1/5 the view moved to %s (straight down, 330 yd), so you do not have to; it goes back when the probe ends", P.place[4])
		end, function() ns.Redraw() end) -- (a few seconds for the buildings there to load and be built)
	end
	Step(1, 0, function()
		local cam = ns.cam
		local W, H = ns.canvas:GetSize()
		Say("1/5 view: map %s, tile %.2f, %.2f, %.0f yd, tilt %.1f, yaw %.0f; canvas %.0f x %.0f, UI scale %.2f; buildings %s",
			tostring(cam.map), cam.x / ns.TILE, -cam.y / ns.TILE, cam.dist, cam.vp or cam.pitch, cam.yaw, W or 0, H or 0,
			UIParent.GetEffectiveScale and UIParent:GetEffectiveScale() or 1, select(3, ns.Budgets()) and "on" or "off")
		Say("1/5 cost per texture and per call: 6 settings, each still / redrawn / turning (frame ms median, GPS3D's Lua ms, calls a frame)")
		if not select(3, ns.Budgets()) then ns.SetDetail(true) end
		ns.SetCamMode("free")
	end)
	for _, s in ipairs(P.SETTINGS) do Row(s[1], s[2]) end
	Step(1, 0, function() Part1Report() end)
	cleanups[1] = function() RestoreSettings(); ns.cam.yaw = P.saved.yaw; ns.Render() end
	-- 2 and 3
	Step(2, P.T.picture, function()
		local panel = Panel()
		local ok, r = pcall(BuildFold, panel)
		P.foldResult = ok and r or ("error: " .. tostring(r))
		local ok3, r3 = pcall(BuildRotate, panel)
		P.rotResult = ok3 and r3 or ("error: " .. tostring(r3))
		panel:Show()
		Say("2/5 fold: %s. TAKE A SCREENSHOT NOW (Print Screen), the picture stays %d s. Two squares of the test picture, one corner lifted 45 px in each; in the picture a red diagonal joins corners 1-4 (upper left, lower right) and a blue one corners 2-3: the one that stays straight is the diagonal the game folds a bent texture along",
			P.foldResult, floor(P.T.picture * P.scale + 0.5))
		Say("3/5 RotateTextures: %s. On the right the same bent triangle as on the left, in a frame turned by RotateTextures(0.5), with a white ghost where it was: if it still covers the ghost, only the image inside turned (C2 is out); if it sits turned off the ghost, the geometry turned (C2 works)",
			P.rotResult)
	end)
	cleanups[2] = function() if P.panel then P.panel:Hide() end end
	-- 4
	Step(4, P.T.base, Part4Start, function(elapsed) if p4.skip then return true end PhaseFrame(p4.base, elapsed, nil, false) end,
		function() if p4.base then PhaseEnd(p4.base) end end)
	Step(4, P.T.shiftOne, Part4ShiftStart, function(elapsed)
		if p4.skip then return true end
		local t = p4.one.frames / 30
		p4.frame:SetPointsOffset(3 * sin(2 * pi * t), 2 * cos(2 * pi * t))
		PhaseFrame(p4.one, elapsed, nil, false)
	end, function() if p4.one and p4.one.frames > 0 then PhaseEnd(p4.one) end end)
	Step(4, nil, Part4GlideStart, Part4GlideFrame, function() if p4.glide and p4.glide.frames > 0 then PhaseEnd(p4.glide) end end)
	Step(4, P.T.hold, nil, function() return p4.skip end, Part4Report)
	cleanups[4] = function() Unanchor(); if P.cross then P.cross:Hide() end end
	-- 5
	Step(5, 0, Part5)
end

local function Planned(part) -- seconds planned (for one part, or all), the settling and the glide at their least
	local s, T = 0, P.T
	for _, st in ipairs(steps) do if not part or st.part == part then s = s + (st.dur or 0) end end
	if not part or part == 1 then s = s + #P.SETTINGS * T.settle end
	if not part or part == 4 then s = s + T.glide end
	return s * P.scale
end
P.Planned = Planned

------------------------------------------------------------------------------------------------
-- Running
------------------------------------------------------------------------------------------------
local function RunCleanup(part)
	local f = cleanups[part]
	if f then
		cleanups[part] = nil
		local ok, err = pcall(f)
		if not ok then Say("part %d: error putting things back: %s", part, tostring(err)) end
	end
end

local function Finish(why)
	if not P.running then return end
	P.running = false
	driver:Hide()
	for part = 1, 5 do RunCleanup(part) end
	pcall(RestoreSettings)
	pcall(RestoreCamera)
	for _, f in ipairs(P.made) do f:Hide() end
	pcall(ns.Render)
	if why then Say("stopped: %s; settings, camera and anchors put back", why)
	else Say("done in %.0f s; settings and camera put back. Send the chat lines (or SavedVariables\\GPS3D.lua after /reload) and the screenshot", GetTime() - P.began) end
	local db = ns.DB()
	db.probe = { when = date and date("%Y-%m-%d %H:%M:%S") or "", lines = P.lines }
end
P.Finish = Finish

local function Advance()
	local s = steps[P.i]
	if s and s.done then
		local ok, err = pcall(s.done)
		if not ok then Say("part %d: error: %s", s.part, tostring(err)) end
	end
	P.i = P.i + 1
	P.t = 0
	P.begun = false
	local nxt = steps[P.i]
	if s and (not nxt or nxt.part ~= s.part) then RunCleanup(s.part) end
end

local function Fail(s, err)
	Say("part %d: error: %s (the other parts go on)", s.part, tostring(err))
	local part = s.part
	while steps[P.i] and steps[P.i].part == part do P.i = P.i + 1 end
	P.t, P.begun = 0, false
	RunCleanup(part)
end

driver:SetScript("OnUpdate", function(_, elapsed)
	if not P.running then driver:Hide(); return end
	local s = steps[P.i]
	if not s then Finish(); return end
	if not P.begun then
		P.begun = true
		if s.start then
			local ok, err = pcall(s.start)
			if not ok then Fail(s, err); return end
		end
		if s.dur == 0 then Advance(); return end
		return -- (the frames of a step start with the next one: its first elapsed is not the change itself)
	end
	P.t = P.t + elapsed
	local doneNow = false
	if s.frame then
		local ok, r = pcall(s.frame, elapsed, P.t)
		if not ok then Fail(s, r); return end
		doneNow = r == true
	end
	if doneNow or (s.dur and P.t >= s.dur * P.scale) then Advance() end
end)

driver:SetScript("OnEvent", function(_, event)
	if event == "PLAYER_REGEN_DISABLED" and P.running then Finish("combat started") end
end)
driver:RegisterEvent("PLAYER_REGEN_DISABLED")
ns.frame:HookScript("OnHide", function() if P.running then Finish("the 3D window closed") end end)

function ns.Probe(arg)
	arg = (arg or ""):lower()
	if arg == "stop" then
		if P.running then Finish("/gps3d probe stop") else Say("not running") end
		return
	end
	if P.running then Say("already running (/gps3d probe stop ends it)") return end
	-- where: a city by name (default Orgrimmar), or "here" for the view as it is
	if arg == "" then arg = P.DEFAULT_PLACE end
	if arg == "here" then P.place = nil
	elseif P.PLACES[arg] then P.place = P.PLACES[arg]
	else Say("unknown place '%s': /gps3d probe [orgrimmar|stormwind|here|stop]", arg) return end
	if InCombatLockdown and InCombatLockdown() then
		Say("not in combat: it changes the 3D view's settings and frames for about a minute; run it again after the fight")
		return
	end
	GPS3D_API.Open()
	if not ns.frame:IsShown() then Say("the 3D window did not open") return end
	if not P.place and ns.cam.dist >= ns.MAX_DIST then Say("zoom in below %d yd first: it measures the ground, not the planet", ns.MAX_DIST) return end
	P.lines = {}
	Save()
	Plan()
	P.i, P.t, P.begun, P.running, P.began = 1, 0, false, true, GetTime()
	for k in pairs(p4) do p4[k] = nil end
	Say("starting: about %.0f s. Do not touch the mouse or the keys (no moving, no turning, no zoom) until it says done; /gps3d probe stop ends it at once. Part 1 measures for about %.0f s; then a test picture: take a screenshot when it asks; then the ground slides on its own for a few seconds. The lines also go to the debug log (if on) and to GPS3D_DB.probe",
		Planned(), Planned(1))
	driver:Show()
end
