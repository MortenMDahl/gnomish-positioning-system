# The ground's frame times (J8, 2026-10-22): Render's processor time at test_terrain.py's far views (the camera
# turning a degree a frame: median of 40 frames) and over its zoom sweeps (2 % a frame from 14,000 to 30 yd:
# mean per frame; the clock moving on 1/30 s a frame), for several versions of GPS3D.lua, each run several times in turn in fresh processes and
# the fastest run of each kept (other programs and the machine's own variation only ever add time).
# Usage: python3 perf_terrain.py [runs] label=path[:LOD_P] ...   (path "-": the sandbox's copy; PERF_ONLY=a,b: only the
# scenarios whose names contain one of these)
#   e.g. python3 perf_terrain.py 3 J1=/tmp/GPS3D_J1.lua J8=- "J8 more=1.6=-:MORE=1.6"
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

CHILD = r'''
import os, sys, time, json
os.environ['TERRAIN_NOZOOM'] = '1'
src = open('test_terrain.py').read()
cut = src.index('FAR = [')
__file__ = os.path.abspath('test_terrain.py')
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src[:cut], __file__, 'exec'))
out = {}
# the clock moves on 1/30 s a frame, as in the game at 30 fps (else meshes unused for 3 s are never given back)
L.execute('local function findup(f, name) for i = 1, 20 do local n, v = debug.getupvalue(f, i); if not n then return end; if n == name then return v end end end; CLOCK_S = findup(GetTime, "S")')
S_ = G.CLOCK_S
if os.environ.get('PERF_NOGC'): L.execute('collectgarbage("stop")')
def step():
    S_.time = S_.time + 1 / 30
# the sandbox's SetParent looks for the texture in its old frame's list, one by one (thousands of textures
# there): its time is counted apart, as the game's own SetParent is not that
L.execute("""local f = CreateFrame("Frame"); local T = getmetatable(f:CreateTexture()).__index
local SP, clock = T.SetParent, os.clock
SP_TIME = 0
T.SetParent = function(...) local t = clock(); SP(...); SP_TIME = SP_TIME + clock() - t end""")
ONLY = [x for x in os.environ.get('PERF_ONLY', '').split(',') if x]
for name, m, gx, gy, yaw in [('Hyjal', 1, 38.6, 21.8, 30), ('Durotar', 1, 40.6, 30.6, 200), ('Elwynn', 0, 31.9, 49.75, 0)]:
    for pitch in (45, 89.9):
        if ONLY and not any(o in f'zoom {name} {"45" if pitch < 89 else "down"}' for o in ONLY): continue
        view(m, gx, gy, 14000, pitch, yaw); ns.Render()
        if not os.environ.get('PERF_NOGC'): L.execute('collectgarbage()')
        d, ts, tris = 14000.0, [], 0
        G.SP_TIME = 0
        while d > 30:
            cam.dist = d; step(); t0 = time.process_time(); ns.Render(); ts.append(time.process_time() - t0); tris += int(st.tris); d *= 0.98
        key = f'zoom {name} {"45" if pitch < 89 else "down"}'
        out[key] = (sum(ts) / len(ts) * 1000, tris / len(ts))
        out[key + ' w/o SetParent'] = ((sum(ts) - G.SP_TIME) / len(ts) * 1000, tris / len(ts))
for name, m, gx, gy, dist, pitch, yaw in [('far Hyjal', 1, 38.6, 21.8, 5000, 45, 30), ('far Stormwind', 0, 30.8, 48.56, 3000, 45, 0),
        ('far Durotar', 1, 40.6, 30.6, 4000, 89.9, 0), ('far Thousand Needles', 1, 38.0, 42.3, 4000, 45, 0), ('far Stranglethorn', 0, 30.0, 56.0, 4000, 45, 0)]:
    if ONLY and not any(o in name for o in ONLY): continue
    view(m, gx, gy, dist, pitch, yaw)
    for _ in range(80): step(); ns.Render()
    L.execute('collectgarbage()')
    ts, sp = [], []
    for k in range(40):
        p0 = G.SP_TIME
        cam.yaw = yaw + k; step(); t0 = time.process_time(); ns.Render(); ts.append(time.process_time() - t0); sp.append(ts[-1] - (G.SP_TIME - p0))
    ts.sort(); sp.sort()
    out[name] = (ts[len(ts) // 2] * 1000, int(st.tris))
    out[name + ' w/o SetParent'] = (sp[len(sp) // 2] * 1000, int(st.tris))
print('RESULT ' + json.dumps(out))
'''


def run(path, lodp):
    env = dict(os.environ)
    env.pop('GPS3D_LUA', None); env.pop('LOD_P', None)
    if path != '-':
        env['GPS3D_LUA'] = path
    if lodp:
        env['LOD_P'] = lodp
    r = subprocess.run([sys.executable, '-c', CHILD], cwd=HERE, env=env, capture_output=True, text=True, timeout=3000)
    for line in r.stdout.splitlines():
        if line.startswith('RESULT '):
            return json.loads(line[7:])
    raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])


def main():
    args = sys.argv[1:]
    runs = int(args.pop(0)) if args and args[0].isdigit() else 3
    configs = []
    for a in args:
        label, rest = a.split('=', 1)
        path, _, lodp = rest.partition(':')
        configs.append((label, path, lodp))
    best = {c[0]: {} for c in configs}
    for k in range(runs):
        for label, path, lodp in configs:
            res = run(path, lodp)
            for key, (ms, tris) in res.items():
                b = best[label].get(key)
                if b is None or ms < b[0]:
                    best[label][key] = (ms, tris)
            print(f'run {k + 1} {label} done', flush=True)
    keys = list(best[configs[0][0]])
    base = configs[0][0]
    print(f'{"":24s}' + ''.join(f'{c[0]:>26s}' for c in configs))
    for key in keys:
        row = f'{key:24s}'
        for label, _, _ in configs:
            ms, tris = best[label][key]
            rel = ms / best[base][key][0] - 1
            row += f'{ms:9.2f} ms {tris:5.0f} tris {rel * 100:+4.0f} %'
        print(row)
    json.dump(best, open(os.path.join(HERE, 'shots', 'perf_terrain.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
