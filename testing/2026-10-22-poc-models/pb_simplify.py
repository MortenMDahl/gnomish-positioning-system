# One building: simplify its closed shell to several sizes and give every triangle the game's texture of the
# original surface it lies on (that triangle's texture mapping extended over its plane)
import sys, json, numpy as np, pymeshlab
from scipy.spatial import cKDTree
from matplotlib.path import Path
from load import load

def decimate(V, F, n):
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(vertex_matrix=V, face_matrix=F.astype(np.int32)))
    for pn, qt in ((True, 0.3), (False, 0.1), (False, 0.0)):        # (stricter first; looser where it stalls)
        if ms.current_mesh().face_number() <= n * 1.02: break
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=n, preserveboundary=True, boundaryweight=2.0, preservenormal=pn, preservetopology=True, optimalplacement=True, planarquadric=True, planarweight=0.002, qualitythr=qt, autoclean=True)
    mm = ms.current_mesh()
    return mm.vertex_matrix().astype(float), mm.face_matrix().astype(np.int64)

def transfer(Pn, Tn, A, B, C, UVo, TEXo):
    a, b, c = Pn[Tn[:, 0]], Pn[Tn[:, 1]], Pn[Tn[:, 2]]
    n0 = np.cross(B - A, C - A); a0 = np.linalg.norm(n0, axis=1); n0 /= np.maximum(a0[:, None], 1e-9)
    nn = np.cross(b - a, c - a); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
    tree = cKDTree((A + B + C) / 3)
    d, idx = tree.query((a + b + c) / 3, k=min(32, len(A)))
    score = np.abs(np.einsum('nkj,nj->nk', n0[idx], nn)) ** 4 * np.sqrt(a0[idx]) / (d + 1.0)
    best = idx[np.arange(len(idx)), np.argmax(score, 1)]
    oa, ob, oc = A[best], B[best], C[best]; ua, ub, uc = UVo[best, 0], UVo[best, 1], UVo[best, 2]
    pinv = np.linalg.pinv(np.stack([ob - oa, oc - oa], -1))
    uvs = []
    for q in (a, b, c):
        st = np.einsum('nij,nj->ni', pinv, q - oa)
        uvs.append(ua + st[:, :1] * (ub - ua) + st[:, 1:] * (uc - ua))
    UV = np.concatenate(uvs, 1); UV -= np.tile(np.floor(UV[:, [0, 1]]), 3)
    return UV, TEXo[best]

if __name__ == '__main__':
    shell, poly, out, sizes = sys.argv[1], np.array(json.load(open(sys.argv[2]))), sys.argv[3], [int(s) for s in sys.argv[4].split(',')]
    z = np.load(shell); V, F = z['V'], z['F']
    m = load('stormwind'); P = m['P'].astype(float); T = m['T']
    cen = P[T].mean(1)
    big = Path(poly).contains_points(cen[:, :2], radius=-4.0) | Path(poly).contains_points(cen[:, :2], radius=4.0)
    k = np.nonzero(big)[0]
    A, B, C = P[T[k, 0]], P[T[k, 1]], P[T[k, 2]]; UVo = m['UV'][T[k]].astype(float); TEXo = m['TEX'][k]
    res = {}
    for n in sizes:
        Pn, Tn = decimate(V, F, n)
        UV, FD = transfer(Pn, Tn, A, B, C, UVo, TEXo)
        np.savez_compressed(f'{out}_{n}.npz', V=Pn, F=Tn, UV=UV, FD=FD)
        res[n] = int(len(Tn))
    print(json.dumps(res))
