# Checks the window look ("minimap rings", option B) on the sandbox engine (Lua 5.4, as in the
# sandbox) for the 2D and 3D windows (the traditional map: test_modes.py): what each window shows, the rings and what they do, tooltips, and layout at the
# smallest window size. Usage: python test_look.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
toc = open(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua', 'World.lua', 'MapWindow.lua', 'MapKey.lua']), ('GPS3D', gps3d_files)]:
    for f in files:
        if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')
W, H = 1280, 800
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
def chat():
    c = G.SANDBOX_CHAT()
    if c: print('CHAT>', c.replace('\n', '\nCHAT> '))
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
rect = lambda o: tuple(G.SANDBOX.rect(o))
def inside(a, b):  # a within b (l, b, r, t)
    return a[0] >= b[0] - 0.5 and a[1] >= b[1] - 0.5 and a[2] <= b[2] + 0.5 and a[3] <= b[3] + 0.5
def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
def lua_list(t): return [t[i] for i in range(1, len(t) + 1)]
_rawequal = L.eval('function(a, b) return rawequal(a, b) end')
def same(xs, ys): return len(xs) == len(ys) and all(_rawequal(a, b) for a, b in zip(xs, ys))
def click(b): b._scripts.OnClick(b, 'LeftButton')
def hover(b): b._scripts.OnEnter(b)

G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
ns1, ns2 = G.SANDBOX.namespaces['GnomishPositioningSystem'], G.SANDBOX.namespaces['GPS3D']
u1, u2 = ns1.ui, ns2.ui
G.SlashCmdList.GPS(''); tick(5); chat()
F1 = G.GPS_MapFrame
bd = F1.GetBackdrop(F1)
check('2D: frameless, a 1 px black edge', bd.edgeSize == 1 and 'white8x8' in str(bd.edgeFile).lower() and tuple(F1._bdBorder.values())[:3] == (0, 0, 0), f'edge {bd.edgeFile} {bd.edgeSize}')
rings1 = lua_list(u1.rings)
check('2D: rings are compass, mode ring (2D), Me', same(rings1, [u1.compass, u1.modeSwitch, u1.me]) and u1.modeSwitch.label.GetText(u1.modeSwitch.label) == '2D', f'{len(rings1)} rings')
check('2D: close uses the RedButton-Exit atlas', u1.close._normal.GetAtlas(u1.close._normal) == 'RedButton-Exit' and u1.close._pushed.GetAtlas(u1.close._pushed) == 'RedButton-exit-pressed')
zi, zo = u1.zoomIn, u1.zoomOut
check('2D: zoom buttons are rings the size of the others (30 px) with a small sign (plus: 4 bars, minus: 2; the sign 9 px)',
      zi.GetWidth(zi) == 30 and zo.GetWidth(zo) == 30 and zi.GetWidth(zi) == u1.modeSwitch.GetWidth(u1.modeSwitch) and len(lua_list(zi.bars)) == 4 and len(lua_list(zo.bars)) == 2
      and abs(max(t.GetWidth(t) for t in lua_list(zi.bars)) - (9 + 2)) < 1e-9, f'{zi.GetWidth(zi)} px, bars {len(lua_list(zi.bars))}/{len(lua_list(zo.bars))}')
check('2D: map switch shown (< map >)', u1.prev.IsShown(u1.prev) and u1.next.IsShown(u1.next) and u1.subtitle.GetText(u1.subtitle) == 'Eastern Kingdoms', str(u1.subtitle.GetText(u1.subtitle)))
check('2D: footer says where you are', 'Northshire Valley' in str(u1.footer.GetText(u1.footer)), str(u1.footer.GetText(u1.footer)))
check('2D: Me ring gold while following', ns1.view.follow and u1.me.active == True)
ns1.view.follow = False; tick(3)
check('2D: Me ring brass once you look elsewhere', u1.me.active == False)
click(u1.me); tick(3)
check('2D: Me ring follows you again', ns1.view.follow and u1.me.active == True)
hover(u1.modeSwitch)
tip1 = lua_list(u1.modeSwitch.tooltip(u1.modeSwitch))
check('2D: mode ring tooltip names the next mode and, right-click, the one before',
      G.GameTooltip.IsShown(G.GameTooltip) and G.GameTooltip.IsOwned(G.GameTooltip, u1.modeSwitch)
      and tip1 == ['2D map', 'Click: 3D view of the same place', 'Right-click: Traditional map'], str(tip1))
G.GameTooltip_Hide()

def layout_ok(frame, ui, name):
    fr = rect(frame); rs = [rect(b) for b in lua_list(ui.rings)]
    zs = [rect(ui.zoomIn), rect(ui.zoomOut), rect(ui.close), rect(ui.fullScreen), rect(ui.globe)]  # (the globe and full screen since 2026-10-21)
    ok_in = all(inside(r, fr) for r in rs + zs)
    ok_sep = not any(overlap(a[i], a[j]) for a in (rs, zs) for i in range(len(a)) for j in range(i + 1, len(a)))
    ok_zoom = not any(overlap(r, z) for r in rs for z in zs)
    ft = rect(ui.footer)
    ok_footer = not overlap(ft, rect(ui.zoomOut))
    check(f'{name}: rings, close, full screen, globe and zoom inside the window, none overlapping', ok_in and ok_sep and ok_zoom and ok_footer, f'in {ok_in} apart {ok_sep} clear of zoom/close {ok_zoom} footer clear {ok_footer}')

layout_ok(F1, u1, '2D at 900x650')
F1.SetSize(F1, 400, 300); tick(2)
layout_ok(F1, u1, '2D at 400x300 (smallest)')
F1.SetSize(F1, 900, 650); tick(2)

# ---- 3D
click(u1.modeSwitch); tick(10); chat()
F2 = G.GPS3D_Frame
check('mode ring (click) opens the 3D view in the same place', F2.IsShown(F2) and not F1.IsShown(F1) and rect(F2) == rect(F1))
rings2 = lua_list(u2.rings)
check('3D: rings are compass, mode (3D), Me, then camera and straight down', same(rings2, [ns2.compass, u2.modeSwitch, u2.me, ns2.camButton, ns2.topButton]) and u2.modeSwitch.label.GetText(u2.modeSwitch.label) == '3D', f'{len(rings2)} rings')
check('compass, mode ring and Me at the same places in 2D and 3D (they stay under the mouse when switching)', all(rect(a) == rect(b) for a, b in ((u1.compass, ns2.compass), (u1.modeSwitch, u2.modeSwitch), (u1.me, u2.me))), str([rect(x)[:2] for x in (u1.compass, u1.modeSwitch, u1.me, ns2.compass, u2.modeSwitch, u2.me)]))
check('3D: < and > around the map name, at the same places as on the 2D map, brass', u2.prev.IsShown(u2.prev) and u2.next.IsShown(u2.next) and u2.subtitle.GetText(u2.subtitle) == 'Eastern Kingdoms'
      and rect(u2.prev) == rect(u1.prev) and u2.prev.color[1] == u1.prev.color[1] > 0.7, f'{u2.subtitle.GetText(u2.subtitle)}; 3D < {rect(u2.prev)[:2]} 2D < {rect(u1.prev)[:2]}')
# > steps to the next map that has terrain, seen whole from above, the camera freed; < comes back
order = [m for m in lua_list(G.GPS_API.MapOrder) if ns2.World[m] is not None]
i0 = order.index(int(ns2.cam.map))
click(u2.next); tick(3)
went = int(ns2.cam.map); mode_next = ns2.CamMode(); sub_next = str(u2.subtitle.GetText(u2.subtitle)); dist_next = ns2.cam.dist
click(u2.prev); tick(3)
check('3D: > shows the next map with terrain whole (camera freed, name updated), < goes back', went == order[(i0 + 1) % len(order)] and mode_next == 'free' and sub_next != 'Eastern Kingdoms'
      and dist_next > 3000 and int(ns2.cam.map) == order[i0], f'{order[i0]} -> {went} ({sub_next}, {mode_next}, distance {dist_next:.0f}) -> {ns2.cam.map}')
ns2.FollowMe(); tick(30)
check('3D: opens following you; camera ring and Me gold', ns2.CamMode() == 'follow' and ns2.camButton.active == True and u2.me.active == True)
check('3D: footer: where you are, then the mode', 'Northshire Valley' in str(u2.footer.GetText(u2.footer)) and str(u2.footer.GetText(u2.footer)).endswith('Following|r'), str(u2.footer.GetText(u2.footer)))
seq = []
for _ in range(3):
    click(ns2.camButton); tick(20)
    ic = str(ns2.camButton.icon.GetTexture(ns2.camButton.icon)).split('\\')[-1]
    seq.append((ns2.CamMode(), ns2.camButton.active, str(u2.footer.GetText(u2.footer)).split('|cffc9a24a')[-1].replace('|r', ''), ic))
check('camera ring steps Follow -> Behind -> Free -> Follow (its icon shows the mode; gold while locked on you)',
      seq == [('behind', True, 'Behind you', 'cambehind'), ('free', False, 'Free camera', 'camfree'), ('follow', True, 'Following', 'camfollow')], str(seq))
hover(ns2.camButton)
tip = G.GameTooltip
check('camera ring tooltip names the mode', tip.IsShown(tip) and tip.IsOwned(tip, ns2.camButton) and ns2.camButton.tooltip(ns2.camButton)[1] == 'Camera: following you', str(ns2.camButton.tooltip(ns2.camButton)[1]))
G.GameTooltip_Hide()
ns2.SetCamMode('free'); tick(2)
check('Free: camera ring and Me brass', ns2.camButton.active == False and u2.me.active == False)
click(u2.me); tick(20)
check('Me (from Free) locks back on you the way you last chose', ns2.CamMode() == 'follow' and u2.me.active == True, ns2.CamMode())
ok = True; det = []
for yaw in (0, 45, 135, 270):
    ns2.cam.yaw = yaw; ns2.Render()
    r = ns2.compass.icon.GetRotation(ns2.compass.icon)
    det.append(f'{yaw}:{r:.3f}'); ok = ok and abs(r - math.radians(yaw)) < 1e-9
check('compass needle turned by the view yaw (north on screen)', ok, ' '.join(det))
top0 = ns2.IsTopDown()
def cell_corners(k):  # screen offsets of a grid cell's corners from the ring's centre (1 UL, 2 LL, 3 UR, 4 LR)
    t, b = ns2.topButton.cells[k], ns2.topButton
    l, bo, r, tp = rect(t)          # the texture's own rectangle (its corners before the offsets)
    bl, bb, br, bt = rect(b)
    cx, cy = (bl + br) / 2, (bb + bt) / 2 + b.centreY  # the ring's centre: the button's, raised by centreY
    base = {1: (l, tp), 2: (l, bo), 3: (r, tp), 4: (r, bo)}
    out = {}
    for i in range(1, 5):
        dx, dy = t.GetVertexOffset(t, i)
        out[i] = (base[i][0] + dx - cx, base[i][1] + dy - cy)
    return out
def edge(c, a, b): return math.hypot(c[a][0] - c[b][0], c[a][1] - c[b][1])
ns2.cam.yaw = 0; ns2.Render()
c = cell_corners(1)
check('straight down: ring gold, its grid square (far and near edges equal)', top0 and ns2.topButton.active == True and abs(edge(c, 1, 3) - edge(c, 2, 4)) < 0.01, f'far {edge(c, 1, 3):.2f} near {edge(c, 2, 4):.2f} px')
ns2.cam.yaw = 30; ns2.Render()
c30 = cell_corners(1)
ang = math.degrees(math.atan2(c30[3][1] - c30[1][1], c30[3][0] - c30[1][0]))
check('the grid turns with the view, like the needle (30 degrees)', abs(ang - 30) < 0.01, f'{ang:.3f} degrees')
ns2.cam.yaw = 0
click(ns2.topButton); tick(30)
c = cell_corners(1)
check('tilt free: ring brass, its grid in perspective (far edge shorter, squashed in depth)',
      ns2.IsTopDown() != top0 and ns2.topButton.active == False and edge(c, 1, 3) < edge(c, 2, 4) - 0.1 and edge(c, 1, 2) < edge(c, 2, 4),
      f'pitch {ns2.cam.pitch:.1f} far {edge(c, 1, 3):.2f} near {edge(c, 2, 4):.2f} side {edge(c, 1, 2):.2f} px')
pts = [p for k in range(1, 5) for p in cell_corners(k).values()]
r_tilt = max(math.hypot(x, y) for x, y in pts)
pitch_was = ns2.cam.pitch
ns2.cam.pitch, ns2.cam.yaw = 89.9, 45; ns2.UpdateGrid()  # straight down, turned: the corners reach furthest
r_top = max(math.hypot(x, y) for k in range(1, 5) for x, y in cell_corners(k).values())
ns2.cam.pitch, ns2.cam.yaw = pitch_was, 0; ns2.UpdateGrid()
ring_w = ns2.topButton.GetWidth(ns2.topButton)
check('the whole grid stays well inside the ring (within 0.22 of its width from the centre, padding included)', max(r_tilt, r_top) <= ring_w * 0.22 * 1.25,
      f'furthest corner {r_tilt:.2f} px tilted, {r_top:.2f} px straight down and turned; ring {ring_w:.0f} px')
# The drawn grid centred in the ring at every tilt and turn: the outline's four outer corners (ground
# points (+-1, +-1)) as the game draws them, 1/8 of the texture in from each outer cell's corner (the
# cell texture is drawn on the bent quad: bilinear between its 4 corners), their bounding box's centre
# within a quarter of a pixel of the ring's centre (GPS3D centres the outline as projected; the game
# stretches the texture over the bent quad without perspective, which moves the drawn line up to
# about 0.15 px; before 2026-10-18 the grid sat up to 1.3 px low when tilted).
E = 1 / 6
CELL_OF = {(-1, -1): 1, (0, -1): 2, (-1, 0): 3, (0, 0): 4}  # GPS3D's CELLS order
def drawn_corner(U, V):
    u0, v0 = (-1 if U < 0 else 0), (-1 if V < 0 else 0)
    c = cell_corners(CELL_OF[(u0, v0)])  # 1 (lo u, hi v), 2 (lo, lo), 3 (hi, hi), 4 (hi, lo)
    a, b = (U - u0 + E) / (1 + 2 * E), (V - v0 + E) / (1 + 2 * E)
    w = {2: (1 - a) * (1 - b), 1: (1 - a) * b, 4: a * (1 - b), 3: a * b}
    return sum(w[i] * c[i][0] for i in w), sum(w[i] * c[i][1] for i in w)
worst_off, worst_at = 0, ''
for pitch in (45, 50, 60, 70, 80, 89.9):
    for yaw in (0, 20, 45, 90, 135, 200, 300):
        ns2.cam.pitch, ns2.cam.yaw = pitch, yaw; ns2.UpdateGrid()
        pts = [drawn_corner(U, V) for U in (-1, 1) for V in (-1, 1)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        off = math.hypot((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        if off > worst_off: worst_off, worst_at = off, f'pitch {pitch} yaw {yaw}: ({(min(xs) + max(xs)) / 2:+.2f}, {(min(ys) + max(ys)) / 2:+.2f}) px'
ns2.cam.pitch, ns2.cam.yaw = pitch_was, 0; ns2.UpdateGrid()
check('the drawn grid is centred in the ring at every tilt and turn (its outline\'s box within 0.25 px of the centre)', worst_off <= 0.25,
      f'worst {worst_off:.3f} px at {worst_at}')
# The rings' contents on the gold ring's centre: the ring art's gold band measured in the image itself
# (the middle of the band's outer extent on each of rows and columns 12..27, in texels), taken through
# the texture coordinates and rectangle the code gives the ring texture, against the centre the disc,
# label, icon and grid are placed on (the disc's centre). Until 2026-10-18 they sat 0.38 px left.
from PIL import Image
_art = Image.open(os.path.join(HERE, 'site', 'ui', 'minimap-trackingborder.png')).convert('RGBA')
_px = _art.load()
def _gold(x, y): p = _px[x, y]; return p[3] > 150 and p[0] > 60
_cx = sum((min(k for k in range(40) if _gold(k, i)) + max(k for k in range(40) if _gold(k, i))) / 2 + 0.5 for i in range(12, 28)) / 16
_cy = sum((min(k for k in range(40) if _gold(i, k)) + max(k for k in range(40) if _gold(i, k))) / 2 + 0.5 for i in range(12, 28)) / 16
worst_ring, det = 0, []
for b in [ns1.ui.compass if hasattr(ns1, 'ui') and ns1.ui else None] + rings2:
    if b is None or not b.ring: continue
    tc = list(b.ring.GetTexCoord(b.ring))  # UL x, y, LL x, y, UR x, y, LR x, y
    l, bo, r, tp = rect(b.ring)
    gx = l + (_cx / 64 - tc[0]) / (tc[4] - tc[0]) * (r - l)
    gy = tp - (_cy / 64 - tc[1]) / (tc[3] - tc[1]) * (tp - bo)
    dl, db, dr, dt = rect(b.disc)
    dx, dy = (dl + dr) / 2 - gx, (db + dt) / 2 - gy
    worst_ring = max(worst_ring, math.hypot(dx, dy)); det.append(f'({dx:+.2f},{dy:+.2f})')
check(f'every ring\'s contents sit on the gold ring\'s centre (art centre {_cx:.2f}, {_cy:.2f} texels; within 0.1 px)', worst_ring <= 0.1 and len(det) >= 5,
      f'worst {worst_ring:.3f} px; disc minus ring per ring: ' + ' '.join(det))
# a ring's label: shrunk to fit the hole by a smaller font (not SetTextScale, which in the game left the
# shrunk "2D" about 1 px left of the ring's centre, 2026-10-21), its centre on the disc's centre
lab_det, lab_ok = [], True
for txt in ('2D', '3D', '90°', 'Behind'):
    b = u2.modeSwitch; b.SetLabel(b, txt); tick(1)
    fs = b.label; fl, fb, fr, ft = rect(fs); dl, db, dr, dt = rect(b.disc)
    w = fs.GetStringWidth(fs); off = abs((fl + fr) / 2 - (dl + dr) / 2)
    scaled = fs.GetTextScale(fs)
    lab_ok = lab_ok and w <= b.GetWidth(b) * 0.4 + 1e-6 and off < 1e-6 and scaled == 1
    lab_det.append(f'{txt}: {w:.1f} px, off {off:.2f}, text scale {scaled}')
u2.modeSwitch.SetLabel(u2.modeSwitch, '3D'); tick(1)
check('ring labels fit the hole by font size and sit on its centre', lab_ok, '; '.join(lab_det))
click(ns2.topButton); tick(20)
layout_ok(F2, u2, '3D at 900x650')
F2.SetSize(F2, 400, 300); tick(3)
layout_ok(F2, u2, '3D at 400x300 (smallest)')
F2.SetSize(F2, 900, 650); tick(3)
u2.modeSwitch._scripts.OnClick(u2.modeSwitch, 'RightButton'); tick(5)
check('mode ring in 3D, right-click: back to the 2D map', F1.IsShown(F1) and not F2.IsShown(F2))
def background(canvas):  # the canvas's bottom-most texture (BACKGROUND, sublevel -8) and its colour
    regs = [r for r in canvas._regions.values() if r._layer == 1 and r._sub == -8]
    t = regs[0]
    return t, tuple(round(v * 255) for v in list(t._color.values())[:3])
b1, c1 = background(ns1.canvas)
b2, c2 = background(ns2.canvas)
check('2D and 3D backgrounds are both the open sea of the minimap images (#081110), no gradient', c1 == c2 == (8, 17, 16) and not b1._grad and not b2._grad, f'2D {c1}, 3D {c2}')
chat()
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
