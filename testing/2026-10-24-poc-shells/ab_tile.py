# All buildings, phase 1 (S1e, 2026-10-24): whole-block shells (66.7 yd, the coverage build's level 4) for one ADT
# tile from the tile export (gps_tile_export.ts: bins/<map>_<x>_<y>.bin), baked at 0.75 px a yard.
#   1. the tile's WMO triangles; those wholly more than 2 yd under the ground grid (prototypes/GPS3D/Data/World_<map>.lua,
#      the drawn ground) dropped (caves' tunnels, cellars), and on map 0 those inside the Trade District square, which
#      has its own finer shells (its blocks there are completed outside the square);
#   2. sh_build3.py 4 (owners: the 66.7-yd blocks) on them, every face kept (no visibility pass);
#   3. sh_bakeprep.py 4 0.75, sh_bake.py (WebGL, the game's textures), sh_fill.py.
# Usage: python3 ab_tile.py <map> <tx> <ty> <bins dir> <work root>   (PORT for the baker if several run at once)
import sys, os, json, struct, shutil, subprocess, time, base64, numpy as np
M, TX, TY, BINS, ROOT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', '/home/claude/wt/poc')
TILE = 1600 / 3
SQUARE = (0, 16426.667 - 260, 16426.667 + 260, -25896.533 - 260, -25896.533 + 260)   # (map, x0, x1, y0, y1): the Trade District export square (raw/stormwind.json, +-R), which has its own finer shells
# building models left to the old simplified blocks: Orgrimmar's city model (its cliffs overhang the streets, and a
# 2.5D shell, the highest surface over each spot, roofs the city over with rock, grey where nothing was baked)
SKIP_WMO = {int(v) for v in os.environ.get('SKIP_WMO', '7964229').split(',') if v}
# (S1f, option 1) parts of a building model left out by texture: OPTION1="<model fdid>:<tex>,<tex>,...", e.g. Orgrimmar's
# cliffs and canyon floor (7964229: textures 0, 8250846, 8250845, 8253979), so only its buildings get shells
DROP_TEX = {}
for spec in [v for v in os.environ.get('OPTION1', '').split(';') if v]:
    m_, t_ = spec.split(':'); DROP_TEX[int(m_)] = {int(v) for v in t_.split(',')}
LAYERS = int(os.environ.get('LAYERS', '1'))   # (S1f, option 2) 2: a second layer of shells under every overhang
TEX0_FILL = os.environ.get('TEX0_FILL', '0') == '1'   # (S1f) used by both option runs; off by default (the shipped S1e data had it off)
key = f'{M}_{TX}_{TY}'
W = os.path.join(ROOT, key); os.makedirs(W, exist_ok=True)
T0 = time.time()
def log(**k): print(json.dumps(dict(tile=key, s=round(time.time() - T0, 1), **k)), flush=True)
# --- 1. triangles
buf = open(os.path.join(BINS, key + '.bin'), 'rb').read(); o = 0; P, UV, FD = [], [], []
while o < len(buf):
    uid, fdid, nv, nt = struct.unpack_from('<4i', buf, o); o += 16
    pos = np.frombuffer(buf, np.float32, nv * 3, o).reshape(nv, 3); o += nv * 12
    uv = np.frombuffer(buf, np.float32, nv * 2, o).reshape(nv, 2); o += nv * 8
    idx = np.frombuffer(buf, np.uint32, nt * 3, o).reshape(nt, 3); o += nt * 12
    tx = np.frombuffer(buf, np.uint32, nt, o); o += nt * 4
    if fdid in SKIP_WMO: continue
    keep_t = np.ones(nt, bool)
    if fdid in DROP_TEX: keep_t = ~np.isin(tx, list(DROP_TEX[fdid]))
    t3 = pos[idx]
    # (S1f) triangles with no texture (a material the reader gives none: 40 % of Orgrimmar's model, baked grey) take
    # the model's texture with the most area in this tile
    tx = tx.copy()
    if TEX0_FILL and (tx == 0).any() and (tx != 0).any():
        ar = np.linalg.norm(np.cross(t3[:, 1] - t3[:, 0], t3[:, 2] - t3[:, 0]), axis=1)
        nzm = tx != 0; ids, inv = np.unique(tx[nzm], return_inverse=True); tx[tx == 0] = ids[np.bincount(inv, weights=ar[nzm]).argmax()]
    P.append(t3[keep_t]); UV.append(uv[idx][keep_t]); FD.append(tx[keep_t])
if not P: print(json.dumps(dict(tile=key, empty=True, skipped_models=True))); sys.exit(0)
tri, uv, fd = np.concatenate(P).astype(float), np.concatenate(UV).astype(float), np.concatenate(FD).astype(np.int64)
# the ground grid round the tile (3 x 3 tiles, missing ones at the lowest height seen)
B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'; VAL = {c: i for i, c in enumerate(B64)}
_world = {}
def world(m):
    if m not in _world:
        import re
        t = {}
        for line in open(os.path.join(REPO, 'prototypes/GPS3D/Data', f'World_{m}.lua')):
            mm = re.match(r'\[(\d+)\]="([^"]*)",$', line.strip())
            if mm: t[int(mm.group(1))] = mm.group(2)
        _world[m] = t
    return _world[m]
def grid(m, tx, ty):
    s = world(m).get(ty * 64 + tx)
    if not s: return None
    base = (VAL[s[0]] * 64 + VAL[s[1]]) * 64 + VAL[s[2]] - 131072
    return np.array([(base + VAL[s[3 + i * 2]] * 64 + VAL[s[4 + i * 2]]) * 0.5 for i in range(33 * 33)]).reshape(33, 33)
G = np.full((97, 97), np.nan)
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        g = grid(M, TX + dx, TY + dy)
        if g is not None: G[(dy + 1) * 32:(dy + 1) * 32 + 33, (dx + 1) * 32:(dx + 1) * 32 + 33] = g
G = np.where(np.isnan(G), np.nanmin(G) if np.isfinite(np.nanmin(G)) else 0, G)
def ground(x, y):
    fx = np.clip((np.asarray(x) / TILE - (TX - 1)) * 32, 0, 95.999); fy = np.clip((-np.asarray(y) / TILE - (TY - 1)) * 32, 0, 95.999)
    i, j = np.floor(fy).astype(int), np.floor(fx).astype(int); a, b = fy - i, fx - j
    return G[i, j] * (1 - a) * (1 - b) + G[i, j + 1] * (1 - a) * b + G[i + 1, j] * a * (1 - b) + G[i + 1, j + 1] * a * b
n0 = len(tri)
under = (tri[..., 2] < ground(tri[..., 0], tri[..., 1]) - 2).all(1)
cen = tri.mean(1)
inside = np.zeros(len(tri), bool)
if M == SQUARE[0]: inside = (cen[:, 0] >= SQUARE[1]) & (cen[:, 0] <= SQUARE[2]) & (cen[:, 1] >= SQUARE[3]) & (cen[:, 1] <= SQUARE[4])
keep = ~under & ~inside
# degenerate triangles out
e = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1); keep &= e > 1e-6
tri, uv, fd = tri[keep], uv[keep], fd[keep]
if len(tri) == 0: log(empty=True, tris=n0); sys.exit(0)
BLK = TILE / 8
c2 = tri.mean(1); blk = (np.floor(c2[:, 0] / BLK).astype(int) - 230) * 1000 + (np.floor(-c2[:, 1] / BLK).astype(int) - 300)
np.savez_compressed(os.path.join(W, 'sh_in.npz'), tri=tri.astype(np.float32), uv=uv.astype(np.float32), fd=fd, both=np.ones(len(tri), np.int8),
                    bld=(-2 - blk).astype(np.int64), street=np.zeros(len(tri), bool), piece=np.zeros(len(tri), np.int64))
# sw_ground.json stand-in: 385 x 385 points TILE/128 apart over the 3 x 3 tiles (x, h, z), as sh_build2.py reads
gs = TILE / 128; xs = (TX - 1) * TILE + np.arange(385) * gs; zs = (TY - 1) * TILE + np.arange(385) * gs
XX, ZZ = np.meshgrid(xs, zs); HH = ground(XX, -ZZ)
gp = np.stack([XX, HH, ZZ], -1).reshape(-1, 3).astype(np.float32)
json.dump({'g': {'pos': base64.b64encode(gp.tobytes()).decode()}}, open(os.path.join(W, 'sw_ground.json'), 'w'))
log(step='prep', tris=int(len(tri)), dropped_under=int(under.sum()), dropped_square=int(inside.sum()), blocks=int(len(np.unique(blk))))
# --- 2. shells
def run(*a, env=None):
    r = subprocess.run([sys.executable, *a], cwd=W, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if r.returncode: print(r.stdout[-2000:], r.stderr[-3000:], file=sys.stderr); raise SystemExit(f'{a[0]} failed')
    return r.stdout.strip().split('\n')[-1]
out = run(os.path.join(HERE, 'sh_build3.py'), '4'); log(step='build', out=json.loads(out))
import pickle
R = pickle.load(open(os.path.join(W, 'sh_shells_4.pkl'), 'rb'))
if LAYERS == 2:
    import shapely
    from shapely import vectorized
    # every region that stands clear of the ground (a floating region, or one whose base is more than LIFT yd over the
    # ground there): an underside (its polygon at its base, facing down), and the triangles under it make a lower layer
    LIFT = 3.0
    raised = []
    for U in R:
        for ri, r in enumerate(U['regions']):
            c = r['poly'].representative_point()
            if r['base'] > float(ground(c.x, c.y)) + LIFT:
                raised.append(r)
                for t in shapely.constrained_delaunay_triangles(r['poly']).geoms:
                    cs = np.asarray(shapely.orient_polygons(t).exterior.coords)[:-1][::-1]   # (clockwise from above: faces down)
                    U['faces'].append(dict(kind='under', reg=('u', ri), c=np.array([(x, y, r['base']) for x, y in cs])))
    pickle.dump(R, open(os.path.join(W, 'sh_shells_4.pkl'), 'wb'))
    lower = np.zeros(len(tri), bool)
    cen3 = tri.mean(1); top3 = tri[..., 2].max(1)
    for r in raised:
        inside_r = vectorized.contains(r['poly'], cen3[:, 0], cen3[:, 1])
        lower |= inside_r & (top3 < r['base'] - 0.5)
    log(step='layers', raised_regions=len(raised), lower_tris=int(lower.sum()))
    if lower.sum() > 0:
        WB = os.path.join(W, 'b'); os.makedirs(WB, exist_ok=True)
        tb = tri[lower]; cb = tb.mean(1); bb = (np.floor(cb[:, 0] / BLK).astype(int) - 230) * 1000 + (np.floor(-cb[:, 1] / BLK).astype(int) - 300)
        np.savez_compressed(os.path.join(WB, 'sh_in.npz'), tri=tb.astype(np.float32), uv=uv[lower].astype(np.float32), fd=fd[lower], both=np.ones(len(tb), np.int8),
                            bld=(-2 - bb).astype(np.int64), street=np.zeros(len(tb), bool), piece=np.zeros(len(tb), np.int64))
        shutil.copy(os.path.join(W, 'sw_ground.json'), WB)
        rb = subprocess.run([sys.executable, os.path.join(HERE, 'sh_build3.py'), '4'], cwd=WB, capture_output=True, text=True)
        if rb.returncode: print(rb.stderr[-2000:], file=sys.stderr); raise SystemExit('lower layer build failed')
        RB = pickle.load(open(os.path.join(WB, 'sh_shells_4.pkl'), 'rb'))
        nfb = sum(len(U['faces']) for U in RB)
        log(step='lower layer', units=len(RB), faces=nfb)
        if nfb:
            np.savez(os.path.join(WB, 'sh_vis_4.npz'), front=np.ones(nfb, np.int32))
            for f in ('sh_bake.html', 'three.module.min.js'): shutil.copy(os.path.join(HERE, f), WB)
            if not os.path.exists(os.path.join(WB, 'tex')): os.symlink(os.environ.get('TEXPNG', '/home/claude/allb/texpng'), os.path.join(WB, 'tex'))
            for a in (['sh_bakeprep.py', '4', '0.75'], ['sh_bake.py', '4'], ['sh_fill.py', '4', 'pages']):
                rr = subprocess.run([sys.executable, os.path.join(HERE, a[0]), *a[1:]], cwd=WB, capture_output=True, text=True, env={**os.environ, 'REGEO': '1'})
                if rr.returncode: print(rr.stderr[-2000:], file=sys.stderr); raise SystemExit(a[0] + ' failed (lower layer)')
            for f in os.listdir(WB):
                if f not in ('sh_faces_4.pkl', 'pages', 'sh_shells_4.pkl'):
                    p_ = os.path.join(WB, f)
                    if os.path.islink(p_) or os.path.isfile(p_): os.remove(p_)
nf = sum(len(U['faces']) for U in R)
if nf == 0: log(empty=True, step='build'); sys.exit(0)
np.savez(os.path.join(W, 'sh_vis_4.npz'), front=np.ones(nf, np.int32))
for f in ('sh_bake.html', 'three.module.min.js'):
    if not os.path.exists(os.path.join(W, f)): shutil.copy(os.path.join(HERE, f), W)
if not os.path.exists(os.path.join(W, 'tex')): os.symlink(os.environ.get('TEXPNG', '/home/claude/allb/texpng'), os.path.join(W, 'tex'))
out = run(os.path.join(HERE, 'sh_bakeprep.py'), '4', '0.75', env={'REGEO': '1'}); log(step='bakeprep', out=json.loads(out))
run(os.path.join(HERE, 'sh_bake.py'), '4'); log(step='bake')
out = run(os.path.join(HERE, 'sh_fill.py'), '4', 'pages'); log(step='fill', out=out)
# keep what the collector needs, drop the rest
for f in os.listdir(W):
    if f not in ('sh_faces_4.pkl', 'pages', 'sh_shells_4.pkl'):
        p = os.path.join(W, f)
        if os.path.islink(p) or os.path.isfile(p): os.remove(p)
log(done=True)
