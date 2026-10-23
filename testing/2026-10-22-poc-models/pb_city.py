# The game's own models over the whole exported Stormwind square as addon data for distance-based detail:
# every triangle the finer hidden-part pass saw (back-only flipped, both-sides flagged), cut to 10-yd pieces (each
# piece keeps its game triangle's area, so a part is kept or dropped whole), in 24-yd cells; in each cell the pieces
# are sorted biggest part first and the vertices numbered in first-use order, so "the n biggest parts" is a prefix.
# Each cell is its own function in the Lua file (WoW's Lua 5.1: at most 2^18 constants per function).
import sys, os, json, numpy as np
sys.path.insert(0, '/home/claude/wt/poc/testing/2026-10-22-poc-models')
src = open('/home/claude/wt/poc/testing/2026-10-22-poc-models/to_lua.py').read()
exec(src[:src.index("out = ['--")])          # (subdivide only)
from load import load
CELL = 24.0
m = load('stormwind'); P = m['P'].astype(float); T = m['T'].copy(); UVa = m['UV'].astype(float)
fr = np.zeros(len(T), np.uint32); bk = np.zeros(len(T), np.uint32); cover = np.zeros(len(T), int)
for i in (-1, 0, 1):
    for j in (-1, 0, 1):
        v = np.load(f'{os.environ.get("VISTAG", "pbvt")}_{i}_{j}_vis.npz'); r = v['region']
        fr[r] = v['front'][r]; bk[r] = v['back'][r]; cover[r] += 1
idx = np.nonzero((cover > 0) & ((fr + bk) >= 1))[0]
A, B, C = P[T[idx, 0]], P[T[idx, 1]], P[T[idx, 2]]
area = np.linalg.norm(np.cross(B - A, C - A), axis=1) / 2
Tk = T[idx].copy(); UVc = UVa[Tk]
flip = (fr[idx] == 0) & (bk[idx] >= 1)
Tk[flip] = Tk[flip][:, [0, 2, 1]]; UVc[flip] = UVc[flip][:, [0, 2, 1]]
both = ((fr[idx] >= 1) & (bk[idx] >= 1)).astype(int)
# pieces (2026-10-23): neighbours sharing an edge, with the same texture and facing within 30 degrees, join one
# piece (a roof slope, a wall face, a beam side); every part ranks by its whole piece's area (RANK=tri: its own)
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
key = np.round(P / 0.05).astype(np.int64); _, wi = np.unique(key, axis=0, return_inverse=True); wi = wi.reshape(-1)
W = wi[Tk]
nrm = np.cross(P[Tk[:, 1]] - P[Tk[:, 0]], P[Tk[:, 2]] - P[Tk[:, 0]]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
TEXk = m['TEX'][idx]
e = np.concatenate([np.stack([W[:, a], W[:, b]], 1) for a, b in ((0, 1), (1, 2), (2, 0))])
et = np.tile(np.arange(len(W)), 3)
e.sort(1)
order = np.lexsort((e[:, 1], e[:, 0])); e, et = e[order], et[order]
same = np.all(e[1:] == e[:-1], 1)
i1, i2 = et[:-1][same], et[1:][same]
ok = (TEXk[i1] == TEXk[i2]) & (np.einsum('ij,ij->i', nrm[i1], nrm[i2]) > np.cos(np.radians(30)))
npc, piece = connected_components(coo_matrix((np.ones(ok.sum()), (i1[ok], i2[ok])), shape=(len(W), len(W))), directed=False)
parea = np.bincount(piece, weights=area)
rank_area = area if os.environ.get('RANK') == 'tri' else parea[piece]
pcount = np.bincount(piece)
print('pieces', npc, 'triangles per piece: median', float(np.median(pcount)), 'max', int(pcount.max()), 'biggest piece', round(float(parea.max()), 1), 'sq yd', flush=True)
used, inv = np.unique(Tk.reshape(-1), return_inverse=True)
V = P[used]; T2 = inv.reshape(-1, 3)
V, T2, Fi, UVc = subdivide(V, T2, C=np.arange(len(T2)), UV=UVc)
FD = m['TEX'][idx][Fi]; BF = both[Fi]; AR = rank_area[Fi]; PC = piece[Fi]
if os.environ.get('RANK') == 'value':   # a piece ranks by what each of its parts buys: its area / its parts (after the cut)
    nparts = np.bincount(PC, minlength=npc); val = parea / np.maximum(nparts, 1)
    # streets and squares (big flat pieces facing up) come after the buildings: the map picture under them shows them
    pnz = np.bincount(piece, weights=np.abs(nrm[:, 2]) * area) / np.maximum(parea, 1e-9)
    street = (parea > 300) & (pnz > 0.9)
    val[street] /= 10
    print('street pieces', int(street.sum()), 'parts', int(np.isin(PC, np.nonzero(street)[0]).sum()), 'of', len(PC), flush=True)
    AR = val[PC]
cen = V[T2].mean(1)
if os.environ.get('RANK') == 'tri': key = np.floor(cen[:, :2] / CELL).astype(int)
else:   # (a piece's parts all go to the cell of the piece's middle: one distance, so it is drawn or dropped whole)
    pa = np.linalg.norm(np.cross(V[T2[:, 1]] - V[T2[:, 0]], V[T2[:, 2]] - V[T2[:, 0]]), axis=1) / 2 + 1e-6
    pcx = np.bincount(PC, weights=cen[:, 0] * pa) / np.bincount(PC, weights=pa); pcy = np.bincount(PC, weights=cen[:, 1] * pa) / np.bincount(PC, weights=pa)
    key = np.floor(np.stack([pcx[PC], pcy[PC]], 1) / CELL).astype(int)
cells = {}
for n, k in enumerate(map(tuple, key)): cells.setdefault(k, []).append(n)
f = lambda a, fmt: ','.join(fmt % x for x in a)
out = ['-- Proof of concept data (branch poc-models): the game\'s own building models over the exported Stormwind square,',
       '-- in 24-yd cells, biggest parts first (PocModels.lua, /gps3d poc city)', 'local _, ns = ...',
       'ns.PocCity = { map = 0, cells = {} }', 'local C = ns.PocCity.cells']
sizes = []
for k, lst in sorted(cells.items()):
    lst = np.array(lst); lst = lst[np.lexsort((PC[lst], -AR[lst]))]
    tri = T2[lst]
    order, seen_v = [], {}
    for t in tri.reshape(-1):
        if t not in seen_v: seen_v[t] = len(order) + 1; order.append(t)
    tl = np.vectorize(seen_v.get)(tri)
    Vc = V[order]
    lo, hi = Vc.min(0), Vc.max(0); c = (lo + hi) / 2; r = float(np.linalg.norm(Vc - c, axis=1).max())
    out.append('C[#C + 1] = (function() return { x = %.1f, y = %.1f, h = %.1f, r = %.1f, v = {%s}, t = {%s}, uv = {%s}, f = {%s}, b = {%s}, a = {%s}, g = {%s} } end)()' % (
        c[0], c[1], c[2], r, f(Vc.reshape(-1), '%.2f'), f(tl.reshape(-1), '%d'), f(UVc[lst].reshape(-1), '%.4f'), f(FD[lst], '%d'), f(BF[lst], '%d'), f(AR[lst], '%.2f'), f(PC[lst], '%d')))
    sizes.append(len(lst))
path = os.environ.get('OUT', '/home/claude/wt/poc/prototypes/GPS3D/PocCity.lua')
open(path, 'w').write('\n'.join(out) + '\n')
import os
print(json.dumps({'game_tris_in_square': int((cover > 0).sum()), 'visible_game_tris': int(len(idx)), 'flipped': int(flip.sum()), 'both': int(both.sum()),
                  'pieces': int(len(T2)), 'cells': len(cells), 'per_cell_max': int(max(sizes)), 'lua_bytes': os.path.getsize(path),
                  'area_pct': {str(t): round(float((area >= t).mean() * 100), 1) for t in (0.5, 1, 2, 4, 8, 16)}}))
