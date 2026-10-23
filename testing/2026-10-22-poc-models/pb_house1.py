import json, numpy as np
from load import load
from pb_io import groups, save, cam
m = load('stormwind'); P = m['P'].astype(float); T = m['T']
cen = P[T].mean(1); x0, y0, half = 16374, -25924, 45
k = (np.abs(cen[:, 0] - x0) < half) & (np.abs(cen[:, 1] - y0) < half)
UV = m['UV'][T[k]].reshape(-1, 6)
save('pb_orig_region.json', groups(P, T[k], UV, m['TEX'][k]))
z = np.load('pb_house_region.npz'); save('pb_shell_region.json', groups(z['V'], z['F']))
c = cam()
json.dump([{'out': 'pb_r_orig.png', 'm': 'pb_orig_region.json', 'cam': c}, {'out': 'pb_r_shell.png', 'm': 'pb_shell_region.json', 'cam': c, 'cull': 1}], open('jobs.json', 'w'))
