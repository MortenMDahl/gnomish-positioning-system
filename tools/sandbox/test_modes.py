# Checks GPS's three modes on the sandbox engine (Lua 5.4): the traditional map window (Blizzard's
# map canvas, here the engine's stand-in for it), the mode ring stepping 2D -> 3D -> Map -> 2D (and
# back with a right-click), which mode opens (the one you chose, or the traditional map where GPS
# cannot show you), the switch on entering and leaving a dungeon, floors, Me, zoom, focus between
# modes, saved place and size, the slash commands and the self-test lines.
# Usage: python test_modes.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
gps_files = toc_files(os.path.join(HERE, '..', '..', 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))
gps3d_files = toc_files(os.path.join(HERE, '..', '..', 'prototypes', 'GPS3D', 'GPS3D.toc'))
for addon, files in [('GnomishPositioningSystem', gps_files), ('GPS3D', gps3d_files)]:
    for f in files:
        if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
W, H = 1280, 800
def tick(n=1, dt=1 / 30):
    for _ in range(n): G.SANDBOX_TICK(dt, W, H)
errors = []
def chat():
    c = G.SANDBOX_CHAT()
    if c:
        print('CHAT>', c.replace('\n', '\nCHAT> '))
        errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l)
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
rect = lambda o: tuple(G.SANDBOX.rect(o))
def inside(a, b): return a[0] >= b[0] - 0.5 and a[1] >= b[1] - 0.5 and a[2] <= b[2] + 0.5 and a[3] <= b[3] + 0.5
def overlap(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
def lua_list(t): return [t[i] for i in range(1, len(t) + 1)] if t else []
_rawequal = L.eval('function(a, b) return rawequal(a, b) end')
def same(xs, ys): return len(xs) == len(ys) and all(_rawequal(a, b) for a, b in zip(xs, ys))
def click(b, button='LeftButton'): b._scripts.OnClick(b, button)
def shown(f): return bool(f.IsShown(f))
def text(fs): return str(fs.GetText(fs) or '')

def overworld(X=-8958.3, Y=-190, zone='Elwynn Forest', sub='Northshire Valley'):
    G.SANDBOX_PLAYER(X, Y, 0, 0, 0.3, zone, sub, 1429, 0.48, 0.41)
def dungeon():
    G.SANDBOX_PLAYER(0, 0, 0, -1, 0.0, 'The Deadmines', '', 291, 0.42, 0.55)
def loading_screen():
    G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', False, False); G.SANDBOX_FIRE('ZONE_CHANGED_NEW_AREA'); tick(3)
    tick(40)  # the second check, a second later

overworld()
G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); tick(2)
ns1, ns2 = G.SANDBOX.namespaces['GnomishPositioningSystem'], G.SANDBOX.namespaces['GPS3D']
F1, F2, F3 = G.GPS_MapFrame, G.GPS3D_Frame, G.GPS_WorldMapFrame
mw = ns1.mapWindow
u1, u2, u3 = ns1.ui, ns2.ui, mw.ui
def only(f): return [shown(x) for x in (F1, F2, F3)] == [_rawequal(x, f) for x in (F1, F2, F3)]

# ---- opening and the mode ring
check('three modes available, in ring order', lua_list(ns1.AvailableModes()) == ['2D', '3D', 'Map'], str(lua_list(ns1.AvailableModes())))
G.GPS_Toggle(); tick(5); chat()
check('opening in the world (nothing chosen yet): the 2D map', only(F1) and ns1.db.mode == '2D')
r0 = rect(F1)
click(u1.modeSwitch); tick(10)
check('mode ring 2D -> 3D, same place and size', only(F2) and rect(F2) == r0 and ns1.db.mode == '3D')
click(u2.modeSwitch); tick(5); chat()
check('mode ring 3D -> traditional map, same place and size', only(F3) and rect(F3) == r0 and ns1.db.mode == 'Map')
click(u3.modeSwitch); tick(5)
check('mode ring Map -> 2D', only(F1) and ns1.db.mode == '2D')
click(u1.modeSwitch, 'RightButton'); tick(5)
check('right-click 2D -> traditional map (back one)', only(F3))
click(u3.modeSwitch, 'RightButton'); tick(10)
check('right-click Map -> 3D', only(F2))
click(u2.modeSwitch, 'RightButton'); tick(5)
check('right-click 3D -> 2D', only(F1))
tip3 = lua_list(u3.modeSwitch.tooltip(u3.modeSwitch))
check('Map mode ring tooltip', tip3 == ['Traditional map', 'Click: 2D map of the same place', 'Right-click: 3D view'], str(tip3))

# ---- the traditional map window
click(u1.modeSwitch, 'RightButton'); tick(5); chat()
m = mw.map
check('built from MapCanvasMixin with a MapCanvasFrameScrollContainerTemplate scroll frame', m is not None and m.ScrollContainer is not None and m.ScrollContainer.Child is not None and _rawequal(m.OnLoad, G.MapCanvasMixin.OnLoad))
provs = [p._name for p in m.dataProviders.keys()]
check('Blizzard\'s data providers added (27: the zone map\'s set, the world map\'s quest layers, the area label; GroupMembers draws you)', len(provs) == 27 and 'QuestDataProviderMixin' in provs and 'QuestBlobDataProviderMixin' in provs and 'GroupMembersDataProviderMixin' in provs and 'AreaLabelDataProviderMixin' in provs, f'{len(provs)} providers')
al = [p for p in m.dataProviders.keys() if p._name == 'AreaLabelDataProviderMixin'][0]
check('hovered zone name sits under the title band (AreaLabel offset -58)', al.offsetY == -58)
lm = m.GetPinFrameLevelsManager(m)
check('controls above the pins (close at level >= 9500; pins end at ' + str(lm.maxLevel) + ')', u3.close.GetFrameLevel(u3.close) >= 9500 and u3.close.GetFrameLevel(u3.close) > 9000 and lm.maxLevel < 9000, f'close {u3.close.GetFrameLevel(u3.close)}')
check('Map: rings are compass, mode ring (folded map icon), Me', same(lua_list(u3.rings), [u3.compass, u3.modeSwitch, u3.me]) and str(u3.modeSwitch.icon.GetTexture(u3.modeSwitch.icon)).endswith('media\\map') and shown(u3.modeSwitch.icon))
check('compass, mode ring and Me at the same places in all three windows', all(rect(a) == rect(b) == rect(c) for a, b, c in ((u1.compass, u2.compass, u3.compass), (u1.modeSwitch, u2.modeSwitch, u3.modeSwitch), (u1.me, u2.me, u3.me))), str([rect(x)[:2] for x in (u1.compass, u2.compass, u3.compass, u1.modeSwitch, u2.modeSwitch, u3.modeSwitch)]))
check('the compass points north (needle unturned) in the 2D map and the traditional map', u1.compass.icon.GetRotation(u1.compass.icon) == 0 and u3.compass.icon.GetRotation(u3.compass.icon) == 0 and str(u3.compass.icon.GetTexture(u3.compass.icon)).endswith('media\\needle'))
check('Map: opens on your zone (title), the map above it as subtitle, no floor arrows', text(u3.title) == 'Elwynn Forest' and text(u3.subtitle) == 'Eastern Kingdoms' and not shown(u3.prev) and not shown(u3.next), f'{text(u3.title)} / {text(u3.subtitle)}')
tick(10)
check('Map: footer says where you are; Me ring gold (your map)', 'Northshire Valley' in text(u3.footer) and u3.me.active == True, text(u3.footer))
check('Map: close uses the RedButton-Exit atlas; zoom rings at the bottom right', u3.close._normal.GetAtlas(u3.close._normal) == 'RedButton-Exit' and inside(rect(u3.zoomIn), rect(F3)) and inside(rect(u3.zoomOut), rect(F3)))
sc = m.ScrollContainer
l, b, r, t = rect(sc)
G.SANDBOX_MOUSE('move', (l + r) / 2, (b + t) / 2, None, 0); G.SANDBOX_MOUSE('down', (l + r) / 2, (b + t) / 2, 'RightButton', 0); G.SANDBOX_MOUSE('up', (l + r) / 2, (b + t) / 2, 'RightButton', 0); tick(10)
check('right-click on the map: the map above (Eastern Kingdoms); Me brass', text(u3.title) == 'Eastern Kingdoms' and text(u3.subtitle) == 'Azeroth' and u3.me.active == False, f'{text(u3.title)} / {text(u3.subtitle)} / Me {u3.me.active}')
# click Westfall's box on the continent
wf = [bx for bx in lua_list(sc.boxes) if bx.id == 1436][0]
cl, cb, cr, ct = rect(sc.Child)
x, y = cl + (wf.l + wf.r) / 2 * (cr - cl), ct - (wf.t + wf.b) / 2 * (ct - cb)
G.SANDBOX_MOUSE('move', x, y, None, 0); G.SANDBOX_MOUSE('down', x, y, 'LeftButton', 0); G.SANDBOX_MOUSE('up', x, y, 'LeftButton', 0); tick(5)
check('click a zone on the continent: that zone (Westfall)', text(u3.title) == 'Westfall' and m.GetMapID(m) == 1436, text(u3.title))
click(u3.zoomIn); tick(2)
z1 = sc.zoom
click(u3.zoomOut); tick(2)
check('zoom rings zoom the map in and out', z1 == 1 and sc.zoom == 0, f'{z1} -> {sc.zoom}')
click(u3.me); tick(10)
check('Me: back to your map, gold', text(u3.title) == 'Elwynn Forest' and u3.me.active == True)
for w_, h_ in ((900, 650), (400, 300)):
    F3.SetSize(F3, w_, h_); tick(3)
    fr = rect(F3); rs = [rect(x) for x in lua_list(u3.rings)]; zs = [rect(u3.zoomIn), rect(u3.zoomOut), rect(u3.close)]
    ok = all(inside(x, fr) for x in rs + zs) and not any(overlap(a, b) for a in rs for b in zs) and not overlap(rect(u3.footer), rect(u3.zoomOut))
    check(f'Map at {w_}x{h_}: rings, close and zoom inside, none overlapping', ok)
F3.SetSize(F3, 700, 500); tick(2)
F3.Hide(F3); tick(2)
check('closing the map window keeps its size as the saved one', abs(ns1.db.width - 700) < 0.01 and abs(ns1.db.height - 500) < 0.01, f'{ns1.db.width}x{ns1.db.height}')

# ---- focus between modes: the map looks at Westfall, 2D opens there, and back
G.GPS_Toggle(); tick(5)  # db.mode is Map now
check('opening again: the mode you chose last (the traditional map)', only(F3) and ns1.db.mode == 'Map')
mw.SetMap(1436); tick(3)
click(u3.modeSwitch); tick(5)
gx, gy = ns1.view.cx, ns1.view.cy
X, Y = ns1.GridToWorld(gx, gy)
wb = G.SANDBOX.uiMaps[1436].box  # Westfall's map: top X, bottom X, left Y, right Y
check('Map (Westfall) -> 2D opens on the middle of Westfall\'s map, not following you', only(F1) and not ns1.view.follow
      and abs(X - (wb[1] + wb[2]) / 2) < 1 and abs(Y - (wb[3] + wb[4]) / 2) < 1, f'world {X:.0f}, {Y:.0f}')
click(u1.modeSwitch, 'RightButton'); tick(5)
check('2D (looking at Westfall) -> Map opens on Westfall', only(F3) and m.GetMapID(m) == 1436 and u3.me.active == False, text(u3.title))
F3.Hide(F3); tick(2)

# ---- dungeons: the traditional map opens where GPS cannot show you
ns1.db.mode = '3D'
dungeon(); loading_screen(); chat()
G.GPS_Toggle(); tick(5); chat()
check('in a dungeon, opening shows the traditional map (you chose 3D)', only(F3) and ns1.autoMap == True and ns1.db.mode == '3D')
check('dungeon map with floors: title, floor 1 of 2, < > shown', text(u3.title) == 'The Deadmines' and text(u3.subtitle) == 'The Deadmines  (1 of 2)' and shown(u3.prev) and shown(u3.next), text(u3.subtitle))
check('your arrow on the dungeon map (Blizzard draws it from the game; here the stand-in)', shown(sc.arrow))
click(u3.next); tick(3)
check('> : the next floor (Ironclad Cove), Me brass', m.GetMapID(m) == 292 and text(u3.subtitle) == 'Ironclad Cove  (2 of 2)' and u3.me.active == False, text(u3.subtitle))
click(u3.next); tick(3)
check('> wraps to the first floor', m.GetMapID(m) == 291)
click(u3.prev); tick(3); click(u3.me); tick(3)
check('Me: your floor again', m.GetMapID(m) == 291 and u3.me.active == True)
overworld(); loading_screen(); chat()
check('leaving the dungeon: back to the mode you chose (3D)', only(F2) and ns1.autoMap is None)

# 2D open following you, then into a dungeon and out again
click(u2.modeSwitch, 'RightButton'); tick(5)
check('2D open, following you', only(F1) and ns1.view.follow and ns1.db.mode == '2D')
dungeon(); loading_screen(); chat()
check('entering a dungeon with 2D open: switches to the traditional map', only(F3) and ns1.autoMap == True and ns1.db.mode == '2D')
overworld(); loading_screen()
check('leaving: back to 2D', only(F1) and ns1.autoMap is None)
# a mode picked by hand in the dungeon stays
dungeon(); loading_screen()
click(u3.modeSwitch); tick(5)
check('in the dungeon, picking 2D by hand: 2D, remembered, no automatic switch pending', only(F1) and ns1.db.mode == '2D' and ns1.autoMap is None)
loading_screen()
check('... and it stays at the next loading screen inside', only(F1))
overworld(); loading_screen()
# 2D looking elsewhere (not following): not switched
ns1.view.follow = False; dungeon(); loading_screen()
check('2D looking elsewhere when you enter a dungeon: left alone', only(F1))
overworld(); loading_screen(); ns1.view.follow = True
F1.Hide(F1); tick(2)

# ---- the 3D window keeps its place and size (audit finding 1); /gps3d opens through the modes (9)
G.SANDBOX_SLASH('/gps 3d'); tick(10)
F2.ClearAllPoints(F2); F2.SetPoint(F2, 'TOPLEFT', G.UIParent, 'BOTTOMLEFT', 50, 750); F2.SetSize(F2, 600, 400)
u2.band._scripts.OnDragStop(u2.band); tick(2)   # as after dragging the title band
moved = rect(F2)
F2.Hide(F2); tick(2)
G.GPS_Toggle(); tick(10)
check('3D window: moved and resized, closed, opened again: same place and size', only(F2) and rect(F2) == moved, f'{moved} -> {rect(F2)}')
F2.SetSize(F2, 700, 450); u2.grip._scripts.OnMouseUp(u2.grip); tick(2)   # as after dragging the corner
sized = rect(F2)
G.SANDBOX_SLASH('/gps 2d'); tick(5)
check('... and the 2D map opens there too', only(F1) and rect(F1) == sized)
G.SANDBOX_SLASH('/gps3d'); tick(10)
check('/gps3d with the 2D map open: the 3D view in its place, one window', only(F2) and rect(F2) == sized and ns1.db.mode == '3D')
G.SANDBOX_SLASH('/gps3d'); tick(2)
check('/gps3d again closes it', not shown(F1) and not shown(F2) and not shown(F3))
G.SANDBOX_SLASH('/gps map'); tick(5)
G.SANDBOX_SLASH('/gps3d top'); tick(10)
check('/gps3d top with the traditional map open: the 3D view replaces it', only(F2))
G.SANDBOX_SLASH('/gps3d top'); tick(10)
F2.Hide(F2); tick(2)
G.SANDBOX_CHAT()

# ---- Escape, slash commands, self-test
G.SANDBOX_SLASH('/gps map'); tick(5)
check('/gps map opens the traditional map (and remembers it)', only(F3) and ns1.db.mode == 'Map')
G.SANDBOX_KEY('ESCAPE'); tick(2)
check('Escape closes it', not shown(F3))
G.SANDBOX_SLASH('/gps 3d'); tick(5)
check('/gps 3d', only(F2) and ns1.db.mode == '3D')
G.SANDBOX_SLASH('/gps 2d'); tick(5)
check('/gps 2d', only(F1) and ns1.db.mode == '2D')
G.SANDBOX_CHAT()

# ---- title: the zone in the middle of the view; footer: where you are
TILE = 1600 / 3
def grid_of(zone, x=0.5, y=0.5):  # a point of a stand-in zone, from its world box
    bx = G.SANDBOX.uiMaps[zone].box
    X = bx[1] - y * (bx[1] - bx[2]); Y = bx[3] - x * (bx[3] - bx[4])
    return 32 - Y / TILE, 32 - X / TILE
v1 = ns1.view
overworld(); tick(10)  # 2D open, following you in Northshire
check('2D title: your zone while following you, the map under it, where you are in the footer',
      text(u1.title) == 'Elwynn Forest' and text(u1.subtitle) == 'Eastern Kingdoms' and 'Northshire Valley' in text(u1.footer), f'{text(u1.title)} / {text(u1.subtitle)} / {text(u1.footer)}')
v1.follow = False; v1.cx, v1.cy = grid_of(1436); ns1.Layout(); tick(8)
check('2D title: panned to Westfall, the title says Westfall, the footer still where you are', text(u1.title) == 'Westfall' and 'Northshire Valley' in text(u1.footer), f'{text(u1.title)} / {text(u1.footer)}')
v1.cx, v1.cy = grid_of(1426, 0.3, 0.6); ns1.Layout(); tick(8)
check('2D title: Dun Morogh', text(u1.title) == 'Dun Morogh', text(u1.title))
v1.cx, v1.cy = grid_of(1415, 0.05, 0.95); ns1.Layout(); tick(8)
check('2D title: where no zone is (the sea), the map\'s name', text(u1.title) == 'Eastern Kingdoms', text(u1.title))
G.SANDBOX_SLASH('/gps 3d'); tick(10)
ns2.SetCamMode('free'); gx, gy = grid_of(1436); ns2.cam.x, ns2.cam.y = gx * TILE, -gy * TILE; ns2.Render(); tick(2)
check('3D title: the zone in the middle of the view (Westfall); footer: still where you are', text(u2.title) == 'Westfall' and text(u2.subtitle) == 'Eastern Kingdoms' and 'Northshire Valley' in text(u2.footer), f'{text(u2.title)} / {text(u2.footer)}')
ns2.FollowMe('follow'); tick(40)
check('3D title: following you again, your zone', text(u2.title) == 'Elwynn Forest', text(u2.title))
# every zone of both continents: a point that the zone data puts in the zone, then the 2D title there
L.execute('''
function SANDBOX_POINTIN(id)  -- the first chunk (scanning from the box's middle outwards) in zone map id
	local m = SANDBOX.uiMaps[id]
	local b = m.box
	local cx, cy = (b[1] + b[2]) / 2, (b[3] + b[4]) / 2
	local step = 1600 / 3 / 16
	for r = 0, 400 do
		for dx = -r, r do
			for _, dy in ipairs(r == 0 and { 0 } or { -r, r }) do
				for _, p in ipairs({ { dx, dy }, { dy, dx } }) do
					local X, Y = cx + p[1] * step, cy + p[2] * step
					if SANDBOX.mapAt(m.continent, X, Y) == id then return X, Y end
				end
			end
		end
	end
end''')
zones = [(int(z[1]), str(z[3]), int(z[4])) for z in lua_list(G.SANDBOX_ZONES.zones)]
missing, wrong, texts = [], [], []
G.SANDBOX_SLASH('/gps 2d'); tick(5)
v1.follow = False
for uid, name, cont in zones:
    pt = L.eval(f'function() local X, Y = SANDBOX_POINTIN({uid}); return X and {{ X, Y }} end')()
    if pt is None: missing.append(name); continue
    X, Y = pt[1], pt[2]
    ns1.ShowMap(cont, True); v1.follow = False; v1.cx, v1.cy = 32 - Y / TILE, 32 - X / TILE; ns1.Layout(); tick(7)
    if text(u1.title) != name: wrong.append((name, text(u1.title)))
    G.SANDBOX_PLAYER(X, Y, 0, cont, 0, 'stale', 'stale', -1, -1, -1)
    if str(G.GetZoneText()) != name: texts.append((name, str(G.GetZoneText())))
check(f'2D title: every zone of both continents ({len(zones)}): the title names the zone in the middle of the view',
      len(zones) >= 50 and not missing and not wrong, f'missing {missing}, wrong {wrong[:5]}')
check('zone texts (footer, readout) come from your position for every zone, not from the last place you went to', not texts, str(texts[:5]))
overworld(); tick(2)
G.SANDBOX_SLASH('/gps 2d'); tick(5); ns1.FollowPlayer(); tick(5)
G.SANDBOX_CHAT()
G.SANDBOX_SLASH('/gps test'); tick(90)
out = G.SANDBOX_CHAT() or ''
lines = [l for l in out.split('\n') if 'modes:' in l or 'traditional map:' in l]
print('\n'.join(lines))
check('self-test reports the modes and the traditional map', any('modes: 2D, 3D, Map; opening here picks 2D map' in l for l in lines) and any('traditional map: your map 1429 (Elwynn Forest), 1 art layer(s), 27 data providers, controls at level' in l for l in lines))
errors.extend(l for l in out.split('\n') if 'Lua error' in l)
check('no Lua errors or unsimulated calls along the way', not errors, '; '.join(errors[:3]))
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
