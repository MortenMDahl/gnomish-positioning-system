# Measures the open sea in the shots of scn_seaview.py (shots/sv_<TAG>_*.png, shots/sv_<TAG>.json):
# per view, the most common colour (the sea), how far the open-sea pixels (more than 6 px from anything else)
# stray from it (largest channel difference: max, 99.9th percentile, share over 2 levels), the share of the
# minimap's darker sea tone (8, 13, 16) that drew the triangles, and the colours (3 x 3 px) on either side of
# edges in the sea north-east of Azshara (the ground's last tiles against the sea beyond; a coastal tile's sea
# against the open-sea tile next to it), and the largest difference along the old tan line north-east of Azshara
# from the sea 0.4 tile further out. Usage: python3 measure_sea.py <TAG> [--json out.json]
import json, sys
import numpy as np
from PIL import Image

DARK = np.array([8, 13, 16])


def erode(mask, r):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out &= np.roll(np.roll(mask, dy, 0), dx, 1)
    out[:r] = out[-r:] = False
    out[:, :r] = out[:, -r:] = False
    return out


def measure(tag):
    meta = json.load(open('shots/sv_%s.json' % tag))
    res = {}
    for name, info in meta.items():
        a = np.asarray(Image.open('shots/sv_%s_%s.png' % (tag, name)).convert('RGB')).astype(int)
        flat = a.reshape(-1, 3)
        vals, counts = np.unique(flat, axis=0, return_counts=True)
        mode = vals[counts.argmax()]
        sea = np.abs(a - mode).max(2) <= 12
        open_ = erode(sea, 6)
        d = np.abs(a - mode).max(2)[open_]
        dark = (np.abs(a - DARK).max(2) <= 1)[open_]
        r = dict(mode=[int(v) for v in mode], open_px=int(open_.sum()), spread_max=int(d.max()) if d.size else None,
                 spread_p999=float(np.percentile(d, 99.9)) if d.size else None, over2=round(float((d > 2).mean()), 4) if d.size else None,
                 dark_share=round(float(dark.mean()), 4) if d.size else None, state=info['state'])
        edge = {}
        H, W = a.shape[:2]
        for k, side, x, y in info.get('edge', []):
            x, y = int(round(x)), int(round(y))
            if 2 <= x < W - 2 and 2 <= y < H - 2:
                edge.setdefault(k, {})[side] = [round(float(v), 1) for v in a[y - 1:y + 2, x - 1:x + 2].reshape(-1, 3).mean(0)]
        diffs = [round(max(abs(p - q) for p, q in zip(e['in'], e['out'])), 1) for e in edge.values() if 'in' in e and 'out' in e]
        r['edge'] = edge
        # the old line north-east of Azshara: the largest difference along it from the sea 0.4 tile further out
        ld = [int(np.abs(a[int(round(y)), int(round(x))] - a[int(round(ry)), int(round(rx))]).max()) for x, y, rx, ry in info.get('line', [])
              if 0 <= round(x) < W and 0 <= round(y) < H and 0 <= round(rx) < W and 0 <= round(ry) < H]
        r['line_max'] = max(ld) if ld else None
        r['edge_diff_max'] = max(diffs) if diffs else None
        res[name] = r
    return res


if __name__ == '__main__':
    tag = sys.argv[1]
    res = measure(tag)
    for name, r in res.items():
        print('%-10s mode %-14s open %7d  spread max %s p99.9 %s >2: %s  dark tone %s  edge diff %s  line %s  [%s]' % (
            name, r['mode'], r['open_px'], r['spread_max'], r['spread_p999'], r['over2'], r['dark_share'], r['edge_diff_max'], r['line_max'], r['state']))
    if '--json' in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
