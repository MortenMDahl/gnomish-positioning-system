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

# ---- Q6: objective areas in 3D (J5). The stand-in's quest-area frame answers its hit-test from known
# shapes (quest 33: two joined ellipses, a waisted shape; quest 38: an ellipse), worked out here from
# the stand-in maps' boxes, independently of GPS.
import math, time
QA = ns2.questAreas
layer = ns2.decal.GetParent(ns2.decal)
def area_key(qid): return qid * 100000 + quests[qid].zone
def shape_of(qid):
    s = Q.areaShapes[area_key(qid)]
    return s if s is not None and not s.none else None
def zone_uv(zone, gx, gy):
    g0, g1 = zone_to_grid(zone, 0, 0), zone_to_grid(zone, 1, 1)
    return (gx - g0[0]) / (g1[0] - g0[0]), (gy - g0[1]) / (g1[1] - g0[1])
def true_inside(qid, gx, gy):
    q = quests[qid]; u, v = zone_uv(q.zone, gx, gy)
    for a in (q.area, q.area2):
        if a is not None and ((u - a[1]) / a[3]) ** 2 + ((v - a[2]) / a[4]) ** 2 <= 1: return True
    return False
def ring(qid, gx, gy, r_yd, want):  # every point r_yd round (gx, gy) inside (want True) or outside (want False)
    return all(true_inside(qid, gx + r_yd * math.cos(k * math.pi / 8) / TILE, gy + r_yd * math.sin(k * math.pi / 8) / TILE) == want for k in range(16))
def drawn_fills(qid=None):
    return [t for t in lua_list(QA.fills) if t.on and (qid is None or t.shape.questID == qid)]
def pieces(s, ks):
    out = []
    for k in ks:
        vs = [s.p1[k], s.p2[k], s.p3[k], s.p4[k]]
        out.append([(s.gx[v], s.gy[v]) for v in vs])
    return out
def in_piece(poly, x, y):
    sign = 0
    for i in range(4):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
        if x1 == x2 and y1 == y2: continue
        c = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(c) < 1e-12: continue
        if sign == 0: sign = 1 if c > 0 else -1
        elif (c > 0) != (sign > 0): return False
    return True
def coverage(qid):
    s = shape_of(qid)
    drawn = pieces(s, sorted({t.piece for t in drawn_fills(qid)}))
    cell, tol = s.cell, s.cell / 8
    step = cell / 2 / TILE
    deep = covered_deep = far_out = spills = 0
    worst_spill = 0.0
    y = s.y0 - 2 * cell / TILE
    while y <= s.y1 + 2 * cell / TILE:
        x = s.x0 - 2 * cell / TILE
        while x <= s.x1 + 2 * cell / TILE:
            inside = true_inside(qid, x, y)
            cov = any(in_piece(p, x, y) for p in drawn)
            if inside and ring(qid, x, y, cell, True):
                deep += 1; covered_deep += cov
            if not inside and ring(qid, x, y, tol, False):
                far_out += 1
                if cov: spills += 1
            x += step
        y += step
    return deep, covered_deep, far_out, spills, s.np, len(drawn), cell
def wait_area(qid, frames=120):
    for _ in range(frames):
        if shape_of(qid) is not None and not lua_list(Q.areaJobs): return True
        tick(1)
    return shape_of(qid) is not None
def look_at(qid, dist):
    gx, gy = want_grid[qid]
    q = quests[qid]
    if q.area is not None:
        g = zone_to_grid(q.zone, q.area[1], q.area[2]); gx, gy = g
    cam.x, cam.y, cam.dist = gx * TILE, -gy * TILE, dist
    ns2.Render(); tick(1)

def area_checks():
    G.C_SuperTrack.SetSuperTrackedQuestID(33); settle()
    ns2.SetCamMode('free'); ns2.SetTopDown(True, True)
    before_hits = S.blobHits
    look_at(33, 900)
    found = wait_area(33); tick(2); ns2.Render(); tick(1)
    s33 = shape_of(33)
    check('3D area: the tracked quest\'s (33) area found through the area frame\'s hit-test, frame hidden', found and s33.way == 'hidden' and s33.np > 50,
          f'way {s33 and s33.way}, {s33 and s33.np} pieces, {s33 and len(lua_list(s33.ls))} outline(s)')
    print(f'SAMPLING quest 33: {s33.calls} hit-tests ({S.blobHits - before_hits} counted by the stand-in), {s33.ms:.1f} ms over {s33.frames} frames, grid {s33.nx}x{s33.ny} cells of {s33.cell:.1f} yd')
    deep, cov, far, spills, np_, nd, cell = coverage(33)
    check('3D area: covers the true shape (every point more than a cell inside covered, none more than 1/8 cell outside), straight down',
          deep > 100 and cov == deep and spills == 0 and nd == np_, f'{cov} of {deep} deep points covered, {spills} of {far} outside points covered; {nd} of {np_} pieces drawn, cell {cell:.1f} yd')
    outlines = len(lua_list(s33.ls))
    check('3D area: one closed border round the waisted shape, drawn as a glow each side', outlines == 1 and QA.nEdge == 2 * len(lua_list(s33.lv)), f'{outlines} outline(s), {QA.nEdge} border pieces for {len(lua_list(s33.lv))} edge points')
    def ground_error(qid):
        s = shape_of(qid)
        worst_h = worst_px = 0.0
        BASE = {1: (-0.5, 0.5), 2: (-0.5, -0.5), 3: (0.5, 0.5), 4: (0.5, -0.5)}
        for t in drawn_fills(qid):
            k = t.piece
            for corner, v in ((1, s.p1[k]), (2, s.p2[k]), (4, s.p3[k]), (3, s.p4[k])):
                x, y = s.gx[v] * TILE, -s.gy[v] * TILE
                h = s.h3d[v]
                worst_h = max(worst_h, abs(h - ns2.GroundHeight(x, y, 0)))
                p = proj3(x, y, h)
                ox_, oy_ = t.GetVertexOffset(t, corner)
                sx, sy = BASE[corner][0] + ox_, BASE[corner][1] + oy_
                worst_px = max(worst_px, abs(sx - p[1]), abs(sy - p[2]))
        return worst_h, worst_px
    proj3 = L.eval('function(f) return function(x, y, h) local a, b, c = f(x, y, h); return { a, b, c } end end')(_proj)
    wh, wp = ground_error(33)
    check('3D area: on the ground: each drawn corner at the ground height under it, where the view projects it', wh < 0.01 and wp < 0.5, f'worst {wh:.4f} yd, {wp:.3f} px')
    ns2.SetTopDown(False, True); cam.yaw = (cam.yaw + 70) % 360; cam.pitch = 50; cam.dist = 700; ns2.Render(); tick(1)
    wh2, wp2 = ground_error(33)
    deep2, cov2, far2, spills2, _, nd2, _ = coverage(33)
    check('3D area: tilted 40 degrees and turned: still on the ground, covering the shape', wh2 < 0.01 and wp2 < 0.5 and nd2 > 0.8 * np_ and spills2 == 0,
          f'worst {wh2:.4f} yd, {wp2:.3f} px; {nd2} of {np_} pieces face the camera, {cov2} of {deep2} deep points covered')
    bucket_levels = [f.GetFrameLevel(f) for f in lua_list(ns2.bucketFrames)]
    t0_ = drawn_fills(33)[0]
    own = t0_.GetParent(t0_)  # the frame the area's textures are drawn in
    lv_ = own.GetFrameLevel(own)
    check('3D area: over the ground, under your arrow, the models and the quest markers',
          lv_ > max(bucket_levels) and lv_ < ns2.questLayer.GetFrameLevel(ns2.questLayer) and lv_ < ns2.scene.GetFrameLevel(ns2.scene)
          and (own != layer or (t0_._layer == 2 and ns2.decal._layer == 3)) and lv_ <= layer.GetFrameLevel(layer),
          f'area {lv_} (draw layer {t0_._layer}), ground up to {max(bucket_levels)}, your arrow {layer.GetFrameLevel(layer)} (draw layer {ns2.decal._layer}), models {ns2.scene.GetFrameLevel(ns2.scene)}, markers {ns2.questLayer.GetFrameLevel(ns2.questLayer)}')
    # frame time with and without the area (same view, 60 turns)
    def frame_ms(n=60):
        t = time.perf_counter()
        for _ in range(n):
            cam.yaw = (cam.yaw + 6) % 360; ns2.Render()
        return (time.perf_counter() - t) * 1000 / n
    def area_ms(n=200):  # the area's own share: projected and drawn again after each turn
        t = time.perf_counter()
        for _ in range(n):
            cam.yaw = (cam.yaw + 6) % 360; ns2.UpdateQuestAreas()
        return (time.perf_counter() - t) * 1000 / n
    cam.dist = 900; ns2.Render(); frame_ms(10)
    with_area = frame_ms()
    upd = ns2.UpdateQuestAreas; ns2.UpdateQuestAreas = None
    without_area = frame_ms()
    ns2.UpdateQuestAreas = upd; ns2.Render()
    with_area2 = frame_ms()
    own = area_ms()
    print(f'FRAME 3D (sandbox, Lua 5.4, 60 turns): {with_area:.2f} / {with_area2:.2f} ms with the area ({QA.nFill} fill + {QA.nEdge} border pieces), {without_area:.2f} ms without; the area itself {own:.3f} ms per frame')
    # hovering a 3D marker: its area too (Westfall's quest 38), leaving removes it
    ns2.SetTopDown(True, True); look_at(38, 900)
    p38 = {p.gpsQuestID: p for p in lua_list(ns2.questPins) if shown(p)}.get(38)
    p38._scripts.OnEnter(p38); wait_area(38); ns2.Render(); tick(1)
    hov = sorted({t.shape.questID for t in drawn_fills()})
    deep38, cov38, far38, spills38, np38, nd38, _ = coverage(38)
    p38._scripts.OnLeave(p38); tick(1); ns2.Render()
    after = sorted({t.shape.questID for t in drawn_fills()})
    check('3D area: hovering a marker draws that quest\'s area too (Westfall\'s 38, covering its shape), leaving removes it',
          hov == [38] and cov38 == deep38 > 50 and spills38 == 0 and after == [] and QA.nShapes == 1,
          f'hovered {hov} ({cov38} of {deep38} deep, {spills38} spills), after {after}, areas {QA.nShapes}')
    # hover, click (the list is re-sorted: this button may show another quest now), leave: no hover left
    look_at(33, 3000)
    p7 = {p.gpsQuestID: p for p in lua_list(ns2.questPins) if shown(p)}.get(7)
    p7._scripts.OnEnter(p7); p7._scripts.OnClick(p7, 'LeftButton'); settle(); ns2.Render(); tick(1)
    shows_now = p7.gpsQuestID
    p7._scripts.OnLeave(p7); tick(1)
    check('hover, click, leave: the hovered quest is cleared even when the button shows another quest by then', Q.hovered is None and S.superTracked == 7 and shows_now != 7,
          f'button shows {shows_now} after the click, hovered {Q.hovered}')
    G.C_SuperTrack.SetSuperTrackedQuestID(33); settle()
    look_at(33, 900)
    n_on = len(drawn_fills(33))
    ns1.db.quests = False; Q.Changed(); tick(1); ns2.Render()
    off_setting = len(drawn_fills())
    ns1.db.quests = True; Q.Changed(); tick(1)
    S.cvars.questPOI = False; G.SANDBOX_FIRE('CVAR_UPDATE', 'questPOI'); settle(); ns2.Render()
    off_cvar = len(drawn_fills())
    S.cvars.questPOI = True; G.SANDBOX_FIRE('CVAR_UPDATE', 'questPOI'); settle(); wait_area(33); ns2.Render(); tick(1)
    back = len(drawn_fills(33))
    cam.dist = 40000; ns2.Render(); tick(2)
    planet = bool(ns2.GlobeOn()) and not any(t.IsVisible(t) for t in lua_list(QA.fills) + lua_list(QA.edges))
    cam.dist = 900; ns2.Render(); tick(2)
    check('3D area: none with the setting off, none with questPOI off, hidden on the planet view; back after each',
          n_on > 50 and off_setting == 0 and off_cvar == 0 and back == n_on and planet and all(t.IsVisible(t) for t in drawn_fills(33)) and len(drawn_fills(33)) == n_on,
          f'{n_on} -> setting off {off_setting}, questPOI off {off_cvar}, back {back}; planet: hidden {planet}')
    # the ways round a hit-test that does not answer while the frame is hidden
    def fresh(answers):
        S.blobAnswers = answers
        Q.area.way, Q.area.broken, Q.area.last = None, None, None
        for k in list(Q.areaShapes.keys()): Q.areaShapes[k] = None
        Q.Changed(); tick(1); ns2.Render(); wait_area(33, 200); tick(2); ns2.Render(); tick(1)
        s = shape_of(33)
        return (s.way if s else None), len(drawn_fills(33)), (Q.sampler.IsShown(Q.sampler) if Q.sampler else None)
    w_shown = fresh('shown')
    w_drawn = fresh('drawn')
    w_never = fresh('never')
    st_never = str(Q.AreaStatus())
    w_back = fresh('always')
    check('3D area: hit-test answering only while shown: found at alpha 0; only while drawn: behind the 3D view; never: none drawn; the sampler hidden after',
          w_shown[0] == 'invisible' and w_shown[1] > 50 and w_shown[2] is False and w_drawn[0] == 'behind' and w_drawn[1] > 50 and w_drawn[2] is False
          and w_never[0] is None and w_never[1] == 0 and 'no area found' in st_never and w_back[0] == 'hidden',
          f'shown {w_shown}, drawn {w_drawn}, never {w_never}, always {w_back}; status when never: {st_never[:120]}')
    # the game not answering at all: no hit-test method, or no quest-area frame
    G.SANDBOX_SLASH('/gps debug on'); chat()
    def broken(how):
        Q.sampler = None
        orig = S.makeQuestPOIFrame
        if how == 'nomethod':
            S.makeQuestPOIFrame = L.eval('function(orig) return function(f) orig(f); f.UpdateMouseOverTooltip = false end end')(orig)
        else:
            S.makeQuestPOIFrame = L.eval('function() error("unknown frame type QuestPOIFrame") end')
        fresh('always')
        S.makeQuestPOIFrame = orig
        G.SANDBOX_SLASH('/gps3d test'); tick(100)
        line = [l for l in chat().split('\n') if 'quest areas:' in l]
        return len(drawn_fills()), line[0] if line else ''
    n_nomethod, line_nomethod = broken('nomethod')
    n_noframe, line_noframe = broken('noframe')
    logged = '\n'.join(str(l) for l in lua_list(G.GnomishPositioningSystemLog.lines))
    check('3D area: the game without the hit-test, or without the quest-area frame: nothing drawn, no error, /gps3d test and the debug log say why',
          n_nomethod == 0 and n_noframe == 0 and 'no hit-test (UpdateMouseOverTooltip)' in line_nomethod and 'cannot be made here' in line_noframe
          and '3D areas: the quest-area frame has no hit-test' in logged and '3D areas: the game\'s quest-area frame (QuestPOIFrame) cannot be made' in logged,
          f'{n_nomethod}, {n_noframe}; {line_nomethod[-120:]} | {line_noframe[-120:]}')
    Q.sampler = None; fresh('always')
    G.SANDBOX_SLASH('/gps3d test'); tick(100)
    line_ok = [l for l in chat().split('\n') if 'quest areas:' in l]
    check('/gps3d test: the quest-area line names the way and the last area', line_ok and 'frame hidden' in line_ok[0] and 'quest 33 in zone 1429' in line_ok[0], line_ok[0][-200:] if line_ok else '')
    G.SANDBOX_SLASH('/gps debug off'); chat()
try:
    area_checks()
except Exception as e:  # (on code without 3D areas: the checks above fail, the rest cannot run)
    check('3D area: the remaining area checks ran', False, f'{type(e).__name__}: {e}')
G.C_SuperTrack.SetSuperTrackedQuestID(176); settle()

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
