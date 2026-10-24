# S1 shells, second build (2026-10-24): the whole district as ONE coverage, so shells never overlap.
# The first build (sh_build2.py) made each building unit's shell from its own triangles: the units' footprints
# overlapped by 44-52 % of their area (a timber storey and its stone base as two units, eaves over a neighbour), and
# no draw order can be right between shells that pass through each other (order_shells.py: 10-15 % of the shells'
# pixels wrong, almost all between different units). Here every cell of the district's raster has one owner, the
# unit whose geometry is highest there (streets in 60-yd cells are owners too); regions are cells with the same owner,
# plane and base; the regions of the whole district are simplified together (shared borders stay shared) and walls
# stand only where the heights on the two sides of a border differ. A unit's shell is its regions' faces.
# Usage: python3 sh_build3.py <lod>   (levels as sh_build2.py; level 4: owners are 66.7-yd blocks)
import sys, json, pickle, time, numpy as np, shapely
L = int(sys.argv[1]); sys.argv = [sys.argv[0], str(L)]
import sh_build2 as B
from scipy import ndimage
from pb_common import sample_tris
RES, MIN_CELLS, SIMPLIFY, HOLE_CELLS, SAMPLE = B.RES, B.MIN_CELLS, B.SIMPLIFY, B.HOLE_CELLS, B.SAMPLE
T0 = time.time()
FRAG = max(2.0, B.MIN_AREA / 16)   # yd2: a region smaller than this with no neighbour of its own unit joins any neighbour
TRI, ST, BLD, NRM, AREA = B.TRI, B.ST, B.BLD, B.NRM0, B.AREA
cen = TRI.mean(1)
STREET_CELL = 60.0
owner = np.where(ST, 10 ** 6 + (np.floor(cen[:, 0] / STREET_CELL).astype(int) - 260) * 1000 + (np.floor(-cen[:, 1] / STREET_CELL).astype(int) - 420), BLD)
if L == 4: owner = 2 * 10 ** 6 + B.BLOCK_OF
A, Bv, C = TRI[:, 0], TRI[:, 1], TRI[:, 2]
lo = TRI.reshape(-1, 3).min(0) - 2; hi = TRI.reshape(-1, 3).max(0) + 2
ox, oy = np.floor(lo[0] / RES) * RES, np.floor(lo[1] / RES) * RES
nx, ny = int(np.ceil((hi[0] - ox) / RES)) + 1, int(np.ceil((hi[1] - oy) / RES)) + 1
def cells(p): return np.floor((p[:, 1] - oy) / RES).astype(int) * nx + np.floor((p[:, 0] - ox) / RES).astype(int)
def raster_max(tt):
    top = np.full(ny * nx, -1e9); tri = np.full(ny * nx, -1)
    for i in range(0, len(tt), 20000):
        t = tt[i:i + 20000]
        pts, ti = sample_tris(A[t], Bv[t], C[t], SAMPLE); cl = cells(pts); h = pts[:, 2]
        o = np.lexsort((h, cl)); last = np.r_[cl[o][1:] != cl[o][:-1], True]
        c2, h2, t2 = cl[o][last], h[o][last], t[ti[o][last]]
        better = h2 > top[c2]; top[c2[better]] = h2[better]; tri[c2[better]] = t2[better]
    return top.reshape(ny, nx), tri.reshape(ny, nx)
def raster_min(tt, sp):
    r = np.full(ny * nx, 1e9)
    for i in range(0, len(tt), 20000):
        t = tt[i:i + 20000]; p, _ = sample_tris(A[t], Bv[t], C[t], sp); np.minimum.at(r, cells(p), p[:, 2])
    return r.reshape(ny, nx)
up = np.nonzero(NRM[:, 2] > B.UPZ)[0]; dn = np.nonzero(NRM[:, 2] < B.DOWNZ)[0]; sp = np.nonzero(np.abs(NRM[:, 2]) <= B.UPZ)[0]
top, toptri = raster_max(up); stop, stri = raster_max(sp)
low = raster_min(np.arange(len(TRI)), max(SAMPLE, 0.3)); bot = raster_min(dn, SAMPLE)
print('rasters', nx, ny, round(time.time() - T0, 1), 's', flush=True)
gx, gy = ox + (np.arange(nx) + 0.5) * RES, oy + (np.arange(ny) + 0.5) * RES
GX, GY = np.meshgrid(gx, gy); gr = B.ground(GX, GY)
have = toptri >= 0
own = np.where(have, owner[np.maximum(toptri, 0)], -1)
# planes: per owner, its up-facing triangles that won cells
pn_all, po_all = [], []
plane_of_tri = np.full(len(TRI), -1)
won = np.unique(toptri[have])
for o in np.unique(owner[won]):
    t = won[owner[won] == o]
    lab, pn, po = B.planes_of(NRM[t], TRI[t].mean(1), AREA[t])
    plane_of_tri[t] = lab + len(pn_all); pn_all += list(pn); po_all += list(po)
key_plane = np.where(have, plane_of_tri[np.maximum(toptri, 0)], -1)
# walls with nothing on top: strips one cell wider, owned by the wall's unit, a plane fitted to the walls' tops
wl = (stop > -1e8) & ~have
if wl.any():
    st2 = ndimage.grey_dilation(np.where(wl, stop, -1e9), size=3)
    _, (ii, jj) = ndimage.distance_transform_edt(~wl, return_indices=True)
    wl2 = ndimage.binary_dilation(wl) & ~have
    stop2 = np.where(wl, stop, st2); sown = np.where(stri >= 0, owner[np.maximum(stri, 0)], -1)[ii, jj]
    cc, m = ndimage.label(wl2, structure=np.ones((3, 3)))
    objs = ndimage.find_objects(cc)
    for c in range(1, m + 1):
        sl = objs[c - 1]; mm = cc[sl] == c
        X = np.stack([GX[sl][mm], GY[sl][mm], np.ones(mm.sum())], 1); h = stop2[sl][mm]
        if mm.sum() >= 3:
            coef = np.linalg.lstsq(X, h, rcond=None)[0]; g_ = np.hypot(coef[0], coef[1])
            if g_ > 1: coef[:2] /= g_
            coef[2] = (h - X[:, :2] @ coef[:2]).max() if mm.sum() < 12 else np.median(h - X[:, :2] @ coef[:2])
        else: coef = np.array([0, 0, h.max()])
        Ln = np.sqrt(coef[0] ** 2 + coef[1] ** 2 + 1)
        pn_all.append(np.array([-coef[0], -coef[1], 1]) / Ln); po_all.append(coef[2] / Ln)
        kp = key_plane[sl]; kp[mm] = len(pn_all) - 1; key_plane[sl] = kp
        ow = own[sl]; ow[mm] = sown[sl][mm]; own[sl] = ow
    have = have | wl2; top = np.where(wl2, stop2, top)
pn_all, po_all = np.array(pn_all), np.array(po_all)
isstreet = own >= 10 ** 6 if L != 4 else np.zeros_like(have)
sf = B.street_floor(GX, GY)
floor = ndimage.minimum_filter(np.minimum(sf, low), size=int(4.5 / RES) | 1)
flt = have & (bot < top - 0.3) & (bot > floor + B.FLOAT_GAP) & ~isstreet
# small holes filled from the nearest cell
filled = ndimage.binary_fill_holes(have); holes, nh = ndimage.label(filled & ~have)
if nh:
    hs = ndimage.sum(np.ones_like(holes), holes, np.arange(1, nh + 1)); small = np.isin(holes, 1 + np.nonzero(hs <= HOLE_CELLS)[0])
    _, (ii, jj) = ndimage.distance_transform_edt(~have, return_indices=True)
    key_plane = np.where(small, key_plane[ii, jj], key_plane); own = np.where(small, own[ii, jj], own); flt = np.where(small, flt[ii, jj], flt); have = have | small
print('labels', round(time.time() - T0, 1), 's', flush=True)
# regions: connected cells of one (owner, plane, base); small ones merged into the neighbour they border most
# (one of the same owner if any)
key = np.where(have, key_plane.astype(np.int64) * 2 + flt, -1)
# connected components of equal keys (4-neighbours), all at once
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
idx = np.arange(ny * nx).reshape(ny, nx); kf = key
e1 = (kf[:, 1:] == kf[:, :-1]) & (kf[:, 1:] >= 0); e2 = (kf[1:, :] == kf[:-1, :]) & (kf[1:, :] >= 0)
ia = np.r_[idx[:, 1:][e1], idx[1:, :][e2]]; ib = np.r_[idx[:, :-1][e1], idx[:-1, :][e2]]
ncomp, lab = connected_components(coo_matrix((np.ones(len(ia), np.int8), (ia, ib)), shape=(ny * nx, ny * nx)), directed=False)
lab = lab.reshape(ny, nx)
# number the components on cells that have a key 1..n
used = np.unique(lab[have]); remap = np.zeros(ncomp, np.int64); remap[used] = np.arange(1, len(used) + 1)
comp = np.where(have, remap[lab], 0); n = len(used)
cinfo = [None] * (n + 1)
flat_c = comp[have]; flat_k = key[have]; flat_o = own[have]
first = np.zeros(n + 1, np.int64); first[flat_c] = flat_k
o_ = np.lexsort((flat_o, flat_c)); fc, fo = flat_c[o_], flat_o[o_]
brk = np.r_[0, np.nonzero(np.diff(fc))[0] + 1, len(fc)]
for a, b in zip(brk[:-1], brk[1:]):
    vals, cnts = np.unique(fo[a:b], return_counts=True); c = fc[a]
    cinfo[c] = [int(first[c] // 2), int(first[c] % 2), int(vals[np.argmax(cnts)])]
print('components', n, round(time.time() - T0, 1), 's', flush=True)
objs = ndimage.find_objects(comp)
for _ in range(4):
    sizes = np.bincount(comp.ravel(), minlength=n + 1); changed = False
    for c in np.argsort(sizes):
        if c == 0 or sizes[c] == 0 or sizes[c] >= MIN_CELLS: continue
        sl = objs[c - 1]
        if sl is None: continue
        sl2 = tuple(slice(max(0, s.start - 1), s.stop + 1) for s in sl)
        sub = comp[sl2]; m_ = sub == c; ring = ndimage.binary_dilation(m_) & ~m_
        nb = sub[ring]; nb = nb[nb > 0]
        if len(nb) == 0:
            if sizes[c] * RES * RES < 1.0: sub[m_] = 0; sizes[c] = 0
            continue
        cnt = np.bincount(nb); same = [t for t in np.nonzero(cnt)[0] if cinfo[t][2] == cinfo[c][2]]
        if same: t = max(same, key=lambda t: cnt[t])
        elif sizes[c] * RES * RES < FRAG: t = int(cnt.argmax())   # (a fragment of another unit's: taken by its neighbour)
        else: continue                                            # (a small unit of its own: kept)
        sub[m_] = t; sizes[t] += sizes[c]; sizes[c] = 0; changed = True
        # (the target's box grows to cover the merged cells)
        st_ = objs[t - 1]; objs[t - 1] = tuple(slice(min(a.start, b.start), max(a.stop, b.stop)) for a, b in zip(st_, sl2))
    if not changed: break
regs = [c for c in np.unique(comp) if c > 0]
print('regions', len(regs), round(time.time() - T0, 1), 's', flush=True)
polys = []
for c in regs:
    sl = objs[c - 1]; m_ = comp[sl] == c
    polys.append(B.poly_of(m_, ox + sl[1].start * RES, oy + sl[0].start * RES))
simp = B.arc_simplify(polys, SIMPLIFY)
print('simplified', round(time.time() - T0, 1), 's', flush=True)
# regions with their planes, heights and bases; then faces per owner
R = []
for c, p in zip(regs, simp):
    if p.is_empty or p.area < 0.5: continue
    pl, fl, ow = cinfo[c]
    sl = objs[c - 1]; m_ = comp[sl] == c
    tv = top[sl][m_]; tv = tv[tv > -1e8]
    r = dict(poly=p, n=pn_all[pl], off=po_all[pl], float=bool(fl), owner=ow, cells=int(m_.sum()),
             tmin=float(tv.min()) - 0.3 if len(tv) else -1e9, tmax=float(tv.max()) + 0.3 if len(tv) else 1e9)
    gxm, gym = GX[sl][m_], GY[sl][m_]
    if ow >= 10 ** 6 and L != 4: base = max(float(gr[sl][m_].min()) - 0.5, float(B.top_h(r, gxm, gym).min()) - 8)
    elif fl and (bot[sl][m_] < 1e8).any(): b_ = bot[sl][m_]; base = min(float(np.median(b_[b_ < 1e8])), float(B.top_h(r, gxm, gym).min()) - 0.5)
    else:
        sl2 = tuple(slice(max(0, s.start - int(2 / RES)), s.stop + int(2 / RES)) for s in sl)
        big = np.zeros(comp[sl2].shape, bool); big[sl[0].start - sl2[0].start:sl[0].stop - sl2[0].start, sl[1].start - sl2[1].start:sl[1].stop - sl2[1].start] = m_
        base = float(min(sf[sl2][ndimage.binary_dilation(big, iterations=int(2 / RES))].min(), low[sl2][ndimage.binary_dilation(big, iterations=int(1 / RES))].min())) - 0.3
    r['base'] = base; R.append(r)
U = dict(unit=-9, deck=False, regions=R, back=lambda x, y: (x, y))
faces = B.faces_of(U)
print('faces', len(faces), round(time.time() - T0, 1), 's', flush=True)
by = {}
for f in faces: by.setdefault(R[f['reg']]['owner'], []).append(f)
regs_by = {}
for i, r in enumerate(R): regs_by.setdefault(r['owner'], []).append(r)
res = []
for o, fl in sorted(by.items()):
    unit = (-2 - (o - 2 * 10 ** 6)) if L == 4 else (o if o < 10 ** 6 else -1000 - (o - 10 ** 6))
    res.append(dict(unit=unit, owner=o, deck=o >= 10 ** 6, regions=regs_by.get(o, []), faces=fl))
pickle.dump(res, open(f'sh_shells_{L}.pkl', 'wb'))
nf = {'wall': 0, 'roof': 0}
for f in faces: nf[f['kind']] += 1
nb = np.array([len(U_['faces']) for U_ in res if not U_['deck']])
print(json.dumps({'lod': L, 'units': len(res), 'regions': len(R), 'faces': len(faces), **nf, 'bld_faces_median': float(np.median(nb)), 'bld_faces_mean': round(float(nb.mean()), 1), 's': round(time.time() - T0, 1)}))
