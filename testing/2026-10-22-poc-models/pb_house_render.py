import json, sys, numpy as np
from matplotlib.path import Path
from load import load
from pb_io import groups, save, cam
m = load('stormwind'); P = m['P'].astype(float); T = m['T']
poly = np.array(json.load(open('pb_poly.json')))
cen = P[T].mean(1); x0, y0 = 16374.4, -25924.3
reg = (np.abs(cen[:, 0] - x0) < 45) & (np.abs(cen[:, 1] - y0) < 45)
inh = Path(poly).contains_points(cen[:, :2]) & (cen[:, 2] > 96)
ctx = reg & ~inh
save('pb_ctx.json', groups(P, T[ctx], m['UV'][T[ctx]].reshape(-1, 6), m['TEX'][ctx]))
save('pb_lv_orig.json', groups(P, T[inh], m['UV'][T[inh]].reshape(-1, 6), m['TEX'][inh]))
levels = [int(s) for s in sys.argv[1].split(',')]
for n in levels:
    z = np.load(f'pb_h_{n}.npz'); V, F, UV, FD = z['V'], z['F'], z['UV'], z['FD']
    nn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
    keep = ~((nn[:, 2] < -0.7) & (V[F].mean(1)[:, 2] < 100))      # (the underside)
    save(f'pb_lv_{n}.json', groups(V, F[keep], UV[keep], FD[keep]))
    save(f'pb_lvg_{n}.json', groups(V, F[keep]))
    print(n, int(keep.sum()))
c1 = cam(); c2 = cam(x=16371, y=-25926, th=118, dist=75, yaw=25, pitch=40)
jobs = []
for lv in ['orig'] + levels:
    jobs.append({'out': f'pb_v1_{lv}.png', 'm': f'pb_ctx.json,pb_lv_{lv}.json', 'cam': c1})
    jobs.append({'out': f'pb_v2_{lv}.png', 'm': f'pb_ctx.json,pb_lv_{lv}.json', 'cam': c2, 'cull': 1})
    if lv != 'orig': jobs.append({'out': f'pb_v2g_{lv}.png', 'm': f'pb_lvg_{lv}.json', 'cam': c2, 'cull': 1})
json.dump(jobs, open('jobs.json', 'w'))
