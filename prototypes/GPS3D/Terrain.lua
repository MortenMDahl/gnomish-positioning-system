-- GPS 3D: the ground's mesh and level of detail (since 2026-10-22; J8, "uneven ground mesh"). Loaded after
-- GPS3D.lua, which keeps the drawing (ChooseTiles, BuildGridMesh, RenderWorld) and calls ns.Lod for the rest.
--
-- Each tile's 33 x 33 heights are a right-triangle bintree: the tile is two right triangles split along its
-- north-west to south-east diagonal, and a triangle splits at the middle of its long side into two halves;
-- ten rounds of that reach the full grid (2048 triangles). Every grid point but the corners is the middle of
-- one long side: its two ends are its parents (a coarser mesh has it half way between them), and the points
-- at the right angles of the triangles on that side must be in the mesh before it (no cracks inside a tile).
-- Data/Lod_<map>.lua (scripts/build_terrain_lod.py) gives every tile eleven nested levels, j = 0 (2048
-- triangles, every point) to 10 (the two halves of the tile): the points join in the order of how much
-- height error they take off, so a level puts its triangles where the relief is (a cliff gets many, a flat
-- field few) instead of spreading them evenly as the even grids of 2026-10-21 did (steps 1 to 32 cells).
-- Offline, at the far views of tools/sandbox/test_terrain.py and the triangle count J1 drew there, that
-- leaves 11-15 % less height error on screen than the even grid at its best (scripts/terrain_lod_study.py;
-- a free mesh per tile, which cannot be nested, 16-26 %); in the sandbox, at the same count, 6-21 % less
-- than the even grids (Mount Hyjal 6, Stormwind 16, Durotar 21, Thousand Needles 14, Stranglethorn 20).
-- Per level the data also has its triangle count, its mean height error and its largest triangles.
-- Levels 1 and 3 are not drawn (Lod.SKIP: making the finest meshes again at every level while zooming
-- cost too much time).
-- Choice (as J1's, GPS3D.lua's ChooseTiles): tile i may take level j once its nearest point is B_j away,
-- B_j = W * max(sqrt(G_j * Slant / tau), (GT_j * TEX / tau)^(1/3)), G_j the height error level j adds per
-- triangle it saves (from the stored mean errors), GT_j the same for the texture's linear mapping (from its
-- largest triangles; falls with the distance cubed). tau keeps the count at the target.
-- Morphing (Lod.Morph): a point a coarser level drops is drawn between its own height and the middle of its
-- two parents (as drawn), by its own distance d: its own height up to b - w, that middle from b (b: B of
-- the level that drops it), linearly in between, so a tile switching level moves nothing; w is a fifth of b,
-- but at least 150 yd or half of b (J1's), and wide enough that a point moves about 2 px a frame at most
-- zooming 2 % a frame (Window). d is the tile's nearest point (as the choice measures it), the
-- same for all its points: with J1's own distance per point, a tile's far side was drawn as a coarser level
-- than the tile's (that cost 5 % more error at the far views). Points on a tile edge use the edge's
-- nearest point and the smaller b of the two tiles (each tile's own level for that point), the same from
-- both sides, so a finer tile's edge lies on a coarser neighbour's straight edge: no cracks.
local addonName, ns = ...
local Lod = ns.Lod
if not Lod then return end

local TileHeights, TILE = ns.TileHeights, ns.TILE
local GRID, CELLS = 33, 32
local NP = GRID * GRID
local CELL = TILE / CELLS
local LEVELS = 10 -- levels 0..10
local floor, sqrt, abs, min, max = math.floor, math.sqrt, math.abs, math.min, math.max
local B64 = ns.B64

Lod.Q, Lod.WIDE, Lod.WK, Lod.TEX = 0.8, 150, 0.025, 0.03 -- (the morph window: Lod.Morph; the texture's part of the choice)
Lod.SKIP = { 1, 3 } -- (levels never drawn: Tile)

------------------------------------------------------------------------------------------------
-- The bintree on the grid (point p = j * 33 + i + 1, i east, j south, from the tile's north-west corner)
------------------------------------------------------------------------------------------------
local DEP, PA, PB, SIDE, ORDER = {}, {}, {}, {}, {}
do
	local function P(i, j) return j * GRID + i + 1 end
	local tri = { { P(32, 0), P(0, 0), P(32, 32) }, { P(0, 32), P(32, 32), P(0, 0) } } -- { apex, left, right }
	for _, c in ipairs({ P(0, 0), P(32, 0), P(0, 32), P(32, 32) }) do DEP[c] = 0 end
	for d = 1, 10 do
		local nxt = {}
		for _, t in ipairs(tri) do
			local apex, l, r = t[1], t[2], t[3]
			local m = (l + r) / 2 -- (the middle point's index: both coordinates are even sums)
			if not DEP[m] then DEP[m], PA[m], PB[m] = d, l, r end
			nxt[#nxt + 1] = { m, l, apex }
			nxt[#nxt + 1] = { m, apex, r }
		end
		tri = nxt
	end
	for d = 0, 10 do for p = 1, NP do if DEP[p] == d then ORDER[#ORDER + 1] = p end end end
	for p = 1, NP do
		local i, j = (p - 1) % GRID, floor((p - 1) / GRID)
		SIDE[p] = (j == 0 and 1) or (i == CELLS and 2) or (j == CELLS and 3) or (i == 0 and 4) or 0
	end
end
-- the point of the next tile that is the same point on a shared edge (side 1 north .. 4 west)
local function Mirror(p, side)
	if side == 1 then return p + CELLS * GRID elseif side == 2 then return p - CELLS elseif side == 3 then return p - CELLS * GRID end
	return p + CELLS
end
-- the middle of a long side l..r, or nil when it is not a grid point (the full grid's half cells)
local function Mid(l, r)
	local il, ir = (l - 1) % GRID, (r - 1) % GRID
	if (il + ir) % 2 ~= 0 or (floor((l - 1) / GRID) + floor((r - 1) / GRID)) % 2 ~= 0 then return nil end
	return (l + r) / 2
end

------------------------------------------------------------------------------------------------
-- A tile's levels (Data/Lod_<map>.lua; terrain_lod.encode): per level j = 0..10 its triangle count (2
-- characters), mean height error in 1/64 yd (3) and its largest triangles' depth (1), then each grid
-- point's coarsest level, 4 bits, three points to two characters
------------------------------------------------------------------------------------------------
local HEAD = 6 * (LEVELS + 1)
local function Num(s, pos, n)
	local v = 0
	for k = pos, pos + n - 1 do v = v * 64 + B64[s:byte(k)] end
	return v
end
-- a point's coarsest level (s: the tile's string; false: a flat tile, the even bintree)
local function LevelOf(s, p)
	if not s then return LEVELS - DEP[p] end
	local g = floor((p - 1) / 3)
	local v = Num(s, HEAD + 2 * g + 1, 2)
	local r = (p - 1) % 3
	if r == 1 then v = floor(v / 16) elseif r == 2 then v = floor(v / 256) end
	return v % 16
end
Lod.LevelOf = LevelOf

-- One height for points two tiles share (GPS3D.lua until 2026-10-22, moved): a corner as the planet view
-- takes it (the tile south-east of it first), an east edge from the tile to the east and a south edge from
-- the tile to the south (where they exist). (i, j: the point in the tile's grid, from 0.)
local function CornerHeight(map, i, j)
	local h = TileHeights(map, i, j)
	if h then return h[1] end
	h = TileHeights(map, i - 1, j); if h then return h[GRID] end
	h = TileHeights(map, i, j - 1); if h then return h[CELLS * GRID + 1] end
	h = TileHeights(map, i - 1, j - 1); if h then return h[NP] end
	return 0
end
local function Canon(map, tx, ty, h, i, j)
	if (i == 0 or i == CELLS) and (j == 0 or j == CELLS) then return CornerHeight(map, tx + i / CELLS, ty + j / CELLS) end
	if i == CELLS then
		local e = TileHeights(map, tx + 1, ty)
		if e then return e[j * GRID + 1] end
	elseif j == CELLS then
		local e = TileHeights(map, tx, ty + 1)
		if e then return e[i + 1] end
	end
	return h[j * GRID + i + 1]
end
Lod.Canon = Canon

-- A tile's record: s (its string, false when flat), T[0..10] triangles, G[j] = G_j and sG[j] = sqrt(G_j), GT[j] = GT_j and cT[j] = GT_j^(1/3)
-- (j = 1..10, never falling from level to level), B (thresholds this frame, f = that frame), nb (its four
-- neighbours' records, false: none). Without data for the map (no Lod file): the even bintree, errors
-- estimated from the height range (J1's estimates: mean error of an even step as a share of the range).
local PE = { 0.01, 0.02, 0.03, 0.042, 0.058, 0.08, 0.106, 0.14, 0.18, 0.23 }
local tiles = {}
local function Grow(v, T, out, raw, root) -- per triangle saved, never falling from level to level
	local g = 0
	for j = 1, LEVELS do
		local x = (v[j] - v[j - 1]) / (T[j - 1] - T[j])
		if x > g then g = x end
		out[j], raw[j] = root(g), g
	end
end
local function Cbrt(x) return x ^ (1 / 3) end
local E, X = {}, {}
local function Tile(map, tx, ty)
	if tx < 0 or tx > 63 or ty < 0 or ty > 63 then return false end
	local key = map * 4096 + ty * 64 + tx
	local r = tiles[key]
	if r ~= nil then return r end
	local h = TileHeights(map, tx, ty)
	if not h then tiles[key] = false return false end
	local data = ns.LodData and ns.LodData[map]
	local s = data and data[ty * 64 + tx] or false
	r = { map = map, tx = tx, ty = ty, s = s, T = {}, sG = {}, cT = {}, G = {}, GT = {}, B = {}, f = -1 }
	local T = r.T
	for j = 0, LEVELS do
		local depth
		if s then
			local p = 6 * j + 1
			T[j], E[j], depth = Num(s, p, 2), Num(s, p + 2, 3) / 64, Num(s, p + 5, 1)
		else
			T[j], E[j], depth = 2 ^ (11 - j), (j > 0 and not data) and (h.hi - h.lo) * PE[j] or 0, LEVELS - j
		end
		X[j] = TILE * TILE / 2 ^ depth -- its largest triangles' short side, squared
	end
	-- open sea is drawn in one colour (ns.OpenSeaTile): no image to map, so only its heights count
	if ns.OpenSeaTile(map, tx, ty) then for j = 0, LEVELS do X[j] = 0 end end
	Grow(E, T, r.sG, r.G, sqrt)
	Grow(X, T, r.cT, r.GT, Cbrt)
	-- levels 1 and 3 (1024 and 256 triangles) are not drawn: a tile goes from 2048 to 512 to 128 directly
	-- (their thresholds those of the next level), as the even grids did. Zooming in, a tile is made again
	-- at each level it passes, and the finest levels cost the most: with them a tile made 4,094 triangles on
	-- its way down, 2,814 without, the even grids 2,730; the far views use only levels 4 and up.
	for _, j in ipairs(Lod.SKIP) do r.G[j], r.sG[j], r.GT[j], r.cT[j] = r.G[j + 1], r.sG[j + 1], r.GT[j + 1], r.cT[j + 1] end
	tiles[key] = r
	return r
end
function Lod.Tile(map, tx, ty)
	local r = Tile(map, tx, ty)
	if not r.nb then r.nb = { Tile(map, tx, ty - 1), Tile(map, tx + 1, ty), Tile(map, tx, ty + 1), Tile(map, tx - 1, ty) } end
	return r
end

------------------------------------------------------------------------------------------------
-- The choice (called by ChooseTiles; Lod.cx, cy, dz2: the camera and its height over the ground it looks at)
------------------------------------------------------------------------------------------------
-- (VIEW: a height error shows on screen by the sine of the angle between the line of sight and the
-- vertical, across / distance at the tile's nearest point, but at least VIEW)
local function Slant(r)
	if r.sf == Lod.frame then return r.sl end
	local x0, y1 = r.tx * TILE, -r.ty * TILE
	local cx, cy = Lod.cx, Lod.cy
	local nx, ny = min(x0 + TILE, max(x0, cx)) - cx, min(y1, max(y1 - TILE, cy)) - cy
	local a2 = nx * nx + ny * ny
	local v = sqrt(a2 / (a2 + Lod.dz2))
	if v < Lod.VIEW then v = Lod.VIEW end
	r.sf, r.sl = Lod.frame, v -- (once a frame: Critical and Thresholds both ask)
	return v
end
-- this frame's thresholds of a tile (B[1..10], never falling)
local function Thresholds(r, now)
	if r.f == now then return r.B end
	r.f = now
	local sG, cT, B = r.sG, r.cT, r.B
	local W, TT = Lod.W, Lod.TT
	local it = W * sqrt(Slant(r) / Lod.tau)
	for j = 1, LEVELS do
		local b, t = sG[j] * it, cT[j] * TT
		B[j] = b > t and b or t
	end
	return B
end
Lod.Thresholds = Thresholds
-- the coarsest level whose threshold the tile's nearest point (ld away) is past
function Lod.Level(r, ld, now)
	local B, j = Thresholds(r, now), LEVELS
	while j > 0 and ld < B[j] do j = j - 1 end -- (from the coarse end: most tiles in view are far ones)
	return j
end
-- The budget: tile i may take level j from the tolerance max(G_j * W2[i], GT_j * W3[i]) (never falling from
-- level to level, as G and GT do not; worked out only for the levels a count looks at). Count: the
-- triangles at tolerance tau; Solve: the smallest tolerance (not under TAU_MIN) with at most target triangles.
local RC, W2s, W3s = {}, {}, {}
function Lod.Critical(i, r, ld, W)
	RC[i], W2s[i], W3s[i] = r, W * W * Slant(r) / (ld * ld), W * W * W * Lod.TEX / (ld * ld * ld)
end
local HINT = {} -- (per tile of the list, the level the last count gave it: the next count starts there)
local function Count(n, tau)
	local t = 0
	for i = 1, n do
		local r, w2, w3 = RC[i], W2s[i], W3s[i]
		local G, GT = r.G, r.GT
		local j = HINT[i] or 0
		if j > LEVELS then j = LEVELS end
		if j > 0 and G[j] * w2 > tau or j > 0 and GT[j] * w3 > tau then
			j = j - 1
			while j > 0 and (G[j] * w2 > tau or GT[j] * w3 > tau) do j = j - 1 end
		else
			while j < LEVELS and G[j + 1] * w2 <= tau and GT[j + 1] * w3 <= tau do j = j + 1 end
		end
		HINT[i] = j
		t = t + r.T[j]
	end
	return t
end
Lod.Count = Count
function Lod.Solve(n, target)
	local lo = Lod.TAU_MIN
	if n == 0 or Count(n, lo) <= target then return lo end
	local hi = lo
	for i = 1, n do -- every tile at its coarsest
		local r = RC[i]
		local a, b = r.G[LEVELS] * W2s[i], r.GT[LEVELS] * W3s[i]
		if b > a then a = b end
		if a > hi then hi = a end
	end
	if hi <= lo or Count(n, hi) > target then return hi end
	for _ = 1, 60 do
		local mid = sqrt(lo * hi)
		if Count(n, mid) <= target then hi = mid else lo = mid end
		if hi < lo * 1.001 then break end
	end
	return hi
end
-- the tolerance this frame (and the texture's part of the thresholds, the same for every tile)
function Lod.SetTau(tau, W)
	Lod.tau, Lod.W = tau, W
	Lod.TT = W * (Lod.TEX / tau) ^ (1 / 3)
end

-- Blocks of 4 x 4 tiles for ChooseTiles' first test: per block (by * 16 + bx) a sphere { x, y, h, radius }
-- holding the bounding spheres of its tiles (each round its tile's box, as ChooseTiles takes it), worked out
-- once per map.
local blockSpheres = {}
function Lod.Blocks(map)
	local list = blockSpheres[map]
	if list then return list end
	list = {}
	local m = ns.World[map] or {}
	for bk = 0, 255 do
		local bx, by = bk % 16, floor(bk / 16)
		local lo, hi, any = math.huge, -math.huge, false
		for ty = by * 4, by * 4 + 3 do
			for tx = bx * 4, bx * 4 + 3 do
				local h = m[ty * 64 + tx] and TileHeights(map, tx, ty)
				if h then any = true; lo = min(lo, h.lo); hi = max(hi, h.hi) end
			end
		end
		if any then
			local x, y, z, rad = (bx * 4 + 2) * TILE, -(by * 4 + 2) * TILE, (lo + hi) / 2, 0
			for ty = by * 4, by * 4 + 3 do
				for tx = bx * 4, bx * 4 + 3 do
					local h = m[ty * 64 + tx] and TileHeights(map, tx, ty)
					if h then
						local dx, dy, dz = (tx + 0.5) * TILE - x, -(ty + 0.5) * TILE - y, (h.lo + h.hi) / 2 - z
						local e = sqrt(dx * dx + dy * dy + dz * dz) + sqrt(TILE * TILE / 2 + (h.hi - h.lo) ^ 2 / 4)
						if e > rad then rad = e end
					end
				end
			end
			list[bk] = { x, y, z, rad * 1.0001 + 1 }
		end
	end
	blockSpheres[map] = list
	return list
end

------------------------------------------------------------------------------------------------
-- A tile's mesh at a level (BuildGridMesh in GPS3D.lua adds the textures): its points with their own
-- heights (g) and positions, the points that morph (coarsest first, so their parents are drawn before
-- them) and the triangles, corners in the order GPS3D draws them (counter-clockwise from above). The
-- triangles' corners are left in Lod.ta, tb, tc (1..count, the count returned) for BuildGridMesh.
------------------------------------------------------------------------------------------------
local ta, tb, tc = {}, {}, {}
Lod.ta, Lod.tb, Lod.tc = ta, tb, tc
local stack, LV, PTS, PLV = {}, {}, {}, {}
-- The points of a tile at a level, parents first, into PTS (and their coarsest levels into PLV); returns how
-- many. Levels COARSE and coarser read their list from the string (only their own points: a 2-triangle mesh
-- reads 4), finer ones go through every point's level.
local COARSE = 4
local LIST = HEAD + 2 * NP / 3 -- (where the coarse levels' counts start)
local function LevelPoints(s, level)
	local n = 0
	if not s then -- (a flat tile: the even bintree, every point by its depth)
		for q = 1, NP do
			local p = ORDER[q]
			if DEP[p] > LEVELS - level then break end
			n = n + 1
			PTS[n], PLV[n] = p, LEVELS - DEP[p]
		end
	elseif level >= COARSE then
		local count = Num(s, LIST + 2 * (level - COARSE) + 1, 2)
		local pos, j = LIST + 2 * (LEVELS - COARSE + 1), LEVELS
		local bound = Num(s, LIST + 2 * (j - COARSE) + 1, 2)
		for q = 1, count do
			while q > bound do j = j - 1; bound = Num(s, LIST + 2 * (j - COARSE) + 1, 2) end
			PTS[q], PLV[q] = Num(s, pos + 2 * q - 1, 2) + 1, j
		end
		n = count
	else
		for q = 0, NP / 3 - 1 do
			local c1, c2 = s:byte(HEAD + 2 * q + 1, HEAD + 2 * q + 2)
			local v = B64[c1] * 64 + B64[c2]
			LV[3 * q + 1], LV[3 * q + 2], LV[3 * q + 3] = v % 16, floor(v / 16) % 16, floor(v / 256) % 16
		end
		for q = 1, NP do
			local p = ORDER[q]
			local lp = LV[p]
			if lp >= level then n = n + 1; PTS[n], PLV[n] = p, lp end
		end
	end
	return n
end
function Lod.NewMesh(map, tx, ty, level, h)
	local r = Lod.Tile(map, tx, ty)
	local count = LevelPoints(r.s, level)
	local x0, y0 = tx * TILE, -ty * TILE
	local vx, vy, vh, g, fixed, at = {}, {}, {}, {}, {}, {}
	local mv, ma, mb, md, ms, mn, mw, ei = {}, {}, {}, {}, {}, {}, {}, {}
	local wmax, nm, k = {}, 0, 0
	for q = 1, count do
		local p, lp = PTS[q], PLV[q]
		k = k + 1
		local i, j = (p - 1) % GRID, floor((p - 1) / GRID)
		vx[k], vy[k] = x0 + i * CELL, y0 - j * CELL
		g[k] = Canon(map, tx, ty, h, i, j) -- its own height (vh: as drawn, Lod.Morph)
		vh[k] = g[k]
		at[p] = k
		local side = SIDE[p]
		-- vertices on the tile's edge are shared with neighbours (and T-junctions): always drawn exactly
		if side > 0 then fixed[k] = true end
		if DEP[p] > 0 then
			nm = nm + 1
			local a, b = at[PA[p]], at[PB[p]]
			local e = abs(g[k] - (g[a] + g[b]) * 0.5) -- its own error: how far it moves (the same from both sides of an edge)
			mv[nm], ma[nm], mb[nm], md[nm], ms[nm], mn[nm], mw[nm] = k, a, b, lp + 1, side, 0, e
			if side > 0 then
				ei[#ei + 1] = nm
				local o = r.nb[side]
				if o then mn[nm] = LevelOf(o.s, Mirror(p, side)) + 1 end -- (the next tile's level for it)
			elseif e > (wmax[lp + 1] or -1) then
				wmax[lp + 1] = e -- (per level that drops points inside, the one that moves furthest)
			end
		end
	end
	-- the triangles: the two halves of the tile (apex, left, right; the long side left..right), split while
	-- the middle of the long side is in the mesh
	local nt, sp = 0, 2
	stack[1], stack[2], stack[3] = CELLS + 1, 1, NP           -- north-east half
	stack[4], stack[5], stack[6] = CELLS * GRID + 1, NP, 1    -- south-west half
	while sp > 0 do
		local o = (sp - 1) * 3
		local apex, l, rr = stack[o + 1], stack[o + 2], stack[o + 3]
		local m = Mid(l, rr)
		if m and at[m] then
			stack[o + 1], stack[o + 2], stack[o + 3] = m, l, apex
			stack[o + 4], stack[o + 5], stack[o + 6] = m, apex, rr
			sp = sp + 1
		else
			sp = sp - 1
			-- counter-clockwise seen from above: in grid coordinates (j south) a negative cross product
			local ia, ja = (apex - 1) % GRID, floor((apex - 1) / GRID)
			local il, jl = (l - 1) % GRID, floor((l - 1) / GRID)
			local ir, jr = (rr - 1) % GRID, floor((rr - 1) / GRID)
			nt = nt + 1
			if (il - ia) * (jr - ja) - (ir - ia) * (jl - ja) < 0 then
				ta[nt], tb[nt], tc[nt] = at[apex], at[l], at[rr]
			else
				ta[nt], tb[nt], tc[nt] = at[apex], at[rr], at[l]
			end
		end
	end
	local mesh = { map = map, tx = tx, ty = ty, tkey = ty * 64 + tx, level = level, vx = vx, vy = vy, vh = vh, g = g, h = h, px = {}, py = {}, pd = {}, fixed = fixed, at = at,
		rec = r, nm = nm, mv = mv, ma = ma, mb = mb, md = md, ms = ms, mn = mn, mw = mw, ei = ei, wmax = wmax, st = {}, es = {} }
	return mesh, nt
end

------------------------------------------------------------------------------------------------
-- Morphing: the heights a grid mesh is drawn with this frame (cx, cy: the camera). A mesh none of whose
-- points is part way, each where it was last frame (own height or its parents' middle), keeps its heights.
------------------------------------------------------------------------------------------------
-- the window below b over which a point morphs: (1 - Q) of b, but at least WIDE yd or half of b, so that
-- near the camera, where a yard is many pixels, the ground does not move too fast while zooming (J1's);
-- and at least e = WK x the focal length (px) x the point's own error (yd), so that a point that moves far
-- (the uneven levels keep a cliff's points until coarse levels, where they move tens of yards) moves at
-- most about 2 px a frame zooming in at 2 % a frame; never more than 3/4 of b
local function Window(b, e)
	local w, m = b * (1 - Lod.Q), b * 0.5
	if m > Lod.WIDE then m = Lod.WIDE end
	if w < m then w = m end
	if w < e then w = e end
	m = b * 0.75
	return w < m and w or m
end
Lod.Window = Window
local Ns, E2 = {}, {}
function Lod.Morph(mesh, cx, cy, now)
	local n = mesh.nm
	if n == 0 then return end -- (the coarsest level: nothing morphs)
	local r = mesh.rec
	local B = Thresholds(r, now)
	local nb = r.nb
	for s = 1, 4 do local o = nb[s]; Ns[s] = o and Thresholds(o, now) or false end
	local dz2, WF = Lod.dz2, Lod.WK * Lod.F -- (WF: per yard a point moves, the window's least width)
	-- the distances: inside, the tile's nearest point (as ChooseTiles measures it); on each edge, the
	-- edge's nearest point (worked out the same way by both tiles)
	local tx, ty = mesh.tx, mesh.ty
	local x0, x1, y1, y0 = tx * TILE, (tx + 1) * TILE, -ty * TILE, -(ty + 1) * TILE
	local nx, ny = min(x1, max(x0, cx)) - cx, min(y1, max(y0, cy)) - cy
	local near2 = nx * nx + ny * ny + dz2
	E2[1] = nx * nx + (y1 - cy) ^ 2 + dz2
	E2[3] = nx * nx + (y0 - cy) ^ 2 + dz2
	E2[2] = (x1 - cx) ^ 2 + ny * ny + dz2
	E2[4] = (x0 - cx) ^ 2 + ny * ny + dz2
	local mv, ma, mb, md, ms, mn, mw = mesh.mv, mesh.ma, mesh.mb, mesh.md, mesh.ms, mesh.mn, mesh.mw
	-- is any point part way? inside: per level that drops points, its threshold; on the edges (few points)
	-- each against its own. States (1: at the middle, 0: own height) kept per mesh.
	local st, es = mesh.st, mesh.es
	local moving, changed = false, not st.ok
	local wmax = mesh.wmax
	for D = mesh.level + 1, LEVELS do
		local e = wmax[D]
		if e then
			local b = B[D]
			local a = b - Window(b, e * WF)
			local state
			if b * b <= near2 then state = 1 elseif a * a >= near2 then state = 0 else moving = true break end
			if st[D] ~= state then st[D] = state; changed = true end
		end
	end
	if not moving then
		local ei = mesh.ei
		for q = 1, #ei do
			local i = ei[q]
			local s = ms[i]
			local b, o = B[md[i]], Ns[s]
			if o then local b2 = o[mn[i]]; if b2 < b then b = b2 end end
			local a, d2 = b - Window(b, mw[i] * WF), E2[s]
			local state
			if b * b <= d2 then state = 1 elseif a * a >= d2 then state = 0 else moving = true break end
			if es[q] ~= state then es[q] = state; changed = true end
		end
	end
	if moving then st.ok = false elseif changed then st.ok = true else return end
	local g, vh = mesh.g, mesh.vh
	local Q, WIDE = Lod.Q, Lod.WIDE
	for i = 1, n do
		local k = mv[i]
		local b = B[md[i]]
		local s = ms[i]
		local d2 = near2
		if s > 0 then
			local o = Ns[s]
			if o then local b2 = o[mn[i]]; if b2 < b then b = b2 end end
			d2 = E2[s]
		end
		local mid = (vh[ma[i]] + vh[mb[i]]) * 0.5
		if d2 >= b * b then
			vh[k] = mid
		else
			local w, m = b * (1 - Q), b * 0.5 -- (Window, inlined)
			if m > WIDE then m = WIDE end
			if w < m then w = m end
			m = mw[i] * WF
			if w < m then w = m end
			m = b * 0.75
			if w > m then w = m end
			local A = b - w
			local own = g[k]
			if d2 <= A * A then
				vh[k] = own
			else
				vh[k] = own + (mid - own) * (sqrt(d2) - A) / w
			end
		end
	end
end

-- The drawn height of a grid mesh at a world point in its tile (for the tests: tools/sandbox/test_terrain.py,
-- test_world.py's SEAMCHECK): down the bintree to the mesh's triangle there.
function Lod.DrawnAt(mesh, x, y)
	local fi, fj = (x - mesh.tx * TILE) / CELL, (-mesh.ty * TILE - y) / CELL
	local at = mesh.at
	local apex, l, r
	if fi >= fj then apex, l, r = CELLS + 1, 1, NP else apex, l, r = CELLS * GRID + 1, NP, 1 end
	while true do
		local m = Mid(l, r)
		if not (m and at[m]) then break end
		-- the half the point lies in: (m, l, apex) or (m, apex, r), by the side of the line m..apex
		local im, jm = (m - 1) % GRID, floor((m - 1) / GRID)
		local ia, ja = (apex - 1) % GRID, floor((apex - 1) / GRID)
		local il, jl = (l - 1) % GRID, floor((l - 1) / GRID)
		local side = (ia - im) * (fj - jm) - (ja - jm) * (fi - im)
		local sideL = (ia - im) * (jl - jm) - (ja - jm) * (il - im)
		if (side >= 0) == (sideL >= 0) then apex, l, r = m, l, apex else apex, l, r = m, apex, r end
	end
	local x1, y1 = (apex - 1) % GRID, floor((apex - 1) / GRID)
	local x2, y2 = (l - 1) % GRID, floor((l - 1) / GRID)
	local x3, y3 = (r - 1) % GRID, floor((r - 1) / GRID)
	local det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
	local l2 = ((fi - x1) * (y3 - y1) - (x3 - x1) * (fj - y1)) / det
	local l3 = ((x2 - x1) * (fj - y1) - (fi - x1) * (y2 - y1)) / det
	local vh = mesh.vh
	local ka, kb, kc = at[apex], at[l], at[r]
	return vh[ka] * (1 - l2 - l3) + vh[kb] * l2 + vh[kc] * l3, ka, kb, kc, 1 - l2 - l3, l2, l3 -- (and the triangle's vertices and weights)
end
