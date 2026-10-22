# Building blocks made into textures while running through a city (GPS3D.lua's BlockGeo, BuildBlockMesh,
# ReleaseMesh and BUILD_LIMIT; since 2026-10-22, perf round step A2), checked and measured in Lua 5.4 (lupa) on
# the real data, 1280 x 800 window, buildings at the default budget.
#
# The scenario: you run 20 yd a frame (30 frames a second: a fast flight) three laps round Stormwind (the gate,
# the Trade District, the Mage Quarter, the park, the Cathedral, the Dwarven District, Old Town), the camera
# following you at 330 yd straight down, then stand still. Most frames make the blocks that came into view.
# Measured per frame (GC stopped during the frame): Render's Lua ms (processor time, without the sandbox's slow
# SetParent), the part of it spent making blocks (BlockGeo + BuildBlockMesh), Lua allocation (garbage) in KB
# (the sandbox's stand-ins for SetTexCoord and SetVertexColor fill their tables in place: the addon's garbage
# only), new building triangles made into textures; per block: frames from first chosen until drawn at the
# level chosen (meanwhile another level of it, or flat), and block-frames flat on the canvas; frames after
# stopping until every block in view is drawn at its level. BB_PASS=calls counts the C calls instead (not
# timed); MEASURE=1 only measures; BB_FRAMES=1 lists the slowest frames; BB_NOVERIFY=1 skips the exact check.
# Checks (garbage and pool fail on the code before):
#   garbage   a busy frame (one that makes blocks) allocates less than half of what the code before did
#             (BEFORE_KB below, measured on the code before with GPS3D_LUA=<file>)
#   cap       at most BUILD_LIMIT (1,500) new building triangles a frame (a single bigger block alone); 500, as
#             the review proposed, made blocks visibly late (testing/2026-10-22-perf-round/GATES-A2.md)
#   pool      the block meshes' triangle tables are given back with their meshes and used again, and decoded
#             blocks' arrays forgotten by the cache are used again for the next block decoded
#   exact     every frame, every triangle of every block mesh drawn is what a fresh decode and build of that
#             block gives (corners, texture or colour, coordinates) and is on screen where its vertices project
#             (the corners the engine holds); no texture or triangle table in two places
#   late      blocks are not late: no block chosen is flat on the canvas while running, and after stopping every
#             block in view is drawn at its level the next frame
# BB_DUMP=<file> writes the drawn view (every texture shown: image, coordinates, colour, corners, layer, frame)
# at three views after the run; BB_COMPARE=<file> compares with such a dump (the code before against this one).
# GPS3D_LUA=<file> loads another GPS3D.lua (the code before: measured, checks reported).
import lupa.lua54 as lupa54, math, time, os, sys, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())
PASS = os.environ.get('BB_PASS', 'time')
if PASS == 'calls':
    L.execute('''
CALLS = { n = 0 }
local names = { "SetVertexOffset", "SetDrawLayer", "SetParent", "Show", "Hide", "SetTexCoord", "SetTexture", "SetVertexColor" }
local Texture = getmetatable(UIParent:CreateTexture())
for _, n in ipairs(names) do
  local f = Texture[n]
  Texture[n] = function(...) CALLS.n = CALLS.n + 1 return f(...) end
end''')
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
print('code', ALT or 'sandbox copy', 'pass', PASS)

L.execute(r'''
BB = {}
local ns = SANDBOX.namespaces.GPS3D
local function findup(f, name) for i = 1, 300 do local n, v = debug.getupvalue(f, i); if not n then return end; if n == name then return v, i end end end
local RW = findup(ns.Render, 'RenderWorld')
local meshes = findup(RW, 'meshes')
local ReleaseMesh = findup(RW, 'ReleaseMesh')
local pool = findup(ReleaseMesh, 'pool')
local BuildBlockMesh = findup(RW, 'BuildBlockMesh')
local MinimapFile, OverviewOf = findup(BuildBlockMesh, 'MinimapFile'), findup(BuildBlockMesh, 'OverviewOf')
local WALL_STEEPNESS = findup(BuildBlockMesh, 'WALL_STEEPNESS')
local VO_EPS, CLIP_D = findup(RW, 'VO_EPS'), 1.5
BB.BUILD_LIMIT = findup(RW, 'BUILD_LIMIT') or (ns.blockBuild and ns.blockBuild.LIMIT)
local Choose = findup(ns.ChooseBlocks, 'Choose') or ns.ChooseBlocks
local InView = findup(Choose, 'InView')
local CLOCK_S = findup(GetTime, 'S')
local TILE, BLOCK, BLOCKS = ns.TILE, ns.BLOCK, 8
local STEP = TILE / 64 / 8 -- (1.04 yd: the raster's step, as GPS3D.lua's STEP)
local LEVELS = { 'Detail', 'DetailLow', 'DetailFar' }
local WHITE = 'interface\\buttons\\white8x8'
local SUN = { -0.4, 0.8, -0.35 }
do local l = math.sqrt(SUN[1] ^ 2 + SUN[2] ^ 2 + SUN[3] ^ 2) SUN[1], SUN[2], SUN[3] = SUN[1] / l, SUN[2] / l, SUN[3] / l end
local B64 = ns.B64
function BB.Advance(dt) CLOCK_S.time = CLOCK_S.time + dt end
function BB.FrameNo() return findup(RW, 'frameNo') end

-- a block decoded on its own (the format as GPS3D.lua documents it), not through BlockGeo
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
  -- each triangle as BuildBlockMesh's rule makes it: { file or WHITE, u/v x 3 or colour, colour }
  local file = MinimapFile(map, tx, ty)
  local au, av, aw, ah = 0, 0, 1, 1
  if not file then file, au, av, aw, ah = OverviewOf(map, tx, ty) end
  local tx0, ty0 = tx * TILE, -ty * TILE
  local us, vs = aw / TILE, ah / TILE
  local tri = {}
  for k = 1, nt do
    local a, b, c = idx[3 * k - 2], idx[3 * k - 1], idx[3 * k]
    local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
    local ex2, eh2, ez2 = vx[c] - vx[a], vh[c] - vh[a], -(vy[c] - vy[a])
    local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
    local l = math.sqrt(nx * nx + nh * nh + nz * nz)
    if l > 0 then nx, nh, nz = nx / l, nh / l, nz / l end
    local shade = 0.45 + 0.55 * math.abs(nx * SUN[1] + nh * SUN[2] + nz * SUN[3])
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
    if wall then
      local col = pal[vc[wall]] or pal[1]
      tri[k] = { WHITE, nil, col[1] * shade, col[2] * shade, col[3] * shade }
    elseif top and lv > 1 and file then
      local u, v = au + (vx[top] - tx0) * us, av + (ty0 - vy[top]) * vs
      tri[k] = { file, { u, v, u, v, u, v }, shade, shade, shade }
    elseif file then
      tri[k] = { file, { au + (vx[a] - tx0) * us, av + (ty0 - vy[a]) * vs, au + (vx[b] - tx0) * us, av + (ty0 - vy[b]) * vs, au + (vx[c] - tx0) * us, av + (ty0 - vy[c]) * vs }, 1, 1, 1 }
    else
      tri[k] = { WHITE, nil, 0.35, 0.42, 0.3 }
    end
  end
  r = { vx = vx, vy = vy, vh = vh, vc = vc, idx = idx, pal = pal, nv = nv, nt = nt, tri = tri }
  nrefs = nrefs + 1
  if nrefs > 600 then refs, nrefs = {}, 0 end
  refs[key] = r
  return r
end
local function same(a, b) return type(a) == 'number' and type(b) == 'number' and math.abs(a - b) <= 1e-9 * math.max(1, math.abs(a), math.abs(b)) end
local function lower(f) return type(f) == 'string' and f:lower():gsub('/', '\\') or f end

-- every triangle of every block mesh drawn this frame against Ref; corners on screen; nothing in two places
BB.bad, BB.badWhat, BB.checkedTris, BB.checkedCorners = 0, nil, 0, 0
local function bad(what) BB.bad = BB.bad + 1; if not BB.badWhat then BB.badWhat = what end end
function BB.Verify()
  local frameNo = findup(RW, 'frameNo')
  local F = ns.Focal()
  local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
  local texSeen, triSeen = {}, {}
  for key, m in pairs(meshes) do
    for k = 1, #m.tris do
      local t = m.tris[k]
      if triSeen[t] then bad('triangle table in two meshes') end
      triSeen[t] = true
      if texSeen[t.tex] then bad('texture in two triangles') end
      texSeen[t.tex] = true
      if t.mesh ~= m then bad('triangle of another mesh') end
    end
    if m.detail and m.active == frameNo then
      local k4 = -key
      local lv = k4 % 4
      local bk = (k4 - lv) // 4
      local bi = bk % 64
      local tk = (bk - bi) // 64
      local map = tk // 4096
      local tile = tk % 4096
      local tx, ty = tile % 64, tile // 64
      local r = Ref(map, tx, ty, bi, lv)
      local whole = true -- (the mesh's own counts and vertices; its triangles are checked only when they are right)
      if #m.tris ~= r.nt or #m.vx ~= r.nv or #m.vy ~= r.nv or #m.vh ~= r.nv then whole = false; bad(('counts %d/%d tris, %d/%d vertices'):format(#m.tris, r.nt, #m.vx, r.nv)) end
      for i = 1, r.nv do
        if not (same(m.vx[i], r.vx[i]) and same(m.vy[i], r.vy[i]) and same(m.vh[i], r.vh[i])) then whole = false; bad('vertex ' .. i); break end
      end
      local px, py, pd = m.px, m.py, m.pd
      for k = 1, whole and r.nt or 0 do
        local t, e = m.tris[k], r.tri[k]
        BB.checkedTris = BB.checkedTris + 1
        if t.a ~= r.idx[3 * k - 2] or t.b ~= r.idx[3 * k - 1] or t.c ~= r.idx[3 * k] then bad('corners of triangle ' .. k) end
        local tex = t.tex
        if lower(tex._file) ~= lower(e[1]) then bad('image ' .. tostring(tex._file) .. ' for ' .. tostring(e[1])) end
        local col = tex._color
        if not (same(col[1], e[3]) and same(col[2], e[4]) and same(col[3], e[5])) then bad('colour') end
        if tex.r ~= col[1] or tex.g ~= col[2] or tex.b ~= col[3] or lower(tex.file) ~= lower(tex._file) then bad('remembered colour or image') end
        local uv = e[2]
        if uv then
          if not (t.u1 and same(t.u1, uv[1]) and same(t.v1, uv[2]) and same(t.u2, uv[3]) and same(t.v2, uv[4]) and same(t.u3, uv[5]) and same(t.v3, uv[6])) then bad('kept coordinates') end
          if not t.clipped then
            local tc = tex._tc
            for q = 1, 6 do if not same(tc[q], uv[q]) then bad('coordinates'); break end end
            if not (same(tc[7], uv[5]) and same(tc[8], uv[6])) then bad('fourth corner coordinates') end
          end
        elseif t.u1 ~= nil then bad('coordinates kept on a coloured triangle')
        end
        if t.shown ~= tex._shown then bad('shown') end
        if t.blk ~= nil then bad('a ground triangle field on a block triangle') end
        -- on screen: shown and whole, its corners where its vertices are drawn, those within VO_EPS of the
        -- exact projection
        if t.shown and not t.clipped then
          local vo = tex._vo
          local a, b, c = t.a, t.b, t.c
          if not (vo and vo[1] == px[a] + 0.5 and vo[2] == py[a] - 0.5 and vo[3] == px[b] + 0.5 and vo[4] == py[b] + 0.5
            and vo[5] == px[c] - 0.5 and vo[6] == py[c] - 0.5 and vo[7] == px[c] - 0.5 and vo[8] == py[c] + 0.5) then bad('corners on screen') end
          for _, q in ipairs({ a, b, c }) do
            local x, y, z = m.vx[q] - cx, m.vy[q] - cy, m.vh[q] - cz
            local d = x * fx + y * fy + z * fz
            local s = F / d
            local sx, sy = (x * rx + y * ry) * s, (x * ux + y * uy + z * uz) * s
            BB.checkedCorners = BB.checkedCorners + 1
            if math.abs(sx - px[q]) > VO_EPS + 1e-9 or math.abs(sy - py[q]) > VO_EPS + 1e-9 then bad(('vertex drawn %.2f px off'):format(math.max(math.abs(sx - px[q]), math.abs(sy - py[q])))) end
          end
        end
      end
    end
  end
end

-- per frame: new building triangles made, blocks chosen and how they are drawn, the wait per block
local seen = setmetatable({}, { __mode = 'k' })
local wait, lat = {}, {}
BB.lat, BB.left = lat, 0
function BB.Frame()
  local frameNo = findup(RW, 'frameNo')
  local newTris, newBlocks = 0, 0
  for key, m in pairs(meshes) do
    if m.detail and not seen[m] then seen[m] = true; newTris = newTris + #m.tris; newBlocks = newBlocks + 1 end
  end
  local F = ns.Focal()
  local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
  local w, h = ns.canvas:GetSize()
  local kx, ky = (w / 2 + 2) / F, (h / 2 + 2) / F
  local chosen, atLevel, other, flat, flatCanvas = 0, 0, 0, 0, 0
  local now = {}
  local map = ns.cam.map
  for i = 1, #ns.blockList do
    local e = ns.blockList[i]
    if e.lv > 0 then
      chosen = chosen + 1
      now[e.bk] = true
      local m = meshes[-(e.bk * 4 + e.lv)]
      if m and m.active == frameNo then
        atLevel = atLevel + 1
        if wait[e.bk] then lat[#lat + 1] = frameNo - wait[e.bk]; wait[e.bk] = nil end
      else
        if not wait[e.bk] then wait[e.bk] = frameNo end
        local any = false
        for l = 1, 3 do local m2 = meshes[-(e.bk * 4 + l)]; if m2 and m2.active == frameNo then any = true end end
        if any then other = other + 1 else
          flat = flat + 1
          local tb = ns.TileBlocks(map, e.c.tx, e.c.ty)
          if InView(e.x0, e.x0 + BLOCK, e.y1 - BLOCK, e.y1, tb.lo[e.bi], tb.top[e.bi], kx, ky, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz) then flatCanvas = flatCanvas + 1 end
        end
      end
    end
  end
  for bk in pairs(wait) do if not now[bk] then wait[bk] = nil; BB.left = BB.left + 1 end end
  return newTris, newBlocks, chosen, atLevel, other, flat, flatCanvas
end
-- the time spent making blocks (BlockGeo and BuildBlockMesh as RenderWorld calls them), per frame
BB.bt = 0
do
  local clock = os.clock
  for _, name in ipairs({ 'BlockGeo', 'BuildBlockMesh' }) do
    local f, i = findup(RW, name)
    debug.setupvalue(RW, i, function(...) local t = clock(); local a, b = f(...); BB.bt = BB.bt + clock() - t; return a, b end)
  end
end
-- tables met again in another block (used again from the pools): triangle tables (from any earlier mesh, ground
-- or building), screen-position arrays, decoded vertex arrays
local firstVx, firstPx = setmetatable({}, { __mode = 'k' }), setmetatable({}, { __mode = 'k' })
local meshSeen, triSeen = setmetatable({}, { __mode = 'k' }), setmetatable({}, { __mode = 'k' })
BB.reVx, BB.rePx, BB.reTri, BB.newTri = 0, 0, 0, 0
function BB.Reuse()
  for key, m in pairs(meshes) do
    if not meshSeen[m] then
      meshSeen[m] = true
      for k = 1, #m.tris do
        local t = m.tris[k]
        if m.detail then if triSeen[t] then BB.reTri = BB.reTri + 1 else BB.newTri = BB.newTri + 1 end end
        triSeen[t] = true
      end
      if m.detail then
        local f = firstVx[m.vx]; if not f then firstVx[m.vx] = -key elseif f ~= -key then BB.reVx = BB.reVx + 1; firstVx[m.vx] = -key end
        f = firstPx[m.px]; if not f then firstPx[m.px] = m elseif f ~= m then BB.rePx = BB.rePx + 1; firstPx[m.px] = m end
      end
    end
  end
end
-- decode n blocks of the tiles round (tx, ty) through BlockGeo (more than the cache keeps: it forgets and its
-- arrays are used again) and compare each with Ref: every vertex, colour index, corner and palette colour, and
-- no leftover entries past the block's own (lengths)
function BB.GeoCheck(map, tx0, ty0, want)
  local n, wrong, what, reused = 0, 0, nil, 0
  for r = 0, 6 do
    for ty = ty0 - r, ty0 + r do
      for tx = tx0 - r, tx0 + r do
        if math.max(math.abs(tx - tx0), math.abs(ty - ty0)) == r then
          for lv = 1, 3 do
            local tb = ns.TileBlocks(map, tx, ty, lv)
            if tb then
              for bi = 0, 63 do
                if tb[bi] and n < want then
                  n = n + 1
                  local g = ns.BlockGeo(map, tx, ty, bi, lv)
                  local ref = Ref(map, tx, ty, bi, lv)
                  local f = firstVx[g.vx]
                  if f and f ~= g.key then reused = reused + 1 end
                  firstVx[g.vx] = g.key
                  -- (since A4 the corners, colours and palette are decoded from the block's string when asked:
                  -- ns.BlockTris, into the shared arrays BuildBlockMesh uses, which must come out exact each time)
                  local idx, vc, pal = g.idx, g.vc, g.pal
                  if ns.BlockTris then local r = pool.rest; idx, vc, pal = ns.BlockTris(g, r.idx, r.vc, r.pal) end
                  local ok = #g.vx == ref.nv and #g.vy == ref.nv and #g.vh == ref.nv and #vc == ref.nv and #idx == 3 * ref.nt and g.nt == ref.nt
                  if not ok then what = what or ('lengths ' .. #g.vx .. '/' .. ref.nv .. ' ' .. #idx .. '/' .. 3 * ref.nt) end
                  for k = 1, ref.nv do if not (same(g.vx[k], ref.vx[k]) and same(g.vy[k], ref.vy[k]) and same(g.vh[k], ref.vh[k]) and vc[k] == ref.vc[k]) then ok = false; what = what or 'vertex' break end end
                  for k = 1, 3 * ref.nt do if idx[k] ~= ref.idx[k] then ok = false; what = what or 'corner' break end end
                  if #pal ~= #ref.pal then ok = false; what = what or 'palette length' end
                  for k = 1, #ref.pal do local a, b = pal[k], ref.pal[k]; if not (a and same(a[1], b[1]) and same(a[2], b[2]) and same(a[3], b[3])) then ok = false; what = what or 'palette' break end end
                  if not ok then wrong = wrong + 1 end
                end
              end
            end
          end
        end
      end
    end
  end
  return n, wrong, what, reused
end
function BB.Pool() return pool.tris.n end
function BB.ReleaseAll()
  local n = 0
  for key, m in pairs(meshes) do if m.detail then n = n + #m.tris end end
  local before = pool.tris.n
  local keys = {}
  for key in pairs(meshes) do keys[#keys + 1] = key end
  for _, key in ipairs(keys) do ReleaseMesh(key) end
  return n, pool.tris.n - before
end
-- (the sandbox's stand-ins for the game's C functions SetTexCoord and SetVertexColor make a new table per call;
-- in the game they make no Lua garbage, so here they fill the texture's own table: the garbage counted is the
-- addon's)
do
  local Texture = getmetatable(UIParent:CreateTexture())
  local tc8, col = Texture.SetTexCoord, Texture.SetVertexColor
  Texture.SetTexCoord = function(self, ...)
    local t = self._tc
    if not t or select('#', ...) ~= 8 then return tc8(self, ...) end
    t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8] = ...
    self._sv = (self._sv or 0) + 1; CLOCK_S.dirty = true
  end
  Texture.SetVertexColor = function(self, r, g, b, a)
    local c = self._color
    c[1], c[2], c[3], c[4] = r, g, b, a or 1
    self._sv = (self._sv or 0) + 1; CLOCK_S.dirty = true
  end
end
-- (the sandbox's SetParent looks the texture up in its old frame's list, thousands long: its time is taken out of
-- the Lua ms reported; in the game it is one C call)
local SP = { t = 0 }
do
  local Texture = getmetatable(UIParent:CreateTexture())
  local f, clock = Texture.SetParent, os.clock
  Texture.SetParent = function(...) local t = clock(); f(...); SP.t = SP.t + clock() - t end
end
function BB.Garbage(f)
  collectgarbage('collect'); collectgarbage('stop')
  local k0 = collectgarbage('count')
  local s0 = SP.t
  local t0 = os.clock()
  f()
  local ms = (os.clock() - t0) * 1000
  local kb = collectgarbage('count') - k0
  collectgarbage('restart')
  return ms - (SP.t - s0) * 1000, kb, ms
end
-- the drawn view: every texture shown in the depth frames, as text rows
function BB.Signature()
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
BB = G.BB
# the route: three laps of Stormwind (world X north, Y west), 20 yd a frame; a lap (2,600 yd, 4.3 s) is longer
# than meshes are kept unused (KEEP_SECONDS, 3 s), so each lap makes its blocks again, from the pools
ROUTE = [(-9000, 450), (-8830, 640), (-9000, 900), (-8750, 1080), (-8450, 1000), (-8380, 640), (-8600, 420), (-8830, 640), (-9000, 450)]
SPEED = 20
def path():
    pts = []
    assert sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(ROUTE, ROUTE[1:])) > 3 * 30 * SPEED
    for lap in range(3):
        for (x0, y0), (x1, y1) in zip(ROUTE, ROUTE[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, round(d / SPEED))
            for k in range(n):
                f = k / n
                pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.atan2(y1 - y0, x1 - x0), lap))
    return pts
PATH = path()
VERIFY = PASS == 'time' and not os.environ.get('BB_NOVERIFY')
# start: at the route's first point, settled (the band's data loaded, the blocks there made)
# (the building data of the tiles round the route loaded first: a band's first load is OnDemand.lua's hitch, not this)
for (X, Y) in ROUTE:
    gx, gy = 32 - Y / TILE, 32 - X / TILE
    for tx in range(int(gx) - 3, int(gx) + 4):
        for ty in range(int(gy) - 3, int(gy) + 4):
            for lv in (1, 2, 3): ns.TileBlocks(0, tx, ty, lv)
place(PATH[0][0], PATH[0][1], 0, PATH[0][2]); tick(5)
for _ in range(30): G.BB.Advance(1 / 30); ns.ReadPlayer(); ns.FollowStep(1 / 30); ns.Render()
BB.Frame()
frames = []
for (X, Y, hd, lap) in PATH:
    place(X, Y, 0, hd)
    def one():
        BB.Advance(1 / 30); ns.ReadPlayer(); ns.FollowStep(1 / 30); ns.Render()
    BB.bt = 0
    if PASS == 'calls':
        G.CALLS.n = 0; one(); ms, kb, raw, calls = 0, 0, 0, int(G.CALLS.n)
    else:
        ms, kb, raw = BB.Garbage(one); calls = 0
    bms = BB.bt * 1000
    BB.Reuse()
    nt, nb, chosen, atl, other, flat, flatc = BB.Frame()
    if VERIFY: BB.Verify()
    frames.append(dict(lap=lap, ms=ms, raw=raw, bms=bms, kb=kb, calls=calls, nt=nt, nb=nb, chosen=chosen, atl=atl, other=other, flat=flat, flatc=flatc, shown=int(st.shown)))
# stop: frames until every block in view is drawn at its level
settle = None
for k in range(1, 41):
    BB.Advance(1 / 30); ns.ReadPlayer(); ns.FollowStep(1 / 30); ns.Render()
    nt, nb, chosen, atl, other, flat, flatc = BB.Frame()
    if VERIFY: BB.Verify()
    if atl == chosen: settle = k; break
lat = [int(v) for v in BB.lat.values()] if BB.lat else []

def med(a): a = sorted(a); return a[len(a) // 2] if a else 0
busy = [f for f in frames if f['nt'] > 0]
quiet = [f for f in frames if f['nt'] == 0]
steady = [f for f in busy if f['lap'] > 0]
print(f'\n{len(frames)} frames, {len(busy)} make blocks ({len(steady)} of them in laps 2-3), {sum(f["nt"] for f in frames)} building triangles made')
if PASS == 'calls':
    print(f'C calls a frame: busy median {med([f["calls"] for f in busy])}, worst {max(f["calls"] for f in frames)}; quiet median {med([f["calls"] for f in quiet])}')
else:
    print(f'garbage a busy frame: median {med([f["kb"] for f in busy]):.0f} KB, laps 2-3 {med([f["kb"] for f in steady]):.0f} KB, worst {max(f["kb"] for f in busy):.0f} KB; quiet frames {med([f["kb"] for f in quiet]):.0f} KB')
    print(f'making blocks (BlockGeo + BuildBlockMesh) ms a frame: busy median {med([f["bms"] for f in busy]):.2f}, worst {max(f["bms"] for f in busy):.2f}')
    print(f'frame ms with the sandbox\'s SetParent: busy median {med([f["raw"] for f in busy]):.2f}, worst {max(f["raw"] for f in frames):.2f}')
    print(f'Lua ms (without it): busy median {med([f["ms"] for f in busy]):.2f}, worst busy {max(f["ms"] for f in busy):.2f}, worst of all {max(f["ms"] for f in frames):.2f}; quiet median {med([f["ms"] for f in quiet]):.2f}; all median {med([f["ms"] for f in frames]):.2f}')
if os.environ.get('BB_FRAMES'):
    for i, f in sorted(enumerate(frames), key=lambda p: -p[1]['ms'])[:12]: print('  frame', i, f)
print(f'new building triangles a frame: busy median {med([f["nt"] for f in busy])}, most {max(f["nt"] for f in frames)} (most blocks {max(f["nb"] for f in frames)})')
print(f'blocks chosen a frame: median {med([f["chosen"] for f in frames])}; waiting (another level or flat) block-frames {sum(f["chosen"] - f["atl"] for f in frames)}, of them flat {sum(f["flat"] for f in frames)}, flat on the canvas {sum(f["flatc"] for f in frames)}')
print(f'wait from chosen to drawn at its level: {len(lat)} waits, mean {sum(lat) / max(len(lat), 1):.2f} frames, worst {max(lat) if lat else 0}; {int(BB.left)} left the view before made')
print(f'after stopping: every block in view drawn at its level after {settle} frame(s)')
if VERIFY: print(f'checked {int(BB.checkedTris)} block triangles and {int(BB.checkedCorners)} corners on screen: {int(BB.bad)} wrong' + (f' (first: {BB.badWhat})' if BB.bad else ''))

# views after the run (the pools well used): the drawn view, for BB_DUMP / BB_COMPARE
VIEWS = [('Trade District 330 yd down', -8830, 640, 330, 89.9, 0), ('Mage Quarter 330 yd tilted 45', -8980, 880, 330, 45, 132), ('Cathedral 150 yd tilted 45', -8560, 840, 150, 45, 60)]
sigs = {}
for name, X, Y, dist, pitch, yaw in VIEWS:
    ns.SetCamMode('free')
    ns.SetTopDown(pitch >= 89, True)
    cam.map, cam.x, cam.y = 0, 32 * TILE - Y, X - 32 * TILE
    cam.dist, cam.pitch, cam.yaw = dist, pitch, yaw
    cam.th = ns.GroundHeight(cam.x, cam.y)
    for _ in range(60):
        BB.Advance(1 / 30); ns.Render()
        if st.detailPending == 0: break
    for _ in range(3): BB.Advance(1 / 30); ns.Render()
    if VERIFY: BB.Verify()
    n, text = BB.Signature()
    sigs[name] = (int(n), hashlib.sha1(text.encode()).hexdigest(), int(st.detail), int(st.detailTris))
    print(f'view {name}: {n} textures shown, {int(st.detail)} blocks, {int(st.detailTris)} building triangles, sha1 {sigs[name][1][:12]}')
if os.environ.get('BB_DUMP'):
    json.dump(sigs, open(os.environ['BB_DUMP'], 'w'), indent=1)
same_as = None
if os.environ.get('BB_COMPARE'):
    ref = json.load(open(os.environ['BB_COMPARE']))
    same_as = all(tuple(ref[k]) == tuple(v) for k, v in sigs.items())
# more blocks decoded than the cache keeps (GEO_LIMIT 400): forgotten blocks' arrays used again, each decode exact;
# then the Trade District again (meshes made before the cache forgot their blocks still draw their own vertices)
geo_n, geo_wrong, geo_what, geo_reused = BB.GeoCheck(0, 30, 48, 900)
print(f'decoded {geo_n} blocks round the Trade District: {geo_wrong} wrong' + (f' ({geo_what})' if geo_wrong else '') + f', {geo_reused} into arrays of a block the cache forgot')
name, X, Y, dist, pitch, yaw = VIEWS[0]
cam.x, cam.y, cam.dist, cam.pitch, cam.yaw = 32 * TILE - Y, X - 32 * TILE, dist, pitch, yaw
ns.SetTopDown(True, True)
for _ in range(10): BB.Advance(1 / 30); ns.Render()
if VERIFY: BB.Verify()
print(f'during the run: {int(BB.reTri)} block triangles made on a table given back ({int(BB.newTri)} on a new one), {int(BB.rePx)} block meshes on a given-back mesh\'s arrays, {int(BB.reVx)} on decoded arrays of a forgotten block')
# give everything back: the block triangles go to the pool
rel_n, rel_back = BB.ReleaseAll()
print(f'released every mesh: {rel_n} block triangles, the free triangle tables grew by {rel_back}')

if PASS == 'calls' or os.environ.get('MEASURE'): sys.exit(0)
# measured on the code before (2026-10-22, 15bb3e4, GPS3D_LUA=<its GPS3D.lua>): a busy frame's garbage (median, KB)
BEFORE_KB = 142
check('garbage: a frame that makes blocks allocates under half of what it did before (the pools)', med([f['kb'] for f in busy]) * 2 < BEFORE_KB,
      f'median {med([f["kb"] for f in busy]):.0f} KB, laps 2-3 {med([f["kb"] for f in steady]):.0f} KB (before {BEFORE_KB} and 112)')
cap = int(BB.BUILD_LIMIT or 0)
check('cap: at most BUILD_LIMIT (1,500) new building triangles a frame (a single bigger block alone)', cap == 1500 and all(f['nt'] <= cap or f['nb'] == 1 for f in frames),
      f'BUILD_LIMIT {cap}, most {max(f["nt"] for f in frames)}')
check('pool: every block triangle given back with its mesh; the next blocks made on them, on a given-back mesh\'s arrays and on a forgotten block\'s decoded arrays (each such decode exact)',
      rel_n > 0 and rel_back >= rel_n and BB.reTri > 0 and BB.rePx > 0 and geo_reused > 100 and geo_wrong == 0,
      f'{rel_back} of {rel_n} given back; triangles made on given-back tables {int(BB.reTri)} (new {int(BB.newTri)}), meshes on given-back arrays {int(BB.rePx)}; decodes into forgotten arrays {geo_reused} of {geo_n}, {geo_wrong} wrong')
check('exact: every block triangle drawn is a fresh build of its block, on screen where its vertices project; nothing in two places',
      not VERIFY or (BB.checkedTris > 100000 and BB.bad == 0), f'{int(BB.checkedTris)} triangles, {int(BB.bad)} wrong' + (f' ({BB.badWhat})' if BB.bad else ''))
check('late: no block chosen is drawn flat on the canvas while running (as before), and every block in view is drawn at its level the frame after stopping',
      sum(f['flatc'] for f in frames) == 0 and settle == 1, f'{sum(f["flatc"] for f in frames)} block-frames, settled after {settle}')
if same_as is not None: check('the drawn views after the run are the same as in the compared dump', same_as)
print(f'\n{sum(r[1] for r in results)} of {len(results)} checks passed')
sys.exit(0 if all(r[1] for r in results) else 1)
