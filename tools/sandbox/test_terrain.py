# The 3D view's ground mesh (GPS3D.lua: ChooseTiles, BuildGridMesh, the morphing in RenderWorld), checked
# and measured in Lua 5.4 (lupa) on the real height data:
#   pops     zooming slowly (2 % a frame) from 14,000 to 30 yd, tilted 45 degrees and straight down, at
#            Mount Hyjal, Durotar near Orgrimmar and Elwynn Forest: how much the drawn ground moves at
#            fixed world points from one frame to the next (the camera's own motion moves nothing there)
#   far      fixed far views (Hyjal 5,000 yd tilted 45, Stormwind 3,000 yd tilted 45, Durotar 4,000 yd
#            straight down): the drawn ground's error against the full 33 x 33 grid, in screen pixels,
#            weighted by screen area (each grid point stands for the pixels its 16.7-yd cell covers)
#   seams    every shared tile edge drawn at the same heights from both sides, also while morphing
#   time     Render's time (processor time, so other programs running do not count) at those views, the
#            camera turning a degree a frame, and during the zoom
#   hand-over just short of 18,000 yd (the planet view takes over there) every tile at its coarsest step
# GPS3D_LUA=<path> loads another GPS3D.lua in place of the sandbox's copy (to measure the code before a
# change); TERRAIN_QUICK=1 zooms at one place only.
import lupa.lua54 as lupa54, math, time, os, sys
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
ns = G.SANDBOX.namespaces['GPS3D']
if os.environ.get('LOD_P'):  # experiments: the level-of-detail parameters (GPS3D.lua's Lod.TAU_MIN, TEX, WIDE)
    L.execute('''local ns = SANDBOX.namespaces.GPS3D
local function findup(f, name) for i = 1, 200 do local n, v = debug.getupvalue(f, i); if not n then return end; if n == name then return v end end end
LOD = findup(findup(ns.Render, 'RenderWorld'), 'Lod')''')
    for kv in os.environ['LOD_P'].split(','):
        k, v = kv.split('=')
        G.LOD[k] = float(v)
TILE = 1600 / 3
W, H = 1280, 800
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
ns = G.SANDBOX.namespaces['GPS3D']
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

G.SANDBOX_PLAYER(-9464, 62, 0, 0, 0.3, 'Elwynn Forest', 'Goldshire', -1, -1, -1)
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
cam, st = ns.cam, ns.stats
ns.SetCamMode('free')
print('budget', int(G.GPS3D_DB.grid or 3200), 'code', ALT or 'sandbox copy')

L.execute(r'''
TERRAIN = {}
local ns = SANDBOX.namespaces.GPS3D
local TILE, CELL = 1600 / 3, 1600 / 3 / 32
local byTile = {}
-- the grid meshes drawn this frame, by tile (a mesh with any triangle shown)
function TERRAIN.index()
  for k in pairs(byTile) do byTile[k] = nil end
  for _, t in ipairs(ns.stats.visible) do local m = t.mesh; if m and not m.detail then byTile[m.ty * 64 + m.tx] = m end end
  return byTile
end
-- where a world point lies in a mesh: its triangle's three vertices and their weights
local function locate(m, x, y)
  local s, n = m.step, m.n
  local fi, fj = (x - m.tx * TILE) / (CELL * s), (-m.ty * TILE - y) / (CELL * s)
  local i, j = math.floor(fi), math.floor(fj)
  if i >= n then i = n - 1 end
  if j >= n then j = n - 1 end
  if i < 0 then i = 0 end
  if j < 0 then j = 0 end
  local u, v = fi - i, fj - j
  local row = n + 1
  local k00 = j * row + i + 1
  if u >= v then return k00, k00 + row + 1, k00 + 1, 1 - u, v, u - v end -- (00, 11, 10)
  return k00, k00 + row, k00 + row + 1, 1 - v, v - u, u                   -- (00, 01, 11)
end
-- the drawn height at a world point (nil where no grid mesh is drawn)
function TERRAIN.drawn(x, y)
  local tx, ty = math.floor(x / TILE), math.floor(-y / TILE)
  if tx < 0 or tx > 63 or ty < 0 or ty > 63 then return nil end
  local m = byTile[ty * 64 + tx]
  if not m or m.tx ~= tx or m.ty ~= ty then return nil end
  local a, b, c, wa, wb, wc = locate(m, x, y)
  local vh = m.vh
  return vh[a] * wa + vh[b] * wb + vh[c] * wc, m
end
local cam
local function basis()
  local F = ns.Focal()
  local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
  cam = { F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz }
end
local function project(x, y, h)
  local F, fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = table.unpack(cam)
  local dx, dy, dz = x - cx, y - cy, h - cz
  local d = dx * fx + dy * fy + dz * fz
  if d <= 1.5 then return nil end
  return (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d, d
end

-- pops: fixed world points, the drawn height there each frame against the frame before
local P = { x = {}, y = {}, prev = {}, dyd = {}, dpx = {}, n = 0 }
function TERRAIN.popStart(x0, y0)
  P.x, P.y, P.prev, P.dyd, P.dpx, P.n, P.pairs = {}, {}, {}, {}, {}, 0, 0
  local k = 0
  local r = 12
  while r < 32000 do
    for a = 0, 47 do
      local ang = (a + (k % 2) * 0.5) / 48 * 2 * math.pi
      k = k + 1
      P.x[k], P.y[k] = x0 + r * math.cos(ang), y0 + r * math.sin(ang)
    end
    r = r * 1.12
  end
  P.np = k
end
function TERRAIN.popFrame(W, H)
  TERRAIN.index(); basis()
  local hw, hh = W / 2, H / 2
  local fmax, fk, fm = 0, nil, nil
  for k = 1, P.np do
    local x, y = P.x[k], P.y[k]
    local h, mesh = TERRAIN.drawn(x, y)
    local old = P.prev[k]
    if h and old then
      local sx, sy = project(x, y, h)
      if sx and sx > -hw and sx < hw and sy > -hh and sy < hh then
        local qx, qy = project(x, y, old)
        if qx then
          P.n = P.n + 1
          P.dyd[P.n] = math.abs(h - old)
          P.dpx[P.n] = math.sqrt((sx - qx) ^ 2 + (sy - qy) ^ 2)
          if P.dpx[P.n] > fmax then fmax, fk, fm = P.dpx[P.n], k, mesh end
        end
      end
    end
    P.prev[k] = h or false
  end
  return fmax, fk, fm
end
local function stats(a, n)
  table.sort(a)
  local function pct(p) if n == 0 then return 0 end return a[math.max(1, math.min(n, math.ceil(p * n)))] end
  local over1, over05 = 0, 0
  for i = 1, n do if a[i] > 1 then over1 = over1 + 1 end; if a[i] > 0.5 then over05 = over05 + 1 end end
  return { n = n, max = a[n] or 0, p99 = pct(0.99), p999 = pct(0.999), over1 = over1, over05 = over05 }
end
function TERRAIN.popResult()
  return stats(P.dpx, P.n), stats(P.dyd, P.n)
end

-- far quality: every full-grid point of every drawn tile, drawn height (and where its texel lands, the
-- triangle's corners mapped linearly as the game maps a bent texture) against the exact grid point
function TERRAIN.farError(W, H)
  TERRAIN.index(); basis()
  local hw, hh = W / 2, H / 2
  local F = cam[1]
  local list, lt, wsum, sh, stt = {}, {}, 0, 0, 0
  local n = 0
  for key, m in pairs(byTile) do
    local h = m.h
    local px, py, pd = {}, {}, {}
    for k = 1, #m.vx do px[k], py[k], pd[k] = project(m.vx[k], m.vy[k], m.vh[k]) end
    for j = 0, 32 do
      for i = 0, 32 do
        local x, y = (m.tx * 32 + i) * CELL, -(m.ty * 32 + j) * CELL
        local exact = h[j * 33 + i + 1]
        local ex, ey, ed = project(x, y, exact)
        if ex and ex > -hw and ex < hw and ey > -hh and ey < hh then
          local a, b, c, wa, wb, wc = locate(m, x, y)
          if pd[a] and pd[b] and pd[c] then
            local dh = m.vh[a] * wa + m.vh[b] * wb + m.vh[c] * wc
            local dx, dy = project(x, y, dh)
            local ax, ay = px[a] * wa + px[b] * wb + px[c] * wc, py[a] * wa + py[b] * wb + py[c] * wc
            n = n + 1
            local w = (F / ed) ^ 2 -- pixels per square yard here (about): screen-area weight
            list[n] = { math.sqrt((dx - ex) ^ 2 + (dy - ey) ^ 2), w, math.sqrt((ax - ex) ^ 2 + (ay - ey) ^ 2) }
            wsum = wsum + w
            local tk = TERRAIN.tileErr
            if tk then tk[key] = tk[key] or { 0, 0, m.step, ed, 0 }; local q = tk[key]; q[1] = q[1] + w * list[n][1]; q[2] = q[2] + w; q[5] = q[5] + 1; if ed < q[4] then q[4] = ed end end
          end
        end
      end
    end
  end
  local function wstats(idx)
    table.sort(list, function(p, q) return p[idx] < q[idx] end)
    local mean, acc, p95 = 0, 0, 0
    for i = 1, n do mean = mean + list[i][idx] * list[i][2] end
    for i = 1, n do acc = acc + list[i][2]; if acc >= 0.95 * wsum then p95 = list[i][idx] break end end
    return mean / wsum, p95, list[n][idx]
  end
  local m1, p1, x1 = wstats(1)
  local m2, p2, x2 = wstats(3)
  return { n = n, mean = m1, p95 = p1, max = x1, tmean = m2, tp95 = p2, tmax = x2 }
end

-- seams: along every edge shared by two drawn tiles, the heights from both sides; how many tiles were
-- morphing (some vertex drawn away from its own grid height)
function TERRAIN.seams()
  TERRAIN.index()
  local function edgeH(m, x, y)
    local a, b, c, wa, wb, wc = locate(m, x, y)
    return m.vh[a] * wa + m.vh[b] * wb + m.vh[c] * wc
  end
  local worst, edges, mixed, morphing = 0, 0, 0, 0
  for key, m in pairs(byTile) do
    local moved = false
    for j = 0, m.n do for i = 0, m.n do
      local k = j * (m.n + 1) + i + 1
      local own = m.g and m.g[k] or m.h[(j * m.step) * 33 + i * m.step + 1]
      if math.abs(m.vh[k] - own) > 1e-6 then moved = true end
    end end
    if moved then morphing = morphing + 1 end
    for side = 1, 2 do
      local e = byTile[key + (side == 1 and 1 or 64)]
      if e and (side == 1 and e.tx == m.tx + 1 and e.ty == m.ty or side == 2 and e.tx == m.tx and e.ty == m.ty + 1) then
        edges = edges + 1
        if e.step ~= m.step then mixed = mixed + 1 end
        for k = 0, 128 do
          local x, y
          if side == 1 then x, y = (m.tx + 1) * TILE, -m.ty * TILE - k * TILE / 128
          else x, y = m.tx * TILE + k * TILE / 128, -(m.ty + 1) * TILE end
          worst = math.max(worst, math.abs(edgeH(m, x, y) - edgeH(e, x, y)))
        end
      end
    end
  end
  return worst, edges, mixed, morphing
end
''')
T = G.TERRAIN

def view(m, gx, gy, dist, pitch, yaw=0):
    if pitch >= 89: ns.SetTopDown(True, True)
    else: ns.SetTopDown(False, True); cam.pitch = pitch
    cam.map, cam.x, cam.y, cam.dist, cam.yaw = m, gx * TILE, -gy * TILE, dist, yaw
    cam.th = ns.GroundHeight(cam.x, cam.y, m)

PLACES = [('Mount Hyjal', 1, 38.6, 21.8, 30), ('Durotar near Orgrimmar', 1, 40.6, 30.6, 200), ('Elwynn Forest', 0, 31.9, 49.75, 0)]
if os.environ.get('TERRAIN_QUICK'): PLACES = PLACES[:1]
if os.environ.get('TERRAIN_PLACE'): PLACES = [p for p in PLACES if p[0].startswith(os.environ['TERRAIN_PLACE'])]
STEP = 0.98

def zoom_run(place, pitch):
    name, m, gx, gy, yaw = place
    view(m, gx, gy, 14000, pitch, yaw)
    ns.Render()
    T.popStart(cam.x, cam.y)
    times, seam_worst, seam_morph, seam_mixed = [], 0.0, 0, 0
    tris = []
    d, frames = 14000.0, 0
    while d > 30:
        cam.dist = d
        t0 = time.process_time(); ns.Render(); times.append((time.process_time() - t0) * 1000)
        T.popFrame(W, H)
        tris.append(int(st.tris))
        if frames % 10 == 0:
            w, e, mixed, morph = T.seams()
            seam_worst = max(seam_worst, w); seam_morph += morph; seam_mixed += mixed
        d *= STEP; frames += 1
    px, yd = T.popResult()
    return frames, px, yd, times, seam_worst, seam_morph, seam_mixed, sum(tris) / len(tris)

ZOOM = []
if os.environ.get('TERRAIN_NOZOOM'): PLACES = []
for place in PLACES:
    for pitch in (45, 89.9):
        frames, px, yd, times, sw, smorph, smixed, mtris = zoom_run(place, pitch)
        times.sort()
        ZOOM.append((place[0], pitch, px, yd, times, sw, smorph, smixed))
        print(f'ZOOM {place[0]:24s} tilt {"45" if pitch < 89 else "down"}: {frames} frames, {int(px.n)} point-frames; '
              f'jump px max {px.max:.2f} p99.9 {px.p999:.3f} p99 {px.p99:.4f}, >1 px {int(px.over1)}, >0.5 px {int(px.over05)}; '
              f'yd max {yd.max:.2f} p99 {yd.p99:.4f}; grid triangles {mtris:.0f} on average; render mean {sum(times) / len(times):.2f} ms, median {times[len(times) // 2]:.2f}, worst {times[-1]:.1f}; '
              f'seams worst {sw:.1e} yd ({smorph} morphing tiles, {smixed} mixed-step edges sampled)')

FAR = [('Hyjal 5,000 yd tilted 45', 1, 38.6, 21.8, 5000, 45, 30), ('Stormwind 3,000 yd tilted 45', 0, 30.8, 48.56, 3000, 45, 0),
       ('Durotar 4,000 yd straight down', 1, 40.6, 30.6, 4000, 89.9, 0)]
FARR = []
FB = [int(x) for x in os.environ['FAR_BUDGET'].split(',')] if os.environ.get('FAR_BUDGET') else None
for fi, (name, m, gx, gy, dist, pitch, yaw) in enumerate(FAR):
    if FB: ns.SetGridBudget(FB[fi])
    view(m, gx, gy, dist, pitch, yaw)
    for _ in range(int(os.environ.get('TERRAIN_SETTLE', '80'))): ns.Render()  # (estimated errors replaced by the real ones)
    e = T.farError(W, H)
    tris = int(st.tris)
    ts = []
    L.execute('collectgarbage()')
    for k in range(40):
        cam.yaw = yaw + k; t0 = time.process_time(); ns.Render(); ts.append((time.process_time() - t0) * 1000)
    cam.yaw = yaw
    ts.sort()
    FARR.append((name, e, tris, ts[len(ts) // 2]))
    print(f'FAR {name:32s}: {tris} grid triangles (tau {float(st.tau or 0):.3g}), {int(st.tiles)} tiles; height error px mean {e.mean:.2f} p95 {e.p95:.2f} max {e.max:.1f}; '
          f'with the texture mapping mean {e.tmean:.2f} p95 {e.tp95:.2f}; render median {ts[len(ts) // 2]:.2f} ms ({int(e.n)} grid points); steps {dict(sorted((int(k), int(v)) for k, v in st.steps.items()))}')

# hand-over: just short of 18,000 yd every tile at the coarsest step, as the planet view draws them
view(1, 38.6, 21.8, 17900, 45, 30)
for _ in range(3): ns.Render()
handover = dict(sorted((int(k), int(v)) for k, v in st.steps.items()))

# ---- checks (the thresholds are the gates of GATES-J1.md; the code before 2026-10-21 fails the first and third)
worst_px = max([z[2].max for z in ZOOM] or [0]); worst_p99 = max([z[2].p99 for z in ZOOM] or [0])
if ZOOM: check('zooming slowly (2 % a frame, 14,000 to 30 yd, three places, tilted and straight down): no pops, the drawn ground at fixed points never moves more than 25 px from one frame to the next (before: up to 160 px), 99 % of the time under 2.5 px (before: up to 3.2)',
      worst_px < 25 and worst_p99 < 2.5, f'worst {worst_px:.2f} px, p99 at most {worst_p99:.3f} px')
if ZOOM: check('no cracks while zooming: shared tile edges at the same heights from both sides, morphing tiles among them',
      max(z[5] for z in ZOOM) < 1e-3 and sum(z[6] for z in ZOOM) > 0 and sum(z[7] for z in ZOOM) > 0,
      f'worst {max(z[5] for z in ZOOM):.1e} yd, {sum(z[6] for z in ZOOM)} morphing tiles, {sum(z[7] for z in ZOOM)} edges between different steps')
budget = int(G.GPS3D_DB.grid or 3200)
FAR_MAX = {'Hyjal': 2.45, 'Stormwind': 2.4, 'Durotar': 1.29}  # (before: 2.62, 2.55, 1.30)
check('far views within the ground budget, the height error on screen lower than before (mean under 2.45, 2.4 and 1.29 px; before 2.62, 2.55, 1.30)',
      all(f[2] <= budget for f in FARR) and all(f[1].mean < FAR_MAX[f[0].split()[0]] for f in FARR), '; '.join(f'{f[0]}: {f[2]} tris, mean {f[1].mean:.2f} p95 {f[1].p95:.2f}' for f in FARR))
check('hand-over: at 17,900 yd every tile at its coarsest step (the planet view draws tiles by their corners)', list(handover) == [32], str(handover))
print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed')
