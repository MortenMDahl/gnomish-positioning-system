# The planet view (GPS3D's Globe.lua): the continents' layout, the sphere's maths, the hand-over from the ground,
# the planet drawn (sea, land, clouds, Maelstrom, glow, your arrow), the controls on it, speed and memory.
# Each of the mutations at the end breaks one piece of Globe.lua and must make its check fail.
# Run: python3 tools/sandbox/test_globe.py   (python3 test_globe.py --mutant N runs one mutation's check)
import lupa.lua54 as lupa54, math, os, sys, time, subprocess, random

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
TILE = 1600 / 3
W, H = 1280, 800

MUTANTS = [
    # (what is broken, old text, new text, the check that must catch it)
    ('the sphere: stereographic without its scale', 'return 2 * qx * k, 2 * qy * k, (1 - s) * k\nend\n-- back from a unit vector to the plane', 'return 2 * qx, 2 * qy, (1 - s) * k\nend\n-- back from a unit vector to the plane', 'maths'),
    ('the camera ignores the straightened tilt', '\tlocal yaw, p = rad(cam.yaw), rad(cam.vp or cam.pitch)\n\tlocal sy_, cy_, sp, cp = sin(yaw), cos(yaw), sin(p), cos(p)\n\tG.fx', '\tlocal yaw, p = rad(cam.yaw), rad(cam.pitch)\n\tlocal sy_, cy_, sp, cp = sin(yaw), cos(yaw), sin(p), cos(p)\n\tG.fx', 'handover'),
    ('picking: the wrong root of the ray and the sphere', 'local s = (-b - sqrt(disc)) / (2 * a)', 'local s = (-b + sqrt(disc)) / (2 * a)', 'pick'),
    ('drag and wheel: the point is not held under the cursor', 'before the move\n\tfor _ = 1, 12 do', 'before the move\n\tfor _ = 1, 0 do', 'controls'),
    ('spinning to the other continent keeps the old map', '	local m = NearestMap(X, Y)\n	if m ~= cam.map then\n		GPS.Log("3D", "planet: view map', '	local m = cam.map\n	if m ~= cam.map then\n		GPS.Log("3D", "planet: view map', 'spin'),
    ('the view does not straighten past the old limit', 'if s > 0 then cam.vp = cam.pitch + ((ns.MAX_PITCH or 89.9) - cam.pitch) * s else cam.vp = nil end', 'cam.vp = nil', 'straighten'),
    ('zooming in over the sea: the point looked at is not drawn onto the map', '	if d >= 1.6 * HANDOVER then return end', '	if true then return end', 'pull'),
    ('instances zoom out to the planet too', 'ns.ZoomMax = function() return Available() and GLOBE_MAX or nil end', 'ns.ZoomMax = function() return GLOBE_MAX end', 'instances'),
    ('the overview images are not whole at the hand-over', 'local atlasA = max(Smooth((tilePx - SWAP_LO) / (SWAP_HI - SWAP_LO)), 1 - Smooth((d - HANDOVER) / (0.25 * HANDOVER)))', 'local atlasA = Smooth((tilePx - SWAP_LO) / (SWAP_HI - SWAP_LO)) * 0.5', 'handover'),
    ('back faces of the planet drawn', 'ok = (bx_ - ax_) * (cy_ - ay_) - (cx_ - ax_) * (by_ - ay_) > 0', 'ok = true', 'planet'),
    ('a drag moves the point looked at in the plane, not round the sphere', '\t\tif G.flat then\n\t\t\tlocal hx, hy = PickPlane(px, py)', '\t\tif true then\n\t\t\tlocal hx, hy = PickPlane(px, py)', 'farspin'),
    ('a drag does not keep the way the view faces from the planet\'s north', 'local kept = north + NorthOffset()', 'local kept = free', 'farspin'),
    ('a flight on the planet goes through the plane', 'if not (active and start.x and target.x and not G.flat and G.t > 0.02) then return nil end', 'if true then return nil end', 'farfly'),
    ('no stop short of the poles', '\t\t\tif abs(oy) > lim then', '\t\t\tif false then', 'pole'),
    ('clouds\' shadows not offset from them', 'local ox, oy = SHADOW_X * CLOUD_H * ppy, SHADOW_Y * CLOUD_H * ppy', 'local ox, oy = 0, 0', 'weather'),
    ('clouds not lit as the planet is', 'local light = LightAt(mx, my, alpha)', 'local light = 1', 'weather'),
    ('southern storms not mirrored', 'mirror = kind == 4 and lat < 0 }', 'mirror = false }', 'weather'),
    ('no lightning', '\tif now >= flash.next then', '\tif false then', 'weather'),
]

mutant = None
if '--mutant' in sys.argv:
    mutant = MUTANTS[int(sys.argv[sys.argv.index('--mutant') + 1])]

L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())
toc = open(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua']), ('GPS3D', gps3d_files)]:
    for f in files:
        src = open(f'{SITE}/addons/{addon}/{f}').read()
        if mutant and f == 'Globe.lua':
            assert src.count(mutant[1]) == 1, ('mutation text not found once', mutant[0])
            src = src.replace(mutant[1], mutant[2])
        ok = G.SANDBOX_LOAD(addon, f, src)
        if not ok: print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')

def chat():
    c = G.SANDBOX_CHAT()
    return c or ''
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
def place(X, Y, m, facing=0.0, zone='', sub=''):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, zone, sub, -1, -1, -1)

ns = G.SANDBOX.namespaces['GPS3D']
tostr = L.eval('tostring')
cam, GS = ns.cam, ns.GlobeFrameState
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    if not mutant: print(('PASS' if ok else 'FAIL'), name, detail)
    return bool(ok)

place(-8958.3, -190, 0, 0.3, 'Elwynn Forest', 'Northshire Valley')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(30); chat()
cv = ns.canvas
l, b, r, t = G.SANDBOX.rect(cv)
CX, CY = (l + r) / 2, (b + t) / 2
def mouse(kind, px, py, btn='', d=0): G.SANDBOX_MOUSE(kind, CX + px, CY + py, btn, d)
GL = ns.GLOBE
HANDOVER, ROUND, GLOBE_MAX, RADIUS = GL.HANDOVER, GL.ROUND, GL.GLOBE_MAX, GL.RADIUS
lay = ns.GlobeLayout
def plane_of(m, x, y): return ns.GlobeToPlane(m, x, y)
def proj_plane(X, Y, h=0):
    p = ns.GlobeProject(X, Y, h)
    return (p[0], p[1]) if p and p[0] is not None else None
def at(d, m=None, x=None, y=None):
    if m is not None: cam.map = m
    if x is not None: cam.x, cam.y = x, y
    cam.dist = d
    ns.Render()

# ------------------------------------------------------------------------------------------------
def c_layout():
    e0, e1 = lay[0], lay[1]
    ok = ns.GlobeLayoutInfo.source == 'fallback' and e1.x1 < e0.x0 and (e0.x0 - e1.x1) > 5000
    ok = ok and all(abs(lay[m].ax - 1) < 0.005 and abs(lay[m].ay - 1) < 0.005 for m in (0, 1))
    check('layout: the classic world map (no world map in the sandbox): Kalimdor left of the Eastern Kingdoms, a sea between, each at its true size (scale within 0.5 % of 1)', ok,
          f'gap {e0.x0 - e1.x1:.0f} yd, scales {lay[0].ax:.4f} {lay[1].ax:.4f}, reason: {ns.GlobeLayoutInfo.why}')
    # the same numbers from a stand-in world map (as the game's C_Map would give them): read back within 1 yd
    L.execute('''
    local FB = { [0] = { 44688.53, 29795.11, 32601.04, 9894.93 }, [1] = { 44878.66, 29916.10, 8723.96, 14824.53 } }
    local CONT = { [0] = 1415, [1] = 1414 }
    SANDBOX_SAVED_CMAP = { GetMapRectOnMap = C_Map.GetMapRectOnMap, GetWorldPosFromMapPos = C_Map.GetWorldPosFromMapPos, GetMapPosFromWorldPos = C_Map.GetMapPosFromWorldPos, GetMapInfo = C_Map.GetMapInfo }
    local function contOf(ui) for m, c in pairs(CONT) do if c == ui then return m end end end
    -- each continent's own map covers a box of its world: corners at (0,0) and (1,1)
    local BOX = { [0] = { 7000, 4500, -16500, -7500 }, [1] = { 11500, 5000, -10000, -9500 } } -- X top, Y left, X bottom, Y right (world X north, Y west)
    C_Map.GetMapPosFromWorldPos = function(inst, v) return CONT[inst], CreateVector2D(0.5, 0.5) end
    C_Map.GetMapInfo = function(ui)
        if ui == 947 then return { mapID = 947, mapType = 1, parentMapID = 946 } end
        if contOf(ui) then return { mapID = ui, mapType = 2, parentMapID = 947 } end
        return SANDBOX_SAVED_CMAP.GetMapInfo(ui)
    end
    C_Map.GetWorldPosFromMapPos = function(ui, v)
        local m = contOf(ui); if not m then return SANDBOX_SAVED_CMAP.GetWorldPosFromMapPos(ui, v) end
        local b = BOX[m]; local x, y = v:GetXY()
        return m, CreateVector2D(b[1] + (b[3] - b[1]) * y, b[2] + (b[4] - b[2]) * x)
    end
    C_Map.GetMapRectOnMap = function(ui, parent)
        local m = contOf(ui); local d, b = FB[m], BOX[m]
        local function u(Y) return (d[3] - Y) / d[1] end
        local function v(X) return (d[4] - X) / d[2] end
        return u(b[2]), u(b[4]), v(b[1]), v(b[3])
    end
    ''')
    ns.GlobeChooseLayout()
    info = ns.GlobeLayoutInfo
    worst = 0
    fb = {0: (44688.53, 29795.11, 32601.04, 9894.93), 1: (44878.66, 29916.10, 8723.96, 14824.53)}
    for m in (0, 1):
        dd = lay[m].data
        worst = max(worst, *(abs(dd[i + 1] - fb[m][i]) for i in range(4)))
    check('layout from the game\'s world map (stand-in C_Map: rectangles and corners): the same numbers within 1 yd, used', info.source == 'game' and worst < 1, f'source {info.source}, worst {worst:.4f} yd, world map {info.world}')
    L.execute('for k, v in pairs(SANDBOX_SAVED_CMAP) do C_Map[k] = v end; C_Map.GetMapRectOnMap = nil')
    ns.GlobeChooseLayout()
    check('without C_Map.GetMapRectOnMap: back to the classic numbers', ns.GlobeLayoutInfo.source == 'fallback')

def c_maths():
    rnd = random.Random(7); worst_rt, worst_len, worst_conf = 0, 0, 0
    for _ in range(200):
        X, Y = rnd.uniform(-60000, 100000), rnd.uniform(-80000, 50000)
        rt = rnd.choice([RADIUS, RADIUS * 3, RADIUS * 40])
        u = ns.GlobeUnit(X, Y, rt)
        worst_len = max(worst_len, abs(math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2) - 1))
        p = ns.GlobePlaneOf(u[0], u[1], u[2], rt)
        worst_rt = max(worst_rt, abs(p[0] - X), abs(p[1] - Y))
        e = 0.5
        a = ns.GlobeUnit(X + e, Y, rt); c = ns.GlobeUnit(X, Y + e, rt)
        dx = [a[i] - u[i] for i in range(3)]; dy = [c[i] - u[i] for i in range(3)]
        lx, ly = math.sqrt(sum(v * v for v in dx)), math.sqrt(sum(v * v for v in dy))
        cosang = sum(dx[i] * dy[i] for i in range(3)) / (lx * ly)
        worst_conf = max(worst_conf, abs(lx / ly - 1), abs(cosang))
    check('the sphere: unit vectors of length 1, plane -> sphere -> plane round trip within 1e-6 yd', worst_len < 1e-12 and worst_rt < 1e-6, f'length {worst_len:.1e}, round trip {worst_rt:.1e} yd')
    check('the sphere keeps shapes: east and north stay at right angles and equally scaled (conformal)', worst_conf < 1e-4, f'worst {worst_conf:.1e}')

def c_straighten():
    ns.SetCamMode('free')
    ns.SetTopDown(False, True); cam.pitch = 50
    cam.map, cam.x, cam.y = 0, 32 * TILE, -40 * TILE
    vals = []
    qa = []
    for d in (14000, 16000, 18000):
        at(d); vals.append(cam.vp); qa.append(ns.questLayer.GetAlpha(ns.questLayer))
    ok = vals[0] is None and vals[1] is not None and 50 < vals[1] < 89.9 and abs(vals[2] - 89.9) < 1e-9 and qa[0] == 1 and qa[2] == 0
    check('past the old limit (14,000 yd) the view straightens to look down by the hand-over (18,000), your quest markers fading out', ok, f'tilt drawn {vals}, markers {qa}')
    at(12000)
    check('closer than 14,000 yd: the tilt you set, markers whole', cam.vp is None and ns.questLayer.GetAlpha(ns.questLayer) == 1)
    ns.SetTopDown(True, True)

def c_identical():
    # closer than the old limit, the 3D view draws exactly what it drew without the planet view
    cam.map, cam.x, cam.y = 0, 32.4 * TILE, -47.6 * TILE
    ns.SetTopDown(False, True); cam.pitch = 52; cam.yaw = 33
    worst, n = 0, 0
    for d in (300, 2500, 9000, 14000):
        at(d)
        for _ in range(12):  # let building blocks still waiting to be made be made
            if ns.stats.detailPending == 0: break
            ns.Render()
        ns.Render()
        a = {}
        for tt in ns.stats.visible.values():
            a[tostr(tt)] = list(tt.tex._vo)
        saved = (ns.GlobeRender, ns.ZoomMax)
        ns.GlobeRender = None; ns.ZoomMax = None
        at(d)
        for tt in ns.stats.visible.values():
            v = list(tt.tex._vo); w = a.get(tostr(tt))
            if w is None: worst = max(worst, 1e9); continue
            n += 1; worst = max(worst, max(abs(v[i] - w[i]) for i in range(8)))
        ns.GlobeRender, ns.ZoomMax = saved
    check('closer than 14,000 yd: every triangle where it was without the planet view (300 to 14,000 yd, tilted)', worst < 1e-9 and n > 1000, f'{n} triangles, worst {worst:.1e} px')
    ns.SetTopDown(True, True)

def c_firstentry():
    # zoomed out past 6,000 yd, the hand-over's land is made ready on idle frames: the first crossing is quick
    ns.SetCamMode('free'); ns.SetTopDown(True, True)
    at(9000, 0, 33 * TILE, -44 * TILE)
    tick(30)
    lv = ns.GlobeLevels()
    ready = [l for l in lv.values() if l.n == 1]
    full = all((l.assignedTo or 0) == len(l.tris) for l in ready) and len(ready) == 4
    at(HANDOVER * 0.98)
    t0 = time.perf_counter(); at(HANDOVER * 1.02); first = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter(); at(HANDOVER * 1.04); second = (time.perf_counter() - t0) * 1000
    check('the first crossing of a session is quick: the land was made ready while idle (2 continents x overview and pages)', full and ns.GlobeOn() and first <= max(3 * second, 6), f'{len(ready)} levels ready: {full}; first planet frame {first:.1f} ms, next {second:.1f} ms')

def c_handover():
    # at the hand-over the planet view's ground is where the ground was: the corners of tiles, both ways
    ns.SetTopDown(False, True); cam.pitch = 60; cam.yaw = 20
    cam.map, cam.x, cam.y = 0, 33.2 * TILE, -45.3 * TILE
    at(HANDOVER)  # still the ground (the planet view starts beyond)
    worst, n = 0, 0
    pts = []
    for tx in range(25, 44, 3):
        for ty in range(25, 60, 4):
            h = ns.TileHeights(0, tx, ty)
            if h:
                x, y = tx * TILE, -ty * TILE
                p = ns.Project(x, y, h[1])
                if p and p[0] is not None and abs(p[0]) < 600 and abs(p[1]) < 380: pts.append((x, y, h[1], p[0], p[1]))
    cam.dist = HANDOVER + 1e-6; ns.Render()
    on = ns.GlobeOn()
    for x, y, hh, sx, sy in pts:
        X, Y = plane_of(0, x, y)
        q = proj_plane(X, Y, hh)
        if q: n += 1; worst = max(worst, abs(q[0] - sx), abs(q[1] - sy))
    check('hand-over: the planet view takes over at 18,000 yd with the ground where it was (tile corners, tilted 60 and straightened)', on and n > 30 and worst < 0.05, f'{n} corners, worst {worst:.3f} px')
    st = GS.stats
    check('hand-over: the overview images whole (as the ground had them), no blue, no bending', st.atlas >= 0.999 and st.k == 0 and st.t == 0, f'overview {st.atlas}, blue {st.k}, curvature {st.t}')
    ns.SetTopDown(True, True)

def c_planet():
    ns.SetCamMode('free')
    # the point between the continents, from far out: the whole planet
    X0 = (lay[0].x0 + lay[1].x1) / 2; Y0 = (lay[0].y0 + lay[0].y1 + lay[1].y0 + lay[1].y1) / 4
    x, y = ns.GlobeFromPlane(0, X0, Y0)
    at(70000, 0, x, y)
    st = GS.stats
    maps = set()
    for k, lv in ns.GlobeLevels().items():
        if lv.active:
            for tt in lv.tris.values():
                if tt.shown: maps.add(lv.m)
    check('the whole planet from 70,000 yd: round, both continents drawn, sea blue', st.t == 1 and maps == {0, 1} and st.k == 1 and st.shown > 50, f'curvature {st.t}, continents {sorted(maps)}, land triangles {st.shown}, blue {st.k}')
    # the sea's disc: the sphere's outline as seen from the camera
    d = cam.dist; F = ns.Focal(); q = RADIUS / (RADIUS + d)
    want = F * q / math.sqrt(1 - q * q)
    check('the sea\'s disc is the planet\'s outline (radius from the camera\'s distance and field of view, within 1 %)', abs(st.rp - want) / want < 0.01 and ns.globeTex.disc._shown, f'{st.rp:.1f} px, expected {want:.1f}')
    bgc = ns.globeTex.bg._color
    check('space is black around it', bgc[1] == 0 and bgc[2] == 0 and bgc[3] == 0)
    # every land triangle shown faces the camera (counter-clockwise on screen); none from the far side
    bad = 0; n = 0
    for k, lv in ns.GlobeLevels().items():
        if not lv.active: continue
        for tt in lv.tris.values():
            if tt.shown:
                n += 1
                ax, ay, bx, by, cx, cy = lv.px[tt.a], lv.py[tt.a], lv.px[tt.b], lv.py[tt.b], lv.px[tt.c], lv.py[tt.c]
                if (bx - ax) * (cy - ay) - (cx - ax) * (by - ay) <= 0: bad += 1
    at(70000, 0, *ns.GlobeFromPlane(0, lay[0].x0 + 3000, (lay[0].y0 + lay[0].y1) / 2))  # over the Eastern Kingdoms: Kalimdor partly behind
    st = GS.stats
    check('land on the far side is not drawn: only triangles facing the camera are shown, some turned away', bad == 0 and n > 0 and st.culled > 0, f'{n} shown, {bad} facing away, {st.culled} culled')
    # draw order: nearer triangles in higher draw layers
    order = {'BACKGROUND': 0, 'BORDER': 1, 'ARTWORK': 2, 'OVERLAY': 3}
    pairs, wrong = 0, 0
    vis = []
    for k, lv in ns.GlobeLevels().items():
        if not lv.active: continue
        for tt in lv.tris.values():
            if tt.shown: vis.append((tt.depth, tt.tex._layer * 16 + tt.tex._sub))
    vis.sort()
    for i in range(len(vis) - 1):
        pairs += 1
        if vis[i][1] < vis[i + 1][1]: wrong += 1  # nearer must not be below a farther one
    check('draw order: nearer land never under farther land', pairs > 0 and wrong == 0, f'{pairs} pairs, {wrong} wrong')

def c_sky():
    X0 = (lay[0].x0 + lay[1].x1) / 2; Y0 = (lay[0].y0 + lay[0].y1 + lay[1].y0 + lay[1].y1) / 4
    at(70000, 0, *ns.GlobeFromPlane(0, X0, Y0))
    st = GS.stats
    clouds = ns.globeClouds
    shown = [clouds[i] for i in range(1, len(clouds) + 1) if clouds[i].tex and clouds[i].tex._shown]
    facing = True
    for c in shown:
        v = c.tex._vo  # corners: upper left, lower left, upper right, lower right
        p = [(v[1] - 0.5, v[2] + 0.5), (v[3] - 0.5, v[4] - 0.5), (v[5] + 0.5, v[6] + 0.5), (v[7] + 0.5, v[8] - 0.5)]
        if (p[1][0] - p[0][0]) * (p[3][1] - p[0][1]) - (p[3][0] - p[0][0]) * (p[1][1] - p[0][1]) <= 0: facing = False
    check('clouds over the planet (facing the camera), the Maelstrom between the continents, the glow round the edge', len(shown) >= 8 and facing and st.mael and ns.globeTex.glow._shown, f'{len(shown)} clouds, Maelstrom {st.mael}, glow {ns.globeTex.glow._shown}')
    # the Maelstrom sits on the point between the continents
    mv = ns.globeTex.mael._vo
    mx = (mv[1] + mv[3] + mv[5] + mv[7]) / 4; my = (mv[2] + mv[4] + mv[6] + mv[8]) / 4
    c0 = proj_plane(X0, Y0)
    MX = (lay[1].x1 + lay[0].x0) / 2  # the middle of the sea between Kalimdor's east coast box and the Eastern Kingdoms' west
    c0 = proj_plane(MX, Y0)
    check('the Maelstrom is drawn in the middle of the sea between the continents', c0 and abs(mx - c0[0]) < 2 and abs(my - c0[1]) < 2, f'{mx:.1f},{my:.1f} vs {c0}')
    at(HANDOVER * 1.05, 0, 32 * TILE, -45 * TILE)
    nshow = sum(1 for i in range(1, len(clouds) + 1) if clouds[i].tex and clouds[i].tex._shown)
    check('near the hand-over: no clouds, Maelstrom or glow yet, the sea the minimap\'s colour', nshow == 0 and not GS.stats.mael and not ns.globeTex.glow._shown and GS.stats.k == 0, f'{nshow} clouds, blue {GS.stats.k}')

def c_weather():
    # the clouds (2026-10-19): kinds placed by latitude, each with its shadow below it toward the lower right,
    # lit as the planet is; southern storms mirrored; the Maelstrom's storm over its whirlpool, and lightning
    X0, Y0, MX, MY = ns.GlobeCentres()
    at(70000, 0, *ns.GlobeFromPlane(0, MX, MY)); cam.yaw = 0; ns.Render()
    clouds = ns.globeClouds
    cl = [clouds[i] for i in range(1, len(clouds) + 1)]
    kinds = sorted(set(c.kind for c in cl))
    shown = [c for c in cl if c.tex and c.tex._shown]
    worst_sh, ok_sh = 0, True
    for c in shown:
        v, w = c.tex._vo, c.sh._vo
        dx, dy = w[1] - v[1], w[2] - v[2]
        if not (c.sh._shown and dx > 0.3 and dy < -0.3 and all(abs((w[i] - v[i]) - (dx if i % 2 else dy)) < 1e-6 for i in range(1, 9))): ok_sh = False
        if c.sh._color[4] > 0.3 * c.tex._color[4] + 1e-9: ok_sh = False
    check('clouds of all six kinds on the planet, each drawn with its shadow below it toward the lower right (faint)', kinds == [1, 2, 3, 4, 5, 6] and len(cl) >= 60 and len(shown) >= 10 and ok_sh,
          f'{len(cl)} clouds of kinds {kinds}, {len(shown)} shown, shadows {"ok" if ok_sh else "wrong"}')
    # lit as the planet: brighter toward the light (upper left), darker away from it
    pts = []
    for c in shown:
        v = c.tex._vo
        pts.append(((v[1] + v[7]) / 2, (v[2] + v[8]) / 2, c.tex._color[1]))
    hi = max(pts, key=lambda p: p[2]); lo = min(pts, key=lambda p: p[2])
    lx, ly = -0.45, 0.55
    check('clouds lit as the planet is: brighter toward the light (upper left), darker on the far side of it', lo[2] < 0.9 and hi[2] > lo[2] + 0.1 and (hi[0] - lo[0]) * lx + (hi[1] - lo[1]) * ly > 0,
          f'brightest {hi[2]:.2f} at {hi[0]:.0f},{hi[1]:.0f}; darkest {lo[2]:.2f} at {lo[0]:.0f},{lo[1]:.0f}')
    # storms: northern ones as drawn, southern ones mirrored (they turn the other way)
    storms = [c for c in cl if c.kind == 4]
    good = 0
    for c in storms:
        lat_n = ns.GlobeUnit(c.X, c.Y, RADIUS)[1] > 0
        good += (c.mirror is True) == (not lat_n)
    check('storms turn the way their hemisphere\'s storms turn: the southern ones mirrored', len(storms) >= 3 and good == len(storms) and any(c.mirror for c in storms) and not all(c.mirror for c in storms), f'{good} of {len(storms)} storms')
    # the Maelstrom: the storm over the whirlpool, 1.45 x its size, both centred on it
    T = ns.globeTex
    mv, sv = T.mael._vo, T.storm._vo
    def size(v): return math.hypot(v[5] - v[1], v[6] - v[2])
    def centre(v): return ((v[1] + v[3] + v[5] + v[7]) / 4, (v[2] + v[4] + v[6] + v[8]) / 4)
    mc, sc = centre(mv), centre(sv)
    check('the Maelstrom: its storm over the whirlpool (1.45 x its size, on it), both shown', T.mael._shown and T.storm._shown and abs(size(sv) / size(mv) - 1.45) < 0.05 and math.hypot(mc[0] - sc[0], mc[1] - sc[1]) < 3,
          f'size ratio {size(sv) / size(mv):.3f}, centres {math.hypot(mc[0] - sc[0], mc[1] - sc[1]):.2f} px apart')
    # lightning: over 12 seconds, flashes now and then (not all the time), each in the storm
    a0 = []
    frames, lit, inside = 0, 0, True
    r_storm = size(sv) / 2
    for _ in range(360):
        tick(1); frames += 1
        if T.bolt._shown and T.bolt._color[4] > 0.01:
            lit += 1
            bc = centre(T.bolt._vo)
            if math.hypot(bc[0] - mc[0], bc[1] - mc[1]) > r_storm: inside = False
    check('lightning flashes in the Maelstrom\'s storm now and then (over 12 s: some frames, not most), always within the storm', 3 <= lit <= 0.25 * frames and inside, f'{lit} of {frames} frames lit')

def c_arrow():
    ns.FollowMe('follow'); tick(30)
    pl = ns.player
    at(60000)
    a = ns.globeTex.arrow
    v = a._vo
    cx_ = (v[1] - 0.5 + v[3] - 0.5 + v[5] + 0.5 + v[7] + 0.5) / 4; cy_ = (v[2] + 0.5 + v[4] - 0.5 + v[6] + 0.5 + v[8] - 0.5) / 4
    X, Y = plane_of(pl.map, pl.x, pl.y)
    c = proj_plane(X, Y, 0)
    check('your arrow on the planet, where you are (following you, 60,000 yd)', a._shown and c and abs(cx_ - c[0]) < 1.5 and abs(cy_ - c[1]) < 1.5 and ns.IsFollowing(), f'{cx_:.1f},{cy_:.1f} vs {c}')

def c_pick():
    # a point on the near side of the planet, projected to the screen, is picked back (not the far side's)
    worst = 0; n = 0
    rnd = random.Random(3)
    for d in (HANDOVER + 1, 30000, 45000, 70000):
        at(d, 0, 33 * TILE, -44 * TILE)
        XF, YF = plane_of(0, cam.x, cam.y)
        for _ in range(40):
            X, Y = XF + rnd.uniform(-6000, 6000), YF + rnd.uniform(-6000, 6000)
            q = proj_plane(X, Y, 0)
            if q and abs(q[0]) < 500 and abs(q[1]) < 330:
                p = ns.GlobePickPlane(q[0], q[1])
                if p and p[0] is not None:
                    n += 1; worst = max(worst, math.hypot(p[0] - X, p[1] - Y))
                else:
                    n += 1; worst = max(worst, 1e9)
    check('picking: a point of the planet shown on screen is picked back from its pixel (flat, bending, round)', n > 100 and worst < 0.5, f'{n} points, worst {worst:.4f} yd')

def c_controls():
    ns.SetCamMode('free')
    at(45000, 0, 33 * TILE, -44 * TILE)
    # wheel toward the cursor on the planet: the point under it stays there
    mouse('move', 140, -60)
    p0 = ns.GlobePickPlane(140, -60)
    d0 = cam.dist
    mouse('wheel', 140, -60, '', 1)
    p1 = ns.GlobePickPlane(140, -60)
    ok = p0 and p1 and math.hypot(p0[0] - p1[0], p0[1] - p1[1]) < 15 and abs(cam.dist - d0 * 0.85) < 1
    check('wheel on the planet: zooms toward the cursor, the point under it stays (within 15 yd)', ok, f'moved {math.hypot(p0[0] - p1[0], p0[1] - p1[1]):.2f} yd, dist {d0:.0f} -> {cam.dist:.0f}')
    # drag turns the planet: the grabbed point stays under the cursor
    at(60000)
    mouse('move', -50, 30)
    g = ns.GlobePickPlane(-50, 30)
    mouse('down', -50, 30, 'LeftButton')
    for k in range(1, 11): mouse('move', -50 + k * 12, 30 - k * 5); tick(1)
    q = proj_plane(g[0], g[1], 0)
    mouse('up', -50 + 120, 30 - 50, 'LeftButton'); tick(2)
    check('drag on the planet: the grabbed point stays under the cursor (within 2 px)', q and abs(q[0] - 70) < 2 and abs(q[1] + 20) < 2, f'{q}')
    # right-drag turns the view
    y0 = cam.yaw
    mouse('down', 0, 0, 'RightButton')
    for k in range(1, 6): mouse('move', -k * 10, 0); tick(1)
    mouse('up', -50, 0, 'RightButton'); tick(2)
    check('right-drag on the planet turns the view', abs(((cam.yaw - y0 + 180) % 360) - 180 - 20) < 1e-6, f'yaw {y0:.1f} -> {cam.yaw:.1f}')

def c_spin():
    ns.SetCamMode('free')
    at(70000, 0, 33 * TILE, -44 * TILE)
    k0 = lay[1]
    target = ((k0.x0 + k0.x1) / 2, (k0.y0 + k0.y1) / 2)
    # a fixed point (Kalimdor's middle) on screen before and after the view's map changes
    maps = []
    jumps = 0
    for step in range(40):
        before = proj_plane(*target)
        p = ns.GlobePickPlane(0, 0)
        # drag a little toward Kalimdor
        X, Y = p
        mouse('move', 0, 0); mouse('down', 0, 0, 'LeftButton')
        mouse('move', 25, 0); tick(1); mouse('up', 25, 0, 'LeftButton'); tick(1)
        after_map = cam.map
        maps.append(after_map)
        if after_map == 1: break  # (the planet turns all the way round since 2026-10-19: stop on Kalimdor)
    ok = 0 in maps and 1 in maps and maps[-1] == 1
    check('spinning the planet from the Eastern Kingdoms to Kalimdor: the view\'s map becomes Kalimdor on the way', ok, f'maps seen {sorted(set(maps))}, last {maps[-1]}')
    # the switch itself moves nothing: the same plane point before and after re-saying the focus on the other map
    at(70000, 0, *ns.GlobeFromPlane(0, (lay[0].x0 + lay[1].x1) / 2 - 500, (lay[0].y0 + lay[0].y1) / 2))
    q0 = proj_plane(*target)
    X, Y = plane_of(cam.map, cam.x, cam.y)
    cam.map = 1; cam.x, cam.y = ns.GlobeFromPlane(1, X, Y); ns.Render()
    q1 = proj_plane(*target)
    check('changing the view\'s map on the planet moves nothing on screen', q0 and q1 and abs(q0[0] - q1[0]) < 0.01 and abs(q0[1] - q1[1]) < 0.01, f'{q0} vs {q1}')

def sphere_state():
    lat = math.degrees(math.asin(max(-1, min(1, GS.oy)))); lon = math.degrees(math.atan2(GS.ox, GS.oz))
    return lat, lon, (cam.yaw - ns.GlobeNorth()) % 360
def unit_under(px, py):
    u = ns.GlobePickUnit(px, py)
    return u if u and u[0] is not None else None
def ang(a, b): return math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(a, b))))))

def c_farspin():
    # spinning the planet round and round (2026-10-19: a drag got stuck on the far side, where the plane the
    # planet is made from is infinitely far): 30 drags of 120 px to the left through the middle of the view,
    # every frame the grabbed point under the cursor, the view facing the same way from the planet's north
    ns.SetCamMode('free')
    X0, Y0, MX, MY = ns.GlobeCentres()
    at(70000, 0, *ns.GlobeFromPlane(0, (lay[0].x0 + lay[0].x1) / 2, Y0)); cam.yaw = 0; ns.Render()  # on the equator, north up
    lat0, lon0, h0 = sphere_state()
    total, last, worst, worsth, far = 0.0, lon0, 0.0, 0.0, 0
    for k in range(30):
        mouse('move', 60, 0); g = unit_under(60, 0)
        mouse('down', 60, 0, 'LeftButton'); tick(1)
        for i in range(1, 9):
            px, py = 60 - 15 * i, 0
            mouse('move', px, py); tick(1)
            w = unit_under(px, py)
            worst = max(worst, ang(g, w) * math.pi / 180 * RADIUS if w else 1e9)
            lat, lon, h = sphere_state()
            worsth = max(worsth, abs((h - h0 + 180) % 360 - 180))
            total += (last - lon + 180) % 360 - 180; last = lon
            if GS.oz < -0.9: far += 1
        mouse('up', px, py, 'LeftButton'); tick(1)
    check('spinning the planet round and round: 30 drags turn it more than twice, through the far side, the grabbed point under the cursor every frame (within 3 yd) and the view facing the same way from the planet\'s north (within 0.5 degrees)',
          abs(total) > 720 and far > 0 and worst < 3 and worsth < 0.5 and abs(sphere_state()[0] - lat0) < 0.5, f'turned {abs(total):.0f} degrees, {far} frames over the far side\'s middle, worst {worst:.2f} yd off the cursor, facing changed {worsth:.3f} degrees, latitude {lat0:.2f} -> {sphere_state()[0]:.2f}')
    # drags round a square, away from the equator: a free turn would roll the planet a little every loop; the
    # view keeps facing the same way from the planet's north (the continents come back upright)
    at(70000, 0, 33 * TILE, -40 * TILE); cam.yaw = 30; ns.Render()
    _, _, h0 = sphere_state()
    worst = 0
    path = [(-40, -40), (40, -40), (40, 40), (-40, 40), (-40, -40)]
    for loop in range(6):
        for (ax_, ay_), (bx_, by_) in zip(path, path[1:]):
            mouse('move', ax_, ay_); g = unit_under(ax_, ay_)
            mouse('down', ax_, ay_, 'LeftButton'); tick(1)
            for i in range(1, 9):
                px, py = ax_ + (bx_ - ax_) * i / 8, ay_ + (by_ - ay_) * i / 8
                mouse('move', px, py); tick(1)
                w = unit_under(px, py)
                worst = max(worst, ang(g, w) * math.pi / 180 * RADIUS if w else 1e9)
            mouse('up', px, py, 'LeftButton'); tick(1)
    _, _, h = sphere_state()
    check('drags round a square, six times: the grabbed point under the cursor every frame and the view facing the same way from the planet\'s north at the end (within 0.5 degrees)',
          worst < 3 and abs((h - h0 + 180) % 360 - 180) < 0.5, f'worst {worst:.2f} yd off the cursor, facing {h0:.2f} -> {h:.2f}')
    # starting right over the far side's middle (the plane's infinity): a drag still turns the planet
    rt = GS.rt
    X, Y = ns.GlobePlaneOf(0.0005, 0.0003, -math.sqrt(1 - 0.0005 ** 2 - 0.0003 ** 2), rt)
    at(70000, 0, *ns.GlobeFromPlane(0, X, Y))
    oz0 = GS.oz
    mouse('move', 80, 0); g = unit_under(80, 0)
    mouse('down', 80, 0, 'LeftButton'); tick(1)
    for i in range(1, 9): mouse('move', 80 - 20 * i, 0); tick(1)
    w = unit_under(-80, 0)
    mouse('up', -80, 0, 'LeftButton'); tick(1)
    off = ang(g, w) * math.pi / 180 * RADIUS if w else 1e9
    check('a drag over the middle of the far side turns the planet away from it, the grabbed point under the cursor', oz0 < -0.9999 and GS.oz > -0.8 and off < 3, f'z {oz0:.5f} -> {GS.oz:.3f}, {off:.2f} yd off')
    # the wheel toward the cursor there keeps the point under it
    mouse('move', 90, 40); u0 = unit_under(90, 40)
    mouse('wheel', 90, 40, '', 1)
    u1 = unit_under(90, 40)
    off = ang(u0, u1) * math.pi / 180 * RADIUS if u0 and u1 else 1e9
    check('the wheel over the far side zooms toward the cursor, the point under it stays (within 15 yd)', off < 15, f'{off:.2f} yd')
    # the compass shows the planet's north there, and a click turns it up
    _, _, h = sphere_state()
    rot = ns.compass.icon._rot
    ok = rot is not None and abs(((math.degrees(rot) - h) + 180) % 360 - 180) < 0.01
    ns.compass._scripts.OnClick(ns.compass, 'LeftButton'); tick(30)
    _, _, h2 = sphere_state()
    check('the compass shows the planet\'s north on the planet, and its click turns that north up', ok and min(h2, 360 - h2) < 0.01, f'needle {math.degrees(rot or 0):.2f} vs facing {h:.2f}; after the click {h2:.3f}')
    # that north is the ground's at the hand-over (the compass does not jump)
    at(GL.HANDOVER * 1.0005, 0, 33 * TILE, -44 * TILE)
    n1 = ns.GlobeNorth()
    at(ns.GlobeCurveStart() * 1.01)
    n2 = ns.GlobeNorth()
    check('the planet\'s north is the ground\'s where the ground starts to bend (the compass carries on smoothly)', n1 == 0 and abs(n2) < 0.05, f'{n1:.4f}, {n2:.4f} degrees')

def c_farfly():
    # Me from the far side: the view travels along the sphere at an even pace (not out along the plane and
    # then rushing in at the end)
    ns.SetCamMode('free')
    rt = RADIUS
    at(70000, 0, 33 * TILE, -44 * TILE)
    X, Y = ns.GlobePlaneOf(0.3, 0.1, -math.sqrt(1 - 0.09 - 0.01), GS.rt)
    at(70000, 0, *ns.GlobeFromPlane(0, X, Y))
    prev = (GS.ox, GS.oy, GS.oz)
    ns.ui.me._scripts.OnClick(ns.ui.me, 'LeftButton')
    steps = []
    for _ in range(25):
        tick(1); ns.Render()
        cur = (GS.ox, GS.oy, GS.oz); steps.append(ang(prev, cur)); prev = cur
    tick(30)
    pl = ns.player
    # the flight lasts 0.5 s (15 frames here) and eases in and out (smoothstep: its fastest frame is 1.5 x the
    # average); through the plane, nearly all of the way would come in the last frames
    total = sum(steps)
    check('Me from the far side: the view flies round the planet to you at an even pace (no frame more than 1.6 x the average of a 15-frame flight), then follows you',
          total > 90 and max(steps) < 1.6 * total / 15 and cam.map == pl.map and abs(cam.x - pl.x) < 1e-6 and ns.IsFollowing(), f'{total:.0f} degrees in all, fastest frame {max(steps):.1f}, average {total / 15:.1f}')

def c_pole():
    # dragging toward a pole stops 70 degrees from the equator (the view never turns over the pole)
    ns.SetCamMode('free')
    at(70000, 0, 33 * TILE, -44 * TILE); cam.yaw = 0; ns.Render()
    _, _, h0 = sphere_state()
    lats = []
    for k in range(6):
        mouse('move', 0, -120); mouse('down', 0, -120, 'LeftButton'); tick(1)
        for i in range(1, 9): mouse('move', 0, -120 + 30 * i); tick(1); lats.append(sphere_state()[0])
        mouse('up', 0, 120, 'LeftButton'); tick(1)
    _, _, h = sphere_state()
    check('dragging toward a pole: the planet stops 70 degrees from the equator, the view still facing north', min(lats) > -70.01 and min(lats) < -69.9 and abs((h - h0 + 180) % 360 - 180) < 0.5, f'furthest {min(lats):.2f} degrees, facing {h0:.1f} -> {h:.1f}')

def c_flydown():
    ns.SetCamMode('free')
    at(60000, 0, 33 * TILE, -44 * TILE)
    k1 = lay[1]
    X, Y = (k1.x0 + k1.x1) / 2, (k1.y0 + k1.y1) / 2
    q = proj_plane(X, Y)
    if not q:
        check('double-click on Kalimdor flies down to it', False, 'Kalimdor not on screen'); return
    for _ in range(2):
        mouse('move', q[0], q[1]); mouse('down', q[0], q[1], 'LeftButton'); mouse('up', q[0], q[1], 'LeftButton'); tick(2)
    tick(60)
    tx, ty = ns.GlobeFromPlane(1, X, Y)
    check('double-click on Kalimdor (planet view): flies down to it, the ground below at the end', cam.map == 1 and abs(cam.x - tx) < 300 and abs(cam.y - ty) < 300 and cam.dist < HANDOVER and not ns.GlobeOn(), f'map {cam.map}, at {cam.x / TILE:.2f},{-cam.y / TILE:.2f}, dist {cam.dist:.0f}')

def c_me():
    # Me on the planet while looking at Kalimdor: the flight to you starts where the view is (no jump)
    ns.SetCamMode('free')
    e = lay[1]
    at(60000, 1, *ns.GlobeFromPlane(1, (e.x0 + e.x1) / 2, (e.y0 + e.y1) / 2))
    before = plane_of(cam.map, cam.x, cam.y)
    ns.ui.me._scripts.OnClick(ns.ui.me, 'LeftButton')
    tick(1)
    after = plane_of(cam.map, cam.x, cam.y)
    moved = math.hypot(after[0] - before[0], after[1] - before[1])
    tick(40)
    pl = ns.player
    check('Me on the planet: the view flies from where it is to you (first frame moves little), then follows you', moved < 2000 and cam.map == pl.map and abs(cam.x - pl.x) < 1e-6 and ns.IsFollowing(), f'first frame moved {moved:.0f} yd of {math.hypot(*(a - b for a, b in zip(plane_of(pl.map, pl.x, pl.y), before))):.0f}')

def c_cycle():
    ns.SetCamMode('free')
    at(60000, 0, 33 * TILE, -44 * TILE)
    d0 = cam.dist
    G.GPS3D_Frame and ns.ui.next._scripts.OnClick(ns.ui.next, 'LeftButton')
    tick(50)
    e = lay[1]
    tx, ty = ns.GlobeFromPlane(1, (e.x0 + e.x1) / 2, (e.y0 + e.y1) / 2)
    check('> on the planet turns it to the other continent, keeping the distance', cam.map == 1 and abs(cam.x - tx) < 1 and abs(cam.y - ty) < 1 and abs(cam.dist - d0) < 1e-6, f'map {cam.map}, dist {cam.dist:.0f}')

def c_pull():
    # zooming in over the open sea between the continents: on the map's land box by the last planet frame, so
    # the ground taking over has nothing to move
    ns.SetCamMode('free')
    X, Y = (lay[0].x0 + lay[1].x1) / 2, (lay[0].y0 + lay[0].y1) / 2
    at(40000, 0, *ns.GlobeFromPlane(0, X, Y))
    e = lay[0]
    last = None
    while cam.dist > 12000:
        ns.Zoom(0.97)
        if ns.GlobeOn(): last = (cam.dist, cam.x, cam.y, cam.map)
    d, x, y, m = last
    e = lay[m]
    inside = e.tx0 * TILE - 1 <= x <= (e.tx1 + 1) * TILE + 1 and -(e.ty1 + 1) * TILE - 1 <= y <= -e.ty0 * TILE + 1
    check('zooming in over the open sea: on the map\'s land box by the last planet frame (nothing jumps at the hand-over)', inside and not ns.GlobeOn(), f'last planet frame at {d:.0f} yd: {x / TILE:.2f},{-y / TILE:.2f} on map {m}')

def c_instances():
    cam.map, cam.x, cam.y, cam.dist = 30, 0, 0, 9000
    b = None
    for key in ns.World[30].keys(): b = key; break
    cam.x, cam.y = (b % 64 + 0.5) * TILE, -(b // 64 + 0.5) * TILE
    ns.SetCamMode('free'); ns.Render()
    for _ in range(20): ns.Zoom(1 / 0.85)
    check('maps that are not on the planet (Alterac Valley) still stop at 14,000 yd', abs(cam.dist - 14000) < 1e-6 and not ns.GlobeOn() and cam.vp is None, f'dist {cam.dist:.0f}')
    cam.map = 0; cam.x, cam.y = 32 * TILE, -45 * TILE; cam.dist = 9000; ns.Render()

def c_follow():
    ns.FollowMe('follow'); tick(40)
    for _ in range(25): ns.Zoom(1 / 0.85)
    tick(5)
    pl = ns.player
    check('following you, the wheel zooms out to the planet with you in the middle', ns.GlobeOn() and abs(cam.x - pl.x) < 1e-6 and abs(cam.dist - GLOBE_MAX) < 1e-6 and ns.IsFollowing(), f'dist {cam.dist:.0f}')
    # the rings: the compass needle turns with the view; the straight-down ring shows straight down
    check('the straight-down ring shows the view looking down on the planet', ns.compass.pitch == cam.vp and abs(cam.vp - 89.9) < 1e-9)
    for _ in range(25): ns.Zoom(0.85)
    tick(5)
    check('... and back in to you: the ground, the tilt you had', not ns.GlobeOn() and cam.vp is None and cam.dist < 14000, f'dist {cam.dist:.0f}')

def c_selftest():
    G.SlashCmdList.GPS3D('test'); tick(2)
    c = chat()
    tick(100); c += chat()
    lines = [s for s in c.split('\n') if 'planet:' in s]
    ok = any('classic numbers' in s for s in lines) and any('ms a frame at 60,000 yd' in s for s in lines) and any('report loaded' in s for s in lines)
    check('/gps3d test reports the planet: layout, a planet frame\'s time, its images', ok, ' | '.join(s[s.index('planet:'):][:90] for s in lines))
    st = G.GPS3D_API.DebugState()
    check('the debug log\'s view line says whether the planet view is on', 'planet:' in st, st[-120:])

def c_speed():
    ns.SetCamMode('free')
    gc = L.eval('function() collectgarbage("collect"); collectgarbage("collect"); return collectgarbage("count") end')
    res = {}
    for name, d in (('hand-over', HANDOVER * 1.02), ('bending', 32000), ('round', 60000), ('far', 100000)):
        at(d, 0, 33 * TILE, -44 * TILE)
        for _ in range(3): cam.yaw += 1; ns.Render()
        t0 = time.perf_counter()
        for _ in range(30): cam.yaw += 1; ns.Render()
        res[name] = (time.perf_counter() - t0) * 1000 / 30
    at(12000, 0, 33 * TILE, -44 * TILE)
    t0 = time.perf_counter()
    for _ in range(30): cam.yaw += 1; ns.Render()
    flat = (time.perf_counter() - t0) * 1000 / 30
    check('frame time on the planet no slower than the ground at 12,000 yd (native Lua)', max(res.values()) <= max(flat * 1.5, 4), f'planet {", ".join(f"{k} {v:.1f} ms" for k, v in res.items())}; ground at 12,000 yd {flat:.1f} ms')
    # crossing the hand-over back and forth: no frame much slower than the others (nothing rebuilt each time)
    at(HANDOVER * 0.97, 0, 33 * TILE, -44 * TILE); at(HANDOVER * 1.03); at(HANDOVER * 0.97)  # first crossing builds once
    # (three sweeps of six crossings each way, the best sweep's worst frame: a real rebuild costs every sweep, a
    # one-off pause of the machine does not, and made this check fail now and then)
    sweeps = []
    for _ in range(3):
        worst = 0
        for k in range(6):
            for d in (HANDOVER * 1.03, HANDOVER * 0.97):
                t0 = time.perf_counter(); at(d); worst = max(worst, (time.perf_counter() - t0) * 1000)
        sweeps.append(worst)
    worst = min(sweeps)
    check('crossing the hand-over back and forth: every frame quick (the planet keeps its images between crossings)', worst <= max(flat * 2, 6), f'worst crossing frame {worst:.1f} ms, best of 3 sweeps ({", ".join(f"{w:.1f}" for w in sweeps)}) (ground at 12,000 yd {flat:.1f} ms)')
    at(60000)
    for _ in range(10): cam.yaw += 1; ns.Render()
    m0 = gc()
    for _ in range(300): cam.yaw += 0.3; ns.Render()
    m1 = gc()
    check('no garbage kept: memory flat over 300 planet frames', m1 - m0 < 64, f'{m1 - m0:+.1f} KB')

CHECKS = {'layout': c_layout, 'maths': c_maths, 'straighten': c_straighten, 'identical': c_identical, 'firstentry': c_firstentry, 'handover': c_handover,
          'planet': c_planet, 'sky': c_sky, 'weather': c_weather, 'arrow': c_arrow, 'pick': c_pick, 'controls': c_controls, 'spin': c_spin,
          'flydown': c_flydown, 'me': c_me, 'cycle': c_cycle, 'pull': c_pull, 'instances': c_instances, 'follow': c_follow,
          'farspin': c_farspin, 'farfly': c_farfly, 'pole': c_pole, 'selftest': c_selftest, 'speed': c_speed}

if mutant:
    try:
        CHECKS[mutant[3]]()
    except Exception as e:
        results.append(('error', False)); print('error', e)
    print('MUTANT', 'caught' if not all(ok for _, ok in results) else 'NOT caught')
    sys.exit(0)

for name, fn in CHECKS.items():
    try:
        fn()
    except Exception as e:
        import traceback; traceback.print_exc()
        check(f'{name}: ran without errors', False, str(e))
errors = [s for s in chat().split('\n') if 'rror' in s and 'Globe' in s]
check('no Lua errors from the planet view', not errors, '; '.join(errors[:2]))

# each mutation must make its check fail
caught = 0
for i, m in enumerate(MUTANTS if not os.environ.get('GLOBE_NO_MUTANTS') else []):
    out = subprocess.run([sys.executable, os.path.abspath(__file__), '--mutant', str(i)], capture_output=True, text=True, timeout=600).stdout
    ok = 'MUTANT caught' in out
    caught += ok
    print(('     caught' if ok else '     NOT caught'), m[0], '->', m[3])
if not os.environ.get('GLOBE_NO_MUTANTS'): check(f'every mutation of Globe.lua is caught by its check ({len(MUTANTS)} mutations)', caught == len(MUTANTS), f'{caught} of {len(MUTANTS)}')

n_ok = sum(1 for _, ok in results if ok)
print(f'{n_ok} of {len(results)} checks passed')
sys.exit(0 if n_ok == len(results) else 1)
