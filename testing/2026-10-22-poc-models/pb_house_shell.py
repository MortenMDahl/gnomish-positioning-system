# A closed shell from one building's own triangles only (inside its footprint polygon, above a floor height)
import sys, json, numpy as np
from matplotlib.path import Path
from load import load
from pb_shell import shell
poly = np.array(json.load(open(sys.argv[1]))); hmin = float(sys.argv[2]); out = sys.argv[3]
m = load('stormwind'); P = m['P'].astype(float); T = m['T']
cen = P[T].mean(1)
k = Path(poly).contains_points(cen[:, :2]) & (cen[:, 2] > hmin)
c = poly.mean(0); half = float(np.abs(poly - c).max()) + 2
V, F, info = shell(P, T[k], c[0], c[1], half)
# drop the underside (the ground fill's floor under the building)
cz = V[F].mean(1)[:, 2]
n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
under = (n[:, 2] < -0.7) & (cz < hmin + 4)   # (kept for simplifying; dropped after)
np.savez_compressed(out, V=V, F=F)
info.update(orig_tris=int(k.sum()), shell_tris=int(len(F)), underside_dropped=int(under.sum())); print(json.dumps(info))
