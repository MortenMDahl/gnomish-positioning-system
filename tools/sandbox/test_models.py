# Checks the game's own models in the 3D view (prototypes/GPS3D/Models.lua) on the sandbox engine
# (Lua 5.4), against the real exported placements (data/models.json, from the game's files):
# the data as the addon reads it, where each actor is put, which models are chosen (an independent
# Python choice from the export), the actor pool, the building check both ways (the game refusing
# WMOs or loading them) and the simplified blocks giving way, the settings' effects, the debug log's
# performance lines and the self-test. Ends with mutations: each breaks one rule in Models.lua and
# must make its check fail.
# Usage: python test_models.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os, json, math, random, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
TILE = 1600 / 3
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
GPS_FILES = toc_files(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))
GPS3D_FILES = toc_files(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc'))
W, H = 1280, 800
DATA = json.load(open(os.path.join(ROOT, 'data', 'models.json')))
results, errors = [], []
# Mutations (run at the end, each in its own process): a broken rule in Models.lua, and the check that must catch it
MUTATIONS = {
    'yaw': (('	a:SetYaw(t.yaw[i] + M.turn)', '	a:SetYaw(-t.yaw[i] + M.turn)'), 'each actor stands as in the game files'),
    'pitch': (('tilt == "flip" and -t.pitch[i] or t.pitch[i])', 'tilt == "flip" and -t.pitch[i] or t.roll[i])'), 'each actor stands as in the game files'),
    'range': (('if ox * ox + oy * oy > lim * lim then return end', 'if ox * ox + oy * oy > 4 * lim * lim then return end'), 'top-down, no count limit'),
    'order': (('local function ByScore(a, b) return candScore[a] > candScore[b] end', 'local function ByScore(a, b) return candScore[a] < candScore[b] end'), 'count 60'),
    'cover': (('local ex, ey = max(abs(x0 - M.coverX), abs(x0 + B - M.coverX)), max(abs(y1 - M.coverY), abs(y1 - B - M.coverY))',
               'local ex, ey = min(abs(x0 - M.coverX), abs(x0 + B - M.coverX)), min(abs(y1 - M.coverY), abs(y1 - B - M.coverY))'), "the game's buildings shown"),
    'swaps': (('if swaps >= SWAP_LIMIT then later = later + 1 else', 'if false then later = later + 1 else'), 'a jump'),
    'holes': (('if (nx - h[1]) ^ 2 + (ny - h[2]) ^ 2 <= h[3] * h[3] then return false end', 'if false then return false end'), 'a building that never loads'),
    'refused': (('elseif M.wmoSets > 0 and now - M.wmoSince > WMO_WAIT then', 'elseif false then'), 'the game refusing buildings'),
}
MUT = os.environ.get('GPS_MUTATION')
QUIET = '--quiet' in sys.argv
def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    if not QUIET or not ok: print(('PASS' if ok else 'FAIL'), name, detail)
    return bool(ok)

class Game:
    def __init__(self, patch=None, with_models=True, wmo=True, before=False):
        if MUT and not patch: patch = MUTATIONS[MUT][0]
        OLD = os.path.join(ROOT, 'notes', 'rollback-before-game-models')
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        G.SANDBOX_WMO = wmo
        files3d = toc_files(os.path.join(OLD, 'GPS3D.toc')) if before else GPS3D_FILES
        for addon, files in [('GnomishPositioningSystem', GPS_FILES), ('GPS3D', files3d)]:
            for f in files:
                if not with_models and f.startswith('Data/Models_'): continue
                # (the saved TOC lists Detail_1_4.lua, which the build no longer makes since caves are left out)
                if before and f.startswith('Data/Detail_') and not os.path.exists(f'{SITE}/addons/{addon}/{f}'): continue
                src = open(os.path.join(OLD, 'GPS3D.lua') if before and f == 'GPS3D.lua' else f'{SITE}/addons/{addon}/{f}').read()
                if patch and f == 'Models.lua':
                    old, new = patch
                    assert src.count(old) == 1, ('patch target', old)
                    src = src.replace(old, new)
                if not G.SANDBOX_LOAD(addon, f, src): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        G.SANDBOX_PLAYER(-9464, 62, 0, 0, 1.0, 'Elwynn Forest', 'Goldshire', 1429, 0.42, 0.65)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); self.tick(2)
        self.ns = G.SANDBOX.namespaces['GPS3D']
        self.chat()
    def tick(self, n=1, dt=1 / 30):
        for _ in range(n): self.G.SANDBOX_TICK(dt, W, H)
    def chat(self):
        c = str(self.G.SANDBOX_CHAT() or '')
        if c:
            if not QUIET: print('CHAT>', c.replace('\n', '\nCHAT> '))
            errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l)
        return c
    def open3d(self):
        self.G.GPS_API.OpenNamed('3D'); self.tick(20)
    def free_view(self, x, y, dist, pitch=89.9, yaw=0):
        ns = self.ns
        ns.SetCamMode('free')
        if pitch < 89: ns.SetTopDown(False, True)
        else: ns.SetTopDown(True, True)
        ns.cam.map, ns.cam.x, ns.cam.y, ns.cam.dist, ns.cam.pitch, ns.cam.yaw = 0, x, y, dist, pitch, yaw
        ns.cam.th = ns.GroundHeight(x, y)
        ns.Render(); self.tick(3)
    def actors(self):
        """Shown actors with a file model (the game's models): dicts."""
        out = []
        for a in self.ns.scene._actors.values():
            if a._shown and a._fileID:
                p = a._pos
                out.append({'fdid': a._fileID, 'x': p[1], 'y': p[2], 'h': p[3], 'yaw': a._yaw, 'pitch': a._pitch, 'roll': a._roll, 's': a._scale, 'a': a})
        return out
    def entries(self):
        st = self.ns.modelState
        return [e for e in st.pool.values() if e.id is not None]

# ---- the export, as Python sees it ----
def placements(mid):
    m = DATA['maps'][str(mid)]
    M = m['models']
    for key, pl in m['tiles'].items():
        tx, ty = map(int, key.split('_'))
        for p in pl:
            mi, x, y, h, yaw, pitch, roll, s = p
            fd, kind, r, lo, hi = M[mi]
            size = max(r, (hi - lo) / 2) * s
            if size <= 0: continue
            yield {'tile': (tx, ty), 'fdid': fd, 'wmo': kind == 1, 'x': x, 'y': y, 'h': h, 'yaw': yaw, 'pitch': pitch, 'roll': roll, 's': s,
                   'size': size, 'cz': h + (lo + hi) / 2 * s, 'r': r * s}
MAP0 = list(placements(0))
BY_TILE = {}
for p in MAP0: BY_TILE.setdefault(p['tile'], []).append(p)
def angdiff(a, b): return abs((a - b + math.pi) % (2 * math.pi) - math.pi)
def find(a):
    """The export's placement of the same model at the same spot (the closest in pose when the game
    has two in one place)."""
    tx, ty = math.floor(a['x'] / TILE), math.floor(-a['y'] / TILE)
    best, bd = None, None
    for p in BY_TILE.get((tx, ty), []):
        if p['fdid'] == a['fdid'] and abs(p['x'] - a['x']) < 0.02 and abs(p['y'] - a['y']) < 0.02:
            d = abs(p['h'] - a['h']) + angdiff(p['yaw'], a['yaw']) + angdiff(p['pitch'], a['pitch']) + angdiff(p['roll'], a['roll']) + abs(p['s'] - a['s'])
            if best is None or d < bd: best, bd = p, d
    return best

def expected(g, R, minPx, props=True, buildings=True, slack=0.0):
    """Python's own choice from the export (top-down: no occlusion), for the current camera: every
    placement passing the rules, with its on-screen size; slack > 0 makes each rule looser (to get
    'may be shown'), < 0 stricter ('must be shown')."""
    ns = g.ns
    F = ns.Focal()
    fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
    w, h = ns.canvas.GetSize(ns.canvas)
    hw, hh = w / 2, h / 2
    out = []
    for p in MAP0:
        if p['wmo'] and not buildings or not p['wmo'] and not props: continue
        lim = R + (p['r'] if p['wmo'] else 0)
        if math.hypot(p['x'] - ns.cam.x, p['y'] - ns.cam.y) > lim + slack * 2: continue
        dx, dy, dz = p['x'] - cx, p['y'] - cy, p['cz'] - cz
        d = dx * fx + dy * fy + dz * fz
        if d <= -p['size']: continue
        dd = max(d, 1)
        px = p['size'] * F / dd
        if px < minPx * (1 - slack * 0.03): continue
        sx, sy = (dx * rx + dy * ry) * F / dd, (dx * ux + dy * uy + dz * uz) * F / dd
        if d > p['size'] and (abs(sx) > hw + px + slack * 3 or abs(sy) > hh + px + slack * 3): continue
        out.append((p, px))
    return out

def key(p): return (p['fdid'], round(p['x'], 2), round(p['y'], 2))

g = Game()
G, ns = g.G, g.ns
st = ns.modelState
g.open3d()

# ---- M1: the data as the addon reads it ----
nmaps = sum(1 for _ in ns.Models.keys())
n_lua = 0
for mid in ns.Models.keys():
    for k, s in ns.Models[mid].items():
        n_lua += int(G.SANDBOX.namespaces['GPS3D'].ModelTile(mid, k % 64, k // 64).n)
n_json = sum(1 for mid in DATA['maps'] for p in placements(int(mid)))
check('data: every map of the export (16), every placement with a size read by the addon', nmaps == len(DATA['maps']) == 16 and n_lua == n_json, f'{nmaps} maps, {n_lua} placements (export {n_json})')
random.seed(7)
keys = random.sample(sorted(BY_TILE), 25)
bad, compared = [], 0
for (tx, ty) in keys:
    t = ns.ModelTile(0, tx, ty)
    pal = ns.ModelPalette(0)
    want = sorted(BY_TILE[(tx, ty)], key=lambda p: -p['size'])
    got = []
    for i in range(1, int(t.n) + 1):
        got.append({'fdid': pal.fdid[t.mi[i]], 'x': t.x[i], 'y': t.y[i], 'h': t.h[i], 'yaw': t.yaw[i], 'pitch': t.pitch[i], 'roll': t.roll[i], 's': t.sc[i], 'size': t.size[i]})
    if len(got) != len(want): bad.append(('count', tx, ty)); continue
    # same set (the order among equal sizes may differ): match each decoded one to the export
    for q in got:
        p = find(q)
        compared += 1
        if not p or abs(p['h'] - q['h']) > 0.04 or angdiff(p['yaw'], q['yaw']) > 0.002 or angdiff(p['pitch'], q['pitch']) > 0.002 or angdiff(p['roll'], q['roll']) > 0.002 or abs(q['s'] / p['s'] - 1) > 0.0025:
            bad.append((tx, ty, q['fdid'])); break
    sizes = [q['size'] for q in got]
    if any(sizes[i + 1] > sizes[i] for i in range(len(sizes) - 1)): bad.append(('order', tx, ty))
check('data: 25 random tiles of Eastern Kingdoms decoded in Lua equal the export (position, height, rotation, scale), biggest first', not bad, f'{compared} placements; {bad[:3]}')
wl = ns.ModelWmoList(0)
check('data: the buildings list holds every building of the map', int(wl.n) == sum(1 for p in MAP0 if p['wmo']), f'{wl.n} vs {sum(1 for p in MAP0 if p["wmo"])}')

# ---- M2: a top-down view over Goldshire: what is chosen ----
GX, GY = 32.3 * TILE, -49.5 * TILE
g.free_view(GX, GY, 300)
g.tick(15)
R, PX, COUNT = int(ns.ModelSetting('modelRange')), float(ns.ModelSetting('modelPx')), int(ns.ModelSetting('modelCount'))
acts = g.actors()
unmatched = [a for a in acts if not find(a)]
check('every shown model is a placement of the export (same model, same spot)', acts and not unmatched, f'{len(acts)} shown, {len(unmatched)} unmatched')
pose_bad = []
for a in acts:
    p = find(a)
    if not p: continue
    if abs(a['h'] - p['h']) > 0.04 or angdiff(a['yaw'], p['yaw']) > 0.002 or angdiff(a['pitch'], p['pitch']) > 0.002 or angdiff(a['roll'], p['roll']) > 0.002 or abs(a['s'] / p['s'] - 1) > 0.0025:
        pose_bad.append((a['fdid'], a['yaw'], p['yaw']))
check('each actor stands as in the game files: height, yaw, pitch, roll and scale (SetYaw/SetPitch/SetRoll/SetScale)', not pose_bad, str(pose_bad[:3]))
g.G.GPS3D_DB.modelCount = 1500; ns.ModelsChanged(); g.tick(15)
acts = g.actors()
shown = {key(find(a)) for a in acts if find(a)}
may = {key(p) for p, _ in expected(g, R, PX, slack=1)}
must = {key(p) for p, _ in expected(g, R, PX, slack=-1)}
check('top-down, no count limit: shown = Python\'s own choice from the export (range, in view, at least the smallest size)', must <= shown <= may and len(must) > 50,
      f'shown {len(shown)}, must {len(must)}, may {len(may)}; missing {len(must - shown)}, extra {len(shown - may)}')
g.G.GPS3D_DB.modelCount = 60; ns.ModelsChanged(); g.tick(15)
acts = g.actors()
props = [a for a in acts if not find(a)['wmo']]
exp = expected(g, R, PX)
pxs = {key(p): px for p, px in exp}
shown_px = [pxs.get(key(find(a)), 0) for a in props]
others = [px for p, px in exp if not p['wmo'] and key(p) not in {key(find(a)) for a in props}]
check('count 60: 60 props, the biggest on screen (none left out is bigger than the smallest shown)', len(props) == 60 and min(shown_px) >= max(others) * 0.98,
      f'{len(props)} props; smallest shown {min(shown_px):.1f} px, biggest left out {max(others):.1f} px')
wmo_exp = {key(p) for p, _ in expected(g, R, PX, props=False, slack=-1)}
wmo_shown = {key(find(a)) for a in acts if find(a)['wmo']}
check('buildings: all of them in range and view, not limited by the count', wmo_exp and wmo_exp <= wmo_shown, f'{len(wmo_shown)} shown, {len(wmo_exp)} expected')
g.G.GPS3D_DB.modelCount = None; ns.ModelsChanged(); g.tick(15)

# ---- M3: the pool ----
before = {int(e.id): e for e in g.entries()}
loads0 = int(G.SANDBOX.modelLoads or 0)
ns.cam.x = ns.cam.x + 40; ns.Render(); g.tick(15)
after = {int(e.id): e for e in g.entries()}
same = [i for i in after if i in before]
same_ref = g.L.eval('function(a, b) return rawequal(a, b) end')
kept = all(same_ref(after[i], before[i]) for i in same)
loads1 = int(G.SANDBOX.modelLoads or 0)
new_ids = [i for i in after if i not in before]
check('a small pan: models still chosen keep their actor; only new ones load (each actor showing one model reused before another loads)', kept and len(same) > 0 and loads1 - loads0 <= len(new_ids),
      f'{len(same)} kept, {len(new_ids)} new, {loads1 - loads0} loads')
pool0 = int(len(st.pool))
# a jump to Stormwind (other models): loads counted tick by tick (one choice per tick at most)
far_tiles = [(len([p for p in pl if not p['wmo']]), t) for t, pl in BY_TILE.items() if abs(t[0] - 32) + abs(t[1] - 49) >= 4]
_, (jx, jy) = max(far_tiles)
ns.cam.x = (jx + 0.5) * TILE; ns.cam.y = -(jy + 0.5) * TILE; ns.cam.th = ns.GroundHeight(ns.cam.x, ns.cam.y); ns.Render()
deltas, was_pending = [], False
for k in range(60):
    l0 = int(G.SANDBOX.modelLoads or 0); g.tick(1); deltas.append(int(G.SANDBOX.modelLoads or 0) - l0)
    was_pending = was_pending or bool(st.pending)
check('a jump: at most SWAP_LIMIT model loads per choice, the rest on the following choices, until all are shown', max(deltas) <= int(ns.modelConst.SWAP_LIMIT) and was_pending and not st.pending and int(st.shown) > 100,
      f'tile {jx}_{jy}: loads per tick {[d for d in deltas if d]}; {st.shown} shown; pool {pool0} -> {len(st.pool)}')
check('pool never above the props limit plus the buildings shown', int(len(st.pool)) <= int(ns.ModelSetting('modelCount')) + int(st.shownWmo) + int(ns.modelConst.SWAP_LIMIT),
      f'{len(st.pool)} actors, {st.shownWmo} buildings')

# ---- M4: occlusion (tilted): a prop behind a hill is not drawn over it ----
mx, my, valley = 18057, -21867, (17297, -21507)
cz = ns.GridHeight(0, valley[0], valley[1]) + 5
ahead = ns.ModelOccluded(mx + (mx - valley[0]) * 0.6, my + (my - valley[1]) * 0.6, ns.GridHeight(0, mx + (mx - valley[0]) * 0.6, my + (my - valley[1]) * 0.6) + 5, valley[0], valley[1], cz, 0)
near = ns.ModelOccluded(valley[0] + 30, valley[1] + 10, ns.GridHeight(0, valley[0] + 30, valley[1] + 10) + 5, valley[0], valley[1], cz, 0)
check('occlusion: a prop behind the mountain from the valley is hidden, one next to you is not', ahead and not near, f'{ahead} {near}')

# ---- M5: the building check, the game loading WMOs (sandbox default) ----
G.GPS3D_DB.modelRange = 200
g.free_view(GX, GY, 500)
g.tick(30)
R = 200
check('building check: buildings load here -> "yes", saved for this game build', st.wmo == 'yes' and G.GPS3D_DB.wmoCheck == 'yes' and G.GPS3D_DB.wmoBuild == '1.60.1.sandbox', f'{st.wmo} {G.GPS3D_DB.wmoCheck} {G.GPS3D_DB.wmoBuild}')
# which blocks give way: record ModelsCover's answers for one frame
L = g.L
L.execute("""
SANDBOX_COVERLOG = {}
local ns = SANDBOX.namespaces['GPS3D']
local orig = ns.ModelsCover
ns.ModelsCover = function(x0, y1) local r = orig(x0, y1); SANDBOX_COVERLOG[#SANDBOX_COVERLOG + 1] = { x0, y1, r }; return r end
SANDBOX_COVERORIG = orig
""")
def cover_frame():
    L.execute('wipe(SANDBOX_COVERLOG)'); ns.Render()
    log = [(float(e[1]), float(e[2]), bool(e[3])) for e in G.SANDBOX_COVERLOG.values()]
    return log, int(ns.stats.detail)
log, drawn_game = cover_frame()
B = 1600 / 3 / 8
def far_corner(x0, y1, cx, cy): return math.hypot(max(abs(x0 - cx), abs(x0 + B - cx)), max(abs(y1 - cy), abs(y1 - B - cy)))
hidden = [(x0, y1) for x0, y1, r in log if r]
wrong = [b for b in hidden if far_corner(b[0], b[1], st.coverX, st.coverY) > R + 1e-6]
kept_inside = [(x0, y1) for x0, y1, r in log if not r and far_corner(x0, y1, st.coverX, st.coverY) <= R - 1]
check('the game\'s buildings shown: building blocks wholly within the model distance give way, the others stay', hidden and not wrong and not kept_inside and drawn_game > 0,
      f'{len(hidden)} blocks give way, {len(wrong)} of them reach past {R} yd, {len(kept_inside)} inside kept; {drawn_game} blocks still drawn')
# a building that is not drawn (never loads, or still loading): its simplified shape stays
def overlaps(x0, y1, cx_, cy_, r_):
    nx, ny = min(max(cx_, x0), x0 + B), min(max(cy_, y1 - B), y1)
    return (nx - cx_) ** 2 + (ny - cy_) ** 2 <= r_ * r_
shown_w = [e for e in g.entries() if e.wmo]
victim = shown_w[0]
vx, vy, vr, vf = float(victim.x), float(victim.y), float(victim.r), victim.fdid
st.bad[vf] = True; ns.ModelsChanged(); g.tick(3)
log3, _ = cover_frame()
hidden_on_victim = [(x0, y1) for x0, y1, r in log3 if r and overlaps(x0, y1, vx, vy, vr)]
others_hidden = [(x0, y1) for x0, y1, r in log3 if r]
check('a building that never loads: the blocks it stands on keep their simplified shape (the rest still give way)', not hidden_on_victim and others_hidden and not any(e.fdid == vf for e in g.entries()),
      f'building {vf} radius {vr:.0f} yd: {len(hidden_on_victim)} of its blocks hidden, {len(others_hidden)} other blocks give way')
st.bad[vf] = None
G.SANDBOX.modelLoadDelay = 3.0
for e in g.entries():
    if e.wmo:  # let go of them, so they load again
        st.byId[e.id] = None; e.id = None; e.fdid = None; e.actor.Hide(e.actor)
ns.ModelsChanged(); g.tick(3)
log4, _ = cover_frame()
loading_w = [e for e in g.entries() if e.wmo and not e.loaded]
hidden_loading = [(x0, y1) for x0, y1, r in log4 if r and any(overlaps(x0, y1, float(e.x), float(e.y), float(e.r)) for e in loading_w)]
g.tick(30 * 4)
log5, _ = cover_frame()
check('buildings still loading: their blocks stay until they have loaded, then give way', loading_w and not hidden_loading and sum(1 for *_, r in log5 if r) >= len(hidden),
      f'{len(loading_w)} loading, {len(hidden_loading)} of their blocks hidden; after loading {sum(1 for *_, r in log5 if r)} blocks give way')
G.SANDBOX.modelLoadDelay = 0
G.GPS3D_DB.buildingModels = 'simple'; ns.ModelsChanged(); g.tick(10)
log2, drawn_simple = cover_frame()
check('simplified shapes chosen: no block gives way, more blocks drawn, no building models', not any(r for _, _, r in log2) and drawn_simple > drawn_game and not any(find(a)['wmo'] for a in g.actors()),
      f'{drawn_simple} blocks vs {drawn_game}')
G.GPS3D_DB.buildingModels = None; ns.ModelsChanged(); g.tick(10)
wmo_on = sum(1 for a in g.actors() if find(a)['wmo'])
ns.SetDetail(False); g.tick(10)
check('Buildings off: no building models either (props stay)', wmo_on > 0 and not any(find(a)['wmo'] for a in g.actors()) and any(not find(a)['wmo'] for a in g.actors()), f'{wmo_on} buildings before')
ns.SetDetail(True); g.tick(10)
G.GPS3D_DB.modelRange = None; ns.ModelsChanged(); g.tick(5)
R = int(ns.ModelSetting('modelRange'))

# ---- M6: the building check, the game refusing WMOs ----
g2 = Game(wmo=False)
ns2, st2 = g2.ns, g2.ns.modelState
g2.open3d(); g2.free_view(GX, GY, 500); g2.tick(6)
testing = str(st2.wmo)
L2 = g2.L
L2.execute("""
SANDBOX_COVERLOG = {}
local ns = SANDBOX.namespaces['GPS3D']
local orig = ns.ModelsCover
ns.ModelsCover = function(x0, y1) local r = orig(x0, y1); SANDBOX_COVERLOG[#SANDBOX_COVERLOG + 1] = r; return r end
""")
ns2.Render()
gave_way_testing = any(bool(r) for r in g2.G.SANDBOX_COVERLOG.values())
wmo_during = sum(1 for a in g2.actors() if g2.G.GPS3D_API.ModelInfo(a['fdid'])[3])
g2.tick(30 * (int(ns2.modelConst.WMO_WAIT) + 2))
chat2 = g2.chat()
L2.execute('wipe(SANDBOX_COVERLOG)'); ns2.Render()
gave_way_no = any(bool(r) for r in g2.G.SANDBOX_COVERLOG.values())
wmo_after = sum(1 for a in g2.actors() if g2.G.GPS3D_API.ModelInfo(a['fdid'])[3])
props_after = len(g2.actors()) - wmo_after
check('building check while it runs: "testing", the buildings are tried, the simplified shapes stay drawn', testing == 'testing' and wmo_during > 0 and not gave_way_testing, f'{testing}, {wmo_during} tried')
check('the game refusing buildings: "no" after the wait, said in chat, saved; simplified shapes stay, no building actors, props still shown',
      st2.wmo == 'no' and 'does not draw buildings' in chat2 and g2.G.GPS3D_DB.wmoCheck == 'no' and not gave_way_no and wmo_after == 0 and props_after > 0,
      f'{st2.wmo}, {wmo_after} buildings, {props_after} props')
# next session, same build: the saved answer, no new check; /gps3d models wmo checks again
g2.G.SANDBOX_WMO = True
st2.wmo = None
ns2.ModelsChanged(); g2.tick(15)
still_no = str(st2.wmo)
g2.G.SlashCmdList.GPS3D('models wmo'); g2.tick(40)
check('the saved answer is used for the same build; /gps3d models wmo checks again (and now finds them)', still_no == 'no' and st2.wmo == 'yes', f'{still_no} -> {st2.wmo}')

# ---- M7: loading and failing ----
g3 = Game()
g3.G.SANDBOX.modelLoadDelay = 1.0
g3.open3d(); g3.free_view(GX, GY, 300); g3.tick(8)
loading = int(g3.ns.modelState.loading)
g3.tick(40)
check('models load after a while: counted as loading, then loaded', loading > 0 and int(g3.ns.modelState.loading) == 0, f'{loading} loading, then {g3.ns.modelState.loading}')
g3.G.SANDBOX.modelLoadDelay = 1000
g3.ns.cam.x = g3.ns.cam.x + 900; g3.ns.Render(); g3.tick(30 * (int(g3.ns.modelConst.LOAD_WAIT) + 2))
failed = int(g3.ns.modelState.failed)
bad_fdids = sum(1 for _ in g3.ns.modelState.bad.keys())
g3.ns.cam.x = g3.ns.cam.x + 30; g3.ns.Render(); g3.tick(10)
chosen_bad = [e for e in g3.entries() if g3.ns.modelState.bad[e.fdid]]
check('a model that never loads counts as failed and is not chosen again', failed > 0 and bad_fdids > 0 and not chosen_bad, f'{failed} failed, {bad_fdids} models marked, {len(chosen_bad)} chosen again')

# ---- M8: the debug log and the self-test ----
G.SlashCmdList.GPS('debug on'); g.tick(5)
g.free_view(GX, GY, 300)
for k in range(12): ns.cam.yaw = (ns.cam.yaw + 7) % 360; ns.Render(); g.tick(10)
g.tick(30 * 6)
lines = [str(l) for l in G.GnomishPositioningSystemLog.lines.values()]
perf = [l for l in lines if ' PERF ' in l and 'models:' in l]
view = [l for l in lines if ' VIEW ' in l and 'models:' in l]
mlog = [l for l in lines if ' MODELS ' in l]
check('debug log PERF: models shown (buildings, props), loading, failed, actors, choices and their times, model loads', perf and re.search(r'models: \d+ shown \(\d+ buildings, \d+ props\), \d+ loading, \d+ failed, \d+ actors; \d+ choices, [\d.]+ ms average, [\d.]+ ms worst, \d+ candidates average; \d+ model loads', perf[-1]),
      perf[-1] if perf else str(lines[-3:]))
check('debug log VIEW: the models settings and state', view and 'buildings the game\'s (WMOs load)' in view[-1], view[-1][-200:] if view else '')
g.chat()
G.SlashCmdList.GPS3D('test'); g.tick(30 * 4)
out = g.chat()
check('self-test: the data line (16 maps, every placement) and the state', f'models data: 16 maps' in out and f'{n_lua} placements' in out and 'models: buildings' in out, re.findall(r'models data:[^\n]*', out))
probe = re.findall(r'models: (building \(WMO\)|prop \(M2\)) probe fileID (\d+): set=(\w+) loaded=(\w+) box ([^\n|]*)', out)
check('self-test: a building and a prop probe from the data near the view, set and loaded, with a box', len(probe) == 2 and all(p[2] == 'true' and p[3] == 'true' and 'yd' in p[4] for p in probe), str(probe))
logged = [str(l) for l in G.GnomishPositioningSystemLog.lines.values() if ' TEST ' in str(l) and 'models' in str(l)]
check('self-test lines are in the debug log too', len(logged) >= 4, str(len(logged)))
G.SlashCmdList.GPS('debug off')

# ---- M9: slash commands ----
for cmd, test in [('models props off', lambda: G.GPS3D_DB.props is False), ('models props on', lambda: G.GPS3D_DB.props is True),
                  ('models count 120', lambda: G.GPS3D_DB.modelCount == 120), ('models range 900', lambda: G.GPS3D_DB.modelRange == 900),
                  ('models px 9', lambda: G.GPS3D_DB.modelPx == 9), ('models buildings simple', lambda: G.GPS3D_DB.buildingModels == 'simple'),
                  ('models buildings game', lambda: G.GPS3D_DB.buildingModels == 'game')]:
    G.SlashCmdList.GPS3D(cmd); g.tick(3)
    if not test(): check(f'/gps3d {cmd}', False); break
else:
    check('/gps3d models props/count/range/px/buildings change the settings', True)
out = g.chat()
check('/gps3d models prints the state', 'models: buildings' in out)
# the rotation fixes for the in-game check: turn every model, flip or drop the lean
g.free_view(GX, GY, 300); g.tick(10)
a0 = {key(find(a)): a for a in g.actors() if find(a)}
G.SlashCmdList.GPS3D('models turn 90'); g.tick(5)
a1 = [a for a in g.actors() if find(a)]
turned = all(angdiff(a['yaw'], find(a)['yaw'] + math.pi / 2) < 0.002 for a in a1)
G.SlashCmdList.GPS3D('models tilt flip'); g.tick(5)
a2 = [a for a in g.actors() if find(a)]
flipped = all(angdiff(a['pitch'], -find(a)['pitch']) < 0.002 and angdiff(a['roll'], -find(a)['roll']) < 0.002 for a in a2) and any(abs(find(a)['pitch']) > 0.01 for a in a2)
G.SlashCmdList.GPS3D('models tilt off'); g.tick(5)
upright = all(a['pitch'] == 0 and a['roll'] == 0 for a in g.actors() if find(a))
G.SlashCmdList.GPS3D('models turn 0'); G.SlashCmdList.GPS3D('models tilt normal'); g.tick(5)
back = all(angdiff(a['yaw'], find(a)['yaw']) < 0.002 and angdiff(a['pitch'], find(a)['pitch']) < 0.002 for a in g.actors() if find(a))
out = g.chat()
check('/gps3d models turn 90, tilt flip / off / normal: every model turned, its lean reversed, dropped, and back; shown in the state', turned and flipped and upright and back and 'turned 90 degrees, tilt flip' in out,
      f'{turned} {flipped} {upright} {back}')
for k in ('modelCount', 'modelRange', 'modelPx'): G.GPS3D_DB[k] = None
ns.ModelsChanged()
G.SlashCmdList.GPS3D('budget 3200'); g.tick(2)
check('other /gps3d commands still work', 'grid triangles per frame' in g.chat())

# ---- M10: another map, no data, cost ----
ns.SetCamMode('free'); ns.cam.map = 1; ns.cam.x, ns.cam.y = 40.5 * TILE, -30.5 * TILE; ns.cam.th = ns.GroundHeight(ns.cam.x, ns.cam.y); ns.Render(); g.tick(15)
on_map1 = [a for a in g.actors()]
check('another map: its own models, none of the last map\'s', on_map1 and all(math.floor(a['x'] / TILE) in range(30, 50) for a in on_map1), f'{len(on_map1)} shown')
g4 = Game(with_models=False)
g4.open3d(); g4.free_view(GX, GY, 300); g4.tick(20)
g4.G.SlashCmdList.GPS3D('test'); g4.tick(30 * 4)
out4 = g4.chat()
check('without the model data: no models, no errors, the self-test says 0', not g4.actors() and 'models data: 0 maps' in out4 and 'Lua error' not in out4)
# the rollback note's "way 1": simplified shapes and no props draw what the 3D view drew before the models
def views(game, off):
    if off:
        game.G.SlashCmdList.GPS3D('models buildings simple'); game.G.SlashCmdList.GPS3D('models props off')
    game.open3d(); out = []
    for (x, y, d, p, yw) in [(32.3, 49.55, 300, 89.9, 0), (31.0, 48.4, 450, 50, 30), (32.3, 48.3, 700, 60, 200)]:
        game.free_view(x * TILE, -y * TILE, d, pitch=p, yaw=yw); game.tick(20); game.ns.Render()
        st_ = game.ns.stats
        out.append((int(st_.tiles), int(st_.tris), int(st_.detail), int(st_.detailTris), sum(1 for a in game.actors())))
    return out
before_v = views(Game(before=True), False)
off_v = views(Game(), True)
check('switched off (simplified shapes, no props), the 3D view draws what it drew before the models (tiles, triangles, building blocks; no game models)', before_v == off_v and all(v[4] == 0 for v in off_v),
      f'before {before_v}, now {off_v}')
# cost in the sandbox (native Lua, not the game): the choice, and frames with and without models
import time
g.free_view(GX, GY, 400, pitch=55, yaw=30); g.tick(30)
st.perf.picks, st.perf.ms, st.perf.worst = 0, 0, 0
for k in range(30):
    ns.cam.yaw = (ns.cam.yaw + 3) % 360; ns.Render(); g.tick(4)
picks, ms, worst = int(st.perf.picks), float(st.perf.ms), float(st.perf.worst)
check('choices are made at most 10 times a second while the view keeps turning', picks <= 30 * 4 / 30 * 10 + 1 and picks > 0, f'{picks} choices in 4 s')
print(f'COST: choice {ms / max(picks, 1):.2f} ms average, {worst:.2f} ms worst over {picks} choices (tilted, 400 yd, Goldshire); {st.shown} shown, {len(st.pool)} actors')

# ---- mutations: each must make its check fail ----
if not MUT:
    import subprocess
    for name, (_, target) in MUTATIONS.items():
        r = subprocess.run([sys.executable, __file__, '--quiet'], env={**os.environ, 'GPS_MUTATION': name}, capture_output=True, text=True, timeout=900)
        failed = [l for l in r.stdout.splitlines() if l.startswith('FAIL')]
        check(f'mutation "{name}" is caught by "{target}"', any(target in l for l in failed), f'{len(failed)} checks failed: ' + '; '.join(l[5:60] for l in failed[:3]))

print()
print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed')
if errors: print('ERRORS', errors[:5])
