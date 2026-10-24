# Fit of the coverage-built shells: per unit, IoU of its shell's footprint (its regions) against the cells where
# the unit's real geometry is the highest seen from above (0.25 yd; streets in 60-yd cells as in sh_build3.py);
# units of at least 150 yd2. Usage: python3 sh_fit3.py <lod>
import sys, pickle, json, numpy as np, shapely
from pb_common import sample_tris
L = int(sys.argv[1]); R2 = 0.25
d = np.load('sh_in.npz'); T = d['tri'].astype(float); BLD = d['bld']; ST = d['street']
cen = T.mean(1)
owner = np.where(ST, 10 ** 6 + (np.floor(cen[:, 0] / 60).astype(int) - 260) * 1000 + (np.floor(-cen[:, 1] / 60).astype(int) - 420), BLD)
lo = T.reshape(-1, 3).min(0) - 2; hi = T.reshape(-1, 3).max(0) + 2
nx, ny = int((hi[0] - lo[0]) / R2) + 1, int((hi[1] - lo[1]) / R2) + 1
top = np.full(ny * nx, -1e9); own = np.full(ny * nx, -1)
for i in range(0, len(T), 20000):
    t = np.arange(i, min(i + 20000, len(T)))
    p, ti = sample_tris(T[t, 0], T[t, 1], T[t, 2], 0.12)
    c = np.floor((p[:, 1] - lo[1]) / R2).astype(int) * nx + np.floor((p[:, 0] - lo[0]) / R2).astype(int)
    o = np.lexsort((p[:, 2], c)); last = np.r_[c[o][1:] != c[o][:-1], True]
    c2, h2, ow2 = c[o][last], p[o][last, 2], owner[t[ti[o][last]]]
    b = h2 > top[c2]; top[c2[b]] = h2[b]; own[c2[b]] = ow2[b]
own = own.reshape(ny, nx)
S = pickle.load(open(f'sh_shells_{L}.pkl', 'rb'))
X, Y = np.meshgrid(lo[0] + (np.arange(nx) + 0.5) * R2, lo[1] + (np.arange(ny) + 0.5) * R2)
res = []
for U in S:
    o = U['owner']
    if o >= 10 ** 6: continue
    real = own == o
    if real.sum() * R2 * R2 < 150: continue
    poly = shapely.union_all([r['poly'] for r in U['regions']])
    if poly.is_empty: res.append(0.0); continue
    x0, y0, x1, y1 = poly.bounds; ys, xs = np.nonzero(real)
    i0, i1 = max(0, min(int((y0 - lo[1]) / R2), ys.min()) - 2), min(ny, max(int((y1 - lo[1]) / R2), ys.max()) + 3)
    j0, j1 = max(0, min(int((x0 - lo[0]) / R2), xs.min()) - 2), min(nx, max(int((x1 - lo[0]) / R2), xs.max()) + 3)
    sm = shapely.contains_xy(poly, X[i0:i1, j0:j1], Y[i0:i1, j0:j1]); rm = real[i0:i1, j0:j1]
    res.append(float((sm & rm).sum() / max((sm | rm).sum(), 1)))
res = np.array(res)
print(json.dumps({'lod': L, 'units_150yd2': len(res), 'iou_median': round(float(np.median(res)), 3), 'under_085': round(float((res < 0.85).mean()), 3), 'under_070': round(float((res < 0.7).mean()), 3)}))
