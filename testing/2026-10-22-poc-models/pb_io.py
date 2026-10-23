# Mesh -> JSON groups for pb_view.html (GPS x east, y north, h up -> three x, y up, z = -north); camera helper
import json, base64, numpy as np
def b64(a): return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()
def groups(V, F, UV=None, FD=None, grey=0.85):
    """V (n,3) GPS coords, F (m,3); UV (m,6) per-corner or None; FD (m,) texture file IDs or None (grey)."""
    tri = V[F]                                       # (m,3,3)
    g3 = np.stack([tri[..., 0], tri[..., 2], -tri[..., 1]], -1).astype(np.float32)
    if FD is None: return [{'f': 0, 'grey': grey, 'pos': b64(g3.reshape(-1))}]
    out = []
    for f in np.unique(FD):
        k = FD == f
        out.append({'f': int(f), 'pos': b64(g3[k].reshape(-1)), 'uv': b64(UV[k].astype(np.float32).reshape(-1))})
    return out
def save(path, gr): json.dump(gr, open(path, 'w'))
def cam(x=16426, y=-25896, th=117.5, dist=200, yaw=25, pitch=45):
    yw, p = np.radians(yaw), np.radians(pitch)
    f = np.array([np.sin(yw) * np.cos(p), np.cos(yw) * np.cos(p), -np.sin(p)])
    c = np.array([x, y, th]) - f * dist
    return [float(v) for v in c] + [float(v) for v in f]
