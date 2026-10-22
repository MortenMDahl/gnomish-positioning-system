# What a decoded building block keeps (GPS3D.lua's BlockGeo, BlockHeight, BuildBlockMesh; since 2026-10-22, perf
# round step A4), checked and measured in Lua 5.4 (lupa) on the real data, 1280 x 800 window, buildings at the
# default budget.
#
# Since A4 the cache of decoded blocks (geoCache, GEO_LIMIT 400) keeps only what the meshes draw every frame (the
# vertices: vx, vy, vh); the triangle corners, the vertex colours and the palette are decoded again from the block's
# string when a mesh is made (into one set of arrays, ns.BlockTris) and, for heights, kept for the few blocks under
# the camera (BlockHeight's own small cache, ns.blockHold, HOLD blocks).
#
# The scenario per city (Stormwind round the Trade District, Mage Quarter, Cathedral and Old Town; Orgrimmar round
# the Valley of Strength): you fly a lap at 10 yd a frame with the camera following at 330 yd tilted 45, then
# straight down, then walk 0.25 yd a frame (a run at 30 fps) tilted 45, the camera's lift reading the roofs ahead.
# Measured (BM_PASS=time, the default): the cache's Lua heap (every block the cache holds decoded afresh into new
# arrays, and the heights asked again for the blocks it holds them for, the difference of the collected heap), the
# whole Lua heap after the scenario, Render's Lua ms while walking and flying (GC stopped during the frame, without
# the sandbox's slow SetParent), BlockHeight's decodes.
# Checks (memory and kept fail on the code before):
#   memory    the cache's heap per block is under 65 % of what it was before in both cities (BEFORE below, measured
#             on the code before with GPS3D_LUA=<file>; the review estimated -40-50 %)
#   kept      no cached block keeps triangle corners, vertex colours or a palette; at most HOLD blocks keep their
#             corners for heights
#   heights   GroundHeight on a 4 yd grid over each city (and the same points in a shuffled order, which makes
#             BlockHeight's small cache forget and decode again all the time) is exactly a full decode's height
#             (the block decoded on its own here, its triangles found the same way)
#   corners   ns.BlockTris gives exactly the full decode's corners, colours and palette (blocks round each city,
#             all three levels), and the meshes drawn are made from them (every block triangle drawn: its corners
#             and its image or colour against the full decode)
# BM_DUMP=<file> writes the heights (sha1 of every grid point's height, both orders) and the drawn views (every
# texture shown) per city; BM_COMPARE=<file> compares with such a dump (the code before against this one).
# MEASURE=1 only measures. GPS3D_LUA=<file> loads another GPS3D.lua (the code before).
import lupa.lua54 as lupa54, math, os, sys, json, hashlib, random
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())
toc = open(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
ALT = os.environ.get('GPS3D_LUA')
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua']), ('GPS3D', gps3d_files)]:
    for f in files:
        path = ALT if (ALT and addon == 'GPS3D' and f == 'GPS3D.lua') else f'{SITE}/addons/{addon}/{f}'
        ok = G.SANDBOX_LOAD(addon, f, open(path).read())
        if not ok: print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')
TILE = 1600 / 3
W, H = 1280, 800
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
def place(X, Y, m, facing=0.0):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, '', '', -1, -1, -1)
ns = G.SANDBOX.namespaces['GPS3D']
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

place(-8958.3, -190, 0, 0.3)
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
G.GPS3D_DB.buildingModels = 'simple'; ns.ModelsChanged()
cam, st = ns.cam, ns.stats
print('code', ALT or 'sandbox copy')

L.execute(r'''
BM = {}
local ns = SANDBOX.namespaces.GPS3D
local function findup(f, name) for i = 1, 300 do local n, v = debug.getupvalue(f, i); if not n then return end; if n == name then return v, i end end end
BM.findup = findup
local RW = findup(ns.Render, 'RenderWorld')
local meshes = findup(RW, 'meshes')
local geoCache, geoCacheI = findup(ns.BlockGeo, 'geoCache')
local _, geoCountI = findup(ns.BlockGeo, 'geoCount')
local pool = findup(ns.BlockGeo, 'pool')
local GroundHeight = findup(ns.GroundHeight, 'GroundHeight')
local BlockHeight = findup(GroundHeight, 'BlockHeight')
local BuildBlockMesh = findup(RW, 'BuildBlockMesh')
local MinimapFile, OverviewOf = findup(BuildBlockMesh, 'MinimapFile'), findup(BuildBlockMesh, 'OverviewOf')
local WALL_STEEPNESS = findup(BuildBlockMesh, 'WALL_STEEPNESS')
local CLOCK_S = findup(GetTime, 'S')
local TILE, BLOCK, BLOCKS = ns.TILE, ns.BLOCK, 8
local STEP = TILE / 64 / 8
local WHITE = 'interface\\buttons\\white8x8'
local SUN = { -0.4, 0.8, -0.35 }
do local l = math.sqrt(SUN[1] ^ 2 + SUN[2] ^ 2 + SUN[3] ^ 2) SUN[1], SUN[2], SUN[3] = SUN[1] / l, SUN[2] / l, SUN[3] / l end
local B64 = ns.B64
function BM.Advance(dt) CLOCK_S.time = CLOCK_S.time + dt end

-- a block decoded on its own (the format as GPS3D.lua documents it), with its height lookup built the way
-- BlockHeight builds it (8 x 8 cells of the triangles' boxes) but from this decode
local refs, nrefs = {}, 0
local function Num(s, pos, n) local v = 0; for i = pos, pos + n - 1 do v = v * 64 + B64[s:byte(i)] end return v end
local function Ref(map, tx, ty, bi, lv)
  local key = ((map * 4096 + ty * 64 + tx) * 64 + bi) * 4 + lv
  local r = refs[key]
  if r then return r end
  local tb = ns.TileBlocks(map, tx, ty, lv)
  local s, pos = tb.s, tb[bi]
  local base = (Num(s, pos + 1, 3) - 131072) * 0.25
  local nv, nt, np = Num(s, pos + 4, 3), Num(s, pos + 7, 3), Num(s, pos + 10, 1)
  local p = pos + 11
  local pal = {}
  for k = 1, np do pal[k] = { Num(s, p, 1) / 63, Num(s, p + 1, 1) / 63, Num(s, p + 2, 1) / 63 }; p = p + 3 end
  local x0, y0 = tx * TILE + (bi % BLOCKS) * BLOCK, -ty * TILE - math.floor(bi / BLOCKS) * BLOCK
  local vx, vy, vh, vc = {}, {}, {}, {}
  for k = 1, nv do
    local v = Num(s, p, 6)
    vc[k] = v % 64; v = v // 64
    vh[k] = base + (v % 65536) * 0.25; v = v // 65536
    vy[k] = y0 - (v % 128) * STEP; vx[k] = x0 + (v // 128) * STEP
    p = p + 6
  end
  local w = nv > 4095 and 3 or 2
  local idx = {}
  for k = 1, nt * 3 do idx[k] = Num(s, p, w) + 1; p = p + w end
  r = { vx = vx, vy = vy, vh = vh, vc = vc, idx = idx, pal = pal, nv = nv, nt = nt, x0 = x0, y0 = y0, map = map, tx = tx, ty = ty, lv = lv }
  nrefs = nrefs + 1
  if nrefs > 300 then refs, nrefs = {}, 0 end
  refs[key] = r
  return r
end
BM.Ref = Ref
local function RefHeight(r, x, y)
  local cs = BLOCK / 8
  local vx, vy, vh, idx = r.vx, r.vy, r.vh, r.idx
  if not r.cells then
    local cells = {}
    for q = 0, 63 do cells[q] = {} end
    for k = 1, r.nt do
      local a, b, c = idx[k * 3 - 2], idx[k * 3 - 1], idx[k * 3]
      local c0 = math.max(0, math.floor((math.min(vx[a], vx[b], vx[c]) - r.x0) / cs))
      local c1 = math.min(7, math.floor((math.max(vx[a], vx[b], vx[c]) - r.x0) / cs))
      local r0 = math.max(0, math.floor((r.y0 - math.max(vy[a], vy[b], vy[c])) / cs))
      local r1 = math.min(7, math.floor((r.y0 - math.min(vy[a], vy[b], vy[c])) / cs))
      for row = r0, r1 do for col = c0, c1 do local l = cells[row * 8 + col]; l[#l + 1] = k end end
    end
    r.cells = cells
  end
  local col, row = math.floor((x - r.x0) / cs), math.floor((r.y0 - y) / cs)
  if col < 0 or col > 7 or row < 0 or row > 7 then return nil end
  local best
  for _, k in ipairs(r.cells[row * 8 + col]) do
    local a, b, c = idx[k * 3 - 2], idx[k * 3 - 1], idx[k * 3]
    local ax, ay, bx, by, cx, cy = vx[a], vy[a], vx[b], vy[b], vx[c], vy[c]
    local den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if den ~= 0 then
      local w1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
      local w2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
      local w3 = 1 - w1 - w2
      if w1 >= -1e-6 and w2 >= -1e-6 and w3 >= -1e-6 then
        local h = w1 * vh[a] + w2 * vh[b] + w3 * vh[c]
        if not best or h > best then best = h end
      end
    end
  end
  return best
end
-- the ground height at a point from the full decode: GroundHeight's rule (the fine block there, else the grid)
local function FullHeight(map, x, y)
  local tx, ty = math.floor(x / TILE), math.floor(-y / TILE)
  local tb = ns.TileBlocks(map, tx, ty)
  if tb then
    local bx = math.min(BLOCKS - 1, math.max(0, math.floor((x - tx * TILE) / BLOCK)))
    local by = math.min(BLOCKS - 1, math.max(0, math.floor((-ty * TILE - y) / BLOCK)))
    if tb[by * BLOCKS + bx] then
      local h = RefHeight(Ref(map, tx, ty, by * BLOCKS + bx, 1), x, y)
      if h then return h end
    end
  end
  return ns.GridHeight(map, x, y) or 0
end

-- heights on a grid (x0..x1 east, y0..y1 north, step yd), in rows or shuffled (order: a list of point numbers);
-- each against the full decode; a sha1-able text of every height
function BM.Heights(map, x0, x1, y0, y1, step, order)
  local nx = math.floor((x1 - x0) / step) + 1
  local ny = math.floor((y1 - y0) / step) + 1
  local out, n, wrong, firstWrong, onBlocks = {}, 0, 0, nil, 0
  local total = order and #order or nx * ny
  for q = 1, total do
    local i = order and order[q] - 1 or q - 1
    local x, y = x0 + (i % nx) * step, y1 - (i // nx) * step
    local h = ns.GroundHeight(x, y, map)
    local want = FullHeight(map, x, y)
    if h ~= want then wrong = wrong + 1; firstWrong = firstWrong or ('%.1f %.1f: %s for %s'):format(x, y, tostring(h), tostring(want)) end
    if ns.GridHeight(map, x, y) ~= h then onBlocks = onBlocks + 1 end
    n = n + 1
    out[n] = ('%.17g'):format(h)
  end
  return n, wrong, firstWrong, onBlocks, table.concat(out, ' ')
end
function BM.Count(map, x0, x1, y0, y1, step)
  return (math.floor((x1 - x0) / step) + 1) * (math.floor((y1 - y0) / step) + 1)
end

-- ns.BlockTris (since A4) or the cached block's own arrays (the code before): corners, colours, palette
local function Tris(g)
  if ns.BlockTris then return ns.BlockTris(g, {}, {}, {}) end
  return g.idx, g.vc, g.pal
end
local function same(a, b) return type(a) == 'number' and type(b) == 'number' and math.abs(a - b) <= 1e-9 * math.max(1, math.abs(a), math.abs(b)) end
-- every block of the tiles round (tx, ty), all levels: BlockGeo's vertices and the corners, colours and palette
-- (ns.BlockTris) against the full decode
function BM.TrisCheck(map, tx0, ty0, r)
  local n, wrong, what, tris = 0, 0, nil, 0
  for ty = ty0 - r, ty0 + r do
    for tx = tx0 - r, tx0 + r do
      for lv = 1, 3 do
        local tb = ns.TileBlocks(map, tx, ty, lv)
        for bi = 0, 63 do
          if tb and tb[bi] then
            n = n + 1
            local g = ns.BlockGeo(map, tx, ty, bi, lv)
            local ref = Ref(map, tx, ty, bi, lv)
            local idx, vc, pal = Tris(g)
            local ok = g.nv == ref.nv and g.nt == ref.nt and #g.vx == ref.nv and #g.vy == ref.nv and #g.vh == ref.nv and #vc == ref.nv and #idx == 3 * ref.nt and #pal == #ref.pal
            if not ok then what = what or 'lengths' end
            for k = 1, ref.nv do if not (same(g.vx[k], ref.vx[k]) and same(g.vy[k], ref.vy[k]) and same(g.vh[k], ref.vh[k]) and vc[k] == ref.vc[k]) then ok = false; what = what or 'vertex' break end end
            for k = 1, 3 * ref.nt do if idx[k] ~= ref.idx[k] then ok = false; what = what or 'corner' break end end
            for k = 1, #ref.pal do local a, b = pal[k], ref.pal[k]; if not (a and same(a[1], b[1]) and same(a[2], b[2]) and same(a[3], b[3])) then ok = false; what = what or 'palette' break end end
            tris = tris + ref.nt
            if not ok then wrong = wrong + 1 end
          end
        end
      end
    end
  end
  return n, wrong, what, tris
end

-- every block mesh drawn this frame: its triangles' corners and their image or colour from the full decode
BM.drawnTris, BM.drawnBad, BM.drawnWhat = 0, 0, nil
local function lower(f) return type(f) == 'string' and f:lower():gsub('/', '\\') or f end
function BM.CheckDrawn()
  local frameNo = findup(RW, 'frameNo')
  for key, m in pairs(meshes) do
    if m.detail and m.active == frameNo then
      local k4 = -key
      local lv = k4 % 4
      local bk = (k4 - lv) // 4
      local bi = bk % 64
      local tk = (bk - bi) // 64
      local map, tile = tk // 4096, tk % 4096
      local tx, ty = tile % 64, tile // 64
      local r = Ref(map, tx, ty, bi, lv)
      local vx, vy, vh, vc, idx, pal = r.vx, r.vy, r.vh, r.vc, r.idx, r.pal
      local file = MinimapFile(map, tx, ty)
      if not file then file = OverviewOf(map, tx, ty) end
      if #m.tris ~= r.nt then BM.drawnBad = BM.drawnBad + 1; BM.drawnWhat = BM.drawnWhat or 'count' end
      for k = 1, math.min(#m.tris, r.nt) do
        local t = m.tris[k]
        local a, b, c = idx[3 * k - 2], idx[3 * k - 1], idx[3 * k]
        BM.drawnTris = BM.drawnTris + 1
        local ok = t.a == a and t.b == b and t.c == c
        -- its image or colour: a wall (by BuildBlockMesh's rule, from this decode's colours) is WHITE in the
        -- palette colour shaded, else the tile's image
        local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
        local ex2, eh2, ez2 = vx[c] - vx[a], vh[c] - vh[a], -(vy[c] - vy[a])
        local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
        local l = math.sqrt(nx * nx + nh * nh + nz * nz)
        if l > 0 then nx, nh, nz = nx / l, nh / l, nz / l end
        local wall, top
        if math.abs(nh) < WALL_STEEPNESS then
          top = a
          if vh[b] > vh[top] then top = b end
          if vh[c] > vh[top] then top = c end
          if vc[top] > 0 then wall = top
          elseif lv > 1 then
            for _, q in ipairs({ a, b, c }) do if vc[q] > 0 and (not wall or vh[q] > vh[wall]) then wall = q end end
          end
        end
        local tex = t.tex
        if wall then
          local shade = 0.45 + 0.55 * math.abs(nx * SUN[1] + nh * SUN[2] + nz * SUN[3])
          local col = pal[vc[wall]] or pal[1]
          local got = tex._color
          ok = ok and lower(tex._file) == lower(WHITE) and same(got[1], col[1] * shade) and same(got[2], col[2] * shade) and same(got[3], col[3] * shade)
        else
          ok = ok and lower(tex._file) == lower(file)
        end
        if not ok then BM.drawnBad = BM.drawnBad + 1; BM.drawnWhat = BM.drawnWhat or ('triangle %d of block %d'):format(k, bk) end
      end
    end
  end
end

-- the cache's Lua heap: every block it holds decoded afresh into new arrays (the cache emptied, the forgotten
-- blocks' arrays set aside), and the heights asked again for the blocks it holds them for (the code before: the
-- blocks with their height cells; since A4: BlockHeight's held blocks); then the cache as it was
local function Heap() collectgarbage('collect'); collectgarbage('collect'); return collectgarbage('count') end
BM.Heap = Heap
function BM.CacheMem()
  local list, saved, nsaved = {}, {}, 0
  local hold = ns.blockHold
  local heightKeys = {}
  for k, g in pairs(geoCache) do
    saved[k] = g; nsaved = nsaved + 1
    list[#list + 1] = { g.map, g.tx, g.ty, g.bi, g.level }
    if g.cells then heightKeys[#heightKeys + 1] = { g.map, g.tx, g.ty, g.bi } end
  end
  if hold then for i = 1, #hold do local e = hold[i]; heightKeys[#heightKeys + 1] = { e.map, e.tx, e.ty, e.bi } end end
  local _, savedCount = debug.getupvalue(ns.BlockGeo, geoCountI)
  local savedPool, savedHold = pool.geo, {}
  if hold then for i = 1, #hold do savedHold[i] = hold[i]; hold[i] = nil end end
  for k in pairs(saved) do geoCache[k] = nil end
  debug.setupvalue(ns.BlockGeo, geoCountI, 0)
  pool.geo = { n = 0 }
  local h0 = Heap()
  local nv, nt = 0, 0
  for _, b in ipairs(list) do local g = ns.BlockGeo(b[1], b[2], b[3], b[4], b[5]); nv = nv + g.nv; nt = nt + g.nt end
  local h1 = Heap()
  for _, b in ipairs(heightKeys) do
    local g = ns.BlockGeo(b[1], b[2], b[3], b[4], 1)
    BlockHeight(g, g.x0 + 1, g.y0 - 1)
  end
  local h2 = Heap()
  -- back as it was
  for k in pairs(geoCache) do geoCache[k] = nil end
  for k, g in pairs(saved) do geoCache[k] = g end
  debug.setupvalue(ns.BlockGeo, geoCountI, savedCount)
  pool.geo = savedPool
  if hold then for i = 1, math.max(#hold, #savedHold) do hold[i] = savedHold[i] end end
  return nsaved, (h1 - h0), (h2 - h1), nv, nt, #heightKeys
end
-- the blocks BlockHeight is asked for (distinct, per frame): GroundHeight's BlockHeight wrapped, nothing else changed
BM.asked, BM.nasked = {}, 0
do
  local f, i = findup(GroundHeight, 'BlockHeight')
  debug.setupvalue(GroundHeight, i, function(g, x, y)
    if not BM.asked[g.key] then BM.asked[g.key] = true; BM.nasked = BM.nasked + 1 end
    return f(g, x, y)
  end)
end
function BM.Asked() local n = BM.nasked; BM.asked, BM.nasked = {}, 0; return n end
-- the time spent making blocks (BlockGeo and BuildBlockMesh as RenderWorld calls them) and asking blocks' heights
-- (GroundHeight's BlockGeo and BlockHeight), per frame
BM.bt, BM.ht, BM.built, BM.rebuilt = 0, 0, 0, 0
do
  local clock = os.clock
  local f, i = findup(RW, 'BlockGeo')
  debug.setupvalue(RW, i, function(...) local t = clock(); local a, b = f(...); BM.bt = BM.bt + clock() - t; return a, b end)
  local f2, i2 = findup(RW, 'BuildBlockMesh')
  debug.setupvalue(RW, i2, function(g) local t = clock(); local a = f2(g); BM.bt = BM.bt + clock() - t; BM.built = BM.built + 1; return a end)
  local f3, i3 = findup(GroundHeight, 'BlockHeight')
  debug.setupvalue(GroundHeight, i3, function(...) local t = clock(); local a = f3(...); BM.ht = BM.ht + clock() - t; return a end)
  local f4, i4 = findup(GroundHeight, 'BlockGeo') -- (the blocks heights are asked of, decoded at the fine level)
  debug.setupvalue(GroundHeight, i4, function(...) local t = clock(); local a = f4(...); BM.ht = BM.ht + clock() - t; return a end)
end
function BM.Times() local a, b, n = BM.bt, BM.ht, BM.built; BM.bt, BM.ht, BM.built = 0, 0, 0; return a * 1000, b * 1000, n end
function BM.Kept()
  local withTris, withHeights = 0, 0
  for k, g in pairs(geoCache) do
    if g.idx or g.vc or g.pal then withTris = withTris + 1 end
    if g.cells then withHeights = withHeights + 1 end
  end
  local hold = ns.blockHold
  return withTris, withHeights + (hold and #hold or 0), hold and hold.HOLD or -1, hold and hold.decodes or -1
end
-- (the sandbox's SetParent looks the texture up in its old frame's list, thousands long: its time is taken out of
-- the Lua ms reported; in the game it is one C call)
local SP = { t = 0 }
do
  local Texture = getmetatable(UIParent:CreateTexture())
  local f, clock = Texture.SetParent, os.clock
  Texture.SetParent = function(...) local t = clock(); f(...); SP.t = SP.t + clock() - t end
end
function BM.Frame(f)
  collectgarbage('collect'); collectgarbage('stop')
  local k0 = collectgarbage('count')
  local s0 = SP.t
  local t0 = os.clock()
  f()
  local ms = (os.clock() - t0) * 1000
  local kb = collectgarbage('count') - k0
  collectgarbage('restart')
  return ms - (SP.t - s0) * 1000, kb
end
function BM.Time(f, ...)
  local t0 = os.clock()
  local x, y, h = f(...)
  return (os.clock() - t0) * 1000, ('%.17g %.17g %.17g'):format(x or 0, y or 0, h or 0)
end
function BM.Signature()
  local rows = {}
  for fi, f in ipairs(ns.bucketFrames) do
    for _, t in ipairs(f._regions) do
      if t._shown and t._parent == f then
        local tc, c, vo = t._tc or {}, t._color, t._vo or {}
        local r = { fi, t._layer, t._sub, tostring(t._file) }
        for q = 1, 8 do r[#r + 1] = ('%.6f'):format(tc[q] or -1) end
        for q = 1, 3 do r[#r + 1] = ('%.6f'):format(c[q]) end
        for q = 1, 8 do r[#r + 1] = ('%.3f'):format(vo[q] or 0) end
        rows[#rows + 1] = table.concat(r, ' ')
      end
    end
  end
  table.sort(rows)
  return #rows, table.concat(rows, '\n')
end
''')
BM = G.BM
VERIFY = not os.environ.get('MEASURE')

def loop(points, speed):
    pts = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, round(d / speed))
        for k in range(n):
            f = k / n
            pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.atan2(y1 - y0, x1 - x0)))
    return pts
def frame(m, X, Y, hd):
    place(X, Y, m, hd)
    def one():
        BM.Advance(1 / 30); ns.ReadPlayer(); ns.FollowStep(1 / 30); ns.Render()
    d0 = BM.Kept()[3]
    BM.Asked(); BM.Times()
    ms, kb = BM.Frame(one)
    asked = BM.Asked()
    bt, ht, built = BM.Times()
    if VERIFY: BM.CheckDrawn()
    return ms, kb, BM.Kept()[3] - d0, asked, bt, ht, built
def med(a): a = sorted(a); return a[len(a) // 2] if a else 0

# (world X north, Y west; map; the lap; the walk; the height grid: world X from..to, Y from..to)
CITIES = [
    ('Stormwind', 0, [(-9000, 450), (-8830, 640), (-9000, 900), (-8750, 1080), (-8450, 1000), (-8380, 640), (-8600, 420), (-8830, 640), (-9000, 450)],
     [(-8830, 640), (-8880, 700)], (-9100, -8300, 350, 1200)),
    ('Orgrimmar', 1, [(1630, -4380), (1800, -4300), (1950, -4450), (1880, -4650), (1650, -4600), (1500, -4450), (1630, -4380)],
     [(1630, -4380), (1680, -4420)], (1350, 2100, -4900, -4100)),
]
out = {}
for name, m, lap, walk, (X0, X1, Y0, Y1) in CITIES:
    print(f'\n== {name}')
    # load the tiles' data first (OnDemand.lua's hitch is not this step's)
    for (X, Y) in lap:
        gx, gy = 32 - Y / TILE, 32 - X / TILE
        for tx in range(int(gx) - 3, int(gx) + 4):
            for ty in range(int(gy) - 3, int(gy) + 4):
                for lv in (1, 2, 3): ns.TileBlocks(m, tx, ty, lv)
    ns.SetCamMode('follow')
    ns.SetTopDown(False, True)
    cam.dist, cam.pitch = 330, 45
    place(lap[0][0], lap[0][1], m, 0); tick(3)
    for _ in range(20): frame(m, lap[0][0], lap[0][1], 0)
    fly = []
    for (X, Y, hd) in loop(lap, 10): fly.append(frame(m, X, Y, hd))
    ns.SetTopDown(True, True)
    for (X, Y, hd) in loop(lap, 10): fly.append(frame(m, X, Y, hd))
    ns.SetTopDown(False, True)
    cam.dist, cam.pitch = 330, 45
    walks = []
    pts = loop(walk + [walk[0]], 0.25)[:300]
    for _ in range(10): frame(m, pts[0][0], pts[0][1], pts[0][2])
    d0 = BM.Kept()[3]
    for (X, Y, hd) in pts: walks.append(frame(m, X, Y, hd))
    d1 = BM.Kept()[3]
    # close up: 40 yd tilted 20 (the camera's lift reads the roofs round it and ahead)
    cam.dist, cam.pitch = 40, 20
    lows = []
    for _ in range(10): frame(m, pts[0][0], pts[0][1], pts[0][2])
    for (X, Y, hd) in pts: lows.append(frame(m, X, Y, hd))
    cam.dist, cam.pitch = 330, 45
    n_cached, mem_geo, mem_h, nv, nt, nh = BM.CacheMem()
    heap = BM.Heap()
    kept_tris, kept_h, HOLD, decodes = BM.Kept()
    print(f'cache: {int(n_cached)} blocks ({int(nv)} vertices, {int(nt)} triangles): {mem_geo:.0f} KB decoded ({mem_geo / max(n_cached, 1):.1f} KB a block), heights for {int(nh)} blocks {mem_h:.0f} KB; together {mem_geo + mem_h:.0f} KB')
    print(f'whole Lua heap after the scenario: {heap / 1024:.1f} MB')
    print(f'blocks keeping corners/colours/palette: {int(kept_tris)}; keeping height lookups: {int(kept_h)} (HOLD {int(HOLD)}); BlockHeight decodes while walking {int(d1 - d0) if d0 >= 0 else -1} in {len(pts)} frames')
    print(f'Lua ms: walking 0.25 yd/frame tilted 45 median {med([w[0] for w in walks]):.2f} (garbage {med([w[1] for w in walks]):.1f} KB); flying 10 yd/frame median {med([f[0] for f in fly]):.2f}, worst {max(f[0] for f in fly):.2f}')
    print(f'Lua ms: walking 40 yd tilted 20 median {med([w[0] for w in lows]):.2f}')
    for lab, fs in (('walking 330 yd', walks), ('walking 40 yd', lows), ('flying', fly)):
        print(f'  {lab}: making blocks {sum(f[4] for f in fs) / len(fs):.3f} ms a frame on average ({sum(f[6] for f in fs)} meshes made in {len(fs)} frames), heights of blocks (GroundHeight\'s BlockGeo and BlockHeight) {sum(f[5] for f in fs) / len(fs):.3f} ms a frame')
    print(f'BlockHeight decodes a frame: walking most {max(w[2] for w in walks):.0f}, close up {sum(w[2] for w in lows):.0f} in {len(lows)} frames, most {max(w[2] for w in lows):.0f}; flying {sum(f[2] for f in fly):.0f} in {len(fly)} frames, most {max(f[2] for f in fly):.0f} (frames with any: {sum(1 for f in fly if f[2] > 0)})')
    print(f'blocks asked for heights a frame: walking most {max(w[3] for w in walks):.0f}, close up most {max(w[3] for w in lows):.0f} (median {med([w[3] for w in lows]):.0f}), flying most {max(f[3] for f in fly):.0f}')
    # the drawn view at two fixed views
    sigs = {}
    for vname, dist, pitch, yaw in (('330 yd tilted 45', 330, 45, 30), ('150 yd straight down', 150, 89.9, 0)):
        ns.SetCamMode('free'); ns.SetTopDown(pitch >= 89, True)
        cam.map, cam.x, cam.y = m, 32 * TILE - walk[0][1], walk[0][0] - 32 * TILE
        cam.dist, cam.pitch, cam.yaw = dist, pitch, yaw
        cam.th = ns.GroundHeight(cam.x, cam.y)
        for _ in range(60):
            BM.Advance(1 / 30); ns.Render()
            if st.detailPending == 0: break
        for _ in range(3): BM.Advance(1 / 30); ns.Render()
        if VERIFY: BM.CheckDrawn()
        n, text = BM.Signature()
        sigs[vname] = (int(n), hashlib.sha1(text.encode()).hexdigest())
        print(f'view {vname}: {n} textures shown, sha1 {sigs[vname][1][:12]}')
    # the ground under the cursor (ScreenToTerrain: a mouse-wheel step zooms toward it, a left-press grabs it): low and
    # tilted, the ray walks over many blocks; each point asked three times in a row (wheel steps), the cursor at 24
    # places over the canvas
    picks = []
    for dist, pitch in ((60, 15), (330, 45)):
        ns.SetCamMode('free'); ns.SetTopDown(False, True)
        cam.map, cam.x, cam.y = m, 32 * TILE - walk[0][1], walk[0][0] - 32 * TILE
        cam.dist, cam.pitch, cam.yaw = dist, pitch, 30
        cam.th = ns.GroundHeight(cam.x, cam.y)
        for _ in range(3): BM.Advance(1 / 30); ns.Render()
        for i in range(24):
            px, py = -600 + (i % 6) * 240, -300 + (i // 6) * 200
            for rep in range(3):
                d0 = BM.Kept()[3]; BM.Asked()
                ms, hit = BM.Time(ns.ScreenToTerrain, px, py)
                picks.append((ms, BM.Asked(), BM.Kept()[3] - d0, rep, hit))
    first, again = [p_ for p_ in picks if p_[3] == 0], [p_ for p_ in picks if p_[3] > 0]
    print(f'ScreenToTerrain: first ask median {med([p_[0] for p_ in first]):.2f} ms, worst {max(p_[0] for p_ in first):.2f} ({max(p_[1] for p_ in first):.0f} blocks asked at most, {sum(p_[2] for p_ in first):.0f} decodes); asked again median {med([p_[0] for p_ in again]):.2f} ms, worst {max(p_[0] for p_ in again):.2f} ({sum(p_[2] for p_ in again):.0f} decodes)')
    sigs['cursor'] = (len(picks), hashlib.sha1(' '.join(p_[4] for p_ in picks).encode()).hexdigest())
    # heights: a 4 yd grid in rows, then the same points shuffled
    cx0, cx1, cy0, cy1 = 32 * TILE - Y1, 32 * TILE - Y0, X0 - 32 * TILE, X1 - 32 * TILE
    total = int(BM.Count(m, cx0, cx1, cy0, cy1, 4))
    hs = {}
    wrong_all = 0
    for oname, order in (('rows', None), ('shuffled', None)):
        if oname == 'shuffled':
            rnd = random.Random(4)
            order = list(range(1, total + 1)); rnd.shuffle(order); order = L.table_from(order[:20000])
        dd0 = BM.Kept()[3]
        n, wrong, first, onb, text = BM.Heights(m, cx0, cx1, cy0, cy1, 4, order)
        dd1 = BM.Kept()[3]
        wrong_all += int(wrong)
        hs[oname] = (int(n), hashlib.sha1(text.encode()).hexdigest())
        print(f'heights {oname}: {int(n)} points ({int(onb)} on buildings), {int(wrong)} not the full decode\'s' + (f' (first: {first})' if wrong else '') + f', sha1 {hs[oname][1][:12]}; BlockHeight decodes {int(dd1 - dd0) if dd0 >= 0 else -1}')
    tn, twrong, twhat, ttris = BM.TrisCheck(m, int(32 - walk[0][1] / TILE), int(32 - walk[0][0] / TILE), 1)
    print(f'corners, colours, palette of {int(tn)} blocks ({int(ttris)} triangles) round the city, all levels: {int(twrong)} not the full decode\'s' + (f' ({twhat})' if twrong else ''))
    out[name] = dict(n_cached=int(n_cached), mem=mem_geo + mem_h, per=(mem_geo + mem_h) / max(n_cached, 1),
                     walkdec=max(max(w[2] for w in walks), max(w[2] for w in lows)), againdec=sum(p_[2] for p_ in again), kept_tris=int(kept_tris), kept_h=int(kept_h), HOLD=int(HOLD),
                     wrong=wrong_all, twrong=int(twrong), tn=int(tn), heights=hs, views=sigs, walk=med([w[0] for w in walks]), fly=med([f[0] for f in fly]))
if VERIFY: print(f'\nblock triangles drawn checked against the full decode: {int(BM.drawnTris)}, {int(BM.drawnBad)} wrong' + (f' (first: {BM.drawnWhat})' if BM.drawnBad else ''))

dump = {k: dict(heights=v['heights'], views=v['views']) for k, v in out.items()}
if os.environ.get('BM_DUMP'): json.dump(dump, open(os.environ['BM_DUMP'], 'w'), indent=1)
if os.environ.get('MEASURE'): sys.exit(0)
# measured on the code before (2026-10-22, 7d8f038, GPS3D_LUA=<its GPS3D.lua>): the cache's heap per block, KB
# (Stormwind 11,337 KB for 306 blocks, Orgrimmar 11,857 KB for 371, heights included)
BEFORE = {'Stormwind': 37.0, 'Orgrimmar': 32.0}
for name, o in out.items():
    b = BEFORE[name]
    check(f'memory: {name}: the cache\'s heap per block, heights included, under 65 % of before', o['per'] < 0.65 * b, f'{o["per"]:.1f} KB a block (before {b}), {o["mem"]:.0f} KB for {o["n_cached"]} blocks')
for name, o in out.items():
    check(f'kept: {name}: no cached block keeps corners, colours or a palette; at most HOLD keep height lookups', o['kept_tris'] == 0 and 0 < o['HOLD'] and o['kept_h'] <= o['HOLD'],
          f'{o["kept_tris"]} blocks with corners, {o["kept_h"]} with height lookups (HOLD {o["HOLD"]})')
check('held: walking (330 yd tilted 45 and 40 yd tilted 20) BlockHeight decodes at most one block a frame, and a cursor point asked again none',
      all(0 <= o['walkdec'] <= 1 and o['againdec'] == 0 for o in out.values()) and all(o['HOLD'] > 0 for o in out.values()),
      ', '.join(f'{k}: most {v["walkdec"]} a frame, {v["againdec"]} asked again' for k, v in out.items()))
check('heights: GroundHeight on a 4 yd grid over both cities, in rows and shuffled, is exactly the full decode\'s', all(o['wrong'] == 0 for o in out.values()),
      ', '.join(f'{k} {v["heights"]["rows"][0]} + {v["heights"]["shuffled"][0]} points, {v["wrong"]} wrong' for k, v in out.items()))
check('corners: ns.BlockTris gives the full decode\'s corners, colours and palette, and the block triangles drawn are made from them',
      all(o['twrong'] == 0 and o['tn'] > 100 for o in out.values()) and BM.drawnTris > 100000 and BM.drawnBad == 0,
      f'{sum(o["tn"] for o in out.values())} blocks; {int(BM.drawnTris)} triangles drawn, {int(BM.drawnBad)} wrong')
if os.environ.get('BM_COMPARE'):
    ref = json.load(open(os.environ['BM_COMPARE']))
    diff = [f'{k} {part} {kk}' for k, v in dump.items() for part in ('heights', 'views') for kk, vv in v[part].items() if tuple(ref[k][part][kk]) != tuple(vv)]
    check('the heights and the drawn views are the same as in the compared dump', not diff, ', '.join(diff))
print(f'\n{sum(r[1] for r in results)} of {len(results)} checks passed')
sys.exit(0 if all(r[1] for r in results) else 1)
