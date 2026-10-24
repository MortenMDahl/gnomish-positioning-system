# S1 shells (2026-10-23): a closed 2.5D shell per building unit, built from the unit's own visible game triangles.
#   1. top raster (0.5 yd): the highest up-facing game triangle over each cell (points sampled every 0.2 yd), and the
#      lowest down-facing one (soffits: eaves, jetties, bridge decks);
#   2. the up-facing triangles grouped into planes (normals within 6 degrees, offsets within 0.35 yd);
#   3. regions: cells with the same plane and the same base (ground, or a soffit more than 2.5 yd above the ground),
#      connected; bits under 2 yd2 merged into their longest-bordering neighbour, small holes filled;
#   4. polygons: each region's cells as a polygon, the unit's regions simplified together (shapely coverage_simplify:
#      shared borders stay shared, so no gaps or overlaps appear);
#   5. faces: each region's top as its plane over the polygon (constrained Delaunay, then pairs joined into 4-corner
#      parts), and walls along every border where this side's height interval [base, top] is not covered by the
#      other side's (outside: nothing), facing outwards.
# Writes sh_shells.pkl (per unit: faces with 3D corners and their bake frames) and prints counts.
import sys, json, base64, pickle, time, numpy as np, shapely
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from pb_common import sample_tris
RES, UPZ, DOWNZ = 0.5, 0.25, -0.25
PLANE_ANG, PLANE_OFF = np.cos(np.radians(6)), 0.35
FLOAT_GAP, HOLE_CELLS = 2.5, 16
# levels of detail: (smallest region in cells of 0.25 yd2, simplification tolerance in yd, lowest wall drawn in yd)
LODS = {0: (16, 0.8, 0.15), 1: (64, 1.5, 0.4), 2: (256, 3.0, 1.0)}
LOD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
MIN_CELLS, SIMPLIFY, MIN_WALL = LODS[LOD]
ONLY = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2] else None
T0 = time.time()
d = np.load('sh_in.npz'); TRI = d['tri'].astype(float); BLD = d['bld']; ST = d['street']
g = json.load(open('sw_ground.json'))['g']; gp = np.frombuffer(base64.b64decode(g['pos']), np.float32).reshape(-1, 3).astype(float)
GS = 1600 / 3 / 128; GX0, GZ0 = gp[:, 0].min(), gp[:, 2].min(); GN = 385
GH = np.zeros((GN, GN)); GH[np.round((gp[:, 2] - GZ0) / GS).astype(int), np.round((gp[:, 0] - GX0) / GS).astype(int)] = gp[:, 1]
def ground(x, y):
    fx = np.clip((np.asarray(x) - GX0) / GS, 0, GN - 1.001); fz = np.clip((-np.asarray(y) - GZ0) / GS, 0, GN - 1.001)
    i, j = np.floor(fz).astype(int), np.floor(fx).astype(int); a, b = fz - i, fx - j
    return GH[i, j] * (1 - a) * (1 - b) + GH[i, j + 1] * (1 - a) * b + GH[i + 1, j] * a * (1 - b) + GH[i + 1, j + 1] * a * b
A, B, C = TRI[:, 0], TRI[:, 1], TRI[:, 2]
NRM = np.cross(B - A, C - A); AREA = np.linalg.norm(NRM, axis=1) / 2; NRM /= np.maximum(2 * AREA[:, None], 1e-12)

_SF = None
def street_floor(X, Y):
    global _SF
    if _SF is None:
        ids = np.nonzero(ST)[0]; lo = TRI[ids].reshape(-1, 3).min(0) - 2; hi = TRI[ids].reshape(-1, 3).max(0) + 2
        nx, ny = int((hi[0] - lo[0]) / RES) + 1, int((hi[1] - lo[1]) / RES) + 1
        g = np.full(ny * nx, -1e9); pts, _ = sample_tris(A[ids], B[ids], C[ids], 0.3)
        np.maximum.at(g, np.floor((pts[:, 1] - lo[1]) / RES).astype(int) * nx + np.floor((pts[:, 0] - lo[0]) / RES).astype(int), pts[:, 2])
        g[g < -1e8] = 1e9; _SF = (lo[0], lo[1], nx, ny, g.reshape(ny, nx))
    x0, y0, nx, ny, g = _SF
    i = np.floor((Y - y0) / RES).astype(int); j = np.floor((X - x0) / RES).astype(int)
    ok = (i >= 0) & (i < ny) & (j >= 0) & (j < nx)
    return np.where(ok, g[np.clip(i, 0, ny - 1), np.clip(j, 0, nx - 1)], 1e9)

def planes_of(ids):
    """Group up-facing triangles into planes; returns cluster per triangle and (normal, offset) per cluster."""
    n, c = NRM[ids], TRI[ids].mean(1); off = np.einsum('ij,ij->i', n, c)
    dot = n @ n.T; dist = np.abs(c @ n.T - off[None, :])   # dist[i, j]: centroid i from plane j
    ok = (dot > PLANE_ANG) & (dist < PLANE_OFF) & (dist.T < PLANE_OFF)
    i, j = np.nonzero(np.triu(ok, 1))
    k, lab = connected_components(coo_matrix((np.ones(len(i)), (i, j)), shape=(len(ids), len(ids))), directed=False)
    w = AREA[ids]
    pn = np.zeros((k, 3)); np.add.at(pn, lab, n * w[:, None]); pn /= np.linalg.norm(pn, axis=1, keepdims=True)
    po = np.bincount(lab, weights=np.einsum('ij,ij->i', pn[lab], c) * w, minlength=k) / np.bincount(lab, weights=w, minlength=k)
    return lab, pn, po

def poly_of(mask, ox, oy):
    """Cells of a mask as one (multi)polygon in world x, y: rows of runs as boxes, unioned."""
    bx = []
    for r in range(mask.shape[0]):
        row = mask[r]
        if not row.any(): continue
        e = np.diff(np.concatenate([[0], row.astype(np.int8), [0]])); s, t = np.nonzero(e == 1)[0], np.nonzero(e == -1)[0]
        for a, b in zip(s, t): bx.append(shapely.box(ox + a * RES, oy + r * RES, ox + b * RES, oy + (r + 1) * RES))
    return shapely.union_all(bx)

def build_unit(u):
    deck = u < 0   # the street layer: every street part of the district as one unit (shared borders inside it)
    ids = np.nonzero(ST)[0] if deck else np.nonzero((BLD == u) & ~ST)[0]
    if len(ids) == 0: return None
    lo = TRI[ids].reshape(-1, 3).min(0) - 1; hi = TRI[ids].reshape(-1, 3).max(0) + 1
    ox, oy = np.floor(lo[0] / RES) * RES, np.floor(lo[1] / RES) * RES
    nx, ny = int(np.ceil((hi[0] - ox) / RES)) + 1, int(np.ceil((hi[1] - oy) / RES)) + 1
    up = ids[NRM[ids, 2] > UPZ]; dn = ids[NRM[ids, 2] < DOWNZ]; sp = ids[np.abs(NRM[ids, 2]) <= UPZ]
    def raster_max(tt):
        top = np.full(ny * nx, -1e9); tri = np.full(ny * nx, -1)
        if len(tt):
            pts, ti = sample_tris(A[tt], B[tt], C[tt], 0.2)
            cell = np.floor((pts[:, 1] - oy) / RES).astype(int) * nx + np.floor((pts[:, 0] - ox) / RES).astype(int)
            o = np.lexsort((pts[:, 2], cell)); last = np.r_[cell[o][1:] != cell[o][:-1], True]
            top[cell[o][last]] = pts[o][last, 2]; tri[cell[o][last]] = ti[o][last]
        return top.reshape(ny, nx), tri.reshape(ny, nx)
    top, toptri = raster_max(up)
    stop, _ = raster_max(sp)
    low = np.full(ny * nx, 1e9)
    pa_, _ = sample_tris(A[ids], B[ids], C[ids], 0.3)
    np.minimum.at(low, np.floor((pa_[:, 1] - oy) / RES).astype(int) * nx + np.floor((pa_[:, 0] - ox) / RES).astype(int), pa_[:, 2])
    low = low.reshape(ny, nx)
    bot = np.full(ny * nx, 1e9)
    if len(dn):
        pd, _ = sample_tris(A[dn], B[dn], C[dn], 0.2)
        cd = np.floor((pd[:, 1] - oy) / RES).astype(int) * nx + np.floor((pd[:, 0] - ox) / RES).astype(int)
        np.minimum.at(bot, cd, pd[:, 2])
    bot = bot.reshape(ny, nx)
    if len(up): lab, pn, po = planes_of(up)
    else: lab, pn, po = np.zeros(0, int), np.zeros((0, 3)), np.zeros(0)
    have = toptri >= 0
    gx, gy = ox + (np.arange(nx) + 0.5) * RES, oy + (np.arange(ny) + 0.5) * RES
    GX, GY = np.meshgrid(gx, gy); gr = ground(GX, GY)
    key = np.where(have, lab[np.maximum(toptri, 0)] if len(lab) else 0, -1) * 2
    # walls with nothing on top (quays, free-standing walls, bridge sides, wall tops beyond the roofs): their cells,
    # widened by one, as a strip whose top is a plane fitted to the walls' highest points
    wl = (stop > -1e8) & ~have
    if wl.any():
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
    # the floor around each cell: the streets' tops and the unit's own lowest geometry within 2 yd
    sf = street_floor(GX, GY) if not deck else np.full_like(GX, 1e9)
    floor = ndimage.minimum_filter(np.minimum(sf, low), size=9)
    flt = have & (bot < top - 0.3) & (bot > floor + FLOAT_GAP) & (not deck)
    key = np.where(have, key + flt, -1)
    # small holes inside the unit: filled from the nearest cell
    filled = ndimage.binary_fill_holes(have)
    holes, nh = ndimage.label(filled & ~have)
    if nh:
        hs = ndimage.sum(np.ones_like(holes), holes, np.arange(1, nh + 1))
        small = np.isin(holes, 1 + np.nonzero(hs <= HOLE_CELLS)[0])
        _, (ii, jj) = ndimage.distance_transform_edt(~have, return_indices=True)
        key = np.where(small, key[ii, jj], key); have = have | small
    # regions: connected cells of one key; small ones merged into the neighbour they border most
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
            if len(nb) == 0: comp[m] = 0; sizes[c] = 0; continue
            t = np.bincount(nb).argmax(); comp[m] = t; sizes[t] += sizes[c]; sizes[c] = 0; changed = True
        if not changed: break
    regs = [c for c in np.unique(comp) if c > 0]
    polys = [poly_of(comp == c, ox, oy) for c in regs]
    ok = [p for p in polys if not p.is_empty]
    simp = shapely.coverage_simplify(np.array(polys, dtype=object), SIMPLIFY)
    out = []
    for c, p0, p in zip(regs, polys, simp):
        k = ckey[c]; pl = k // 2; fl = k % 2
        m = comp == c
        if p.is_empty or p.area < 0.5: continue
        if deck: base = max(float(gr[m].min()) - 0.5, float(top_h(dict(n=pn[pl], off=po[pl]), GX[m], GY[m]).min()) - 8)
        elif fl: base = float(np.median(bot[m]))
        else:
            near = ndimage.binary_dilation(m, iterations=4)
            base = float(min(sf[near].min(), low[ndimage.binary_dilation(m, iterations=2)].min())) - 0.3
        out.append(dict(poly=p, n=pn[pl], off=po[pl], base=base, float=bool(fl), cells=int(m.sum())))
    return dict(unit=int(u), deck=deck, regions=out, raw=polys, grid=(ox, oy, nx, ny), have=have, comp=comp, ids=ids)

def top_h(r, x, y):
    n, off = r['n'], r['off']; return (off - n[0] * x - n[1] * y) / n[2]

def faces_of(U):
    """Roof faces and walls of a unit's regions. Each face: corners (k, 3) in order (outward normal by the right-hand rule)."""
    regs = U['regions']; faces = []
    # every region's oriented border edges (region on the left)
    edges = {}
    rings = []
    for ri, r in enumerate(regs):
        p = shapely.orient_polygons(r['poly'])
        for g_ in (p.geoms if p.geom_type == 'MultiPolygon' else [p]):
            for ring in [g_.exterior] + list(g_.interiors):
                cs = np.asarray(ring.coords)[:-1]
                rings.append((ri, cs))
                for a, b in zip(cs, np.roll(cs, -1, 0)): edges[(tuple(np.round(a, 4)), tuple(np.round(b, 4)))] = ri
    nwall = 0
    for ri, cs in rings:
        r = regs[ri]
        for a, b in zip(cs, np.roll(cs, -1, 0)):
            if np.hypot(*(b - a)) < 1e-6: continue
            other = edges.get((tuple(np.round(b, 4)), tuple(np.round(a, 4))))
            t = np.array([top_h(r, *a), top_h(r, *b)]); bb = np.array([r['base'], r['base']])
            if other is None: parts = [(bb, t)]
            else:
                o = regs[other]; ot = np.array([top_h(o, *a), top_h(o, *b)]); obb = np.array([o['base'], o['base']])
                parts = [(np.maximum(bb, ot), t), (bb, np.minimum(t, obb))]   # above the other side; below its base
            for lo, hi in parts:
                dlt = hi - lo
                if (dlt <= MIN_WALL).all(): continue
                if (dlt > 0.05).all():
                    corners = [(a[0], a[1], lo[0]), (b[0], b[1], lo[1]), (b[0], b[1], hi[1]), (a[0], a[1], hi[0])]
                else:   # the interval closes along the edge: a triangle up to where it does
                    s = dlt[0] / (dlt[0] - dlt[1]); m = a + s * (b - a); hm = lo[0] + s * (lo[1] - lo[0])
                    corners = [(a[0], a[1], lo[0]), (m[0], m[1], hm), (a[0], a[1], hi[0])] if dlt[0] > 0 else [(m[0], m[1], hm), (b[0], b[1], lo[1]), (b[0], b[1], hi[1])]
                faces.append(dict(kind='wall', reg=ri, c=np.array(corners, float))); nwall += 1
    for ri, r in enumerate(regs):
        tris = shapely.constrained_delaunay_triangles(r['poly'])
        tl = []
        for t in tris.geoms:
            cs = np.asarray(shapely.orient_polygons(t).exterior.coords)[:-1]
            tl.append(np.array([(x, y, top_h(r, x, y)) for x, y in cs]))
        for q in join_quads(tl): faces.append(dict(kind='roof', reg=ri, c=q))
    return faces

def join_quads(tl):
    """Pairs of triangles sharing an edge joined into convex 4-corner faces (all lie in one plane here)."""
    used = [False] * len(tl); out = []
    key = lambda p: tuple(np.round(p[:2], 4))
    emap = {}
    for i, t in enumerate(tl):
        for e in range(3): emap.setdefault(frozenset((key(t[e]), key(t[(e + 1) % 3]))), []).append((i, e))
    order = sorted(range(len(tl)), key=lambda i: -tri_area(tl[i]))
    for i in order:
        if used[i]: continue
        t = tl[i]; best = None
        for e in sorted(range(3), key=lambda e: -np.hypot(*(t[(e + 1) % 3][:2] - t[e][:2]))):
            for j, f in emap[frozenset((key(t[e]), key(t[(e + 1) % 3])))]:
                if j == i or used[j]: continue
                s = tl[j]; far = s[(f + 2) % 3]
                q = np.array([t[e], far, t[(e + 1) % 3], t[(e + 2) % 3]])   # t: e, e+1, e+2; s brings far between e and e+1
                if convex(q): best = (j, q); break
            if best: break
        used[i] = True
        if best: used[best[0]] = True; out.append(best[1])
        else: out.append(t)
    return out

def cross2(a, b): return a[0] * b[1] - a[1] * b[0]
def tri_area(t): return abs(cross2(t[1][:2] - t[0][:2], t[2][:2] - t[0][:2])) / 2
def convex(q):
    s = [cross2(q[(i + 1) % 4][:2] - q[i][:2], q[(i + 2) % 4][:2] - q[(i + 1) % 4][:2]) for i in range(4)]
    return all(x > 1e-6 for x in s) or all(x < -1e-6 for x in s)

if __name__ == '__main__':
    units = ONLY or [int(u) for u in np.unique(BLD[~ST])] + [-1]
    res = []; nf = {'wall': 0, 'roof': 0}; quads = 0; tris = 0; regions = 0
    for i, u in enumerate(units):
        U = build_unit(u)
        if U is None: continue
        U['faces'] = faces_of(U)
        for f in U['faces']:
            nf[f['kind']] += 1; quads += len(f['c']) == 4; tris += len(f['c']) == 3
        regions += len(U['regions'])
        for k in ('have', 'comp', 'raw'): U.pop(k)
        res.append(U)
        if i % 100 == 0: print(i, u, round(time.time() - T0, 1), 's', flush=True)
    pickle.dump(res, open(f'sh_shells_{LOD}.pkl' if not ONLY else 'sh_shells_test.pkl', 'wb'))
    print(json.dumps({'units': len(res), 'regions': regions, 'faces': sum(nf.values()), **nf, 'quads': quads, 'tris': tris, 's': round(time.time() - T0, 1)}))
