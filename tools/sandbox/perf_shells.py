# (proof of concept S1, building shells) Render's Lua ms per frame at Stormwind, fresh game per setting (as
# perf_poc7.py): median of 40 frames turning 1 degree a frame and 10 standing still (redrawn anyway); textures shown,
# shell faces drawn, C calls a frame. Settings: shells (old blocks off), blocks (the old jagged blocks, shells off),
# none (ground only); views closeup 45 yd (since 2026-10-24), near 90 yd, close 200, high 420, mid 800, far 2,000.
# LOD="0:3,70:5,125:7,300:7,580:9" sets the five levels (start yd : set) for the "shells" setting; "shells-l<N>": set N everywhere.
import os, sys, json, statistics
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
VIEWS = {'mid': (16426, -25896, 800, 25, 55), 'closeup': (16380, -25920, 45, 25, 40), 'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62), 'far': (16426, -25896, 2000, 25, 50)}
TH = float(os.environ.get('TH', '0')) or None   # (orbit height: the ground under the view unless given; the shots use 117.5, the streets)
VARS = os.environ.get('VARS', 'shells,blocks').split(',')
if os.environ.get('VIEWSJSON'): VIEWS = json.loads(os.environ['VIEWSJSON'])  # ({name: [x, y, dist, yaw, pitch, map]})
views = os.environ.get('VIEWSEL', ','.join(VIEWS)).split(',')
out = {}
for vk in views:
    x, y, d, yaw, pitch = VIEWS[vk][:5]; mp = VIEWS[vk][5] if len(VIEWS[vk]) > 5 else 0
    for var in VARS:
        g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
        g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
        if var == 'shells':
            G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on')
            for i, e in enumerate([e for e in os.environ.get('LOD', '').split(',') if e], 1):  # (LOD="0:3,70:5,...": the five levels' start yd and set)
                a, b = e.split(':'); G.SlashCmdList.GPS3D(f'shells lod {i} {a} {b}')
            if os.environ.get('BUDGET'): G.SlashCmdList.GPS3D('shells budget ' + os.environ['BUDGET'])  # (faces; 0: none)
            if os.environ.get('TILES'): G.SlashCmdList.GPS3D('shells tiles ' + os.environ['TILES'])  # (the whole-block shells' faces; 0: none)
        elif var == 'shells-detail': G.SlashCmdList.GPS3D('detail on'); G.SlashCmdList.GPS3D('shells on')  # (as the game starts: old blocks on, shells on)
        elif var == 'shells-tiles0': G.SlashCmdList.GPS3D('detail on'); G.SlashCmdList.GPS3D('shells on'); G.SlashCmdList.GPS3D('shells tiles 0')  # (the whole-block shells off, the old blocks instead)
        elif var.startswith('shells-l'): G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on'); G.SlashCmdList.GPS3D('shells level ' + var[-1])
        elif var.startswith('shells-px'):
            pp = var[len('shells-px'):].split('-'); G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on'); G.SlashCmdList.GPS3D('shells px ' + ' '.join(pp))
        elif var == 'blocks': G.SlashCmdList.GPS3D('shells off'); G.SlashCmdList.GPS3D('detail on')
        else: G.SlashCmdList.GPS3D('shells off'); G.SlashCmdList.GPS3D('detail off')
        L.eval('''function(ns, m, x, y, d, yaw, pitch, TH) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = TH or ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')(ns3, mp, x, y, d, yaw, pitch, TH)
        frame = L.eval('function(ns, dy) ns.cam.yaw = ns.cam.yaw + dy; CALLS_RESET(); COUNTING = true; local t0 = os.clock(); ns.Redraw(); local ms = (os.clock() - t0) * 1000; COUNTING = false; local st = ns.shells and ns.shells.stats; return ms, ns.stats.shown, st and st.faces or 0, CALLS_TOTAL(), st and st.units or 0 end')
        for _ in range(20): frame(ns3, 0); g.tick(1)
        turn = [frame(ns3, 1.0) for _ in range(40)]; still = [frame(ns3, 0.0) for _ in range(10)]
        r = {'ms_turn': round(statistics.median(t[0] for t in turn), 1), 'ms_still': round(statistics.median(t[0] for t in still), 1), 'shown': int(turn[-1][1]), 'faces': int(turn[-1][2]), 'units': int(turn[-1][4]), 'calls_turn': int(statistics.median(t[3] for t in turn))}
        out[f'{vk}_{var}'] = r; print(vk, var, r, flush=True)
print('PERFJSON', json.dumps(out))
print('FOCAL', L.eval('function(ns) local w, h = ns.canvas:GetSize(); return string.format("%f %d %d", ns.Focal(), w, h) end')(ns3))
