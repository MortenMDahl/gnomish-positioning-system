# (proof of concept, perf_poc4) native-Lua cost of the game's own models (finer hidden-part pass) vs today at fixed views: Render's Lua ms and the texture calls
# the game would make (SetVertexOffset, SetDrawLayer, Show ...) per frame, turning 1 degree a frame and standing still
import os, sys, json, statistics
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
errors = []
VIEWS0 = {('sw', 'high'): (0, 16400, -25880, 420, 25, 62, (-8830, 640)), ('sw', 'close'): (0, 16426, -25896, 200, 25, 45, (-8830, 640)),
         ('org', 'high'): (1, 21446, -15437, 420, 200, 62, (1630, -4380)), ('org', 'close'): (1, 21446, -15437, 200, 200, 45, (1630, -4380))}
VIEWS = {k: v for k, v in VIEWS0.items() if k == ('sw', 'close')}
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
    for var in ('today', 'tex', 'texfine', 'texfine1'):
        if var == 'today': G.SlashCmdList.GPS3D('poc off'); G.SlashCmdList.GPS3D('detail on')
        else:
            G.SlashCmdList.GPS3D('detail off')
            G.SlashCmdList.GPS3D('poc both off'); G.SlashCmdList.GPS3D(f'poc {name} ' + var)
        setcam(ns3, m, x, y, d, yaw, pitch)
        for _ in range(12): frame(ns3, 0); g.tick(1)    # settle (blocks made, data loaded)
        m0 = mem()
        turn = [frame(ns3, 1.0) for _ in range(40)]
        still = [frame(ns3, 0.0) for _ in range(10)]
        r = {'ms_turn': round(statistics.median(t[0] for t in turn), 2), 'calls_turn': int(statistics.median(t[1] for t in turn)),
             'shown': int(statistics.median(t[2] for t in turn)), 'ms_still': round(statistics.median(t[0] for t in still), 2),
             'calls_still': int(statistics.median(t[1] for t in still)), 'lua_mb': round(m0 / 1024, 1)}
        out[f'{pk}_{vk}_{var}'] = r; print(pk, vk, var, r, flush=True)
        g.chat()
print('PERFJSON', json.dumps(out))
print('errors', errors[:3])
