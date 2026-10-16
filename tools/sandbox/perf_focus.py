# Focused per-frame measurement: Render ms (median), C-API calls per frame, Lua garbage per frame.
# Usage: python3 perf_focus.py [label]
import math, time, sys, statistics
import os
src = open("test_world51.py" if os.environ.get("LUA") == "51" else "test_world.py").read().split("place(-8958.3, -190, 0, 0.3")[0]
WRAP = '\nCALLS = {}\nlocal names = { "SetVertexOffset", "SetDrawLayer", "SetParent", "Show", "Hide", "SetTexCoord", "SetTexture", "SetVertexColor" }\nlocal tex = UIParent:CreateTexture()\nlocal Texture = getmetatable(tex)\nfor _, n in ipairs(names) do\n  local f = Texture[n]\n  Texture[n] = function(...) CALLS[n] = (CALLS[n] or 0) + 1 return f(...) end\nend\nfunction CALLS_RESET() for k in pairs(CALLS) do CALLS[k] = 0 end end\nfunction RUNFRAME(f)\n  collectgarbage("collect"); collectgarbage("stop")\n  local k0 = collectgarbage("count")\n  local t0 = os.clock()\n  f()\n  local ms = (os.clock() - t0) * 1000\n  local kb = collectgarbage("count") - k0\n  collectgarbage("restart")\n  return ms, kb\nend\n'
src = src.replace("L.execute(open(f'{SITE}/engine.lua').read())", "L.execute(open(f'{SITE}/engine.lua').read()); L.execute(WRAP)")
assert 'L.execute(WRAP)' in src
exec(compile(src, 'setup', 'exec'))
label = sys.argv[1] if len(sys.argv) > 1 else ''

place(-8958.3, -190, 0, 0.3, 'Elwynn Forest', 'Northshire Valley')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
st, cam, pl = ns2.stats, ns2.cam, ns2.player
calls = G.CALLS
NAMES = ["SetVertexOffset", "SetDrawLayer", "SetParent", "Show", "Hide", "SetTexCoord", "SetTexture", "SetVertexColor"]

def measure(fn, n):
    ms, kb, cl = [], [], {k: [] for k in NAMES}
    for _ in range(n):
        G.CALLS_RESET()
        m, k = G.RUNFRAME(fn)
        ms.append(m); kb.append(k)
        for key in NAMES: cl[key].append(int(calls[key] or 0))
    ms.sort(); kb.sort()
    med = lambda a: a[len(a) // 2]
    return med(ms), ms[-1], med(kb), {k: med(sorted(v)) for k, v in cl.items()}

def report(name, r):
    med, worst, kb, cl = r
    tot = sum(cl.values())
    print(f'{label} {name:42s} {med:6.1f} ms med {worst:6.1f} worst  {kb:7.0f} KB/frame  C calls {tot:6d} ' + ' '.join(f'{k[3:] if k.startswith("Set") else k}={v}' for k, v in cl.items()) + f'  shown {int(st.shown)} blocks {int(st.detail)}')

def turn():
    cam.yaw = cam.yaw + 3; ns2.Render()
def still():
    ns2.Render()
def render_only():
    ns2.Render()

scenes = [('Stormwind Trade District', -8830, 640, 0), ('Northshire Abbey', -8900, -160, 0), ('Open country (Westfall)', -10300, 1500, 0)]
for name, X, Y, m in scenes:
    for detail in ['off', 'on']:
        G.SlashCmdList.GPS3D('detail ' + detail)
        if detail == 'on': G.SlashCmdList.GPS3D('buildings 4000')
        place(X, Y, m, 1.0); tick(5)
        for _ in range(8): tick(1)
        ns2.Render(); ns2.Render()
        report(f'{name[:20]} bld={detail} turn 3deg', measure(turn, 40))
        if detail == 'on' and name.startswith('Stormwind'):
            report(f'{name[:20]} bld={detail} static re-render', measure(still, 20))
            # realistic walking: 0.25 yd per frame at 30 fps
            state = {'k': 0}
            def step():
                state['k'] += 1
                x = X + math.cos(1.0) * 0.25 * state['k']; y = Y + math.sin(1.0) * 0.25 * state['k']
                place(x, y, m, 1.0); ns2.ReadPlayer(); ns2.FollowStep(1 / 30); ns2.Render()
            report(f'{name[:20]} bld={detail} walk 0.25yd/frame', measure(step, 60))
            state = {'k': 0}
            def step60():
                state['k'] += 1
                x = X + math.cos(1.0) * 0.12 * state['k']; y = Y + math.sin(1.0) * 0.12 * state['k']
                place(x, y, m, 1.0); ns2.ReadPlayer(); ns2.FollowStep(1 / 60); ns2.Render()
            report(f'{name[:20]} bld={detail} walk 0.12yd/frame', measure(step60, 60))
            cam.dist = 800; ns2.Render(); ns2.Render()
            report(f'{name[:20]} bld={detail} walk 0.25yd dist 800', measure(step, 60))
            cam.dist = 330; ns2.Render()

# fast walk: block building hitches (20 yd/frame, 600 yd)
G.SlashCmdList.GPS3D('detail on'); G.SlashCmdList.GPS3D('buildings 4000')
for name, X, Y, m, hd in [('Stormwind', -8700, 400, 0, 1.0)]:
    place(X, Y, m, hd); tick(5)
    state = {'k': 0}
    def step():
        state['k'] += 1
        x = X + math.cos(hd) * 20 * state['k']; y = Y + math.sin(hd) * 20 * state['k']
        place(x, y, m, hd); ns2.ReadPlayer(); ns2.FollowStep(1 / 30); ns2.Render()
    report(f'{name} walk 20yd/frame (new blocks)', measure(step, 30))
    place(X, Y, m, hd); tick(5)
    state = {'k': 0}
    def step2():
        state['k'] += 1
        x = X + math.cos(hd) * 3.3 * state['k']; y = Y + math.sin(hd) * 3.3 * state['k']
        place(x, y, m, hd); ns2.ReadPlayer(); ns2.FollowStep(1 / 30); ns2.Render()
    report(f'{name} walk 3.3yd/frame', measure(step2, 180))
print(f'{label} textures made: {ns2.stats and ""}')
