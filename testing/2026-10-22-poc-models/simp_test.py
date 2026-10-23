import numpy as np, pymeshlab, sys
from load import load
name = sys.argv[1]
m = load(name); P, T = m['P'].astype(float), m['T']
f = np.fromfile(f'{name}_front.u32', np.uint32) >= 2; b = np.fromfile(f'{name}_back.u32', np.uint32) >= 2
keep = f | b; T = T[keep].copy(); flip = (b & ~f)[keep]; T[flip] = T[flip][:, [0, 2, 1]]
key = np.round(P / 0.02).astype(np.int64); _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.reshape(-1)
Pw = np.zeros((inv.max() + 1, 3)); Pw[inv] = P; Tw = inv[T]
g = (Tw[:, 0] != Tw[:, 1]) & (Tw[:, 1] != Tw[:, 2]) & (Tw[:, 0] != Tw[:, 2]); Tw = Tw[g]
def up_area(Pn, Tn):
    a, b_, c = Pn[Tn[:, 0]], Pn[Tn[:, 1]], Pn[Tn[:, 2]]; nn = np.cross(b_ - a, c - a); an = np.linalg.norm(nn, axis=1); nn /= np.maximum(an[:, None], 1e-9)
    return int(an[np.abs(nn[:, 2]) > 0.3].sum() / 2)
A0 = up_area(Pw, Tw); print('original: triangles', len(Tw), 'upward area', A0)
res = {}
def run(label, fn):
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(vertex_matrix=Pw, face_matrix=Tw.astype(np.int32))); fn(ms)
    mm = ms.current_mesh(); Pn, Tn = mm.vertex_matrix(), mm.face_matrix().astype(np.int64)
    print(f'{label:34s} triangles {len(Tn):6d}  upward area kept {up_area(Pn, Tn) / A0 * 100:5.1f}%', flush=True); res[label] = (Pn, Tn)
for tgt in ():
    run(f'edges free {tgt}', lambda ms: ms.meshing_decimation_quadric_edge_collapse(targetfacenum=tgt, preserveboundary=False, boundaryweight=0.5, preservenormal=True, preservetopology=False, optimalplacement=True, planarquadric=True, qualitythr=0.2, autoclean=True))
    run(f'edges kept {tgt}', lambda ms: ms.meshing_decimation_quadric_edge_collapse(targetfacenum=tgt, preserveboundary=True, boundaryweight=3.0, preservenormal=True, preservetopology=False, optimalplacement=True, planarquadric=True, qualitythr=0.2, autoclean=True))
for tgt in (3000, 8000):
    for bw in (200.0, 1000.0, 5000.0):
        run(f'edges heavy x{bw:g} {tgt}', lambda ms: ms.meshing_decimation_quadric_edge_collapse(targetfacenum=tgt, preserveboundary=False, boundaryweight=bw, preservenormal=True, preservetopology=False, optimalplacement=True, planarquadric=True, qualitythr=0.2, autoclean=True))
    def two(ms, tgt=tgt):
        ms.meshing_decimation_clustering(threshold=pymeshlab.PureValue(1.5))
        ms.meshing_remove_duplicate_faces(); ms.meshing_remove_null_faces()
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=tgt, preserveboundary=False, boundaryweight=10.0, preservenormal=True, preservetopology=False, optimalplacement=True, planarquadric=True, qualitythr=0.2, autoclean=True)
    pass
import pickle; pickle.dump(res, open(f'{name}_simptest4.pkl', 'wb'))
