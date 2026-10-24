# The ground grid's heights (raised city floor) over the shells' box, 257 x 257, for sh_floorimg.py. Run from tools/sandbox.
import os, sys, json, numpy as np
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
x0, x1, y0, y1, out = float(os.environ['X0']), float(os.environ['X1']), float(os.environ['Y0']), float(os.environ['Y1']), os.environ['OUT']
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
f = L.eval('function(ns, x0, x1, y0, y1, n) local o = {} for i = 0, n - 1 do for j = 0, n - 1 do o[#o + 1] = string.format("%.2f", ns.GroundHeight(x0 + (x1 - x0) * j / (n - 1), y1 - (y1 - y0) * i / (n - 1), 0) or -9999) end end return table.concat(o, ",") end')
H = np.array([float(v) for v in f(ns3, x0, x1, y0, y1, 257).split(',')]).reshape(257, 257)
np.save(out, H); print(H.min(), H.max(), (H < -9000).sum())
