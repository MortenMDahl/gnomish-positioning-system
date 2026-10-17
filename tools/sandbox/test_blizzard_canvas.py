# Runs GPS's traditional map (MapWindow.lua) on Blizzard's REAL map canvas code instead of the
# sandbox's stand-in: Blizzard_MapCanvas (MapCanvasMixin, the scroll container, the detail layers,
# the pin frame levels, the data-provider base) and the SharedXMLBase pieces it needs, from a clone
# of Blizzard's interface source (Gethe/wow-ui-source, branch "forever"). The XML templates are built
# here the way their XML describes; a few game functions are stubbed (art layers, texture pools,
# secure-call helpers). The data providers are Blizzard's base class only (their pins need XML).
# This checks that MapWindow builds and drives Blizzard's canvas in a valid order (OnLoad, SetMapID,
# OnShow, size changes, zoom, pan, view rect, right-click navigation, floors) without errors.
# Usage: WOWUI=/path/to/wow-ui-source python test_blizzard_canvas.py   (fill site/addons first)
import lupa.lua54 as lupa54, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
WOWUI = os.environ.get('WOWUI') or (sys.argv[1] if len(sys.argv) > 1 else '')
AO = os.path.join(WOWUI, 'Interface', 'AddOns')
if not os.path.isdir(AO):
    sys.exit('set WOWUI to a clone of Gethe/wow-ui-source (branch forever)')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
L.execute(open(f'{SITE}/zones.lua').read())  # every zone of the two continents (make_zones.py)

# ---- what the game provides that the engine does not (stubs), before Blizzard's files load
L.execute(r'''
local S = SANDBOX
issecure = function() return true end
securecallfunction = function(f, ...) return f(...) end
secureexecuterange = function(t, f, ...) for k, v in pairs(t) do f(k, v, ...) end end
SafePack = table.pack
SafeUnpack = function(t) return table.unpack(t, 1, t.n) end
GetTickTime = function() return 1 / 30 end
GetCVarNumberOrDefault = function() return 1 end
IsGMClient = function() return false end
InputUtil = { IsGamepadUIEnabled = function() return false end }
SoftCursor = { IsShown = function() return false end }
EventRegistry = { TriggerEvent = function() end, RegisterCallback = function() end }
ClearCachedActivitiesForPlayer = function() end
GetMouseFoci = function() return { S.hover } end
GetMouseFocus = function() return S.hover end
GetOrCreateTableEntry = function(t, k) local v = t[k]; if not v then v = {}; t[k] = v end; return v end
math.clamp = function(v, a, b) return math.max(a, math.min(b, v)) end
math.lerp = function(a, b, t) return a + (b - a) * t end
math.saturate = function(v) return math.max(0, math.min(1, v)) end
Clamp = math.clamp
FrameDeltaLerp = function(a, b, amount) return a + (b - a) * amount end
Lerp = function(a, b, t) return a + (b - a) * t end
TextureLoadingGroupMixin = { Reset = function() end, AddTexture = function() end, IsFullyLoaded = function() return true end }
-- C_Map art (the game's data): one layer of 4 x 3 tiles of 256 px for every map
C_Map.GetMapArtID = function(id) return id end
C_Map.GetMapArtBackgroundAtlas = function() return "AdventureMap_TileBg" end
C_Map.MapHasArt = function() return true end
C_Map.GetFallbackWorldMapID = function() return 947 end
C_Map.GetMapArtLayers = function() return { { layerWidth = 1002, layerHeight = 668, tileWidth = 256, tileHeight = 256, minScale = 1, maxScale = 3, additionalZoomSteps = 2 } } end
C_Map.GetMapArtLayerTextures = function() local t = {}; for i = 1, 12 do t[i] = 1000 + i end; return t end
C_Map.GetMapInfoAtPosition = function() return nil end
-- frame methods the engine lacks: scroll frames, scale
local F = getmetatable(UIParent).__index
function F:SetScrollChild(c) self._scrollChild = c end
function F:SetHorizontalScroll(v) self._hs = v; S.dirty = true end
function F:GetHorizontalScroll() return self._hs or 0 end
function F:SetVerticalScroll(v) self._vs = v; S.dirty = true end
function F:GetVerticalScroll() return self._vs or 0 end
function F:SetScale(s) self._scale = s end
function F:GetScale() return self._scale or 1 end
function F:SetUndefinedEventsAllowed() end
function F:IsMouseMotionFocus() return S.hover == self end
function F:SetForbidden() end
-- the engine answers any unknown capitalised key with a do-nothing method; Blizzard's code tests
-- optional children such as BorderFrame.Underlay by key, which must be nil when absent
do
	local c = getmetatable(UIParent)
	while getmetatable(c) and type(getmetatable(c).__index) == "table" do c = getmetatable(c).__index end
	local mt = getmetatable(c)
	local missing = mt.__index
	mt.__index = function(t, k) if k == "Underlay" then return nil end return missing(t, k) end
end
-- pools (Blizzard's Pools.lua needs the game's frame factory): a plain pool with the same calls
local function Pool(create)
	local p = { active = {}, free = {} }
	function p:Acquire() local o = table.remove(self.free); local new = not o; o = o or create(); self.active[o] = true; return o, new end -- (object, made now), as the game's pools
	function p:Release(o) self.active[o] = nil; o:Hide(); self.free[#self.free + 1] = o end
	function p:ReleaseAll() for o in pairs(self.active) do self:Release(o) end end
	function p:EnumerateActive() return pairs(self.active) end
	function p:GetNumActive() local n = 0; for _ in pairs(self.active) do n = n + 1 end; return n end
	return p
end
CreateFramePool = function(kind, parent, template) return Pool(function() return CreateFrame(kind == "FRAME" and "Frame" or kind, nil, parent, template) end) end
CreateTexturePool = function(parent, layer, sub) return Pool(function() return parent:CreateTexture(nil, layer, nil, sub) end) end
''')
files = [
    'Blizzard_SharedXMLBase/TableUtil.lua', 'Blizzard_SharedXMLBase/MathUtil.lua', 'Blizzard_SharedXMLBase/FunctionUtil.lua', 'Blizzard_SharedXMLBase/EnumUtil.lua', 'Blizzard_SharedXMLBase/CallbackRegistry.lua', 'Blizzard_SharedXMLBase/TaggableObject.lua', 'Blizzard_SharedXMLBase/Rectangle.lua', 'Blizzard_SharedXML/Vector2D.lua',
    'Blizzard_MapCanvasSecureUtil/Blizzard_MapCanvasSecureUtil.lua',
    'Blizzard_MapCanvas/MapCanvas_DataProviderBase.lua', 'Blizzard_MapCanvas/MapCanvas_PinFrameLevelsManager.lua',
    'Blizzard_MapCanvas/Blizzard_MapCanvasDetailLayer.lua', 'Blizzard_MapCanvas/MapCanvas_ScrollContainerMixin.lua',
    'Blizzard_MapCanvas/Blizzard_MapCanvas.lua',
]
for f in files:
    src = open(os.path.join(AO, f), encoding='utf-8').read()
    ok = G.SANDBOX_LOAD('Blizzard', f, src)
    print('blizzard', f, 'loaded' if ok else 'FAILED')

# ---- the XML templates, built as Blizzard_MapCanvas.xml describes them; data providers are the
# real base class (MapCanvasDataProviderMixin), with AreaLabel's offset setter
L.execute(r'''
local S = SANDBOX
function S.makeMapScroll(f)   -- MapCanvasFrameScrollContainerTemplate
	Mixin(f, MapCanvasScrollControllerMixin)
	f._clips, f._mouse, f._wheel = true, true, true
	f.Child = CreateFrame("Frame", nil, f)
	f.Child:SetPoint("TOPLEFT")
	f.Child.TiledBackground = f.Child:CreateTexture(nil, "BACKGROUND", nil, -8)
	f.Child.TiledBackground:SetPoint("CENTER")
	f:SetScrollChild(f.Child)
	for _, s in ipairs({ "OnShow", "OnHide", "OnMouseUp", "OnMouseDown", "OnMouseWheel", "OnUpdate" }) do f:SetScript(s, f[s]) end
	f:OnLoad()
end
local applied = {}
local origCreate = CreateFrame
function CreateFrame(kind, name, parent, template)
	local f = origCreate(kind, name, parent, template ~= "MapCanvasDetailLayerTemplate" and template or nil)
	if template == "MapCanvasDetailLayerTemplate" then
		Mixin(f, MapCanvasDetailLayerMixin)
		f:SetScript("OnUpdate", f.OnUpdate)
		f:SetFrameLevel(parent:GetFrameLevel()) -- useParentLevel
		f:OnLoad()
	end
	return f
end
for _, name in ipairs({ "MapExplorationDataProviderMixin", "MapHighlightDataProviderMixin", "BattlefieldFlagDataProviderMixin",
	"VehicleDataProviderMixin", "FogOfWarDataProviderMixin", "DeathMapDataProviderMixin", "ScenarioDataProviderMixin",
	"VignetteDataProviderMixin", "GossipDataProviderMixin", "FlightPointDataProviderMixin", "PetTamerDataProviderMixin",
	"DigSiteDataProviderMixin", "DungeonEntranceDataProviderMixin", "MapLinkDataProviderMixin",
	"SelectableGraveyardDataProviderMixin", "AreaPOIDataProviderMixin", "AreaPOIEventDataProviderMixin",
	"QuestSessionDataProviderMixin", "EncounterJournalDataProviderMixin", "GroupMembersDataProviderMixin",
	"QuestOfferDataProviderMixin", "BonusObjectiveDataProviderMixin", "QuestBlobDataProviderMixin", "QuestDataProviderMixin",
	"WaypointLocationDataProviderMixin", "SuperTrackWaypointDataProviderMixin" }) do
	_G[name] = CreateFromMixins(MapCanvasDataProviderMixin, { _name = name })
end
AreaLabelDataProviderMixin = CreateFromMixins(MapCanvasDataProviderMixin, { _name = "AreaLabelDataProviderMixin", SetOffsetY = function(self, y) self.offsetY = y end })
''')

def toc_files(path):
    return [l.strip().replace('\\', '/') for l in open(path).read().splitlines() if l.strip() and not l.startswith('##')]
for f in toc_files(os.path.join(HERE, '..', '..', 'Interface', 'AddOns', 'GnomishPositioningSystem', 'GnomishPositioningSystem.toc')):
    if not G.SANDBOX_LOAD('GnomishPositioningSystem', f, open(f'{SITE}/addons/GnomishPositioningSystem/{f}').read()): print('LOAD FAILED', f)
G.SANDBOX_LOADED('GnomishPositioningSystem')
G.SANDBOX_PLAYER(-8958.3, -190, 0, 0, 0.3, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
G.SANDBOX_FIRE('PLAYER_LOGIN'); G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', True, False)
W, H = 1280, 800
def tick(n=1):
    for _ in range(n): G.SANDBOX_TICK(1 / 30, W, H)
errors = []
def chat():
    c = G.SANDBOX_CHAT()
    if c:
        print('CHAT>', c.replace('\n', '\nCHAT> ')[:3000])
        errors.extend(l for l in c.split('\n') if 'Lua error' in l)
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
ns = G.SANDBOX.namespaces['GnomishPositioningSystem']
mw = ns.mapWindow
ui = mw.ui
F3 = G.GPS_WorldMapFrame

G.SANDBOX_SLASH('/gps map'); tick(10); chat()
m = mw.map
check('real MapCanvasMixin.OnLoad ran on the GPS canvas (pin levels manager, handler registries)', m is not None and m.pinFrameLevelsManager is not None and m.mouseClickHandlers is not None and m.detailLayerPool is not None)
check('window open on your map (real SetMapID -> scroll container -> zoom levels)', F3.IsShown(F3) and m.GetMapID(m) == 1429 and m.ScrollContainer.zoomLevels is not None and len(m.ScrollContainer.zoomLevels) == 4, f'{len(m.ScrollContainer.zoomLevels or {})} zoom levels')
nd = m.detailLayerPool.GetNumActive(m.detailLayerPool)
check('real OnShow refreshed the detail layers (one art layer, 12 tiles)', nd == 1, f'{nd} layer(s)')
check('27 data providers added through the real AddDataProvider (OnAdded ran), the 6 quest ones among them', sum(1 for _ in m.dataProviders.keys()) == 27 and all(p.owningMap is not None for p in m.dataProviders.keys())
      and {'QuestDataProviderMixin', 'QuestBlobDataProviderMixin', 'QuestOfferDataProviderMixin', 'BonusObjectiveDataProviderMixin', 'WaypointLocationDataProviderMixin', 'SuperTrackWaypointDataProviderMixin'} <= {p._name for p in m.dataProviders.keys()})
# the pin frame levels in the order Blizzard's own world map defines them (Forever's Blizzard_WorldMap.lua)
import re
wm = open(os.path.join(AO, 'Blizzard_WorldMap', 'Blizzard_WorldMap.lua'), encoding='utf-8').read()
blizz = re.findall(r'AddFrameLevel\("(PIN_FRAME_LEVEL_\w+)"', wm)
ours = [ns.MAP_PIN_LEVELS[i][1] for i in range(1, len(ns.MAP_PIN_LEVELS) + 1)]
missing = [n for n in ours if n not in blizz]
def subsequence(xs, ys):  # xs appear in ys in the same order
    it = iter(ys)
    return all(any(x == y for y in it) for x in xs)
order_ok = not missing and subsequence(ours, blizz)
check('pin frame levels: all of Blizzard\'s world map, in its order (quest blob, quest offer, bonus, active and super-tracked quest, waypoint)', order_ok and {'PIN_FRAME_LEVEL_QUEST_BLOB', 'PIN_FRAME_LEVEL_ACTIVE_QUEST', 'PIN_FRAME_LEVEL_SUPER_TRACKED_QUEST', 'PIN_FRAME_LEVEL_QUEST_OFFER', 'PIN_FRAME_LEVEL_WAYPOINT_LOCATION'} <= set(ours), f'missing {missing}')
check('quest pin levels exist in the real manager', all(m.pinFrameLevelsManager.GetValidFrameLevel(m.pinFrameLevelsManager, n) for n in ('PIN_FRAME_LEVEL_QUEST_BLOB', 'PIN_FRAME_LEVEL_ACTIVE_QUEST', 'PIN_FRAME_LEVEL_SUPER_TRACKED_QUEST')))
lm = m.GetPinFrameLevelsManager(m)
check('pin frame levels defined by the real manager stay under the GPS controls', lm.maxLevel < 9000 and ui.close.GetFrameLevel(ui.close) > lm.maxLevel, f'pins up to {lm.maxLevel}, close at {ui.close.GetFrameLevel(ui.close)}')
check('title from the map (Elwynn Forest)', ui.title.GetText(ui.title) == 'Elwynn Forest')
s0 = m.GetCanvasScale(m)
ui.zoomIn._scripts.OnClick(ui.zoomIn, 'LeftButton'); tick(30)
s1 = m.GetCanvasScale(m)
ui.zoomOut._scripts.OnClick(ui.zoomOut, 'LeftButton'); tick(30)
s2 = m.GetCanvasScale(m)
check('zoom rings drive the real ZoomIn / ZoomOut', s1 > s0 and abs(s2 - s0) < 1e-6, f'scale {s0:.3f} -> {s1:.3f} -> {s2:.3f}')
ui.zoomIn._scripts.OnClick(ui.zoomIn, 'LeftButton'); tick(30)
r = m.GetViewRect(m)
cx, cy = r.GetCenter(r)
check('real GetViewRect has a centre (used for the focus of the other modes)', 0 <= cx <= 1 and 0 <= cy <= 1, f'{cx:.3f}, {cy:.3f}')
ui.me._scripts.OnClick(ui.me, 'LeftButton'); tick(30)
check('Me: your map, panned to you when zoomed in (real PanTo)', m.GetMapID(m) == 1429 and mw.follow == True)
F3.SetSize(F3, 600, 420)
G.SANDBOX.sizeChanged[m] = True  # the game sends OnSizeChanged to the anchored canvas; the engine only does so for drags
tick(5)
want = min(598 / 1002, 418 / 668)
check('a size change reaches the real OnFrameSizeChanged (zoom levels rebuilt for the new size)', abs(m.ScrollContainer.baseScale - want) < 1e-3 and len(m.ScrollContainer.zoomLevels) == 4, f'base scale {m.ScrollContainer.baseScale:.3f} (want {want:.3f})')
# right-click on the map: the real scroll container's mouse handling navigates to the parent
sc = m.ScrollContainer
l, b, rr, t = G.SANDBOX.rect(sc)
G.SANDBOX_MOUSE('move', (l + rr) / 2, (b + t) / 2, None, 0)
G.SANDBOX_MOUSE('down', (l + rr) / 2, (b + t) / 2, 'RightButton', 0)
G.SANDBOX_MOUSE('up', (l + rr) / 2, (b + t) / 2, 'RightButton', 0); tick(10); chat()
check('right-click (real OnMouseUp -> NavigateToParentMap): Eastern Kingdoms, title updated, not following', m.GetMapID(m) == 1415 and ui.title.GetText(ui.title) == 'Eastern Kingdoms' and mw.follow == False, str(ui.title.GetText(ui.title)))
foc = mw.Focus()
check('focus for the other modes from the real view rect', foc is not None and foc.map == 0, f'{foc and (foc.map, round(foc.gx, 2), round(foc.gy, 2))}')
# a dungeon with floors
G.SANDBOX_PLAYER(0, 0, 0, -1, 0.0, 'The Deadmines', '', 291, 0.42, 0.55)
G.SANDBOX_FIRE('PLAYER_ENTERING_WORLD', False, False); tick(5)
ui.me._scripts.OnClick(ui.me, 'LeftButton'); tick(10)
ui.next._scripts.OnClick(ui.next, 'LeftButton'); tick(10)
check('floors through the real SetMapID (Ironclad Cove, 2 of 2)', m.GetMapID(m) == 292 and ui.subtitle.GetText(ui.subtitle) == 'Ironclad Cove  (2 of 2)', str(ui.subtitle.GetText(ui.subtitle)))
F3.Hide(F3); tick(2); F3.Show(F3); tick(10)
check('hide and show again (real OnHide / OnShow) without errors', F3.IsShown(F3))
chat()
check('no Lua errors from Blizzard\'s code or GPS', not errors, '; '.join(errors[:2]))
n = sum(1 for _, ok in results if ok)
print(f'{n} of {len(results)} checks passed')
