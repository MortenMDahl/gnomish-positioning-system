# The ground grid's cells (16.7 yd) that the shells' tops cover (at least FRAC of the cell, level 1): the city's floor,
# which GPS3D.lua sorts a little behind the shells; the rest of the ground (a hill inside the city's box) is sorted
# with the shells by distance. Writes sh_floorcells.json (cell keys: gy * 4096 + gx, gx = floor(x / cell),
# gy = floor(-y / cell)). Usage: [VAR=e_] python3 sh_floorcells.py
import os, pickle, json, numpy as np
from matplotlib.path import Path
VAR = os.environ.get('VAR', 'e_'); FRAC = float(os.environ.get('FRAC', '0.3'))
CELL = 1600 / 3 / 32; R = 0.5
S = pickle.load(open(f'sh_faces_{VAR}1.pkl', 'rb'))
tops = [f['c'] for f in S['faces'] if f['kind'] == 'roof']
P = np.vstack(tops); x0, y0 = np.floor(P[:, 0].min()), np.floor(P[:, 1].min()); x1, y1 = np.ceil(P[:, 0].max()), np.ceil(P[:, 1].max())
nx, ny = int((x1 - x0) / R) + 1, int((y1 - y0) / R) + 1
cov = np.zeros((ny, nx), bool)
gx, gy = np.meshgrid(x0 + (np.arange(nx) + 0.5) * R, y0 + (np.arange(ny) + 0.5) * R)
for c in tops:
    a, b = c[:, :2].min(0), c[:, :2].max(0)
    j0, j1 = int((a[0] - x0) / R), int((b[0] - x0) / R) + 1; i0, i1 = int((a[1] - y0) / R), int((b[1] - y0) / R) + 1
    sub = (slice(i0, i1), slice(j0, j1))
    ins = Path(np.vstack([c[:, :2], c[:1, :2]])).contains_points(np.stack([gx[sub].ravel(), gy[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
    cov[sub] |= ins
cx = np.floor(gx / CELL).astype(int); cy = np.floor(-gy / CELL).astype(int)
key = cy * 4096 + cx
tot = {}; hit = {}
for k, v in zip(key.ravel(), cov.ravel()):
    tot[k] = tot.get(k, 0) + 1; hit[k] = hit.get(k, 0) + v
full = (CELL / R) ** 2
cells = sorted(int(k) for k in tot if hit[k] >= FRAC * full)
json.dump(cells, open('sh_floorcells.json', 'w'))
print({'cells': len(cells), 'cells_touched': len(tot), 'frac': FRAC})
