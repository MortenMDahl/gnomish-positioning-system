# Checks the map key toggle and full screen (J6, 2026-10-21) on the sandbox engine (Lua 5.4):
# - the globe on Blizzard's map (WorldMapFrame; a stand-in here with Forever's BorderFrame, its
#   CloseButton and MaximizeMinimizeFrame, Blizzard_WorldMap.xml) just left of its maximize button,
#   its tooltip, and its click: the map key opens GPS (saved), Blizzard's map closes, GPS opens on
#   the place it showed;
# - in each GPS window (2D, 3D, traditional map) the globe and the full-screen button left of the
#   close X, clear of the title, the close button and the rings; the globe's click: the map key opens
#   Blizzard's map (saved), GPS closes, Blizzard's map opens;
# - full screen in each mode: the screen and back to the exact rect, kept when switching modes and
#   over a reload, no moving or resizing, following a change of screen size, /gps reset;
# - the map key: override bindings on the keys of TOGGLEWORLDMAP while the choice is GPS, none
#   otherwise; refused in combat, so applied after it; a rebind moves them; no loop on UPDATE_BINDINGS;
# - the setting, /gps mapkey, /gps fullscreen and the /gps test line;
# - each check's code broken on purpose (MUTANTS) makes that check fail.
# Usage: python test_mapkey.py   (fill site/addons first)   NO_MUTANTS=1 skips the mutation runs.
import lupa.lua54 as lupa54, os, sys, subprocess, json
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
# (name, file, text, replacement, the check that must fail)
MUTANTS = [
    ('globe on Blizzard\'s map anchored on the maximize button instead of left of it', 'MapKey.lua', 'b:SetPoint("RIGHT", anchor, "LEFT", -1, 0)', 'b:SetPoint("RIGHT", anchor, "RIGHT", -1, 0)', "Blizzard's map: a globe just left of its maximize button"),
    ('the globe on Blizzard\'s map does not close it', 'MapKey.lua', '\tif WorldMapFrame and WorldMapFrame:IsShown() and HideUIPanel then HideUIPanel(WorldMapFrame) end\n\tif not ns.ShownMode()', '\tif not ns.ShownMode()', "globe on Blizzard's map (Westfall)"),
    ('GPS does not open where Blizzard\'s map looked', 'MapKey.lua', '\treturn { map = continent, gx = gx, gy = gy }\nend', '\treturn nil\nend', "globe on Blizzard's map (Westfall)"),
    ('Blizzard\'s map on your zone does not make GPS follow you', 'MapKey.lua', '\tif id == mine then return "you" end\n', '', "globe on Blizzard's map (your zone)"),
    ('full-screen button on top of the close button', 'Core.lua', 'full:SetPoint("RIGHT", close, "LEFT", -1, 0)', 'full:SetPoint("RIGHT", close, "RIGHT", 0, 0)', '2D: globe and full screen at the top right'),
    ('the title runs under the buttons', 'Core.lua', '\tui.title:SetPoint("TOPRIGHT", -4, -8)\n', '', '2D: globe and full screen at the top right'),
    ('the globe in GPS does not open Blizzard\'s map', 'MapKey.lua', '\tif WorldMapFrame and not WorldMapFrame:IsShown() and ToggleWorldMap then ToggleWorldMap() end\n', '', "globe in the 3D view"),
    ('leaving full screen does not go back to the saved place', 'Core.lua', '\t\tframe:SetPoint(p[1], UIParent, p[2], p[3], p[4])', '\t\tframe:SetPoint("CENTER")', '2D: full screen fills the screen and goes back to the exact rect'),
    ('the saved place and size overwritten in full screen', 'Core.lua', '\tif ns.IsFullScreen() then return end -- (the place and size to go back to stay as they were)\n', '', 'full screen leaves the saved place and size alone'),
    ('a mode switched to in full screen gets a fixed size, not the screen', 'Core.lua', '\tif ns.IsFullScreen() then\n\t\tto:ClearAllPoints()\n\t\tto:SetAllPoints(UIParent)\n\t\treturn\n\tend\n', '', 'full screen follows a change of screen size'),
    ('full screen not restored at login', 'Core.lua', '\tif db.fullScreen then frame:ClearAllPoints(); frame:SetAllPoints(UIParent) end\n', '', 'after a reload'),
    ('the window can be dragged in full screen', 'Core.lua', 'band:SetScript("OnDragStart", function() if not ns.IsFullScreen() then frame:StartMoving() end end)', 'band:SetScript("OnDragStart", function() frame:StartMoving() end)', 'full screen: no moving'),
    ('full screen keeps the expand art', 'Core.lua', 'on and "RedButton-Condense" or "RedButton-Expand"', '"RedButton-Expand"', '2D: full screen fills the screen and goes back to the exact rect'),
    ('no override binding set', 'MapKey.lua', '\tfor _, key in ipairs(want) do SetOverrideBinding(owner, false, key, GPS_COMMAND) end\n', '', 'map key on GPS'),
    ('bindings changed in combat', 'MapKey.lua', '\tif InCombat() then\n\t\tif not mk.pending', '\tif false then\n\t\tif not mk.pending', 'in combat'),
    ('the change waiting on combat never applied', 'MapKey.lua', '\t\towner:RegisterEvent("PLAYER_REGEN_ENABLED")\n', '', 'after combat'),
    ('a rebound map key not followed', 'MapKey.lua', 'owner:RegisterEvent("UPDATE_BINDINGS")\n', '', 'rebinding the map key'),
    ('UPDATE_BINDINGS answering its own change', 'MapKey.lua', '\tif event == "UPDATE_BINDINGS" and mk.busy then return end\n', '', 'one override per key'),
    ('the map key on GPS leaves Blizzard\'s map open', 'Core.lua', '\tif ns.mapkey then ns.mapkey.CloseBlizzard() end\n', '', 'quest log key'),
    ('the setting does nothing', 'Settings.lua', '\t\tset = function(v) ns.mapkey.Set(v) end,', '\t\tset = function(v) end,', 'settings page'),
    ('no /gps mapkey', 'Core.lua', '\telseif cmd == "mapkey" or cmd:match("^mapkey%s") then\n\t\tif ns.mapkey then ns.mapkey.Command(cmd:match("^mapkey%s*(.-)$")) end\n', '', '/gps mapkey'),
    ('no map key line in /gps test', 'Core.lua', '\tif ns.mapkey then ns.mapkey.SelfTest(Report) end\n', '', '/gps test'),
]
mutant = MUTANTS[int(sys.argv[sys.argv.index('--mutant') + 1])] if '--mutant' in sys.argv else None
W, H = 1280, 800

# Blizzard's world map, as far as GPS touches it: WorldMapFrame with BorderFrame.CloseButton and
# BorderFrame.MaximizeMinimizeFrame (28 px in Forever's Camelot skin, the maximize frame anchored
# left of the close button), GetMapID / SetMapID / GetViewRect, and the global functions the bindings
# and GPS call (ShowUIPanel / HideUIPanel refuse addons in combat, as UIParentPanelManager.lua does).
BLIZZARD = r'''
local S = SANDBOX
local WM = CreateFrame("Frame", "WorldMapFrame", UIParent)
WM:SetSize(1000, 640); WM:SetPoint("CENTER"); WM:SetFrameStrata("HIGH"); WM:Hide()
WM.BorderFrame = CreateFrame("Frame", nil, WM); WM.BorderFrame:SetAllPoints()
local close = CreateFrame("Button", nil, WM.BorderFrame); close:SetSize(28, 28); close:SetPoint("TOPRIGHT", 0, 3)
WM.BorderFrame.CloseButton = close
local mm = CreateFrame("Frame", nil, WM.BorderFrame); mm:SetSize(28, 28); mm:SetFrameLevel(510)
mm:SetPoint("RIGHT", close, "LEFT", -1, 0)
WM.BorderFrame.MaximizeMinimizeFrame = mm
WM.mapID = 1429
function WM:GetMapID() return self.mapID end
function WM:SetMapID(id) self.mapID = id end
function WM:GetViewRect() return { GetCenter = function() return 0.5, 0.5 end } end
function ShowUIPanel(f) if InCombatLockdown() then S.blocked[#S.blocked + 1] = "ShowUIPanel" return end f:Show() end
function HideUIPanel(f) if InCombatLockdown() then S.blocked[#S.blocked + 1] = "HideUIPanel" return end f:Hide() end
function ToggleWorldMap() if WM:IsShown() then HideUIPanel(WM) else ShowUIPanel(WM) end end
S.bindingActions.TOGGLEWORLDMAP = function() ToggleWorldMap() end
S.bindingActions.TOGGLEQUESTLOG = function() if WM:IsShown() then HideUIPanel(WM) else ShowUIPanel(WM) end end
'''

class Game:
    def __init__(self, saved=None):
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        self.L.execute(BLIZZARD)
        if saved: G.SANDBOX_RESTORE(saved)
        def toc(p): return [l.strip().replace('\\', '/') for l in open(p).read().splitlines() if l.strip() and not l.startswith('##')]
        for addon, files in [('GnomishPositioningSystem', toc(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))),
                             ('GPS3D', toc(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc')))]:
            for f in files:
                src = open(f'{SITE}/addons/{addon}/{f}').read()
                if mutant and addon == 'GnomishPositioningSystem' and f == mutant[1]:
                    assert src.count(mutant[2]) == 1, ('mutation text not found once', mutant[0])
                    src = src.replace(mutant[2], mutant[3])
                if not G.SANDBOX_LOAD(addon, f, src): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        G.SANDBOX_BINDINGS_XML(open(f'{SITE}/addons/GnomishPositioningSystem/Bindings.xml').read() if os.path.exists(f'{SITE}/addons/GnomishPositioningSystem/Bindings.xml')
                               else open(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'Bindings.xml')).read())
        G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); G.SANDBOX_FIRE('UPDATE_BINDINGS')
        self.tick(5)
        self.ns = G.SANDBOX.namespaces['GnomishPositioningSystem']; self.ns3 = G.SANDBOX.namespaces['GPS3D']
        self.chatlog = ''
        self.chat()
    def tick(self, n=1, w=None, h=None):
        for _ in range(n): self.G.SANDBOX_TICK(1 / 30, w or W, h or H)
    def chat(self):
        c = str(self.G.SANDBOX_CHAT() or '')
        if c:
            if not mutant: print('CHAT>', c.replace('\n', '\nCHAT> ')[:1500])
            errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l or 'stack overflow' in l)
            self.chatlog += c + '\n'
        return c
    def slash(self, line): self.G.SANDBOX_SLASH(line); self.tick(3); return self.chat()
    def press(self, key): r = self.G.SANDBOX_PRESS(key); self.tick(5); self.chat(); return r
    def rect(self, o): return tuple(round(v, 3) for v in self.G.SANDBOX.rect(o))
    def frames(self): return {'2D': self.G.GPS_MapFrame, '3D': self.G.GPS3D_Frame, 'Map': self.G.GPS_WorldMapFrame}
    def shown_mode(self):
        name = self.ns.ShownMode()
        return name if isinstance(name, str) else (name[0] if name else None)
    def gps_shown(self): return any(f.IsShown(f) for f in self.frames().values())
    def wm_shown(self): return bool(self.G.WorldMapFrame.IsShown(self.G.WorldMapFrame))
    def close_all(self):
        for f in self.frames().values():
            if f.IsShown(f): f.Hide(f)
        if self.wm_shown(): self.G.HideUIPanel(self.G.WorldMapFrame)
        self.tick(3)
    def ui(self, mode): return {'2D': self.ns.ui, '3D': self.ns3.ui, 'Map': self.ns.mapWindow.ui}[mode]
    def overrides(self):
        return [(o.key, o.command) for o in self.G.SANDBOX.overrides.values()]
    def tip(self, b):
        b._scripts.OnEnter(b)
        t = b.tooltip(b) if callable(b.tooltip) else b.tooltip
        self.G.GameTooltip_Hide()
        return [t[i] for i in range(1, len(t) + 1)] if not isinstance(t, str) else [t]

results = []
errors = []
def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    if not mutant: print(('PASS' if ok else 'FAIL'), name, detail)
def click(b, button='LeftButton'): b._scripts.OnClick(b, button)
def inside(a, b): return a[0] >= b[0] - 0.01 and a[1] >= b[1] - 0.01 and a[2] <= b[2] + 0.01 and a[3] <= b[3] + 0.01
def overlap(a, b): return a[0] < b[2] - 0.01 and b[0] < a[2] - 0.01 and a[1] < b[3] - 0.01 and b[1] < a[3] - 0.01
TILE = 1600 / 3

g = Game()
G, ns, ns3 = g.G, g.ns, g.ns3
DB = lambda: G.GnomishPositioningSystemDB
WM = G.WorldMapFrame
mk = ns.mapkey
same = g.L.eval('function(a, b) return rawequal(a, b) end')

# ---- defaults: Blizzard's map, nothing overridden
check('fresh install: the map key opens Blizzard\'s map, no override binding', DB().mapKey == 'blizzard' and g.overrides() == [] and mk.Choice() == 'blizzard', str(g.overrides()))

# ---- the globe on Blizzard's map
G.SANDBOX_PRESS('M'); g.tick(3)
b = mk.wmButton
mm = WM.BorderFrame.MaximizeMinimizeFrame
rb, rm = (g.rect(b) if b else None), g.rect(mm)
ok = (b is not None and g.wm_shown() and b.IsVisible(b) and G.SANDBOX.rect(b) is not None and abs(rb[2] - (rm[0] - 1)) < 0.01 and abs((rb[1] + rb[3]) / 2 - (rm[1] + rm[3]) / 2) < 0.01
      and rb[2] - rb[0] == 28 and 'globe' in str(b.icon.GetTexture(b.icon)).lower() and same(b.GetParent(b), WM.BorderFrame) and b.GetFrameLevel(b) == mm.GetFrameLevel(mm))
check("Blizzard's map: a globe just left of its maximize button (1 px gap, same middle, 28 px like it, a child of its BorderFrame at its level)", ok, f'globe {rb}, maximize {rm}')
tip = g.tip(b)
check("Blizzard's map globe tooltip: what the map key opens and what a click does", tip[0] == "Map key: Blizzard's map" and tip[1] == "The map key (M) opens Blizzard's map." and tip[2].startswith('Click: open GPS here, and the map key opens GPS'), str(tip))
check("Blizzard's map globe brass while the key opens Blizzard's map", b.active is False)
WM.SetMapID(WM, 1436)  # Westfall
click(b); g.tick(10); g.chat()
v = ns.view
west = G.SANDBOX.uiMaps[1436].box
cx_want = 32 - ((west[3] + west[4]) / 2) / TILE; cy_want = 32 - ((west[1] + west[2]) / 2) / TILE
check("globe on Blizzard's map (Westfall): the map key opens GPS (saved, overridden), Blizzard's map closed, GPS open on Westfall",
      DB().mapKey == 'gps' and not g.wm_shown() and g.shown_mode() == '2D' and abs(v.cx - cx_want) < 1e-6 and abs(v.cy - cy_want) < 1e-6 and not v.follow and g.overrides() == [('M', 'GPS_TOGGLE')] and b.active is True,
      f'mapKey {DB().mapKey}, WM {g.wm_shown()}, GPS {g.shown_mode()}, view {v.cx:.3f},{v.cy:.3f} want {cx_want:.3f},{cy_want:.3f}, overrides {g.overrides()}')
g.close_all()
G.ToggleWorldMap(); g.tick(3); WM.SetMapID(WM, 1429)  # your zone
click(b); g.tick(10); g.chat()
check("globe on Blizzard's map (your zone): GPS opens following you", not g.wm_shown() and g.shown_mode() == '2D' and v.follow is True, f'follow {v.follow}')
g.close_all()

# ---- the top-right buttons in each GPS window
LONG = 'A very long name of a zone that would run on under the buttons at the top right of the window'
def top_right_ok(mode):
    u = g.ui(mode); f = g.frames()[mode]
    u.title.SetText(u.title, LONG); g.tick(2)
    fr, gl, fs, cl, ti = g.rect(f), g.rect(u.globe), g.rect(u.fullScreen), g.rect(u.close), g.rect(u.title)
    rings = [g.rect(r) for r in u.rings.values()]
    mid = lambda r: (r[1] + r[3]) / 2
    ok = (u.globe.IsVisible(u.globe) and u.fullScreen.IsVisible(u.fullScreen) and all(inside(r, fr) for r in (gl, fs))
          and abs(fs[2] - (cl[0] - 1)) < 0.01 and abs(gl[2] - (fs[0] - 2)) < 0.01 and abs(mid(fs) - mid(cl)) < 0.01 and abs(mid(gl) - mid(cl)) < 0.01
          and not any(overlap(a, c) for a in (gl, fs) for c in [cl, ti] + rings) and not overlap(gl, fs) and ti[2] <= gl[0]
          and 'globe' in str(u.globe.icon.GetTexture(u.globe.icon)).lower() and u.fullScreen._normal.GetAtlas(u.fullScreen._normal) == 'RedButton-Expand')
    check(f'{mode}: globe and full screen at the top right, left of close (1 px, then 2 px; same middle), clear of the title (a long one cut short), close and the rings',
          ok, f'window {fr} globe {gl} full {fs} close {cl} title {ti}')
    return u

def full_ok(mode):
    u = g.ui(mode); f = g.frames()[mode]
    before = g.rect(f); saved = (tuple(DB().point.values()), DB().width, DB().height)
    click(u.fullScreen); g.tick(5)
    on = g.rect(f); atlas_on = u.fullScreen._normal.GetAtlas(u.fullScreen._normal); grip_on = u.grip.IsShown(u.grip)
    click(u.fullScreen); g.tick(5)
    after = g.rect(f); atlas_off = u.fullScreen._normal.GetAtlas(u.fullScreen._normal)
    check(f'{mode}: full screen fills the screen and goes back to the exact rect (condense art and no grip while on)',
          on == (0, 0, W, H) and after == before and atlas_on == 'RedButton-Condense' and atlas_off == 'RedButton-Expand' and not grip_on and u.grip.IsShown(u.grip)
          and (tuple(DB().point.values()), DB().width, DB().height) == saved, f'{before} -> {on} -> {after}; {atlas_on}/{atlas_off}, grip {grip_on}')

G.SANDBOX_PRESS('M'); g.tick(5)  # (the map key on GPS now: opens the 2D map)
F1 = G.GPS_MapFrame
F1.SetSize(F1, 760, 520); F1.ClearAllPoints(F1); F1.SetPoint(F1, 'TOPLEFT', G.UIParent, 'TOPLEFT', 37, -41); ns.SaveFrame(); g.tick(3)
top_right_ok('2D'); full_ok('2D')
click(ns.ui.modeSwitch); g.tick(20); g.chat()
top_right_ok('3D'); full_ok('3D')
tip3 = g.tip(ns3.ui.globe)
check('globe in GPS: tooltip says the map key opens GPS and a click opens Blizzard\'s map', tip3[0] == 'Map key: GPS' and tip3[2].startswith("Click: open Blizzard's map"), str(tip3))
click(ns3.ui.modeSwitch); g.tick(10); g.chat()
top_right_ok('Map'); full_ok('Map')
click(ns.mapWindow.ui.modeSwitch); g.tick(5)  # back to 2D

# ---- full screen across modes, saved place and size, screen size, moving, reload, reset
r0 = g.rect(F1); saved0 = (tuple(DB().point.values()), DB().width, DB().height)
click(ns.ui.fullScreen); g.tick(3)
click(ns.ui.modeSwitch); g.tick(20)
F2 = G.GPS3D_Frame
r3 = g.rect(F2)
g.tick(3, 1024, 700); r3b = g.rect(F2); g.tick(3)
check('full screen follows a change of screen size (after switching to the 3D view in full screen)', r3 == (0, 0, W, H) and r3b == (0, 0, 1024, 700), f'{r3} then {r3b}')
click(ns3.ui.modeSwitch); g.tick(10)
F3 = G.GPS_WorldMapFrame
rm3 = g.rect(F3)
click(ns.mapWindow.ui.modeSwitch); g.tick(5)
check('full screen stays on through the mode ring (2D -> 3D -> Map -> 2D), all three at the screen\'s size', r3 == (0, 0, W, H) and rm3 == (0, 0, W, H) and g.rect(F1) == (0, 0, W, H) and DB().fullScreen is True, f'3D {r3}, Map {rm3}, 2D {g.rect(F1)}')
check('full screen leaves the saved place and size alone (switching modes saves geometry)', (tuple(DB().point.values()), DB().width, DB().height) == saved0, f'{saved0} -> {(tuple(DB().point.values()), DB().width, DB().height)}')
L = g.L
L.execute('SANDBOX.moveLog = {}')
moved = G.SANDBOX.moveLog
L.execute('GPS_MapFrame.StartMoving = function(self) SANDBOX.moveLog[#SANDBOX.moveLog + 1] = "move" end; GPS_MapFrame.StartSizing = function(self) SANDBOX.moveLog[#SANDBOX.moveLog + 1] = "size" end')
band, grip = ns.ui.band, ns.ui.grip
band._scripts.OnDragStart(band); band._scripts.OnDragStop(band); grip._scripts.OnMouseDown(grip); grip._scripts.OnMouseUp(grip)
check('full screen: no moving (title band) or resizing (grip, hidden)', len(list(moved.values())) == 0 and not grip.IsShown(grip) and g.rect(F1) == (0, 0, W, H), str(list(moved.values())))
L.execute('GPS_MapFrame.StartMoving = nil; GPS_MapFrame.StartSizing = nil')
saved = str(G.SANDBOX_SAVE('GnomishPositioningSystemDB,GnomishPositioningSystemLog'))
g2 = Game(saved)
g2.G.GPS_Toggle(); g2.tick(5)
fr2 = g2.rect(g2.G.GPS_MapFrame); atl2 = g2.ns.ui.fullScreen._normal.GetAtlas(g2.ns.ui.fullScreen._normal)
click(g2.ns.ui.fullScreen); g2.tick(3)
check('after a reload: full screen remembered (opens filling the screen, condense art), and leaving it goes back to the rect from before',
      fr2 == (0, 0, W, H) and atl2 == 'RedButton-Condense' and g2.rect(g2.G.GPS_MapFrame) == r0, f'{fr2} {atl2}, then {g2.rect(g2.G.GPS_MapFrame)} (before {r0})')
check('after a reload: the map key choice remembered (override on M)', g2.ns.mapkey.Choice() == 'gps' and g2.overrides() == [('M', 'GPS_TOGGLE')], str(g2.overrides()))
g.slash('/gps reset')
check('/gps reset leaves full screen: the middle at 900x650', DB().fullScreen is False and g.rect(F1) == ((W - 900) / 2, (H - 650) / 2, (W + 900) / 2, (H + 650) / 2) and ns.ui.fullScreen._normal.GetAtlas(ns.ui.fullScreen._normal) == 'RedButton-Expand', str(g.rect(F1)))
g.slash('/gps fullscreen')
fs_on = g.rect(F1)
g.slash('/gps fullscreen')
check('/gps fullscreen toggles it', fs_on == (0, 0, W, H) and DB().fullScreen is False and g.rect(F1) != (0, 0, W, H), str(fs_on))

# ---- the globe in GPS: Blizzard's map
click(ns.ui.modeSwitch); g.tick(20)
click(ns3.ui.globe); g.tick(5); g.chat()
check("globe in the 3D view: the map key opens Blizzard's map (saved, overrides gone), GPS closed, Blizzard's map open",
      DB().mapKey == 'blizzard' and not g.gps_shown() and g.wm_shown() and g.overrides() == [] and ns3.ui.globe.active is False and mk.wmButton.active is False,
      f'{DB().mapKey}, GPS {g.gps_shown()}, WM {g.wm_shown()}, {g.overrides()}')
g.close_all()

# ---- the map key
G.SANDBOX_BIND('GPS_TOGGLE', 'SHIFT-G'); g.tick(2)
g.press('M'); a = (g.wm_shown(), g.gps_shown())
g.press('M'); b2 = (g.wm_shown(), g.gps_shown())
g.press('SHIFT-G'); c = (g.wm_shown(), g.gps_shown()); g.close_all()
check("map key on Blizzard's map: M opens and closes Blizzard's map (no override), GPS's own key still opens GPS",
      a == (True, False) and b2 == (False, False) and c == (False, True) and G.GetBindingAction('M', True) == 'TOGGLEWORLDMAP', f'{a} {b2} {c}')
L.execute('SANDBOX.setLog = {}')
nset = G.SANDBOX.setLog
L.execute('local f = SetOverrideBinding; SetOverrideBinding = function(...) SANDBOX.setLog[#SANDBOX.setLog + 1] = select(3, ...); return f(...) end')
g.slash('/gps mapkey gps')
check('one override per key for a change (no loop through UPDATE_BINDINGS, which the sandbox fires for each change)', list(nset.values()) == ['M'] and not any('stack overflow' in e for e in errors), str(list(nset.values())))
g.press('M'); a = (g.wm_shown(), g.gps_shown())
g.press('M'); b2 = (g.wm_shown(), g.gps_shown())
check('map key on GPS: M is overridden to GPS_TOGGLE and opens and closes GPS; Blizzard\'s map stays shut',
      G.GetBindingAction('M', True) == 'GPS_TOGGLE' and g.overrides() == [('M', 'GPS_TOGGLE')] and a == (False, True) and b2 == (False, False), f'{a} {b2} {g.overrides()}')
g.press('L'); ql = (g.wm_shown(), g.gps_shown())
g.press('M'); after_m = (g.wm_shown(), g.gps_shown())
check('the quest log key still opens Blizzard\'s map; then M opens GPS and closes Blizzard\'s map', ql == (True, False) and after_m == (False, True), f'{ql} {after_m}')
g.close_all()
G.SANDBOX_BIND('TOGGLEWORLDMAP', 'N', 'SHIFT-M'); g.tick(2)
check('rebinding the map key (N and SHIFT-M): the overrides follow (UPDATE_BINDINGS), M is free again', sorted(g.overrides()) == [('N', 'GPS_TOGGLE'), ('SHIFT-M', 'GPS_TOGGLE')] and G.GetBindingAction('M', True) == '', str(g.overrides()))
G.SANDBOX_BIND('TOGGLEWORLDMAP', 'M'); g.tick(2)
# combat
G.SANDBOX_COMBAT(True)
nblocked = len(G.SANDBOX.blocked)
g.slash('/gps mapkey blizzard')
testlines = g.slash('/gps test'); g.tick(70); g.chat()
check('in combat: nothing set or cleared (no blocked action), the GPS override stays until combat ends, the setting is saved, /gps test says it waits',
      len(G.SANDBOX.blocked) == nblocked and g.overrides() == [('M', 'GPS_TOGGLE')] and DB().mapKey == 'blizzard' and mk.pending is True and 'waiting for the end of combat' in testlines,
      f'blocked {list(G.SANDBOX.blocked.values())}, overrides {g.overrides()}')
g.close_all()
G.SANDBOX_COMBAT(True)
WM.Show(WM); g.tick(2)
click(mk.wmButton); g.tick(3); g.chat()
check('in combat: the globe on Blizzard\'s map saves the choice and says so, without trying to close Blizzard\'s map (refused in combat)',
      DB().mapKey == 'gps' and len(G.SANDBOX.blocked) == nblocked and g.wm_shown() and 'when combat ends' in g.chatlog, list(G.SANDBOX.blocked.values()))
g.slash('/gps mapkey blizzard')
G.SANDBOX_COMBAT(False); g.tick(2)
check('after combat: the waiting change applied (override gone)', g.overrides() == [] and mk.pending is None and len(G.SANDBOX.blocked) == nblocked, str(g.overrides()))
g.close_all()

# ---- the setting, /gps mapkey, /gps test
page = json.loads(str(G.SANDBOX_SETTINGS()))
ctl = next((c for c in page[0]['controls'] if c.get('var') == 'GPS_MapKey'), None)
G.SANDBOX_SETTING_SET('GPS_MapKey', 'gps'); g.tick(2)
on = (DB().mapKey, g.overrides())
G.SANDBOX_SETTING_SET('GPS_MapKey', 'blizzard'); g.tick(2)
off = (DB().mapKey, g.overrides())
check('settings page: "Map key opens" GPS / Blizzard\'s map (default Blizzard\'s map), each choice applied at once',
      ctl is not None and [o['value'] for o in ctl['options']] == ['gps', 'blizzard'] and ctl['default'] == 'blizzard' and on == ('gps', [('M', 'GPS_TOGGLE')]) and off == ('blizzard', []),
      f'{ctl and ctl["options"]} {on} {off}')
s1 = g.slash('/gps mapkey gps'); k1 = (DB().mapKey, g.overrides())
s2 = g.slash('/gps mapkey'); s3 = g.slash('/gps mapkey nonsense')
s4 = g.slash('/gps mapkey blizzard'); k4 = (DB().mapKey, g.overrides())
check('/gps mapkey gps|blizzard sets it (and says so); no argument says what it is; anything else shows the usage',
      k1 == ('gps', [('M', 'GPS_TOGGLE')]) and k4 == ('blizzard', []) and 'opens GPS' in s1 and 'opens GPS' in s2 and '/gps mapkey gps|blizzard' in s3 and "opens Blizzard's map" in s4, f'{s1!r} {s3!r}')
g.slash('/gps mapkey gps')
t = g.slash('/gps test'); g.tick(70); g.chat(); g.close_all()
line = next((l for l in t.split('\n') if 'map key:' in l), '')
check('/gps test: a "map key:" line (choice, the keys, the override the game reports, the globe on Blizzard\'s map)',
      'opens GPS' in line and "Blizzard's map key (TOGGLEWORLDMAP): M" in line and 'overridden: M -> GPS_TOGGLE' in line and 'globe on Blizzard\'s map: yes' in line, line)

g.chat()
check('no Lua errors', not errors, '; '.join(errors[:3]))
n = sum(1 for _, ok in results if ok)
if mutant:
    failed = [name for name, ok in results if not ok]
    hit = any(mutant[4] in name for name in failed)
    print('MUTANT', 'caught' if hit else 'NOT caught', '| failed:', failed[:4]); sys.exit(0)
caught = 0
for i, m in enumerate(MUTANTS if not os.environ.get('NO_MUTANTS') else []):
    out = subprocess.run([sys.executable, os.path.abspath(__file__), '--mutant', str(i)], capture_output=True, text=True, timeout=1200).stdout
    c = 'MUTANT caught' in out; caught += c
    print(('     caught' if c else '     NOT caught'), m[0], '->', (out.strip().split('\n')[-1] if out.strip() else 'no output')[:220])
if not os.environ.get('NO_MUTANTS'):
    check(f'every mutation is caught by its own check ({len(MUTANTS)} mutations)', caught == len(MUTANTS), f'{caught} of {len(MUTANTS)}')
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
