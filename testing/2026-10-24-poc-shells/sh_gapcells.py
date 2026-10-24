# (2026-10-24) The share of the ground's 16.7-yd cells (inside the data box) where some level's shell tops miss game-covered ground
# Usage (in the scratch folder of the S1 build, after sh_all3.sh): [LV=1,2,3,4] python3 sh_gapcells.py
import pickle, numpy as np, json, sys
sys.argv = ['x', '1']
src = open('sh_cover.py').read(); src = src[:src.index("S = pickle.load")]
exec(src)
miss = np.zeros_like(game)
for L in tuple(int(v) for v in __import__("os").environ.get("LV", "1,2,3,4").split(",")):
    S = pickle.load(open(f'sh_faces_e_{L}.pkl', 'rb')); tr = []
    for f in S['faces']:
        c = f['c']; tr.append(c[[0, 1, 2]])
        if len(c) == 4: tr.append(c[[0, 2, 3]])
    m = game & ~rast(np.array(tr)); print(L, 'miss yd2', int(m.sum() * 0.25)); miss |= m
CELL = 1600 / 3 / 32
box = (16162 + 1, 16688 - 1, -26163.5 + 1, -25631.5 - 1)
ys, xs = np.nonzero(miss); wx = lo[0] + (xs + 0.5) * R2; wy = lo[1] + (ys + 0.5) * R2
cx0, cx1 = int(np.ceil(box[0] / CELL)), int(np.floor(box[1] / CELL)); cy0, cy1 = int(np.ceil(box[2] / CELL)), int(np.floor(box[3] / CELL))
ncell = (cx1 - cx0) * (cy1 - cy0)
for thr in (1, 4, 16):
    ix, iy = np.floor(wx / CELL).astype(int), np.floor(wy / CELL).astype(int)
    ok = (ix >= cx0) & (ix < cx1) & (iy >= cy0) & (iy < cy1)
    u, cnt = np.unique(np.stack([ix[ok], iy[ok]], 1), axis=0, return_counts=True)
    print(json.dumps({'min_miss_px_per_cell': thr, 'min_yd2': thr * 0.25, 'cells_marked': int((cnt >= thr).sum()), 'cells_in_box': ncell, 'share': round(float((cnt >= thr).sum() / ncell), 3)}))
