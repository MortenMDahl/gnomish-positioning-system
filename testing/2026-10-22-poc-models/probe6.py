# Where the close view's time goes with the parts budget: the city's per-frame choice vs the rest of Render
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('poc city'); G.SlashCmdList.GPS3D('poc radius 400'); G.SlashCmdList.GPS3D('poc min 0')
L.execute('''local ns = SANDBOX.namespaces.GPS3D; local P = ns.poc; local f = P.CityFrame
  CITY_MS, CITY_N = 0, 0
  P.CityFrame = function(a, n, fr) local t0 = os.clock(); local r = f(a, n, fr); CITY_MS = CITY_MS + (os.clock() - t0) * 1000; CITY_N = CITY_N + 1; return r end''')
setcam = L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')
frame = L.eval('function(ns, dy) ns.cam.yaw = ns.cam.yaw + dy; local t0 = os.clock(); ns.Redraw(); return (os.clock() - t0) * 1000 end')
for b in ('4000', '8000'):
    G.SlashCmdList.GPS3D('poc budget ' + b)
    setcam(ns3, 0, 16426, -25896, 200, 25, 45)
    for _ in range(12): frame(ns3, 0)
    L.execute('CITY_MS, CITY_N = 0, 0')
    tot = sum(frame(ns3, 1.0) for _ in range(40))
    print('budget', b, 'frame ms', round(tot / 40, 1), 'of which the city choice', round(G.CITY_MS / G.CITY_N, 1), 'k', ns3.poc.stats.at200)
