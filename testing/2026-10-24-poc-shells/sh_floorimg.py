# The city's floor picture (2026-10-24): what the ground under and round the shells shows instead of the minimap image,
# whose top-down picture of the buildings showed a second time beside and under their 3D shells (a bridge's ghost on
# the water under it). One 2048 x 2048 page over the city's box, top-down: the street geometry (the street pseudo-units
# of the bake, sh_bake.html) where there is any; under a building's footprint without street, the nearest street's
# colour; elsewhere (water, terrain) the minimap. Usage: python3 sh_floorimg.py <minimap dir> <out.jpg> [<out.json>]
import sys, os, json, base64, asyncio, threading, http.server, socketserver, functools, pickle, numpy as np
from PIL import Image
from scipy import ndimage
from matplotlib.path import Path
from playwright.async_api import async_playwright
MM, OUTJ = sys.argv[1], sys.argv[2]; OUTM = sys.argv[3] if len(sys.argv) > 3 else 'sh_floorimg.json'
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE, TILE = 2048, 1600 / 3
GEO = json.load(open('sh_geo.json'))
boxes = {int(k): v for k, v in GEO['boxes'].items()}
streets = [k for k in boxes if k <= -1000]
S = pickle.load(open('sh_faces_e_1.pkl', 'rb'))
P = np.vstack([f['c'] for f in S['faces']])
x0, x1, y0, y1 = float(np.floor(P[:, 0].min())), float(np.ceil(P[:, 0].max())), float(np.floor(P[:, 1].min())), float(np.ceil(P[:, 1].max()))
side = max(x1 - x0, y1 - y0); x1, y1 = x0 + side, y0 + side   # (a square: one scale for both axes)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
def gl(v): return [float(v[0]), float(v[2]), float(-v[1])]
job = dict(units=streets, x=0, y=0, w=PAGE, h=PAGE, o=gl([cx, cy, 100.0]), u=gl([1, 0, 0]), v=gl([0, 1, 0]), n=gl([0, 0, 1]),
           u0=-side / 2, u1=side / 2, v0=-side / 2, v1=side / 2, front=400.0, back=400.0)
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8798), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def bake():
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(); pg.set_default_timeout(3600000)
        await pg.goto('http://127.0.0.1:8798/sh_bake.html'); await pg.wait_for_function('window.READY === true')
        await pg.evaluate(f'initBake({PAGE})')
        url, missing = await pg.evaluate('(j) => bakePage(j)', [job])
        await b.close()
        return np.asarray(Image.open(__import__('io').BytesIO(base64.b64decode(url.split(',')[1]))).convert('RGBA')).astype(float)
BAKE = os.environ.get('BAKE', 'floor_bake.npy')
if os.path.exists(BAKE): img = np.load(BAKE)
else: img = asyncio.run(bake()); np.save(BAKE, img)
# world position of every pixel (row 0 north)
res = side / PAGE
xs = x0 + (np.arange(PAGE) + 0.5) * res; ys = y1 - (np.arange(PAGE) + 0.5) * res
X, Y = np.meshgrid(xs, ys)
# the minimap at each pixel
mm = np.zeros((PAGE, PAGE, 3))
gx, gy = X / TILE, -Y / TILE
tx, ty = np.floor(gx).astype(int), np.floor(gy).astype(int)
for (a, b) in set(zip(tx.ravel().tolist(), ty.ravel().tolist())):
    f = os.path.join(MM, f'0_{a}_{b}.jpg')
    if not os.path.exists(f): continue
    t = np.asarray(Image.open(f).convert('RGB')).astype(float); n = t.shape[0]
    m = (tx == a) & (ty == b)
    i = np.clip(((gy[m] - b) * n).astype(int), 0, n - 1); j = np.clip(((gx[m] - a) * n).astype(int), 0, n - 1)
    mm[m] = t[i, j]
# buildings' footprints: the tops of building units (level 1)
foot = np.zeros((PAGE, PAGE), bool)
for f in S['faces']:
    if f['kind'] != 'roof' or f['unit'] < 0: continue
    c = f['c'][:, :2]
    a_, b_ = c.min(0), c.max(0)
    j0, j1 = max(0, int((a_[0] - x0) / res)), min(PAGE, int((b_[0] - x0) / res) + 1); i0, i1 = max(0, int((y1 - b_[1]) / res)), min(PAGE, int((y1 - a_[1]) / res) + 1)
    if j0 >= j1 or i0 >= i1: continue
    sub = (slice(i0, i1), slice(j0, j1))
    foot[sub] |= Path(np.vstack([c, c[:1]])).contains_points(np.stack([X[sub].ravel(), Y[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
street = img[..., 3] >= 250
# the streets' top height at each pixel (their horizontal faces, a plane through each face's corners) against the
# ground grid's (raised floor, sh_grounddump.py): a street more than LIFT yd above the ground is a bridge, a stair or
# a wall-walk over water or a lower street, and its picture must not lie on the ground under it (its ghost)
LIFT = 2.5
top = np.full((PAGE, PAGE), -np.inf)
for f in S['faces']:
    if f['unit'] >= 0 or f['kind'] != 'roof': continue
    c = f['c']; a_, b_ = c[:, :2].min(0), c[:, :2].max(0)
    j0, j1 = max(0, int((a_[0] - x0) / res)), min(PAGE, int((b_[0] - x0) / res) + 1); i0, i1 = max(0, int((y1 - b_[1]) / res)), min(PAGE, int((y1 - a_[1]) / res) + 1)
    if j0 >= j1 or i0 >= i1: continue
    sub = (slice(i0, i1), slice(j0, j1))
    ins = Path(np.vstack([c[:, :2], c[:1, :2]])).contains_points(np.stack([X[sub].ravel(), Y[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
    if not ins.any(): continue
    A = np.c_[c[:, 0], c[:, 1], np.ones(len(c))]; k = np.linalg.lstsq(A, c[:, 2], rcond=None)[0]
    z = k[0] * X[sub] + k[1] * Y[sub] + k[2]
    top[sub] = np.where(ins, np.maximum(top[sub], z), top[sub])
H = np.load(os.environ.get('GROUND', 'floor_ground.npy')); n = H.shape[0] - 1
gi, gj = np.clip((y1 - Y) / side * n, 0, n), np.clip((X - x0) / side * n, 0, n)
ground = ndimage.map_coordinates(H, [gi, gj], order=1)
lifted = street & (top - ground > LIFT)
low = street & ~lifted
# what may be shown on the ground: low streets, and the minimap away from buildings and lifted streets (it has them
# drawn from above too); everything else takes the nearest such pixel's colour
r2 = int(np.ceil(2 / res))
covered = ndimage.binary_dilation(foot | lifted, iterations=r2)
good = low | (~street & ~covered)
out = mm.copy()
out[low] = img[..., :3][low]
_, (ii, jj) = ndimage.distance_transform_edt(~good, return_indices=True)
bad = ~good
out[bad] = out[ii[bad], jj[bad]]
under = foot & ~street
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUTJ, quality=88)
json.dump({'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1}, open(OUTM, 'w'))
print(json.dumps({'box': [x0, x1, y0, y1], 'px_per_yd': round(PAGE / side, 2), 'street_share': round(float(street.mean()), 3), 'under_buildings_filled': round(float(under.mean()), 3), 'lifted_streets': round(float(lifted.mean()), 3), 'refilled': round(float(bad.mean()), 3),
                  'minimap_share': round(float((~street & ~foot).mean()), 3), 'bytes': os.path.getsize(OUTJ)}))
