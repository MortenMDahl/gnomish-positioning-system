# The 3D view's tile and block choice kept between frames (GPS3D.lua's ChooseTiles wrapper and ns.ChooseBlocks,
# ns.choice; since 2026-10-22, perf round step A1), checked and measured in Lua 5.4 (lupa) on the real data.
#
# A scripted path (walk, pan, turn, tilt, zoom) at Stormwind's Trade District, Orgrimmar's Valley of Strength,
# Mount Hyjal from 5,000 yd and the Eastern Kingdoms from 12,000 yd. After every frame the full choice is made
# again from the same state (the ground's controller held, the blocks' last levels as a fresh choice would see
# them; everything put back afterwards: "the shadow"), and what the frame drew is compared with it:
#   missing   no tile whose ground the full choice draws and no raised block it draws, whose box reaches the
#             canvas (2 px round it, where triangles are cut), may be missing from the kept choice
#   lag       on every frame that chose afresh the kept choice is the full one (tiles, levels, minimap or
#             overview image, blocks and their levels); so a difference lasts at most until the next one
#   corners   every corner drawn of a mesh at the full choice's level within VO_EPS (0.25 px) of the exact
#             projection of its vertex
#   budget    the ground's triangles never over the budget
#   reuse     share of frames that kept the choice, per segment (0 on the code before: it fails there)
#   stale     a resize, another map, a budget, buildings switched, the game's buildings covering blocks
#             (ns.coverStamp) and the probe's putting back each make the next frame choose afresh
#   mutation  the bound made 10 x too loose (CHOICE_MUT=loose, the choice kept as long as the bound allows):
#             ground goes missing and the check says so (CHOICE_KEEP=1000: the bound alone, nothing missing)
# Measured per segment: Render's Lua ms (processor time, median), the choice's own ms (ChooseTiles +
# ns.ChooseBlocks), C calls and garbage per frame (CHOICE_PASS=calls: counted, not timed).
# GPS3D_LUA=<file> loads another GPS3D.lua (the code before: measured, the shadow checks skipped);
# CHOICE_QUICK=1 runs fewer frames; CHOICE_JSON=<file> writes the per-segment numbers.
import lupa.lua54 as lupa54, math, time, os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())
PASS = os.environ.get('CHOICE_PASS', 'time')
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
NEW = ns.choice is not None
MUT = os.environ.get('CHOICE_MUT')
print('code', ALT or 'sandbox copy', '(keeps the choice)' if NEW else '(chooses every frame)', 'pass', PASS, 'mutation', MUT)

L.execute(r'''
SH = { on = false }
local ns = SANDBOX.namespaces.GPS3D
local function findup(f, name) for i = 1, 300 do local n, v = debug.getupvalue(f, i); if not n then return end; if n == name then return v, i end end end
SH.findup = findup
local RW = findup(ns.Render, 'RenderWorld')
local CT = findup(RW, 'ChooseTiles')
local clock = os.clock
-- the choice's own time: ChooseTiles and ns.ChooseBlocks wrapped (the same wrapper on the code before)
SH.ms = 0
local _, ict = findup(RW, 'ChooseTiles')
debug.setupvalue(RW, ict, function(...) local t = clock(); local a, b = CT(...); SH.ms = SH.ms + (clock() - t) * 1000; return a, b end)
local CB = ns.ChooseBlocks
ns.ChooseBlocks = function(...) local t = clock(); local a, b = CB(...); SH.ms = SH.ms + (clock() - t) * 1000; return a, b end
local keep = ns.choice
if not keep then return end
SH.on = true
local Full = findup(CT, 'Choose')
local FullB = findup(CB, 'Choose')
local LevelsB = findup(FullB, 'Levels') or FullB -- (the blocks' levels: lvPrev, lvNow, lvFrame)
local cands = findup(Full, 'cands')
local BoxInView = findup(Full, 'BoxInView')
local InView = findup(FullB, 'InView')
local MINIMAP_PX = findup(RW, 'MINIMAP_PX')
local VO_EPS = findup(RW, 'VO_EPS')
local blist = ns.blockList
local Lod = ns.Lod
local TILE = ns.TILE
local LODF = { 'list', 'kappa', 'target', 'tau', 'W', 'TT', 'ox', 'oy', 'od', 'map', 'cx', 'cy', 'dz2', 'F', 'frame' }
local CF = { 'tx', 'ty', 'key', 'd', 'toTarget', 'ld', 'rec', 'grid', 'level' }
local EF = { 'c', 'bi', 'd', 'x0', 'y1', 'dc', 'ppy', 'bk', 1, 2, 3, 'want', 'lv', 'nt' }
local function tiles(n, F)
  local t = {}
  for i = 1, n do local c = cands[i]; t[c.key] = { c = c, grid = c.grid, level = c.level, sharp = TILE * F / math.max(c.d, 1) > MINIMAP_PX } end
  return t
end
local function blocks() -- (copied out: the tables are the pool's, which the shadow's choice fills again)
  local b = {}
  for i = 1, #blist do local e = blist[i]; b[e.bk] = { lv = e.lv, ppy = e.ppy, bi = e.bi, x0 = e.x0, y1 = e.y1, tx = e.c.tx, ty = e.c.ty } end
  return b
end
-- does a convex polygon (screen x, y pairs) reach the canvas (half sizes hw, hh)? (separating axes)
local function onCanvas(P, n, hw, hh)
  local x0, x1, y0, y1 = math.huge, -math.huge, math.huge, -math.huge
  for i = 1, n do local x, y = P[2 * i - 1], P[2 * i]; x0 = math.min(x0, x); x1 = math.max(x1, x); y0 = math.min(y0, y); y1 = math.max(y1, y) end
  if x1 < -hw or x0 > hw or y1 < -hh or y0 > hh then return false end
  for i = 1, n do
    local j = i % n + 1
    local ex, ey = P[2 * j - 1] - P[2 * i - 1], P[2 * j] - P[2 * i]
    local nx, ny = ey, -ex
    local pmin, pmax = math.huge, -math.huge
    for k = 1, n do local v = P[2 * k - 1] * nx + P[2 * k] * ny; pmin = math.min(pmin, v); pmax = math.max(pmax, v) end
    local rmin, rmax = math.huge, -math.huge
    for _, c in ipairs({ { -hw, -hh }, { hw, -hh }, { -hw, hh }, { hw, hh } }) do local v = c[1] * nx + c[2] * ny; rmin = math.min(rmin, v); rmax = math.max(rmax, v) end
    if pmax < rmin or pmin > rmax then return false end
  end
  return true
end
-- does a triangle (world corners) show on the canvas: cut at the near plane as the drawing cuts it, back faces
-- (cull) left out as the drawing leaves them out
local CLIP_D = 1.5
local function triOnCanvas(V, cam, hw, hh, cull)
  local F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = table.unpack(cam)
  local D, Q = {}, {}
  for i = 0, 2 do
    local x, y, z = V[3 * i + 1] - cx, V[3 * i + 2] - cy, V[3 * i + 3] - cz
    D[i + 1] = { x * fx + y * fy + z * fz, x * rx + y * ry, x * ux + y * uy + z * uz }
  end
  local n, front = 0, 0
  for i = 1, 3 do
    local a, b = D[i], D[i % 3 + 1]
    if a[1] > CLIP_D then n = n + 1; Q[2 * n - 1], Q[2 * n] = a[2] * F / a[1], a[3] * F / a[1]; front = front + 1 end
    if (a[1] > CLIP_D) ~= (b[1] > CLIP_D) then
      local t = (CLIP_D - a[1]) / (b[1] - a[1])
      local s, u = a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t
      n = n + 1; Q[2 * n - 1], Q[2 * n] = s * F / CLIP_D, u * F / CLIP_D
    end
  end
  if n < 3 then return false end
  if cull and front == 3 and (Q[3] - Q[1]) * (Q[6] - Q[2]) - (Q[5] - Q[1]) * (Q[4] - Q[2]) <= 0 then return false end
  return onCanvas(Q, n, hw, hh)
end
local STEP = { TILE / 512, TILE / 128, TILE / 64 }
SH.stat = { lvBvis = 0, lvBhyst = 0, lvBlate = 0, lvBother = 0, lvBgone = 0, imgOff = 0, frames = 0, boxOnly = 0, fresh = 0, missT = 0, missB = 0, lvT = 0, sharpT = 0, lvB = 0, freshDiff = 0, corner = 0, cornersN = 0, overBudget = 0, maxTris = 0, lagMax = 0, boxOnly = 0 }
local since = {} -- key -> frame a difference was first seen
local function note(key, frame, differs)
  if differs then if not since[key] then since[key] = frame end
  elseif since[key] then local lag = frame - since[key]; if lag > SH.stat.lagMax then SH.stat.lagMax = lag end; since[key] = nil end
end
-- After a Render: the full choice made again from the same state, compared with the one drawn, all put back.
function SH.check()
  local S = SH.stat
  local frameNo = findup(RW, 'frameNo')
  local fresh = keep.frame == frameNo
  S.frames = S.frames + 1
  if fresh then S.fresh = S.fresh + 1 end
  local F = ns.Focal()
  local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
  local w, h = ns.canvas:GetSize()
  local nA = keep.n
  local useDetail = select(3, ns.Budgets())
  local drawsBlocks = useDetail and ns.cam.dist < 2500
  local A, AB = tiles(nA, F), drawsBlocks and blocks() or {}
  local tris = ns.stats.tris
  if tris > S.maxTris then S.maxTris = tris end
  local budget = ns.Budgets()
  if tris > budget then S.overBudget = S.overBudget + 1 end
  -- save
  local savedC = {}
  for i = 1, #cands do local c, s = cands[i], {}; for _, f in ipairs(CF) do s[f] = c[f] end; savedC[i] = s end
  local savedL = {}
  for _, f in ipairs(LODF) do savedL[f] = Lod[f] end
  local list = {}; for i = 1, #Lod.list do list[i] = Lod.list[i] end
  local savedB, order = {}, {}
  for i = 1, #blist do local e, s = blist[i], {}; for _, f in ipairs(EF) do s[f] = e[f] end; savedB[i] = s; order[i] = e end
  local lvPrev, iP = findup(LevelsB, 'lvPrev')
  local lvNow, iN = findup(LevelsB, 'lvNow')
  local lvFrame, iF = findup(LevelsB, 'lvFrame')
  local tau0, px0 = ns.stats.tau, ns.stats.detailPx
  -- the shadow: the controller held (0 steps), the blocks' levels kept from the last choice as a fresh one would
  debug.setupvalue(LevelsB, iF, frameNo - 1)
  local nS = Full(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, 0)
  local S_T = tiles(nS, F)
  local S_B, Tshadow = {}, 0
  if drawsBlocks then
    FullB(F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, nS)
    Tshadow = ns.stats.detailPx
    S_B = blocks()
  end
  for k, t in pairs(S_T) do t.lo, t.hi = nil, nil end
  -- compare: tiles whose ground the full choice draws and whose box reaches the canvas
  local hw, hh = w / 2 + 2, h / 2 + 2
  local map = ns.cam.map
  local diffs = {}
  for key, s in pairs(S_T) do
    local a = A[key]
    if s.grid then
      local tx, ty = key % 64, math.floor(key / 64)
      local hgt = ns.TileHeights(map, tx, ty)
      local vis = BoxInView(tx * TILE, (tx + 1) * TILE, -(ty + 1) * TILE, -ty * TILE, hgt.lo, hgt.hi, F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz, hw, hh)
      if vis and not (a and a.grid) then
        -- the box reaches the canvas: does the ground drawn there (the full choice's level, morphed)?
        local mesh, nt = Lod.NewMesh(map, tx, ty, s.level, hgt)
        Lod.Morph(mesh, cx, cy, frameNo)
        local camv = { F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz }
        vis = false
        for i = 1, nt do
          local A, B, C = Lod.ta[i], Lod.tb[i], Lod.tc[i]
          if triOnCanvas({ mesh.vx[A], mesh.vy[A], mesh.vh[A], mesh.vx[B], mesh.vy[B], mesh.vh[B], mesh.vx[C], mesh.vy[C], mesh.vh[C] }, camv, hw, hh, true) then vis = true break end
        end
        if not vis then S.boxOnly = S.boxOnly + 1 end
      end
      if vis and not (a and a.grid) then
        S.missT = S.missT + 1
        if SH.verbose then io.write(('MISSING tile %d,%d frame %d (fresh %s) in kept %s grid %s; kept at frame %d\n'):format(tx, ty, frameNo, tostring(fresh), tostring(a ~= nil), tostring(a and a.grid), keep.frame)) end
      end
    end
    local dl = a and a.grid and s.grid and a.level ~= s.level
    local ds = a and a.grid and s.grid and a.sharp ~= s.sharp
    if dl then S.lvT = S.lvT + 1 end
    if ds then
      S.sharpT = S.sharpT + 1
      local off = math.abs(TILE * F / math.max(s.c.d, 1) / MINIMAP_PX - 1)
      if off > S.imgOff then S.imgOff = off end
    end
    if fresh and (dl or ds or not a or a.grid ~= s.grid) then S.freshDiff = S.freshDiff + 1 end
    note('t' .. key, frameNo, dl or ds)
  end
  if fresh then for key in pairs(A) do if not S_T[key] then S.freshDiff = S.freshDiff + 1 end end end
  local kx, ky = (w / 2 + 2) / F, (h / 2 + 2) / F
  for bk, s in pairs(S_B) do
    local a = AB[bk]
    if s.lv > 0 then
      local tb = ns.TileBlocks(map, s.tx, s.ty)
      local vis = InView(s.x0, s.x0 + ns.BLOCK, s.y1 - ns.BLOCK, s.y1, tb.lo[s.bi], tb.top[s.bi], kx, ky, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
      if vis and not a then
        local g = ns.BlockGeo(map, s.tx, s.ty, s.bi, s.lv)
        local camv = { F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz }
        vis = false
        local idx = ns.BlockTris and ns.BlockTris(g, {}) or g.idx -- (corners decoded when asked since A4)
        for i = 1, g.nt do
          local A, B, C = idx[3 * i - 2], idx[3 * i - 1], idx[3 * i]
          if triOnCanvas({ g.vx[A], g.vy[A], g.vh[A], g.vx[B], g.vy[B], g.vh[B], g.vx[C], g.vy[C], g.vh[C] }, camv, hw, hh, false) then vis = true break end
        end
        if not vis then S.boxOnly = S.boxOnly + 1 end
      end
      if vis and not a then
        S.missB = S.missB + 1
        if SH.verbose then io.write(('MISSING block %d frame %d\n'):format(bk, frameNo)) end
      end
    end
    local dl = (a and a.lv or 0) ~= s.lv
    if dl then S.lvB = S.lvB + 1 end
    if fresh and dl then S.freshDiff = S.freshDiff + 1 end
    -- on the canvas (a block in the 40 px margin round it is not seen at either level)
    local tb = ns.TileBlocks(map, s.tx, s.ty)
    local seen = dl and InView(s.x0, s.x0 + ns.BLOCK, s.y1 - ns.BLOCK, s.y1, tb.lo[s.bi], tb.top[s.bi], kx, ky, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
    if seen then
      S.lvBvis = S.lvBvis + 1
      -- a level the full choice's own hysteresis would keep (had it been last frame's); kept flat (the budget's
      -- far end: the full choice raises it); kept raised (it goes flat); or another level
      local lv, T, ppy = a and a.lv or 0, Tshadow, s.ppy
      if lv > 0 and s.lv > 0 and STEP[lv] * ppy <= T * 1.25 and (lv == 3 or STEP[lv + 1] * ppy > T / 1.25) then S.lvBhyst = S.lvBhyst + 1
      elseif lv == 0 then S.lvBlate = S.lvBlate + 1 elseif s.lv == 0 then S.lvBgone = S.lvBgone + 1 else S.lvBother = S.lvBother + 1 end
    end
    note('b' .. bk, frameNo, seen)
  end
  for bk, e in pairs(AB) do
    if e.lv > 0 and not S_B[bk] then
      S.lvB = S.lvB + 1
      if fresh then S.freshDiff = S.freshDiff + 1 end
      local tb = ns.TileBlocks(map, e.tx, e.ty)
      local seen = InView(e.x0, e.x0 + ns.BLOCK, e.y1 - ns.BLOCK, e.y1, tb.lo[e.bi], tb.top[e.bi], kx, ky, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz)
      if seen then S.lvBvis = S.lvBvis + 1; S.lvBgone = S.lvBgone + 1 end
      note('b' .. bk, frameNo, seen)
    end
  end
  -- corners: every corner drawn of a mesh at the full choice's level, against its vertex's exact projection
  for _, t in ipairs(ns.stats.visible) do
    local m = t.mesh
    local same
    if m and m.detail then
      local s = S_B[math.floor(-m.key / 4)]
      same = s and s.lv == (-m.key) % 4
    elseif m then
      local s = S_T[m.ty * 64 + m.tx]
      same = s and s.level == m.level
    end
    if same and not t.clipped then
      local fixed = m.fixed or {}
      for q, k in ipairs({ t.a, t.b, t.c }) do
        local x, y, z = m.vx[k] - cx, m.vy[k] - cy, m.vh[k] - cz
        local d = x * fx + y * fy + z * fz
        if d > 1 then
          local s = F / d
          local px, py = (x * rx + y * ry) * s, (x * ux + y * uy + z * uz) * s
          local sx, sy = t['x' .. q], t['y' .. q]
          local e = math.max(math.abs(px - sx), math.abs(py - sy))
          if e > S.corner then S.corner = e end
          S.cornersN = S.cornersN + 1
        end
      end
    end
  end
  -- put back
  for i = 1, #savedC do local c, s = cands[i], savedC[i]; for _, f in ipairs(CF) do c[f] = s[f] end end
  for _, f in ipairs(LODF) do Lod[f] = savedL[f] end
  for i = 1, #Lod.list do Lod.list[i] = nil end
  for i = 1, #list do Lod.list[i] = list[i] end
  Lod.SetTau(savedL.tau, savedL.W)
  for i = #blist, 1, -1 do blist[i] = nil end
  for i = 1, #order do local e, s = order[i], savedB[i]; for _, f in ipairs(EF) do e[f] = s[f] end; blist[i] = e end
  debug.setupvalue(LevelsB, iP, lvPrev); debug.setupvalue(LevelsB, iN, lvNow); debug.setupvalue(LevelsB, iF, lvFrame)
  ns.stats.tau, ns.stats.detailPx = tau0, px0
  -- at a fresh choice every open difference must be gone
  if fresh then for k, f in pairs(since) do local lag = frameNo - f; if lag > S.lagMax then S.lagMax = lag end; since[k] = nil end end
end
function SH.reset() for k in pairs(SH.stat) do SH.stat[k] = 0 end; for k in pairs(since) do since[k] = nil end end
''')
SH = G.SH
SH.verbose = bool(os.environ.get('CHOICE_VERBOSE'))
if MUT == 'loose' and NEW:  # the bound 10 x too loose: the kept view's margin as if 400 px (and the choice kept as long as it allows)
    L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.choice.MARGIN = 400; ns.choice.KEEP = 1000')
if os.environ.get('CHOICE_KEEP') and NEW:  # (frames a choice may be kept while the view moves: the bound alone with a large one)
    ns.choice.KEEP = int(os.environ['CHOICE_KEEP'])

def view(m, gx, gy, dist, pitch, yaw=0):
    ns.SetCamMode('free')
    if pitch >= 89: ns.SetTopDown(True, True)
    else: ns.SetTopDown(False, True); cam.pitch = pitch
    cam.map, cam.x, cam.y, cam.dist, cam.yaw = m, gx * TILE, -gy * TILE, dist, yaw
    cam.th = ns.GroundHeight(cam.x, cam.y, m)
    ns.SnapLift()

QUICK = os.environ.get('CHOICE_QUICK')
def nf(n): return max(6, n // 3) if QUICK else n

SEGS = []  # (place, name, frames, setup, step)
def walker(X, Y, m, hd, speed, pitch):
    state = {'k': 0}
    def setup():
        place(X, Y, m, hd); ns.ReadPlayer(); ns.FollowMe('follow')
        tick(40)  # (the flight to you ends)
        if pitch >= 89: ns.SetTopDown(True, True)
        else: ns.SetTopDown(False, True); cam.pitch = pitch
        state['k'] = 0
        ns.FollowStep(1 / 30); ns.SnapLift()
    def step():
        state['k'] += 1
        place(X + math.cos(hd) * speed * state['k'], Y + math.sin(hd) * speed * state['k'], m, hd)
        ns.ReadPlayer(); ns.FollowStep(1 / 30)
    return setup, step
def setter(m, gx, gy, dist, pitch, yaw):
    return lambda: view(m, gx, gy, dist, pitch, yaw)
def pan(dx, dy):
    def step(): cam.x = cam.x + dx; cam.y = cam.y + dy
    return step
def turn(deg):
    def step(): cam.yaw = (cam.yaw + deg) % 360
    return step
def tilt(deg):
    def step():
        cam.pitch = max(45, min(89.9, cam.pitch + deg))
    return step
def zoom(f):
    def step(): cam.dist = cam.dist * f
    return step

# Stormwind, Trade District (default view: 330 yd straight down, following you)
SW = (-8830, 640, 0)
sgx, sgy = 32 - SW[1] / TILE, 32 - SW[0] / TILE
for name, setup_step, n in [
        ('walk 0.25 yd/frame, straight down', walker(SW[0], SW[1], 0, 1.0, 0.25, 89.9), 90),
        ('walk 0.25 yd/frame, tilted 45', walker(SW[0], SW[1], 0, 1.0, 0.25, 45), 90)]:
    SEGS.append(('Stormwind', name, nf(n), setup_step[0], setup_step[1]))
SEGS += [
    ('Stormwind', 'pan 2 yd/frame, straight down', nf(60), setter(0, sgx, sgy, 330, 89.9, 0), pan(1.4, 1.4)),
    ('Stormwind', 'turn 1 deg/frame, straight down', nf(60), setter(0, sgx, sgy, 330, 89.9, 0), turn(1)),
    ('Stormwind', 'turn 3 deg/frame, tilted 45', nf(40), setter(0, sgx, sgy, 330, 45, 0), turn(3)),
    ('Stormwind', 'tilt 1 deg/frame, 45 to 89.9', nf(45), setter(0, sgx, sgy, 330, 45, 20), tilt(1)),
    ('Stormwind', 'zoom in 2 %/frame, 800 to 240 yd', nf(60), setter(0, sgx, sgy, 800, 89.9, 0), zoom(0.98)),
    ('Stormwind', 'still, redrawn', nf(30), setter(0, sgx, sgy, 330, 89.9, 0), lambda: None),
]
OG = (1630, -4380, 1)
ogx, ogy = 32 - OG[1] / TILE, 32 - OG[0] / TILE
og_setup, og_step = walker(OG[0], OG[1], 1, 2.0, 0.25, 45)
SEGS += [
    ('Orgrimmar', 'walk 0.25 yd/frame, tilted 45, 150 yd', nf(90), lambda: (og_setup(), setattr(cam, "dist", 150)), og_step),
    ('Orgrimmar', 'pan 1 yd/frame, tilted 45, 150 yd', nf(60), setter(1, ogx, ogy, 150, 45, 30), pan(0.7, -0.7)),
    ('Orgrimmar', 'turn 1 deg/frame, tilted 45, 150 yd', nf(60), setter(1, ogx, ogy, 150, 45, 30), turn(1)),
    ('Orgrimmar', 'zoom out 2 %/frame, 150 to 500 yd', nf(60), setter(1, ogx, ogy, 150, 60, 30), zoom(1.02)),
]
SEGS += [
    ('Hyjal far', 'turn 1 deg/frame, 5,000 yd tilted 45', nf(60), setter(1, 38.6, 21.8, 5000, 45, 30), turn(1)),
    ('Hyjal far', 'pan 20 yd/frame, 5,000 yd tilted 45', nf(60), setter(1, 38.6, 21.8, 5000, 45, 30), pan(14, 14)),
    ('Hyjal far', 'tilt 0.5 deg/frame, 5,000 yd', nf(60), setter(1, 38.6, 21.8, 5000, 50, 30), tilt(0.5)),
    ('Hyjal far', 'zoom in 2 %/frame, 5,000 to 1,500 yd', nf(60), setter(1, 38.6, 21.8, 5000, 45, 30), zoom(0.98)),
    ('Hyjal far', 'still, redrawn', nf(30), setter(1, 38.6, 21.8, 5000, 45, 30), lambda: None),
    ('Eastern Kingdoms', 'turn 1 deg/frame, 12,000 yd tilted 55', nf(60), setter(0, 32, 40, 12000, 55, 0), turn(1)),
    ('Eastern Kingdoms', 'still, redrawn, 12,000 yd', nf(30), setter(0, 32, 40, 12000, 55, 0), lambda: None),
]

clock = L.eval('os.clock')
gccount = L.eval('function() return collectgarbage("count") end')
gcstop = L.eval('function() collectgarbage("collect"); collectgarbage("stop") end')
gcgo = L.eval('function() collectgarbage("restart") end')
out = []
check_shadow = SH.on and PASS == 'time'
for place_name, name, n, setup, step in SEGS:
    setup()
    for _ in range(3): ns.Render()  # meshes made, blocks decoded
    for _ in range(40):
        ns.Render()
        if st.detailPending == 0: break
    if check_shadow: SH.reset()
    ms, cms, calls, kb, reused, tris_max, over, kept_ms, fresh_ms = [], [], [], [], 0, 0, 0, [], []
    for k in range(n):
        step()
        if PASS == 'calls':
            G.CALLS.n = 0; gcstop(); k0 = gccount()
            ns.Render()
            kb.append(gccount() - k0); gcgo(); calls.append(int(G.CALLS.n))
        else:
            SH.ms = 0
            t0 = clock(); ns.Render(); ms.append((clock() - t0) * 1000); cms.append(float(SH.ms))
        if NEW and ns.choice.reused: reused += 1
        if PASS != 'calls': (kept_ms if NEW and ns.choice.reused else fresh_ms).append(cms[-1])
        tris_max = max(tris_max, int(st.tris)); over += int(st.tris) > int(ns.Budgets()[0])
        if check_shadow: SH.check()
    med = lambda a: sorted(a)[len(a) // 2] if a else 0
    mean = lambda a: sum(a) / len(a) if a else 0
    r = {'place': place_name, 'seg': name, 'n': n, 'reused': reused / n, 'tris': tris_max, 'over': over}
    if PASS == 'calls':
        r.update({'calls': med(calls), 'calls_mean': mean(calls), 'kb': med(kb)})
        print(f'{place_name:16s} {name:42s} reused {r["reused"] * 100:5.1f} %  C calls median {r["calls"]:6d} mean {r["calls_mean"]:8.1f}  garbage {r["kb"]:6.1f} KB')
    else:
        r.update({'ms': med(ms), 'ms_mean': mean(ms), 'choice': med(cms), 'choice_mean': mean(cms), 'kept_ms': kept_ms, 'fresh_ms': fresh_ms})
        line = f'{place_name:16s} {name:42s} reused {r["reused"] * 100:5.1f} %  ground tris max {tris_max} (over budget {over})  Render {r["ms"]:6.2f} ms median {r["ms_mean"]:6.2f} mean  choice {r["choice"]:5.2f} median {r["choice_mean"]:5.2f} mean'
        if check_shadow:
            s = SH.stat
            r.update({k: float(s[k]) for k in ('frames', 'fresh', 'missT', 'missB', 'lvT', 'sharpT', 'lvB', 'freshDiff', 'corner', 'cornersN', 'overBudget', 'maxTris', 'lagMax', 'boxOnly', 'lvBhyst', 'lvBlate', 'lvBother', 'lvBgone', 'imgOff', 'lvBvis')})
            line += f'  | fresh {int(s.fresh)}/{int(s.frames)} missing {int(s.missT)} tiles {int(s.missB)} blocks (boxes only {int(s.boxOnly)}); differing (tile-frames) level {int(s.lvT)} image {int(s.sharpT)} (at most {s.imgOff * 100:.1f} % from the switch) blocks {int(s.lvB)}, on the canvas {int(s.lvBvis)} (within hysteresis {int(s.lvBhyst)}, kept flat {int(s.lvBlate)}, kept raised {int(s.lvBgone)}, other {int(s.lvBother)}); at fresh frames {int(s.freshDiff)}; lag max {int(s.lagMax)} frames; corners {int(s.cornersN)} worst {s.corner:.3f} px; tris max {int(s.maxTris)} over budget {int(s.overBudget)}'
        print(line)
    out.append(r)
    sys.stdout.flush()

if os.environ.get('CHOICE_JSON'):
    json.dump([{k: v for k, v in r.items() if not isinstance(v, list)} for r in out], open(os.environ['CHOICE_JSON'], 'w'), indent=1)

if PASS == 'time':
    walk = [r for r in out if r['seg'].startswith('walk') or r['seg'].startswith('pan')]
    check('the choice is kept on most frames while walking and panning (Stormwind, Orgrimmar, Hyjal)', walk and min(r['reused'] for r in walk) >= 0.4,
          ', '.join(f'{r["place"]} {r["seg"].split(",")[0]} {r["reused"] * 100:.0f} %' for r in walk))
    if NEW:
        kept = [x for r in out for x in r['kept_ms']]; fresh = [x for r in out for x in r['fresh_ms']]
        mk, mf = sum(kept) / max(len(kept), 1), sum(fresh) / max(len(fresh), 1)
        walk_old = [r for r in out if r['seg'].startswith('walk')]
        check('a kept frame\'s choice costs under a quarter of a full one (same run, all segments)', kept and fresh and mk < 0.25 * mf,
              f'{len(kept)} kept frames {mk:.3f} ms on average, {len(fresh)} full choices {mf:.3f} ms')
    else:
        check('(the code before: every frame chooses afresh, nothing kept)', False)
    if check_shadow:
        tot = lambda k: sum(r.get(k, 0) for r in out)
        check('no ground and no raised block missing on the canvas on any frame of the path (against the full choice each frame)', tot('missT') == 0 and tot('missB') == 0,
              f'{int(tot("frames"))} frames, missing tiles {int(tot("missT"))}, blocks {int(tot("missB"))}')
        keepn = int(ns.choice.KEEP)
        check(f'on every frame that chose afresh, tiles, levels, images and blocks are the full choice; so a difference on the canvas lasts at most until the next fresh choice, {keepn - 1} frames at most (KEEP {keepn})',
              tot('freshDiff') == 0 and max(r.get('lagMax', 0) for r in out) <= keepn - 1, f'{int(tot("fresh"))} fresh frames, differences there {int(tot("freshDiff"))}; kept frames: tile levels differing {int(tot("lvT"))} tile-frames, images {int(tot("sharpT"))}, blocks {int(tot("lvB"))} (on the canvas {int(tot("lvBvis"))}); longest {int(max(r.get("lagMax", 0) for r in out))} frames')
        worst = max(r.get('corner', 0) for r in out)
        check('every corner drawn (meshes at the full choice\'s level) within VO_EPS = 0.25 px of its exact projection', worst <= 0.25 + 1e-6, f'{int(tot("cornersN"))} corners, worst {worst:.4f} px')
        check('the ground never over its triangle budget', tot('overBudget') == 0, f'most {int(max(r.get("maxTris", 0) for r in out))} triangles')
    elif not NEW:
        check('(the code before: the shadow checks need ns.choice)', False)

    # recompute at once on a resize, a map change, a setting change or a data change
    if NEW:
        view(0, sgx, sgy, 330, 89.9, 0)
        for _ in range(3): ns.Render()
        ns.Render()
        fails = []
        def fresh_after(what, fn):
            ns.Render(); ns.Render()
            was, before = ns.choice.reused, ns.choice.frame
            fn()
            ns.Render()  # (the setters redraw at once themselves)
            if not (was and ns.choice.frame > before): fails.append(what)
        def resize():
            global W, H
            W, H = 1200, 760; tick(1); W, H = 1280, 800
        fresh_after('budget', lambda: ns.SetGridBudget(3000))
        ns.SetGridBudget(3200)
        fresh_after('buildings budget', lambda: ns.SetBuildingBudget(3500))
        ns.SetBuildingBudget(4000)
        fresh_after('buildings off', lambda: ns.SetDetail(False))
        ns.SetDetail(True)
        fresh_after('the game\'s buildings covering blocks', lambda: setattr(ns, 'coverStamp', (ns.coverStamp or 0) + 1))
        fresh_after('the probe putting levels back', lambda: ns.BlockLevels(ns.BlockLevels()))
        fresh_after('another map', lambda: (setattr(cam, 'map', 1), setattr(cam, 'x', 40.6 * TILE), setattr(cam, 'y', -30.6 * TILE)))
        view(0, sgx, sgy, 330, 89.9, 0)
        ns.Render(); ns.Render()
        G.GPS3D_Frame.SetSize(G.GPS3D_Frame, 880, 640)
        ns.Render()
        if ns.choice.reused: fails.append('resize')
        G.GPS3D_Frame.SetSize(G.GPS3D_Frame, 900, 650)
        # near the camera (Orgrimmar, 150 yd tilted: towers and cliffs within reach of the camera's height), a
        # block reaching into the view that the kept choice did not gather stops it being kept
        view(1, ogx, ogy, 150, 45, 30)
        ns.Render(); ns.Render(); ns.Render()
        kept_before = bool(ns.choice.reused)
        bset = ns.choice.blockSet
        saved = {k: v for k, v in bset.items()}
        for k in list(saved): bset[k] = None
        cam.x = cam.x + 0.2; ns.Render()
        stopped = not ns.choice.reused
        for k, v in saved.items(): bset[k] = v
        check('near the camera (Orgrimmar 150 yd tilted 45), the choice is kept only while every block reaching into the view there is in it', kept_before and stopped,
              f'kept with the blocks {kept_before}, chosen afresh without them {stopped}')
        check('a resize, another map, a budget, buildings switched, the game\'s buildings covering blocks and the probe\'s putting back each make the next frame choose afresh',
              not fails, 'not afresh after: ' + ', '.join(fails) if fails else '7 of 7')

print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed')
sys.exit(0 if results and all(ok for _, ok in results) else 1)
