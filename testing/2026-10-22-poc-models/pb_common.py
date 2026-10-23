# Shared helpers for the per-building try: points sampled densely on triangles
import numpy as np

def sample_tris(A, B, C, spacing):
    """Points on every triangle on a barycentric grid finer than `spacing` (edges included).
    Returns (points (m, 3), triangle index (m,))."""
    e = np.maximum.reduce([np.linalg.norm(B - A, axis=1), np.linalg.norm(C - B, axis=1), np.linalg.norm(A - C, axis=1)])
    k = np.maximum(1, np.ceil(e / spacing).astype(int))
    pts, idx = [], []
    for kk in np.unique(k):
        sel = np.nonzero(k == kk)[0]
        i, j = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing='ij')
        m = (i + j) <= kk
        u = (i[m] / kk)[None, :, None]; v = (j[m] / kk)[None, :, None]
        a, b, c = A[sel][:, None], B[sel][:, None], C[sel][:, None]
        p = a + u * (b - a) + v * (c - a)
        pts.append(p.reshape(-1, 3)); idx.append(np.repeat(sel, m.sum()))
    return np.vstack(pts), np.concatenate(idx)
