"""/gps3d probe (GPS3D's Probe.lua): the in-game checks of the 2026-10-22 performance review, run in the sandbox.

Runs the probe at Stormwind's Trade District (330 yd, straight down) four times: on the bare engine, where
RotateTextures, SetPointsOffset and the OffScreenFrame's methods are missing; with working stand-ins of them
(defined here, not in the engine); with stand-ins that raise errors; and stopped part way (combat, the stop
command, the window closing). Checks: it runs and prints all five parts, its count of the C calls a frame makes
against the engine's exact count, the settings, camera and anchors put back, nothing of it left shown, the view
drawn afterwards the same as before, missing and failing APIs reported without stopping the other parts, the
glide of part 4 lining up with the real redraw, and that it refuses to start in combat.

Run: python3 test_probe.py   (about 2 minutes; PROBE_ADDON=<dir> loads GPS3D's files from another folder, e.g.
the code before the probe, to show the checks fail there)
"""
import lupa.lua54 as lupa54, os, sys, time, re
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
GPS3D_DIR = os.environ.get('PROBE_ADDON', os.path.join(SITE, 'addons', 'GPS3D'))
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
# the engine's exact count of the calls the probe counts (as perf_focus.py does)
L.execute('''
CALLS = {}
local names = { "SetVertexOffset", "SetDrawLayer", "SetParent", "Show", "Hide", "SetTexCoord" }
local Texture = getmetatable(UIParent:CreateTexture())
for _, n in ipairs(names) do
  local f = Texture[n]
  Texture[n] = function(...) CALLS[n] = (CALLS[n] or 0) + 1 return f(...) end
end
function CALLS_RESET() for k in pairs(CALLS) do CALLS[k] = 0 end end
function CALLS_TOTAL() local s = 0 for _, v in pairs(CALLS) do s = s + v end return s end
''')
L.execute(open(f'{SITE}/zones.lua').read())
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
for addon, folder in [('GnomishPositioningSystem', os.path.join(SITE, 'addons', 'GnomishPositioningSystem')), ('GPS3D', GPS3D_DIR)]:
    for f in toc_files(os.path.join(folder, addon + '.toc')):
        src = os.path.join(folder, f) if os.path.exists(os.path.join(folder, f)) else os.path.join(SITE, 'addons', addon, f)
        if not G.SANDBOX_LOAD(addon, f, open(src).read()): print('LOAD FAILED', addon, f)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')

# Stand-ins of what the engine lacks, switched on and off by the test: 'work' (they do what the game's
# documentation says: a frame's points offset, the textures turned, snapshots taken), 'error' (each raises, as a
# protected or refused call would; CreateFrame refuses the OffScreenFrame type), nil (missing, as in the engine).
L.execute('''
PROBE_LOG = { spo = 0, clear = 0, rot = {}, snaps = 0, shownAtSnap = {} }
local Frame = getmetatable(CreateFrame("Frame")).__index
local plainCreate = CreateFrame
local mode
function PROBE_STANDINS(m)
  mode = m
  if not m then
    Frame.SetPointsOffset, Frame.ClearPointsOffset, Frame.RotateTextures = nil, nil, nil
    CreateFrame = plainCreate
    return
  end
  if m == "error" then
    Frame.SetPointsOffset = function() error("SetPointsOffset: protected (stand-in)") end
    Frame.ClearPointsOffset = function() error("ClearPointsOffset: protected (stand-in)") end
    Frame.RotateTextures = function() error("RotateTextures: refused (stand-in)") end
    CreateFrame = function(kind, ...)
      if kind == "OffScreenFrame" then error("CreateFrame: Unknown frame type 'OffScreenFrame' (stand-in)") end
      return plainCreate(kind, ...)
    end
    return
  end
  Frame.SetPointsOffset = function(self, x, y)
    PROBE_LOG.spo = PROBE_LOG.spo + 1
    local base = self._pbase
    if not base then
      base = {}
      for _, p in ipairs(self._points) do base[#base + 1] = { p[1], p[2], p[3], p[4], p[5] } end
      self._pbase = base
    end
    self._pofs = { x, y }
    for _, p in ipairs(base) do self:SetPoint(p[1], p[2], p[3], p[4] + x, p[5] + y) end
  end
  Frame.ClearPointsOffset = function(self)
    PROBE_LOG.clear = PROBE_LOG.clear + 1
    local base = self._pbase
    if base then for _, p in ipairs(base) do self:SetPoint(p[1], p[2], p[3], p[4], p[5]) end end
    self._pbase, self._pofs = nil, nil
  end
  Frame.RotateTextures = function(self, r) PROBE_LOG.rot[#PROBE_LOG.rot + 1] = r end
  CreateFrame = function(kind, ...)
    if kind ~= "OffScreenFrame" then return plainCreate(kind, ...) end
    local f = plainCreate("Frame", ...)
    f.TakeSnapshot = function(self)
      PROBE_LOG.snaps = PROBE_LOG.snaps + 1
      PROBE_LOG.shownAtSnap[#PROBE_LOG.shownAtSnap + 1] = self:IsShown()
      return 7
    end
    f.ApplySnapshot = function(self, tex, id) return id == 7 end
    f.IsSnapshotValid = function(self, id) return id == 7 end
    f.GetMaxSnapshots = function() return 4 end
    f.SetMaxSnapshots = function() end
    f.Flush = function() end
    f.UsesNPOT = function() return true end
    return f
  end
end
-- how many textures drawn are anchored elsewhere than the 3D canvas
function PROBE_OFF_CANVAS()
  local ns = SANDBOX.namespaces.GPS3D
  local vis, bad = ns.stats.visible, 0
  for i = 1, ns.stats.shown do local _, rel = vis[i].tex:GetPoint(1); if rel ~= ns.canvas then bad = bad + 1 end end
  return bad
end
''')

TILE = 1600 / 3
W, H = 1280, 800
DT = 1 / 30
def tick(n=1):
    for _ in range(n): G.SANDBOX_TICK(DT, W, H)
CHAT = []
def chat():
    c = G.SANDBOX_CHAT()
    if c: CHAT.extend(c.split('\n'))
    return c or ''
def place(X, Y, m, facing=0.0, zone=''):
    G.SANDBOX_PLAYER(X, Y, 0, m, facing, zone, '', -1, -1, -1)
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)

ns2 = G.SANDBOX.namespaces['GPS3D']
place(-8830, 640, 0, 1.0, 'Stormwind City')
G.SlashCmdList.GPS('debug on')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
G.GPS3D_DB.buildingModels = 'simple'; ns2.ModelsChanged()
tick(40); chat()
st, cam = ns2.stats, ns2.cam
P = ns2.probe
if P is None:
    check('/gps3d probe exists (GPS3D has a probe)', False, 'ns.probe is missing: the code before the probe')
    G.SlashCmdList.GPS3D('probe'); tick(5); out = chat()
    check('/gps3d probe starts and prints its first part', '1/5' in out, repr(out[:120]))
    print(f'\n{sum(ok for _, ok in results)} of {len(results)} checks passed')
    sys.exit(1)

def state():
    g, b, d = ns2.Budgets()
    db = G.GPS3D_DB
    return (g, b, d, db.grid, db.buildings, db.detail, round(cam.yaw, 9), round(cam.x, 6), round(cam.y, 6), ns2.CamMode())

def view_sig():
    """The triangles drawn on the canvas (any part of them inside it: the canvas clips the rest): their
    corners as sent to the game and their depth bucket."""
    w, h = ns2.canvas.GetSize(ns2.canvas)
    out = []
    vis = st.visible
    for i in range(1, int(st.shown) + 1):
        t = vis[i]
        c = tuple(float(v or 0) for v in (t.x1, t.y1, t.x2, t.y2, t.x3, t.y3))
        if max(c[0], c[2], c[4]) < -w / 2 or min(c[0], c[2], c[4]) > w / 2 or max(c[1], c[3], c[5]) < -h / 2 or min(c[1], c[3], c[5]) > h / 2:
            continue
        out.append(c + (int(t.bucket),))
    return out

def same_view(before, after, tol=0.26):
    """Triangles of `after` matched one to one with those of `before`: the same depth bucket and every corner
    within tol px (a vertex that moved less than VO_EPS, 0.25 px, keeps the place it was last sent to, so a view
    redrawn from elsewhere may differ from one that settled in place by up to that)."""
    cells = {}
    for i, b in enumerate(before):
        cells.setdefault((b[6], int(b[0] // 2), int(b[1] // 2)), []).append(i)
    used, matched, worst = set(), 0, 0.0
    for a in after:
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in cells.get((a[6], int(a[0] // 2) + dx, int(a[1] // 2) + dy), ()):
                    if i in used: continue
                    d = max(abs(a[k] - before[i][k]) for k in range(6))
                    if d <= tol and (best is None or d < best[0]): best = (d, i)
        if best:
            used.add(best[1]); matched += 1; worst = max(worst, best[0])
    return matched, worst

def settle():
    # until redraws change nothing and the ground's level-of-detail controller is at rest (it eases over a few
    # dozen frames)
    calm, k0 = 0, None
    for _ in range(400):
        P.Snapshot(); ns2.Render(); c = P.Diff()
        calm = calm + 1 if (c.total == 0 and st.detailPending == 0 and ns2.Lod.kappa == k0) else 0
        k0 = ns2.Lod.kappa
        if calm >= 5: return True
        tick(1)
    return False

def made_hidden():
    return all(not f.IsShown(f) for f in P.made.values())

def anchors_on_canvas():
    return int(G.PROBE_OFF_CANVAS())

def run(limit_s=200):
    n = 0
    while P.running and n < limit_s / DT:
        tick(1); n += 1
    chat()
    return n * DT

settle()

# ---- run 1: the bare engine (RotateTextures, SetPointsOffset, the OffScreenFrame's methods missing) ---------
check('the probe is idle until asked: its driver frame is hidden (no OnUpdate, the normal frame unchanged)', not P.driver.IsShown(P.driver))
before_state = state(); before_view = view_sig()
def lod_state():
    return (ns2.Lod.kappa, ns2.Lod.target, sorted((int(k), int(v)) for k, v in ns2.BlockLevels().items()))
before_lod = lod_state()
log0 = len(G.GnomishPositioningSystemLog.lines)
CHAT.clear()
G.SANDBOX_SLASH('/gps3d probe'); tick(1); chat()
check('/gps3d probe starts, says how long it runs and not to touch the mouse', P.running and any('starting: about' in l and 'not touch the mouse' in l for l in CHAT), CHAT[0][:140] if CHAT else '')
planned = float(P.Planned())
secs = run()
text = '\n'.join(CHAT)
check('it runs to the end in about the time it said (a minute)', not P.running and 'done in' in text and 40 <= secs <= planned + 15, f'{secs:.0f} s simulated, planned {planned:.0f} s')
check('it prints all five parts', all(f'{k}/5' in text for k in range(1, 6)), ' '.join(f'{k}/5:{text.count(f"{k}/5")}' for k in range(1, 6)))
rows = [l for l in CHAT if re.search(r'ground \d+, buildings \d+:', l)]
nums = []
for l in rows:
    m = re.search(r'ground (\d+), buildings (\d+): (\d+) textures \| still ([\d.]+) ms .*redraw ([\d.]+) ms, Lua ([\d.]+), (\d+) calls \| turn ([\d.]+) ms, Lua ([\d.]+), (\d+) calls \((\d+) SetVertexOffset\)', l)
    if m: nums.append([float(v) for v in m.groups()])
check('part 1: six settings, each with textures, frame times, Lua ms and calls', len(nums) == 6 and all(r[2] > 0 and r[3] > 0 and r[8] > 0 for r in nums), '\n   ' + '\n   '.join(l.split('|r ')[-1] for l in rows))
check('part 1: turning sends calls, redrawing an unmoved view almost none', all(r[9] > 1000 and r[6] <= 50 for r in nums), str([(int(r[0]), int(r[1]), int(r[6]), int(r[9])) for r in nums]))
# (more budget never fewer textures; at Orgrimmar from 330 yd the ground fits in 3,200 triangles, so 6,400 adds none)
check('part 1: more ground or building budget, more textures (never fewer; at least 4 different counts)', nums[0][2] < nums[1][2] <= nums[2][2] and nums[1][2] < nums[3][2] < nums[4][2] <= nums[5][2] and len(set(int(r[2]) for r in nums)) >= 4 if len(nums) == 6 else False, str([int(r[2]) for r in nums]))
# (since 2026-10-22 it moves the view itself: Morten plays Horde and wants to run it without moving; default Orgrimmar)
view_line = next((l for l in CHAT if '1/5 view:' in l), '')
check('with no place given it measures at Orgrimmar (the view moved there, map 1, straight down at 330 yd), not where you are', any('moved to Orgrimmar, Valley of Strength' in l for l in CHAT) and 'map 1, tile 40.21, 28.94, 330 yd, tilt 89.9' in view_line, view_line.split('|r ')[-1][:140])
check('part 1: an estimate line per texture and per call', any('1/5 estimate from 6 settings' in l for l in CHAT))
check('missing APIs say "missing" and the other parts go on', '3/5 RotateTextures: missing' in text and '4/5 SetPointsOffset: missing' in text and '5/5 OffScreenFrame: made; methods there: none' in text and '2/5 fold: shown' in text)
check('settings, camera mode and view put back exactly', state() == before_state, f'{state()} vs {before_state}')
check('the ground\'s level-of-detail controller and the building blocks\' levels put back (they keep some of their past: without this the view comes back with other levels)',
      lod_state() == before_lod, f'kappa {ns2.Lod.kappa} vs {before_lod[0]}, {len(before_lod[2])} blocks')
check('nothing the probe made is left shown; the 3D window still open', made_hidden() and ns2.frame.IsShown(ns2.frame))
settle()
after_view = view_sig()
matched, worst = same_view(before_view, after_view)
check('the view drawn afterwards is the one drawn before (every triangle on the canvas in the same depth bucket, every corner within VO_EPS)',
      len(after_view) == len(before_view) == matched, f'{matched} of {len(before_view)} matched ({len(after_view)} now), worst corner {worst:.3f} px')
lines = list(G.GPS3D_DB.probe.lines.values()) if G.GPS3D_DB.probe else []
logged = [l for l in list(G.GnomishPositioningSystemLog.lines.values())[log0:] if ' PROBE ' in l]
check('results kept in GPS3D_DB.probe and in the debug log (category PROBE)', len(lines) >= 12 and len(logged) >= 12, f'{len(lines)} saved lines, {len(logged)} log lines')

# ---- the call count against the engine's exact count ------------------------------------------------------
settle()
for name, step in [('turning 3 degrees a frame', lambda: setattr(cam, 'yaw', cam.yaw + 3)),
                   ('turning 0.33 degrees a frame (the probe\'s 20 a second at 60 fps)', lambda: setattr(cam, 'yaw', cam.yaw + 0.33)),
                   ('redrawn, nothing moved', lambda: None),
                   ('moved 0.25 yd east', lambda: setattr(cam, 'x', cam.x + 0.25))]:
    worst = 0; est_sum = 0; ex_sum = 0
    for _ in range(5):
        step(); P.Snapshot(); G.CALLS_RESET(); ns2.Render(); c = P.Diff()
        exact = int(G.CALLS_TOTAL()); est = int(c.total)
        est_sum += est; ex_sum += exact
        worst = max(worst, abs(est - exact) - (0.03 * exact + 20))
    check(f'the probe counts the C calls of a frame within 3 % (+20) of the engine\'s exact count: {name}', worst <= 0,
          f'counted {est_sum // 5}, exact {ex_sum // 5} a frame (SetVertexOffset {int(G.CALLS.SetVertexOffset or 0)})')
place(-8830, 640, 0, 1.0, 'Stormwind City'); ns2.FollowMe('follow'); tick(150)  # (Me flies back: wait for the flight to end)
settle()


# ---- run 2: working stand-ins ----------------------------------------------------------------------------
G.PROBE_STANDINS('work'); P.off = None
P.SETTINGS = L.eval('{ { 3200, 4000 } }')  # (part 1 once, to keep the run short)
CHAT.clear(); before_state = state()
G.SANDBOX_SLASH('/gps3d probe stormwind'); tick(1)
# watch part 4: anchors to the depth frames, the glide's shift on every frame, the cross on the shifted ground
seen = {'anchored': 0, 'glide': 0, 'ok': 0, 'worst': 0.0, 'cross': 0.0}
track = None
while P.running:
    tick(1)
    p4 = P.p4
    if p4.glide and not seen['anchored']:
        seen['anchored'] = len(P.anchored)
        # the visible vertex nearest the middle of the view (the cross), its screen place before the glide
        best = None
        vis = st.visible
        for i in range(1, int(st.shown) + 1):
            t = vis[i]
            if t.x1 is None: continue
            if t.mesh is not None and t.mesh.hk: continue  # (the ground's: a city shell may change level at the moved camera, its old faces hidden)
            d = (t.x1 - p4.sx0) ** 2 + (t.y1 - p4.sy0) ** 2
            if best is None or d < best[0]: best = (d, t, t.x1, t.y1)
        track = best
    if p4.glide and P.running and len(P.anchored) and P.cross.IsShown(P.cross):
        bf = ns2.bucketFrames
        offs = [bf[k]._pofs for k in range(1, 9)]
        if all(o is not None for o in offs):
            seen['glide'] += 1
            ox, oy = offs[0][1], offs[0][2]
            same_shift = all(abs(o[1] - ox) < 1e-9 and abs(o[2] - oy) < 1e-9 for o in offs)
            # a ground texture's anchor point moved with its frame (the engine's layout)
            t = track[1]
            l, b, r, tp = G.SANDBOX.rect(t.tex)
            l0, b0, r0, t0 = G.SANDBOX.rect(ns2.canvas)
            cx_moved = (l + r) / 2 - (l0 + r0) / 2
            if same_shift and abs(cx_moved - ox) < 1e-6: seen['ok'] += 1
            seen['last'] = (track[2] + ox, track[3] + oy)
    if P.p4.glide is not None and seen.get('last') and not P.cross.IsShown(P.cross) and 'after' not in seen:
        # the end of the glide: the ground drawn for real at the moved camera; the tracked vertex where the shift put it
        t = track[1]
        if t.x1 is not None:
            seen['after'] = (t.x1, t.y1)
chat(); text = '\n'.join(CHAT)
check('with SetPointsOffset there: the ground\'s textures anchored to their depth frames, every frame shifted alike as the camera glides, the textures moving with them',
      seen['anchored'] > 1000 and seen['glide'] >= 30 and seen['ok'] == seen['glide'], f"{seen['anchored']} anchored, {seen['glide']} glide frames, {seen['ok']} lined up, {G.PROBE_LOG.spo} SetPointsOffset calls")
if seen.get('after') and seen.get('last'):
    dx, dy = seen['after'][0] - seen['last'][0], seen['after'][1] - seen['last'][1]
    jump = (dx * dx + dy * dy) ** 0.5
else:
    jump = 99
check('the glide\'s last shifted frame and the real redraw after it agree near the cross (nothing jumps)', jump <= 0.6, f'{jump:.2f} px at the vertex nearest the cross')
check('part 4 reports frame times with and without the shift, no error', '4/5 SetPointsOffset: no error' in text, next((l.split('|r ')[-1][:200] for l in CHAT if '4/5 SetPointsOffset' in l), ''))
mv_line = next((l.split('|r ')[-1] for l in CHAT if '4/5 one-call move' in l), '')
check('part 4 one-call move (2026-10-24): corners, SetPoint and AdjustPointsOffset timed per 1,000 calls, a 0.3 px SetPoint kept (not snapped)', 'per 1,000 calls: SetVertexOffset' in mv_line and 'SetPoint 0.' in mv_line and 'moved GetCenter by 0.30' in mv_line and int(mv_line.split(':')[1].split()[0]) > 0, mv_line[:220])
check('part 3: RotateTextures(0.5) called on the turned frame', list(G.PROBE_LOG.rot.values()) == [0.5] and '3/5 RotateTextures: called' in text)
check('part 5: the OffScreenFrame\'s methods listed, a snapshot taken and applied, the frame shown only for that call',
      '5/5 OffScreenFrame: made; methods there: TakeSnapshot ApplySnapshot IsSnapshotValid GetMaxSnapshots SetMaxSnapshots Flush UsesNPOT; missing: none; TakeSnapshot hidden -> 7, shown -> 7; ApplySnapshot -> true' in text
      and list(G.PROBE_LOG.shownAtSnap.values()) == [False, True] and not P.off.IsShown(P.off))
bf = ns2.bucketFrames
check('afterwards: every depth frame\'s offset cleared, every texture anchored to the canvas again, nothing left shown',
      all(bf[k]._pofs is None for k in range(1, 9)) and anchors_on_canvas() == 0 and len(P.anchored) == 0 and made_hidden(), f'{anchors_on_canvas()} anchored elsewhere')
check('settings and camera put back (run 2)', state() == before_state, f'{state()} vs {before_state}')
view_line = next((l for l in CHAT if '1/5 view:' in l), '')
check('/gps3d probe stormwind measures at the Trade District (map 0, tile 30.80, 48.56)', 'map 0, tile 30.80, 48.56, 330 yd' in view_line and any('moved to Stormwind, Trade District' in l for l in CHAT), view_line.split('|r ')[-1][:140])

# ---- run 3: every new API raises ---------------------------------------------------------------------------
G.PROBE_STANDINS('error'); P.off = None
CHAT.clear(); before_state = state()
here_view = (round(cam.x / ns2.TILE, 2), round(-cam.y / ns2.TILE, 2))
G.SANDBOX_SLASH('/gps3d probe here'); run(); text = '\n'.join(CHAT)
view_line = next((l for l in CHAT if '1/5 view:' in l), '')
check('/gps3d probe here measures the view as it is (no move)', not any('moved to' in l for l in CHAT) and f'tile {here_view[0]:.2f}, {here_view[1]:.2f}' in view_line, view_line.split('|r ')[-1][:140])
check('APIs that raise: each part says "error" and the probe still runs to the end',
      'RotateTextures: error' in text and '4/5 SetPointsOffset: error' in text and '5/5 OffScreenFrame: missing (CreateFrame' in text and 'done in' in text,
      ' | '.join(l.split('|r ')[-1][:90] for l in CHAT if re.search(r'[345]/5', l)))
check('settings, camera and anchors put back after the errors', state() == before_state and anchors_on_canvas() == 0 and made_hidden())

# ---- stopping part way --------------------------------------------------------------------------------------
G.PROBE_STANDINS('work'); P.off = None
P.SETTINGS = L.eval('{ { 800, 0 }, { 6400, 8000 } }')
for how in ['combat', 'stop', 'close']:
    CHAT.clear(); before_state = state()
    G.SANDBOX_SLASH('/gps3d probe')
    if how == 'combat':
        tick(90)  # (in part 1, the second setting)
        G.SANDBOX_COMBAT(True); tick(1); G.SANDBOX_COMBAT(False)
    elif how == 'stop':
        while P.running and not (P.p4.glide and len(P.anchored)): tick(1)
        G.SANDBOX_SLASH('/gps3d probe stop')
    else:
        tick(90); ns2.frame.Hide(ns2.frame)
    tick(2); chat(); text = '\n'.join(CHAT)
    if how == 'close':
        G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame); tick(5)
    reason = {'combat': 'stopped: combat started', 'stop': 'stopped: /gps3d probe stop', 'close': 'stopped: the 3D window closed'}[how]
    check(f'stopped part way ({how}): it says so, puts the settings, camera and anchors back, leaves nothing shown',
          not P.running and reason in text and state()[:6] == before_state[:6] and (how == 'close' or state() == before_state)
          and anchors_on_canvas() == 0 and all(bf[k]._pofs is None for k in range(1, 9)) and made_hidden() and not P.driver.IsShown(P.driver),
          f'{state()} vs {before_state}')
G.PROBE_STANDINS(None)

# ---- not in combat ------------------------------------------------------------------------------------------
G.SANDBOX_COMBAT(True); CHAT.clear(); before_state = state()
G.SANDBOX_SLASH('/gps3d probe'); tick(3); chat()
check('in combat it refuses and says so; nothing changes', not P.running and any('not in combat' in l for l in CHAT) and state() == before_state, CHAT[-1][:120] if CHAT else '')
G.SANDBOX_COMBAT(False)

print(f'\n{sum(ok for _, ok in results)} of {len(results)} checks passed')
sys.exit(0 if all(ok for _, ok in results) else 1)
