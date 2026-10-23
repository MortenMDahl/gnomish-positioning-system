# Whole buildings (2026-10-23): the city's pieces joined into buildings. Pieces touching within 0.6 yd join (points
# 1 yd apart on every game triangle, plus its corners); streets and squares stay apart (cut into 24-yd cells, they
# are only ground); joined structures over 60 yd across or 3,000 parts are cut into 40-yd cells (each piece whole in
# the cell of its middle). Writes pb_buildings.npz (building per part, street flag per part) and an overlay image.
import os, sys, json, numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
os.environ['RANK'] = 'value'; os.environ.setdefault('VISTAG', 'pbvw')
src = open('pb_city.py').read(); exec(compile(src[:src.index('cells = {}')], 'pb_city_part', 'exec'))
from pb_common import sample_tris
JOIN, GIANT_EXT, GIANT_PARTS, GIANT_CELL = 0.6, 60.0, 3000, 40.0
isstreet_piece = street                                   # (per piece, from pb_city)
# points on the game triangles of each non-street piece
gtri = np.nonzero(~isstreet_piece[piece])[0]              # game triangles (index into Tk) not in streets
A, B, C = P[Tk[gtri, 0]], P[Tk[gtri, 1]], P[Tk[gtri, 2]]
pts, ti = sample_tris(A, B, C, 1.0)
pp = piece[gtri][ti]
pts = np.vstack([pts, A, B, C]); pp = np.concatenate([pp, piece[gtri], piece[gtri], piece[gtri]])
pairs = cKDTree(pts).query_pairs(JOIN, output_type='ndarray')
a, b = pp[pairs[:, 0]], pp[pairs[:, 1]]; k = a != b
nb, comp = connected_components(coo_matrix((np.ones(k.sum()), (a[k], b[k])), shape=(npc, npc)), directed=False)
print('points', len(pts), 'joined pairs', int(k.sum()), 'components', nb, flush=True)
# parts (after the 10-yd cut) -> building; piece middles
pa = np.linalg.norm(np.cross(V[T2[:, 1]] - V[T2[:, 0]], V[T2[:, 2]] - V[T2[:, 0]]), axis=1) / 2 + 1e-6
pcx = np.bincount(PC, weights=cen[:, 0] * pa, minlength=npc) / np.maximum(np.bincount(PC, weights=pa, minlength=npc), 1e-9)
pcy = np.bincount(PC, weights=cen[:, 1] * pa, minlength=npc) / np.maximum(np.bincount(PC, weights=pa, minlength=npc), 1e-9)
bld = comp[PC].copy()
st = isstreet_piece[PC]
# giants (joined structures over 45 yd across or 1,500 parts): cut where they hold together least (recursive
# spectral bisection of the pieces' contact graph, weighted by how much they touch), so a row of houses parts at the
# walls between houses rather than through a house
from scipy.sparse.linalg import eigsh
from scipy.sparse import csgraph, diags
Wp = coo_matrix((np.ones(k.sum()), (a[k], b[k])), shape=(npc, npc)).tocsr(); Wp = Wp + Wp.T
ppx = pcx; ppy = pcy
pparts = np.bincount(PC, minlength=npc)
LIMIT_EXT, LIMIT_PARTS = 45.0, 1500
def extent(ps): return max(np.ptp(ppx[ps]), np.ptp(ppy[ps])) if len(ps) > 1 else 0.0
def bisect(ps):
    if len(ps) < 4: return None
    sub = Wp[ps][:, ps]
    nc, lab = connected_components(sub, directed=False)
    if nc > 1:   # (already apart inside: split off the biggest connected part)
        big = np.bincount(lab).argmax(); return ps[lab == big], ps[lab != big]
    L = csgraph.laplacian(sub.astype(float), normed=True)
    try:
        vals, vecs = eigsh(L, k=2, sigma=-1e-3, which='LM') if len(ps) > 60 else np.linalg.eigh(L.toarray())
        if len(ps) <= 60: vals, vecs = vals[:2], vecs[:, :2]
        f = vecs[:, np.argsort(vals)[1]]
    except Exception:
        f = ppx[ps] - ppx[ps].mean()
    w = pparts[ps]
    order = np.argsort(f); cw = np.cumsum(w[order]) / w.sum()
    # the sweep cut with the least contact per smaller side, within 15-85 % of the parts
    best, bi = None, None
    deg = np.asarray(sub.sum(1)).ravel()
    cand = np.nonzero((cw > 0.15) & (cw < 0.85))[0]
    if len(cand) == 0: cand = np.array([len(order) // 2])
    inS = np.zeros(len(ps), bool)
    # (cut weight for every prefix by incremental update)
    subo = sub[order][:, order].tocsr(); cut = 0.0; vol = 0.0; tot = deg.sum()
    cuts = np.zeros(len(order))
    for i in range(len(order)):
        row = subo.getrow(i); idx, val = row.indices, row.data
        cut += val[idx > i].sum() - val[idx < i].sum()
        vol += deg[order[i]]; cuts[i] = cut / max(min(vol, tot - vol), 1e-9)
    bi = cand[np.argmin(cuts[cand])]
    return ps[order[:bi + 1]], ps[order[bi + 1:]]
ids = np.unique(bld[~st]); nxt = bld.max() + 1; giants = 0; pieces_of = {}
for c in ids:
    ps = np.unique(PC[(bld == c) & ~st])
    stack, done = [ps], []
    while stack:
        q = stack.pop()
        if (extent(q) > LIMIT_EXT or pparts[q].sum() > LIMIT_PARTS) and len(q) >= 4:
            r = bisect(q)
            if r is not None and len(r[0]) and len(r[1]): stack += [r[0], r[1]]; continue
        done.append(q)
    if len(done) > 1:
        giants += 1
        for q in done:
            bld[np.isin(PC, q) & ~st] = nxt; nxt += 1
# small bits left over (under 40 parts) join the unit they touch most, smallest first, while it stays within the limits
for _ in range(6):
    pb = np.full(npc, -1); pb[PC[~st]] = bld[~st]        # unit of each piece
    units, ucount = np.unique(bld[~st], return_counts=True)
    usize = dict(zip(units.tolist(), ucount.tolist()))
    # contact between units
    rows, cols = Wp.nonzero(); keep = (pb[rows] >= 0) & (pb[cols] >= 0) & (pb[rows] != pb[cols])
    U = coo_matrix((np.asarray(Wp[rows[keep], cols[keep]]).ravel(), (pb[rows[keep]], pb[cols[keep]])), shape=(bld.max() + 1, bld.max() + 1)).tocsr()
    merged = 0; target = {}
    for u in sorted(units.tolist(), key=lambda u: usize[u]):
        if usize[u] >= 40 or u in target: continue
        row = U.getrow(u)
        if row.nnz == 0: continue
        v = int(row.indices[np.argmax(row.data)])
        while v in target: v = target[v]
        if v == u or usize.get(v, 0) + usize[u] > LIMIT_PARTS: continue
        target[u] = v; usize[v] = usize.get(v, 0) + usize[u]; merged += 1
    if not merged: break
    for u, v in target.items():
        while v in target: v = target[v]
        bld[bld == u] = v
    print('merged small bits', merged, flush=True)
# streets: 24-yd cells of each part's middle, as their own groups
skey = np.floor(cen[st, :2] / 24.0).astype(int); _, sinv = np.unique(skey, axis=0, return_inverse=True)
bld[np.nonzero(st)[0]] = nxt + sinv.reshape(-1)
_, bld = np.unique(bld, return_inverse=True); bld = bld.reshape(-1)
nb = bld.max() + 1
cnt = np.bincount(bld); isst = np.zeros(nb, bool); isst[bld[st]] = True
bc = cnt[~isst]
ext = np.array([max(np.ptp(cen[bld == i, 0]), np.ptp(cen[bld == i, 1])) for i in range(nb)])
info = {'buildings': int((~isst).sum()), 'street_groups': int(isst.sum()), 'giants_cut': giants,
        'parts_per_building': {'median': float(np.median(bc)), 'p90': float(np.percentile(bc, 90)), 'max': int(bc.max())},
        'size_yd': {'median': round(float(np.median(ext[~isst])), 1), 'p90': round(float(np.percentile(ext[~isst], 90)), 1)},
        'buildings_under_10_parts': int((bc < 10).sum())}
print(json.dumps(info), flush=True)
np.savez_compressed('pb_buildings.npz', bld=bld, street=st)
# overlay: building colours from above
from PIL import Image
cx0, cy0 = m_ = (cen[:, 0].min(), cen[:, 1].min())
S = 2.0
W = int(np.ptp(cen[:, 0]) * S) + 2; H = int(np.ptp(cen[:, 1]) * S) + 2
img = np.zeros((H, W, 3), np.uint8)
rng = np.random.default_rng(3); pal = rng.integers(60, 255, (nb, 3)); pal[isst] = 70
order = np.argsort(cen[:, 2])                    # (higher parts over lower)
x = ((cen[order, 0] - cx0) * S).astype(int); y = H - 1 - ((cen[order, 1] - cy0) * S).astype(int)
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        img[np.clip(y + dy, 0, H - 1), np.clip(x + dx, 0, W - 1)] = pal[bld[order]]
Image.fromarray(img).save('pb_buildings.png')
