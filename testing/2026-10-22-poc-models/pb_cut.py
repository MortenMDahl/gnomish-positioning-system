# Cut one building out of a region shell by a footprint polygon (GPS x, y) and a floor height
import sys, json, numpy as np
from matplotlib.path import Path
z = np.load(sys.argv[1]); V, F = z['V'], z['F']
poly = np.array(json.loads(sys.argv[2])); hmin = float(sys.argv[3]); out = sys.argv[4]
cen = V[F].mean(1)
keep = Path(poly).contains_points(cen[:, :2]) & (cen[:, 2] > hmin)
Fk = F[keep]; used, inv = np.unique(Fk, return_inverse=True)
np.savez_compressed(out, V=V[used], F=inv.reshape(-1, 3))
print(json.dumps({'tris': int(keep.sum()), 'h': [float(V[used][:, 2].min()), float(V[used][:, 2].max())]}))
