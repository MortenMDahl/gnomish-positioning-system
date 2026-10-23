# Textures for the simplified models: each new triangle takes the texture of the original triangle it replaces (near,
# facing the same way, big) and that triangle's texture mapping extended over its plane (UV = ua + s (ub - ua) + t (uc - ua))
import sys, numpy as np
from scipy.spatial import cKDTree
from load import load
SIZES = [x for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else (3000, 8000)
for name in sys.argv[1:2]:
    m = load(name); P, T, TEX, UV = m['P'].astype(float), m['T'], m['TEX'], m['UV'].astype(float)
    seen = np.fromfile(f'{name}_seen.u32', np.uint32) >= 2
    T, TEX = T[seen], TEX[seen]
    A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n0 = np.cross(B - A, C - A); a0 = np.linalg.norm(n0, axis=1); n0 /= np.maximum(a0[:, None], 1e-9)
    tree = cKDTree((A + B + C) / 3)
    for size in SIZES:
        z = np.load(f'{name}_{size}.npz'); Pn, Tn = z['P'], z['T']
        a, b, c = Pn[Tn[:, 0]], Pn[Tn[:, 1]], Pn[Tn[:, 2]]
        nn = np.cross(b - a, c - a); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
        d, idx = tree.query((a + b + c) / 3, k=24)
        score = np.abs(np.einsum('nkj,nj->nk', n0[idx], nn)) ** 4 * np.sqrt(a0[idx]) / (d + 1.0)
        best = idx[np.arange(len(idx)), np.argmax(score, 1)]
        oa, ob, oc = A[best], B[best], C[best]; ua, ub, uc = UV[T[best, 0]], UV[T[best, 1]], UV[T[best, 2]]
        e1, e2 = ob - oa, oc - oa
        M = np.stack([e1, e2], -1)                       # (n, 3, 2)
        pinv = np.linalg.pinv(M)                         # (n, 2, 3)
        uvs = []
        for q in (a, b, c):
            st = np.einsum('nij,nj->ni', pinv, q - oa)
            uvs.append(ua + st[:, :1] * (ub - ua) + st[:, 1:] * (uc - ua))
        UVn = np.concatenate(uvs, 1)                      # (n, 6)
        # keep UVs near 0 for float precision (textures repeat): shift each triangle by whole tiles
        sh = np.floor(UVn[:, [0, 1]]); UVn -= np.tile(sh, 3)
        np.savez_compressed(f'{name}_tex{size}.npz', P=Pn, T=Tn, UV=UVn, F=TEX[best])
        print(name, size, 'textures used', len(np.unique(TEX[best])), 'UV range', round(float(UVn.min()), 2), round(float(UVn.max()), 2))
