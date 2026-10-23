# Lua memory (sandbox, Lua 5.4): after login, after the city's models are set up, after drawing the close view at
# 8,000 parts and after walking the view across the district (every building decoded once), and after 60 s unused
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
mem = L.eval('function() collectgarbage(); collectgarbage(); return collectgarbage("count") / 1024 end')
m0 = mem()
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('poc city'); G.SlashCmdList.GPS3D('poc budget 8000'); G.SlashCmdList.GPS3D('poc radius 400'); G.SlashCmdList.GPS3D('poc target 0')
m1 = mem()
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; ns.Redraw(); ns.Redraw()')
m2 = mem()
walk = L.eval('function(ns, x, y) local c = ns.cam; c.x, c.y, c.dist, c.pitch = x, y, 90, 40; ns.Redraw() end')
for i in range(-3, 4):
    for j in range(-3, 4):
        walk(ns3, 16426 + i * 70, -25896 + j * 70); g.tick(1)
m3 = mem()
G.SANDBOX_TICK(61, W, H); L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.cam.dist = 3000; ns.Redraw(); ns.Redraw()')
m4 = mem()
print(f'MEM login {m0:.1f} MB; city on {m1:.1f}; close view drawn {m2:.1f}; after walking the district {m3:.1f}; 60 s later, far away {m4:.1f}')
