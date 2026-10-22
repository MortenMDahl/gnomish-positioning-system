# Checks GPS as the minimap (GPS3D's Minimap.lua, since 2026-10-22) on the sandbox engine (Lua 5.4), with the
# engine's stand-in of Blizzard's minimap (SANDBOX_MINIMAP: MinimapCluster, Minimap 198 px round, its zoom buttons,
# ring, blips drawn flat at C_Minimap.GetViewRadius, rotateMinimap, PingLocation, C_Minimap.SetDrawGroundTextures):
# - off by default; the setting on GPS's settings page and /gps minimap on|off, applied at once, kept over a reload;
# - its own detail ("Minimap ground detail", "Minimap building detail", /gps minimap ground|buildings <n>), applied at
#   once, saved, and independent of the 3D window's Ground and Building detail both ways;
# - on: GPS3D's canvas in a host under Blizzard's Minimap (BACKGROUND strata, as Blizzard's HybridMinimap), the
#   minimap's ground art off, the ground and buildings drawn, every texture masked round;
# - follows you, north up or turned with you (rotateMinimap), tilted as set; Blizzard's blips (drawn flat by the
#   game) on the ground point they mark; zoom with Blizzard's own buttons and wheel; clicks stay Blizzard's (ping);
# - falls back to Blizzard's minimap in an instance, indoors, without a position or terrain, while the 3D window
#   is open (which then draws exactly as in a game that never had the minimap on), and back;
# - off restores everything exactly (Blizzard's minimap and GPS3D's canvas, frame levels, strata, anchors);
# - the cost a frame standing still and walking (Lua ms, C calls, textures) and memory; the buildings' data
#   loaded for the minimap; no Blizzard function or field replaced; combat;
# - each check's code broken on purpose (MUTANTS) makes that check fail.
# Usage: python test_minimap.py   (fill site/addons first)   NO_MUTANTS=1 skips the mutation runs.
import lupa.lua54 as lupa54, os, sys, subprocess, json, math, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
ROOT = os.path.join(HERE, '..', '..')
os.chdir(HERE)  # (the data addons load from site/addons)
# (name, addon, file, text, replacement, the check that must fail)
MUTANTS = [
    ("the minimap's ground art left on", 'GPS3D', 'Minimap.lua', '\tif C_Minimap and C_Minimap.SetDrawGroundTextures then C_Minimap.SetDrawGroundTextures(false) end\n', '', 'on: GPS\'s view in the minimap'),
    ('no stretch: the tilted view squashes the ground', 'GPS3D', 'Minimap.lua', '\tcam.stretch = 1 / sin(rad(pitch))\n', '\tcam.stretch = nil\n', "Blizzard's blips on the ground"),
    ('levels not put back', 'GPS3D', 'Minimap.lua', '\t\te[1]:SetFrameLevel(e[3])\n', '', 'off restores'),
    ('the 3D window opens without taking the canvas back', 'GPS3D', 'GPS3D.lua', '\tif ns.MinimapYield then ns.MinimapYield() end -- the minimap gives the canvas and the camera back (Minimap.lua)\n', '', 'the 3D window'),
    ('no round mask', 'GPS3D', 'Minimap.lua', '\tif Round() then MaskAll(true) end\n', '', 'round mask'),
    ('redrawn every frame', 'GPS3D', 'Minimap.lua', '\tif Aim() or ns.stats.detailPending > 0 then Draw() end\n', '\tAim(); Draw()\n', 'standing still'),
    ('no fallback in an instance', 'GPS3D', 'Minimap.lua', '\tif MM.indoor then return MM.indoor end\n', '', 'instance'),
    ('the zoom not followed', 'GPS3D', 'Minimap.lua', '\tlocal R = C_Minimap and C_Minimap.GetViewRadius and C_Minimap.GetViewRadius() or MM.RADIUS\n', '\tlocal R = MM.RADIUS\n', 'zoom'),
    ('north up while the minimap turns', 'GPS3D', 'Minimap.lua', '\tcam.yaw = Rotating() and (-deg(p.facing)) % 360 or 0\n', '\tcam.yaw = 0\n', 'turns with you'),
    ('the canvas takes the mouse', 'GPS3D', 'Minimap.lua', '\tcanvas:EnableMouse(false)\n', '', 'mouse'),
    ('the minimap draws at fixed budgets, not its settings', 'GPS3D', 'Minimap.lua', '\tns.SetBudgets(MM.grid, MM.detail)\n', '\tns.SetBudgets(1200, 1500)\n', 'Minimap ground detail'),
    ("the 3D window's budgets not put back after a minimap draw", 'GPS3D', 'Minimap.lua', '\tns.SetBudgets(grid, detail)\n', '', 'independent'),
    ('no /gps minimap', 'GnomishPositioningSystem', 'Core.lua', '\telseif cmd == "minimap" or cmd:match("^minimap%s") then\n', '\telseif cmd == "minimap-off" then\n', '/gps minimap'),
]
mutant = MUTANTS[int(sys.argv[sys.argv.index('--mutant') + 1])] if '--mutant' in sys.argv else None
W, H = 1280, 800
TILE = 1600 / 3

# Counting the texture calls GPS makes inside the minimap's driver (as perf_focus.py, installed before the addons
# load, since GPS3D binds SetVertexOffset once at load)
WRAP = r'''
CALLS, COUNTING = {}, false
local names = { "SetVertexOffset", "SetDrawLayer", "SetParent", "Show", "Hide", "SetTexCoord", "SetTexture", "SetVertexColor", "AddMaskTexture", "RemoveMaskTexture" }
local tex = UIParent:CreateTexture()
local Texture = getmetatable(tex)
for _, n in ipairs(names) do
  local f = Texture[n]
  Texture[n] = function(...) if COUNTING then CALLS[n] = (CALLS[n] or 0) + 1 end return f(...) end
end
function CALLS_RESET() for k in pairs(CALLS) do CALLS[k] = 0 end end
function CALLS_TOTAL() local s = 0 for _, v in pairs(CALLS) do s = s + v end return s end
'''
HELPERS = r'''
local S = SANDBOX
function SNAP_CANVAS()
  local ns = S.namespaces.GPS3D
  local c = ns.canvas
  local out = {}
  local function pts(f) local t = {} for i = 1, f:GetNumPoints() do local p, r, rp, x, y = f:GetPoint(i); t[#t + 1] = p .. ":" .. tostring(r) .. ":" .. rp .. ":" .. x .. ":" .. y end return table.concat(t, ";") end
  out[#out + 1] = tostring(c:GetParent()) .. "|" .. pts(c) .. "|" .. c:GetFrameStrata() .. "|" .. c:GetFrameLevel() .. "|" .. tostring(c:IsMouseEnabled()) .. "|" .. tostring(c:IsMouseWheelEnabled()) .. "|" .. tostring(c:IsShown())
  local function walk(f) for _, k in ipairs({ f:GetChildren() }) do out[#out + 1] = tostring(k) .. "|" .. k:GetFrameStrata() .. "|" .. k:GetFrameLevel() .. "|" .. tostring(k:IsShown()) .. "|" .. pts(k); walk(k) end end
  walk(c)
  local masked = 0
  for _, r in ipairs({ c:GetRegions() }) do if (r.GetNumMaskTextures and r:GetNumMaskTextures() or 0) > 0 then masked = masked + 1 end end
  for _, f in ipairs(ns.bucketFrames) do for _, r in ipairs({ f:GetRegions() }) do if r:GetNumMaskTextures() > 0 then masked = masked + 1 end end end
  out[#out + 1] = "masked " .. masked
  local cam = ns.cam
  for _, k in ipairs({ "map", "x", "y", "th", "dist", "yaw", "pitch", "fov", "vp", "stretch" }) do out[#out + 1] = k .. "=" .. tostring(cam[k]) end
  local g, d, u = ns.Budgets()
  out[#out + 1] = "budgets " .. g .. " " .. d .. " " .. tostring(u)
  return table.concat(out, "\n")
end
function SNAP_BLIZZ()
  local out = {}
  local function keys(t, name) local ks = {} for k, v in pairs(t) do if type(k) == "string" and not k:match("^_") then ks[#ks + 1] = k .. "=" .. tostring(v) end end table.sort(ks) out[#out + 1] = name .. ": " .. table.concat(ks, ",") end
  keys(Minimap, "Minimap"); keys(MinimapCluster, "Cluster"); keys(C_Minimap, "C_Minimap"); keys(Minimap.ZoomIn, "ZoomIn"); keys(MinimapBackdrop, "Backdrop")
  for _, s in ipairs({ "OnMouseUp", "OnMouseWheel", "OnEnter", "OnLeave", "OnUpdate", "OnShow", "OnHide" }) do out[#out + 1] = s .. "=" .. tostring(Minimap:GetScript(s)) end
  out[#out + 1] = "ground " .. tostring(C_Minimap.GetDrawGroundTextures()) .. " zoom " .. Minimap:GetZoom() .. " strata " .. Minimap:GetFrameStrata() .. " level " .. Minimap:GetFrameLevel() .. " alpha " .. Minimap:GetAlpha() .. " shown " .. tostring(Minimap:IsShown())
  out[#out + 1] = "rect " .. table.concat({ S.rect(Minimap) }, ",") .. " mask " .. tostring(Minimap._maskFile)
  local blips = {}
  for _, t in ipairs(Minimap.SandboxBlips) do blips[t] = true end -- (the stand-in's own blip textures, made as blips come)
  for _, r in ipairs({ Minimap:GetRegions() }) do if not blips[r] then out[#out + 1] = "region " .. tostring(r) .. " " .. tostring(r:IsShown() or r == Minimap.SandboxGround) .. " " .. (r.GetNumMaskTextures and r:GetNumMaskTextures() or 0) end end
  for _, n in ipairs({ "Minimap_ZoomIn", "Minimap_ZoomOut", "GetMinimapShape", "ToggleMinimap", "Minimap" }) do out[#out + 1] = n .. "=" .. tostring(_G[n]) end
  return table.concat(out, "\n")
end
-- every shown ground texture of the 3D canvas: image and screen corners
function DRAWSTATE()
  local ns = S.namespaces.GPS3D
  local list = {}
  for _, f in ipairs(ns.bucketFrames) do
    if f:IsVisible() then
      for _, t in ipairs({ f:GetRegions() }) do
        if t:IsShown() and t._file then
          local l, b, r, tp = S.rect(t)
          local vo = t._vo or { 0, 0, 0, 0, 0, 0, 0, 0 }
          local tc = t._tc or { 0, 0, 0, 1, 1, 0, 1, 1 }
          list[#list + 1] = string.format("%s|%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f|%.4f,%.4f,%.4f,%.4f,%.4f,%.4f", tostring(t._file), l + vo[1], tp + vo[2], l + vo[3], b + vo[4], r + vo[5], tp + vo[6], r + vo[7], b + vo[8], tc[1], tc[2], tc[3], tc[4], tc[5], tc[6])
        end
      end
    end
  end
  table.sort(list)
  return table.concat(list, "\n")
end
-- the minimap's shown textures and how many carry the mask, and which other textures do
function MASKSTATE()
  local ns = S.namespaces.GPS3D
  local mm = ns.minimap
  local shown, masked, wrong = 0, 0, 0
  local all = { ns.canvas:GetRegions() }
  for _, f in ipairs(ns.bucketFrames) do for _, t in ipairs({ f:GetRegions() }) do all[#all + 1] = t end end
  for _, t in ipairs(all) do
    if t.GetNumMaskTextures then
      local m = t:GetNumMaskTextures() > 0
      if t:IsVisible() then shown = shown + 1; if m and t:GetMaskTexture(1) == mm.mask then masked = masked + 1 end end
      if m and t:GetMaskTexture(1) ~= mm.mask then wrong = wrong + 1 end
    end
  end
  return shown, masked, wrong
end
function TIME_DRIVER()
  local mm = S.namespaces.GPS3D.minimap
  local f = mm.driver:GetScript("OnUpdate")
  DRIVER_MS = {}
  mm.driver:SetScript("OnUpdate", function(...)
    COUNTING = true
    local t0 = os.clock()
    f(...)
    DRIVER_MS[#DRIVER_MS + 1] = (os.clock() - t0) * 1000
    COUNTING = false
  end)
end
function TIME_FRAME()
  local fr = GPS3D_Frame
  local f = fr:GetScript("OnUpdate")
  FRAME_MS = {}
  fr:SetScript("OnUpdate", function(...)
    COUNTING = true
    local t0 = os.clock()
    f(...)
    FRAME_MS[#FRAME_MS + 1] = (os.clock() - t0) * 1000
    COUNTING = false
  end)
end
'''

def load(addon, f):
    src = open(f'{SITE}/addons/{addon}/{f}').read()
    if mutant and addon == mutant[1] and f == mutant[2]:
        assert src.count(mutant[3]) == 1, ('mutation text not found once', mutant[0])
        src = src.replace(mutant[3], mutant[4])
    return src

class Game:
    def __init__(self, saved=None, minimap=True, place='sw'):
        self.L = lupa54.LuaRuntime(); G = self.G = self.L.globals()
        G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
        self.L.execute(open(f'{SITE}/engine.lua').read())
        self.L.execute(WRAP)
        self.L.execute(open(f'{SITE}/zones.lua').read())
        if minimap: G.SANDBOX_MINIMAP()  # (Blizzard's minimap exists before any addon loads)
        if saved: G.SANDBOX_RESTORE(saved)
        def toc(p): return [l.strip().replace('\\', '/') for l in open(p).read().splitlines() if l.strip() and not l.startswith('##')]
        for addon, files in [('GnomishPositioningSystem', toc(os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc'))),
                             ('GPS3D', toc(os.path.join(ROOT, 'prototypes', 'GPS3D', 'GPS3D.toc')))]:
            for f in files:
                if not G.SANDBOX_LOAD(addon, f, load(addon, f)): print('LOAD FAILED', addon, f)
            G.SANDBOX_LOADED(addon)
        self.L.execute(HELPERS)
        self.goto(place)
        G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False)
        self.tick(3)
        self.ns = G.SANDBOX.namespaces['GnomishPositioningSystem']; self.ns3 = G.SANDBOX.namespaces['GPS3D']
        self.mm = self.ns3.minimap
        self.same = self.L.eval('function(a, b) return rawequal(a, b) end')
        self.chatlog = ''
        self.chat()
    PLACES = {  # world X (north), Y (west), map, facing, zone, subzone
        'sw': (-8830, 640, 0, 2.3, 'Stormwind City', 'Trade District'),
        'goldshire': (-9464, 62, 0, 1.6, 'Elwynn Forest', 'Goldshire'),
        'org': (1630, -4380, 1, 0.0, 'Orgrimmar', ''),
        'durotar': (-600, -4250, 1, 0.8, 'Durotar', 'Razor Hill'),
    }
    def goto(self, place, facing=None):
        X, Y, m, f, z, s = self.PLACES[place]
        self.at(X, Y, m, f if facing is None else facing, z, s)
    def at(self, X, Y, m=0, facing=0.0, zone='Elwynn Forest', sub=''):
        self.G.SANDBOX_PLAYER(X, Y, 0, m, facing, zone, sub, 1429, 0.5, 0.5)
    def dungeon(self):
        self.G.SANDBOX_PLAYER(0, 0, 0, -1, 0.0, 'The Deadmines', '', 291, 0.42, 0.55)
    def loading_screen(self):
        G = self.G
        G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', False, False); G.SANDBOX_FIRE('ZONE_CHANGED_NEW_AREA'); self.tick(3)
    def tick(self, n=1):
        for _ in range(n): self.G.SANDBOX_TICK(1 / 30, W, H)
    def chat(self):
        c = str(self.G.SANDBOX_CHAT() or '')
        if c:
            if not mutant: print('CHAT>', c.replace('\n', '\nCHAT> ')[:1500])
            errors.extend(l for l in c.split('\n') if 'Lua error' in l or 'stack overflow' in l or ('not simulated' in l and 'SetFixed' not in l))
            self.chatlog += c + '\n'
        return c
    def slash(self, line): self.G.SANDBOX_SLASH(line); self.tick(2); return self.chat()
    def setting(self, var, value):
        self.G.SANDBOX_SETTING_SET(var, 'true' if value is True else 'false' if value is False else str(value)); self.tick(2); self.chat()
    def control(self, var):
        for c in json.loads(str(self.G.SANDBOX_SETTINGS()))[0]['controls']:
            if c.get('var') == var: return c
    def rect(self, o): return tuple(round(v, 3) for v in self.G.SANDBOX.rect(o))
    def in_minimap(self): return bool(self.same(self.ns3.canvas.GetParent(self.ns3.canvas), self.mm.host)) if self.mm.host else False
    def in_window(self): return bool(self.same(self.ns3.canvas.GetParent(self.ns3.canvas), self.G.GPS3D_Frame))
    def ground(self): return bool(self.G.SANDBOX.minimapGround)
    def proj(self, x, y, h):
        r = self.ns3.Project(x, y, h)
        return r
    def project(self, x, y, h):
        f = self.L.eval('function(ns, x, y, h) local a, b, d = ns.Project(x, y, h); return a, b, d end')
        return f(self.ns3, x, y, h)
    def close_all(self):
        for f in (self.G.GPS_MapFrame, self.G.GPS3D_Frame, self.G.GPS_WorldMapFrame):
            if f is not None and f.IsShown(f): f.Hide(f)
        self.tick(2)

results = []
errors = []
def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    if not mutant: print(('PASS' if ok else 'FAIL'), name, detail)

g = Game()
G, ns, ns3, MM = g.G, g.ns, g.ns3, g.mm
S = G.SANDBOX
DB3 = lambda: G.GPS3D_DB

# ---- default off
canvas0 = str(G.SNAP_CANVAS()); blizz0 = str(G.SNAP_BLIZZ())
ctl = g.control('GPS3D_Minimap'); tilt = g.control('GPS3D_MinimapTilt')
check('default off: nothing of the minimap changed, GPS3D\'s canvas in its window, the settings page shows it off',
      not MM.on and not MM.active and g.ground() and g.in_window() and MM.host is None and ctl is not None and ctl['default'] is False and ctl['value'] is False
      and not MM.driver.IsShown(MM.driver), f'{ctl}')
check('settings page: "Use GPS as minimap" (off) and "Minimap tilt" (35 degrees) under a "Minimap" header after the 3D view\'s',
      ctl and ctl['name'] == 'Use GPS as minimap' and tilt and tilt['default'] == 35 and tilt['label'] == '35°', f'{tilt}')
mg, mb = g.control('GPS3D_MinimapGrid'), g.control('GPS3D_MinimapBuildings')
wg, wb = g.control('GPS3D_GridBudget'), g.control('GPS3D_BuildingBudget')
check('settings page: "Minimap ground detail" (1,200, 400 to 3,200) and "Minimap building detail" (1,500, 500 to 4,000), apart from the 3D view\'s Ground and Building detail',
      mg and mb and wg and wb and mg['name'] == 'Minimap ground detail' and mg['default'] == 1200 and mg['label'] == '1200' and mg['min'] == 400 and mg['max'] == 3200
      and mb['name'] == 'Minimap building detail' and mb['default'] == 1500 and mb['label'] == '1500' and mb['min'] == 500 and mb['max'] == 4000
      and wg['default'] == 3200 and wb['default'] == 4000, f'{mg} {mb}')

# ---- on, through the settings page
g.setting('GPS3D_Minimap', True); g.tick(2)
st = ns3.stats
r_canvas, r_mm = g.rect(ns3.canvas), g.rect(G.Minimap)
strata = [str(x) for x in g.L.eval('function(c) local t = { c:GetFrameStrata() } local function w(f) for _, k in ipairs({ f:GetChildren() }) do t[#t + 1] = k:GetFrameStrata(); w(k) end end w(c) return table.concat(t, ",") end')(ns3.canvas).split(',')]
check("on: GPS's view in the minimap (the canvas in a host under Blizzard's Minimap, BACKGROUND strata, its rect; ground art off; ground and buildings drawn)",
      MM.active and g.in_minimap() and r_canvas == r_mm and not g.ground() and set(strata) == {'BACKGROUND'} and MM.host.GetFrameStrata(MM.host) == 'BACKGROUND'
      and G.Minimap.GetFrameStrata(G.Minimap) == 'LOW' and st.tris > 0 and st.detail > 0 and DB3().minimap is True,
      f'canvas {r_canvas} minimap {r_mm} ground {g.ground()} strata {set(strata)} tris {st.tris} blocks {st.detail}')
hidden = g.L.eval('function(ns) local n = 0 for _, f in ipairs({ ns.canvas:GetChildren() }) do local b = false for _, x in ipairs(ns.bucketFrames) do if x == f then b = true end end if not b and f:IsShown() then n = n + 1 end end return n end')(ns3)
check("only the ground in GPS's view: your arrow, the models and the markers are Blizzard's minimap's own (GPS's hidden there)",
      hidden == 0 and not ns3.decal.IsVisible(ns3.decal) and not ns3.scene.IsVisible(ns3.scene), f'{hidden} other frames shown')

# ---- follows and turns
p = ns3.player
x, y, d = g.project(p.x, p.y, p.h)
w_, h_ = r_mm[2] - r_mm[0], r_mm[3] - r_mm[1]
north = g.project(p.x, p.y + 100, p.h); east = g.project(p.x + 100, p.y, p.h)
check('follows you: your spot in the middle; north up (rotateMinimap off): a point north of you straight up, east to the right',
      abs(x) < 0.5 and abs(y) < 0.5 and abs(north[0]) < 0.5 and north[1] > 10 and east[0] > 10 and abs(east[1]) < 0.5 and abs(MM.tilt - 35) < 1e-9 and abs(ns3.cam.pitch - 55) < 1e-9,
      f'you {x:.2f},{y:.2f}; north {north[0]:.2f},{north[1]:.2f}; east {east[0]:.2f},{east[1]:.2f}')
d0 = MM.draws
for k in range(1, 31):
    g.at(-8830 + k * 0.25, 640 + k * 0.1, 0, 2.3, 'Stormwind City', 'Trade District'); g.tick(1)
x, y, _ = g.project(p.x, p.y, p.h)
check('walking: redrawn every frame you moved, still centred', MM.draws - d0 == 30 and abs(x) < 0.5 and abs(y) < 0.5, f'{MM.draws - d0} redraws in 30 frames, you at {x:.2f},{y:.2f}')
S.cvars.rotateMinimap = True; g.tick(2)
f = 2.3
ahead = g.project(p.x - math.sin(f) * 100, p.y + math.cos(f) * 100, p.h)  # facing: 0 north, counter-clockwise
north = g.project(p.x, p.y + 100, p.h)
check('turns with you (rotateMinimap on, as Blizzard\'s minimap): the way you face straight up',
      abs(ahead[0]) < 0.5 and ahead[1] > 10 and abs(north[0]) > 10, f'ahead {ahead[0]:.2f},{ahead[1]:.2f}, north {north[0]:.2f},{north[1]:.2f}, yaw {ns3.cam.yaw:.2f}')
S.minimapIgnoreRotate = True; g.tick(2)
north = g.project(p.x, p.y + 100, p.h)
check('... north up again while the game says the rotation is ignored (C_Minimap.IsRotateMinimapIgnored)', abs(north[0]) < 0.5 and north[1] > 10, f'{north}')
S.minimapIgnoreRotate = False

# ---- Blizzard's blips: a point on the ground at your height projects onto the spot the game draws its blip
def blip_errors(mm_w):
    R = G.C_Minimap.GetViewRadius()
    out = {}
    for frac in (0.25, 0.5, 0.95):
        worst = 0
        for i in range(16):
            a = i * math.pi / 8
            e, n = frac * R * math.cos(a), frac * R * math.sin(a)
            # the stand-in's blip: world X north, Y west
            G.SANDBOX.minimapBlips = g.L.table_from([g.L.table_from([S.player.X + n, S.player.Y - e, 1, 1, 0])])
            g.G.SANDBOX_TICK(0, W, H)
            blip = G.Minimap.SandboxBlips[1]._blip
            sx, sy, _ = g.project(p.x + e, p.y + n, p.h)
            worst = max(worst, math.hypot(sx - blip[1], sy - blip[2]))
        out[frac] = worst
    G.SANDBOX.minimapBlips = g.L.table_from([])
    return out
errs = {}
for rot in (False, True):
    S.cvars.rotateMinimap = rot; g.tick(2)
    errs[rot] = blip_errors(w_)
check("Blizzard's blips on the ground they mark: a point at your height within 2 px of its blip halfway out, 7 px at the rim (north up and turning)",
      all(e[0.5] <= 2 and e[0.95] <= 7 for e in errs.values()),
      '; '.join(f'{"turning" if r else "north up"}: ' + ', '.join(f'{k:.0%} of the radius {v:.2f} px' for k, v in e.items()) for r, e in errs.items()))
S.cvars.rotateMinimap = False; g.tick(2)

# ---- zoom: Blizzard's buttons and wheel; the rim at GetViewRadius
def rim_ok():
    R = G.C_Minimap.GetViewRadius()
    sx, _, _ = g.project(p.x + R, p.y, p.h)
    return abs(sx - w_ / 2) / (w_ / 2), R
zs = []
for _ in range(5):
    G.Minimap_ZoomIn(); g.tick(2); zs.append(rim_ok())
cx_, cy_ = (r_mm[0] + r_mm[2]) / 2, (r_mm[1] + r_mm[3]) / 2
G.SANDBOX_MOUSE('move', cx_, cy_, '', 0)
for _ in range(5):
    G.SANDBOX_MOUSE('wheel', cx_, cy_, '', -1); g.tick(2); zs.append(rim_ok())
check('zoom: Blizzard\'s zoom buttons and the wheel over the minimap (its own code) zoom GPS\'s view, the rim at C_Minimap.GetViewRadius() yards (within 2 %)',
      all(e < 0.02 for e, _ in zs) and [round(r) for _, r in zs] == [200, 167, 133, 100, 67, 100, 133, 167, 200, 233],
      ', '.join(f'{R:.0f} yd {e:.2%}' for e, R in zs))

# ---- the mouse stays Blizzard's
top = S.hitTest(g.L.eval('function(f) return f._mouse end'))
wheel = S.hitTest(g.L.eval('function(f) return f._wheel end'))
n0 = len(S.pings)
G.SANDBOX_MOUSE('down', cx_ + 20, cy_ + 10, 'LeftButton', 0); G.SANDBOX_MOUSE('up', cx_ + 20, cy_ + 10, 'LeftButton', 0); g.tick(1)
check("mouse: Blizzard's Minimap takes the clicks (a click pings) and the wheel; GPS's frames take none there",
      g.same(top, G.Minimap) and g.same(wheel, G.Minimap) and len(S.pings) == n0 + 1 and not ns3.canvas.IsMouseEnabled(ns3.canvas) and not MM.host.IsMouseEnabled(MM.host),
      f'pings {len(S.pings) - n0}')
G.SANDBOX_MOUSE('leave', 0, 0, '', 0)

# ---- the round mask
shown, masked, wrong = G.MASKSTATE()
mr = g.rect(MM.mask)
check('round mask: every texture GPS shows in the minimap carries the minimap\'s round mask (3 px inside its edge, as HybridMinimap\'s)',
      shown > 0 and masked == shown and wrong == 0 and mr == (r_mm[0] + 3, r_mm[1] + 3, r_mm[2] - 3, r_mm[3] - 3) and 'tempportraitalphamask' in str(MM.mask._file).lower(),
      f'{masked} of {shown} masked, mask {mr}, calls {S.maskCalls}')

# ---- standing still / walking: the cost
G.TIME_DRIVER()
def measure(step, n):
    G.CALLS_RESET(); ms, calls, shownl = [], [], []
    d0 = MM.draws
    for k in range(n):
        G.CALLS_RESET()
        step(k); g.tick(1)
        ms.append(G.DRIVER_MS[len(G.DRIVER_MS)]); calls.append(int(G.CALLS_TOTAL())); shownl.append(int(ns3.stats.shown))
    return statistics.median(ms), max(ms), statistics.median(calls), statistics.median(shownl), MM.draws - d0
g.tick(5)
still = measure(lambda k: None, 60)
check('standing still: not redrawn (the driver reads your position and the zoom, nothing else)',
      still[4] == 0 and still[2] == 0, f'{still[4]} redraws in 60 frames, {still[0]:.3f} ms a frame (worst {still[1]:.3f}), {still[2]} texture calls')
X0, Y0 = -8830, 640
walk = measure(lambda k: g.at(X0 + (k + 1) * 0.25, Y0 + (k + 1) * 0.1, 0, 2.3, 'Stormwind City', 'Trade District'), 90)
turnm = measure(lambda k: (S.cvars.__setitem__('rotateMinimap', True), g.at(X0, Y0, 0, 2.3 + k * 0.05, 'Stormwind City', 'Trade District')), 60)
S.cvars.rotateMinimap = False
# the 3D window walking the same path, for comparison (its own budgets; then the minimap again)
g.slash('/gps 3d'); g.tick(10)
G.TIME_FRAME()
big = []
for k in range(60):
    G.CALLS_RESET(); g.at(X0 + k * 0.25, Y0 + k * 0.1, 0, 2.3, 'Stormwind City', 'Trade District'); g.tick(1)
    big.append((G.FRAME_MS[len(G.FRAME_MS)], int(G.CALLS_TOTAL()), int(ns3.stats.shown)))
g.close_all(); g.tick(3)
bigm = (statistics.median(b[0] for b in big), statistics.median(b[1] for b in big), statistics.median(b[2] for b in big))
check('walking: redrawn each frame you moved, at a smaller cost than the 3D window walking the same path (Lua ms, texture calls, textures)',
      walk[4] == 90 and walk[0] < bigm[0] and walk[2] < bigm[1] and walk[3] < bigm[2],
      f'minimap walking {walk[0]:.2f} ms (worst {walk[1]:.2f}), {walk[2]:.0f} calls, {walk[3]:.0f} textures; turning {turnm[0]:.2f} ms, {turnm[2]:.0f} calls; '
      f'3D window walking {bigm[0]:.2f} ms, {bigm[1]:.0f} calls, {bigm[2]:.0f} textures')
COST = {'still': still, 'walk': walk, 'turn': turnm, 'big': bigm}

# ---- the 3D window: Blizzard's minimap is back while it is open, and it draws as in a game without the minimap
g.goto('goldshire'); g.tick(5)
before = str(G.SNAP_CANVAS())
g.slash('/gps 3d'); g.tick(3)
open_ok = (not MM.active and g.in_window() and g.ground() and not MM.host.IsShown(MM.host) and G.GPS3D_Frame.IsShown(G.GPS3D_Frame))
g.tick(120)
mine = str(G.DRAWSTATE())
ref = Game(minimap=False, place='goldshire')
ref.G.SlashCmdList.GPS('3d'); ref.tick(3); ref.tick(120)
theirs = str(ref.G.DRAWSTATE())
def parse(s):
    out = []
    for line in s.split('\n'):
        if not line: continue
        fl, c, t = line.split('|')
        out.append((fl, [float(v) for v in c.split(',')], [float(v) for v in t.split(',')]))
    return out
a, b = parse(mine), parse(theirs)
worst = max((max(abs(u - v) for u, v in zip(x[1], y[1])) for x, y in zip(a, b)), default=0) if len(a) == len(b) else None
same_files = len(a) == len(b) and all(x[0] == y[0] for x, y in zip(a, b))
check("the 3D window: opening it gives the canvas back (Blizzard's minimap returns while it is open), and it draws as a game that never had the minimap on",
      open_ok and same_files and worst is not None and worst < 0.01, f'textures {len(a)} vs {len(b)}, worst corner {worst}')
del ref
canvas_ref = str(G.SNAP_CANVAS())  # (the canvas as the 3D window has it: what turning the minimap off must give back)
g.close_all(); g.tick(3)
check("the 3D window closed: GPS's view back in the minimap", MM.active and g.in_minimap() and not g.ground())

# ---- off restores exactly
g.setting('GPS3D_Minimap', False); g.tick(2)
canvas1, blizz1 = str(G.SNAP_CANVAS()), str(G.SNAP_BLIZZ())
canvas0 = canvas_ref
diff = [(x, y) for x, y in zip(canvas0.split('\n'), canvas1.split('\n')) if x != y] + [(x, y) for x, y in zip(blizz0.split('\n'), blizz1.split('\n')) if x != y]
check("off restores Blizzard's minimap and GPS3D's canvas exactly (anchors, strata and levels of every frame, mouse, masks, camera, budgets, the ground art)",
      not diff and len(canvas0) == len(canvas1) and len(blizz0) == len(blizz1) and not MM.active and not MM.host.IsShown(MM.host) and MM.driver.IsShown(MM.driver) is False,
      str(diff[:3]))

# ---- /gps minimap
s1 = g.slash('/gps minimap on'); g.tick(2); on1 = MM.active
s2 = g.slash('/gps minimap'); s3 = g.slash('/gps minimap off'); off1 = not MM.active and g.ground()
check('/gps minimap on|off sets it at once and says so; no argument says what it is',
      on1 and off1 and 'on: GPS' in s1 and 'on: GPS' in s2 and 'minimap: off' in s3 and DB3().minimap is False, f'{s1!r} {s3!r}')

# ---- kept over a reload
g.slash('/gps minimap on'); g.tick(2)
saved = str(G.SANDBOX_SAVE('GnomishPositioningSystemDB,GPS3D_DB'))
g2 = Game(saved)
g2.tick(3)
check('kept over a reload: on at login', g2.mm.on and g2.mm.active and g2.in_minimap() and not g2.ground())
g2.setting('GPS3D_MinimapTilt', 20); g2.tick(2)
check('Minimap tilt: the setting tilts the view at once and is saved', abs(g2.ns3.cam.pitch - 70) < 1e-9 and g2.G.GPS3D_DB.minimapTilt == 20, f'{g2.ns3.cam.pitch}')

# ---- the minimap's own detail settings (separate from the 3D window's)
g2.L.execute('function REC_BUDGETS(ns) local orig = ns.RenderWorld; ns.RenderWorld = function(...) local a, b = ns.Budgets(); BUDGET_SEEN = a .. " " .. b; return orig(...) end end')
g2.G.REC_BUDGETS(g2.ns3)
M2, N2 = g2.mm, g2.ns3
def nudge(gg, k):  # (a step, so the minimap redraws; returns whether it did)
    d = gg.mm.draws
    gg.at(-8830 + k * 5, 640, 0, 2.3, 'Stormwind City', 'Trade District'); gg.tick(2)
    return gg.mm.draws > d
nudge(g2, 1)
tris0, seen0 = int(N2.stats.tris), str(g2.G.BUDGET_SEEN)
d0 = M2.draws
g2.setting('GPS3D_MinimapGrid', 600); g2.tick(2)
tris1, seen1 = int(N2.stats.tris), str(g2.G.BUDGET_SEEN)
check('Minimap ground detail: the setting applies at once (redrawn at the new budget, fewer ground triangles), is saved, and the 3D window\'s budget is back after the draw',
      M2.grid == 600 and g2.G.GPS3D_DB.minimapGrid == 600 and M2.draws > d0 and seen0 == '1200 1500' and seen1.startswith('600 ') and tris1 < tris0
      and g2.L.eval('function(ns) local a, b = ns.Budgets(); return a .. " " .. b end')(N2) == '3200 4000',
      f'budgets in the draw {seen0} -> {seen1}, ground triangles {tris0} -> {tris1}')
d0 = M2.draws
g2.setting('GPS3D_MinimapBuildings', 750); g2.tick(2)
dt, seen2 = int(N2.stats.detailTris), str(g2.G.BUDGET_SEEN)
check('Minimap building detail: the setting applies at once (redrawn, building triangles within the new budget) and is saved',
      M2.detail == 750 and g2.G.GPS3D_DB.minimapBuildings == 750 and M2.draws > d0 and seen2 == '600 750' and 0 < dt <= 750,
      f'budgets in the draw {seen2}, building triangles {dt}')
# the 3D window at its defaults (never set) opens with them after the minimap drew at its own
budgets = g2.L.eval('function(ns) local a, b = ns.Budgets(); return a .. " " .. b end')
r2 = nudge(g2, 4)
g2.slash('/gps 3d'); g2.tick(3)
win0 = budgets(N2)
g2.close_all(); g2.tick(3)
# the 3D window's settings changed while the minimap is on: neither side takes the other's
g2.setting('GPS3D_GridBudget', 2400); g2.setting('GPS3D_BuildingBudget', 3000)
r3 = nudge(g2, 2); seen3 = str(g2.G.BUDGET_SEEN)
g2.slash('/gps 3d'); g2.tick(3)
win = budgets(N2)
g2.close_all(); g2.tick(3); r4 = nudge(g2, 3); seen4 = str(g2.G.BUDGET_SEEN)
check("independent: the 3D window opens at its own detail (its defaults, then values changed while the minimap is on), and those leave the minimap's alone",
      r2 and win0 == '3200 4000' and r3 and r4 and seen3 == '600 750' and win == '2400 3000' and seen4 == '600 750' and M2.grid == 600 and M2.detail == 750 and g2.G.GPS3D_DB.grid == 2400,
      f'the 3D window at its defaults {win0}; minimap draws at {seen3} / {seen4}, the 3D window at {win}')
saved2 = str(g2.G.SANDBOX_SAVE('GnomishPositioningSystemDB,GPS3D_DB'))
del g2
g3 = Game(saved2); g3.tick(3)
check('the minimap\'s detail kept over a reload (and shown on the settings page)',
      g3.mm.grid == 600 and g3.mm.detail == 750 and g3.control('GPS3D_MinimapGrid')['value'] == 600 and g3.control('GPS3D_MinimapBuildings')['value'] == 750,
      f'{g3.mm.grid} {g3.mm.detail}')
o1 = g3.slash('/gps minimap ground 900'); o2 = g3.slash('/gps minimap buildings 99999'); o3 = g3.slash('/gps minimap ground')
check('/gps minimap ground|buildings <n>: set at once (rounded to the slider\'s step, kept in range) and said; without a number the range and the value',
      g3.mm.grid == 1000 and g3.mm.detail == 4000 and g3.G.GPS3D_DB.minimapGrid == 1000 and 'ground detail: 1000' in o1 and 'building detail: 4000' in o2
      and 'now 1000' in o3 and '400 to 3200' in o3, f'{o1!r} {o2!r} {o3!r}')
del g3

# ---- fallback: instance, indoors, no terrain; and back
g.dungeon(); g.loading_screen(); g.tick(3)
inst = (not MM.active and g.ground() and not MM.host.IsShown(MM.host), str(MM.why))
g.goto('sw'); g.loading_screen(); g.tick(3)
back = MM.active and g.in_minimap() and not g.ground()
check('in an instance (no position): Blizzard\'s minimap by itself; GPS\'s again outside', inst[0] and back, inst[1])
g.L.execute('function IsInInstance() return true, "pvp" end')
g.at(1600, 1600, 489, 0, 'Warsong Gulch', ''); g.loading_screen(); g.tick(3)
bg = (not MM.active and g.ground(), str(MM.why))
g.L.execute('function IsInInstance() if SANDBOX.player.map == nil then return true, "party" end return false, "none" end')
g.goto('sw'); g.loading_screen(); g.tick(3)
check('in an instance where your position is known (a battleground): Blizzard\'s minimap', bg[0] and bg[1] == 'in an instance' and MM.active, bg[1])
g.L.execute('function IsIndoors() return true end')
G.SANDBOX_FIRE('ZONE_CHANGED_INDOORS'); g.tick(2)
ind = (not MM.active and g.ground(), str(MM.why))
g.L.execute('function IsIndoors() return false end')
G.SANDBOX_FIRE('ZONE_CHANGED_INDOORS'); g.tick(2)
check('indoors: Blizzard\'s minimap (it has the inside\'s layout); outside again GPS\'s', ind[0] and ind[1] == 'indoors' and MM.active, ind[1])
g.at(0, 0, 2991, 0, 'Somewhere', ''); g.tick(3)
nod = (not MM.active and g.ground(), str(MM.why))
g.goto('sw'); g.tick(3)
check('a map without GPS3D\'s terrain: Blizzard\'s minimap; back on a map with it', nod[0] and MM.active, nod[1])
G.Minimap.Hide(G.Minimap); g.tick(2)
hid = (not MM.active, str(MM.why))
G.Minimap.Show(G.Minimap); g.tick(2)
check('the minimap hidden (ToggleMinimap): GPS steps aside; shown again: back', hid[0] and MM.active, hid[1])

# ---- combat: nothing refused, works the same
G.SANDBOX_COMBAT(True); g.tick(2)
nb = len(S.blocked)
g.slash('/gps minimap off'); a1 = not MM.active and g.ground()
g.slash('/gps minimap on'); g.tick(2); a2 = MM.active
for k in range(10): g.at(-8830 + k, 640, 0, 2.3, 'Stormwind City', 'Trade District'); g.tick(1)
G.SANDBOX_COMBAT(False); g.tick(2)
check('combat: on, off and following work in combat, nothing refused', a1 and a2 and MM.active and len(S.blocked) == nb, f'blocked {list(S.blocked.values())[nb:] if hasattr(S.blocked, "values") else ""}')

# ---- safety: no Blizzard function or field replaced
blizz2 = str(G.SNAP_BLIZZ())
diff = [(x, y) for x, y in zip(blizz0.split('\n'), blizz2.split('\n')) if x != y]
ground_line = [d for d in diff if d[0].startswith('ground')]
rest = [d for d in diff if not d[0].startswith('ground') and not d[0].startswith('region')]
check('safety: no Blizzard function, script or field of Minimap, MinimapCluster, C_Minimap or the zoom buttons replaced or written while on (only the ground art switched off)',
      not rest and all('ground false' in d[1] for d in ground_line), str(rest[:3]))

# ---- data on demand: a fresh login at Stormwind with the minimap on loads the band near you
g3 = Game(saved)
loads = [str(v) for v in g3.G.SANDBOX.lodLoads.values()] if g3.G.SANDBOX.lodLoads else []
check("data on demand: the buildings' band near you loads for the minimap (the 3D window never opened), blocks raised in it",
      'GPS3D_EK3' in loads and g3.ns3.stats.detail > 0 and g3.mm.active and not g3.G.GPS3D_Frame.IsShown(g3.G.GPS3D_Frame), f'loaded {loads}, blocks {g3.ns3.stats.detail}')
# memory: the minimap on against off (Lua heap after a full collection), after walking 300 frames
for k in range(300): g3.at(-8830 + k * 0.5, 640 + k * 0.2, 0, 2.3, 'Stormwind City', 'Trade District'); g3.tick(1)
m_walk = g3.L.eval('function() collectgarbage("collect"); return collectgarbage("count") end')()
g3.slash('/gps minimap off'); g3.tick(2)
m_off = g3.L.eval('function() collectgarbage("collect"); return collectgarbage("count") end')()
MEM = (m_walk, m_off)
check('memory: walking 300 frames with the minimap on holds no more than a few MB over the minimap off (the meshes and decoded blocks it keeps)',
      m_walk - m_off < 8 * 1024, f'on after walking {m_walk / 1024:.1f} MB, then off {m_off / 1024:.1f} MB')
del g3

# ---- square minimaps (an addon's GetMinimapShape): no mask
g.slash('/gps minimap off'); g.L.execute('function GetMinimapShape() return "SQUARE" end'); g.slash('/gps minimap on'); g.tick(2)
shown, masked, _ = G.MASKSTATE()
check('a square minimap (an addon\'s GetMinimapShape() says SQUARE): no round mask', MM.active and shown > 0 and masked == 0, f'{masked} of {shown}')
g.L.execute('GetMinimapShape = nil')

g.chat()
check('no Lua errors', not errors, '; '.join(errors[:3]))
if not mutant:
    print('COST', json.dumps({k: [round(v, 3) if isinstance(v, float) else v for v in c] for k, c in COST.items()}), 'MEM', [round(m / 1024, 1) for m in MEM])
if mutant:
    failed = [name for name, ok in results if not ok]
    hit = any(mutant[5] in name for name in failed)
    print('MUTANT', 'caught' if hit else 'NOT caught', '| failed:', failed[:4]); sys.exit(0)
caught = 0
for i, m in enumerate(MUTANTS if not os.environ.get('NO_MUTANTS') else []):
    out = subprocess.run([sys.executable, os.path.abspath(__file__), '--mutant', str(i)], capture_output=True, text=True, timeout=3600).stdout
    c = 'MUTANT caught' in out; caught += c
    print(('     caught' if c else '     NOT caught'), m[0], '->', (out.strip().split('\n')[-1] if out.strip() else 'no output')[:220])
if not os.environ.get('NO_MUTANTS'):
    check(f'every mutation is caught by its own check ({len(MUTANTS)} mutations)', caught == len(MUTANTS), f'{caught} of {len(MUTANTS)}')
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
