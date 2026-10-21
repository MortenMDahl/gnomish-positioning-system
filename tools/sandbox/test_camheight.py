# The camera's height over cities and steep ground (J3, 2026-10-21): zooming in and panning slowly over
# Orgrimmar, Stormwind and Thunder Bluff, straight down and tilted 45, frame by frame at 30 fps.
# Reported in the game: "the height keeps jumping when zooming in"; "looking at cities where height
# changes a lot also makes zooming in look bad, as height changes quickly".
#
# Per frame it measures what the zoom (or pan) step itself does not explain: the ideal zoom moves the
# camera straight toward the point zoomed toward (Free: the ground under the cursor; Follow: you) by the
# step's factor, the ideal pan moves it sideways by the pan; the rest is the lift. "height jump" is that
# rest's height, "view jump" the largest screen motion it causes on ground points seen in the frame
# before (a 7 x 5 grid over the view). It also checks that the camera is never under the ground or a
# roof, reaches the clearance after the ease, and that zooming in still stops there.
#
# Run: python3 test_camheight.py              (the addon as in site/addons)
#      python3 test_camheight.py --file X.lua (another GPS3D.lua, e.g. the old one, for before/after)
#      --fast: fewer triangles drawn (the camera reads the data, not the triangles: same numbers, quicker)
#      --only zoom|pan|ease: one part and its checks (for trying mutations)
import lupa.lua54 as lupa54, math, time, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
OVERRIDE = sys.argv[sys.argv.index('--file') + 1] if '--file' in sys.argv else None
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())
toc = open(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua']), ('GPS3D', gps3d_files)]:
    for f in files:
        path = OVERRIDE if (OVERRIDE and addon == 'GPS3D' and f == 'GPS3D.lua') else f'{SITE}/addons/{addon}/{f}'
        if not G.SANDBOX_LOAD(addon, f, open(path).read()): print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')
W, H, FPS = 1280, 800, 30
def tick(n=1):
    for _ in range(n): G.SANDBOX_TICK(1 / FPS, W, H)
def place(X, Y, m, facing=0.0, zone=''):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, zone, '', -1, -1, -1)
ns = G.SANDBOX.namespaces['GPS3D']
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

place(1630, -4380, 1, 0.3, 'Orgrimmar')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
G.GPS3D_DB.buildingModels = 'simple'; ns.ModelsChanged()  # the in-game default since 2026-10-21
if '--fast' in sys.argv:  # fewer triangles drawn: the camera does not depend on them (GroundHeight reads the data), only the run time does
    ns.SetGridBudget(300); ns.SetBuildingBudget(0)
cam, pl = ns.cam, ns.player
l, b, r, t = G.SANDBOX.rect(ns.canvas)
CX, CY, CW, CH = (l + r) / 2, (b + t) / 2, r - l, t - b
def mouse(kind, px, py, btn='', d=0): G.SANDBOX_MOUSE(kind, CX + px, CY + py, btn, d)
EASE = 0.5  # seconds the camera may take to reach the clearance (the new code eases its lift; the old one jumped)

def basis():
    return tuple(ns.CameraBasis())
def project(bs, ex, ey, ez, P):
    fx, fy, fz, rx, ry, ux, uy, uz = bs[:8]
    dx, dy, dz = P[0] - ex, P[1] - ey, P[2] - ez
    d = dx * fx + dy * fy + dz * fz
    if d < 3: return None
    F = ns.Focal()
    return (dx * rx + dy * ry) * F / d, (dx * ux + dy * uy + dz * uz) * F / d
GRID = [((i / 6 - 0.5) * 0.8 * CW, (j / 4 - 0.5) * 0.8 * CH) for i in range(7) for j in range(5)]
def ground_points():
    pts = []
    for sx, sy in GRID:
        p = ns.ScreenToTerrain(sx, sy)
        if p: pts.append((p[0], p[1], p[2]))
    return pts
def view_jump(bs, ideal, actual, pts):
    worst = 0.0
    for P in pts:
        a, b = project(bs, *ideal, P), project(bs, *actual, P)
        if a and b and abs(a[0]) < CW and abs(a[1]) < CH: worst = max(worst, math.hypot(a[0] - b[0], a[1] - b[1]))
    return worst
def above_surface():
    bs = basis(); return bs[10] - ns.GroundHeight(bs[8], bs[9])
def clearance25():  # the camera's height above the highest ground or roof within 25 yd (2-yd grid)
    bs = basis(); ex, ey, ez = bs[8], bs[9], bs[10]; top = -1e9
    for i in range(-25, 26, 2):
        for j in range(-25, 26, 2):
            if i * i + j * j <= 625: top = max(top, ns.GroundHeight(ex + i, ey + j))
    return ez - top

RINGS = [(6, 6), (12, 10), (18, 14), (25, 18)]  # GroundUnder's points: the camera's spot and four rings
def ground_under(x, y):
    g = ns.GroundHeight(x, y); k = 0
    for ri, (rr, n) in enumerate(RINGS):
        for i in range(n):
            a = (i + 0.37 * ri) / n * 2 * math.pi
            g = max(g, ns.GroundHeight(x + rr * math.cos(a), y + rr * math.sin(a)))
    return g
def eye_clear():
    bs = basis(); return bs[10] - ground_under(bs[8], bs[9])

CITIES = [('Orgrimmar, Valley of Strength', 1630, -4380, 1), ('Stormwind, cathedral', -8520, 850, 0),
          ('Stormwind, Trade District', -8830, 640, 0), ('Thunder Bluff', -1280, 130, 1)]
def setup(X, Y, m, mode, pitch):
    place(X, Y, m, 0.8); tick(2)
    if mode == 'follow':
        ns.FollowMe('follow'); tick(30)
    else:
        ns.SetCamMode('free'); tick(1)
    if pitch >= 89: ns.SetTopDown(True, True)
    else: ns.SetTopDown(False, True); cam.pitch = pitch
    cam.yaw = 30
    if mode == 'free':
        cam.map, cam.x, cam.y = m, pl.x, pl.y
        cam.th = ns.GroundHeight(cam.x, cam.y)
    cam.dist = 1500
    ns.Render(); tick(int(EASE * FPS) + 5)

def zoom_run(name, X, Y, m, mode, pitch, cur):
    setup(X, Y, m, mode, pitch)
    px, py = cur
    if mode == 'free': mouse('move', px, py)
    hj = vj = raw = 0.0; below = 1e9; inside = 1e9; frames = 0; still = 0; ms = []; worst_at = None; tr = 1.0; prev = None
    while frames < 450 and still < int(EASE * FPS) + 10:
        bs0 = basis(); E0 = bs0[8:11]; d0 = cam.dist
        if mode == 'free':
            Z = ns.ScreenToTerrain(px, py) or (cam.x, cam.y, cam.th)
        else:
            Z = (cam.x, cam.y, cam.th)
        pts = ground_points()
        depth = math.dist(Z, E0)  # how far the point zoomed toward is: the camera moves 2 % of it
        if prev and abs(k - 1) > 1e-9: tr = max(tr, depth / (prev * k), prev * k / depth)  # 1: the next step moves as the last
        prev = depth
        t0 = time.perf_counter()
        ns.Zoom(0.98, px if mode == 'free' else None, py if mode == 'free' else None)
        tick(1)
        ms.append((time.perf_counter() - t0) * 1000)
        frames += 1
        bs1 = basis(); E1 = bs1[8:11]
        k = cam.dist / d0
        still = still + 1 if math.dist(E0, E1) < 0.02 else 0  # (Free: a step at the clearance may only move the orbit point)
        ideal = tuple(Z[i] + (E0[i] - Z[i]) * k for i in range(3))
        h = abs(E1[2] - ideal[2])
        if h > hj: hj, worst_at = h, round(cam.dist, 1)
        raw = max(raw, abs(E1[2] - E0[2]))
        vj = max(vj, view_jump(bs1, ideal, E1, pts))
        below = min(below, above_surface()); inside = min(inside, eye_clear())
    held = eye_clear()  # still turning the wheel: the camera may sit up to LAG (2 yd) inside the clearance
    tick(int(EASE * FPS) + 5)  # let go of the wheel: the lift eases in
    return dict(name=name, hj=hj, vj=vj, raw=raw, below=below, dist=cam.dist, clear=clearance25(), frames=frames, at=worst_at, tr=tr, eclear=eye_clear(), held=held, inside=inside, ms=sorted(ms)[len(ms) // 2])

def pan_run(name, X, Y, m, pitch, dist, frames=150, step=12):
    setup(X, Y, m, 'free', pitch)
    cam.dist = dist; ns.Render(); tick(int(EASE * FPS) + 5)
    hj = vj = 0.0; below = 1e9; n = 0; x = -300
    mouse('move', x, 0); mouse('down', x, 0, 'LeftButton')
    while n < frames:
        if x + step > 300:  # let go and grab again on the other side
            mouse('up', x, 0, 'LeftButton'); x = -300; mouse('move', x, 0); mouse('down', x, 0, 'LeftButton')
        bs0 = basis(); E0 = bs0[8:11]; ox, oy = cam.x, cam.y
        pts = ground_points()
        x += step; mouse('move', x, 0); tick(1); n += 1
        bs1 = basis(); E1 = bs1[8:11]
        ideal = (E0[0] + cam.x - ox, E0[1] + cam.y - oy, E0[2])
        hj = max(hj, abs(E1[2] - E0[2]))
        vj = max(vj, view_jump(bs1, ideal, E1, pts))
        below = min(below, above_surface())
    mouse('up', x, 0, 'LeftButton'); tick(int(EASE * FPS))
    return dict(name=name, hj=hj, vj=vj, below=below, clear=clearance25())

ONLY = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
ZOOM, PAN = [], []
for name, X, Y, m in (CITIES if ONLY in (None, 'zoom') else []):
    for pitch in (89.9, 45):
        for mode, cur in (('free', (0, 0)), ('free', (180, -120)), ('follow', (0, 0))):
            r = zoom_run(name, X, Y, m, mode, pitch, cur)
            r.update(mode=mode, pitch=pitch, cur=cur); ZOOM.append(r)
            print(f"ZOOM {name:30s} {mode:6s} {'down' if pitch > 89 else 'tilt45'} cur {cur}: height jump {r['hj']:6.2f} yd (raw {r['raw']:5.2f}) view jump {r['vj']:7.1f} px"
                  f" | lowest above surface {r['below']:6.2f} | stopped at {r['dist']:6.1f} yd, {r['eclear']:5.2f} above the ground within 25 yd ({r['clear']:5.2f} on a 2-yd grid; {r['held']:5.2f} while still zooming, lowest {r['inside']:5.2f}) | worst at {r['at']} yd | zoom speed change x{r['tr']:.2f} | {r['frames']} frames, {r['ms']:.1f} ms/frame")
for name, X, Y, m in (CITIES if ONLY in (None, 'pan') else []):
    for pitch, dist in ((89.9, 30), (45, 45)):
        r = pan_run(name, X, Y, m, pitch, dist)
        r.update(pitch=pitch); PAN.append(r)
        print(f"PAN  {name:30s} {'down' if pitch > 89 else 'tilt45'} dist {dist}: height jump {r['hj']:6.2f} yd view jump {r['vj']:7.1f} px | lowest above surface {r['below']:6.2f} | clearance after {r['clear']:5.2f}")

# the ease on its own: pan in one go from the street onto the cathedral's roof at a low height (Free,
# straight down), then let it settle: frames until the camera is within 0.5 yd of the clearance there,
# and the same at 20, 30 and 60 fps (the ease is worked out exactly for each frame's time)
place(-8520, 850, 0, 0.0, 'Stormwind City'); tick(2)
PX, PY = pl.x, pl.y  # the cathedral's highest point and the lowest street round it, found once
ROOF = max(((ns.GroundHeight(PX + i, PY + j, 0), PX + i, PY + j) for i in range(-90, 91, 3) for j in range(-90, 91, 3)))
STREET = min(((ns.GroundHeight(PX + i, PY + j, 0), PX + i, PY + j) for i in range(-150, 151, 6) for j in range(-150, 151, 6) if ns.GroundHeight(PX + i, PY + j, 0) > 1))
def ease_run(fps):
    global FPS
    place(-8520, 850, 0, 0.0, 'Stormwind City'); tick(2)
    ns.SetCamMode('free'); ns.SetTopDown(True, True); tick(1)
    R, S = ROOF, STREET
    cam.map, cam.x, cam.y, cam.th, cam.dist = 0, S[1], S[2], S[0], 30; ns.Render(); tick(40)
    old, FPS = FPS, fps
    cam.x, cam.y = R[1], R[2]; ns.Render()
    first = above_surface(); n = 0; series = []; overshoot = 0.0
    want = None
    while n < 3 * fps:
        tick(1); n += 1
        c = eye_clear(); series.append(c)
    final = series[-1]
    reach = next((i + 1 for i, c in enumerate(series) if abs(c - final) < 0.5 and all(abs(c2 - final) < 0.5 for c2 in series[i:])), None)
    overshoot = max(0.0, max(series) - final)
    at02 = series[int(0.2 * fps) - 1]
    FPS = old
    return first, reach / fps if reach else None, final, overshoot, at02, R[0] - S[0]
EASES = {fps: ease_run(fps) for fps in ((20, 30, 60) if ONLY in (None, 'ease') else ())}
for fps, e in EASES.items():
    print(f'EASE {fps} fps: roof {e[5]:.0f} yd above the street; first frame {e[0]:.2f} yd above the roof, within 0.5 yd of the clearance after {e[1]} s, settled {e[2]:.2f} yd above the highest point within 25 yd, overshoot {e[3]:.2f} yd; at 0.2 s {e[4]:.3f}')

def worst(rs, key): return max((r[key] for r in rs), default=0.0)
zh, zv, ph, pv = worst(ZOOM, 'hj'), worst(ZOOM, 'vj'), worst(PAN, 'hj'), worst(PAN, 'vj')
print(f'SUMMARY zoom: height jump {zh:.2f} yd, view jump {zv:.1f} px; pan: height jump {ph:.2f} yd, view jump {pv:.1f} px')
if ZOOM:
    check('zooming in over the cities: the camera\'s height never jumps (at most 1 yd in a frame beyond what the zoom step itself moves it)', zh <= 1, f'worst {zh:.2f} yd, the view {zv:.1f} px (until 2026-10-21: 7.13 yd, 141 px)')
    check('zooming in over the cities: the view never jumps (fixed ground points move at most 40 px in a frame beyond the zoom)', zv <= 40, f'worst {zv:.1f} px (until 2026-10-21: 141 px)')
if PAN:
    check('panning slowly over the cities at a low height: the camera\'s height changes at most 8 yd in a frame (climbing a cliff, eased)', ph <= 8, f'worst {ph:.2f} yd, the view {pv:.1f} px (until 2026-10-21: 37.8 yd, 870 px)')
    check('panning slowly over the cities at a low height: the view moves at most 150 px in a frame beyond the pan', pv <= 150, f'worst {pv:.1f} px (until 2026-10-21: 870 px)')
low = min([r['below'] for r in ZOOM + PAN] + [e[0] for e in EASES.values()])
check('never under the ground or a roof: at least 2 yd above the surface right under the camera in every frame', low >= 2 - 1e-6, f'lowest {low:.2f} yd' + (f'; teleported onto a roof, first frame {min(e[0] for e in EASES.values()):.2f} yd above it' if EASES else ''))
if EASES:
    check('the clearance is reached within the ease (0.5 s to within 0.5 yd, no overshoot)', all(e[1] is not None and e[1] <= 0.5 + 1e-9 and e[3] < 0.05 and e[2] >= 8 - 0.05 for e in EASES.values()), str({f: (e[1], round(e[2], 2), round(e[3], 3)) for f, e in EASES.items()}))
    check('the ease is the same at 20, 30 and 60 fps', max(e[4] for e in EASES.values()) - min(e[4] for e in EASES.values()) < 0.05, str({f: round(e[4], 3) for f, e in EASES.items()}))
if ZOOM:
    zc, zi = min(r['eclear'] for r in ZOOM), min(r['inside'] for r in ZOOM)
    check('zooming in still stops at the clearance (8 yd over the ground and roofs within 25 yd once the wheel is let go, less the 0.5 yd a step may take)', zc >= 7.5 - 1e-6, f'lowest {zc:.2f} yd at the end of the {len(ZOOM)} zooms')
    check('while zooming the camera is at most 2 yd inside the clearance (LAG, while the lift eases in)', zi >= 8 - 2 - 1e-6, f'lowest {zi:.2f} yd above the ground and roofs within 25 yd')
print(f'{sum(1 for _, ok in results if ok)} of {len(results)} checks passed')
