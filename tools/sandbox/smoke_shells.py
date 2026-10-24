# (proof of concept S1) smoke run of the building shells in the lupa sandbox: Stormwind views, shells on, old blocks off
import os, sys, json, statistics
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
VIEWS = {'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62), 'far': (16426, -25896, 2000, 25, 50)}
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on')
for vk, (x, y, d, yaw, pitch) in VIEWS.items():
    L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')(ns3, 0, x, y, d, yaw, pitch)
    for _ in range(30): L.eval("function(ns) ns.Redraw() end")(ns3); g.tick(1)
    print(vk, L.eval('function(ns) return ns.shells.Status() end')(ns3), 'shown', L.eval('function(ns) return ns.stats.shown end')(ns3))
