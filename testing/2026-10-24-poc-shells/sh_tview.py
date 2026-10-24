# Textured shells (baked pages) and the game's own textured geometry, z-buffer renders at the same views.
import sys, json, base64, pickle, numpy as np
from sh_view import cam, gl
def b64(a): return base64.b64encode(np.ascontiguousarray(a, np.float32).tobytes()).decode()
def shell_groups(L):
    S = pickle.load(open(f'sh_faces_{L}.pkl', 'rb')); by = {}
    for f in S['faces']:
        c, tc = f['c'], f['tc']; tri = [(0, 1, 2)] + ([(0, 2, 3)] if len(c) == 4 else [])
        g = by.setdefault(f['page'], ([], []))
        for t in tri: g[0].append(c[list(t)]); g[1].append(tc[list(t)])
    return [{'pos': b64(gl(np.array(p))), 'uv': b64(np.array(u)), 'f': f'shell_L{L}_{pg}', 'flat': 1} for pg, (p, u) in by.items()]
def game_groups():
    d = np.load('sh_in.npz'); tri = d['tri'].astype(float); uv = d['uv']; fd = d['fd']; out = []
    for f in np.unique(fd):
        m = fd == f; out.append({'pos': b64(gl(tri[m])), 'uv': b64(uv[m]), 'f': int(f)})
    return out
VIEWS = {'v90': cam(16400, -25880, 110, 90, 200, 40), 'v200': cam(16426, -25896, 110, 200, 200, 45), 'v420': cam(16426, -25896, 110, 420, 200, 55), 'v2000': cam(16426, -25896, 110, 2000, 200, 50)}
if __name__ == '__main__':
    lods = sys.argv[1].split(',')
    json.dump(game_groups(), open('shtv_game.json', 'w'))
    for L in lods: json.dump(shell_groups(L), open(f'shtv_l{L}.json', 'w'))
    jobs = []
    for vn, c in VIEWS.items():
        jobs.append({'m': 'shtv_game.json', 'cam': c, 'out': f'shtv_{vn}_game.png', 'cull': 1, 'page': 'sh_tview.html'})
        for L in lods: jobs.append({'m': f'shtv_l{L}.json', 'cam': c, 'out': f'shtv_{vn}_l{L}.png', 'cull': 1, 'page': 'sh_tview.html'})
    json.dump(jobs, open('shtv_jobs.json', 'w'))
