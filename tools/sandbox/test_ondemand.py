"""GPS3D's building and model data loaded on demand (OnDemand.lua; perf round A5, 2026-10-22).

The buildings (Detail_*) and the game's model placements (Models_*) are load-on-demand addons next to GPS3D
(GPS3D_EK1..4, GPS3D_Kalimdor1..3, GPS3D_Instances, GPS3D_Models), loaded through C_AddOns.LoadAddOn when the 3D
view comes within a tile of them (the sandbox engine reads their TOC and files from site/addons). Checks:
nothing of them at login; only the bands near the view when it opens; each band loaded while still out of
reach (ahead of need) on flights over both continents, with every frame's building counts equal to a game
that loaded everything at login; the drawn view (every texture's image, corners, texture coordinates, colour,
layer; the scene's model actors) equal to that full path at a view on every data addon and with the game's
models on; in combat nothing loads and the view equals the view with buildings off, then loads when combat
ends; a data addon the game will not load is said once in chat, not asked for every frame, listed by
/gps3d test; the per-frame check makes no garbage. Login time and Lua memory are printed for both paths.

Run from tools/sandbox: python3 test_ondemand.py
  A5_OLD=<folder>   runs the checks on another GPS3D folder (one whose TOC lists the data: the code before
                    the change), to show which checks fail there.
  A5_FULL=<folder>  takes the full path (everything at login) from that folder's code instead of this one's.
"""
import lupa.lua54 as lupa54, os, sys, time, re, glob, math

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
TILE = 1600 / 3
W, H = 1280, 800
OLD = os.environ.get('A5_OLD')
FULLDIR = os.environ.get('A5_FULL')
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS' if ok else 'FAIL'), name, detail)
    return bool(ok)


def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('#')]


GPS_FILES = toc_files(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))
DATA_ADDONS = sorted(os.path.basename(d) for d in glob.glob(os.path.join(SITE, 'addons', 'GPS3D_*')))
# every data file by its name (the old TOCs list them as Data\<name>)
DATA_FILES = {os.path.basename(p): p for d in DATA_ADDONS for p in glob.glob(os.path.join(SITE, 'addons', d, '*.lua')) if not p.endswith('Link.lua')}

# The index of the bands (Data/DetailParts.lua), read here independently of the addon
PARTS, TOPS = {}, {}
for m in re.finditer(r'\[(\d+)\] = \{ (.*?),\n\ttiles = \{ (.*?) \},\n\ttops = \{ (.*?) \} \},', open(os.path.join(SITE, 'addons', 'GPS3D', 'Data', 'DetailParts.lua')).read()):
    names = re.findall(r'"([^"]+)"', m.group(2))
    PARTS[int(m.group(1))] = (names, {int(k): names[int(v) - 1] for k, v in re.findall(r'\[(\d+)\]=(\d+)', m.group(3))})
    TOPS[int(m.group(1))] = {int(k): float(v) for k, v in re.findall(r'\[(\d+)\]=([-0-9.e]+)', m.group(4))}


def tile_dist(cx, cy, key):
    tx, ty = key % 64, key // 64
    nx = min(max(cx, tx * TILE), (tx + 1) * TILE)
    ny = min(max(cy, -(ty + 1) * TILE), -ty * TILE)
    return math.hypot(nx - cx, ny - cy)


def bands_near(m, cx, cy, reach):
    return {name for key, name in PARTS.get(m, ([], {}))[1].items() if tile_dist(cx, cy, key) < reach}


SNAPSHOT = r'''
-- What the 3D view draws: every shown texture or text under the canvas (its frame's place in the tree, layer,
-- sublevel, image, corners, texture coordinates, colour, alpha) and every shown model actor of the scene.
local fmt, concat = string.format, table.concat
local function num(v) return fmt("%.6f", v) end
function A5_SNAPSHOT()
  local ns = SANDBOX.namespaces.GPS3D
  local out = {}
  local function walk(f, path)
    if not f:IsVisible() then return end
    for _, r in ipairs(f._regions) do
      if r._shown then
        if r._isText then
          out[#out + 1] = path .. "|T|" .. r._layer .. "|" .. r._sub .. "|" .. tostring(r._text)
        elseif r._file then
          local vo, tc, c = r._vo or {}, r._tc or {}, r._color
          local v, t = {}, {}
          for i = 1, 8 do v[i] = num(vo[i] or 0); t[i] = num(tc[i] or 0) end
          out[#out + 1] = concat({ path, r._layer, r._sub, tostring(r._file), concat(v, ","), concat(t, ","),
            num(c[1]), num(c[2]), num(c[3]), num(c[4] or 1), num(r._alpha) }, "|")
        end
      end
    end
    for i, child in ipairs(f._children) do walk(child, path .. "." .. i) end
  end
  walk(ns.canvas, "c")
  for _, a in ipairs(ns.scene._actors or {}) do
    if a._shown and a._model then
      local p = a._pos or { 0, 0, 0 }
      out[#out + 1] = concat({ "actor", tostring(a._model), num(p[1]), num(p[2]), num(p[3]), num(a._yaw or 0), num(a._pitch or 0), num(a._roll or 0), num(a._scale or 1) }, "|")
    end
  end
  table.sort(out)
  return concat(out, "\n"), #out
end
function A5_MEM() collectgarbage("collect"); collectgarbage("collect"); return collectgarbage("count") / 1024 end
-- garbage made by n calls of the per-frame check, the collector stopped (KB)
function A5_GARBAGE(n)
  local ns = SANDBOX.namespaces.GPS3D
  collectgarbage("collect"); collectgarbage("stop")
  local m0 = collectgarbage("count")
  for _ = 1, n do ns.WantData() end
  local kb = collectgarbage("count") - m0
  collectgarbage("restart")
  return kb
end
'''


class Game:
    """Both addons in a fresh Lua. ondemand: GPS3D as its TOC says (the data addons load when asked);
    full: every data file run in GPS3D's namespace at login, as GPS3D.toc listed them before 2026-10-22."""

    def __init__(self, mode='ondemand', gps3d_dir=None, refuse=None, combat=False, props=None, buildings=None, detail=None):
        self.mode = mode
        self.L = lupa54.LuaRuntime()
        G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(open(f'{SITE}/zones.lua').read())
        G.SANDBOX_SITE = SITE
        for name, reason in (refuse or {}).items():
            G.SANDBOX.lodRefuse[name] = reason
        self.L.execute(SNAPSHOT)
        for f in GPS_FILES:
            if not G.SANDBOX_LOAD('GnomishPositioningSystem', f, open(f'{SITE}/addons/GnomishPositioningSystem/{f}').read()): print('LOAD FAILED', f)
        G.SANDBOX_LOADED('GnomishPositioningSystem')
        m0 = G.A5_MEM()
        t0 = time.perf_counter()
        folder = gps3d_dir or os.path.join(SITE, 'addons', 'GPS3D')
        for f in toc_files(os.path.join(folder, 'GPS3D.toc')):
            path = os.path.join(folder, f)
            if not os.path.exists(path):  # (an old TOC's Data\Detail_*, Data\Models_*: now in the data addons)
                path = DATA_FILES.get(os.path.basename(f)) or os.path.join(SITE, 'addons', 'GPS3D', f)
            if not G.SANDBOX_LOAD('GPS3D', f, open(path).read()): print('LOAD FAILED', f)
        if mode == 'full':
            for d in DATA_ADDONS:
                for f in toc_files(os.path.join(SITE, 'addons', d, d + '.toc')):
                    if f != 'Link.lua' and not gps3d_dir:
                        G.SANDBOX_LOAD('GPS3D', 'Data/' + f, open(os.path.join(SITE, 'addons', d, f)).read())
                G.SANDBOX.loadedAddons[d] = True  # (so the code asks for none of them)
        G.SANDBOX_LOADED('GPS3D')
        self.login_s = time.perf_counter() - t0
        self.login_mb = G.A5_MEM() - m0
        if combat: G.SANDBOX_COMBAT(True)
        G.SANDBOX_PLAYER(-8830, 640, 0, 0, 2.3, 'Stormwind City', 'Trade District', -1, -1, -1)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False)
        self.ns = G.SANDBOX.namespaces['GPS3D']
        self.L.eval('function() GPS3D_DB = GPS3D_DB or {} end')()
        for key, v in (('props', props), ('buildingModels', buildings)):
            if v is not None: G.GPS3D_DB[key] = v
        if props is not None or buildings is not None: self.ns.ModelsChanged()
        if detail is not None: self.ns.SetDetail(detail)
        self.tick(2)

    def tick(self, n=1, dt=1 / 30):
        for _ in range(n): self.G.SANDBOX_TICK(dt, W, H)

    def chat(self):
        return str(self.G.SANDBOX_CHAT() or '')

    def open(self):
        self.G.SlashCmdList.GPS('')
        self.tick(2)
        self.G.GPS3D_API.Show(self.G.GPS_MapFrame, None)
        self.G.GPS_MapFrame.Hide(self.G.GPS_MapFrame)
        self.tick(5)

    def view(self, m, x, y, dist=330, pitch=89.9, yaw=30, jump=True):
        """jump: the view put there as the 2D map hands it over (GPS3D_API.Show with a focus: SetMap); else
        the camera's centre moved as a drag moves it (the height it aims at kept)."""
        ns, cam = self.ns, self.ns.cam
        if jump:
            self.G.GPS3D_API.Show(None, self.L.table_from({'map': m, 'gx': x / TILE, 'gy': -y / TILE}))
        else:
            cam.x, cam.y = x, y
        ns.SetTopDown(pitch >= 89, True)
        cam.dist, cam.pitch, cam.yaw = dist, pitch, yaw

    def settle(self):
        for _ in range(40):
            self.ns.Render()
            if self.ns.stats.detailPending == 0: break
        self.ns.Render()
        self.tick(3)  # (the models' choice runs on its driver frame)
        self.ns.Render()

    def snap(self):
        s, n = self.G.A5_SNAPSHOT()
        return str(s), int(n)

    def loads(self):
        lo = self.G.SANDBOX.lodLoads
        return [str(lo[i]) for i in range(1, len(lo) + 1)]

    def stats(self):
        st = self.ns.stats
        return (int(st.detail), int(st.detailTris), int(st.detailPending), int(st.detailSkipped), int(st.tris), int(st.shown))


def state(g, name):
    d = g.ns.dataState
    return str(d.state[name]) if d is not None and d.state[name] is not None else None


# ---------------------------------------------------------------------------------------------------------------
# Login, and the view opening at Stormwind
# ---------------------------------------------------------------------------------------------------------------
NEW = OLD or None
full = Game('full', gps3d_dir=FULLDIR)
od = Game('ondemand', gps3d_dir=NEW)
print(f'login (sandbox, Lua 5.4): GPS3D with everything {full.login_s * 1000:.0f} ms, +{full.login_mb:.1f} MB; on demand {od.login_s * 1000:.0f} ms, +{od.login_mb:.1f} MB')
nd = sum(1 for _ in (od.ns.Detail[0] or {}).keys()) if od.ns.Detail and od.ns.Detail[0] else 0
check('login: no data addon loaded, no building or model data in memory', od.loads() == [] and nd == 0 and not od.ns.Models,
      f'loaded {od.loads()}, Eastern Kingdoms tiles with buildings {nd}, models {"yes" if od.ns.Models else "no"}; Lua memory +{od.login_mb:.1f} MB (everything at login: +{full.login_mb:.1f} MB)')
check('login: memory down by the data (at least 40 MB less than everything at login)', full.login_mb - od.login_mb > 40, f'{full.login_mb:.1f} -> {od.login_mb:.1f} MB')

# the index's highest point per tile (TileTop reads it instead of the strings since 2026-10-22) against the strings,
# worked out in Lua as TileTop did before: per block its base raised by its highest vertex
full.L.execute('''
function A5_TOPS()
  local ns = SANDBOX.namespaces.GPS3D
  local B64, Num = ns.B64, ns.Num
  local out, n = {}, 0
  for map, m in pairs(ns.Detail) do
    for key, str in pairs(m) do
      local tb = ns.TileBlocks(map, key % 64, key // 64)
      local top = -math.huge
      for bi = 0, 63 do
        local pos = tb[bi]
        if pos then
          local base = (Num(str, pos + 1, 3) - 131072) * 0.25
          local nv, np = Num(str, pos + 4, 3), Num(str, pos + 10, 1)
          local p, best = pos + 11 + np * 3, 0
          for _ = 1, nv do
            local c3, c4, c5 = str:byte(p + 2, p + 4)
            local dh = (B64[c3] % 16) * 4096 + B64[c4] * 64 + B64[c5]
            if dh > best then best = dh end
            p = p + 6
          end
          if base + best * 0.25 > top then top = base + best * 0.25 end
        end
      end
      n = n + 1
      out[n] = map .. ":" .. key .. "=" .. string.format("%.17g", top)
    end
  end
  return table.concat(out, ";")
end''')
got = {}
for item in str(full.G.A5_TOPS()).split(';'):
    k, v = item.split('=')
    m_, key = k.split(':')
    got[(int(m_), int(key))] = float(v)
want = {(m_, k): v for m_, t in TOPS.items() for k, v in t.items()}
bad = sum(1 for k in want if got.get(k) != want[k])
check("the index's highest point of every tile's buildings equals what TileTop read from the strings before", len(got) == len(want) == 859 and bad == 0, f'{len(got)} tiles, {bad} different')

for g in (full, od): g.open()
cam = od.ns.cam
want = bands_near(0, cam.x, cam.y, 1000 + TILE)
check('opening the view at Stormwind loads only the band(s) within a tile of the building reach there, before the first frame',
      sorted(od.loads()) == sorted(want) and od.stats()[0] > 0, f'loaded {od.loads()}, expected {sorted(want)}; first frame {od.stats()[0]} blocks raised')
ms = {n: float(od.ns.dataState.ms[n]) for n in od.loads()} if od.ns.dataState is not None else {}
print('  first-use hitch (sandbox, Lua 5.4):', ', '.join(f'{n} {v:.0f} ms' for n, v in ms.items()))
for g in (full, od): g.tick(20)
a, b = full.snap(), od.snap()
check('Stormwind as the view opens (following you): drawn exactly as with everything loaded at login', a == b, f'{b[1]} textures and actors; {"equal" if a == b else "DIFFERENT"}')

# the per-frame check: no garbage, cheap
if od.ns.WantData is not None:
    kb = float(od.G.A5_GARBAGE(10000))
    t0 = time.perf_counter()
    for _ in range(20000): od.ns.WantData()
    us = (time.perf_counter() - t0) / 20000 * 1e6
    check('the check run before every frame makes no garbage (10,000 calls, the camera still)', kb < 1, f'{kb:.2f} KB; {us:.2f} us a call (sandbox)')
else:
    check('the check run before every frame makes no garbage (10,000 calls, the camera still)', False, 'no OnDemand.lua')

# ---------------------------------------------------------------------------------------------------------------
# A view on every data addon: drawn exactly as the full path
# ---------------------------------------------------------------------------------------------------------------
# per data addon and map, its tile with the most building data
biggest = {}
for d in DATA_ADDONS:
    for p in glob.glob(os.path.join(SITE, 'addons', d, 'Detail_*.lua')):
        m = int(re.match(r'Detail_(\d+)', os.path.basename(p)).group(1))
        for line in open(p):
            r = re.match(r't\[(\d+)\]="', line)
            if r and len(line) > biggest.get((m, d), (0, 0))[1]: biggest[(m, d)] = (int(r.group(1)), len(line))
views = [(m, name, biggest[(m, name)][0]) for m, (names, tiles) in sorted(PARTS.items()) for name in names]
seen_names = set()
for m, name, k in views:
    if m not in (0, 1) and name in seen_names and m not in (309, 509): continue  # (instances: three maps)
    seen_names.add(name)
    x, y = (k % 64 + 0.5) * TILE, -(k // 64 + 0.5) * TILE
    for pitch in (89.9, 45):
        for g in (full, od):
            g.view(m, x, y, 330, pitch)
            g.settle()
        a, b = full.snap(), od.snap()
        sa, sb = full.stats(), od.stats()
        check(f'map {m} tile {k % 64},{k // 64} ({name}), {"straight down" if pitch > 89 else "tilted 45"}: drawn exactly as with everything loaded',
              a == b and sb[0] > 0, f'{sb[0]} blocks, {sb[1]} building triangles, {b[1]} textures and actors; {"equal" if a == b else f"DIFFERENT (full {sa})"}')
print('  loaded so far:', od.loads())

# ---------------------------------------------------------------------------------------------------------------
# Flights over both continents: each band loaded ahead of need, every frame's buildings as the full path
# ---------------------------------------------------------------------------------------------------------------
def flight(m, step=120, dist=330):
    names, tiles = PARTS[m]
    rows = {}
    for k in tiles:
        rows.setdefault(k // 64, []).append(k % 64)
    pts = [((sorted(v)[len(v) // 2] + 0.5) * TILE, -(ty + 0.5) * TILE) for ty, v in sorted(rows.items())]
    path = []
    pts.insert(0, (pts[0][0], pts[0][1] + 3000))  # (from 3,000 yd north of the first row: every band is approached)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        path += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return path


for m, land in ((0, 'the Eastern Kingdoms'), (1, 'Kalimdor')):
    g1, g2 = Game('full', gps3d_dir=FULLDIR), Game('ondemand', gps3d_dir=NEW)
    for g in (g1, g2):
        g.open()
    path = flight(m)
    early, late, worst_ahead, same, frames, raised = [], [], math.inf, True, 0, 0
    at_open = set(g2.loads())  # (Stormwind's band, the view having opened on you there)
    for g in (g1, g2):
        g.view(m, path[0][0], path[0][1], 330, 89.9)  # (the start: a jump, which loads what is within reach there)
    at_jump = [n for n in g2.loads() if n not in at_open]
    jump_ok = sorted(at_jump) == sorted(bands_near(m, g2.ns.cam.x, g2.ns.cam.y, 1000 + TILE))
    for i, (x, y) in enumerate(path):
        before = set(g2.loads())
        for g in (g1, g2):
            g.view(m, x, y, 330, 89.9, jump=False)
            g.ns.Render()
        frames += 1
        for name in set(g2.loads()) - before:  # loaded this frame: how far was its nearest tile?
            d = min(tile_dist(x, y, k) for k, n in PARTS[m][1].items() if n == name)
            worst_ahead = min(worst_ahead, d)
            (early if d > 1000 else late).append((name, round(d)))
        if g1.stats()[:3] != g2.stats()[:3]:
            same = False
            print('  differs at', i, g1.stats(), g2.stats())
        raised += g2.stats()[0]
    names = PARTS[m][0]
    check(f'flight over {land} ({frames} frames of 120 yd, 330 yd straight down): every band loaded, each while more than DETAIL_RANGE (1,000 yd) from the view centre',
          set(names) <= set(g2.loads()) and not late and early and jump_ok,
          f'at the start (a jump) {at_jump}; then in this order {[e[0] for e in early + late]}, the nearest tile of each {[e[1] for e in early + late]} yd away when it loaded (late: {late})')
    check(f'flight over {land}: every frame the same blocks raised, triangles and pending blocks as with everything loaded at login', same and raised > 0, f'{raised} blocks raised over the flight')

# ---------------------------------------------------------------------------------------------------------------
# Far out, nothing loads that the view does not draw; a height asked for anywhere loads its band at once
# ---------------------------------------------------------------------------------------------------------------
gf1, gf2 = Game('full', gps3d_dir=FULLDIR), Game('ondemand', gps3d_dir=NEW)
for g in (gf1, gf2): g.open()
same = True
for g in (gf1, gf2):
    g.view(0, 32 * TILE, -40 * TILE, 12000, 55, 0)  # (a jump: the band under the point looked at loads, for its height)
at_open = gf2.loads()
for k in range(36):  # turning round at 12,000 yd, tilted 55 (the camera's ground point 6,900 yd out, over every band)
    for g in (gf1, gf2):
        g.ns.cam.yaw = k * 10; g.ns.Render()
    same = same and gf1.snap() == gf2.snap()
check('the Eastern Kingdoms from 12,000 yd, tilted 55, turning round: no band loaded while turning (none is drawn), the view drawn exactly as with everything loaded',
      gf2.loads() == at_open and same, f'loaded {gf2.loads()} (before turning: {at_open}); {"equal" if same else "DIFFERENT"} over 36 views')
uc = (31.55 * TILE, -28.91 * TILE)  # the ruins over the Undercity (another band)
h1, h2 = float(gf1.ns.GroundHeight(uc[0], uc[1], 0)), float(gf2.ns.GroundHeight(uc[0], uc[1], 0))
check('a height asked for where no band is loaded (the Undercity ruins) loads its band at once and is the same as with everything loaded',
      h1 == h2 and len(gf2.loads()) == len(at_open) + 1, f'{h2:.2f} vs {h1:.2f} yd; loaded {gf2.loads()}')

# ---------------------------------------------------------------------------------------------------------------
# The game's models: not loaded with the defaults, loaded when switched on, drawn as the full path
# ---------------------------------------------------------------------------------------------------------------
check("the game's models (GPS3D_Models) never loaded with the default settings (props off, buildings simplified)",
      'GPS3D_Models' not in od.loads(), f'loaded {od.loads()}')
gm1 = Game('full', gps3d_dir=FULLDIR, props=True, buildings='game')
gm2 = Game('ondemand', gps3d_dir=NEW, props=True, buildings='game')
gm1.G.SANDBOX_WMO = True; gm2.G.SANDBOX_WMO = True
for g in (gm1, gm2):
    g.open(); g.tick(30)
check("props on and the game's buildings chosen: the models load with the view", 'GPS3D_Models' in gm2.loads(), f'loaded {gm2.loads()}')
for nm, X, Y, m in (('Goldshire', -9464, 62, 0), ('Orgrimmar', 1630, -4380, 1)):
    for g in (gm1, gm2):
        g.G.SANDBOX_PLAYER(X, Y, 0, m, 1.0, nm, '', -1, -1, -1)
        g.tick(60)
        g.ns.Render(); g.tick(5)
    a, b = gm1.snap(), gm2.snap()
    na = sum(1 for l in b[0].split('\n') if l.startswith('actor'))
    check(f"{nm} with the game's models: drawn exactly as with everything loaded (textures and model actors)", a == b and na > 0,
          f'{b[1]} textures and actors, {na} actors; {"equal" if a == b else "DIFFERENT"}')

# ---------------------------------------------------------------------------------------------------------------
# In combat: nothing loads, the view as with buildings off; after combat: loaded, as the full path
# ---------------------------------------------------------------------------------------------------------------
gc = Game('ondemand', gps3d_dir=NEW, combat=True)
goff = Game('full', gps3d_dir=FULLDIR, detail=False)
for g in (gc, goff): g.open(); g.tick(20)
gc.G.SlashCmdList.GPS3D('test'); gc.tick(100)
said = gc.chat()
a, b = goff.snap(), gc.snap()
check('in combat: nothing loaded, the view drawn exactly as with buildings off, no Lua error',
      gc.loads() == [] and a == b and 'Lua error' not in said, f'loaded {gc.loads()}; {b[1]} textures; {"equal" if a == b else "DIFFERENT"}')
check('/gps3d test in combat says the buildings wait for combat to end', 'waits for combat to end' in said and 'which you are in now' in said,
      next((l for l in said.split('\n') if 'data on demand' in l), 'no line')[:220])
gc.G.SANDBOX_COMBAT(False); gc.tick(5)
gfull = Game('full', gps3d_dir=FULLDIR)
gfull.open(); gfull.tick(25)
a, b = gfull.snap(), gc.snap()
check('combat over: the band loads and the view is drawn exactly as with everything loaded', gc.loads() != [] and a == b,
      f'loaded {gc.loads()}; {"equal" if a == b else "DIFFERENT"}')

# ---------------------------------------------------------------------------------------------------------------
# A data addon the game will not load (folder not copied)
# ---------------------------------------------------------------------------------------------------------------
gx = Game('ondemand', gps3d_dir=NEW, refuse={n: 'MISSING' for n in PARTS[0][0]})
gx.open()
for i in range(60):  # moving about Stormwind and Elwynn: the check runs again and again
    gx.view(0, gx.ns.cam.x + 60, gx.ns.cam.y - 30, 330, 89.9, jump=False)
    gx.ns.Render()
said = gx.chat()
gx.G.SlashCmdList.GPS3D('test'); gx.tick(100)
test = gx.chat()
calls = int(gx.ns.dataState.calls) if gx.ns.dataState is not None else -1
asked = len([l for l in said.split('\n') if 'could not load' in l])
check('a band not installed: said once in chat per band, LoadAddOn not asked again every frame, nothing drawn missing but those buildings',
      0 < asked == calls <= 4 and 'Lua error' not in said, f'{asked} chat lines, {calls} LoadAddOn calls over 60 frames: ' + next((l for l in said.split('\n') if 'could not load' in l), '')[:160])
check('/gps3d test names the missing folders', 'data missing' in test and 'GPS3D_EK' in test, next((l for l in test.split('\n') if 'data missing' in l), 'no line')[:200])

passed = sum(1 for _, ok in results if ok)
print(f'{passed} of {len(results)} checks passed')
sys.exit(0 if passed == len(results) else 1)
