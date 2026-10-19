# Checks the 2D map's own logic on the sandbox engine (Lua 5.4): zoom keeps the point under the
# cursor, the live minimap tiles start exactly at LIVE_MIN_SCALE, your arrow sits on your position,
# a map fits its main land, the map follows you onto another continent, and following moves the map
# every frame (not on the 0.2 s text timer). Usage: python test_2d.py   (fill site/addons first)
import lupa.lua54 as lupa54, os, sys, subprocess
# each mutation breaks one piece of the world view (both continents side by side) and must make a check fail
MUTANTS = [
    ('the other continent is not drawn', '\t\t\tif p ~= view.map and Maps[p] then LayoutPeer(p, w, h, wanted); peerShown[p] = true end', '\t\t\tif false then LayoutPeer(p, w, h, wanted); peerShown[p] = true end'),
    ('the other continent drawn without the world map\'s scale', 'PlaceRegion(t, gx, gy, a.cols * kx, a.rows * ky)', 'PlaceRegion(t, gx, gy, a.cols, a.rows)'),
    ('panning onto the other continent keeps the old map', '\t\t\tns.WorldSwitch()\n\t\t\tns.Layout()', '\t\t\tns.Layout()'),
    ('the map switch moves the view (scale not converted)', '\tview.scale = view.scale * L[m].ax / L[view.map].ax\n', ''),
    ('no minimap tiles of the other continent close up', '\tif view.scale >= LIVE_MIN_SCALE then\n\t\tlocal x0, y0 = ns.WorldGridOn', '\tif false then\n\t\tlocal x0, y0 = ns.WorldGridOn'),
]
mutant = MUTANTS[int(sys.argv[sys.argv.index('--mutant') + 1])] if '--mutant' in sys.argv else None
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
    src = open(f'{SITE}/addons/GnomishPositioningSystem/{f}').read()
    if mutant and f == 'Core.lua':
        assert src.count(mutant[1]) == 1, ('mutation text not found once', mutant[0])
        src = src.replace(mutant[1], mutant[2])
    if not G.SANDBOX_LOAD('GnomishPositioningSystem', f, src): print('LOAD FAILED', f)
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
    results.append((name, bool(ok)))
    if not mutant: print(('PASS' if ok else 'FAIL'), name, detail)
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
# (since 2026-10-19 the two continents lie side by side on the 2D map, as on Blizzard's world map: your arrow
# on the other continent is shown at your place round this one)
_, pgx, pgy = ns.PlayerPosition()[0:3]
wx, wy = ns.WorldGridOn(0, pgx, pgy, 1)
sx, sy = ns.GridToScreen(wx, wy)
pt = arrow.GetPoint(arrow, 1)
check('not following: the map stays where you were looking, your arrow at your place on the other continent of the world map', view.map == 1 and arrow.IsShown(arrow) and abs(pt[3] - sx) < 1e-6 and abs(pt[4] + sy) < 1e-6, f'map {view.map}, arrow at {pt[3]:.1f},{pt[4]:.1f} vs {sx:.1f},{-sy:.1f}')

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

# ---- both continents side by side, as on Blizzard's world map (2026-10-19) ----
WL = ns.WorldLayout
view.follow = False; ns.db.follow = False
def peer_first(p):
    pl = ns.peerAtlasOf(p)
    return pl[1] if pl else None
def tl(t):
    p = t.GetPoint(t, 1); return p[3], -p[4]  # canvas top-left offset, y down
def size(t): return t.GetWidth(t), t.GetHeight(t)
# zoomed out over the Eastern Kingdoms: Kalimdor's overview images too, each where the world map puts it
ns.ShowMap(0, True)
e0, e1 = WL[0], WL[1]
kx_, ky_ = ns.WorldGridOn(1, e1.tx1 + 1, (e1.ty0 + e1.ty1) / 2, 0)  # Kalimdor's east edge, in the Eastern Kingdoms' grid
view.cx, view.cy = (kx_ + e0.tx0) / 2, ky_  # the sea between the two
view.scale = 6; ns.Layout()
k1 = G.GPS_API.Maps[1]
worst, shown = 0, 0
pl = ns.peerAtlasOf(1)
for i in range(1, len(k1.atlases) + 1):
    t = pl[i] if pl else None
    if not t: worst = 1e9; continue
    a = t.atlas
    if t.IsShown(t): shown += 1
    gx, gy = ns.WorldGridOn(1, a.x0, a.y0, 0)
    want = ns.GridToScreen(gx, gy)
    got = tl(t)
    w, h = size(t)
    worst = max(worst, abs(got[0] - want[0]), abs(got[1] - want[1]), abs(w - a.cols * view.scale * e1.ax / e0.ax), abs(h - a.rows * view.scale * e1.ay / e0.ay))
own = sum(1 for i in range(1, len(G.GPS_API.Maps[0].atlases) + 1) if ns.atlasTexture(i).IsShown(ns.atlasTexture(i)))
check('zoomed out over the Eastern Kingdoms: Kalimdor drawn beside it, each overview image where Blizzard\'s world map puts it (to the pixel, its scale too)', shown == len(k1.atlases) and own == len(G.GPS_API.Maps[0].atlases) and worst < 1e-6,
      f'{shown} of {len(k1.atlases)} Kalimdor images, {own} Eastern Kingdoms images, worst {worst:.2e} px')
# the gap between them on screen: the world map's ~10,000 yd of sea
kx1 = ns.GridToScreen(*ns.WorldGridOn(1, e1.tx1 + 1, e1.ty0, 0))[0]
ex0 = ns.GridToScreen(e0.tx0, e0.ty0)[0]
gap_yd = (ex0 - kx1) / view.scale * TILE * e0.ax
check('the sea between them on screen is the world map\'s (Kalimdor west of the Eastern Kingdoms)', abs(gap_yd - (e0.x0 - e1.x1)) < 1 and gap_yd > 5000, f'{gap_yd:.0f} yd on screen, world map {e0.x0 - e1.x1:.0f} yd')
# close up near Kalimdor's east coast: its minimap tiles too
view.cx, view.cy = ns.WorldGridOn(1, e1.tx1 - 2, 40, 0); view.scale = 90; ns.Layout()
mine = [k for k in ns.liveTiles.keys() if k >= 2 * 4096]
ok = len(mine) > 0
worst = 0
for k in mine:
    t = ns.liveTiles[k]; key = k - 2 * 4096
    gx, gy = ns.WorldGridOn(1, key % 64, key // 64, 0)
    want = ns.GridToScreen(gx, gy); got = tl(t)
    worst = max(worst, abs(got[0] - want[0]), abs(got[1] - want[1]))
check('close up over the other continent: its minimap tiles drawn there (where the world map puts them)', ok and worst < 1e-6, f'{len(mine)} Kalimdor tiles, worst {worst:.2e} px')
# panning from the Eastern Kingdoms over the sea onto Kalimdor: the view's map becomes Kalimdor on the way,
# nothing moving on screen when it does
ns.ShowMap(0, True)
view.cx, view.cy = e0.tx0 + 3, (e0.ty0 + e0.ty1) / 2; view.scale = 8; ns.Layout()
cw, ch = canvas.GetSize(canvas)
G.SANDBOX_MOUSE('move', 0, 0)
lt, bt, rt_, tt = G.SANDBOX.rect(canvas)
def at(px, py): return lt + px, tt - py
x, y = at(cw / 2, ch / 2)
G.SANDBOX_MOUSE('down', x, y, 'LeftButton'); tick(1)
maps, jumps = [], 0
ref = None
for i in range(1, 41):
    mark = peer_first(1) if view.map == 0 else ns.atlasTexture(1)
    before = tl(mark) if mark else (0, 0)
    G.SANDBOX_MOUSE('move', x + 6 * i, y); tick(1)
    mark2 = peer_first(1) if view.map == 0 else ns.atlasTexture(1)
    after = tl(mark2) if mark2 else (1e9, 1e9)
    # (within 0.25 px: Blizzard's world map scales the continents 0.02 % differently east-west and north-south,
    # and the 2D map has one scale, so at the switch a point 1,000 px from the middle moves up to 0.19 px)
    if abs((after[0] - before[0]) - 6) > 0.25 or abs(after[1] - before[1]) > 0.25:
        jumps += 1
        if os.environ.get('DBG2D'): print('frame', i, 'map', view.map, 'moved', after[0] - before[0], after[1] - before[1])
    maps.append(view.map)
G.SANDBOX_MOUSE('up', x + 240, y, 'LeftButton'); tick(1)
check('panning from the Eastern Kingdoms onto Kalimdor: the view\'s map becomes Kalimdor on the way, Kalimdor moving with the cursor every frame (nothing jumps at the switch, within 0.25 px)', 0 in maps and maps[-1] == 1 and jumps == 0,
      f'maps {maps[0]} -> {maps[-1]}, {jumps} frames off')
sub = ns.ui.subtitle.GetText(ns.ui.subtitle)
check('... the subtitle says Kalimdor, and the view is saved on it', sub == G.GPS_API.Maps[1].name and ns.db.map == 1, f'subtitle {sub!r}, saved map {ns.db.map}')
# a map that is not on the world map (an instance): nothing else drawn round it
inst = next((i for i in G.GPS_API.MapOrder.values() if i not in (0, 1)), None)
ns.ShowMap(inst); ns.Layout()
others = sum(1 for p in (0, 1) for t in (ns.peerAtlasOf(p).values() if ns.peerAtlasOf(p) else []) if t.IsShown(t))
check('a map that is not on the world map (an instance): no continent drawn round it', others == 0, f'map {inst}, {others} images of the continents shown')

chat()
check('no Lua errors', not errors, '; '.join(errors[:2]))
n = sum(1 for _, ok in results if ok)
if mutant:
    print('MUTANT', 'caught' if n < len(results) else 'NOT caught'); sys.exit(0)
caught = 0
for i, m in enumerate(MUTANTS if not os.environ.get('NO_MUTANTS') else []):
    out = subprocess.run([sys.executable, os.path.abspath(__file__), '--mutant', str(i)], capture_output=True, text=True, timeout=600).stdout
    c = 'MUTANT caught' in out; caught += c
    print(('     caught' if c else '     NOT caught'), m[0])
check(f'every mutation of the world view is caught by a check ({len(MUTANTS)} mutations)', caught == len(MUTANTS), f'{caught} of {len(MUTANTS)}')
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
