# Ground grid cells (16.7 yd) wholly covered by the shells' tops in every set (levels 0-4: units' sets and the blocks):
# GPS3D.lua need not draw the ground there while the shells are drawn (it is never seen). Writes sh_solidcells.json.
# Usage: [SOLID=0.999] python3 sh_solidcells.py
import os, pickle, json, numpy as np
from matplotlib.path import Path
CELL = 1600 / 3 / 32; R = 0.5; SOLID = float(os.environ.get('SOLID', '0.999'))
pk = ['sh_faces_f_0.pkl', 'sh_faces_0.pkl', 'sh_faces_e_1.pkl', 'sh_faces_1.pkl', 'sh_faces_e_2.pkl', 'sh_faces_2.pkl', 'sh_faces_e_3.pkl', 'sh_faces_3.pkl', 'sh_faces_e_4.pkl']
allc = None
for f in pk:
    S = pickle.load(open(f, 'rb'))
    tops = [x['c'] for x in S['faces'] if x['kind'] == 'roof']
    if allc is None:
        P = np.vstack(tops); x0, y0 = np.floor(P[:, 0].min()) - 20, np.floor(P[:, 1].min()) - 20; x1, y1 = np.ceil(P[:, 0].max()) + 20, np.ceil(P[:, 1].max()) + 20
        nx, ny = int((x1 - x0) / R) + 1, int((y1 - y0) / R) + 1
        gx, gy = np.meshgrid(x0 + (np.arange(nx) + 0.5) * R, y0 + (np.arange(ny) + 0.5) * R)
        allc = np.ones((ny, nx), bool)
    cov = np.zeros((ny, nx), bool)
    for c in tops:
        a, b = c[:, :2].min(0), c[:, :2].max(0)
        j0, j1 = max(0, int((a[0] - x0) / R)), min(nx, int((b[0] - x0) / R) + 1); i0, i1 = max(0, int((a[1] - y0) / R)), min(ny, int((b[1] - y0) / R) + 1)
        if j0 >= j1 or i0 >= i1: continue
        sub = (slice(i0, i1), slice(j0, j1))
        cov[sub] |= Path(np.vstack([c[:, :2], c[:1, :2]])).contains_points(np.stack([gx[sub].ravel(), gy[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
    print(f, 'covered yd2', int(cov.sum() * R * R))
    allc &= cov
key = (np.floor(-gy / CELL).astype(int) * 4096 + np.floor(gx / CELL).astype(int)).ravel()
tot = np.bincount(np.unique(key, return_inverse=True)[1]); uk = np.unique(key)
hit = np.bincount(np.unique(key, return_inverse=True)[1], weights=allc.ravel().astype(float))
full = (CELL / R) ** 2
solid = sorted(int(k) for k, t, h in zip(uk, tot, hit) if t >= 0.99 * full and h >= SOLID * t)
json.dump(solid, open('sh_solidcells.json', 'w'))
print({'solid_cells': len(solid), 'floor_cells': len(json.load(open('sh_floorcells.json')))})
