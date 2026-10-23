# (proof of concept, perf_poc5) native-Lua cost of the game's own models with distance-based detail (/gps3d poc city, min <n>) vs today at fixed views: Render's Lua ms and the texture calls
# the game would make (SetVertexOffset, SetDrawLayer, Show ...) per frame, turning 1 degree a frame and standing still
import os, sys, json, statistics
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
errors = []
VIEWS0 = {('sw', 'high'): (0, 16400, -25880, 420, 25, 62, (-8830, 640)), ('sw', 'close'): (0, 16426, -25896, 200, 25, 45, (-8830, 640)),
         ('org', 'high'): (1, 21446, -15437, 420, 200, 62, (1630, -4380)), ('org', 'close'): (1, 21446, -15437, 200, 200, 45, (1630, -4380))}
VIEWS0[('sw', 'near')] = (0, 16380, -25920, 90, 25, 40, (-8830, 640))
VIEWS = {k: v for k, v in VIEWS0.items() if k[0] == 'sw'}
VARS = os.environ.get('VARS', 'today,b4000,b8000,r70-b4000,r70-b8000,r70-b30000').split(',')
g = Game(minimap=False)
L = g.L; G = g.G; ns3 = g.ns3
setcam = L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')
frame = L.eval('''function(ns, dyaw) ns.cam.yaw = ns.cam.yaw + dyaw; CALLS_RESET(); COUNTING = true; local t0 = os.clock(); ns.Redraw(); local ms = (os.clock() - t0) * 1000; COUNTING = false; return ms, CALLS_TOTAL(), ns.stats.shown end''')
mem = L.eval('function() collectgarbage(); collectgarbage(); return collectgarbage("count") end')
out = {}
for (pk, vk), (m, x, y, d, yaw, pitch, (X, Y)) in VIEWS.items():
    g.at(X, Y, m, 0, 'x', ''); g.tick(2)
    G.SlashCmdList.GPS('3d'); g.tick(3)
    name = 'stormwind' if pk == 'sw' else 'orgrimmar'
    for var in VARS:
        if var == 'today': G.SlashCmdList.GPS3D('poc off'); G.SlashCmdList.GPS3D('detail on')
        else:
            opt = {p[0]: p[1:] for p in var.split('-')}   # (r radius, b budget, m smallest part)
            G.SlashCmdList.GPS3D('detail ' + ('on' if 'r' in opt else 'off'))
            G.SlashCmdList.GPS3D('poc both off'); G.SlashCmdList.GPS3D('poc city')
            G.SlashCmdList.GPS3D('poc min ' + opt.get('m', '0')); G.SlashCmdList.GPS3D('poc budget ' + opt.get('b', '30000')); G.SlashCmdList.GPS3D('poc radius ' + opt.get('r', '400'))
        setcam(ns3, m, x, y, d, yaw, pitch)
        for _ in range(12): frame(ns3, 0); g.tick(1)    # settle (blocks made, data loaded)
        m0 = mem()
        turn = [frame(ns3, 1.0) for _ in range(40)]
        still = [frame(ns3, 0.0) for _ in range(10)]
        r = {'ms_turn': round(statistics.median(t[0] for t in turn), 2), 'calls_turn': int(statistics.median(t[1] for t in turn)),
             'shown': int(statistics.median(t[2] for t in turn)), 'ms_still': round(statistics.median(t[0] for t in still), 2),
             'calls_still': int(statistics.median(t[1] for t in still)), 'lua_mb': round(m0 / 1024, 1), 'parts': int(ns3.poc.stats.parts) if var != 'today' and ns3.poc.stats else 0, 'cells': int(ns3.poc.stats.cells) if var != 'today' and ns3.poc.stats else 0, 'at200': round(float(ns3.poc.stats.at200), 1) if var != 'today' and ns3.poc.stats else 0}
        out[f'{pk}_{vk}_{var}'] = r; print(pk, vk, var, r, flush=True)
        g.chat()
print('PERFJSON', json.dumps(out))
print('errors', errors[:3])
