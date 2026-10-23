# 4-corner parts (2026-10-23): in each facing group, two triangles of the same piece that share an edge, lie in one
# plane (normals within 1 degree, 4th corner within 0.03 yd of the plane), make a convex 4-sided shape and share one
# texture mapping (the 4th corner's UV within 0.01 of the first triangle's mapping) become one part with 4 corners
# (a, b, c, d around the edge, wound as the first triangle). Greedy, biggest pieces first.
import numpy as np

def merge_quads(lst, T2, V, UVc, PC, BF):
    """lst: part indices (rows of T2) of one group, in drawing order. Returns a list of parts:
    (corners tuple (3 or 4 vertex ids), uv (6 or 8 floats), source part index for texture/area lookups)."""
    pos = {int(p): i for i, p in enumerate(lst)}
    edges = {}
    for p in lst:
        t = T2[p]
        for k in range(3):
            e = (int(min(t[k], t[(k + 1) % 3])), int(max(t[k], t[(k + 1) % 3])))
            edges.setdefault(e, []).append(int(p))
    used = set(); out = []; stats = {'pairs': 0, 'rej_plane': 0, 'rej_convex': 0, 'rej_uv': 0, 'rej_wind': 0}
    def normal(t):
        n = np.cross(V[t[1]] - V[t[0]], V[t[2]] - V[t[0]]); l = np.linalg.norm(n); return n / l if l > 0 else n
    for p in lst:
        p = int(p)
        if p in used: continue
        t = T2[p]; best = None
        for k in range(3):
            y, z, x = int(t[k]), int(t[(k + 1) % 3]), int(t[(k + 2) % 3])     # tri1 = (x, y, z) wound; shared edge y-z
            for q in edges[(min(y, z), max(y, z))]:
                if q == p or q in used or PC[q] != PC[p] or BF[q] != BF[p]: continue
                tq = [int(v) for v in T2[q]]
                pv = [v for v in tq if v != y and v != z]
                if len(pv) != 1: continue
                pv = pv[0]
                # tri2 must run z -> y (the opposite way along the shared edge): consistently wound
                iz = tq.index(z)
                if tq[(iz + 1) % 3] != y: stats['rej_wind'] += 1; continue
                n1 = normal([x, y, z]); n2 = normal(tq)
                if n1 @ n2 < np.cos(np.radians(1.0)) or abs((V[pv] - V[x]) @ n1) > 0.03: stats['rej_plane'] += 1; continue
                # convex: corners x, y, pv, z in order; every turn the same way (and not straight)
                Q = [V[x], V[y], V[pv], V[z]]; ok = True
                for i in range(4):
                    c = np.cross(Q[(i + 1) % 4] - Q[i], Q[(i + 2) % 4] - Q[(i + 1) % 4]) @ n1
                    if c <= 1e-4 * np.linalg.norm(Q[(i + 1) % 4] - Q[i]) * np.linalg.norm(Q[(i + 2) % 4] - Q[(i + 1) % 4]): ok = False; break
                if not ok: stats['rej_convex'] += 1; continue
                # one texture mapping: the 4th corner's UV from tri1's affine mapping
                u1 = UVc[p]; vid = [int(v) for v in t]
                uvof = {vid[i]: u1[i] for i in range(3)}
                A, B, C = V[x], V[y], V[z]; M = np.stack([B - A, C - A], 1); st = np.linalg.lstsq(M, V[pv] - A, rcond=None)[0]
                pred = uvof[x] + st[0] * (uvof[y] - uvof[x]) + st[1] * (uvof[z] - uvof[x])
                uq = {int(T2[q][i]): UVc[q][i] for i in range(3)}
                # tri2's UVs at the shared corners must match tri1's (the same mapping, not a seam), and its 4th corner the prediction
                if np.abs(uq[y] - uvof[y]).max() > 0.01 or np.abs(uq[z] - uvof[z]).max() > 0.01 or np.abs(uq[pv] - pred).max() > 0.01:
                    stats['rej_uv'] += 1; continue
                best = (q, (x, y, pv, z), np.concatenate([uvof[x], uvof[y], uq[pv], uvof[z]])); break
            if best: break
        if best:
            q, corners, uv = best; used.add(p); used.add(q); stats['pairs'] += 1
            out.append((corners, uv, p))
        else:
            used.add(p); out.append((tuple(int(v) for v in t), np.asarray(UVc[p]).reshape(-1), p))
    return out, stats
