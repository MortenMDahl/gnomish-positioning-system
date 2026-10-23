# (proof of concept, perf_poc7: perf_poc6 + C calls a frame, counted by the harness) cost of the game's own models with distance-based detail vs today, each setting in a
# fresh game (so one setting's textures and meshes don't crowd the next one's pool): Render's Lua ms, median of 40
# frames turning 1 degree a frame, and of 10 frames standing still (redrawn anyway)
import os, sys, json, statistics
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
VIEWS = {'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62)}
VARS = os.environ.get('VARS', 'today,b4000,b8000,r70-b4000,r70-b8000,r70').split(',')
out = {}
for vk, (x, y, d, yaw, pitch) in VIEWS.items():
    for var in VARS:
        g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
        g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
        L.execute('SANDBOX.namespaces.GPS3D.PocData = nil; collectgarbage()')   # (earlier test versions: not used here)
        if var == 'today': G.SlashCmdList.GPS3D('poc off'); G.SlashCmdList.GPS3D('detail on')
        else:
            opt = {p[0]: p[1:] for p in var.split('-')}   # (r radius, b budget, m smallest part)
            G.SlashCmdList.GPS3D('detail ' + ('on' if 'r' in opt else 'off')); G.SlashCmdList.GPS3D('poc city')
            if 'a' in opt: G.SlashCmdList.GPS3D('poc target ' + opt['a'])
            G.SlashCmdList.GPS3D('poc min ' + opt.get('m', '0')); G.SlashCmdList.GPS3D('poc budget ' + opt.get('b', '30000')); G.SlashCmdList.GPS3D('poc radius ' + opt.get('r', '400'))
        L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')(ns3, 0, x, y, d, yaw, pitch)
        frame = L.eval('function(ns, dy) ns.cam.yaw = ns.cam.yaw + dy; CALLS_RESET(); COUNTING = true; local t0 = os.clock(); ns.Redraw(); local ms = (os.clock() - t0) * 1000; COUNTING = false; return ms, ns.stats.shown, ns.poc.stats and ns.poc.stats.parts or 0, CALLS_TOTAL() end')
        for _ in range(12): frame(ns3, 0); g.tick(1)
        turn = [frame(ns3, 1.0) for _ in range(40)]; still = [frame(ns3, 0.0) for _ in range(10)]
        r = {'ms_turn': round(statistics.median(t[0] for t in turn), 1), 'ms_still': round(statistics.median(t[0] for t in still), 1), 'shown': int(turn[-1][1]), 'parts': int(turn[-1][2]), 'calls_turn': int(statistics.median(t[3] for t in turn))}
        out[f'{vk}_{var}'] = r; print(vk, var, r, flush=True)
print('PERFJSON', json.dumps(out))
