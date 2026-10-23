# Per-building try, step 2: a closed outer shell for a region, from ALL of the game's triangles there (no visibility
# filter). Voxels (0.5 yd) touched by a triangle = surface; everything below a column's lowest surface = ground (solid);
# the outside = what can be reached from the top/sides without squeezing through gaps under 3 yd (closing, r = 3
# voxels); solid = the rest. The shell's surface is placed with the true distance to the original triangles
# (narrow band), so slopes come out smooth, not stepped.
import sys, json, numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure
from load import load
from pb_common import sample_tris

def shell(P, T, x0, y0, half, vox=0.5, r=3, zmax=None, sigma=0.8, snap=0.75, cap=True):
    A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    cen = (A + B + C) / 3
    pad = r + 3
    sel = (np.abs(cen[:, 0] - x0) < half + 2) & (np.abs(cen[:, 1] - y0) < half + 2)
    if zmax is not None: sel &= cen[:, 2] < zmax
    A, B, C = A[sel], B[sel], C[sel]
    pts, _ = sample_tris(A, B, C, vox * 0.3)
    k = (np.abs(pts[:, 0] - x0) <= half) & (np.abs(pts[:, 1] - y0) <= half)
    pts = pts[k]
    zlo, zhi = pts[:, 2].min(), pts[:, 2].max()
    org = np.array([x0 - half - pad * vox, y0 - half - pad * vox, zlo - pad * vox])
    shp = (np.array([2 * half, 2 * half, zhi - zlo]) / vox).astype(int) + 2 * pad + 1
    S = np.zeros(shp, bool)
    q = ((pts - org) / vox).astype(int)
    S[q[:, 0], q[:, 1], q[:, 2]] = True
    # ground: below each column's lowest surface voxel (columns with none: below the neighbourhood's lowest)
    has = S.any(2)
    low = S.argmax(2)
    _, (ni, nj) = ndimage.distance_transform_edt(~has, return_indices=True)
    low = low[ni, nj]                                                           # (empty columns: nearest column's)
    zz = np.arange(shp[2])[None, None, :]
    G = zz < low[..., None]
    G[:, :, :pad] = True
    G &= ndimage.binary_dilation(has, iterations=r + 1)[..., None]   # (ground only under the geometry, so the shell closes)
    blocked = S | G
    # sealed pits in the top surface (openings in roofs with nothing under them, enclosed on all sides) are capped at
    # their rim: pit filling on the top height map (only basins that don't drain to the region's edge are filled)
    if cap:
        from skimage.morphology import reconstruction
        top = np.where(blocked.any(2), shp[2] - 1 - np.argmax(blocked[:, :, ::-1], 2), 0).astype(float)
        seed2 = top.copy(); seed2[1:-1, 1:-1] = top.max()
        filled = reconstruction(seed2, top, method='erosion')
        pit = (filled - top) * vox > 1.5
        pl, pn = ndimage.label(pit)
        parea = ndimage.sum(np.ones_like(pl), pl, np.arange(1, pn + 1)) * vox * vox
        pit = np.isin(pl, np.nonzero(parea <= 200)[0] + 1)     # (only small sealed openings, not open ground)
        zz2 = np.arange(shp[2])[None, None, :]
        blocked |= pit[..., None] & (zz2 <= filled[..., None]) & (zz2 > top[..., None])
        capped = int(pit.sum())
    else: capped = 0; pit = np.zeros(shp[:2], bool)
    st = ndimage.generate_binary_structure(3, 1)
    D = ndimage.binary_dilation(blocked, st, iterations=r)
    free = ~D
    seed = np.zeros(shp, bool); seed[:, :, -1] = True; seed[0] = seed[-1] = True; seed[:, 0] = seed[:, -1] = True
    seed &= free
    lab, _ = ndimage.label(free, st)
    ext_ids = np.unique(lab[seed]); ext_ids = ext_ids[ext_ids > 0]
    E = np.isin(lab, ext_ids)
    E = ndimage.binary_dilation(E, st, iterations=r) & ~blocked
    solid = ~E
    # smooth the solid a little (no voxel steps), then put each shell vertex onto the original surface if it is near
    sm = ndimage.gaussian_filter(solid.astype(np.float32), sigma)
    tree = cKDTree(pts)
    # (the columns at the region's sides are left open: these edges are cut later)
    sm = np.pad(sm, 1)                                              # (closed at the array's edges too)
    V, F, _, _ = measure.marching_cubes(sm, 0.5, spacing=(vox, vox, vox), allow_degenerate=False)
    V = V + org + 0.5 * vox - vox
    d, i = tree.query(V, k=1, workers=-1)
    near = d < snap
    vi = np.clip(((V - org) / vox).astype(int), 0, np.array(shp) - 1)
    near &= ~ndimage.binary_dilation(pit, iterations=2)[vi[:, 0], vi[:, 1]]   # (caps stay flat)
    V[near] = pts[i[near]]
    # outward winding (GPS: cross(B-A, C-A) points out of the solid)
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    c = V[F].mean(1)
    probe = ((c + 0.6 * n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9) - org) / vox).astype(int)
    probe = np.clip(probe, 0, np.array(shp) - 1)
    outside = ~solid[probe[:, 0], probe[:, 1], probe[:, 2]]
    if outside.mean() < 0.5: F = F[:, [0, 2, 1]]
    return V, F, dict(vox=vox, r=r, shape=[int(s) for s in shp], surface_vox=int(S.sum()), solid_vox=int(solid.sum()), tris_in=int(sel.sum()), snapped=float(near.mean()), capped_cols=capped, winding_ok=float(max(outside.mean(), 1 - outside.mean())))

if __name__ == '__main__':
    x0, y0, half = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    out = sys.argv[4]
    m = load('stormwind')
    V, F, info = shell(m['P'].astype(float), m['T'], x0, y0, half)
    np.savez_compressed(out, V=V, F=F)
    info['mc_tris'] = len(F); print(json.dumps(info))
