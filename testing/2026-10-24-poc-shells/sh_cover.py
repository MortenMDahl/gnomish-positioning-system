# Coverage from straight above: cells (0.5 yd) with game geometry but no shell top, and the other way round.
import sys, pickle, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from pb_common import sample_tris
L = sys.argv[1]; R2 = 0.5
d = np.load('sh_in.npz'); T = d['tri'].astype(float)
lo = T.reshape(-1, 3).min(0) - 2; hi = T.reshape(-1, 3).max(0) + 2
nx, ny = int((hi[0] - lo[0]) / R2) + 1, int((hi[1] - lo[1]) / R2) + 1
def rast(tris, spacing=0.4):
    g = np.zeros(ny * nx, bool)
    for i in range(0, len(tris), 5000):
        t = tris[i:i + 5000]
        p, _ = sample_tris(t[:, 0], t[:, 1], t[:, 2], spacing)
        g[np.floor((p[:, 1] - lo[1]) / R2).astype(int) * nx + np.floor((p[:, 0] - lo[0]) / R2).astype(int)] = True
    return g.reshape(ny, nx)
game = rast(T)
S = pickle.load(open(f'sh_faces_{L}.pkl', 'rb'))
tr = []
for f in S['faces']:
    c = f['c']; tr.append(c[[0, 1, 2]])
    if len(c) == 4: tr.append(c[[0, 2, 3]])
shell = rast(np.array(tr))
miss = game & ~shell; extra = shell & ~game
print({'lod': L, 'game_yd2': int(game.sum() * R2 * R2), 'shell_yd2': int(shell.sum() * R2 * R2), 'missing_yd2': int(miss.sum() * R2 * R2), 'missing_share': round(miss.sum() / game.sum(), 3), 'extra_yd2': int(extra.sum() * R2 * R2)})
img = np.zeros((ny, nx, 3)); img[game & shell] = (0.6, 0.6, 0.6); img[miss] = (1, 0, 0); img[extra] = (0, 0.4, 1)
plt.figure(figsize=(14, 14)); plt.imshow(img[::-1], extent=(lo[0], lo[0] + nx * R2, lo[1], lo[1] + ny * R2)); plt.title(f'L{L}: grey both, red game only, blue shell only'); plt.savefig(f'sh_cover_{L}.png', dpi=60)
