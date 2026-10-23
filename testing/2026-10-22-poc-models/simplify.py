# Visible triangles only, welded, simplified to several sizes; each triangle's colour from the game's texture
# (its average) times the vertex colour, carried over from the original triangles it replaces
import sys, json, numpy as np, pymeshlab
from scipy.spatial import cKDTree
from load import load
TARGETS = [3000, 8000, 20000]
for name in sys.argv[1:]:
    m = load(name); P, T, TEX, COL, UV = m['P'].astype(np.float64), m['T'], m['TEX'], m['COL'], m['UV']
    seen = np.fromfile(f'{name}_seen.u32', np.uint32)
    keep = seen >= 2
    T, TEX = T[keep], TEX[keep]
    # texture averages (alpha-weighted; the alpha-tested parts are holes)
    avg = {}
    for fd, info in m['meta']['textures'].items():
        if 'w' not in info: continue
        a = np.fromfile(f'raw/tex_{fd}.rgba', np.uint8).reshape(info['h'], info['w'], 4).astype(float)
        w = a[..., 3:4] / 255 + 1e-3
        avg[int(fd)] = (a[..., :3] * w).sum((0, 1)) / w.sum() / 255
    tc = np.array([avg.get(int(f), (0.6, 0.6, 0.6)) for f in TEX])
    vc = COL[T][:, :, [2, 1, 0]].mean(1) / 255     # (BGRA)
    col = np.clip(tc, 0, 1)   # (vertex colours left out: on outdoor faces a quarter are near black, not lighting)
    # weld
    key = np.round(P / 0.02).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.reshape(-1)
    Pw = np.zeros((inv.max() + 1, 3)); Pw[inv] = P
    Tw = inv[T]
    good = (Tw[:, 0] != Tw[:, 1]) & (Tw[:, 1] != Tw[:, 2]) & (Tw[:, 0] != Tw[:, 2])
    Tw, col, TEXk = Tw[good], col[good], TEX[good]
    cen0 = Pw[Tw].mean(1)
    n0 = np.cross(Pw[Tw[:, 1]] - Pw[Tw[:, 0]], Pw[Tw[:, 2]] - Pw[Tw[:, 0]]); a0 = np.linalg.norm(n0, axis=1); n0 = n0 / np.maximum(a0[:, None], 1e-9)
    tree = cKDTree(cen0)
    out = {'name': name, 'visible': int(keep.sum()), 'welded': int(len(Tw)), 'levels': {}}
    np.savez_compressed(f'{name}_full.npz', P=Pw, T=Tw, col=col, tex=TEXk)
    for tgt in TARGETS:
        red = 1 - tgt / len(Tw)
        ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(vertex_matrix=Pw, face_matrix=Tw.astype(np.int32)))
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=tgt, preserveboundary=False, boundaryweight=0.5, preservenormal=True, preservetopology=False, optimalplacement=True, planarquadric=True, qualitythr=0.2, autoclean=True)
        mm = ms.current_mesh(); Pn = mm.vertex_matrix().astype(np.float64); Tn = mm.face_matrix().astype(np.int64)
        cen = Pn[Tn].mean(1); nn = np.cross(Pn[Tn[:, 1]] - Pn[Tn[:, 0]], Pn[Tn[:, 2]] - Pn[Tn[:, 0]]); an = np.linalg.norm(nn, axis=1); nn = nn / np.maximum(an[:, None], 1e-9)
        d, idx = tree.query(cen, k=12)
        w = a0[idx] * (np.abs(np.einsum('nkj,nj->nk', n0[idx], nn)) + 0.05) / (d + 0.5)
        c = (col[idx] * w[..., None]).sum(1) / np.maximum(w.sum(1, keepdims=True), 1e-9)
        np.savez_compressed(f'{name}_{tgt}.npz', P=Pn, T=Tn, col=c)
        out['levels'][tgt] = int(len(Tn))
    print(json.dumps(out))
