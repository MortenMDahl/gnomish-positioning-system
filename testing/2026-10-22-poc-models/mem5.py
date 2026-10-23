# Lua memory: the game with GPS3D before and after the city models are built and drawn
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
mem = L.eval('function() collectgarbage(); collectgarbage(); return collectgarbage("count") / 1024 end')
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
m0 = mem()
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.PocData = nil')  # (the earlier test versions, not part of this)
m1 = mem(); saved = L.eval('function() local ns = SANDBOX.namespaces.GPS3D; local c = ns.PocCity; ns.PocCity = nil; collectgarbage(); collectgarbage(); local m = collectgarbage("count") / 1024; ns.PocCity = c; return m end'); mb = saved(); print(f'without any model data {mb:.0f} MB')
G.SlashCmdList.GPS3D('poc city'); m2 = mem()
G.SlashCmdList.GPS3D('poc budget 8000'); G.SlashCmdList.GPS3D('poc radius 70')
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; ns.Redraw(); ns.Redraw()')
m3 = mem()
print(f'all loaded {m0:.0f} MB; without the earlier test data {m1:.0f}; city cells built {m2:.0f}; drawn (8000 parts) {m3:.0f}')
