# Adaptive budget and on-demand loading checks (sandbox):
#  1. login far from Stormwind (Goldshire): the city's data not loaded; the camera glides towards the city: where it loads
#  2. close Stormwind view, target 10 ms: 60 frames turning 1 degree a frame, then standing still (the driver's redraws)
import os, sys, statistics
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
errors = []
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-10500, 1000, 0, 0, 'Westfall', ''); g.tick(2)
G.SlashCmdList.GPS('3d'); g.tick(5)
loaded = L.eval('function() return C_AddOns.IsAddOnLoaded("GPS3D_City_Stormwind") end')
print('1. in Westfall, 3D open (view at', [round(v) for v in L.eval('function() local c = SANDBOX.namespaces.GPS3D.cam; return c.x, c.y end')()], '): city data loaded?', bool(loaded()))
glide = L.eval('function(ns, x, y) local c = ns.cam; ns.SetCamMode("free"); c.map = 0; c.x, c.y = x, y; ns.Redraw() end')
box = (16164.2, 16687.3, -26163.0, -25635.6)
x0, y0 = L.eval('function() local c = SANDBOX.namespaces.GPS3D.cam; return c.x, c.y end')()
at = None
for i in range(101):
    x = x0 + (16426 - x0) * i / 100; y = y0 + (-25896 - y0) * i / 100
    glide(ns3, x, y)
    if loaded() and at is None:
        dx = max(box[0] - x, 0, x - box[1]); dy = max(box[2] - y, 0, y - box[3]); at = (dx * dx + dy * dy) ** 0.5
print('   gliding towards Stormwind: loaded when the view was', None if at is None else round(at), 'yd from the city box (LOAD_NEAR 600)')
print('   /gps3d test lists it:', 'GPS3D_City_Stormwind' in str(L.eval('function() return table.concat(SANDBOX.namespaces.GPS3D.dataState.names, ",") end')()))
G.SlashCmdList.GPS3D('poc target 10'); G.SlashCmdList.GPS3D('poc budget 8000')
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetTopDown(false, true); local c = ns.cam; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; ns.Redraw()')
for _ in range(20): g.tick(1)
frame = L.eval('function(ns, dy) ns.cam.yaw = ns.cam.yaw + dy; ns.Redraw(); return ns.stats.ms, ns.poc.stats.budget, ns.poc.stats.parts end')
turn = [frame(ns3, 1.0) for _ in range(60)]
print('2. turning 1 deg/frame, last 30 frames: Render ms median', round(statistics.median(t[0] for t in turn[30:]), 1), 'range', round(min(t[0] for t in turn[30:]), 1), '-', round(max(t[0] for t in turn[30:]), 1), '; budget median', int(statistics.median(t[1] for t in turn[30:])))
# standing still: the driver frame redraws while the budget still rises
bud = []
for _ in range(60):
    g.tick(1); bud.append((ns3.poc.stats.budget, ns3.stats.ms))
print('   standing still 60 frames: budget', int(turn[-1][1]), '->', int(bud[-1][0]), '(slider 8000); last Render ms', round(bud[-1][1], 1), '; redraws stopped:', bud[-1][0] == bud[-5][0])
