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


# tilted, low, panning past the Redridge peaks: the camera's lift (rings + view ahead) and cut triangles every frame
G.SlashCmdList.GPS3D('detail on'); G.SlashCmdList.GPS3D('buildings 4000')
import os
place(*((-9400, -1300) if not os.environ.get('FLAT') else (-10300, 1500)), 0, 0.0); tick(5); ns2.ReadPlayer()
import os
ns2.SetCamMode('free'); ns2.SetTopDown(False, True)
import os
X0, Y0, TH = (18300, -25627, 66) if not os.environ.get('FLAT') else (pl.x, pl.y, pl.h)
for pitch, dist in ((30, 120), (45, 300)):
    state = {'k': 0}
    cam.map = 0; cam.x, cam.y, cam.th, cam.yaw, cam.pitch, cam.dist = X0, Y0, TH, 90, pitch, dist
    ns2.Render(); ns2.Render()
    def pan():
        state['k'] += 1
        cam.x = X0 + 5 * state['k']; ns2.Render()
    r = measure(pan, 120)
    report(f'Redridge peaks tilt {pitch} dist {dist} pan 5yd', r)
    print('   cut triangles last frame', int(st.cut or 0), 'lift', round(ns2.Lift()))
def lift_only():
    ns2.ForgetLift(); ns2.Lift()
r = measure(lift_only, 200)
print(f'{label} lift alone (rings + view ahead): {r[0]:.3f} ms median')
