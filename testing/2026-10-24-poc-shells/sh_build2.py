# S1 shells (2026-10-23): a closed 2.5D shell per building unit, built from the unit's own visible game triangles.
#   0. the unit is turned so that its main walls lie along the raster (its walls' facing, area-weighted, modulo 90
#      degrees): straight walls come out straight instead of as stairs;
#   1. top raster (0.5 yd): the highest up-facing game triangle over each cell (points sampled every 0.2 yd); the
#      lowest down-facing one (soffits); the lowest of anything (where walls end);
#   2. the up-facing triangles grouped into planes (normals within 6 degrees, offsets within 0.35 yd); cells with only
#      walls (quays, free-standing walls, bridge sides) become strips with a fitted top;
#   3. regions: cells with the same plane and the same base (the floor, or a soffit more than 2.5 yd above it),
#      connected; bits under the level's smallest region merged into the neighbour they border most; small holes filled;
#   4. polygons: the borders between the unit's regions (and the outside) as arcs between junctions, each arc
#      simplified by Douglas-Peucker, the regions rebuilt from the simplified arcs (shared borders stay shared);
#   5. heights at the polygon corners from each region's plane; corners shared by regions whose heights there differ by
#      less than the level's snap are given one height (no slivers of wall along hips and ridges);
#   6. faces: each region's top (constrained Delaunay over its polygon, pairs joined into 4-corner faces) and walls
#      along every border where this side's height interval [base, top] is not covered by the other side's.
# The street layer (every street part of the district) is one unit with no turn; its regions reach down to the
# terrain (at most 8 yd).  Usage: python3 sh_build2.py <lod 0|1|2> [units, comma separated]
import sys, json, base64, pickle, time, numpy as np, shapely
from shapely import affinity
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from pb_common import sample_tris
UPZ, DOWNZ = 0.25, -0.25
PLANE_ANG, PLANE_OFF = np.cos(np.radians(6)), 0.35
FLOAT_GAP, HOLE_AREA = 2.5, 4.0
# levels of detail: raster cell (yd), smallest region (yd2), simplification tolerance (yd), lowest wall drawn (yd), height snap (yd)
LODS = {0: (0.25, 4, 0.35, 0.15, 0.4), 1: (0.5, 16, 0.75, 0.4, 0.8), 2: (0.5, 64, 1.5, 1.0, 1.5), 3: (0.5, 400, 3.0, 2.5, 3.0), 4: (1.0, 300, 6.0, 4.0, 6.0)}  # (4: whole 66.7-yd blocks, buildings and streets together)
LOD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
RES, MIN_AREA, SIMPLIFY, MIN_WALL, SNAP = LODS[LOD]
MIN_CELLS, HOLE_CELLS, SAMPLE = int(MIN_AREA / RES ** 2), int(HOLE_AREA / RES ** 2), RES * 0.45
ONLY = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2] else None
T0 = time.time()
d = np.load('sh_in.npz'); TRI = d['tri'].astype(float); BLD = d['bld']; ST = d['street']
g = json.load(open('sw_ground.json'))['g']; gp = np.frombuffer(base64.b64decode(g['pos']), np.float32).reshape(-1, 3).astype(float)
GS = 1600 / 3 / 128; GX0, GZ0 = gp[:, 0].min(), gp[:, 2].min(); GN = 385
GH = np.zeros((GN, GN)); GH[np.round((gp[:, 2] - GZ0) / GS).astype(int), np.round((gp[:, 0] - GX0) / GS).astype(int)] = gp[:, 1]
def ground(x, y):
    """The terrain GPS3D draws (ADT heights, water surface where higher), bilinear."""
    fx = np.clip((np.asarray(x) - GX0) / GS, 0, GN - 1.001); fz = np.clip((-np.asarray(y) - GZ0) / GS, 0, GN - 1.001)
    i, j = np.floor(fz).astype(int), np.floor(fx).astype(int); a, b = fz - i, fx - j
    return GH[i, j] * (1 - a) * (1 - b) + GH[i, j + 1] * (1 - a) * b + GH[i + 1, j] * a * (1 - b) + GH[i + 1, j + 1] * a * b
BLK = 1600 / 3 / 8
_c = TRI.mean(1); BLOCK_OF = (np.floor(_c[:, 0] / BLK).astype(int) - 230) * 1000 + (np.floor(-_c[:, 1] / BLK).astype(int) - 300)
NRM0 = np.cross(TRI[:, 1] - TRI[:, 0], TRI[:, 2] - TRI[:, 0]); AREA = np.linalg.norm(NRM0, axis=1) / 2; NRM0 /= np.maximum(2 * AREA[:, None], 1e-12)

_SF = None
def street_floor(X, Y):
    """The highest street part over each 0.5-yd cell of the district (1e9 where there is none)."""
    global _SF
    if _SF is None:
        ids = np.nonzero(ST)[0]; lo = TRI[ids].reshape(-1, 3).min(0) - 2; hi = TRI[ids].reshape(-1, 3).max(0) + 2
        nx, ny = int((hi[0] - lo[0]) / RES) + 1, int((hi[1] - lo[1]) / RES) + 1
        gg = np.full(ny * nx, -1e9); pts, _ = sample_tris(TRI[ids, 0], TRI[ids, 1], TRI[ids, 2], 0.3)
        np.maximum.at(gg, np.floor((pts[:, 1] - lo[1]) / RES).astype(int) * nx + np.floor((pts[:, 0] - lo[0]) / RES).astype(int), pts[:, 2])
        gg[gg < -1e8] = 1e9; _SF = (lo[0], lo[1], nx, ny, gg.reshape(ny, nx))
    x0, y0, nx, ny, gg = _SF
    i = np.floor((Y - y0) / RES).astype(int); j = np.floor((X - x0) / RES).astype(int)
    ok = (i >= 0) & (i < ny) & (j >= 0) & (j < nx)
    return np.where(ok, gg[np.clip(i, 0, ny - 1), np.clip(j, 0, nx - 1)], 1e9)

def planes_of(n, c, w):
    """Group up-facing triangles (normals n, centroids c, areas w) into planes: cluster per triangle, normal and offset per cluster."""
    off = np.einsum('ij,ij->i', n, c)
    dot = n @ n.T; dist = np.abs(c @ n.T - off[None, :])
    ok = (dot > PLANE_ANG) & (dist < PLANE_OFF) & (dist.T < PLANE_OFF)
    i, j = np.nonzero(np.triu(ok, 1))
    k, lab = connected_components(coo_matrix((np.ones(len(i)), (i, j)), shape=(len(n), len(n))), directed=False)
    pn = np.zeros((k, 3)); np.add.at(pn, lab, n * w[:, None]); pn /= np.linalg.norm(pn, axis=1, keepdims=True)
    po = np.bincount(lab, weights=np.einsum('ij,ij->i', pn[lab], c) * w, minlength=k) / np.bincount(lab, weights=w, minlength=k)
    return lab, pn, po

def poly_of(mask, ox, oy):
    """Cells of a mask as one (multi)polygon: rows of runs as boxes, unioned."""
    bx = []
    for r in range(mask.shape[0]):
        row = mask[r]
        if not row.any(): continue
        e = np.diff(np.concatenate([[0], row.astype(np.int8), [0]])); s, t = np.nonzero(e == 1)[0], np.nonzero(e == -1)[0]
        for a, b in zip(s, t): bx.append(shapely.box(ox + a * RES, oy + r * RES, ox + b * RES, oy + (r + 1) * RES))
    return shapely.union_all(bx)

def main_angle(ids):
    """The unit's main wall direction (radians, modulo 90 degrees), from its steep triangles' facing, area-weighted."""
    s = ids[np.abs(NRM0[ids, 2]) <= UPZ]
    if len(s) == 0: return 0.0
    a = np.arctan2(NRM0[s, 1], NRM0[s, 0]); w = AREA[s] * np.hypot(NRM0[s, 0], NRM0[s, 1])
    return float(np.arctan2((w * np.sin(4 * a)).sum(), (w * np.cos(4 * a)).sum()) / 4)

def build_unit(u):
    deck = u == -1
    if u <= -2: ids = np.nonzero(BLOCK_OF == -2 - u)[0]   # a block (level 4): every part whose middle is in it
    else: ids = np.nonzero(ST)[0] if deck else np.nonzero((BLD == u) & ~ST)[0]
    if len(ids) == 0: return None
    th = 0.0 if deck else main_angle(ids)
    c0 = TRI[ids].reshape(-1, 3).mean(0)
    cs, sn = np.cos(-th), np.sin(-th)
    def turn(p):   # world -> the unit's frame (about c0, by -th)
        q = p.copy(); x, y = p[..., 0] - c0[0], p[..., 1] - c0[1]
        q[..., 0], q[..., 1] = c0[0] + cs * x - sn * y, c0[1] + sn * x + cs * y; return q
    def back(x, y):   # the unit's frame -> world
        x, y = x - c0[0], y - c0[1]
        return c0[0] + cs * x + sn * y, c0[1] - sn * x + cs * y
    T = turn(TRI[ids]); Nn = turn(NRM0[ids] + c0) - c0; Nn[:, 2] = NRM0[ids, 2]
    A, B, C = T[:, 0], T[:, 1], T[:, 2]
    lo = T.reshape(-1, 3).min(0) - 1; hi = T.reshape(-1, 3).max(0) + 1
    ox, oy = np.floor(lo[0] / RES) * RES, np.floor(lo[1] / RES) * RES
    nx, ny = int(np.ceil((hi[0] - ox) / RES)) + 1, int(np.ceil((hi[1] - oy) / RES)) + 1
    up = np.nonzero(Nn[:, 2] > UPZ)[0]; dn = np.nonzero(Nn[:, 2] < DOWNZ)[0]; sp = np.nonzero(np.abs(Nn[:, 2]) <= UPZ)[0]
    def cells(p): return np.floor((p[:, 1] - oy) / RES).astype(int) * nx + np.floor((p[:, 0] - ox) / RES).astype(int)
    def raster_max(tt):
        top = np.full(ny * nx, -1e9); tri = np.full(ny * nx, -1)
        if len(tt):
            pts, ti = sample_tris(A[tt], B[tt], C[tt], SAMPLE); cell = cells(pts)
            o = np.lexsort((pts[:, 2], cell)); last = np.r_[cell[o][1:] != cell[o][:-1], True]
            top[cell[o][last]] = pts[o][last, 2]; tri[cell[o][last]] = ti[o][last]
        return top.reshape(ny, nx), tri.reshape(ny, nx)
    def raster_min(tt, sp_=None):
        sp_ = sp_ or SAMPLE
        r = np.full(ny * nx, 1e9)
        if len(tt): p, _ = sample_tris(A[tt], B[tt], C[tt], sp_); np.minimum.at(r, cells(p), p[:, 2])
        return r.reshape(ny, nx)
    top, toptri = raster_max(up); stop, _ = raster_max(sp)
    low = raster_min(np.arange(len(T)), max(SAMPLE, 0.3)); bot = raster_min(dn)
    if len(up): lab, pn, po = planes_of(Nn[up], T[up].mean(1), AREA[ids][up])
    else: lab, pn, po = np.zeros(0, int), np.zeros((0, 3)), np.zeros(0)
    have = toptri >= 0
    gx, gy = ox + (np.arange(nx) + 0.5) * RES, oy + (np.arange(ny) + 0.5) * RES
    GX, GY = np.meshgrid(gx, gy); WX, WY = back(GX, GY); gr = ground(WX, WY)
    key = np.where(have, lab[np.maximum(toptri, 0)] if len(lab) else 0, -1) * 2
    wl = (stop > -1e8) & ~have
    if wl.any():   # walls with nothing on top: a strip one cell wider, its top a plane fitted to the walls' highest points
        st2 = ndimage.grey_dilation(np.where(wl, stop, -1e9), size=3)
        wl2 = ndimage.binary_dilation(wl) & ~have
        stop2 = np.where(wl, stop, st2)
        cc, m = ndimage.label(wl2, structure=np.ones((3, 3)))
        pn, po = list(pn), list(po)
        for c in range(1, m + 1):
            mm = cc == c
            X = np.stack([GX[mm], GY[mm], np.ones(mm.sum())], 1); h = stop2[mm]
            if mm.sum() >= 3:
                coef = np.linalg.lstsq(X, h, rcond=None)[0]
                g_ = np.hypot(coef[0], coef[1])
                if g_ > 1: coef[:2] /= g_
                coef[2] = (h - X[:, :2] @ coef[:2]).max() if mm.sum() < 12 else np.median(h - X[:, :2] @ coef[:2])
            else: coef = np.array([0, 0, h.max()])
            L = np.sqrt(coef[0] ** 2 + coef[1] ** 2 + 1)
            pn.append(np.array([-coef[0], -coef[1], 1]) / L); po.append(coef[2] / L)
            key[mm] = (len(pn) - 1) * 2
        pn, po = np.array(pn), np.array(po)
        have = have | wl2
        top = np.where(wl2, stop2, top)
    sf = street_floor(WX, WY) if not deck else np.full_like(GX, 1e9)
    floor = ndimage.minimum_filter(np.minimum(sf, low), size=int(4.5 / RES) | 1)
    flt = have & (bot < top - 0.3) & (bot > floor + FLOAT_GAP) & (not deck)
    key = np.where(have, key + flt, -1)
    filled = ndimage.binary_fill_holes(have)
    holes, nh = ndimage.label(filled & ~have)
    if nh:
        hs = ndimage.sum(np.ones_like(holes), holes, np.arange(1, nh + 1))
        small = np.isin(holes, 1 + np.nonzero(hs <= HOLE_CELLS)[0])
        _, (ii, jj) = ndimage.distance_transform_edt(~have, return_indices=True)
        key = np.where(small, key[ii, jj], key); have = have | small
    comp = np.zeros((ny, nx), int); ckey = [None]; n = 0
    for k in np.unique(key[have]):
        cc, m = ndimage.label(key == k)
        comp[cc > 0] = cc[cc > 0] + n; ckey += [k] * m; n += m
    for _ in range(4):
        sizes = np.bincount(comp.ravel(), minlength=n + 1); changed = False
        for c in np.argsort(sizes):
            if c == 0 or sizes[c] == 0 or sizes[c] >= MIN_CELLS: continue
            m = comp == c; ring = ndimage.binary_dilation(m) & ~m
            nb = comp[ring]; nb = nb[nb > 0]
            if len(nb) == 0:
                if sizes[c] * RES * RES < 1.0: comp[m] = 0; sizes[c] = 0   # (isolated bits over 1 yd2 stay: no unit vanishes)
                continue
            t = np.bincount(nb).argmax(); comp[m] = t; sizes[t] += sizes[c]; sizes[c] = 0; changed = True
        if not changed: break
    regs = [c for c in np.unique(comp) if c > 0]
    if not regs: return None
    unit_lo = float(T[..., 2].min())
    polys = [poly_of(comp == c, ox, oy) for c in regs]
    simp = arc_simplify(polys, SIMPLIFY)
    out = []
    for c, p in zip(regs, simp):
        k = ckey[c]; pl = k // 2; fl = k % 2
        m = comp == c
        if p.is_empty or p.area < 0.5: continue
        tv = top[m]; tv = tv[tv > -1e8]
        r = dict(poly=p, n=pn[pl], off=po[pl], float=bool(fl), cells=int(m.sum()),
                 tmin=float(tv.min()) - 0.3 if len(tv) else -1e9, tmax=float(tv.max()) + 0.3 if len(tv) else 1e9)
        if deck: base = max(float(gr[m].min()) - 0.5, float(top_h(r, GX[m], GY[m]).min()) - 8)
        elif fl and (bot[m] < 1e8).any(): base = min(float(np.median(bot[m][bot[m] < 1e8])), float(top_h(r, GX[m], GY[m]).min()) - 0.5)
        else: base = float(min(sf[ndimage.binary_dilation(m, iterations=int(2 / RES))].min(), low[ndimage.binary_dilation(m, iterations=int(1 / RES))].min())) - 0.3
        r['base'] = max(base, unit_lo - 0.5)   # (never below the unit's own lowest geometry)
        out.append(r)
    return dict(unit=int(u), deck=deck, regions=out, th=th, c0=c0, back=back, raw=polys, comp=comp, grid=(ox, oy, nx, ny), ids=ids)

def arc_simplify(polys, tol):
    """A coverage simplified arc by arc (Douglas-Peucker, junctions kept); falls back to coverage_simplify."""
    try:
        lines = shapely.line_merge(shapely.union_all([p.boundary for p in polys]))
        arcs = list(lines.geoms) if hasattr(lines, 'geoms') else [lines]
        out = []
        for a in arcs:
            cs = np.asarray(a.coords)
            if len(cs) > 3 and np.allclose(cs[0], cs[-1]):   # a closed loop with no junction: keep it a ring
                s_ = shapely.simplify(shapely.Polygon(cs), tol, preserve_topology=True)
                out.append(s_.exterior if not s_.is_empty and s_.geom_type == 'Polygon' else a)
            else: out.append(shapely.simplify(a, tol, preserve_topology=False))
        faces = list(shapely.polygonize(list(shapely.union_all(out).geoms) if hasattr(shapely.union_all(out), 'geoms') else [shapely.union_all(out)]).geoms)
        own = [[] for _ in polys]
        tree = shapely.STRtree(polys)
        for f in faces:
            if f.area < 1e-6: continue
            cand = tree.query(f)
            if len(cand) == 0: continue
            ov = [shapely.intersection(f, polys[i]).area for i in cand]
            if max(ov) < 0.3 * f.area: continue   # (a face outside every region: a notch the simplification closed)
            own[cand[int(np.argmax(ov))]].append(f)
        res = [shapely.union_all(o) if o else shapely.Polygon() for o in own]
        tot0 = sum(p.area for p in polys); tot1 = sum(p.area for p in res)
        if abs(tot1 - tot0) > 0.1 * tot0 + 2 or any(not r.is_valid for r in res): raise ValueError('arc simplification changed the area too much')
        return res
    except Exception:
        return list(shapely.coverage_simplify(np.array(polys, dtype=object), tol * 2))

def top_h(r, x, y):
    """A region's top at (x, y): its plane, kept within the heights its cells really have."""
    n, off = r['n'], r['off']; h = (off - n[0] * x - n[1] * y) / n[2]
    return np.clip(h, r.get('tmin', -1e9), r.get('tmax', 1e9))

def faces_of(U):
    """Tops and walls of a unit's regions, in world coordinates. Each face: corners (k, 3), counter-clockwise seen
    from outside; 'reg' its region, 'kind' roof or wall."""
    regs = U['regions']; back = U['back']
    rings, edges = [], {}
    K = lambda p: (round(p[0], 4), round(p[1], 4))
    for ri, r in enumerate(regs):
        p = shapely.orient_polygons(r['poly'])
        for g_ in (p.geoms if p.geom_type == 'MultiPolygon' else [p]):
            for ring in [g_.exterior] + list(g_.interiors):
                cs = np.asarray(ring.coords)[:-1]
                if len(cs) < 3: continue
                rings.append((ri, cs))
                for a, b in zip(cs, np.roll(cs, -1, 0)): edges[(K(a), K(b))] = ri
    # corner heights per region, snapped together where regions meet at nearly the same height
    hts = {}
    for ri, cs in rings:
        for a in cs: hts.setdefault(K(a), {})[ri] = float(top_h(regs[ri], a[0], a[1]))
    for k, dct in hts.items():
        if len(dct) < 2: continue
        items = sorted(dct.items(), key=lambda t: t[1]); grp = [items[0]]
        def flush(grp):
            m = sum(h for _, h in grp) / len(grp)
            for r_, _ in grp: dct[r_] = m
        for it in items[1:]:
            if it[1] - grp[-1][1] < SNAP: grp.append(it)
            else: flush(grp); grp = [it]
        flush(grp)
    H = lambda ri, p: hts[K(p)][ri] if ri in hts.get(K(p), {}) else float(top_h(regs[ri], p[0], p[1]))
    faces = []
    def add(kind, ri, corners):
        c = np.array(corners, float); x, y = back(c[:, 0], c[:, 1]); c[:, 0], c[:, 1] = x, y
        faces.append(dict(kind=kind, reg=ri, c=c))
    for ri, cs in rings:
        r = regs[ri]
        for a, b in zip(cs, np.roll(cs, -1, 0)):
            if np.hypot(*(b - a)) < 1e-6: continue
            other = edges.get((K(b), K(a)))
            t = np.array([H(ri, a), H(ri, b)]); bb = np.array([r['base'], r['base']])
            if other is None: parts = [(bb, t)]
            else:
                o = regs[other]; ot = np.array([H(other, a), H(other, b)]); obb = np.array([o['base'], o['base']])
                parts = [(np.maximum(bb, ot), t), (bb, np.minimum(t, obb))]
            for lo, hi in parts:
                dlt = hi - lo
                if (dlt <= MIN_WALL).all() or dlt.max() <= 0.05: continue
                if (dlt > 0.05).all():
                    add('wall', ri, [(a[0], a[1], lo[0]), (b[0], b[1], lo[1]), (b[0], b[1], hi[1]), (a[0], a[1], hi[0])])
                else:
                    s = dlt[0] / (dlt[0] - dlt[1]); m = a + s * (b - a); hm = lo[0] + s * (lo[1] - lo[0])
                    add('wall', ri, [(a[0], a[1], lo[0]), (m[0], m[1], hm), (a[0], a[1], hi[0])] if dlt[0] > 0 else [(m[0], m[1], hm), (b[0], b[1], lo[1]), (b[0], b[1], hi[1])])
    for ri, r in enumerate(regs):
        tl = []
        for t in shapely.constrained_delaunay_triangles(r['poly']).geoms:
            cs = np.asarray(shapely.orient_polygons(t).exterior.coords)[:-1]
            tl.append(np.array([(x, y, H(ri, (x, y))) for x, y in cs]))
        for q in join_quads(tl): add('roof', ri, q)
    return faces

def cross2(a, b): return a[0] * b[1] - a[1] * b[0]
def tri_area(t): return abs(cross2(t[1][:2] - t[0][:2], t[2][:2] - t[0][:2])) / 2
def convex(q):
    s = [cross2(q[(i + 1) % 4][:2] - q[i][:2], q[(i + 2) % 4][:2] - q[(i + 1) % 4][:2]) for i in range(4)]
    return all(x > 1e-6 for x in s) or all(x < -1e-6 for x in s)
def join_quads(tl):
    """Pairs of triangles sharing an edge joined into convex 4-corner faces."""
    used = [False] * len(tl); out = []
    key = lambda p: (round(p[0], 4), round(p[1], 4))
    emap = {}
    for i, t in enumerate(tl):
        for e in range(3): emap.setdefault(frozenset((key(t[e]), key(t[(e + 1) % 3]))), []).append((i, e))
    for i in sorted(range(len(tl)), key=lambda i: -tri_area(tl[i])):
        if used[i]: continue
        t = tl[i]; best = None
        for e in sorted(range(3), key=lambda e: -np.hypot(*(t[(e + 1) % 3][:2] - t[e][:2]))):
            for j, f in emap[frozenset((key(t[e]), key(t[(e + 1) % 3])))]:
                if j == i or used[j]: continue
                q = np.array([t[e], tl[j][(f + 2) % 3], t[(e + 1) % 3], t[(e + 2) % 3]])
                if convex(q): best = (j, q); break
            if best: break
        used[i] = True
        if best: used[best[0]] = True; out.append(best[1])
        else: out.append(t)
    return out

if __name__ == '__main__':
    units = ONLY or ([-2 - int(b) for b in np.unique(BLOCK_OF)] if LOD == 4 else [int(u) for u in np.unique(BLD[~ST])] + [-1])
    res = []; nf = {'wall': 0, 'roof': 0}; quads = tris = regions = 0
    for i, u in enumerate(units):
        U = build_unit(u)
        if U is None: continue
        U['faces'] = faces_of(U)
        for f in U['faces']: nf[f['kind']] += 1; quads += len(f['c']) == 4; tris += len(f['c']) == 3
        regions += len(U['regions'])
        U['regions'] = [dict(r, poly=affinity.rotate(r['poly'], U['th'], origin=(U['c0'][0], U['c0'][1]), use_radians=True)) for r in U['regions']]
        for k in ('back', 'raw', 'comp'): U.pop(k)
        res.append(U)
    pickle.dump(res, open(f'sh_shells_{LOD}.pkl' if not ONLY else 'sh_shells_test.pkl', 'wb'))
    nb = np.array([len(U['faces']) for U in res if U['unit'] >= 0])
    print(json.dumps({'lod': LOD, 'units': len(res), 'regions': regions, 'faces': sum(nf.values()), **nf, 'quads': quads, 'tris': tris,
                      'bld_faces_median': float(np.median(nb)), 'bld_faces_mean': round(float(nb.mean()), 1), 'street_faces': sum(len(U['faces']) for U in res if U['unit'] < 0), 's': round(time.time() - T0, 1)}))
