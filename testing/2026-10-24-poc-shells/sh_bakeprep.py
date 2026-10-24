# S1 shells: bake frames and atlas layout for one level of detail.
# Faces never seen in the visibility pass (sh_vis.py) are dropped. Every region's top is one picture (its faces share
# it); every wall is its own picture. A picture is an orthographic view of the unit's own game geometry along the
# face's normal (from outside), clipped to a slab around the face, at PPY pixels per yard, packed into 2048 x 2048
# pages with 2 px of padding. Writes sh_bake_<lod>.json (jobs per page) and sh_faces_<lod>.pkl (faces with their
# texture coordinates in the pages). Also writes the game geometry for the baker once (sh_geo.bin, sh_geo.json).
# Usage: python3 sh_bakeprep.py <lod> <px per yd>
import sys, os, json, pickle, numpy as np
L = int(sys.argv[1]); PPY = float(sys.argv[2])
PAGE, PAD = 2048, 2
SLAB = {'wall': (3.0, 5.0), 'roof': (15.0, 3.0)}   # yd in front of (outside) / behind the face
R = pickle.load(open(f'sh_shells_{L}.pkl', 'rb')); F = np.load(f'sh_vis_{L}.npz')['front']
d = np.load('sh_in.npz')
if not os.path.exists('sh_geo.bin') or os.environ.get('REGEO'):
    tri = d['tri'].astype(np.float32); uv = d['uv'].astype(np.float32); fd = d['fd']; bld = d['bld'].copy(); st = d['street']
    # streets: pseudo-units per 60-yd cell (-1000 - cell), so a picture renders only the streets near it
    cen = tri.mean(1); cell = (np.floor((cen[:, 0] - 16000) / 60) * 100 + np.floor((cen[:, 1] + 26400) / 60)).astype(int)
    bld[st] = -1000 - cell[st]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    SUN = np.array([-0.4, 0.8, -0.35]); SUN = SUN / np.linalg.norm(SUN)   # east, up, south (GPS3D.lua's SUN)
    shade = 0.55 + 0.45 * np.abs(n[:, 0] * SUN[0] + n[:, 2] * SUN[1] - n[:, 1] * SUN[2])
    order = np.lexsort((fd, bld)); tri, uv, fd, bld, shade, both = tri[order], uv[order], fd[order], bld[order], shade[order], d['both'][order]
    gl = np.stack([tri[..., 0], tri[..., 2], -tri[..., 1]], -1).astype(np.float32)
    texs = sorted(set(int(x) for x in fd)); ti = np.searchsorted(texs, fd)
    # groups: (unit, texture, both sides) runs
    key = np.stack([bld, ti, both], 1); brk = np.r_[0, np.nonzero(np.any(key[1:] != key[:-1], 1))[0] + 1, len(key)]
    groups = [[int(bld[a]), int(texs[ti[a]]), int(both[a]), int(a), int(b - a)] for a, b in zip(brk[:-1], brk[1:])]
    with open('sh_geo.bin', 'wb') as fh:
        fh.write(gl.tobytes()); fh.write(uv.astype(np.float32).tobytes()); fh.write(np.repeat(shade, 3).astype(np.float32).tobytes())
    boxes = {}
    for u in np.unique(bld):
        m = bld == u; P_ = tri[m].reshape(-1, 3); boxes[int(u)] = [float(x) for x in np.r_[P_.min(0), P_.max(0)]]
    json.dump({'n': int(len(gl)), 'groups': groups, 'boxes': boxes}, open('sh_geo.json', 'w'))
    print('geometry', len(gl), 'triangles,', len(groups), 'groups,', len(texs), 'textures')

def area(c):
    a = np.linalg.norm(np.cross(c[1] - c[0], c[2] - c[0])) / 2
    return a + (np.linalg.norm(np.cross(c[2] - c[0], c[3] - c[0])) / 2 if len(c) == 4 else 0)
pics = []   # picture: unit, kind, o (world point), u, v, n (unit vectors, world), u0, u1, v0, v1, faces
faces = []; k = 0
for U in R:
    reg_pic = {}
    th = U.get('th', 0.0)
    for f in U['faces']:
        seen = F[k] > 0; k += 1
        if not seen: continue
        c = f['c']
        if f['kind'] == 'wall':
            e = c[1] - c[0] if np.hypot(*(c[1] - c[0])[:2]) > 1e-6 else c[2] - c[1]
            u = np.array([e[0], e[1], 0.0]); u /= np.linalg.norm(u); v = np.array([0, 0, 1.0]); n = np.cross(u, v)
            pics.append(dict(unit=U['unit'], kind='wall', u=u, v=v, n=n, pts=[c], faces=[len(faces)]))
            faces.append(dict(unit=U['unit'], kind='wall', c=c, pic=len(pics) - 1))
        else:
            key = f['reg']
            if key not in reg_pic:
                reg_pic[key] = len(pics); pics.append(dict(unit=U['unit'], kind='roof', pts=[], faces=[], nacc=np.zeros(3)))
            p = pics[reg_pic[key]]; p['pts'].append(c); p['faces'].append(len(faces))
            nn = np.cross(c[1] - c[0], c[2] - c[0]); p['nacc'] += nn
            faces.append(dict(unit=U['unit'], kind='roof', c=c, pic=reg_pic[key]))
    for key, pi in reg_pic.items():
        p = pics[pi]; n = p['nacc'] / np.linalg.norm(p['nacc'])
        u = np.array([np.cos(th), np.sin(th), 0.0]); u -= n * (u @ n)
        if np.linalg.norm(u) < 0.3: u = np.array([-np.sin(th), np.cos(th), 0.0]); u -= n * (u @ n)
        u /= np.linalg.norm(u); v = np.cross(n, u)
        p.update(u=u, v=v, n=n)
for p in pics:
    P = np.vstack(p['pts']); o = P.mean(0)
    pu, pv = (P - o) @ p['u'], (P - o) @ p['v']
    p['o'] = o; p['u0'], p['u1'], p['v0'], p['v1'] = pu.min(), pu.max(), pv.min(), pv.max()
    p['w'] = max(2, int(np.ceil((p['u1'] - p['u0']) * PPY))); p['h'] = max(2, int(np.ceil((p['v1'] - p['v0']) * PPY)))
    if p['w'] > PAGE - 2 * PAD or p['h'] > PAGE - 2 * PAD:   # (too big for a page: fewer pixels per yard for this one)
        s = (PAGE - 2 * PAD) / max(p['w'], p['h']); p['w'], p['h'] = max(2, int(p['w'] * s)), max(2, int(p['h'] * s))
# shelf packing, tallest first
order = sorted(range(len(pics)), key=lambda i: (-pics[i]['h'], -pics[i]['w']))
page, x, y, shelf = 0, 0, 0, 0
for i in order:
    p = pics[i]; W, H = p['w'] + 2 * PAD, p['h'] + 2 * PAD
    if x + W > PAGE: x, y, shelf = 0, y + shelf, 0
    if y + H > PAGE: page, x, y, shelf = page + 1, 0, 0, 0
    p['page'], p['x'], p['y'] = page, x + PAD, y + PAD
    x += W; shelf = max(shelf, H)
npages = page + 1
# texture coordinates of every face corner (0..1 in its page, v down)
for f in faces:
    p = pics[f['pic']]; q = f['c'] - p['o']
    uu = (q @ p['u'] - p['u0']) / max(p['u1'] - p['u0'], 1e-9); vv = (q @ p['v'] - p['v0']) / max(p['v1'] - p['v0'], 1e-9)
    f['tc'] = np.stack([(p['x'] + uu * p['w']) / PAGE, (p['y'] + (1 - vv) * p['h']) / PAGE], 1)
    f['page'] = p['page']
GEO = json.load(open('sh_geo.json')); UB = {int(k): np.array(v) for k, v in GEO['boxes'].items()}
UK = np.array(list(UB.keys())); UBX = np.array([UB[k] for k in UK])
def near_units(p):
    fr, bk = SLAB[p['kind']]
    cs = np.array([p['o'] + p['u'] * a + p['v'] * b + p['n'] * c for a in (p['u0'], p['u1']) for b in (p['v0'], p['v1']) for c in (-bk, fr)])
    lo, hi = cs.min(0), cs.max(0)
    ok = np.all(UBX[:, :3] <= hi + 0.5, 1) & np.all(UBX[:, 3:] >= lo - 0.5, 1)
    return [int(x) for x in UK[ok]]
def gl(v): return [float(v[0]), float(v[2]), float(-v[1])]
jobs = [[] for _ in range(npages)]
for p in pics:
    fr, bk = SLAB[p['kind']]
    jobs[p['page']].append(dict(units=near_units(p), x=p['x'], y=p['y'], w=p['w'], h=p['h'], o=gl(p['o']), u=gl(p['u']), v=gl(p['v']), n=gl(p['n']),
                                u0=float(p['u0']), u1=float(p['u1']), v0=float(p['v0']), v1=float(p['v1']), front=fr, back=bk))
json.dump({'page': PAGE, 'pages': jobs}, open(f'sh_bake_{L}.json', 'w'))
pickle.dump(dict(faces=faces, pics=[{k: p[k] for k in ('unit', 'kind', 'page', 'x', 'y', 'w', 'h')} for p in pics], npages=npages, ppy=PPY), open(f'sh_faces_{L}.pkl', 'wb'))
used = sum((p['w'] + 2 * PAD) * (p['h'] + 2 * PAD) for p in pics)
print(json.dumps({'lod': L, 'ppy': PPY, 'faces_kept': len(faces), 'faces_dropped_unseen': int(k - len(faces)), 'pictures': len(pics), 'pages': npages,
                  'px_used_M': round(used / 1e6, 2), 'fill': round(used / (npages * PAGE * PAGE), 3), 'dxt1_MB_est': round(npages * PAGE * PAGE * 0.5 * 4 / 3 / 1e6, 1)}))
