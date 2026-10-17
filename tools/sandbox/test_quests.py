# Checks your quests on GPS's maps on the sandbox engine (Lua 5.4), with the engine's stand-ins for the
# quest log (7 quests in Elwynn Forest and Westfall), Blizzard's quest button (POIButtonTemplate) and the
# game's quest-area frame (QuestPOIFrame): 2D markers at their world positions (worked out here from
# the stand-in maps' boxes, independently of GPS), following pan and zoom, the tracked quest selected,
# click to track, the tooltip, the setting and Blizzard's questPOI option; the 2D objective area laid
# over its zone's rectangle; the 3D markers at their projected ground points through a pan and a turn;
# and the in-game check lines of /gps test.
# Usage: python test_quests.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
TILE = 1600 / 3
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
L = lupa54.LuaRuntime(); G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
for addon, toc in [('GnomishPositioningSystem', 'Interface/AddOns/GnomishPositioningSystem/GnomishPositioningSystem.toc'), ('GPS3D', 'prototypes/GPS3D/GPS3D.toc')]:
    for f in toc_files(os.path.join(ROOT, toc)):
        if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
W, H = 1280, 800
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
errors = []
def chat():
    c = str(G.SANDBOX_CHAT() or '')
    if c:
        print('CHAT>', c.replace('\n', '\nCHAT> ')[:2500])
        errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l)
    return c
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
def lua_list(t): return [t[i] for i in range(1, len(t) + 1)] if t else []
rect = lambda o: tuple(G.SANDBOX.rect(o))
def centre(o): l, b, r, t = rect(o); return (l + r) / 2, (b + t) / 2
shown = lambda f: bool(f.IsShown(f))
settle = lambda: tick(15)  # quest events are acted on 0.25 s later

G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); tick(2)
ns1, ns2 = G.SANDBOX.namespaces['GnomishPositioningSystem'], G.SANDBOX.namespaces['GPS3D']
Q, S = ns1.quests, G.SANDBOX
view, canvas = ns1.view, ns1.canvas

# where each stand-in quest is, from the stand-in maps' world boxes (top X, bottom X, left Y, right Y)
def zone_to_grid(zone, x, y):
    b = S.uiMaps[zone].box
    X = b[1] - y * (b[1] - b[2]); Y = b[3] - x * (b[3] - b[4])
    return 32 - Y / TILE, 32 - X / TILE
quests = {q.questID: q for q in lua_list(S.quests)}
want_grid = {qid: zone_to_grid(q.zone, q.x, q.y) for qid, q in quests.items()}

def grid_to_screen(gx, gy):  # independent of GPS: canvas top-left + (g - centre) * scale + half size
    l, b, r, t = rect(canvas)
    w, h = r - l, t - b
    return l + (gx - view.cx) * view.scale + w / 2, t - ((gy - view.cy) * view.scale + h / 2)
def pins_2d():
    return [p for p in lua_list(Q.pins2D) if shown(p)]
def worst_2d():
    worst = 0
    for p in pins_2d():
        x, y = centre(p); wx, wy = grid_to_screen(*want_grid[p.gpsQuestID])
        worst = max(worst, abs(x - wx), abs(y - wy))
    return worst

# ---- Q2: 2D markers
G.SANDBOX_SLASH('/gps 2d'); tick(5); chat()
ps = pins_2d()
check('2D: a marker for each of your 7 quests on this map (Elwynn 5, Westfall 2)', sorted(p.gpsQuestID for p in ps) == sorted(quests), str(sorted(p.gpsQuestID for p in ps)))
check('2D: markers are Blizzard\'s quest button (POIButtonTemplate), numbered from the quest log', all(p.SetQuestID is not None and p.questID == p.gpsQuestID for p in ps)
      and {p.gpsQuestID: str(p._label.GetText(p._label)) for p in ps}[7] == '2' and {p.gpsQuestID: str(p._label.GetText(p._label)) for p in ps}[62] == '?')
check('2D: each marker at its world position (within 0.5 px)', worst_2d() < 0.5, f'worst {worst_2d():.3f} px')
view.follow = False; view.cx += 0.37; view.cy -= 0.21; ns1.Layout(); tick(1)
check('2D: after a pan, still at their world positions', worst_2d() < 0.5, f'worst {worst_2d():.3f} px')
l, b, r, t = rect(canvas)
ns1.ZoomAt(300, 200, 2.0); tick(1)
check('2D: after a zoom, still at their world positions', worst_2d() < 0.5 and view.scale > 128, f'worst {worst_2d():.3f} px at {view.scale:.0f} px per tile')
tracked = [p for p in ps if p.selected]
check('2D: the tracked quest (33) is selected and on top', len(tracked) == 1 and tracked[0].gpsQuestID == 33 and all(tracked[0].GetFrameLevel(tracked[0]) > p.GetFrameLevel(p) for p in ps if p.gpsQuestID != 33))
p7 = [p for p in ps if p.gpsQuestID == 7][0]
p7._scripts.OnEnter(p7); tick(1)
tip = lua_list(G.GameTooltip.GetLines(G.GameTooltip))
check('2D: tooltip: title, objectives left, what a click does', tip[:3] == ['Kobold Camp Cleanup', '- Kobold Vermin slain: 6/10', 'Click: track this quest'], str(tip))
p7._scripts.OnLeave(p7); tick(1)
p7._scripts.OnClick(p7, 'LeftButton'); settle(); chat()
sel = {p.gpsQuestID: p.selected for p in pins_2d()}
check('2D: click tracks the quest (Blizzard\'s button), the markers follow', S.superTracked == 7 and sel[7] and not sel[33], f'tracked {S.superTracked}')
ns1.db.quests = False; Q.Changed(); tick(1)
off = len(pins_2d())
ns1.db.quests = True; Q.Changed(); tick(1)
S.cvars.questPOI = False; G.SANDBOX_FIRE('CVAR_UPDATE', 'questPOI'); settle()
cvar_off = len(pins_2d())
S.cvars.questPOI = True; G.SANDBOX_FIRE('CVAR_UPDATE', 'questPOI'); settle()
check('2D: none with the setting off, none with Blizzard\'s quest objectives option off, back after', off == 0 and cvar_off == 0 and len(pins_2d()) == 7, f'{off}, {cvar_off}, {len(pins_2d())}')
ns1.ShowMap(1, False); tick(2)
on_kalimdor = len(pins_2d())
ns1.ShowMap(0, True); view.follow = False; tick(2)
check('2D: none on another map (Kalimdor)', on_kalimdor == 0 and len(pins_2d()) == 7, str(on_kalimdor))

# ---- Q3: 2D objective areas
def areas_shown():
    out = {}
    for zone in (1429, 1436, 1453, 1426):
        f = Q.areas2D[zone]
        if f and shown(f): out[zone] = sorted(q.questID for q in lua_list(f._drawn))
    return out
def area_rect_error(zone):
    f = Q.areas2D[zone]
    l, b, r, t = rect(f)
    x0, y0 = grid_to_screen(*zone_to_grid(zone, 0, 0)); x1, y1 = grid_to_screen(*zone_to_grid(zone, 1, 1))
    return max(abs(l - x0), abs(t - y0), abs(r - x1), abs(b - y1))
check('2D area: the tracked quest\'s (7) in Elwynn\'s quest-area frame', areas_shown() == {1429: [7]} and Q.areas2D[1429].GetMapID(Q.areas2D[1429]) == 1429, str(areas_shown()))
check('2D area: the frame covers Elwynn\'s rectangle on the map (within 0.5 px)', area_rect_error(1429) < 0.5, f'{area_rect_error(1429):.3f} px')
view.cx -= 0.6; view.cy += 0.4; ns1.Layout(); tick(1); ns1.ZoomAt(500, 300, 0.7); tick(1)
check('2D area: after a pan and a zoom, still over Elwynn', area_rect_error(1429) < 0.5, f'{area_rect_error(1429):.3f} px')
p38 = [p for p in pins_2d() if p.gpsQuestID == 38][0]
p38._scripts.OnEnter(p38); tick(1)
hover = areas_shown()
p38._scripts.OnLeave(p38); tick(1)
check('2D area: hovering a marker draws that quest\'s area too (Westfall), leaving removes it', hover == {1429: [7], 1436: [38]} and areas_shown() == {1429: [7]}, f'{hover} -> {areas_shown()}')
check('2D area: the Westfall frame covers Westfall\'s rectangle', area_rect_error(1436) < 0.5, f'{area_rect_error(1436):.3f} px')
G.C_SuperTrack.ClearAllSuperTracked(); settle()
check('2D area: none when nothing is tracked', areas_shown() == {}, str(areas_shown()))
G.C_SuperTrack.SetSuperTrackedQuestID(33); settle()

# ---- Q4: 3D markers
G.SANDBOX_SLASH('/gps 3d'); tick(40); chat()
F2 = G.GPS3D_Frame
cam, c2 = ns2.cam, ns2.canvas
def expected_3d():
    l, b, r, t = rect(c2); cx, cy = (l + r) / 2, (b + t) / 2
    hw, hh = (r - l) / 2 + 16, (t - b) / 2 + 16
    out = {}
    for qid, (gx, gy) in want_grid.items():
        x, y = gx * TILE, -gy * TILE
        p = ns2.Project(x, y, ns2.GroundHeight(x, y, 0))
        if p is not None:
            sx, sy = p[1], p[2]
            if abs(sx) < hw and abs(sy) < hh: out[qid] = (cx + sx, cy + sy)
    return out
def pins_3d(): return {p.gpsQuestID: centre(p) for p in lua_list(ns2.questPins) if shown(p)}
_proj = ns2.Project
ns2.Project = L.eval('function(f) return function(x, y, h) local a, b, c = f(x, y, h); if not a then return nil end return { a, b, c } end end')(_proj)
def compare_3d():
    e, s = expected_3d(), pins_3d()
    worst = max([abs(s[k][0] - e[k][0]) + abs(s[k][1] - e[k][1]) for k in e if k in s] or [0])
    return set(e) == set(s), worst, e, s
ok, worst, e, s = compare_3d()
check('3D: opened on you, the quests near you shown at their projected ground points (within 0.5 px)', ok and len(s) >= 1 and worst < 0.5, f'{sorted(s)} in view, worst {worst:.3f}')
ns2.SetCamMode('free'); cam.dist = 2500; ns2.Render(); tick(1)
ok, worst, e, s = compare_3d()
check('3D: zoomed out over Elwynn, more quests in view, each at its point', ok and len(s) >= 4 and worst < 0.5, f'{sorted(s)} in view, worst {worst:.3f}')
cam.x += 300; cam.y -= 200; ns2.Render(); tick(1)
ok, worst, e, s = compare_3d()
check('3D: after a pan', ok and len(s) >= 3 and worst < 0.5, f'{sorted(s)}, worst {worst:.3f}')
ns2.SetTopDown(False, True); cam.yaw = (cam.yaw + 40) % 360; ns2.Render(); tick(1)
ok, worst, e, s = compare_3d()
check('3D: after a turn and a tilt (45 degrees)', ok and len(s) >= 3 and worst < 0.5, f'{sorted(s)}, worst {worst:.3f}')
cam.dist = 6000; ns2.Render(); tick(1)
ok, worst, e, s = compare_3d()
all_quests_far = len(s)
check('3D: zoomed out, Westfall\'s quests come into view too; quests out of view are hidden', ok and worst < 0.5 and {65, 38} <= set(s), f'{sorted(s)}')
p3 = {p.gpsQuestID: p for p in lua_list(ns2.questPins) if shown(p)}
p3[176]._scripts.OnClick(p3[176], 'LeftButton'); settle(); chat()
sel3 = {p.gpsQuestID: p.selected for p in lua_list(ns2.questPins) if shown(p)}
check('3D: click tracks the quest; the 3D markers follow', S.superTracked == 176 and sel3[176] and not sel3[33], f'tracked {S.superTracked}')
ns1.db.quests = False; Q.Changed(); tick(1)
off3 = len(pins_3d())
ns1.db.quests = True; Q.Changed(); tick(1)
check('3D: none with the setting off, back after', off3 == 0 and len(pins_3d()) == all_quests_far, f'{off3}, {len(pins_3d())}')

# ---- Q5: the in-game check lines
G.SANDBOX_SLASH('/gps test'); tick(100)
out = chat()
ql = [l for l in out.split('\n') if 'quests:' in l]
print('\n'.join(ql))
check('/gps test: the quest check lines (zones, button, area frame, hit-test, look)', len(ql) == 5
      and 'zones on this map, 7 of your quests' in ql[0] and 'tracking 176' in ql[0]
      and 'POIButtonTemplate): made' in ql[1] and 'QuestPOIFrame): made' in ql[2]
      and '-> 3D areas POSSIBLE' in ql[3] and 'shown ' in ql[3] and '4. look' in ql[4] or False, '')
check('no Lua errors', not errors, '; '.join(errors[:3]))
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
raise SystemExit(0 if n == len(results) else 1)
