# Fit of the shells: per unit, footprint IoU against the unit's real geometry seen from straight above (0.25 yd), and
# the top-height error (shell top minus real top) over cells both cover.  Usage: python3 sh_fit.py <lod>
import sys, pickle, json, numpy as np, shapely
from scipy import ndimage
from pb_common import sample_tris
R2 = 0.25
L = sys.argv[1]
d = np.load('sh_in.npz'); TRI = d['tri'].astype(float); BLD = d['bld']; ST = d['street']
S = pickle.load(open(f'sh_shells_{L}.pkl', 'rb'))
def faces_top(faces, X, Y):
    """Highest shell face over each point (roof faces only), -inf where none."""
    h = np.full(X.shape, -np.inf)
    for f in faces:
        if f['kind'] != 'roof': continue
        c = f['c']
        for t in ([c[[0, 1, 2]]] + ([c[[0, 2, 3]]] if len(c) == 4 else [])):
            a, b, cc = t[:, :2]
            v0, v1 = b - a, cc - a; den = v0[0] * v1[1] - v0[1] * v1[0]
            if abs(den) < 1e-9: continue
            px, py = X - a[0], Y - a[1]
            u = (px * v1[1] - py * v1[0]) / den; v = (v0[0] * py - v0[1] * px) / den
            ins = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
            hh = t[0, 2] + u * (t[1, 2] - t[0, 2]) + v * (t[2, 2] - t[0, 2])
            h = np.where(ins, np.maximum(h, hh), h)
    return h
res = []
for U in S:
    if U['unit'] < 0: continue
    ids = np.nonzero((BLD == U['unit']) & ~ST)[0]
    lo = TRI[ids].reshape(-1, 3).min(0) - 3; hi = TRI[ids].reshape(-1, 3).max(0) + 3
    nx, ny = int((hi[0] - lo[0]) / R2) + 1, int((hi[1] - lo[1]) / R2) + 1
    pts, _ = sample_tris(TRI[ids, 0], TRI[ids, 1], TRI[ids, 2], 0.15)
    real = np.full(ny * nx, -np.inf); np.maximum.at(real, np.floor((pts[:, 1] - lo[1]) / R2).astype(int) * nx + np.floor((pts[:, 0] - lo[0]) / R2).astype(int), pts[:, 2])
    real = real.reshape(ny, nx); rm = real > -np.inf
    X, Y = np.meshgrid(lo[0] + (np.arange(nx) + 0.5) * R2, lo[1] + (np.arange(ny) + 0.5) * R2)
    poly = shapely.union_all([r['poly'] for r in U['regions']])
    sm = shapely.contains_xy(poly, X, Y)
    iou = (rm & sm).sum() / max((rm | sm).sum(), 1)
    st = faces_top(U['faces'], X, Y); both = rm & (st > -np.inf)
    err = (st - real)[both]
    res.append(dict(unit=U['unit'], iou=float(iou), area=float(rm.sum() * R2 * R2), herr=float(np.sqrt(np.mean(err ** 2))) if len(err) else None, faces=len(U['faces'])))
units = set(int(u) for u in np.unique(BLD[~ST]))
missing = sorted(units - set(r['unit'] for r in res))
iou = np.array([r['iou'] for r in res]); ar = np.array([r['area'] for r in res]); he = np.array([r['herr'] for r in res if r['herr'] is not None])
json.dump(res, open(f'sh_fit_{L}.json', 'w'))
# missing units: their real footprint area
mar = []
for u in missing:
    ids = np.nonzero((BLD == u) & ~ST)[0]; t = TRI[ids]
    mar.append(float(np.sum(np.abs(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])[:, 2])) / 2))
print(json.dumps({'lod': L, 'units': len(res), 'missing': len(missing), 'missing_area_p50_max': [round(float(np.median(mar)), 1), round(float(max(mar)), 1)] if mar else None,
  'iou_median': round(float(np.median(iou)), 3), 'iou_under_085': round(float((iou < 0.85).mean()), 3), 'iou_under_085_areaweighted': round(float(ar[iou < 0.85].sum() / ar.sum()), 3),
  'iou_under_070': round(float((iou < 0.7).mean()), 3), 'height_rms_median': round(float(np.median(he)), 2), 'height_rms_p90': round(float(np.percentile(he, 90)), 2)}))
