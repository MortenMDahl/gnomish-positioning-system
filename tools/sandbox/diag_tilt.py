# Where does the tilted camera end up "inside" the ground? Renders many tilted views near two peaks and,
# per view: eye vs the drawn mesh under it, and screen samples where the drawn picture is wrong (hole: no
# triangle; see-through: the nearest drawn surface is well behind the real ground on that ray).
import lupa.lua54 as lupa54, os, sys, time, json
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')
SRC = sys.argv[1] if len(sys.argv) > 1 else f'{SITE}/addons/GPS3D/GPS3D.lua'
L = lupa54.LuaRuntime(); G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
toc = open('/mnt/user-data/outputs/GPS3D.toc').read()
files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
for addon, fl in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua']), ('GPS3D', files)]:
    for f in fl:
        src = open(SRC).read() if f == 'GPS3D.lua' else open(f'{SITE}/addons/{addon}/{f}').read()
        if f == 'GPS3D.lua':
            hook = next(h for h in ('stats.shown, stats.culled, stats.behind, stats.cut = nVisible, culled, behind, cut', 'stats.shown, stats.culled, stats.behind = nVisible, culled, behind') if h in src)
            src = src.replace(hook, hook + '\n\tns._active, ns._nActive = active, nActive')
        assert G.SANDBOX_LOAD(addon, f, src), f
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')
W, H = 1280, 800
def tick(n=1):
    for _ in range(n): G.SANDBOX_TICK(1 / 30, W, H)
G.SANDBOX_PLAYER(-9400, -1300, 0, 0, 0.0, 'Elwynn Forest', '', -1, -1, -1)
G.SlashCmdList.GPS(''); tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame); tick(20)
ns = G.SANDBOX.namespaces['GPS3D']
ns.SetCamMode('free'); ns.SetTopDown(False, True); tick(2)
L.execute(r'''
function DIAG(NX, NY)
  local ns = SANDBOX.namespaces.GPS3D
  local cam = ns.cam
  local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis()
  local w, h = ns.canvas:GetSize()
  local F = (h / 2) / math.tan((cam.fov or math.rad(50)) / 2)
  local act, n = ns._active, ns._nActive
  -- the drawn surface under the eye
  local drawn = -math.huge
  for i = 1, n do local m = act[i]
    local vx, vy, vh = m.vx, m.vy, m.vh
    for _, t in ipairs(m.tris) do
      local a, b, c = t.a, t.b, t.c
      local den = (vy[b]-vy[c])*(vx[a]-vx[c]) + (vx[c]-vx[b])*(vy[a]-vy[c])
      if den ~= 0 then
        local w1 = ((vy[b]-vy[c])*(cx-vx[c]) + (vx[c]-vx[b])*(cy-vy[c])) / den
        local w2 = ((vy[c]-vy[a])*(cx-vx[c]) + (vx[a]-vx[c])*(cy-vy[c])) / den
        local w3 = 1 - w1 - w2
        if w1 >= -1e-9 and w2 >= -1e-9 and w3 >= -1e-9 then
          local hh = w1*vh[a] + w2*vh[b] + w3*vh[c]
          if hh > drawn then drawn = hh end
        end
      end
    end
  end
  -- screen samples
  local holes, seeThrough, ground = 0, 0, 0
  ROWS = {}
  NEARW, NEARN, ORDERW, NEARH, NEARS, NEARO, SEED = 0, 0, 0, 0, 0, 0, ''
  for i = 0, NX - 1 do for j = 0, NY - 1 do
    local sx, sy = (i + 0.5) / NX * w - w / 2, (j + 0.5) / NY * h - h / 2
    local x, y, z = ns.ScreenToTerrain(sx, sy)
    if x and math.abs(ns.GroundHeight(x, y) - z) < 1 then
      ground = ground + 1
      local dTrue = (x - cx) * fx + (y - cy) * fy + (z - cz) * fz
      local best, topB, topD = math.huge, -1, nil
      local isNear = dTrue < 150
      if isNear then NEARN = NEARN + 1 end
      local rdx, rdy, rdz = fx + rx * sx / F + ux * sy / F, fy + ry * sx / F + uy * sy / F, fz + uz * sy / F
      for k = 1, n do local m = act[k]
        local vx, vy, vh = m.vx, m.vy, m.vh
        for _, t in ipairs(m.tris) do if t.shown then
          local vo = t.tex._vo
          local x1, y1, x2, y2 = vo[1] - 0.5, vo[2] + 0.5, vo[3] - 0.5, vo[4] - 0.5
          local x3, y3, x4, y4 = vo[5] + 0.5, vo[6] + 0.5, vo[7] + 0.5, vo[8] - 0.5
          if sx >= math.min(x1,x2,x3,x4) and sx <= math.max(x1,x2,x3,x4) and sy >= math.min(y1,y2,y3,y4) and sy <= math.max(y1,y2,y3,y4) then
            local function inside(ax, ay, bx, by, qx, qy)
              local den = (by-qy)*(ax-qx) + (qx-bx)*(ay-qy)
              if den == 0 then return false end
              local w1 = ((by-qy)*(sx-qx) + (qx-bx)*(sy-qy)) / den
              local w2 = ((qy-ay)*(sx-qx) + (ax-qx)*(sy-qy)) / den
              return w1 >= -1e-6 and w2 >= -1e-6 and 1 - w1 - w2 >= -1e-6
            end
            if inside(x1, y1, x2, y2, x4, y4) or inside(x1, y1, x4, y4, x3, y3) then
              local a, b, c = t.a, t.b, t.c
              local e1x, e1y, e1z = vx[b]-vx[a], vy[b]-vy[a], vh[b]-vh[a]
              local e2x, e2y, e2z = vx[c]-vx[a], vy[c]-vy[a], vh[c]-vh[a]
              local nx, ny, nz = e1y*e2z - e1z*e2y, e1z*e2x - e1x*e2z, e1x*e2y - e1y*e2x
              local den = nx*rdx + ny*rdy + nz*rdz
              if den ~= 0 then
                local d = (nx*(vx[a]-cx) + ny*(vy[a]-cy) + nz*(vh[a]-cz)) / den
                if d > 0 then
                  if d < best then best = d end
                  if t.bucket > topB or (t.bucket == topB and d < topD) then topB, topD = t.bucket, d end
                end
              end
            end
          end
        end end
      end
      local wrongTop = topD and topD > best * 1.15 + 5
      if wrongTop then ORDERW = ORDERW + 1 end
      if isNear and (best == math.huge or best > dTrue * 1.15 + 15 or wrongTop) then
        NEARW = NEARW + 1
        if best == math.huge then NEARH = NEARH + 1 elseif best > dTrue * 1.15 + 15 then NEARS = NEARS + 1 else NEARO = NEARO + 1 end
        if best ~= math.huge and best > dTrue * 1.15 + 15 then SEED = SEED .. string.format('%d:%d:%.0f:%.0f ', i, j, dTrue, best) end
      end
      if best == math.huge then holes = holes + 1; ROWS[j] = (ROWS[j] or '') .. 'H'
      elseif best > dTrue * 1.15 + 15 then seeThrough = seeThrough + 1; ROWS[j] = (ROWS[j] or '') .. 'S' end
    end
  end end
  return cz, ns.GroundHeight(cx, cy), drawn, ground, holes, seeThrough, ns.Lift(), ns.stats.behind
end
''')
peaks = [('Redridge', 18607, -25627), ('Dun Morogh', 18057, -21867)]
rows = []
t0 = time.time()
cam = ns.cam
import math
for name, px, py in peaks:
    lo = min((ns.GroundHeight(px + i, py + j), px + i, py + j) for i in range(-700, 701, 50) for j in range(-700, 701, 50) if ns.GroundHeight(px + i, py + j) > 1)
    for r in (0, 200, 400):
        for dirn in ((0, 1), (1, 0), (0, -1), (-1, 0)) if r else ((0, 0),):
            ox, oy = px + dirn[0] * r, py + dirn[1] * r
            for yaw in (0, 90, 180, 270):
                for pitch in (30, 45):
                    for dist in (40, 120, 300):
                        for mode in ('const', 'onground'):
                            cam.map = 0; cam.yaw = yaw; cam.pitch = pitch; cam.dist = dist
                            cam.x, cam.y = ox, oy
                            cam.th = lo[0] if mode == 'const' else ns.GroundHeight(ox, oy)
                            ns.Render(); ns.Render()
                            for _ in range(30):
                                if not ns.stats.detailPending: break
                                ns.Render()
                            cz, gnd, drawn, nground, holes, see, lift, behind = L.globals().DIAG(24, 15)
                            rowh = {j: G.ROWS[j] for j in range(15) if G.ROWS[j]}
                            rows.append(dict(nearh=G.NEARH, nears=G.NEARS, nearo=G.NEARO, seed=G.SEED, orderw=G.ORDERW, nearw=G.NEARW, nearn=G.NEARN, rowh=rowh, peak=name, r=r, dir=dirn, yaw=yaw, pitch=pitch, dist=dist, mode=mode, eye=cz, ground=gnd, drawn=drawn, n=nground, holes=holes, see=see, lift=lift, behind=behind))
print('near wrong: holes', sum(r['nearh'] for r in rows), 'see-through', sum(r['nears'] for r in rows), 'order', sum(r['nearo'] for r in rows))
print('draw-order errors (a farther surface drawn on top)', sum(r['orderw'] for r in rows))
print('near (<150 yd) samples', sum(r['nearn'] for r in rows), 'wrong', sum(r['nearw'] for r in rows), 'views with >10% of near samples wrong', sum(1 for r in rows if r['nearn'] and r['nearw'] / r['nearn'] > 0.1))
print('views', len(rows), 'in', round(time.time() - t0), 's')
json.dump(rows, open(os.environ.get('OUT', 'diag_tilt.json'), 'w'))
bad_in = [r for r in rows if r['drawn'] > r['eye']]
bad_h = [r for r in rows if r['n'] and (r['holes'] + r['see']) / r['n'] > 0.05]
print('eye below the drawn mesh:', len(bad_in), 'of', len(rows))
print('views with >5% wrong samples (hole or see-through):', len(bad_h))
print('total samples on ground', sum(r['n'] for r in rows), 'holes', sum(r['holes'] for r in rows), 'see-through', sum(r['see'] for r in rows))
for r in sorted(rows, key=lambda r: -(r['holes'] + r['see']) / max(1, r['n']))[:12]:
    print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()})
