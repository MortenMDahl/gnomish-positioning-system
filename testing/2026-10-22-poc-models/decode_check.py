# Decode check: every 10th facing group of the city data decoded by the addon (PocModels' DecodeGroup) against the
# exporter's source values (pb_city2's city2_check_q.json): vertices, corners, textures, areas, UVs
import os, sys, json
SP = '/tmp/claude-0/-home-claude/02c73231-da1f-5c67-9fe6-c007a09f80c0/scratchpad/poc'
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
errors = []
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); local c = ns.cam; c.map = 0; c.x, c.y, c.dist = 16426, -25896, 200; ns.Redraw()')
ref = json.load(open(f'{SP}/city2_check_q.json'))
dec = L.eval('''function(ns, ui, gi)
  local u = ns.poc.city.units[ui]; local m = ns.poc.DecodeGroup(u.groups[gi], u)
  local o = {}
  for k = 1, #m.vx do o[#o + 1] = string.format("%.5f %.5f %.5f", m.vx[k], m.vy[k], m.vh[k]) end
  local t = {}
  for k = 1, #m.tris do local q = m.tris[k]; t[#t + 1] = string.format("%d %d %d %d %d %.4f", q.a, q.b, q.c, q.d or 0, m.f[k], m.a[k]) end
  local uv = {}
  for k = 1, #m.tris * 8 do uv[#uv + 1] = m.uv[k] and string.format("%.6f", m.uv[k]) or "nil" end
  return table.concat(o, ";"), table.concat(t, ";"), table.concat(uv, ";") end''')
mv = mu = 0.0; ma = 0.0; bad = 0; groups = 0; parts = 0
for r in ref:
    vs, ts, us = dec(ns3, r['unit'], r['group'])
    V = [list(map(float, x.split())) for x in str(vs).split(';')]
    T = [x.split() for x in str(ts).split(';')]
    U = str(us).split(';')
    groups += 1
    for a, b in zip(V, r['v']): mv = max(mv, max(abs(a[i] - b[i]) for i in range(3)))
    if len(V) != len(r['v']) or len(T) != len(r['corners']): bad += 1; continue
    for k, (t, cr) in enumerate(zip(T, r['corners'])):
        parts += 1
        cor = [int(x) for x in t[:4] if int(x) > 0]
        if cor != cr or int(t[4]) != r['f'][k]: bad += 1
        ma = max(ma, abs(float(t[5]) - r['a'][k]) / max(r['a'][k], 1))
        for j, val in enumerate(r['uv'][k]):
            mu = max(mu, abs(float(U[k * 8 + j]) - val)) if U[k * 8 + j] != "nil" else mu
print(json.dumps({'groups_checked': groups, 'parts_checked': parts, 'mismatched_parts_or_groups': bad, 'max_vertex_err_yd': round(mv, 5), 'max_uv_err': round(mu, 6), 'max_area_rel_err': round(ma, 4)}))
