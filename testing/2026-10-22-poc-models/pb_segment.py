# Per-building try, step 1: split the area into buildings and street level.
# Top-surface height map (0.5 yd), street level = grey opening of it (40 yd), buildings = connected areas standing
# more than 2.5 yd above street level. Each triangle goes to the building under its centre (if above street level - 1).
import sys, json, numpy as np
from scipy import ndimage
from load import load
from pb_common import sample_tris
name = sys.argv[1] if len(sys.argv) > 1 else 'stormwind'
CELL, HALF = 0.5, 270
m = load(name); P = m['P'].astype(float); T = m['T']
cx, cy = m['meta']['cx'], -m['meta']['cz']
A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
cen = (A + B + C) / 3
inbox = (np.abs(cen[:, 0] - cx) < HALF + 30) & (np.abs(cen[:, 1] - cy) < HALF + 30)
N = int(2 * HALF / CELL)
hmax = np.full((N, N), -1e9)
pts, _ = sample_tris(A[inbox], B[inbox], C[inbox], 0.4)
ix = ((pts[:, 0] - (cx - HALF)) / CELL).astype(int); iy = ((pts[:, 1] - (cy - HALF)) / CELL).astype(int)
ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
np.maximum.at(hmax, (iy[ok], ix[ok]), pts[ok, 2])
del pts
empty = hmax < -1e8
# fill empty cells from the nearest filled one
if empty.any():
    _, (ny, nx) = ndimage.distance_transform_edt(empty, return_indices=True); hmax = hmax[ny, nx]
r = int(40 / CELL)
street = ndimage.grey_opening(hmax, footprint=np.ones((r, r), bool))
street = ndimage.uniform_filter(street, 5)
mask = (hmax - street) > 2.5
mask = ndimage.binary_opening(mask, np.ones((3, 3)))               # drop 1-cell specks
lab, nb = ndimage.label(ndimage.binary_closing(mask, np.ones((3, 3))))
sizes = ndimage.sum(np.ones_like(lab), lab, np.arange(1, nb + 1)) * CELL * CELL
# tiny bits (< 6 yd2: lamp posts, crates) go to street level
small = np.nonzero(sizes < 6)[0] + 1
lab[np.isin(lab, small)] = 0
ids = np.unique(lab[lab > 0]); remap = np.zeros(lab.max() + 1, int); remap[ids] = np.arange(1, len(ids) + 1); lab = remap[lab]
nb = len(ids)
# triangles: building under the centre (footprint grown 1.5 yd so walls at the edge belong to it)
grow = ndimage.grey_dilation(lab, size=(7, 7))
lab2 = np.where(lab > 0, lab, grow)
cix = np.clip(((cen[:, 0] - (cx - HALF)) / CELL).astype(int), 0, N - 1); ciy = np.clip(((cen[:, 1] - (cy - HALF)) / CELL).astype(int), 0, N - 1)
bt = lab2[ciy, cix]
bt[~inbox] = -1
bt[(bt > 0) & (cen[:, 2] < street[ciy, cix] - 1.0)] = 0
np.save(f'{name}_pb_bt.npy', bt)
np.savez_compressed(f'{name}_pb_hf.npz', hmax=hmax, street=street, lab=lab, cx=cx, cy=cy, HALF=HALF, CELL=CELL)
area = np.bincount(lab.reshape(-1), minlength=nb + 1)[1:] * CELL * CELL
print(json.dumps({'buildings': nb, 'tris_in_buildings': int((bt > 0).sum()), 'tris_street': int((bt == 0).sum()), 'tris_outside': int((bt < 0).sum()),
                  'footprint_yd2': {'min': float(area.min()), 'median': float(np.median(area)), 'max': float(area.max())},
                  'street_h': [float(street.min()), float(street.max())]}))
# overlay image: buildings coloured, street level grey by height
from PIL import Image
rng = np.random.default_rng(1); pal = rng.integers(60, 255, (nb + 1, 3)); pal[0] = 0
g = ((street - street.min()) / max(np.ptp(street), 1) * 120 + 40).astype(np.uint8)
img = np.where(lab[..., None] > 0, pal[lab], np.stack([g, g, g], -1)).astype(np.uint8)
Image.fromarray(img[::-1]).save(f'{name}_pb_seg.png')
