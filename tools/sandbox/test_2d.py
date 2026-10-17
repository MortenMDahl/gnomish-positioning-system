# Checks the 2D map's own logic on the sandbox engine (Lua 5.4): zoom keeps the point under the
# cursor, the live minimap tiles start exactly at LIVE_MIN_SCALE, your arrow sits on your position,
# a map fits its main land, the map follows you onto another continent, and following moves the map
# every frame (not on the 0.2 s text timer). Usage: python test_2d.py   (fill site/addons first)
import lupa.lua54 as lupa54, os
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
for f in toc_files(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc')):
    if not G.SANDBOX_LOAD('GnomishPositioningSystem', f, open(f'{SITE}/addons/GnomishPositioningSystem/{f}').read()): print('LOAD FAILED', f)
G.SANDBOX_LOADED('GnomishPositioningSystem')
W, H = 1280, 800
def tick(n=1, dt=1 / 60):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
errors = []
def chat():
    c = G.SANDBOX_CHAT()
    if c:
        print('CHAT>', c.replace('\n', '\nCHAT> '))
        errors.extend(l for l in c.split('\n') if 'Lua error' in l)
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
TILE = 1600 / 3
def place(X, Y, m=0, facing=0.3):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, 'Zone', 'Subzone', 1429, 0.5, 0.5)

place(-8958.3, -190)
G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False)
ns = G.SANDBOX.namespaces['GnomishPositioningSystem']
ns.db.mode = '2D'
G.GPS_Toggle(); tick(5); chat()
view, canvas, arrow = ns.view, ns.canvas, ns.arrow

# zoom around the cursor: the grid point under it stays there
view.follow = False
ns.ShowMap(0, True); view.cx, view.cy, view.scale = 32.0, 48.0, 128; ns.Layout()
worst = 0
for px, py, f in ((100, 80, 1.25), (700, 500, 0.8), (450, 300, 1.25), (20, 590, 0.8)):
    g0 = tuple(ns.ScreenToGrid(px, py))
    ns.ZoomAt(px, py, f)
    g1 = tuple(ns.ScreenToGrid(px, py))
    worst = max(worst, abs(g1[0] - g0[0]), abs(g1[1] - g0[1]))
check('zoom keeps the grid point under the cursor (4 zooms in and out)', worst < 1e-9, f'worst drift {worst:.2e} tiles')

# live minimap tiles appear exactly at LIVE_MIN_SCALE px per tile
LIVE = ns.LIVE_MIN_SCALE
def live_count():
    return sum(1 for _ in ns.liveTiles.keys())
view.scale = LIVE - 0.01; ns.Layout(); below = live_count()
view.scale = LIVE; ns.Layout(); at = live_count()
check(f'live minimap tiles only from {LIVE} px per tile', below == 0 and at > 0, f'{below} below, {at} at')

# your arrow at your position
view.follow = True; ns.FollowPlayer(); tick(2)
mapID, gx, gy, facing = ns.PlayerPosition()[0:4]
pt = list(arrow.GetPoint(arrow, 1))
sx, sy = ns.GridToScreen(gx, gy)
check('the arrow sits on your grid position and turns with you', arrow.IsShown(arrow) and pt[2] == 'TOPLEFT' and abs(pt[3] - sx) < 1e-9 and abs(pt[4] + sy) < 1e-9 and abs(arrow.GetRotation(arrow) - facing) < 1e-12, f'{pt[3]:.2f},{pt[4]:.2f} vs {sx:.2f},{-sy:.2f}')

# a map fits its main land (Kalimdor has a small test area far from it)
view.follow = False
ns.ShowMap(1)
m = ns.Maps[1]
cx, cy = (m.fitMinX + m.fitMaxX + 1) / 2, (m.fitMinY + m.fitMaxY + 1) / 2
cw, ch = canvas.GetSize(canvas)
want = min(cw / (m.fitMaxX - m.fitMinX + 1), ch / (m.fitMaxY - m.fitMinY + 1))
check('Kalimdor fits its main land (fit box, not the far test area)', abs(view.cx - cx) < 1e-9 and abs(view.cy - cy) < 1e-9 and abs(view.scale - want) < 1e-9 and (m.minX < m.fitMinX or m.minY < m.fitMinY),
      f'centre {view.cx},{view.cy} scale {view.scale:.2f}; bounds {m.minX}..{m.maxX} x {m.minY}..{m.maxY}')

# following you onto another continent (audit finding 2)
place(-8958.3, -190, 0); ns.FollowPlayer(); tick(3)
place(1630, -4380, 1)  # Orgrimmar
tick(1)
mapID, gx, gy = ns.PlayerPosition()[0:3]
check('following you onto another continent: the map goes with you, arrow shown', view.map == 1 and abs(view.cx - gx) < 1e-9 and abs(view.cy - gy) < 1e-9 and arrow.IsShown(arrow), f'view map {view.map}, arrow {arrow.IsShown(arrow)}')
view.follow = False
place(-8958.3, -190, 0); tick(2)
check('not following: the map stays where you were looking (arrow hidden on the other map)', view.map == 1 and not arrow.IsShown(arrow))

# following moves the map every frame (audit finding 11), not every 0.2 s
ns.FollowPlayer(); tick(3)
G.SANDBOX_CHAT()
moves = 0
for k in range(6):
    place(-8958.3 + k * 0.4, -190)
    tick(1, 1 / 60)
    g = ns.PlayerPosition()
    if abs(view.cx - g[1]) < 1e-9 and abs(view.cy - g[2]) < 1e-9: moves += 1
check('following: the map is centred on you after every single frame', moves == 6, f'{moves} of 6 frames')

chat()
check('no Lua errors', not errors, '; '.join(errors[:2]))
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
