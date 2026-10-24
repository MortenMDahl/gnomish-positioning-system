"""Raises the ground grid (prototypes/GPS3D/Data/World_<map>.lua) to the floor of cities built on the game's
buildings (2026-10-24, branch poc-shells): where a city stands on its own building model rather than on the
terrain (Stormwind: its streets are about 40 yd above the terrain under it, which the game never shows), the
3D view's ground lay far below the buildings, and the city looked as if it flew. The floor comes from the
building blocks' 1-yd height raster (GPS3D_EK1..4, GPS3D_Kalimdor1..3, GPS3D_Instances: ground, water and
every building face seen from above, the highest), taken low so roofs do not count:

- per grid point (16.7 yd apart), the PCT-th percentile of the raster's samples in the 16 x 16 samples
  (16.7 yd) round it, if at least COVER of them have a block;
- a point is raised to that floor only where it is more than RAISE yd and at most CAP yd above the grid there
  (higher is not a floor but a building's crown or a mountain built as a building: Nordrassil, Grim Batol);
- then a grey-scale opening (3 x 3 grid points: erosion, then dilation) of the raised grid, so a raised
  area narrower than about 50 yd (one big building, a bridge over a ravine) goes back to the terrain, and
  the city's floor, hundreds of yards across, stays; nowhere is the ground lowered.

Shared tile edges get the same height in both tiles (each point is worked out from world coordinates).
Run after scripts/build_world.py and before scripts/build_terrain_lod.py (the ground's levels of detail
come from these heights):

  python3 scripts/build_city_floor.py [prototypes] [--maps 0,1] [--dry]

Prints, per map, the points raised and by how much, and the tiles rewritten.
"""
import glob
import os
import re
import sys

import numpy as np
from matplotlib.tri import LinearTriInterpolator, Triangulation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_detail import decode_tile  # noqa: E402

B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
GRID, CELLS, BS, BLOCKS = 33, 32, 64, 8   # grid points per tile side, cells, raster steps per block, blocks per tile
TS = BS * BLOCKS                          # raster samples per tile side (512)
PCT, COVER, RAISE = 20, 0.6, 3.0
FLAT_TOL = 2.0
CAP = 120.0  # a floor more than this above the terrain is not a floor (the World Tree's crown, Grim Batol's mountain): left to the buildings


def decode_world(s):
    base = (VAL[s[0]] * 64 + VAL[s[1]]) * 64 + VAL[s[2]] - 131072
    h = np.array([(base + VAL[s[3 + i * 2]] * 64 + VAL[s[4 + i * 2]]) * 0.5 for i in range(GRID * GRID)])
    return h.reshape(GRID, GRID)  # [row j (south), column i (east)]


def encode_world(h):
    hh = np.round(np.asarray(h).reshape(-1) * 2).astype(int)
    base = int(hh.min())
    rel = hh - base
    assert rel.max() < 4096, ('height range', rel.max())
    b = base + 131072
    s = B64[(b >> 12) & 63] + B64[(b >> 6) & 63] + B64[b & 63]
    s += ''.join(B64[v >> 6] + B64[v & 63] for v in rel)
    t = int(rel.max())
    return s + B64[t >> 6] + B64[t & 63]


def tile_raster(s):
    """The fine building meshes of a tile as a TS x TS raster of heights (NaN where no block), [row south, col east]."""
    r = np.full((TS, TS), np.nan)
    cx, cy = np.meshgrid(np.arange(BS) + 0.5, np.arange(BS) + 0.5)
    for bi, (base, verts, pal, tris) in decode_tile(s).items():
        v = np.array([(x, y, h) for x, y, h, _ in verts], float)
        tri = Triangulation(v[:, 0], v[:, 1], np.array(tris))
        z = LinearTriInterpolator(tri, v[:, 2])(cx, cy).filled(np.nan)
        bx, by = bi % BLOCKS, bi // BLOCKS
        r[by * BS:(by + 1) * BS, bx * BS:(bx + 1) * BS] = z
    return r


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    maps = None
    if '--maps' in args:
        maps = {int(v) for v in args[args.index('--maps') + 1].split(',')}
    pos = [a for a in args if not a.startswith('--') and not re.fullmatch(r'[0-9,]+', a)]
    root = pos[0] if pos else 'prototypes'
    # building strings per map: fine level only (lines t[key]="D2...")
    detail = {}
    for f in sorted(glob.glob(os.path.join(root, 'GPS3D_*', 'Detail_*.lua'))):
        m = int(re.search(r'Detail_(\d+)', f).group(1))
        for line in open(f):
            mm = re.match(r't\[(\d+)\]="(D2[^"]*)"', line)
            if mm: detail.setdefault(m, {})[int(mm.group(1))] = mm.group(2)
    for wf in sorted(glob.glob(os.path.join(root, 'GPS3D', 'Data', 'World_*.lua'))):
        m = int(re.search(r'World_(\d+)', wf).group(1))
        if (maps and m not in maps) or m not in detail: continue
        lines = open(wf).read().split('\n')
        tiles = {}
        for k, line in enumerate(lines):
            mm = re.match(r'\[(\d+)\]="([^"]*)",$', line)
            if mm: tiles[int(mm.group(1))] = (k, mm.group(2))
        # the map's raster and grid, as world-aligned arrays over the tiles' bounding box
        keys = list(tiles)
        tx0, tx1 = min(k % 64 for k in keys), max(k % 64 for k in keys)
        ty0, ty1 = min(k // 64 for k in keys), max(k // 64 for k in keys)
        NX, NY = tx1 - tx0 + 1, ty1 - ty0 + 1
        R = np.full((NY * TS, NX * TS), np.nan, np.float32)
        nb = 0
        for key, s in detail[m].items():
            tx, ty = key % 64, key // 64
            if not (tx0 <= tx <= tx1 and ty0 <= ty <= ty1): continue
            R[(ty - ty0) * TS:(ty - ty0 + 1) * TS, (tx - tx0) * TS:(tx - tx0 + 1) * TS] = tile_raster(s); nb += 1
        G = np.full((NY * CELLS + 1, NX * CELLS + 1), np.nan)   # the grid, world points (shared edges once)
        Glo = np.full_like(G, np.nan)                           # the lowest of the tiles' heights at a shared point
        for key, (_, s) in tiles.items():
            tx, ty = key % 64, key // 64
            h = decode_world(s)
            sl = (slice((ty - ty0) * CELLS, (ty - ty0) * CELLS + GRID), slice((tx - tx0) * CELLS, (tx - tx0) * CELLS + GRID))
            g, gl = G[sl], Glo[sl]
            G[sl] = np.where(np.isnan(g), h, np.fmax(g, h)); Glo[sl] = np.where(np.isnan(gl), h, np.fmin(gl, h))
        # floor per grid point: the PCT-th percentile of the 16 x 16 samples round it
        Fl = np.full_like(G, np.nan)
        FF = np.zeros_like(G)   # share of the samples within FLAT_TOL of the floor (a floor is flat where it is walked)
        H = BS // 4  # 16 samples = one grid cell
        for j in range(G.shape[0]):
            r0, r1 = j * H - H // 2, j * H + H // 2
            if r1 <= 0 or r0 >= R.shape[0]: continue
            rows = R[max(0, r0):min(R.shape[0], r1)]
            if np.all(np.isnan(rows)): continue
            for i in range(G.shape[1]):
                c0, c1 = i * H - H // 2, i * H + H // 2
                w = rows[:, max(0, c0):min(R.shape[1], c1)]
                ok = ~np.isnan(w)
                if ok.sum() >= COVER * H * H:
                    v = w[ok]; f = np.percentile(v, PCT); Fl[j, i] = f
                    FF[j, i] = np.mean(np.abs(v - f) <= FLAT_TOL)
        cand = np.where(~np.isnan(Fl) & ~np.isnan(Glo) & (Fl > Glo + RAISE) & (Fl <= Glo + CAP), Fl, G)
        cand = np.where(np.isnan(cand), -1e9, cand)
        # opening, 3 x 3: erosion then dilation (a raised area narrower than 3 points goes)
        from scipy.ndimage import grey_dilation, grey_erosion
        opened = grey_dilation(grey_erosion(cand, size=(3, 3), mode='nearest'), size=(3, 3), mode='nearest')
        target = np.where((opened > Glo + RAISE) & ~np.isnan(Fl), opened, -1e9)   # raise only where buildings are and the opened floor is clearly above
        raised = (target > -1e8) & ~np.isnan(G)
        changed = []
        for key, (k, s) in tiles.items():
            tx, ty = key % 64, key // 64
            sl = (slice((ty - ty0) * CELLS, (ty - ty0) * CELLS + GRID), slice((tx - tx0) * CELLS, (tx - tx0) * CELLS + GRID))
            h = decode_world(s)
            nh = np.fmax(h, np.where(raised[sl], target[sl], -1e9))
            if np.any(nh > h + 1e-9):
                ns_ = encode_world(nh)
                assert np.allclose(decode_world(ns_), np.round(nh * 2) / 2), key
                lines[k] = f'[{key}]="{ns_}",'
                changed.append((key, int((nh > h + 1e-9).sum()), float((nh - h).max())))
        dh = (np.where(raised, target, G) - Glo)[raised]
        if os.environ.get('FLOOR_DUMP'): np.savez_compressed(os.environ['FLOOR_DUMP'] + f'_{m}.npz', raise_=np.where(raised, target - Glo, 0), tx0=tx0, ty0=ty0, ff=FF, fl=Fl, glo=Glo)
        print(f'map {m}: {nb} tiles with buildings, {int(raised.sum())} grid points raised (mean {dh.mean() if dh.size else 0:.1f} yd, '
              f'max {dh.max() if dh.size else 0:.1f}), {len(changed)} tiles changed: ' +
              ', '.join(f'{key % 64}_{key // 64} ({n} pts, +{d:.0f})' for key, n, d in sorted(changed, key=lambda c: -c[1])[:12]))
        if changed and not dry:
            if not any('build_city_floor' in l for l in lines[:4]):
                lines.insert(2, '-- City floors raised by scripts/build_city_floor.py (2026-10-24): the ground under cities built on their own buildings.')
            open(wf, 'w').write('\n'.join(lines))


if __name__ == '__main__':
    main()
