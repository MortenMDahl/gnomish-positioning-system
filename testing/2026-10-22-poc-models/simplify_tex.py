# Simplification that keeps the game's texture mapping: the visible triangles split by texture, each part welded
# and decimated with MeshLab's texture-aware quadric collapse (wedge UVs), the targets shared by triangle count
import sys, json, numpy as np, pymeshlab
from load import load
for name in sys.argv[1:]:
    m = load(name); P, T, TEX, UV = m['P'].astype(np.float64), m['T'], m['TEX'], m['UV'].astype(np.float64)
    seen = np.fromfile(f'{name}_seen.u32', np.uint32) >= 2
    T, TEX = T[seen], TEX[seen]
    for total in (3000, 8000):
        outP, outT, outUV, outF = [], [], [], []; off = 0; groups = 0
        fds, counts = np.unique(TEX, return_counts=True)
        for fd, cnt in zip(fds, counts):
            sel = TEX == fd; Tg = T[sel]
            tgt = max(2, int(round(total * cnt / len(T))))
            key = np.round(P[Tg.reshape(-1)] / 0.02).astype(np.int64)
            _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
            Vg = P[Tg.reshape(-1)][first]; Fg = inv.reshape(-1, 3).astype(np.int32)
            Wg = UV[Tg.reshape(-1)].reshape(-1, 2)
            good = (Fg[:, 0] != Fg[:, 1]) & (Fg[:, 1] != Fg[:, 2]) & (Fg[:, 0] != Fg[:, 2])
            Fg = Fg[good]; Wg = Wg.reshape(-1, 3, 2)[good].reshape(-1, 2)
            if len(Fg) > tgt:
                with open('part.mtl', 'w') as f: f.write('newmtl m\nmap_Kd dummy.png\n')
                with open('part.obj', 'w') as f:
                    f.write('mtllib part.mtl\nusemtl m\n')
                    f.write(''.join('v %.4f %.4f %.4f\n' % tuple(v) for v in Vg))
                    f.write(''.join('vt %.5f %.5f\n' % tuple(w) for w in Wg))
                    f.write(''.join('f %d/%d %d/%d %d/%d\n' % (a + 1, 3 * k + 1, b + 1, 3 * k + 2, c + 1, 3 * k + 3) for k, (a, b, c) in enumerate(Fg)))
                ms = pymeshlab.MeshSet(); ms.load_new_mesh('part.obj')
                ms.meshing_decimation_quadric_edge_collapse_with_texture(targetfacenum=tgt, qualitythr=0.3, extratcoordw=1.0, preserveboundary=False, boundaryweight=1.0, optimalplacement=True, preservenormal=True, planarquadric=True)
                mm = ms.current_mesh(); Vg = mm.vertex_matrix(); Fg = mm.face_matrix(); Wg = mm.wedge_tex_coord_matrix()
            outP.append(Vg); outT.append(Fg + off); outUV.append(Wg.reshape(-1, 6)); outF.append(np.full(len(Fg), fd)); off += len(Vg); groups += 1
        Pn, Tn, UVn, Fn = np.vstack(outP), np.vstack(outT), np.vstack(outUV), np.concatenate(outF)
        np.savez_compressed(f'{name}_tex{total}.npz', P=Pn, T=Tn, UV=UVn, F=Fn)
        print(name, total, 'textures', groups, 'triangles', len(Tn))
