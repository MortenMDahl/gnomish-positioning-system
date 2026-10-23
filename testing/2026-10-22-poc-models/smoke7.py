# Smoke test of the new city models: loads on demand near the city, draws, adaptive budget, defaults
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
errors = []
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
print('city data at login:', L.eval('function() return SANDBOX.namespaces.GPS3D.PocCityData ~= nil end')())
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; ns.Redraw()')
for i in range(30): g.tick(1)
st = ns3.poc.stats
print('status:', G.SlashCmdList.GPS3D('poc city') or '', str(L.eval('function() return SANDBOX.namespaces.GPS3D.poc.CityStatus() end')()))
print('stats parts', st.parts, 'buildings', st.buildings, 'on screen', st.onScreen, 'waiting', st.waiting, 'budget', st.budget, 'render ms', round(ns3.stats.ms, 1), 'detailTris (old blocks)', ns3.stats.detailTris)
print('loads:', [str(x) for x in (L.eval('function() local o = {} for k, v in pairs(SANDBOX.lodLoads or {}) do o[#o+1] = tostring(v) end return table.concat(o, ",") end')() or '').split(',')])
g.chat()
