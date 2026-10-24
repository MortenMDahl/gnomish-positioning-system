# Fills the empty pixels (alpha 0) of every baked picture from the nearest painted pixel of the same picture; a
# picture with nothing painted takes its unit's average colour. Writes the final pages shells/L<lod>_<page>.png (RGB).
# Usage: python3 sh_fill.py <lod> <out dir>
import sys, os, pickle, numpy as np
from PIL import Image
from scipy import ndimage
L, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
S = pickle.load(open(f'sh_faces_{L}.pkl', 'rb')); pics = S['pics']
pages = [np.asarray(Image.open(f'shb_{L}_{i}.png').convert('RGBA')).copy() for i in range(S['npages'])]
PAD = 2
unit_col = {}
for p in pics:   # a unit's average colour over its painted pixels
    a = pages[p['page']][p['y']:p['y'] + p['h'], p['x']:p['x'] + p['w']]
    m = a[..., 3] >= 250
    if m.any():
        s = unit_col.setdefault(p['unit'], [np.zeros(3), 0]); s[0] += a[..., :3][m].sum(0); s[1] += m.sum()
empty = filled = 0
out = [pg.copy() for pg in pages]
for p in pics:
    x, y, w, h = p['x'], p['y'], p['w'], p['h']
    a = pages[p['page']][y:y + h, x:x + w].astype(float)
    # (only solid pixels are sources: an edge pixel the antialiasing blended with the empty, black background is
    # dark, and filling from it smeared black over whole faces; with no solid pixel, the edge pixels un-blended)
    m = a[..., 3] >= 250
    if not m.any() and (a[..., 3] > 0).any():
        m = a[..., 3] > 0; a[..., :3] = np.where(m[..., None], np.clip(a[..., :3] * 255 / np.maximum(a[..., 3:4], 1), 0, 255), a[..., :3])
    if not m.any():
        s = unit_col.get(p['unit']); c = s[0] / max(s[1], 1) if s else np.array([128, 128, 128])
        a[..., :3] = c; empty += 1
    elif not m.all():
        _, (ii, jj) = ndimage.distance_transform_edt(~m, return_indices=True)
        a[..., :3] = a[ii, jj, :3]; filled += 1
    a[..., 3] = 255
    # padding: the picture's edge pixels copied outwards (no bleeding of neighbours into mip levels)
    x0, y0, x1, y1 = max(0, x - PAD), max(0, y - PAD), x + w + PAD, y + h + PAD
    big = np.pad(a, ((y - y0, y1 - (y + h)), (x - x0, x1 - (x + w)), (0, 0)), mode='edge')
    out[p['page']][y0:y1, x0:x1] = big[:out[p['page']].shape[0] - y0, :out[p['page']].shape[1] - x0].astype(np.uint8)
# the page's unused space: each pixel takes its nearest picture's colour (no black creeping into the pictures'
# edges at the smaller mip levels, far away)
used = [np.zeros(pg.shape[:2], bool) for pg in out]
for p in pics:
    used[p['page']][max(0, p['y'] - PAD):p['y'] + p['h'] + PAD, max(0, p['x'] - PAD):p['x'] + p['w'] + PAD] = True
for pg, u in zip(out, used):
    if u.any() and not u.all():
        _, (ii, jj) = ndimage.distance_transform_edt(~u, return_indices=True)
        pg[..., :3] = pg[ii, jj, :3]
for i, pg in enumerate(out):
    Image.fromarray(pg[..., :3]).save(os.path.join(OUT, f'L{L}_{i}.png'), optimize=True)
print({'lod': L, 'pictures': len(pics), 'partly_empty_filled': filled, 'wholly_empty': empty, 'bytes_png': sum(os.path.getsize(os.path.join(OUT, f'L{L}_{i}.png')) for i in range(len(out)))})
