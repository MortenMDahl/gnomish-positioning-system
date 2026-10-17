# GatherMate2's nodes on GPS's 2D map and in the 3D view (Compat.lua, GPS3D's UpdateAddonPins), on the
# sandbox engine with both addons and the stand-in of GatherMate2 (fixtures/gathermate2_standin.lua,
# its public functions as GatherMate2 has them). Where each node is drawn is checked against the
# game's own conversion of its zone coordinates (C_Map.GetWorldPosFromMapPos, the sandbox's zone
# data), node by node; then GatherMate2's filters and settings, its tooltip and right-click, updates,
# the caps, the setting, and GPS without GatherMate2. With GATHERMATE_SRC pointing at a GatherMate2
# checkout, also checks that no line of GatherMate2's code is in GPS's files.
# Usage: python test_compat.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os, sys, math, glob
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
TILE = 1600 / 3
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
GPS_FILES = toc_files(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))
GPS3D_FILES = toc_files(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc'))
W, H = 1280, 800
results, errors = [], []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

class Game:
    def __init__(self, gathermate=True):
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        if gathermate:
            G.SANDBOX_LOAD('GatherMate2', 'gathermate2_standin.lua', open(os.path.join(HERE, 'fixtures', 'gathermate2_standin.lua')).read())
            G.SANDBOX_LOADED('GatherMate2')
        for addon, files in [('GnomishPositioningSystem', GPS_FILES), ('GPS3D', GPS3D_FILES)]:
            for f in files:
                if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        G.SANDBOX_PLAYER(-9464, 62, 0, 0, 1.0, 'Elwynn Forest', 'Goldshire', 1429, 0.42, 0.65)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); self.tick(3)
        self.ns, self.ns3 = G.SANDBOX.namespaces['GnomishPositioningSystem'], G.SANDBOX.namespaces['GPS3D']
        self.chat()
    def tick(self, n=1):
        for _ in range(n): self.G.SANDBOX_TICK(1 / 30, W, H)
    def chat(self):
        c = str(self.G.SANDBOX_CHAT() or '')
        if c: errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l)
        return c

g = Game()
G, ns, ns3 = g.G, g.ns, g.ns3
GM = G.GM_STANDIN.GM
Disp = GM.modules.Display
# nodes around Goldshire (Elwynn Forest, uiMap 1429), a Fishing node (GatherMate2 does not show Fishing
# here), a node in Westfall (1436)
NODES = [(1429, 'Mining', 201, 0.41, 0.64), (1429, 'Mining', 299, 0.43, 0.655), (1429, 'Herb Gathering', 401, 0.40, 0.67),
         (1429, 'Herb Gathering', 402, 0.445, 0.63), (1429, 'Mining', 202, 0.47, 0.70), (1429, 'Fishing', 501, 0.42, 0.66), (1436, 'Mining', 202, 0.50, 0.50)]
for z, t, i, x, y in NODES: G.GM_STANDIN.AddNode(z, t, i, x, y)
Disp.UpdateWorldMap(Disp)  # (GatherMate2 updates its map after new nodes; Blizzard's map is not shown here)

def world_grid(zone, x, y):
    """The game's conversion (not GPS's): zone coordinates -> world -> GPS's grid."""
    v = G.CreateVector2D(x, y)
    cont, w = G.C_Map.GetWorldPosFromMapPos(zone, v)
    gx, gy = ns.WorldToGrid(w.x, w.y)
    return cont, gx, gy
def shown2d():
    out = []
    for p in ns.compat.pins2D.values():
        if p._shown:
            l, b, r, t = G.SANDBOX.rect(p)
            out.append({'pin': p, 'x': (l + r) / 2, 'y': (b + t) / 2, 'title': str(p.title), 'w': r - l})
    return out

# ---- 2D ----
G.GPS_API.OpenNamed('2D'); g.tick(5)
v = ns.view
_, cgx, cgy = world_grid(1429, 0.43, 0.66)
v.follow, v.map, v.cx, v.cy, v.scale = False, 0, cgx, cgy, 400
ns.Layout(); g.tick(2)
cl, cb, cr, ct = G.SANDBOX.rect(ns.canvas)
exp = {}
for z, t, i, x, y in NODES:
    if z != 1429 or t == 'Fishing': continue
    cont, gx, gy = world_grid(z, x, y)
    px, py = ns.GridToScreen(gx, gy)
    if 0 <= px <= cr - cl and 0 <= py <= ct - cb:
        exp[(round(cl + px, 1), round(ct - py, 1))] = str(GM.names[t][GM.nodeIDReplacementMap[i] or i])
got = shown2d()
match = all(any(abs(p['x'] - ex) < 0.6 and abs(p['y'] - ey) < 0.6 and p['title'] == title for p in got) for (ex, ey), title in exp.items())
check('2D: every visible node in view drawn where the game puts its zone coordinates (to the half pixel), with its name; Fishing not (GatherMate2\'s filter)', len(got) == len(exp) == 5 and match,
      f'{len(got)} drawn, {len(exp)} expected')
p0 = got[0]['pin']
check('2D pins: GatherMate2\'s template, its texture for the node, 12 px x its scale, its alpha, mouse on', p0.gpsTemplate and p0.texture._file and p0.texture._file.startswith('interface\\gpssandbox\\gm_') and abs(got[0]['w'] - 12) < 0.01 and p0._mouse,
      f'{p0.texture._file} {got[0]["w"]}')
p0._scripts.OnEnter(p0); tip = [str(x) for x in G.GameTooltip.GetLines(G.GameTooltip).values()]; p0._scripts.OnLeave(p0)
G.SANDBOX_MOUSE('move', got[0]['x'], got[0]['y'], None, 0)
p0._scripts.OnMouseUp(p0, 'RightButton')
cl_ = G.GM_STANDIN.calls.click
check('2D: hover shows GatherMate2\'s tooltip, right-click opens its menu (its OnClick, with the node\'s zone and coords)', tip == [got[0]['title']] and len(cl_) == 1 and cl_[1].button == 'RightButton' and cl_[1].zone == 1429 and cl_[1].coords is not None,
      f'{tip} {len(cl_)}')
GM.db.profile.scale, GM.db.profile.alpha = 1.5, 0.6
Disp.UpdateWorldMap(Disp); g.tick(36)
got = shown2d()
check('2D: GatherMate2\'s icon scale and alpha followed after it updates its map', got and all(abs(p['w'] - 18) < 0.01 and abs(p['pin']._alpha - 0.6) < 1e-6 for p in got), f'{got[0]["w"] if got else None}')
GM.db.profile.scale, GM.db.profile.alpha = 1.0, 1
G.GM_STANDIN.AddNode(1429, 'Herb Gathering', 401, 0.425, 0.645)
Disp.UpdateWorldMap(Disp); g.tick(36)
check('2D: a new node appears when GatherMate2 updates its map', len(shown2d()) == 6, str(len(shown2d())))
# a node GatherMate2 records while you play: it only schedules a minimap update (ScheduleUpdate)
G.GM_STANDIN.AddNode(1429, 'Mining', 202, 0.435, 0.675)
Disp.ScheduleUpdate(Disp); g.tick(36)
n_sched = len(shown2d())
check('2D: a node recorded while playing (GatherMate2 then only schedules its minimap update) appears too', n_sched == 7, str(n_sched))
GM.show['Herb Gathering'] = 'never'; Disp.UpdateWorldMap(Disp); g.tick(36)
n_noherb = len(shown2d())
GM.show['Herb Gathering'] = 'always'; GM.db.profile.showWorldMap = False; Disp.UpdateWorldMap(Disp); g.tick(36)
n_nomap = len(shown2d())
GM.db.profile.showWorldMap = True; Disp.UpdateWorldMap(Disp); g.tick(36)
check('2D: GatherMate2\'s filters: herbs hidden there -> only ores here; its world map off -> none', n_noherb == 4 and n_nomap == 0, f'{n_noherb}, {n_nomap}')
v.scale = 30; ns.Layout(); g.tick(1)
n_far = len(shown2d())
v.scale = 400; ns.Layout(); g.tick(1)
check('2D: zoomed out (30 px per tile, a continent across the window): no nodes; zoomed in again: back', n_far == 0 and len(shown2d()) == 7, f'{n_far}')

# ---- 3D ----
G.GPS_API.OpenNamed('3D'); g.tick(10)
c = ns3.cam
_, pgx, pgy = world_grid(1429, 0.43, 0.66)
ns3.SetCamMode('free'); ns3.SetTopDown(True, True)
c.map, c.x, c.y, c.dist = 0, pgx * TILE, -pgy * TILE, 400
c.th = ns3.GroundHeight(c.x, c.y); ns3.Render(); g.tick(2)
pins3 = [p for p in ns3.addonPins.values() if p._shown]
ok3, bad3 = 0, []
cw, chh = ns3.canvas.GetSize(ns3.canvas)
c3l, c3b, c3r, c3t = G.SANDBOX.rect(ns3.canvas)
for p in pins3:
    n = p.gpsNode
    x, y = n.gx * TILE, -n.gy * TILE
    sx, sy, _ = ns3.Project(x, y, ns3.GroundHeight(x, y))
    l, b, r, t = G.SANDBOX.rect(p)
    if sx is not None and abs((l + r) / 2 - (c3l + c3r) / 2 - sx) < 0.6 and abs((b + t) / 2 - (c3b + c3t) / 2 - sy) < 0.6: ok3 += 1
    else: bad3.append(str(n.title))
check('3D: the nodes around the view, each on the ground where the camera projects it (the same projection as the terrain), named', len(pins3) == 7 and ok3 == 7, f'{len(pins3)} shown, {ok3} placed right {bad3}')
c.dist = 2500; ns3.Render()
far3 = sum(1 for p in ns3.addonPins.values() if p._shown)
c.dist = 400; c.x = c.x + 900; ns3.Render()
away3 = sum(1 for p in ns3.addonPins.values() if p._shown)
c.x = c.x - 900; ns3.Render()
check('3D: none with the camera far out (2,500 yd), none 900 yd away from them (range 700 yd); back again', far3 == 0 and away3 == 0 and sum(1 for p in ns3.addonPins.values() if p._shown) == 7, f'{far3}, {away3}')
# the setting
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'false'); g.tick(2); ns3.Render()
off3 = sum(1 for p in ns3.addonPins.values() if p._shown)
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'true'); g.tick(2); ns3.Render()
on3 = sum(1 for p in ns3.addonPins.values() if p._shown)
G.GPS_API.OpenNamed('2D'); g.tick(3); v.follow, v.map, v.cx, v.cy, v.scale = False, 0, cgx, cgy, 400; ns.Layout()
on2 = len(shown2d())
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'false'); g.tick(2); ns.Layout()
off2 = len(shown2d())
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'true'); g.tick(2); ns.Layout()
check('setting "Other addons\' map markers" off: none in 3D or 2D; on: back', off3 == 0 and on3 == 7 and off2 == 0 and on2 == 7 and len(shown2d()) == 7, f'3D {off3}/{on3}, 2D {off2}/{on2}')
# caps: 2,000 nodes in view
import random
random.seed(3)
for k in range(2000): G.GM_STANDIN.AddNode(1429, 'Mining', 201, 0.40 + random.random() * 0.06, 0.62 + random.random() * 0.08)
Disp.UpdateWorldMap(Disp); g.tick(36); ns.Layout()
cap2 = len(shown2d())
G.GPS_API.OpenNamed('3D'); g.tick(5)
ns3.SetCamMode('free'); c.map, c.x, c.y, c.dist = 0, pgx * TILE, -pgy * TILE, 600; ns3.Render()
cap3 = sum(1 for p in ns3.addonPins.values() if p._shown)
import time
t0 = time.perf_counter()
for k in range(30): c.yaw = (c.yaw + 2) % 360; ns3.Render()
ms3 = (time.perf_counter() - t0) * 1000 / 30
check('caps with 2,000 nodes in view: 800 on the 2D map, 400 in the 3D view', cap2 == 800 and cap3 == 400, f'{cap2}, {cap3}; 3D frame with them {ms3:.1f} ms (sandbox, all of Render)')
# a big database (an imported one): 30,000 nodes in Elwynn; the list is made once per change, at most once a second
for k in range(28000): G.GM_STANDIN.AddNode(1429, 'Herb Gathering', 402, random.random() * 0.98, random.random() * 0.98)
Disp.UpdateWorldMap(Disp); g.tick(36)
c.x = c.x + 1; ns3.Render()
nbig = sum(1 for _ in ns.compat.nodes.list.values())
check('a big database (30,000 nodes on the map): the list is made in one go when GatherMate2 changes (time in the debug log and /gps test)', nbig > 29000 and ns.compat.rebuildMs is not None,
      f'{nbig} nodes, list made in {ns.compat.rebuildMs:.0f} ms (sandbox, native Lua)')
burst0 = ns.compat.nodes.stamp
for k in range(10): Disp.ScheduleUpdate(Disp); g.tick(1)
burst1 = ns.compat.nodes.stamp
g.tick(40)
check('a burst of 10 updates within a third of a second: one rebuild at once at most, the rest a second later (one more)', burst1 - burst0 <= 1 and ns.compat.nodes.stamp - burst1 == 1, f'{burst1 - burst0} at once, {ns.compat.nodes.stamp - burst1} later')
# self-test
G.SlashCmdList.GPS('test'); g.tick(3)
out = g.chat()
want_n = 0
for z in (1429, 1436):  # the zones of map 0 that have nodes here
    for t in ('Mining', 'Herb Gathering'):
        d = GM.gmdbs[t][z]
        want_n += sum(1 for _ in d.keys()) if d is not None else 0
check('/gps test: GatherMate2\'s nodes on this map (all of its shown types in every zone of the map)', f'other addons: GatherMate2: {want_n} nodes on this map' in out, [l for l in out.split('\n') if 'GatherMate2:' in l] + [want_n])

# ---- without GatherMate2 ----
g2 = Game(gathermate=False)
G2 = g2.G
G2.GPS_API.OpenNamed('2D'); g2.tick(3)
v2 = g2.ns.view
v2.follow, v2.map, v2.cx, v2.cy, v2.scale = False, 0, cgx, cgy, 400; g2.ns.Layout()
G2.GPS_API.OpenNamed('3D'); g2.tick(5); g2.ns3.Render()
G2.SlashCmdList.GPS('test'); g2.tick(3)
out2 = g2.chat()
check('without GatherMate2: nothing drawn, nothing fails, the self-test says so', sum(1 for p in g2.ns.compat.pins2D.values() if p._shown) == 0 and sum(1 for p in g2.ns3.addonPins.values() if p._shown) == 0
      and 'GatherMate2 not installed' in out2 and 'map layers on the traditional map: none found' in out2)

# ---- no GatherMate2 code in GPS ----
src = os.environ.get('GATHERMATE_SRC')
if src and os.path.isdir(src):
    # copied code shows as runs of lines; single common lines (GameTooltip:SetOwner(...), SetTexCoord(0, 1, 0, 1))
    # are the game's idioms, not GatherMate2's. Checked: every run of 3 consecutive code lines with one of 25+ characters.
    def runs(path):
        lines = [l.strip() for l in open(path, encoding='utf-8', errors='replace') if l.strip() and not l.strip().startswith('--')]
        return {tuple(lines[i:i + 3]) for i in range(len(lines) - 2) if max(len(x) for x in lines[i:i + 3]) >= 25}  # (runs of only short lines such as end / end / end say nothing)
    theirs = set()
    for f in glob.glob(os.path.join(src, '*.lua')): theirs |= runs(f)
    ours = []
    for f in glob.glob(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', '*.lua')) + glob.glob(os.path.join(ROOT, 'prototypes', 'GPS3D', '*.lua')):
        ours += [(os.path.basename(f), r) for r in runs(f) & theirs]
    check(f'no code of GatherMate2 in GPS\'s files (no run of 3 lines shared with its {len(theirs)} runs)', not ours, str(ours[:2]))
check('no Lua errors', not errors, '; '.join(errors[:3]))
print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed')
