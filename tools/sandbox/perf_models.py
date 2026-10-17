# Lua-side cost of the game's models in the 3D view (sandbox, native Lua 5.4; the game's own drawing of
# the models is not measured here): frame time (Render) and the time of each tick (Render + the
# models' choice) while the view turns, with props and trees off, at 250 and at 1000, tilted over
# Goldshire and over Stormwind. Usage: python perf_models.py
import time, math, sys, os
sys.argv.append('--quiet')
os.environ['GPS_MUTATION'] = ''
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_models.py')).read()
src = src[:src.index('g = Game()')]
exec(src)
TILE = 1600 / 3
g = Game(); ns = g.ns; G = g.G
g.open3d()
for name, (x, y) in [('Goldshire', (32.3, 49.55)), ('Stormwind', (31.2, 48.3))]:
    for label, props, count in [('props off', False, 250), ('props 250', True, 250), ('props 1000', True, 1000)]:
        G.GPS3D_DB.props, G.GPS3D_DB.modelCount = props, count
        g.free_view(x * TILE, -y * TILE, 400, pitch=55, yaw=0); g.tick(30)
        ns.ModelsChanged(); g.tick(30)
        r, t = [], []
        for k in range(60):
            ns.cam.yaw = (ns.cam.yaw + 3) % 360
            t0 = time.perf_counter(); ns.Render(); r.append(float(ns.stats.ms))
            g.tick(1); t.append((time.perf_counter() - t0) * 1000)
        st = ns.modelState
        print(f'{name:10s} {label:11s}: Render {sum(r) / len(r):5.2f} ms avg; Render + tick {sorted(t)[len(t) // 2]:6.2f} ms median; {st.shown} shown ({st.shownWmo} buildings), {len(st.pool)} actors')
