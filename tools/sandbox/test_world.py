# Runs engine + both addons (Lua 5.4, as in the sandbox) and checks the whole-world 3D view in many places.
import lupa.lua54 as lupa54, math, time, os, sys
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
toc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
t0 = time.time()
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua']), ('GPS3D', gps3d_files)]:
    for f in files:
        ok = G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read())
        if not ok: print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
print('load s', round(time.time() - t0, 2))
G.SANDBOX_FIRE('PLAYER_LOGIN')
TILE = 1600 / 3
W, H = 1280, 800
def chat():
    c = G.SANDBOX_CHAT()
    if c: print('CHAT>', c.replace('\n', '\nCHAT> '))
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
def place(X, Y, m, facing=0.0, zone='', sub=''):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, zone, sub, -1, -1, -1)
ns2 = G.SANDBOX.namespaces['GPS3D']
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

place(-8958.3, -190, 0, 0.3, 'Elwynn Forest', 'Northshire Valley')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(30); chat()
st, cam, pl = ns2.stats, ns2.cam, ns2.player
check('opens following you in Northshire', ns2.CamMode() == 'follow' and cam.map == 0 and abs(cam.x - pl.x) < 1e-6, f'mode {ns2.CamMode()} map {cam.map}')
check('opens looking straight down by default (nothing saved yet)', ns2.IsTopDown() and abs(cam.pitch - 89.9) < 1e-9 and G.GPS3D_DB.topDown == True, f'pitch {cam.pitch:.2f}')
# First zoom-out over a continent (audit finding 3): no decoded heights are kept.
gcount = L.eval('function() collectgarbage("collect"); collectgarbage("collect"); return collectgarbage("count") end')
saved = (cam.map, cam.x, cam.y, cam.dist)
ns2.SetCamMode('free')
for mp, gx, gy in ((0, 32, 40), (1, 40, 30)):
    cam.map, cam.x, cam.y, cam.dist = mp, gx * TILE, -gy * TILE, 4500
    m0 = gcount(); t0 = time.perf_counter(); ns2.Render(); dt = (time.perf_counter() - t0) * 1000; m1 = gcount()
    check(f'zoomed out over map {mp} for the first time: little memory kept (decoded heights took +20-28 MB before)', (m1 - m0) / 1024 < 6, f'+{(m1 - m0) / 1024:.1f} MB, first frame {dt:.0f} ms, {int(st.tiles)} tiles')

cam.map, cam.x, cam.y, cam.dist = saved
ns2.FollowMe('follow'); tick(40)

G.SlashCmdList.GPS3D('top'); tick(30)  # the checks below were written for the tilted view
check('/gps3d top turns it off and back to the tilted view', not ns2.IsTopDown() and abs(cam.pitch - 45) < 1e-6 and G.GPS3D_DB.topDown == False, f'pitch {cam.pitch:.2f} saved {G.GPS3D_DB.topDown}')
check('Northshire: buildings drawn close up, within budget', st.detail > 0 and 0 < st.detailTris <= 4000, f'blocks {st.detail} building tris {st.detailTris} grid tris {st.tris} shown {st.shown}')
places = [
    ('Goldshire', -9464, 62, 0), ('Westfall, Sentinel Hill', -10628, 1037, 0), ('Ironforge gates (approx.)', -5000, -830, 0),
    ('Booty Bay (approx.)', -14300, 440, 0), ('Orgrimmar (approx.)', 1630, -4380, 1), ('Crossroads (approx.)', -450, -2650, 1),
    ('Bloodhoof Village (approx.)', -2350, -350, 1), ('Teldrassil (approx.)', 9940, 2290, 1),
    ('Stormwind, Trade District', -8830, 640, 0), ('Stormwind, cathedral', -8520, 850, 0), ('Undercity ruins (Lordaeron)', 1800, 230, 0),
    ('Stratholme (outside)', 3300, -3380, 0), ('Thunder Bluff', -1280, 130, 1), ('Darnassus', 9950, 2280, 1),
]
BUILDINGS = []
for name, X, Y, m in places:
    place(X, Y, m, 1.0, name)
    tick(30)
    ns2.Render()  # first frame builds the meshes; measure the next ones (turning the view)
    yaw0 = cam.yaw
    t = time.time()
    for k in range(10):
        cam.yaw = cam.yaw + 3; ns2.Render()
    ms = (time.time() - t) * 1000 / 10
    cam.yaw = yaw0; ns2.Render()
    hist = {int(k): int(v) for k, v in st.steps.items()}
    ok = pl.on and cam.map == m and abs(cam.x - pl.x) < 1e-6 and st.shown > 100 and st.tris <= 3200 and st.detailTris <= 4000
    BUILDINGS.append((name, int(st.detail), int(st.detailTris), int(st.detailSkipped), ms, float(st.detailReach), [int(st.detailLevels[k]) for k in (1, 2, 3)]))
    check(f'{name}: view follows you, terrain drawn', ok, f'map {cam.map} tiles {st.tiles} grid tris {st.tris} buildings {st.detail} blocks/{st.detailTris} tris (skipped {st.detailSkipped}) shown {st.shown} h {pl.h:.1f} render {ms:.1f} ms (native Lua) steps {hist}')
print('reach', [(b[0], round(b[5]), b[6]) for b in BUILDINGS])
check('buildings load further: blocks drawn beyond 400 yd from the view centre in some places, far level used', max(b[5] for b in BUILDINGS) > 400 and sum(b[6][2] for b in BUILDINGS) > 0, f'max reach {max(b[5] for b in BUILDINGS):.0f} yd')
check('buildings drawn in the cities', all(b[1] > 0 for b in BUILDINGS if b[0].startswith(('Stormwind', 'Orgrimmar', 'Undercity', 'Thunder', 'Booty', 'Darnassus'))), str([(b[0], b[1]) for b in BUILDINGS]))
# continent views from far away
for m, name in [(0, 'Eastern Kingdoms'), (1, 'Kalimdor')]:
    place(-8958.3 if m == 0 else 1630, -190 if m == 0 else -4380, m)
    tick(10)
    G.SlashCmdList.GPS3D('')  # close
    G.SlashCmdList.GPS3D('')  # open
    tick(5)
    ns2.SetCamMode('free')
    cam.dist, cam.pitch = 12000, 55
    t = time.time(); ns2.Render(); ms0 = (time.time() - t) * 1000
    cam.yaw = cam.yaw + 10
    t = time.time(); ns2.Render(); ms = (time.time() - t) * 1000
    check(f'{name} from 12 km up: drawn within budget', st.shown > 300 and st.tris <= 3200, f'tiles {st.tiles} tris {st.tris} shown {st.shown} render first {ms0:.0f} ms, then {ms:.0f} ms')
    cam.dist, cam.pitch = 330, 32
# no data map (Zephras) and no position
place((32 - 29.5) * TILE, (32 - 25.5) * TILE, 2991)
tick(10)
check('map without terrain: says so', not pl.on and 'No 3D terrain' in str(ns2.ui.footer._text), str(ns2.ui.footer._text))
G.SANDBOX_PLAYER(0, 0, 0, -1, 0, '', '', -1, -1, -1); tick(5)
check('no position: says so', not pl.on and 'not available' in str(ns2.ui.footer._text), str(ns2.ui.footer._text))
# heights: grid vs data decode
place(-9464, 62, 0); tick(10)
gh = ns2.GroundHeight(pl.x, pl.y, 0)
check('ground height at Goldshire is plausible (40..80 yd)', 40 < gh < 80, f'{gh:.1f}')
# caves and mines (underground WMOs, scripts/browser_underground.js) keep their exterior groups (the rock
# around the entrance) and with them the building mesh's fine ground there; their tunnels and rooms are
# left out by the export (checked against the game files there). The ruins over the Undercity still stand.
def block_at(gx, gy):
    tx, ty = int(gx), int(gy)
    tb = ns2.TileBlocks(0, tx, ty)
    bi = int((gy - ty) * 8) * 8 + int((gx - tx) * 8)
    return tb is not None and tb[bi] is not None
def raised(gx, gy, r):
    cx, cy, n, up, worst = gx * TILE, -gy * TILE, 0, 0, 0.0
    for i in range(-r, r + 1, 3):
        for j in range(-r, r + 1, 3):
            if i * i + j * j > r * r: continue
            g0, b0 = ns2.GridHeight(0, cx + i, cy + j), ns2.GroundHeight(cx + i, cy + j, 0)
            if g0 is None or b0 is None: continue
            n += 1
            if abs(b0 - g0) > 3: up += 1; worst = max(worst, abs(b0 - g0))
    return n, up, worst
sites = [(34.2183, 47.7690), (32.2470, 48.2117), (33.1145, 49.1650)]
caves = [(block_at(gx, gy), raised(gx, gy, 45)) for gx, gy in sites]
ruins = raised(31.55, 28.91, 120)
check('caves and mines keep their outside rock and the fine ground around them (the cave east of Northshire and two mines in Elwynn Forest have building blocks); the ruins over the Undercity still stand',
      all(has and r[1] > 100 for has, r in caves) and ruins[1] > 1000, f'blocks {[c[0] for c in caves]}, points off the 16.7-yd grid by > 3 yd {[c[1][1] for c in caves]} of {[c[1][0] for c in caves]}; Undercity {ruins[1]} of {ruins[0]}, up to {ruins[2]:.0f} yd')
# seams: neighbouring tiles with different steps share edge heights
L.execute('''
function SEAMCHECK()
  local ns = SANDBOX.namespaces.GPS3D
  local worst, pairs_ = 0, 0
  -- edges between active grid meshes: compare world-space height along shared edges
  local byTile = {}
  for _, t in ipairs(ns.stats.visible) do local m = t.mesh; if m and not m.detail then byTile[m.ty * 64 + m.tx] = m end end
  local function heightAt(m, x, y)
    -- piecewise-linear along the mesh edge
    local s, n = m.step, m.n
    local x0, y0 = m.tx * 1600 / 3, -m.ty * 1600 / 3
    local cell = (1600 / 3) / 32 * s
    local fi, fj = (x - x0) / cell, (y0 - y) / cell
    local i, j = math.floor(fi + 1e-9), math.floor(fj + 1e-9)
    if i >= n then i = n - 1 end
    if j >= n then j = n - 1 end
    local u, v = fi - i, fj - j
    local row = n + 1
    local h00, h10, h01, h11 = m.vh[j * row + i + 1], m.vh[j * row + i + 2], m.vh[(j + 1) * row + i + 1], m.vh[(j + 1) * row + i + 2]
    if u >= v then return h00 + (h10 - h00) * u + (h11 - h10) * v end
    return h00 + (h11 - h01) * u + (h01 - h00) * v
  end
  for key, m in pairs(byTile) do
    local e = byTile[key + 1]
    if e then
      pairs_ = pairs_ + 1
      local x = (m.tx + 1) * 1600 / 3
      for k = 0, 64 do
        local y = -m.ty * 1600 / 3 - k * (1600 / 3) / 64
        worst = math.max(worst, math.abs(heightAt(m, x - 1e-6, y) - heightAt(e, x + 1e-6, y)))
      end
    end
  end
  return worst, pairs_
end''')
cam.dist, cam.pitch = 1500, 30
ns2.Render()
worst, npairs = G.SEAMCHECK()
check('no cracks: shared tile edges have equal heights', worst < 1e-3 and npairs > 0, f'{npairs} edges, worst {worst:.2e} yd')

# ---- controls and marker (same checks as before, now anywhere in the world): Goldshire
place(-9464, 62, 0, 0.7, 'Elwynn Forest', 'Goldshire'); tick(5)
G.SlashCmdList.GPS3D(''); G.SlashCmdList.GPS3D(''); tick(30)
cv = ns2.canvas
l, b, r, t = G.SANDBOX.rect(cv)
CX, CY = (l + r) / 2, (b + t) / 2
def mouse(kind, px, py, btn='', d=0): G.SANDBOX_MOUSE(kind, CX + px, CY + py, btn, d)
check('Goldshire: follows you', ns2.CamMode() in ('follow', 'behind') and abs(cam.x - pl.x) < 1e-6)
# decal corners = projection
corners = ns2.DecalCorners(); dec = ns2.decal; worst = 0
off = {1: (-0.5, 0.5), 2: (-0.5, -0.5), 3: (0.5, 0.5), 4: (0.5, -0.5)}
for k in (1, 2, 3, 4):
    c = corners[k]; sx, sy, _ = ns2.Project(c[1], c[2], c[3])
    vo = dec._vo; worst = max(worst, abs(vo[k * 2 - 1] + off[k][0] - sx), abs(vo[k * 2] + off[k][1] - sy))
check('arrow corners = projection of its ground corners', dec._shown and worst < 1e-6, f'{worst:.1e} px')
actor = [a for a in ns2.scene._actors.values() if a._model == 'unit:player'][0]
check('character model at your position', abs(actor._pos[1] - pl.x) < 1e-9 and abs(actor._pos[2] - pl.y) < 1e-9 and abs(actor._pos[3] - pl.h) < 1e-9)
# grab-pan
mouse('move', 120, -60)
g0 = ns2.ScreenToTerrain(120, -60)  # the real ground point under the cursor
mouse('down', 120, -60, 'LeftButton')
for k in range(1, 9): mouse('move', 120 + k * 15, -60 + k * 10); tick(1)
g1 = ns2.ScreenToTerrain(120 + 8 * 15, -60 + 8 * 10)
mouse('up', 240, 20, 'LeftButton'); tick(10)
check('left drag: grabbed ground stays under the cursor; switches to Free', abs(g0[0] - g1[0]) < 0.05 and abs(g0[1] - g1[1]) < 0.05 and ns2.CamMode() == 'free', f'{g0[0]:.2f},{g0[1]:.2f} vs {g1[0]:.2f},{g1[1]:.2f}')
# wheel toward cursor
mouse('move', -150, -80); before = ns2.ScreenToTerrain(-150, -80)
mouse('wheel', -150, -80, '', 1); after = ns2.ScreenToTerrain(-150, -80)
check('wheel (Free): ground under the cursor stays put', abs(before[0] - after[0]) < 0.05 and abs(before[1] - after[1]) < 0.05, f'{before[0]:.3f},{before[1]:.3f} vs {after[0]:.3f},{after[1]:.3f}')
# pan across a tile border and keep going: new tiles appear, nothing breaks
x_start, y_start = cam.x, cam.y
for k in range(12):
    mouse('down', 0, 0, 'LeftButton'); mouse('move', -200, 0); tick(1); mouse('up', -200, 0, 'LeftButton'); tick(1)
moved = math.hypot(cam.x - x_start, cam.y - y_start)
check('dragging far across tile borders works', moved > 1000 and st.shown > 100, f'moved {moved:.0f} yd ({cam.x - x_start:.0f} east), {st.tiles} tiles drawn')
# Behind
ns2.FollowMe('behind'); tick(40)
want = (-math.degrees(pl.facing)) % 360
check('Behind: view looks the way you face', ns2.CamMode() == 'behind' and abs(((cam.yaw - want + 540) % 360) - 180) < 1e-3 and abs(cam.x - pl.x) < 1e-6, f'yaw {cam.yaw:.2f} want {want:.2f}')
# ---- tilt limits (right drag) and the 90-degree lock
ns2.SetCamMode('free'); tick(2)
def rdrag(dx, dy, n=10):
    mouse('move', 0, 0); mouse('down', 0, 0, 'RightButton')
    for k in range(1, n + 1): mouse('move', dx * k / n, dy * k / n); tick(1)
    mouse('up', dx, dy, 'RightButton'); tick(1)
rdrag(0, 600)    # drag down a lot: tilt toward the horizon
low_p = cam.pitch
rdrag(0, -900)   # drag up a lot: toward straight down
high_p = cam.pitch
check('tilt limited to 45..90 degrees (at most 45 from straight down)', abs(low_p - 45) < 1e-9 and abs(high_p - 89.9) < 1e-9, f'lowest {low_p:.2f}, highest {high_p:.2f}')
rdrag(0, 200); before = cam.pitch
tb = ns2.topButton
tb._scripts.OnClick(tb); tick(30)
yaw0 = cam.yaw
rdrag(150, 300)
check('90 ring: straight down, locked (drag only turns), ring gold, remembered',
      abs(cam.pitch - 89.9) < 1e-9 and ns2.IsTopDown() and abs(cam.yaw - yaw0) > 10 and tb.active == True and G.GPS3D_DB.topDown == True,
      f'pitch {cam.pitch:.2f} yaw {yaw0:.0f}->{cam.yaw:.0f} saved {G.GPS3D_DB.topDown}')
ns2.Render()
check('straight down: terrain drawn', st.shown > 100, f'shown {st.shown}')
G.SlashCmdList.GPS3D(''); G.SlashCmdList.GPS3D(''); tick(5)
check('90 lock kept when the window opens again', ns2.IsTopDown() and abs(cam.pitch - 89.9) < 1e-9, f'pitch {cam.pitch:.2f}')
tb._scripts.OnClick(tb); tick(30)
check('90 button again: tilt free, back to the earlier tilt, remembered as off', not ns2.IsTopDown() and abs(cam.pitch - before) < 1e-6 and G.GPS3D_DB.topDown == False, f'pitch {cam.pitch:.2f} (before {before:.2f})')
G.SlashCmdList.GPS3D(''); G.SlashCmdList.GPS3D(''); tick(5)
check('turned off stays off when the window opens again', not ns2.IsTopDown(), f'pitch {cam.pitch:.2f}')
# switching back to 2D looks at the same place when free
ns2.SetCamMode('free')
mouse('down', 0, 0, 'LeftButton'); mouse('move', -300, 0); tick(1); mouse('up', -300, 0, 'LeftButton'); tick(5)
gx3, gy3 = cam.x / TILE, -cam.y / TILE
ns2.ui.modeSwitch._scripts.OnClick(ns2.ui.modeSwitch, 'RightButton'); tick(3)  # the mode ring, back one: 3D -> 2D
v = G.SANDBOX.namespaces['GnomishPositioningSystem'].view
check('3D -> 2D (Free): the map shows where the 3D view looked', G.GPS_MapFrame.IsShown(G.GPS_MapFrame) and abs(v.cx - gx3) < 1e-6 and abs(v.cy - gy3) < 1e-6 and not v.follow, f'{v.cx:.3f},{v.cy:.3f} vs {gx3:.3f},{gy3:.3f}')
ns1 = G.SANDBOX.namespaces['GnomishPositioningSystem']
v.cx, v.cy = 40.2, 30.5; v.map = 1
ns1.ui.modeSwitch._scripts.OnClick(ns1.ui.modeSwitch); tick(5)
check('2D -> 3D (not following): the 3D view opens where the map looked', cam.map == 1 and abs(cam.x / TILE - 40.2) < 1e-6 and abs(-cam.y / TILE - 30.5) < 1e-6, f'map {cam.map} {cam.x / TILE:.2f},{-cam.y / TILE:.2f}')

# ---- constant camera height; zooming in stops at the ground (2026-10-15)
CLEAR = 8
def eye():
    b = ns2.CameraBasis(); return b[8], b[9], b[10]
def clearance():
    ex, ey, ez = eye(); return ez - ns2.GroundHeight(ex, ey)
def scan(cx, cy, half, step):
    best_hi = best_lo = None
    for i in range(-half, half + 1, step):
        for j in range(-half, half + 1, step):
            h = ns2.GroundHeight(cx + i, cy + j)
            if best_hi is None or h > best_hi[2]: best_hi = (cx + i, cy + j, h)
            if h > 1 and (best_lo is None or h < best_lo[2]): best_lo = (cx + i, cy + j, h)
    return best_hi, best_lo
place(-5000, -830, 0, 0.0, 'Dun Morogh', ''); tick(3)
ns2.SetCamMode('free'); tick(1)
cam.map = 0
P, V = scan(pl.x, pl.y, 1200, 40)
print('mountain', [round(v) for v in P], 'valley', [round(v) for v in V])
ns2.SetTopDown(True, True)
D = max(60, (P[2] - V[2]) - 60)
cam.x, cam.y, cam.th, cam.dist = V[0], V[1], V[2], D; ns2.Render()
th0 = cam.th; e0 = eye()[2]
# a real drag in the valley: altitude kept after the mouse is let go (it used to settle onto the ground there)
mouse('move', 0, 0); mouse('down', 0, 0, 'LeftButton')
for k in range(1, 9): mouse('move', k * 20, k * 12); tick(1)
mouse('up', 160, 96, 'LeftButton'); tick(15)
check('pan: altitude kept (orbit height and camera height unchanged after a drag)', cam.th == th0 and abs(eye()[2] - e0) < 1e-6, f'th {th0:.1f} -> {cam.th:.1f}, eye {e0:.1f} -> {eye()[2]:.1f}')
cam.x, cam.y = V[0], V[1]; ns2.Render(); e0 = eye()[2]
cam.x, cam.y = P[0], P[1]; ns2.Render()   # panned onto the mountain (a pan only moves x, y)
ep = eye()[2]; cp = clearance()
check('pan over a mountain: camera lifted only as far as needed', cam.th == th0 and ep > e0 and cp >= CLEAR - 1e-6 and ns2.Lift() > 0, f'peak {P[2]:.0f}, chosen eye {e0:.0f}, eye there {ep:.1f} ({cp:.1f} yd above the ground)')
cam.x, cam.y = V[0], V[1]; ns2.Render()
check('...and back down to the chosen height after it', abs(eye()[2] - e0) < 1e-6, f'eye {eye()[2]:.1f} (chosen {e0:.1f})')
# zooming in on the peak, at the centre and toward the cursor: stops above the ground
cam.x, cam.y = P[0], P[1]; ns2.Render()
worst = 1e9; dists = []
for k in range(40):
    mouse('move', (k % 5 - 2) * 60, (k % 3 - 1) * 50); mouse('wheel', (k % 5 - 2) * 60, (k % 3 - 1) * 50, '', 1)
    worst = min(worst, clearance()); dists.append(cam.dist)
d_in = cam.dist
for k in range(5): mouse('wheel', 0, 0, '', -1)
check('zoom in on a peak stops at the ground (never inside it); zoom out works', worst >= CLEAR - 0.5 and cam.dist > d_in * 2, f'lowest {worst:.2f} yd above the ground over 40 zoom steps; dist {D:.0f} -> {d_in:.1f} -> {cam.dist:.1f}')
# tilted, toward a slope
ns2.SetTopDown(False, True); cam.pitch = 30; cam.x, cam.y, cam.th, cam.dist = P[0], P[1], P[2], 400; ns2.Render()
worst = 1e9
for k in range(40):
    mouse('move', 80, -120); mouse('wheel', 80, -120, '', 1); worst = min(worst, clearance())
check('tilted 30 deg, zooming toward a slope: never inside the ground', worst >= CLEAR - 0.5, f'lowest {worst:.2f} yd, dist now {cam.dist:.1f}')
# a roof: Stormwind cathedral
place(-8520, 850, 0, 0.0, 'Stormwind City', 'Cathedral Square'); tick(3)
ns2.SetCamMode('free')
R, S = scan(pl.x, pl.y, 90, 3)
ns2.SetTopDown(True, True); cam.x, cam.y, cam.th, cam.dist = R[0], R[1], S[2], 300; ns2.Render()
worst = 1e9
for k in range(40):
    mouse('wheel', 0, 0, '', 1); worst = min(worst, clearance())
check('zoom onto the cathedral roof stops above the roof', worst >= CLEAR - 0.5, f'roof {R[2]:.1f} (street {S[2]:.1f}); lowest {worst:.2f} yd above it, dist {cam.dist:.1f}')
# tilted near the Redridge peaks: clear all round (25 yd), clear view ahead, no holes in front of the camera
L.execute(r"""
function SANDBOX_COVER(NX, NY, frac)
  -- share of screen samples in the lower part of the view not covered by any drawn triangle
  local ns = SANDBOX.namespaces.GPS3D
  local w, h = ns.canvas:GetSize()
  local quads, nq = {}, 0
  for _, t in ipairs(ns.stats.visible) do
    local vo = t.tex._vo
    nq = nq + 1
    quads[nq] = { vo[1] - 0.5, vo[2] + 0.5, vo[3] - 0.5, vo[4] - 0.5, vo[7] + 0.5, vo[8] - 0.5, vo[5] + 0.5, vo[6] + 0.5 }
  end
  local function inside(sx, sy, ax, ay, bx, by, qx, qy)
    local den = (by-qy)*(ax-qx) + (qx-bx)*(ay-qy)
    if den == 0 then return false end
    local w1 = ((by-qy)*(sx-qx) + (qx-bx)*(sy-qy)) / den
    local w2 = ((qy-ay)*(sx-qx) + (ax-qx)*(sy-qy)) / den
    return w1 >= -1e-6 and w2 >= -1e-6 and 1 - w1 - w2 >= -1e-6
  end
  local miss, n = 0, 0
  for i = 0, NX - 1 do for j = 0, NY - 1 do
    local sx, sy = (i + 0.5) / NX * w - w / 2, -h / 2 + (j + 0.5) / NY * h * frac
    n = n + 1
    local hit = false
    for k = 1, nq do local q = quads[k]
      if inside(sx, sy, q[1], q[2], q[3], q[4], q[5], q[6]) or inside(sx, sy, q[1], q[2], q[5], q[6], q[7], q[8]) then hit = true break end
    end
    if not hit then miss = miss + 1 end
  end end
  return miss, n
end
""")
def disc_clear():
    # distance from the camera to the nearest ground or roof point within 30 yd (2-yd grid)
    ex, ey, ez = eye(); best = 1e9
    for i in range(-30, 31, 2):
        for j in range(-30, 31, 2):
            if i * i + j * j <= 900:
                h = ns2.GroundHeight(ex + i, ey + j)
                best = min(best, math.sqrt(i * i + j * j + max(0.0, ez - h) ** 2))  # ground above the eye: at least its horizontal distance
    return best
place(-9400, -1300, 0, 0.0, 'Elwynn Forest', ''); tick(3)
ns2.SetCamMode('free'); ns2.SetTopDown(False, True)
PK = (18607, -25627)
VL = min((ns2.GroundHeight(PK[0] + i, PK[1] + j), i, j) for i in range(-700, 701, 50) for j in range(-700, 701, 50) if ns2.GroundHeight(PK[0] + i, PK[1] + j) > 1)[0]
worst_disc, worst_ahead, miss_all, n_all, cut_all, nviews = 1e9, 1e9, 0, 0, 0, 0
for (ox, oy) in ((0, 0), (300, 0), (-300, 0), (0, 300), (0, -300), (0, -400)):
    for yaw in (0, 90, 180, 270):
        for pitch, dist in ((30, 120), (45, 40), (30, 300), (60, 80)):
            cam.map = 0; cam.x, cam.y, cam.th, cam.yaw, cam.pitch, cam.dist = PK[0] + ox, PK[1] + oy, VL, yaw, pitch, dist
            ns2.Render(); ns2.Render(); nviews += 1
            worst_disc = min(worst_disc, disc_clear())
            hx, hy, hz = ns2.ScreenToTerrain(0, 0); ex, ey, ez = eye()
            want = min(1.0, 1.2 * math.cos(math.radians(pitch)) ** 2) * dist  # the clear length the rule promises
            worst_ahead = min(worst_ahead, math.dist((hx, hy, hz), (ex, ey, ez)) / want)
            m, n = G.SANDBOX_COVER(24, 6, 0.4); miss_all += m; n_all += n; cut_all += st.cut or 0
check('tilted near peaks: the camera stays about 8 yd from any ground or roof (dense check)', worst_disc >= 7.5, f'{nviews} views; nearest ground point {worst_disc:.2f} yd from the camera')
check('tilted: the middle of the view is clear of hills for the promised length (1.2 x cos^2 tilt x zoom distance)', worst_ahead >= 0.6, f'nearest hit at {worst_ahead:.2f} x that length (checked every 6 yd, so a steep slope can poke in between)')
check('no holes in the lower part of the view (triangles cut at the camera, not hidden)', miss_all == 0 and cut_all > 0, f'{miss_all} of {n_all} samples uncovered; {cut_all} cut triangles drawn')
# straight down is not affected by the view-ahead rule: it still comes down to 8 yd over flat ground
ns2.SetTopDown(True, True); cam.x, cam.y = PK[0], PK[1]; cam.th = ns2.GroundHeight(PK[0], PK[1]); cam.dist = 300; ns2.Render()
for k in range(40): mouse('wheel', 0, 0, '', 1)
check('straight down: zoom still reaches the ground (view-ahead rule off)', clearance() < 30 and clearance() >= CLEAR - 0.5, f'{clearance():.1f} yd above the ground, dist {cam.dist:.1f}')
ns2.SetTopDown(False, True)
# following: still centred on you, still at your height
place(-5000, -830, 0, 0.0, 'Dun Morogh', ''); tick(3)
ns2.FollowMe('follow'); tick(40)
for k in range(40): mouse('wheel', 0, 0, '', 1); tick(1)
check('Follow: still on you and at your height after zooming all the way in', abs(cam.x - pl.x) < 1e-6 and abs(cam.y - pl.y) < 1e-6 and abs(cam.th - pl.h) < 1e-6 and clearance() >= CLEAR - 0.5, f'dist {cam.dist:.1f}, {clearance():.2f} yd above the ground')
ns2.SetTopDown(False, True)

# Heights are read from the tile strings (audit finding 3): every height of every tile equals an
# independent decode of the string, lo and hi are its lowest and highest, and nothing is decoded ahead.
res = L.eval(r"""function()
	local B = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	local V = {}
	for i = 1, 64 do V[B:byte(i)] = i - 1 end
	local ns = SANDBOX.namespaces.GPS3D
	local tiles, bad, tails = 0, 0, 0
	for map, m in pairs(ns.World) do
		for key, s in pairs(m) do
			tiles = tiles + 1
			if #s == 3 + 33 * 33 * 2 + 2 then tails = tails + 1 end
			local base = (V[s:byte(1)] * 64 + V[s:byte(2)]) * 64 + V[s:byte(3)] - 131072
			local h = ns.TileHeights(map, key % 64, key // 64)
			local lo, hi = math.huge, -math.huge
			for i = 1, 33 * 33 do
				local v = (base + V[s:byte(i * 2 + 2)] * 64 + V[s:byte(i * 2 + 3)]) * 0.5
				if v < lo then lo = v end
				if v > hi then hi = v end
				if h[i] ~= v then bad = bad + 1 end
			end
			if h.lo ~= lo or h.hi ~= hi or rawget(h, 1) ~= nil then bad = bad + 1 end
		end
	end
	return tiles, bad, tails
end""")()
check('heights read from the strings equal a full decode, every tile (lo and hi too, no table of heights kept)', res[1] == 0 and res[0] > 2000, f'{res[0]} tiles, {res[1]} mismatches')
check('the 3D data carries each tile\'s highest height (build_world.py), all tiles', res[2] == res[0], f'{res[2]} of {res[0]}')
# One position rule for both views (finding 5): the 3D view's position is the 2D map's, swapaxes and
# flipfacing included. Your position is read every frame (finding 11).
ns1 = G.SANDBOX.namespaces['GnomishPositioningSystem']
place(-9464, 62, 0, 1.6, 'Elwynn Forest', 'Goldshire')
ns2.FollowMe('follow'); tick(40)  # the flight to you ends
def same_place():
    m, gx, gy, f = list(ns1.PlayerPosition())[0:4]
    return m == pl.map and abs(pl.x - gx * TILE) < 1e-6 and abs(pl.y + gy * TILE) < 1e-6 and abs(pl.facing - f) < 1e-12
ok = [same_place()]
G.SlashCmdList.GPS('swapaxes'); G.SlashCmdList.GPS('flipfacing'); tick(1, 1 / 60)
ok.append(same_place())
G.SlashCmdList.GPS('swapaxes'); G.SlashCmdList.GPS('flipfacing'); tick(1, 1 / 60)
ok.append(same_place())
G.SANDBOX_CHAT()
check('3D position = the 2D map\'s (GPS_API.PlayerPosition), also with /gps swapaxes and flipfacing', all(ok), str(ok))
frames = 0
for k in range(5):
    place(-9464 + k * 0.3, 62, 0, 1.6, 'Elwynn Forest', 'Goldshire'); tick(1, 1 / 60)
    if abs(pl.y + (32 - (-9464 + k * 0.3) / TILE) * TILE) < 1e-6 and abs(cam.y - pl.y) < 1e-6: frames += 1
check('following in 3D: your position and the view move every frame', frames == 5, f'{frames} of 5 frames')

G.SlashCmdList.GPS3D('test'); tick(80); chat()
print(f'\n{sum(r[1] for r in results)} of {len(results)} checks passed')
