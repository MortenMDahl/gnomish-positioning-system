# The game's own triangles (80 yd round the close Stormwind view) as addon data, after the finer hidden-part pass:
# texfine = every triangle seen at all; texfine1 = minus pieces under 1 yd2. Seen only from the back: flipped; seen
# from both sides: flagged (drawn from both). Cut to 10-yd pieces as the other textured data (painter's sorting).
import sys, re, json, numpy as np
sys.path.insert(0, '/home/claude/wt/poc/testing/2026-10-22-poc-models')
src = open('/home/claude/wt/poc/testing/2026-10-22-poc-models/to_lua.py').read()
exec(src[:src.index("out = ['--")])          # (subdivide only)
from load import load
m = load('stormwind'); P = m['P'].astype(float); T = m['T'].copy(); UVa = m['UV'].astype(float)
v = np.load('pbv80_vis.npz'); fr, bk = v['front'], v['back']
cx, cy = m['meta']['cx'], -m['meta']['cz']
cen = P[T].mean(1)
near = np.hypot(cen[:, 0] - cx, cen[:, 1] - cy) < 80
A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
area = np.linalg.norm(np.cross(B - A, C - A), axis=1) / 2
lines, info = [], {}
for key, keep in (('texfine', near & ((fr + bk) >= 1)), ('texfine1', near & ((fr + bk) >= 1) & (area >= 1.0))):
    idx = np.nonzero(keep)[0]
    Tk = T[idx].copy(); UVc = UVa[Tk]                       # (n, 3, 2)
    flip = (fr[idx] == 0) & (bk[idx] >= 1)
    Tk[flip] = Tk[flip][:, [0, 2, 1]]; UVc[flip] = UVc[flip][:, [0, 2, 1]]
    both = ((fr[idx] >= 1) & (bk[idx] >= 1)).astype(int)
    used, inv = np.unique(Tk.reshape(-1), return_inverse=True)
    V = P[used]; T2 = inv.reshape(-1, 3)
    V, T2, Fi, UVc = subdivide(V, T2, C=np.arange(len(T2)), UV=UVc)
    F = m['TEX'][idx][Fi]; Bf = both[Fi]
    f = lambda a, fmt: ','.join(fmt % x for x in a)
    lines.append(f'ns.PocData.stormwind.{key} = {{ map = 0, v = {{{f(V.reshape(-1), "%.2f")}}}, t = {{{f((T2 + 1).reshape(-1), "%d")}}}, uv = {{{f(UVc.reshape(-1), "%.4f")}}}, f = {{{f(F, "%d")}}}, b = {{{f(Bf, "%d")}}} }}')
    info[key] = {'game_tris': int(len(idx)), 'after_10yd_cut': int(len(T2)), 'flipped': int(flip.sum()), 'both_sides': int(both.sum()), 'lua_bytes': len(lines[-1])}
info['all_game_tris_80yd'] = int(near.sum())
path = '/home/claude/wt/poc/prototypes/GPS3D/PocData.lua'
s = open(path).read()
s = re.sub(r'ns\.PocData\.stormwind\.texfine1? = [^\n]*\n', '', s)
open(path, 'w').write(s + '\n'.join(lines) + '\n')
print(json.dumps(info))
