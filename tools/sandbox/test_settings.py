# Checks GPS's page in Options > AddOns on the sandbox engine (Lua 5.4), whose Settings stand-in
# keeps what the addons register, with the argument checks of the game's Blizzard_Settings_Shared:
# the page and its order, every control's value and effect, the defaults (= a fresh install), the
# dungeon setting, /gps options, and GPS without GPS3D or without the Settings API.
# Usage: python test_settings.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os, re, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
GPS_FILES = toc_files(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))
GPS3D_FILES = toc_files(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc'))
W, H = 1280, 800
results, errors = [], []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

class Game:
    def __init__(self, with3d=True, settings_api=True):
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        if not settings_api: self.L.execute('Settings = nil; CreateSettingsListSectionHeaderInitializer = nil; CreateSettingsButtonInitializer = nil')
        addons = [('GnomishPositioningSystem', GPS_FILES)] + ([('GPS3D', GPS3D_FILES)] if with3d else [])
        for addon, files in addons:
            for f in files:
                if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        self.overworld()
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); self.tick(2)
        self.ns1 = G.SANDBOX.namespaces['GnomishPositioningSystem']
        self.ns2 = G.SANDBOX.namespaces['GPS3D'] if with3d else None
        self.chat()
    def tick(self, n=1, dt=1 / 30):
        for _ in range(n): self.G.SANDBOX_TICK(dt, W, H)
    def chat(self):
        c = self.G.SANDBOX_CHAT()
        if c:
            print('CHAT>', c.replace('\n', '\nCHAT> '))
            errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'not simulated' in l)
        return str(c or '')
    def overworld(self):
        self.G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
    def goldshire(self):
        self.G.SANDBOX_PLAYER(-9464, 62, 0, 0, 1.0, 'Elwynn Forest', 'Goldshire', 1429, 0.42, 0.65)
    def dungeon(self):
        self.G.SANDBOX_PLAYER(0, 0, 0, -1, 0.0, 'The Deadmines', '', 291, 0.42, 0.55)
    def loading_screen(self):
        G = self.G
        G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', False, False); G.SANDBOX_FIRE('ZONE_CHANGED_NEW_AREA'); self.tick(3); self.tick(40)
    def page(self):
        return json.loads(str(self.G.SANDBOX_SETTINGS()))
    def control(self, var):
        for c in self.page()[0]['controls']:
            if c.get('var') == var: return c
    def set(self, var, value):
        self.G.SANDBOX_SETTING_SET(var, 'true' if value is True else 'false' if value is False else str(value)); self.tick(2); self.chat()
    def click(self, name):
        cat = self.page()[0]
        for i, c in enumerate(cat['controls']):
            if c['kind'] == 'button' and c['name'] == name: self.G.SANDBOX_SETTING_CLICK(cat['id'], i + 1)
        self.tick(2); self.chat()
    def shown(self, f): return bool(f.IsShown(f))
    def frames(self): return self.G.GPS_MapFrame, self.G.GPS3D_Frame, self.G.GPS_WorldMapFrame
    def only(self, f):
        fs = [x for x in self.frames() if x is not None]
        same = self.L.eval('function(a, b) return rawequal(a, b) end')
        return [self.shown(x) for x in fs] == [bool(same(x, f)) for x in fs]
    def rect(self, f): return tuple(self.G.SANDBOX.rect(f))
    def close_all(self):
        for f in self.frames():
            if f is not None and self.shown(f): f.Hide(f)
        self.tick(2)

g = Game()
G, ns1, ns2 = g.G, g.ns1, g.ns2
F1, F2, F3 = g.frames()
DB = lambda: G.GnomishPositioningSystemDB
DB3 = lambda: G.GPS3D_DB

# ---- S1: the page
cats = g.page()
check('one AddOns category, named after the addon', len(cats) == 1 and cats[0]['name'] == 'Gnomish Positioning System', str([c['name'] for c in cats]))
controls = cats[0]['controls']
layout = [(c['kind'], c['name']) for c in controls]
want = [('header', 'Map window'), ('choice', 'Opens as'), ('check', "Traditional map where GPS can't show you"), ('choice', 'Map key opens'), ('button', 'Window'),
        ('header', 'Quests'), ('check', 'Your quests on the 2D map and in the 3D view'),
        ('header', 'Other addons'), ('check', "Other addons' map markers"),
        ('header', '3D view'), ('choice', 'You are shown as'), ('choice', 'Camera on you'), ('check', 'Look straight down'), ('check', 'Buildings'),
        ('slider', 'Building detail'), ('choice', 'Buildings close up'), ('check', 'Props and trees'), ('slider', 'Props and trees at most'),
        ('slider', 'Model distance'), ('slider', 'Smallest model'), ('slider', 'Ground detail'), ('slider', 'Turn your character'),
        ('header', 'Minimap'), ('check', 'Use GPS as minimap'), ('slider', 'Minimap tilt'), ('slider', 'Minimap ground detail'), ('slider', 'Minimap building detail'),
        ('header', 'Position fixes'), ('check', "Swap the map's axes"), ('check', 'Turn the arrow the other way'),
        ('header', 'Debug log'), ('check', 'Keep a debug log'), ('button', 'Debug log')]
check('page: sections and controls in order', layout == want, str(layout))
check('every control has a tooltip', all(c.get('tooltip') for c in controls if c['kind'] != 'header'), str([c['name'] for c in controls if c['kind'] != 'header' and not c.get('tooltip')]))

# ---- S5: defaults = a fresh install (the values the code starts from without saved settings)
core = open(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'Core.lua')).read()
src3 = open(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.lua')).read()
mdef = re.search(r'ns\.modelDefaults = \{(.*?)\}', open(os.path.join(ROOT, 'prototypes', 'GPS3D', 'Models.lua')).read()).group(1)
mval = lambda k: (lambda v: True if v == 'true' else False if v == 'false' else int(v) if v.isdigit() else v.strip('"'))(re.search(k + r' = ([^,]+)', mdef).group(1).strip())
fresh = {
    'GPS_OpenAs': re.search(r'local defaults = \{.*mode = "(\w+)"', core).group(1),
    'GPS_AutoTraditional': 'autoTraditional = true' in re.search(r'local defaults = \{.*\}', core).group(0),
    'GPS_MapKey': re.search(r'local defaults = \{.*mapKey = "(\w+)"', core).group(1),
    'GPS3D_Marker': re.search(r'local markerMode = "(\w+)"', src3).group(1),
    'GPS3D_Camera': re.search(r'GPS3D_DB\.camMode or "(\w+)"\)', src3).group(1),
    'GPS3D_TopDown': 'if GPS3D_DB.topDown ~= false then SetTopDown(true, true)' in src3,
    'GPS3D_Buildings': re.search(r'local useDetail = (\w+)', src3).group(1) == 'true',
    'GPS3D_BuildingBudget': int(re.search(r'local DETAIL_BUDGET = (\d+)', src3).group(1)),
    'GPS3D_GridBudget': int(re.search(r'local TRI_BUDGET = (\d+)', src3).group(1)),
    'GPS3D_ModelYaw': 180 // int(re.search(r'local MODEL_YAW = math\.pi / (\d+)', src3).group(1)),
    'GPS_Quests': 'quests = true' in re.search(r'local defaults = \{.*\}', core).group(0),
    'GPS_AddonMarkers': 'addonMarkers = true' in re.search(r'local defaults = \{.*\}', core).group(0),
    'GPS_SwapAxes': False, 'GPS_FlipFacing': False, 'GPS_DebugLog': False,
    'GPS3D_BuildingModels': mval('buildingModels'), 'GPS3D_Props': mval('props'), 'GPS3D_ModelCount': mval('modelCount'),
    'GPS3D_ModelRange': mval('modelRange'), 'GPS3D_ModelPx': mval('modelPx'),
    # (GPS3D's Minimap.lua, since 2026-10-22: off, and the tilt it starts with)
    'GPS3D_Minimap': re.search(r'\ton = (\w+),', open(f'{SITE}/addons/GPS3D/Minimap.lua').read()).group(1) == 'true',
    'GPS3D_MinimapTilt': int(re.search(r'\ttilt = (\d+),', open(f'{SITE}/addons/GPS3D/Minimap.lua').read()).group(1)),
    'GPS3D_MinimapGrid': int(re.search(r'\tgrid = (\d+),', open(f'{SITE}/addons/GPS3D/Minimap.lua').read()).group(1)),
    'GPS3D_MinimapBuildings': int(re.search(r'\tdetail = (\d+),', open(f'{SITE}/addons/GPS3D/Minimap.lua').read()).group(1)),
}
bad = [(c['var'], c['default'], fresh[c['var']]) for c in controls if c.get('var') and c['default'] != fresh[c['var']]]
check('each default equals the code\'s own starting value', not bad and len([c for c in controls if c.get('var')]) == len(fresh), str(bad))
bad = [(c['var'], c['value'], c['default']) for c in controls if c.get('var') and c['value'] != c['default']]
check('fresh install: every control shows its default', not bad, str(bad))
check('slider labels: counts and degrees', g.control('GPS3D_BuildingBudget')['label'] == '4000' and g.control('GPS3D_ModelYaw')['label'] == '90°',
      g.control('GPS3D_ModelYaw')['label'])

# ---- S2: Map window
opts = [o['value'] for o in g.control('GPS_OpenAs')['options']]
check('Opens as: the three modes', opts == ['2D', '3D', 'Map'], str(opts))
g.set('GPS_OpenAs', '3D')
G.GPS_Toggle(); g.tick(10)
check('Opens as 3D: saved, and the key binding opens the 3D view', DB().mode == '3D' and g.only(F2) and g.control('GPS_OpenAs')['value'] == '3D')
g.close_all()
g.set('GPS_OpenAs', 'Map'); G.GPS_Toggle(); g.tick(5)
check('Opens as traditional map', DB().mode == 'Map' and g.only(F3))
g.close_all()
g.set('GPS_OpenAs', '2D'); G.GPS_Toggle(); g.tick(5)
check('Opens as 2D map', DB().mode == '2D' and g.only(F1))
F1.ClearAllPoints(F1); F1.SetPoint(F1, 'TOPLEFT', G.UIParent, 'TOPLEFT', 10, -10); F1.SetSize(F1, 500, 400); G.SANDBOX.call(ns1.SaveFrame); g.tick(2)
moved = g.rect(F1)
g.click('Window')
r = g.rect(F1)
cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
check('Reset: the window back in the middle at its first size, and saved', abs(cx - W / 2) < 1 and abs(cy - H / 2) < 1 and abs(r[2] - r[0] - 900) < 0.5 and abs(r[3] - r[1] - 650) < 0.5
      and DB().width == 900 and DB().point[1] == 'CENTER' and moved != r, f'{moved} -> {r}')
g.close_all()
g.set('GPS_OpenAs', '3D'); G.GPS_Toggle(); g.tick(10)
F2.ClearAllPoints(F2); F2.SetPoint(F2, 'TOPLEFT', G.UIParent, 'TOPLEFT', 20, -20); F2.SetSize(F2, 600, 400); g.tick(2)
g.click('Window')
check('Reset with the 3D view open: it moves too', g.rect(F2) == g.rect(F1) and abs(g.rect(F2)[2] - g.rect(F2)[0] - 900) < 0.5, f'{g.rect(F2)}')
g.close_all(); g.set('GPS_OpenAs', '2D')

# ---- S3: the traditional map where GPS can't show you
g.dungeon(); g.loading_screen()
G.GPS_Toggle(); g.tick(5)
check('setting on (default): a dungeon opens the traditional map', g.only(F3))
g.close_all()
g.set('GPS_AutoTraditional', False)
G.GPS_Toggle(); g.tick(5)
check('setting off: a dungeon opens your mode (2D)', g.only(F1) and DB().autoTraditional is False and g.control('GPS_AutoTraditional')['value'] is False)
g.close_all()
g.overworld(); g.loading_screen()
G.GPS_Toggle(); g.tick(5)
g.dungeon(); g.loading_screen()
check('setting off: entering a dungeon keeps the 2D map', g.only(F1))
g.overworld(); g.loading_screen()
g.set('GPS_AutoTraditional', True)
g.dungeon(); g.loading_screen()
check('setting on again: entering a dungeon switches to the traditional map', g.only(F3))
g.overworld(); g.loading_screen()
check('... and back to 2D outside', g.only(F1))
g.close_all()

# ---- S2: 3D view
g.goldshire(); g.set('GPS_OpenAs', '3D'); G.GPS_Toggle(); g.tick(30)
st = ns2.stats
actor = lambda: [a for a in ns2.scene._actors.values() if a._model == 'unit:player'][0]
def marker_state(): return bool(ns2.decal.IsShown(ns2.decal)), bool(actor()._shown)
g.set('GPS3D_Marker', 'arrow'); g.tick(2); a = marker_state()
g.set('GPS3D_Marker', 'model'); g.tick(2); m = marker_state()
g.set('GPS3D_Marker', 'both'); g.tick(2); b = marker_state()
check('You are shown as: arrow / character / both, saved', a == (True, False) and m == (False, True) and b == (True, True) and DB3().marker == 'both', f'{a} {m} {b}')
g.set('GPS3D_Camera', 'behind'); g.tick(40)
check('Camera on you: Behind, now and saved', ns2.CamMode() == 'behind' and DB3().camMode == 'behind')
g.set('GPS3D_Camera', 'follow'); g.tick(40)
check('Camera on you: Follow', ns2.CamMode() == 'follow' and DB3().camMode == 'follow')
g.set('GPS3D_TopDown', False); g.tick(30)
check('Look straight down off: tilts back, saved', not ns2.IsTopDown() and ns2.cam.pitch < 89 and DB3().topDown is False, f'pitch {ns2.cam.pitch:.1f}')
g.set('GPS3D_TopDown', True); g.tick(30)
check('Look straight down on', ns2.IsTopDown() and abs(ns2.cam.pitch - 89.9) < 1e-6 and DB3().topDown is True)
# (the simplified building shapes, which these two controls are about; with the game's buildings loading,
# as in the sandbox, the game draws them here instead: Stormwind's one building model reaches Northshire)
g.set('GPS3D_BuildingModels', 'simple'); g.tick(10)
ns2.cam.dist = 300; g.tick(5); ns2.Render(); g.tick(5)
d_on, dt_on = st.detail, st.detailTris
g.set('GPS3D_Buildings', False); g.tick(5)
d_off = st.detail
g.set('GPS3D_Buildings', True); g.tick(20)
check('Buildings: off draws none, on draws them, saved', dt_on > 0 and d_off == 0 and st.detail > 0 and DB3().detail is True, f'on {d_on} blocks ({dt_on} tris), off {d_off}')
g.set('GPS3D_BuildingBudget', 1000); g.tick(20)
check('Building detail 1000: at most 1000 building triangles, saved', 0 < st.detailTris <= 1000 and DB3().buildings == 1000, f'{st.detailTris} (was {dt_on})')
g.set('GPS3D_BuildingBudget', 4000); g.tick(20)
g.set('GPS3D_BuildingModels', 'game'); g.tick(10)
# the game's models (Models.lua): the five controls
def shown_models():
    out = []
    for a_ in ns2.scene._actors.values():
        if a_._shown and a_._fileID:
            r_, lo_, hi_, w_ = G.GPS3D_API.ModelInfo(a_._fileID)
            out.append((bool(w_), a_._pos[1], a_._pos[2]))
    return out
ns2.cam.dist = 300; g.tick(10)
md = shown_models()
check('Props and trees: off by default (none drawn, the buildings still)', DB3().props is None and not any(not w for w, _, _ in md) and any(w for w, _, _ in md),
      f'{sum(1 for w, _, _ in md if not w)} props, {sum(1 for w, _, _ in md if w)} buildings')
g.set('GPS3D_Props', True); g.tick(10)
m0 = shown_models()
g.set('GPS3D_Props', False); g.tick(10); m1 = shown_models()
g.set('GPS3D_Props', True); g.tick(10)
check('Props and trees: on shows the game\'s props, off none (buildings stay), saved', any(not w for w, _, _ in m0) and not any(not w for w, _, _ in m1) and DB3().props is True,
      f'{sum(1 for w, _, _ in m0 if not w)} props on, {sum(1 for w, _, _ in m1 if not w)} off')
g.set('GPS3D_ModelCount', 50); g.tick(10); m2 = shown_models()
check('Props and trees at most 50: at most 50 props, saved', 0 < sum(1 for w, _, _ in m2 if not w) <= 50 and DB3().modelCount == 50, str(sum(1 for w, _, _ in m2 if not w)))
g.set('GPS3D_ModelCount', 250)
g.set('GPS3D_BuildingModels', 'simple'); g.tick(10); m3 = shown_models()
g.set('GPS3D_BuildingModels', 'game'); g.tick(10); m4 = shown_models()
check('Buildings close up: simplified shows no building models, the game\'s shows them, saved', not any(w for w, _, _ in m3) and any(w for w, _, _ in m4) and DB3().buildingModels == 'game',
      f'{sum(1 for w, _, _ in m3 if w)} / {sum(1 for w, _, _ in m4 if w)} buildings')
g.set('GPS3D_ModelRange', 200); g.tick(10); m5 = shown_models()
far = [math.hypot(x - ns2.cam.x, y - ns2.cam.y) for w, x, y in m5 if not w]
check('Model distance 200: props only within 200 yd of the middle of the view, saved', far and max(far) <= 200.01 and DB3().modelRange == 200, f'{len(far)} props, furthest {max(far) if far else 0:.0f}')
g.set('GPS3D_ModelRange', 600)
g.set('GPS3D_ModelPx', 40); g.tick(10); m6 = shown_models(); g.set('GPS3D_ModelPx', 6); g.tick(10); m7 = shown_models()
check('Smallest model 40 px: fewer props than at 6 px, saved', 0 <= sum(1 for w, _, _ in m6 if not w) < sum(1 for w, _, _ in m7 if not w) and DB3().modelPx == 6,
      f'{sum(1 for w, _, _ in m6 if not w)} at 40 px, {sum(1 for w, _, _ in m7 if not w)} at 6 px')
ns2.cam.dist = 3000; g.tick(5)
tris0 = st.tris
g.set('GPS3D_GridBudget', 1600); g.tick(5)
tris1 = st.tris
check('Ground detail 1600: at most 1600 ground triangles (from more), saved', tris0 > 1600 and tris1 <= 1600 and DB3().grid == 1600, f'{tris0} -> {tris1}')
g.set('GPS3D_GridBudget', 3200); g.tick(5)
ns2.cam.dist = 120; g.tick(5)
g.set('GPS3D_ModelYaw', 180); g.tick(3)
yaw = actor()._yaw if actor()._yaw is not None else None
pf = ns2.player.facing
check('Turn your character 180: the model\'s yaw is facing + 180 degrees, saved', yaw is not None and abs(((yaw - pf - math.pi) + math.pi) % (2 * math.pi) - math.pi) < 1e-6 and abs(DB3().modelYaw - math.pi) < 1e-9,
      f'yaw {yaw} facing {pf}')
g.set('GPS3D_ModelYaw', 90)
g.close_all()
# the grid budget is kept for next time (it was not saved before)
def reopen_tris():
    G.GPS_Toggle(); g.tick(40); n = st.tris; g.close_all(); return n
G.GPS3D_DB.grid = None; t_default = reopen_tris()
G.GPS3D_DB.grid = 1000; t_saved = reopen_tris()
check('Ground detail saved is applied when the 3D view opens', t_default > 1000 >= t_saved, f'{t_default} at the default, {t_saved} with 1000 saved')
G.GPS3D_DB.grid = None

# ---- S2: position fixes (the same rule for 2D and 3D)
g.goldshire(); g.set('GPS_OpenAs', '2D'); G.GPS_Toggle(); g.tick(5)
p0 = list(G.GPS_API.PlayerPosition())
g.set('GPS_SwapAxes', True)
p1 = list(G.GPS_API.PlayerPosition())
check('Swap the map\'s axes: position swapped, saved', DB().swapAxes is True and abs(p1[1] - p0[2]) < 1e-9 and abs(p1[2] - p0[1]) < 1e-9, f'{p0[:3]} -> {p1[:3]}')
g.set('GPS_SwapAxes', False)
g.set('GPS_FlipFacing', True)
p2 = list(G.GPS_API.PlayerPosition())
check('Turn the arrow the other way: facing negated, saved', DB().flipFacing is True and abs(p2[3] + p0[3]) < 1e-9, f'{p0[3]} -> {p2[3]}')
g.set('GPS_FlipFacing', False)
g.close_all()

# ---- S4: /gps options
for cmd in ('options', 'settings', 'config'):
    G.SANDBOX_SLASH('/gps ' + cmd); g.tick(1)
    opened = G.SANDBOX_SETTINGS_TAKEOPEN()
    check(f'/gps {cmd} opens the page', opened == ns1.settingsCategory.GetID(ns1.settingsCategory), str(opened))
check('/gps options leaves no window open', not any(g.shown(f) for f in g.frames()))
check('no Lua errors (full addons)', not errors, str(errors[:3]))

# ---- S6: GPS alone, and without the Settings API
errors.clear()
g2 = Game(with3d=False)
c2 = g2.page()[0]['controls']
check('without GPS3D: no 3D section, no 3D choice', '3D view' not in [c['name'] for c in c2] and [o['value'] for o in g2.control('GPS_OpenAs')['options']] == ['2D', 'Map'],
      str([c['name'] for c in c2]))
g2.G.GnomishPositioningSystemDB.mode = '3D'
check('without GPS3D: a saved "3D" shows as 2D', g2.control('GPS_OpenAs')['value'] == '2D')
check('no Lua errors (GPS alone)', not errors, str(errors[:3]))
g3 = Game(settings_api=False)
check('without the Settings API: no page, addons load', g3.ns1.settingsCategory is None and g3.G.GPS_MapFrame is not None)
g3.G.SANDBOX_SLASH('/gps options'); out = g3.chat()
check('without the Settings API: /gps options says so', 'not available' in out, out)
G3 = g3.G; G3.GPS_Toggle(); g3.tick(5)
check('no Lua errors (no Settings API)', not errors, str(errors[:3]))

print(f'\n{sum(ok for _, ok in results)}/{len(results)} passed')
raise SystemExit(0 if all(ok for _, ok in results) else 1)
