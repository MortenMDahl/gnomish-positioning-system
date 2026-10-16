# Checks the window look ("minimap rings", option B) on the sandbox engine (Lua 5.4, as in the
# sandbox): what each window shows, the rings and what they do, tooltips, and layout at the
# smallest window size. Usage: python test_look.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
toc = open(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc')).read()
gps3d_files = [l.strip().replace('\\', '/') for l in toc.splitlines() if l.strip() and not l.startswith('##')]
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua']), ('GPS3D', gps3d_files)]:
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
check('2D: rings are 2D/3D then Me', same(rings1, [u1.modeSwitch, u1.me]) and u1.modeSwitch.label.GetText(u1.modeSwitch.label) == '2D', f'{len(rings1)} rings')
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
check('2D: 2D/3D ring has a tooltip', G.GameTooltip.IsShown(G.GameTooltip) and G.GameTooltip.IsOwned(G.GameTooltip, u1.modeSwitch))
G.GameTooltip_Hide()

def layout_ok(frame, ui, name):
    fr = rect(frame); rs = [rect(b) for b in lua_list(ui.rings)]
    zs = [rect(ui.zoomIn), rect(ui.zoomOut), rect(ui.close)]
    ok_in = all(inside(r, fr) for r in rs + zs)
    ok_sep = not any(overlap(rs[i], rs[j]) for i in range(len(rs)) for j in range(i + 1, len(rs)))
    ok_zoom = not any(overlap(r, z) for r in rs for z in zs)
    ft = rect(ui.footer)
    ok_footer = not overlap(ft, rect(ui.zoomOut))
    check(f'{name}: rings, close and zoom inside the window, none overlapping', ok_in and ok_sep and ok_zoom and ok_footer, f'in {ok_in} apart {ok_sep} clear of zoom/close {ok_zoom} footer clear {ok_footer}')

layout_ok(F1, u1, '2D at 900x650')
F1.SetSize(F1, 400, 300); tick(2)
layout_ok(F1, u1, '2D at 400x300 (smallest)')
F1.SetSize(F1, 900, 650); tick(2)

# ---- 3D
click(u1.modeSwitch); tick(10); chat()
F2 = G.GPS3D_Frame
check('2D/3D ring opens the 3D view in the same place', F2.IsShown(F2) and not F1.IsShown(F1) and rect(F2) == rect(F1))
rings2 = lua_list(u2.rings)
check('3D: rings are compass, straight down, 2D/3D, camera, Me', same(rings2, [ns2.compass, ns2.topButton, u2.modeSwitch, ns2.camButton, u2.me]) and u2.modeSwitch.label.GetText(u2.modeSwitch.label) == '3D', f'{len(rings2)} rings')
check('3D: no map switch; subtitle is just the map', not u2.prev.IsShown(u2.prev) and not u2.next.IsShown(u2.next) and u2.subtitle.GetText(u2.subtitle) == 'Eastern Kingdoms', str(u2.subtitle.GetText(u2.subtitle)))
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
    t = ns2.topButton.cells[k]
    base = {1: (-0.5, 0.5), 2: (-0.5, -0.5), 3: (0.5, 0.5), 4: (0.5, -0.5)}
    out = {}
    for i in range(1, 5):
        dx, dy = t.GetVertexOffset(t, i)
        out[i] = (base[i][0] + dx, base[i][1] + dy)
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
r_max = max(math.hypot(x, y) for x, y in pts)
check('the grid stays inside the ring', r_max <= 30 * 0.3 * 1.25, f'furthest corner {r_max:.2f} px (padding included)')
click(ns2.topButton); tick(20)
layout_ok(F2, u2, '3D at 900x650')
F2.SetSize(F2, 400, 300); tick(3)
layout_ok(F2, u2, '3D at 400x300 (smallest)')
F2.SetSize(F2, 900, 650); tick(3)
click(u2.modeSwitch); tick(5)
check('2D/3D ring in 3D goes back to the 2D map', F1.IsShown(F1) and not F2.IsShown(F2))
chat()
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
