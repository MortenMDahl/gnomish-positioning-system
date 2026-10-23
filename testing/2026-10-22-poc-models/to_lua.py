# The simplified models as Lua data for PocModels.lua: vertices (GPS world x, y, h), triangles (1-based, wound so
# faces seen from above are counter-clockwise from above, as GPS3D's culling wants), colours per triangle
import sys, numpy as np

def subdivide(V, T, C=None, UV=None, L=10.0):
    """Split every triangle's longest edge until no edge is longer than L yd (so painter's sorting sees local depth).
    C: per-triangle colours (copied); UV: per-corner UVs (n, 3, 2), interpolated."""
    V = [tuple(v) for v in V]; out_t, out_c, out_uv = [], [], []
    stack = [(tuple(t), (C[i] if C is not None else None), (UV[i] if UV is not None else None)) for i, t in enumerate(T)]
    mid = {}
    while stack:
        t, c, uv = stack.pop()
        p = [np.array(V[k]) for k in t]
        e = [np.linalg.norm(p[(i + 1) % 3] - p[i]) for i in range(3)]
        i = int(np.argmax(e))
        if e[i] <= L:
            out_t.append(t); out_c.append(c); out_uv.append(uv); continue
        a, b = t[i], t[(i + 1) % 3]; o = t[(i + 2) % 3]
        key = (min(a, b), max(a, b))
        if key not in mid: V.append(tuple((p[i] + p[(i + 1) % 3]) / 2)); mid[key] = len(V) - 1
        m = mid[key]
        if uv is not None:
            um = (uv[i] + uv[(i + 1) % 3]) / 2
            u1 = np.array([uv[i], um, uv[(i + 2) % 3]]); u2 = np.array([um, uv[(i + 1) % 3], uv[(i + 2) % 3]])
        else: u1 = u2 = None
        stack.append(((a, m, o), c, u1)); stack.append(((m, b, o), c, u2))
    return np.array(V), np.array(out_t), (np.array(out_c) if C is not None else None), (np.array(out_uv) if UV is not None else None)

out = ['-- Proof of concept data (branch poc-models): simplified building models, see PocModels.lua', 'local _, ns = ...', 'ns.PocData = ns.PocData or {}']
info = {}
for name, mp in (('stormwind', 0), ('orgrimmar', 1)):
    out.append(f'ns.PocData.{name} = {{}}')
    for size in (3000, 8000, 20000):
        z = np.load(f'{sys.argv[1]}/{name}_{size}.npz'); Pv, T, C = z['P'], z['T'].copy(), z['col']
        n = np.cross(Pv[T[:, 1]] - Pv[T[:, 0]], Pv[T[:, 2]] - Pv[T[:, 0]]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        steep = np.abs(n[:, 2]) > 0.5
        up = (n[steep, 2] > 0).mean()
        if up < 0.5: T = T[:, [0, 2, 1]]
        n0 = len(T)  # (not cut: 10-yd pieces made these 4 to 6 times bigger)
        info[(name, size)] = (n0, len(T), round(float(up), 3))
        f = lambda a, fmt: ','.join(fmt % x for x in a)
        out.append(f'ns.PocData.{name}[{size}] = {{ map = {mp}, v = {{{f(Pv.reshape(-1), "%.2f")}}}, t = {{{f(T.reshape(-1) + 1, "%d")}}}, c = {{{f(C.reshape(-1), "%.3f")}}} }}')
open('prototypes/GPS3D/PocData.lua', 'w').write('\n'.join(out) + '\n')
print(info)
# textured close-ups: the original visible triangles within 80 yd of the middle, with the game's UVs and texture IDs
sys.path.insert(0, sys.argv[1])
from load import load
import os
os.chdir(sys.argv[1])
extra = []
for name, mp in (('stormwind', 0), ('orgrimmar', 1)):
    m = load(name); seen = np.fromfile(f'{name}_seen.u32', np.uint32) >= 2
    cx, cy = m['meta']['cx'], -m['meta']['cz']
    T = m['T'][seen]; F = m['TEX'][seen]
    cen = m['P'][T].mean(1)
    k = np.hypot(cen[:, 0] - cx, cen[:, 1] - cy) < 80
    T, F = T[k], F[k]
    UVc = m['UV'][T].astype(float)
    used, inv = np.unique(T.reshape(-1), return_inverse=True)
    V = m['P'][used].astype(float); T2 = inv.reshape(-1, 3)
    Fi = np.arange(len(T2))
    V, T2, Fi, UVc = subdivide(V, T2, C=Fi, UV=UVc)
    F = F[Fi]; T2 = T2 + 1; UV = UVc.reshape(-1)
    f = lambda a, fmt: ','.join(fmt % x for x in a)
    extra.append(f'ns.PocData.{name}.tex = {{ map = {mp}, v = {{{f(V.reshape(-1), "%.2f")}}}, t = {{{f(T2.reshape(-1), "%d")}}}, uv = {{{f(UV, "%.4f")}}}, f = {{{f(F, "%d")}}} }}')
    print(name, 'textured close-up triangles', len(T2), 'from', len(Fi) and len(m['T'][seen][k]))
os.chdir('/home/claude/wt/poc')
open('prototypes/GPS3D/PocData.lua', 'a').write('\n'.join(extra) + '\n')
