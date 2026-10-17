# Other addons' map layers on GPS's traditional map (Compat.lua), on Blizzard's REAL map canvas code
# (Blizzard_MapCanvas from the Forever UI source, set up as test_blizzard_canvas.py does). Blizzard's
# world map (WorldMapFrame) is built here the same way, with stand-ins of Blizzard's own layers,
# before GPS loads; then other addons add their layers to it as they do in the game:
#   HandyNotes-style  (a stand-in written for this test) added before GPS loads (found by the scan)
#   GatherMate2       (fixtures/gathermate2_standin.lua) added at login, after GPS (found by the hook)
#   a broken layer    whose RefreshAllData errors (must be switched off on GPS's map, quietly)
#   a pin library's   layer (HereBeDragons-Pins style: must be left alone)
# Real code here: MapCanvasMixin's AddDataProvider, AcquirePin (pools by template, OnLoad, OnAcquired,
# frame levels, mouse scripts), RemoveAllPinsByTemplate, SetMapID/OnMapChanged, RemoveDataProvider.
# Usage: WOWUI=/path/to/wow-ui-source python test_compat_canvas.py   (fill site/addons first)
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
NO_SECURE = '--no-issecurevariable' in sys.argv
src = open(os.path.join(HERE, 'test_blizzard_canvas.py')).read()
exec(src[:src.index('def toc_files(path):')])

# ---- what the game also has: template info, secure-variable owners, and Blizzard's world map ----
L.execute(r'''
local S = SANDBOX
nop = function() end -- (Blizzard_SharedXMLBase's EnvironmentUtil.lua, not loaded by the canvas test)
C_XMLUtil = { GetTemplateInfo = function(name) return { type = "Frame", width = 12, height = 12 } end }
-- issecurevariable: tables written by Blizzard's code are secure; an addon's are tainted by its name.
-- Stand-in: the test marks Blizzard's tables and names the addon of the others.
S.secureT, S.ownerT = {}, {}
issecurevariable = function(t, k)
	if S.secureT[t] then return true end
	return false, S.ownerT[t] or "UnknownAddon"
end
-- Blizzard's world map: a map canvas made like GPS's (the same real MapCanvasMixin), with stand-ins of
-- Blizzard's own layers (secure)
local f = CreateFrame("Frame", "WorldMapFrame", UIParent)
f:SetSize(1000, 700); f:SetPoint("CENTER")
Mixin(f, MapCanvasMixin)
local scroll = CreateFrame("ScrollFrame", nil, f, "MapCanvasFrameScrollContainerTemplate")
scroll:ClearAllPoints(); scroll:SetAllPoints(f)
f.ScrollContainer = scroll
f.BorderFrame = CreateFrame("Frame", nil, f)
f:OnLoad()
for _, s in ipairs({ "OnShow", "OnHide", "OnUpdate", "OnEvent" }) do f:SetScript(s, f[s]) end
for _, name in ipairs({ "QuestDataProviderMixin", "MapExplorationDataProviderMixin", "AreaLabelDataProviderMixin" }) do
	local p = CreateFromMixins(_G[name]); S.secureT[p] = true
	f:AddDataProvider(p)
end
f:GetPinFrameLevelsManager():AddFrameLevel("PIN_FRAME_LEVEL_AREA_POI")
f:GetPinFrameLevelsManager():AddFrameLevel("PIN_FRAME_LEVEL_HANDYNOTES_TEST", 3) -- a level an addon defined
f:Hide()
''')
if NO_SECURE:
    L.execute('issecurevariable = nil')

# ---- addons: HandyNotes-style (before GPS), the pin library's layer, a broken one ----
L.execute(r'''
local S = SANDBOX
HN_TEST = { refresh = 0, pins = 0 }
HNPinMixin = CreateFromMixins(MapCanvasPinMixin)
function HNPinMixin:OnLoad() self:UseFrameLevelType("PIN_FRAME_LEVEL_HANDYNOTES_TEST") end
function HNPinMixin:OnAcquired(plugin, x, y) self.pluginName = plugin; self:SetPosition(x, y); HN_TEST.pins = HN_TEST.pins + 1 end
S.xmlTemplates = S.xmlTemplates or {}
S.xmlTemplates.HNTestPinTemplate = function(fr) Mixin(fr, HNPinMixin); fr.texture = fr:CreateTexture(nil, "OVERLAY"); fr:Hide() end
HN_TEST.nodes = { Rares = { { 0.30, 0.40 }, { 0.55, 0.62 } } }
HN_TEST.provider = CreateFromMixins(MapCanvasDataProviderMixin)
local P = HN_TEST.provider
S.ownerT[P] = "HandyNotes"
function P:OnAdded(map) MapCanvasDataProviderMixin.OnAdded(self, map); self:RegisterEvent("QUEST_LOG_UPDATE") end -- (many layers listen to events)
function P:RemoveAllData() if self:GetMap() then self:GetMap():RemoveAllPinsByTemplate("HNTestPinTemplate") end end
function P:RefreshAllData() if not self:GetMap() then return end; self:RemoveAllData(); for plugin in pairs(HN_TEST.nodes) do self:RefreshPlugin(plugin) end end
function P:RefreshPlugin(plugin)
	local map = self:GetMap()
	HN_TEST.refresh = HN_TEST.refresh + 1
	for pin in map:EnumeratePinsByTemplate("HNTestPinTemplate") do if pin.pluginName == plugin then map:RemovePin(pin) end end
	if map:GetMapID() ~= 1429 then return end
	for _, xy in ipairs(HN_TEST.nodes[plugin]) do map:AcquirePin("HNTestPinTemplate", plugin, xy[1], xy[2]) end
end
WorldMapFrame:AddDataProvider(P)
''')
def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
# mutations (each run in its own process at the end): a broken rule in Compat.lua, and the check that must catch it
MUTATIONS = {
    'owner': (('if ok and not secure then return taint or "an addon" end', 'if ok then return taint or "an addon" end'), 'layers copied onto GPS'),
    'replay': (('if self ~= entry.original or entry.state ~= "on" then return end', 'do return end'), 'a new node'),
    'guard': (('return Finish(self, name, pcall(f, self, ...))', 'return f(self, ...)'), 'the broken layer'),
    'mapstate': (('if k ~= "owningMap" and k ~= "registeredEvents" and', 'if'), 'the copies belong to GPS'),
    'levels': (('if not to.definitions[name] and name ~= "PIN_FRAME_LEVEL_TOPMOST" then to:AddFrameLevel(name, def.range) end', ''), 'HandyNotes\'s pins too'),
}
MUT = os.environ.get('GPS_MUTATION')
for f in toc_files(os.path.join(HERE, '..', '..', 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc')):
    code = open(f'{SITE}/addons/GnomishPositioningSystem/{f}').read()
    if MUT and f == 'Compat.lua':
        old, new = MUTATIONS[MUT][0]
        assert code.count(old) == 1, old
        code = code.replace(old, new)
    if not G.SANDBOX_LOAD('GnomishPositioningSystem', f, code): print('LOAD FAILED', f)
G.SANDBOX_LOADED('GnomishPositioningSystem')
G.SlashCmdList.GPS('debug on')  # (from the start, to see every COMPAT line)
# GatherMate2 (stand-in) loads after GPS and adds its layer when enabled (at login), as Display:OnEnable does
G.SANDBOX_LOAD('GatherMate2', 'gathermate2_standin.lua', open(os.path.join(HERE, 'fixtures', 'gathermate2_standin.lua')).read())
L.execute(r'''
local S = SANDBOX
local GM = GM_STANDIN.GM
GM_STANDIN.AddNode(1429, "Mining", 201, 0.40, 0.50)
GM_STANDIN.AddNode(1429, "Mining", 299, 0.42, 0.52)   -- shown as 201 (replacement map)
GM_STANDIN.AddNode(1429, "Herb Gathering", 401, 0.60, 0.30)
GM_STANDIN.AddNode(1429, "Fishing", 501, 0.20, 0.20)  -- Fishing not shown (GatherMate2's own filter)
GM_STANDIN.AddNode(1436, "Mining", 202, 0.50, 0.50)   -- Westfall
S.ownerT[GM.modules.Display.WorldMapDataProvider] = "GatherMate2"
''')
G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
G.SANDBOX_FIRE('PLAYER_LOGIN')
L.execute(r'''
WorldMapFrame:AddDataProvider(GM_STANDIN.GM.modules.Display.WorldMapDataProvider)
-- a broken layer, and a pin library's layer
BROKEN = CreateFromMixins(MapCanvasDataProviderMixin)
SANDBOX.ownerT[BROKEN] = "BrokenAddon"
function BROKEN:RefreshAllData() error("BrokenAddon: something about WorldMapFrame") end
WorldMapFrame:AddDataProvider(BROKEN)
local lib = LibStub:NewLibrary("HereBeDragons-Pins-2.0")
lib.worldmapProvider = CreateFromMixins(MapCanvasDataProviderMixin)
SANDBOX.ownerT[lib.worldmapProvider] = "TomTom"
WorldMapFrame:AddDataProvider(lib.worldmapProvider)
''')
G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False)
W, H = 1280, 800
def tick(n=1):
    for _ in range(n): G.SANDBOX_TICK(1 / 30, W, H)
tick(3)
errors = []
def chat():
    c = str(G.SANDBOX_CHAT() or '')
    if c:
        print('CHAT>', c.replace('\n', '\nCHAT> ')[:3000])
        errors.extend(l for l in c.split('\n') if 'Lua error' in l)
    return c
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
ns = G.SANDBOX.namespaces['GnomishPositioningSystem']
C = ns.compat
mw = ns.mapWindow
G.SANDBOX_SLASH('/gps map'); tick(10); chat()
m = mw.map
WM = G.WorldMapFrame
GMP = G.GM_STANDIN.GM.modules.Display.WorldMapDataProvider
HNP = G.HN_TEST.provider
same = L.eval('function(a, b) return rawequal(a, b) end')
def copies():
    out = {}
    for p in m.dataProviders.keys():
        orig = p.gpsOriginal
        if orig is not None:
            out[str(C.layers[orig].owner)] = p
    return out
def pins(template):
    pool = m.pinPools[template]
    return [p for p in pool.active.keys()] if pool is not None else []

cp = copies()
if NO_SECURE:
    # without issecurevariable: layers on Blizzard's map before GPS loaded count as Blizzard's
    check('without issecurevariable: GatherMate2 (added after GPS loaded) copied; HandyNotes (added before) taken for Blizzard\'s and not copied; Blizzard\'s not copied', set(cp) == {'an addon'} and len(cp) == 1 and same(cp['an addon'].gpsOriginal, GMP), str(set(cp)))
    print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed'); sys.exit(0)

check('layers copied onto GPS\'s map: GatherMate2 (added after GPS, by the hook) and HandyNotes (added before, by the scan); not Blizzard\'s own, not the pin library\'s', set(cp) == {'GatherMate2', 'HandyNotes'}, str(sorted(cp)))
blizz_on_gps = [p for p in m.dataProviders.keys() if p.gpsOriginal is None and p._name in ('QuestDataProviderMixin',) and not same(p.owningMap, m)]
check('the copies belong to GPS\'s map, with their own event registrations; the originals still to Blizzard\'s (Blizzard\'s map untouched: same layers, nothing added)',
      same(cp['GatherMate2'].owningMap, m) and same(GMP.owningMap, WM) and same(HNP.owningMap, WM) and sum(1 for _ in WM.dataProviders.keys()) == 3 + 4
      and cp['HandyNotes'].registeredEvents is not None and not same(cp['HandyNotes'].registeredEvents, HNP.registeredEvents) and m.dataProviderEventsCount['QUEST_LOG_UPDATE'] == 1 and WM.dataProviderEventsCount['QUEST_LOG_UPDATE'] == 1)
tl = C.layers[G.LibStub('HereBeDragons-Pins-2.0').worldmapProvider]
check('the pin library\'s layer (TomTom via HereBeDragons-Pins) is left on Blizzard\'s map, with the reason', tl.state == 'skipped' and 'HereBeDragons-Pins' in str(tl.why), f'{tl.state}: {tl.why}')
bl = C.layers[G.BROKEN]
check('the broken layer was copied, failed on GPS\'s map and was switched off (quietly: no Lua error), the reason kept', bl.state == 'failed' and 'something about WorldMapFrame' in str(bl.why) and not any(same(p, bl.copy) for p in m.dataProviders.keys()), f'{bl.state}: {str(bl.why)[:80]}')

gm = pins('GatherMate2WorldMapPinTemplate')
lm = m.GetPinFrameLevelsManager(m)
poi = lm.GetValidFrameLevel(lm, 'PIN_FRAME_LEVEL_AREA_POI')
canvas = m.GetCanvas(m)
pos = sorted((round(p.normalizedX, 4), round(p.normalizedY, 4), str(p.title)) for p in gm)
check('GatherMate2 draws its own pins on GPS\'s map (real AcquirePin with its template): Elwynn\'s 3 visible nodes, at their zone coordinates, named (old node ID shown as the new one), Fishing filtered by GatherMate2',
      pos == [(0.4, 0.5, 'Copper Vein'), (0.42, 0.52, 'Copper Vein'), (0.6, 0.3, 'Peacebloom')], str(pos))
check('its pins: parented to GPS\'s canvas, at the area-POI level of GPS\'s map, owned by GPS\'s map, textured',
      all(same(p.GetParent(p), canvas) and p.GetFrameLevel(p) == poi and same(p.owningMap, m) and p.texture._file for p in gm), f'level {gm[0].GetFrameLevel(gm[0]) if gm else None} vs {poi}')
hn = pins('HNTestPinTemplate')
hl = lm.GetValidFrameLevel(lm, 'PIN_FRAME_LEVEL_HANDYNOTES_TEST')
check('HandyNotes\'s pins too, at the frame level it defined on Blizzard\'s map (copied to GPS\'s)', len(hn) == 2 and 'PIN_FRAME_LEVEL_HANDYNOTES_TEST' in [k for k in lm.definitions.keys()] and all(p.GetFrameLevel(p) == hl for p in hn), f'{len(hn)} pins at {hn[0].GetFrameLevel(hn[0]) if hn else None} (level {hl})')
check('Blizzard\'s map has no pins of theirs (it is closed; nothing was drawn there by GPS)', WM.pinPools['GatherMate2WorldMapPinTemplate'] is None or WM.pinPools['GatherMate2WorldMapPinTemplate'].GetNumActive(WM.pinPools['GatherMate2WorldMapPinTemplate']) == 0)

# hover and right-click through the real map canvas scripts
p0 = gm[0]
p0._scripts.OnEnter(p0); tip = [str(x) for x in G.GameTooltip.GetLines(G.GameTooltip).values()]
p0._scripts.OnLeave(p0)
p0._scripts.OnMouseUp(p0, 'RightButton', True)
click = G.GM_STANDIN.calls.click
check('hover and right-click reach GatherMate2\'s own handlers (tooltip with the node; its click with the pin\'s zone and coords)',
      int(G.GM_STANDIN.calls.enter) == 1 and tip and tip[0] in ('Copper Vein', 'Peacebloom') and len(click) == 1 and click[1].button == 'RightButton' and click[1].zone == 1429 and click[1].worldmap,
      f'{tip}; click {len(click)}')

# data changes: GatherMate2 updates its world map; HandyNotes refreshes one plugin
G.GM_STANDIN.AddNode(1429, 'Herb Gathering', 402, 0.70, 0.70)
G.GM_STANDIN.GM.modules.Display.UpdateWorldMap(G.GM_STANDIN.GM.modules.Display); tick(2)
n_gm = len(pins('GatherMate2WorldMapPinTemplate'))
L.execute('table.insert(HN_TEST.nodes.Rares, { 0.10, 0.90 })')
r0 = int(G.HN_TEST.refresh)
HNP.RefreshPlugin(HNP, 'Rares'); tick(2)
n_hn = len(pins('HNTestPinTemplate'))
check('a new node: GatherMate2\'s update of its own map reaches the copy (4 pins); HandyNotes\'s RefreshPlugin on its original is replayed on the copy (3 pins)', n_gm == 4 and n_hn == 3 and int(G.HN_TEST.refresh) == r0 + 2, f'GatherMate2 {n_gm}, HandyNotes {n_hn}, refreshes {int(G.HN_TEST.refresh) - r0}')
# another map
mw.SetMap(1436); tick(5)
gm_w, hn_w = pins('GatherMate2WorldMapPinTemplate'), pins('HNTestPinTemplate')
check('another map (Westfall, real SetMapID -> OnMapChanged -> RefreshAllData): its node, none of Elwynn\'s', len(gm_w) == 1 and str(gm_w[0].title) == 'Tin Vein' and len(hn_w) == 0)
mw.SetMap(1429); tick(5)
# the setting
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'false'); tick(2)
off = (len(pins('GatherMate2WorldMapPinTemplate')), len(pins('HNTestPinTemplate')), sum(1 for p in m.dataProviders.keys() if p.gpsOriginal is not None))
G.SANDBOX_SETTING_SET('GPS_AddonMarkers', 'true'); tick(2)
on = (len(pins('GatherMate2WorldMapPinTemplate')), len(pins('HNTestPinTemplate')), sum(1 for p in m.dataProviders.keys() if p.gpsOriginal is not None))
check('setting off: the copies leave GPS\'s map with their pins; on: back, drawn again', off == (0, 0, 0) and on == (4, 3, 2), f'off {off}, on {on}')
# removal on Blizzard's map
WM.RemoveDataProvider(WM, HNP); tick(2)
check('HandyNotes removes its layer from Blizzard\'s map: its copy leaves GPS\'s map, pins released', len(pins('HNTestPinTemplate')) == 0 and C.layers[HNP].state == 'removed' and not any(same(p.gpsOriginal, HNP) for p in m.dataProviders.keys()))
WM.AddDataProvider(WM, HNP); tick(2)
check('HandyNotes puts its layer back (switched off and on): its copy is back on GPS\'s map with its pins', len(pins('HNTestPinTemplate')) == 3 and C.layers[HNP].state == 'on')
# hide and show
G.GPS_WorldMapFrame.Hide(G.GPS_WorldMapFrame); tick(2); G.GPS_WorldMapFrame.Show(G.GPS_WorldMapFrame); tick(5)
check('hide and show GPS\'s map (real OnHide / OnShow refresh the copies)', len(pins('GatherMate2WorldMapPinTemplate')) == 4)
# self-test and log
G.SlashCmdList.GPS('test'); tick(5)
out = chat()
line = [l for l in out.split('\n') if 'other addons: map layers' in l]
check('/gps test: the layers on the traditional map and those not copied, with why', line and 'GatherMate2' in line[0] and 'HandyNotes' in line[0] and 'TomTom (skipped' in line[0] and 'BrokenAddon (failed' in line[0], line[0] if line else out[-300:])
logl = [str(l) for l in G.GnomishPositioningSystemLog.lines.values() if ' COMPAT ' in str(l)]
check('debug log COMPAT lines: found, copied, left alone, switched off, removed, back', any('copied to the traditional map' in l for l in logl) and any('left on Blizzard' in l for l in logl) and any('switched off' in l for l in logl) and any('removed from Blizzard' in l for l in logl) and any('back on the traditional map' in l for l in logl), f'{len(logl)} lines')
check('no Lua errors', not errors, '; '.join(errors[:2]))
import subprocess
if not MUT and not NO_SECURE:
    for name, (_, target) in MUTATIONS.items():
        r = subprocess.run([sys.executable, __file__], capture_output=True, text=True, env={**os.environ, 'GPS_MUTATION': name})
        failed = [l for l in r.stdout.splitlines() if l.startswith('FAIL')]
        crashed = 'Traceback' in r.stdout + r.stderr
        check(f'mutation "{name}" is caught by "{target}"', any(target in l for l in failed) or (crashed and not failed),
              (f'{len(failed)} failed: ' + '; '.join(l[5:70] for l in failed[:2])) if failed else ('crashed: ' + (r.stdout + r.stderr).strip().splitlines()[-1][:120] if crashed else 'nothing failed'))
# the same without issecurevariable (another run of this file)
r = subprocess.run([sys.executable, __file__, '--no-issecurevariable'], capture_output=True, text=True, env=os.environ)
ok = [l for l in r.stdout.splitlines() if l.startswith('PASS') or l.startswith('FAIL')]
check('without issecurevariable (a client that lacks it): only layers added after GPS loaded are copied', ok and all(l.startswith('PASS') for l in ok), ' | '.join(l[:140] for l in ok) or r.stdout[-400:] + r.stderr[-400:])
print(f'{sum(ok for _, ok in results)} of {len(results)} checks passed')
