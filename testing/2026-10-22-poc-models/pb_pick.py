# Cut one building out of the region's shell: region-grow its roof on the shell's top height map from a seed point
# (neighbours within 1 yd of height = same roof; steps over 1 yd = its edge), footprint = roof grown by 1 yd
import sys, json, numpy as np
from scipy import ndimage
from PIL import Image
from pb_common import sample_tris
z = np.load(sys.argv[1]); V, F = z['V'], z['F']
sx, sy = float(sys.argv[2]), float(sys.argv[3]); out = sys.argv[4]
CELL = 0.25
A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
pts, _ = sample_tris(A, B, C, 0.2)
x0, y0 = pts[:, 0].min(), pts[:, 1].min()
nx, ny = int((pts[:, 0].max() - x0) / CELL) + 1, int((pts[:, 1].max() - y0) / CELL) + 1
H = np.full((ny, nx), -1e9)
np.maximum.at(H, (((pts[:, 1] - y0) / CELL).astype(int), ((pts[:, 0] - x0) / CELL).astype(int)), pts[:, 2])
H = ndimage.grey_closing(H, size=(3, 3))
gy, gx = ndimage.sobel(H, 0) / (8 * CELL), ndimage.sobel(H, 1) / (8 * CELL)
step = np.hypot(gx, gy) > 2.5          # slope over ~68 degrees = wall
lab, n = ndimage.label(~step)
k = lab[int((sy - y0) / CELL), int((sx - x0) / CELL)]
roof = ndimage.binary_closing(lab == k, iterations=4)
roof = ndimage.binary_fill_holes(roof)
foot = ndimage.binary_dilation(roof, iterations=int(1.0 / CELL))
ring = ndimage.binary_dilation(foot, iterations=int(4 / CELL)) & ~ndimage.binary_dilation(foot, iterations=int(1 / CELL))
base = float(np.percentile(H[ring], 10))
cen = V[F].mean(1)
ci = np.clip(((cen[:, 1] - y0) / CELL).astype(int), 0, ny - 1); cj = np.clip(((cen[:, 0] - x0) / CELL).astype(int), 0, nx - 1)
keep = foot[ci, cj] & (cen[:, 2] > base - 0.5)
Fk = F[keep]; used, inv = np.unique(Fk, return_inverse=True)
np.savez_compressed(out, V=V[used], F=inv.reshape(-1, 3), base=base)
img = np.where(foot, 255, ((H - H[H > -1e8].min()) / np.ptp(H[H > -1e8]) * 150).clip(0, 150)).astype(np.uint8)[::-1]
Image.fromarray(img).save(out.replace('.npz', '_foot.png'))
print(json.dumps({'roof_yd2': float(roof.sum() * CELL * CELL), 'foot_yd2': float(foot.sum() * CELL * CELL), 'base_h': base, 'roof_h': [float(H[roof].min()), float(H[roof].max())], 'tris': int(len(Fk))}))
