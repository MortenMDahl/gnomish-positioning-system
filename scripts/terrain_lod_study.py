"""Offline study for GPS3D's ground mesh (J8, 2026-10-22): how much height error on screen each way of
spending a tile's triangles leaves, at the far views of tools/sandbox/test_terrain.py.

Usage: python3 scripts/terrain_lod_study.py views.json [--budget-scale 1.0]
  views.json: written by `TERRAIN_DUMP=views.json python3 tools/sandbox/test_terrain.py` (each far view's
  camera, the tiles whose ground is drawn and J1's step for each).

The error is test_terrain's: every point of each drawn tile's 33 x 33 grid, the drawn height against the
tile's own height, projected (screen px), weighted by screen area ((F / depth)^2), points off screen left
out. Schemes (every one on the same heights: shared edges and corners as GPS3D draws them, Canon):
  even    J1's even grid per tile, steps 1 to 32 (2048 to 2 triangles)
  rq      a right-triangle bintree (4-8 mesh) per tile, vertices added in the order of their saturated
          largest error (the classic restricted-quadtree order)
  rqa     the same bintree, vertices in the order of their saturated error summed over the area they
          change (what a mean error over the screen asks for)
Per scheme the triangles are shared out between the tiles in the best way for this view (each tile's
options on its lower convex hull, cheapest error per triangle first), at J1's triangle count; that leaves
only the meshes themselves to compare. `ladder` gives the same with each tile limited to a few nested
levels, as the add-on ships them.
"""
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'prototypes', 'GPS3D', 'Data')
B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
GRID, CELLS = 33, 32
TILE = 1600 / 3
CELL = TILE / CELLS
NP = GRID * GRID

sys.path.insert(0, HERE)
import terrain_lod as TL  # noqa: E402


def load_world(m):
    s = open(os.path.join(DATA, f'World_{m}.lua')).read()
    out = {}
    for key, val in re.findall(r'\[(\d+)\]="([^"]*)"', s):
        out[int(key)] = TL.decode(val)
    return out


def even_hierarchy():
    """J1's quadtree on the grid: each point's level and its two parents (GPS3D.lua's Lod)."""
    lev, pa, pb = np.zeros(NP, int), np.zeros(NP, int), np.zeros(NP, int)

    def level(q):
        if q == 0:
            return 5
        L = 0
        while q % 2 == 0:
            q //= 2
            L += 1
        return min(L, 5)
    for J in range(GRID):
        for I in range(GRID):
            p = J * GRID + I
            L = min(level(I), level(J))
            lev[p] = L
            if L < 5:
                hs = 2 ** L
                if J % (2 * hs) == 0:
                    pa[p], pb[p] = p - hs, p + hs
                elif I % (2 * hs) == 0:
                    pa[p], pb[p] = p - hs * GRID, p + hs * GRID
                else:
                    pa[p], pb[p] = p - hs * GRID - hs, p + hs * GRID + hs
    order = [np.array([p for p in range(NP) if lev[p] == L]) for L in range(4, -1, -1)]
    return lev, pa, pb, order


EV = even_hierarchy()


def even_surface(c, k):
    lev, pa, pb, order = EV
    d = c.copy()
    for idx in order:
        L = lev[idx[0]]
        if L < k:
            d[idx] = (d[pa[idx]] + d[pb[idx]]) * 0.5
    return d


class View:
    def __init__(self, v, worlds):
        self.v = v
        self.F = v['F']
        self.hw, self.hh = v['W'] / 2, v['H'] / 2
        (self.fx, self.fy, self.fz, self.rx, self.ry, self.ux, self.uy, self.uz, self.cx, self.cy, self.cz) = v['basis']
        self.world = worlds[v['map']]
        self.tiles = []
        ii, jj = np.meshgrid(np.arange(GRID), np.arange(GRID))
        ii, jj = ii.ravel(), jj.ravel()
        for tx, ty, step in v['tiles']:
            h = np.array(self.world[ty * 64 + tx])
            c = TL.canon(self.world, tx, ty)
            x, y = (tx * 32 + ii) * CELL, -(ty * 32 + jj) * CELL
            ex, ey, ed = self.project(x, y, h)
            ok = (ed > 1.5) & (np.abs(ex) < self.hw) & (np.abs(ey) < self.hh)
            w = np.where(ok, (self.F / np.maximum(ed, 1e-6)) ** 2, 0.0)
            self.tiles.append(dict(tx=tx, ty=ty, step=step, h=h, c=c, x=x, y=y, ex=ex, ey=ey, w=w, ok=ok, d=float(ed.min())))
        self.wsum = sum(t['w'].sum() for t in self.tiles)

    def project(self, x, y, h):
        dx, dy, dz = x - self.cx, y - self.cy, h - self.cz
        d = dx * self.fx + dy * self.fy + dz * self.fz
        s = self.F / np.maximum(d, 1e-6)
        return (dx * self.rx + dy * self.ry) * s, (dx * self.ux + dy * self.uy + dz * self.uz) * s, d

    def err(self, t, drawn):
        """per point screen error of a drawn surface (0 off screen)"""
        dx, dy, _ = self.project(t['x'], t['y'], drawn)
        return np.where(t['ok'], np.hypot(dx - t['ex'], dy - t['ey']), 0.0)


def hull(opts):
    """lower convex hull of (tris, err) options, from most triangles to fewest"""
    opts = sorted(set(opts))
    best = {}
    for n, e in opts:
        if n not in best or e < best[n]:
            best[n] = e
    pts = sorted(best.items())
    # monotone: keep only options with less error than every coarser one
    mono = []
    for n, e in pts:
        while mono and mono[-1][1] <= e:
            # a coarser option already at most this error: this finer one is useless
            break
        else:
            mono.append((n, e))
    h = []
    for p in mono:
        while len(h) >= 2:
            (n1, e1), (n2, e2) = h[-2], h[-1]
            if (e2 - e1) * (p[0] - n1) >= (p[1] - e1) * (n2 - n1):
                h.pop()
            else:
                break
        h.append(p)
    return h


def allocate(tile_opts, budget):
    """best total error within the budget: every tile starts at its coarsest option and buys the cheapest
    error per triangle first (Lagrangian on the hulls; the last step may overshoot by one option)"""
    import heapq
    state, total_t, total_e, heap = [], 0, 0.0, []
    for i, opts in enumerate(tile_opts):
        h = hull(opts)
        state.append([h, 0])
        total_t += h[0][0]
        total_e += h[0][1]
        if len(h) > 1:
            (n0, e0), (n1, e1) = h[0], h[1]
            heapq.heappush(heap, (-(e0 - e1) / (n1 - n0), i))
    while heap:
        _, i = heapq.heappop(heap)
        h, k = state[i]
        (n0, e0), (n1, e1) = h[k], h[k + 1]
        if total_t + n1 - n0 > budget:
            continue
        total_t += n1 - n0
        total_e += e1 - e0
        state[i][1] = k + 1
        if k + 2 < len(h):
            (n2, e2) = h[k + 2]
            heapq.heappush(heap, (-(e1 - e2) / (n2 - n1), i))
    return total_t, total_e, [s[0][s[1]][0] for s in state]


def weighted_p95(view, errs):
    e = np.concatenate([x for x in errs])
    w = np.concatenate([t['w'] for t in view.tiles])
    o = np.argsort(e)
    cw = np.cumsum(w[o])
    return float(e[o][np.searchsorted(cw, 0.95 * cw[-1])])


def main():
    path = sys.argv[1]
    views = json.load(open(path))
    worlds = {m: load_world(m) for m in sorted({v['map'] for v in views})}
    for v in views:
        V = View(v, worlds)
        budget = v['tris']
        # J1 as drawn (its steps, no morphing) and the even grid allocated at best
        e_j1 = sum((V.err(t, even_surface(t['c'], int(round(math.log2(t['step']))))) * t['w']).sum() for t in V.tiles) / V.wsum
        even_opts = []
        for t in V.tiles:
            even_opts.append([(2 * (32 >> k) ** 2, float((V.err(t, even_surface(t['c'], k)) * t['w']).sum())) for k in range(6)])
        res = {'J1 drawn (no morph)': (budget, e_j1)}
        n, e, _ = allocate(even_opts, budget)
        res['even, best share'] = (n, e / V.wsum)
        LADS = {'x1.4 (20 levels)': [2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048],
                'x2 (11 levels)': [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048],
                'x2.5 (8 levels)': [2, 6, 16, 40, 100, 256, 640, 2048],
                'x4 (6 levels)': [2, 8, 32, 128, 512, 2048]}
        for name, key in (('rq (largest error)', 'max'), ('rqa (error x area)', 'area')):
            opts = []
            lad = {k: [] for k in LADS}
            for t in V.tiles:
                order, ntris = TL.order(t['c'], key)
                o = []
                marks = {k: TL.ladder_marks(ntris, L) for k, L in LADS.items()}
                lo = {k: [] for k in LADS}
                for nv in TL.sample_counts(len(order)):
                    active = TL.active_set(order, nv)
                    d = TL.surface(t['c'], active)
                    err = float((V.err(t, d) * t['w']).sum())
                    o.append((int(ntris[nv - 1]), err))
                    for k in LADS:
                        if nv in marks[k]:
                            lo[k].append((int(ntris[nv - 1]), err))
                opts.append(o)
                for k in LADS:
                    lad[k].append(lo[k])
            n, e, _ = allocate(opts, budget)
            res[name + ', any count'] = (n, e / V.wsum)
            for k in LADS:
                n, e, _ = allocate(lad[k], budget)
                res[name + ', ladder ' + k] = (n, e / V.wsum)
            for f in (0.75, 1.25, 1.5):
                n, e, _ = allocate(lad['x2 (11 levels)'], int(budget * f))
                res[name + f', ladder x2, {f:.0%} of the triangles'] = (n, e / V.wsum)
        print(f"{v['name']}: {len(V.tiles)} tiles, J1 {budget} triangles, measured in the sandbox mean {v['mean']:.2f} px")
        base = res['even, best share'][1]
        for k, (n, e) in res.items():
            print(f'   {k:48s} {n:5d} tris  mean {e:.3f} px  ({(e / base - 1) * 100:+.0f} % against the even grid at best)')


if __name__ == '__main__':
    main()
