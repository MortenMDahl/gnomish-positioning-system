-- GPS3D: your quests' objective areas on the ground (the tracked quest's, and the hovered marker's,
-- as on the 2D map). The game's quest-area frame (QuestPOIFrame) draws an area flat and cannot be
-- bent into perspective, so GPS's Quests.lua learns each area's shape from that frame's hit-test
-- (GPS_API.QuestAreas: pieces of at most 4 corners and closed outlines, in GPS grid coordinates) and
-- this file draws it: every corner at the ground height under it (GroundHeight: roofs where there are
-- building blocks, else the terrain), projected with the view's camera each frame like the terrain.
-- The fill is a translucent blue-violet and the border a brighter glow fading 3 px to each side of
-- the edge, the colours of Blizzard's area on the 2D map measured from Morten's screenshot (fill about
-- 0.16, 0.20, 0.86 at 60 %, border 0.30, 0.55, 1.0 at 75 %).
-- Layer: textures in your arrow's frame (canvas level + BUCKET_FRAMES + 1) at draw layer BORDER, so
-- over every ground frame, under your arrow (ARTWORK there), the game's models (+ 3), other addons'
-- markers (+ 4) and the quest markers (+ 5); hidden with that frame on the planet view (Globe.lua) and
-- faded with the markers between 14,000 and 18,000 yd. Like your arrow it is drawn over all the
-- ground, so a hill between the camera and the area does not hide it; pieces on slopes facing away
-- from the camera are left out. Per frame: no tables or closures are made.
local addonName, ns = ...
local GPS = GPS_API
if not (GPS and ns.frame and ns.decal and ns.questLayer) then return end

local A = {}
ns.questAreas = A
local TILE = ns.TILE
local FILL_R, FILL_G, FILL_B, FILL_A = 0.16, 0.20, 0.86, 0.6
local EDGE_R, EDGE_G, EDGE_B, EDGE_A = 0.30, 0.55, 1.0, 0.75
local EDGE_PX = 3  -- the border's glow each side of the edge, pixels
local NEAR_D = 1.5 -- a corner closer than this in front of the camera leaves its pieces out
local WHITE = "Interface\\Buttons\\WHITE8X8"
local sqrt, max = math.sqrt, math.max
local frame, canvas, cam = ns.frame, ns.canvas, ns.cam
local layer = ns.decal:GetParent()
local SetVertexOffset = ns.decal.SetVertexOffset

local fills, edges = {}, {} -- texture pools
A.fills, A.edges = fills, edges
A.nFill, A.nEdge, A.nShapes = 0, 0, 0 -- drawn last frame
local shownF, shownE, fade = 0, 0, 1
local px, py, pok = {}, {}, {} -- the shape's corners on screen (from the canvas centre, y up)
local ox, oy, ook = {}, {}, {}  -- outline: each entry's offset to one side (the mitre of its two segments)

-- So the "behind" way of finding areas (Quests.lua) can hide its frame in this window.
if GPS.SetQuestAreaHost then GPS.SetQuestAreaHost(frame, canvas) end

local function NewTex(list, sub, glow)
	local t = layer:CreateTexture(nil, "BORDER", nil, sub)
	t:SetTexture(WHITE)
	t:SetSize(1, 1)
	t:SetPoint("CENTER", canvas, "CENTER", 0, 0)
	if glow then
		-- top corners (1, 3) on the edge, bottom ones (2, 4) away from it
		t:SetGradient("VERTICAL", CreateColor(EDGE_R, EDGE_G, EDGE_B, 0), CreateColor(EDGE_R, EDGE_G, EDGE_B, EDGE_A))
	else
		t:SetVertexColor(FILL_R, FILL_G, FILL_B, FILL_A)
	end
	t:SetAlpha(fade)
	t:Hide()
	t.on = false
	list[#list + 1] = t
	return t
end

-- Heights of a shape's corners on the ground under them (once per shape, again if buildings are
-- switched on or off).
local function Heights(s)
	local key = (GPS3D_DB and GPS3D_DB.detail) and true or false
	if s.h3d and s.h3dKey == key then return s.h3d end
	local h = {}
	for v = 1, s.nv do h[v] = ns.GroundHeight(s.gx[v] * TILE, -s.gy[v] * TILE, s.map) end
	s.h3d, s.h3dKey = h, key
	return h
end
A.Heights = Heights

local function Outside(x1, y1, x2, y2, x3, y3, x4, y4, hw, hh)
	return (x1 < -hw and x2 < -hw and x3 < -hw and x4 < -hw) or (x1 > hw and x2 > hw and x3 > hw and x4 > hw)
		or (y1 < -hh and y2 < -hh and y3 < -hh and y4 < -hh) or (y1 > hh and y2 > hh and y3 > hh and y4 > hh)
end

local function DrawShape(s, nF, nE, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, hw, hh)
	local h, gx, gy = Heights(s), s.gx, s.gy
	for v = 1, s.nv do
		local dx, dy, dz = gx[v] * TILE - cx, -gy[v] * TILE - cy, h[v] - cz
		local d = dx * fx + dy * fy + dz * fz
		if d > NEAR_D then
			pok[v], px[v], py[v] = true, (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d
		else
			pok[v] = false
		end
	end
	-- the fill: one texture per piece, its corners where the piece's are
	local p1, p2, p3, p4 = s.p1, s.p2, s.p3, s.p4
	for k = 1, s.np do
		local a, b, c, d = p1[k], p2[k], p3[k], p4[k]
		if pok[a] and pok[b] and pok[c] and pok[d] then
			local ax, ay, bx, by, cx_, cy_, dx_, dy_ = px[a], py[a], px[b], py[b], px[c], py[c], px[d], py[d]
			-- pieces go clockwise seen from above: on screen (y up) a negative area faces the camera
			local area = (bx - ax) * (cy_ - ay) - (cx_ - ax) * (by - ay) + (cx_ - ax) * (dy_ - ay) - (dx_ - ax) * (cy_ - ay)
			if area < 0 and not Outside(ax, ay, bx, by, cx_, cy_, dx_, dy_, hw, hh) then
				nF = nF + 1
				local t = fills[nF] or NewTex(fills, 0)
				SetVertexOffset(t, 1, ax + 0.5, ay - 0.5)
				SetVertexOffset(t, 2, bx + 0.5, by + 0.5)
				SetVertexOffset(t, 4, cx_ - 0.5, cy_ + 0.5)
				SetVertexOffset(t, 3, dx_ - 0.5, dy_ - 0.5)
				if not t.on then t:Show(); t.on = true end
				t.shape, t.piece = s, k
			end
		end
	end
	-- the border: along each closed outline, a glow to each side of the edge
	local lv, ls, le = s.lv, s.ls, s.le
	for L = 1, #ls do
		local i0, i1 = ls[L], le[L]
		for i = i0, i1 do
			local v, vp, vn = lv[i], lv[i == i0 and i1 or i - 1], lv[i == i1 and i0 or i + 1]
			if pok[v] and pok[vp] and pok[vn] then
				local ax, ay = px[v] - px[vp], py[v] - py[vp]
				local bx, by = px[vn] - px[v], py[vn] - py[v]
				local la, lb = sqrt(ax * ax + ay * ay), sqrt(bx * bx + by * by)
				local n1x, n1y, n2x, n2y = 0, 0, 0, 0
				if la > 1e-6 then n1x, n1y = -ay / la, ax / la end
				if lb > 1e-6 then n2x, n2y = -by / lb, bx / lb end
				local nx, ny = n1x + n2x, n1y + n2y
				local l = sqrt(nx * nx + ny * ny)
				if l > 1e-6 then
					nx, ny = nx / l, ny / l
					local k = EDGE_PX / max(0.5, lb > 1e-6 and (nx * n2x + ny * n2y) or (nx * n1x + ny * n1y))
					ook[i], ox[i], oy[i] = true, nx * k, ny * k
				else
					ook[i], ox[i], oy[i] = true, n2x * EDGE_PX, n2y * EDGE_PX
				end
			else
				ook[i] = false
			end
		end
		for i = i0, i1 do
			local j = i == i1 and i0 or i + 1
			if ook[i] and ook[j] then
				local v, w = lv[i], lv[j]
				local x1, y1, x2, y2 = px[v], py[v], px[w], py[w]
				for side = 1, -1, -2 do
					local x3, y3, x4, y4 = x1 + side * ox[i], y1 + side * oy[i], x2 + side * ox[j], y2 + side * oy[j]
					if not Outside(x1, y1, x2, y2, x3, y3, x4, y4, hw, hh) then
						nE = nE + 1
						local t = edges[nE] or NewTex(edges, 1, true)
						SetVertexOffset(t, 1, x1 + 0.5, y1 - 0.5)
						SetVertexOffset(t, 3, x2 - 0.5, y2 - 0.5)
						SetVertexOffset(t, 2, x3 + 0.5, y3 + 0.5)
						SetVertexOffset(t, 4, x4 - 0.5, y4 + 0.5)
						if not t.on then t:Show(); t.on = true end
					end
				end
			end
		end
	end
	return nF, nE
end

-- Called from ns.UpdateQuestPins (GPS3D.lua), so with every frame the view draws.
function ns.UpdateQuestAreas()
	local nF, nE, nS = 0, 0, 0
	local list = GPS.QuestAreas and frame:IsShown() and GPS.QuestAreas(cam.map)
	if list and list[1] then
		local a = ns.questLayer:GetAlpha() -- faded with the markers toward the planet view (Globe.lua)
		if a ~= fade then
			fade = a
			for _, t in ipairs(fills) do t:SetAlpha(a) end
			for _, t in ipairs(edges) do t:SetAlpha(a) end
		end
		local F = ns.Focal()
		local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
		local hw, hh = canvas:GetWidth() / 2, canvas:GetHeight() / 2
		for _, s in ipairs(list) do
			if s.map == cam.map then
				nS = nS + 1
				nF, nE = DrawShape(s, nF, nE, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, hw, hh)
			end
		end
	end
	for i = nF + 1, shownF do local t = fills[i]; if t.on then t:Hide(); t.on = false end end
	for i = nE + 1, shownE do local t = edges[i]; if t.on then t:Hide(); t.on = false end end
	shownF, shownE = nF, nE
	A.nFill, A.nEdge, A.nShapes = nF, nE, nS
end

-- /gps3d test: how the areas are found (or why not), and what is drawn now.
function ns.QuestAreasSelfTest(Report)
	Report("quest areas: %s; drawn now: %d area(s), %d fill pieces, %d border pieces",
		GPS.QuestAreaStatus and GPS.QuestAreaStatus() or "GPS has no quest areas (older version)", A.nShapes, A.nFill, A.nEdge)
end
