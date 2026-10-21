# Checks GPS's debug log (/gps debug, Debug.lua) on the sandbox engine (Lua 5.4): off by default and
# then silent; on: the session header, what the windows, maps, quests, settings and slash commands do,
# position samples, frame times, memory, taint events and Lua errors from GPS's files (not other
# addons'), with the game's own error display still working; the size cap (a log left on stays under
# about 1 MB); off again; kept over a /reload (saved variables) with a reminder; the copy window;
# clear; and the switch on the settings page.
# Usage: python test_debug.py   (fill site/addons first, as for test_world.py)
import lupa.lua54 as lupa54, os, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
TOCS = [('GnomishPositioningSystem', os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc')),
        ('GPS3D', os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc'))]
W, H = 1280, 800
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

class Game:
    def __init__(self, saved=''):
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        if saved: G.SANDBOX_RESTORE(saved)
        for addon, toc in TOCS:
            text = open(toc).read()
            for key in ('Version', 'Title'):
                m = re.search(rf'^## {key}: (.*)$', text, re.M)
                if m: G.SANDBOX_ADDONMETA(addon, key, m.group(1).strip())
            for f in [l.strip().replace('\\', '/') for l in text.splitlines() if l.strip() and not l.startswith('##')]:
                if not G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read()): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False); self.tick(2)
        self.ns = G.SANDBOX.namespaces['GnomishPositioningSystem']
        self.chatlog = self.chat()
    def tick(self, n=1, dt=1 / 30):
        for _ in range(n): self.G.SANDBOX_TICK(dt, W, H)
    def chat(self): return str(self.G.SANDBOX_CHAT() or '')
    def lines(self):
        t = self.G.GnomishPositioningSystemLog.lines
        return [str(t[i]) for i in range(1, len(t) + 1)]
    def slash(self, s): self.G.SANDBOX_SLASH(s); self.tick(2); return self.chat()
    def since(self, n): return self.lines()[n:]
    def has(self, lines, cat, text): return any(re.search(r'\s' + cat + r'\s', l) and text in l for l in lines)

g = Game()
G, ns = g.G, g.ns
# ---- off by default: silent
g.slash('/gps 2d'); g.tick(60)
g.slash('/gps 3d'); g.tick(30)
check('off by default: nothing logged while the windows are used', not ns.debugOn and len(g.lines()) == 0 and not G.GPS_API.DebugOn(), f'{len(g.lines())} lines')
before_handler = G.geterrorhandler()

# ---- on: the header
out = g.slash('/gps debug on')
L0 = g.lines()
check('/gps debug on: on, saved as on, says where the file is', ns.debugOn and G.GnomishPositioningSystemLog.on and 'SavedVariables\\GnomishPositioningSystem.lua' in out, out[:120])
check('header: game build, both versions, screen and scale, data and APIs, both settings, your position',
      g.has(L0, 'SESSION', 'game 1.60.1') and g.has(L0, 'SESSION', 'GPS 0.4.0; GPS3D 0.5.0') and g.has(L0, 'SESSION', 'screen 1280x800')
      and g.has(L0, 'SESSION', 'data: 48 maps') and g.has(L0, 'SESSION', 'settings GPS {') and g.has(L0, 'SESSION', 'settings GPS3D {')
      and g.has(L0, 'SESSION', 'UnitPosition -8958.3'), '\n'.join(L0))
same = g.L.eval('function(a, b) return rawequal(a, b) end')
check('the game\'s error handler is hooked (and was not while off)', not same(G.geterrorhandler(), before_handler))

# ---- what GPS does
n = len(g.lines())
g.slash('/gps 2d'); g.tick(40)
ns.ui.modeSwitch._scripts.OnClick(ns.ui.modeSwitch, 'LeftButton'); g.tick(40)
u2 = G.SANDBOX.namespaces['GPS3D'].ui
u2.modeSwitch._scripts.OnClick(u2.modeSwitch, 'LeftButton'); g.tick(40)
new = g.since(n)
check('windows: slash command, mode ring 2D -> 3D -> Map, which window is shown', g.has(new, 'SLASH', '/gps 2d') and g.has(new, 'MODE', 'mode ring: 2D -> 3D')
      and g.has(new, 'MODE', 'opened 3D') and g.has(new, 'MODE', 'mode ring: 3D -> Map') and g.has(new, 'WINDOW', 'shown: Map'), '\n'.join(new[:12]))
check('the view of each window: 2D centre and scale, 3D camera and you, traditional map',
      g.has(new, 'VIEW', '2D map 0 centre') and g.has(new, 'VIEW', '3D map 0 looking at') and g.has(new, 'VIEW', 'traditional map 1429'))
check('traditional map: the canvas made with all 27 data providers', g.has(new, 'MAPWIN', 'map canvas made: 27 of 27 data providers'))
check('header: the quests shown and the zones known per map', g.has(L0, 'SESSION', 'quests: shown true; 7 in the list; zones known: map 0: '), '')
n = len(g.lines())
G.SANDBOX_SETTING_SET('GPS3D_Marker', 'arrow'); g.tick(2)
reset_at = 1 + [c['name'] for c in json.loads(str(G.SANDBOX_SETTINGS()))[0]['controls']].index('Window')  # (the Reset button's place on the page)
G.SANDBOX_SETTING_CLICK('Gnomish Positioning System', reset_at); g.tick(2)
check('settings: a change and a button', g.has(g.since(n), 'SETTING', 'GPS3D_Marker = arrow') and g.has(g.since(n), 'SETTING', 'Window: Reset clicked'), '\n'.join(g.since(n)))
g.slash('/gps 2d'); g.tick(5)
pin = [p for p in [ns.quests.pins2D[i] for i in range(1, len(ns.quests.pins2D) + 1)] if p.IsShown(p) and p.gpsQuestID == 7][0]
n = len(g.lines())
pin._scripts.OnClick(pin, 'LeftButton'); g.tick(15)
check('quests: a marker click, then the rebuilt list (7 quests, the new tracked one marked)', g.has(g.since(n), 'QUEST', 'marker 7 clicked') and g.has(g.since(n), 'QUEST', '7 quests with a point') and g.has(g.since(n), 'QUEST', '7*@1429'))
n = len(g.lines())
g.slash('/gps test'); g.tick(100); g.chat()
check('/gps test: its lines are in the log too (quests among them)', g.has(g.since(n), 'TEST', 'data: 48 maps') and g.has(g.since(n), 'TEST', 'quests: 2. quest-area frame'))

# ---- position, frame times, memory
n = len(g.lines())
G.SANDBOX_PLAYER(-9464, 62, 0, 0, 1.0, '', '', 1429, 0.4, 0.6); g.tick(40)
moved = [l for l in g.since(n) if ' POS ' in l]
n = len(g.lines())
g.tick(30 * 8)  # 8 s standing still
still8 = [l for l in g.since(n) if ' POS ' in l]
g.tick(30 * 3)
still11 = [l for l in g.since(n) if ' POS ' in l]
check('position: a line when you move (zone from your position), none while you stand still, one every 10 s anyway',
      moved and 'Goldshire' in moved[-1] and 'tile 31_49' in moved[-1] and not still8 and len(still11) == 1, f'{moved[-1:]} / {len(still8)} / {len(still11)}')
n = len(g.lines())
for _ in range(31):  # 31 s, the 2D map panned a little each second
    ns.view.follow = False; ns.view.cx += 0.01; ns.Layout(); g.tick(30)
per = g.since(n)
check('frame times every 5 s (2D layouts, game fps) and memory every 30 s', g.has(per, 'PERF', '2D:') and g.has(per, 'PERF', 'game ') and g.has(per, 'MEMORY', 'Lua '), '\n'.join(l for l in per if 'PERF' in l or 'MEMORY' in l)[:400])
g.slash('/gps 3d'); g.tick(30 * 11)
check('3D frame times', g.has(g.lines()[-60:], 'PERF', '3D:') or any('PERF' in l and '3D:' in l for l in g.lines()), '')

# ---- errors and taint
n = len(g.lines())
g.slash('/gps 2d'); g.tick(3)
orig = ns.LayoutQuests
g.L.execute('SANDBOX.namespaces.GnomishPositioningSystem.LayoutQuests = function() error("debug-log test error") end')
G.SANDBOX.call(ns.Layout); g.tick(1)
ns.LayoutQuests = orig
shown = g.chat()
errs = [l for l in g.since(n) if ' ERROR ' in l]
check('a Lua error in GPS: its message and stack in the log, and the game still shows it', errs and 'debug-log test error' in errs[0] and any('Core.lua' in l for l in errs) and 'Lua error' in shown, '\n'.join(errs[:4]))
n = len(g.lines())
g.L.execute('SANDBOX.call(load("error(\'another addon broke\')", "=OtherAddon/Main.lua"))'); g.tick(1); g.chat()
check('another addon\'s error is not logged', not [l for l in g.since(n) if ' ERROR ' in l])
G.SANDBOX_FIRE('ADDON_ACTION_BLOCKED', 'GnomishPositioningSystem', 'UseAction()'); g.tick(1)
check('blocked actions (taint) are logged', g.has(g.since(n), 'TAINT', 'ADDON_ACTION_BLOCKED GnomishPositioningSystem, UseAction()'))

# ---- size: a log left on stays under the cap
MAX, KEEP, LINE = ns.DEBUG_MAX_BYTES, ns.DEBUG_KEEP_BYTES, ns.DEBUG_MAX_LINE
for i in range(9000):
    ns.Log('MARK', '%s', f'filler {i} ' + 'x' * 200)
ns.Log('MARK', '%s', 'y' * 3000)
ls = g.lines()
size = sum(len(l) + 1 for l in ls)
check(f'size cap: 9,000 long lines in, the log stays under {MAX // 1000} KB, the newest kept, a note where older lines went',
      size <= MAX and size == G.GnomishPositioningSystemLog.bytes and 'filler 8999' in ls[-2] and 'older lines dropped' in ls[0], f'{len(ls)} lines, {size} bytes')
check(f'one line is cut at {LINE} characters', len(ls[-1]) == LINE and ls[-1].endswith('...'), str(len(ls[-1])))
saved = str(G.SANDBOX_SAVE('GnomishPositioningSystemDB,GnomishPositioningSystemLog'))
check('the saved file stays near the cap too (as the game writes it)', len(saved) < MAX * 1.1, f'{len(saved)} bytes')

# ---- copy window, clear, off
g.slash('/gps debug show')
f = G.GPS_DebugFrame
check('/gps debug show: the window with the newest lines, selected for copying', f.IsShown(f) and str(f.box.GetText(f.box)).endswith(g.lines()[-1]) and f.box.HasFocus(f.box)
      and str(f.box.GetText(f.box)).count('\n') == 1499, str(f.title.GetText(f.title)))
G.SANDBOX_KEY('ESCAPE'); g.tick(1)
check('Escape closes it', not f.IsShown(f))
g.slash('/gps debug clear')
check('/gps debug clear: one line left (that it was cleared)', len(g.lines()) == 1 and 'cleared' in g.lines()[0] and G.GnomishPositioningSystemLog.bytes == len(g.lines()[0]) + 1)
g.slash('/gps debug off')
n = len(g.lines())
g.slash('/gps 3d'); g.tick(60)
check('/gps debug off: nothing more logged, saved as off, the error handler given back', len(g.lines()) == n and not G.GnomishPositioningSystemLog.on and same(G.geterrorhandler(), before_handler), f'{len(g.lines()) - n} new lines')

# ---- kept over a /reload, with a reminder
g.slash('/gps debug on'); g.slash('/gps debug mark before the reload')
saved = str(G.SANDBOX_SAVE('GnomishPositioningSystemDB,GnomishPositioningSystemLog'))
g2 = Game(saved)
L2 = g2.lines()
check('after /reload: still on, the earlier lines kept, a new header, a reminder in chat',
      g2.ns.debugOn and any('before the reload' in l for l in L2) and any('login or /reload' in l for l in L2) and 'debug log is on' in g2.chatlog, g2.chatlog[:200])
check('size counted again from the saved lines', g2.G.GnomishPositioningSystemLog.bytes == sum(len(l) + 1 for l in L2))

# ---- the settings page switch
n = len(g2.lines())
g2.G.SANDBOX_SETTING_SET('GPS_DebugLog', 'false'); g2.tick(2)
off = not g2.ns.debugOn
g2.G.SANDBOX_SETTING_SET('GPS_DebugLog', 'true'); g2.tick(2)
check('settings page: "Keep a debug log" turns it off and on', off and g2.ns.debugOn)
errors = [l for l in (g.chat() + g2.chat()).split('\n') if 'not simulated' in l]
check('no unsimulated calls', not errors, str(errors[:3]))
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
raise SystemExit(0 if n == len(results) else 1)
