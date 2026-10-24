# Visibility of shell faces: ID renders of all shells of one level (plus the canals' water at 95 yd as an occluder)
# from straight above and 5 elevations x 24 directions (the 3D view looks down 20-90 degrees). Per face: pixels seen
# from the front, and pixels where a back face shows (a hole: the view sees into a shell).
# Usage: python3 sh_vis.py <lod> [size px]
import asyncio, json, sys, threading, http.server, socketserver, functools, os, pickle, numpy as np
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
L = sys.argv[1]; S = int(sys.argv[2]) if len(sys.argv) > 2 else 3072
ELEVS, AZ = [80, 65, 50, 35, 20], 24
R = pickle.load(open(f'sh_shells_{L}.pkl', 'rb'))
tris, fid = [], []
k = 0
for U in R:
    for f in U['faces']:
        c = f['c']; tris.append(c[[0, 1, 2]]); fid.append(k)
        if len(c) == 4: tris.append(c[[0, 2, 3]]); fid.append(k)
        k += 1
tris = np.array(tris); fid = np.array(fid)
gl = np.stack([tris[..., 0], tris[..., 2], -tris[..., 1]], -1).astype(np.float32)
tag = f'shvis{L}'; gl.reshape(-1).tofile(f'{tag}_tris.f32')
x0, y0 = (tris[..., 0].min() + tris[..., 0].max()) / 2, (tris[..., 1].min() + tris[..., 1].max()) / 2
Rr = max(np.ptp(tris[..., 0]), np.ptp(tris[..., 1])) / 2
w, e = 95.0, Rr + 1200
q = [(x0 - e, w, -(y0 - e)), (x0 + e, w, -(y0 - e)), (x0 - e, w, -(y0 + e)), (x0 + e, w, -(y0 - e)), (x0 + e, w, -(y0 + e)), (x0 - e, w, -(y0 + e))]
np.array(q, np.float32).reshape(-1).tofile(f'{tag}_ground.f32')
open(f'{tag}_box.txt', 'w').write(f'{x0} {-y0} {Rr} {tris[..., 2].min()} {tris[..., 2].max()} {len(tris)}')
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8796), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def main():
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(); pg.set_default_timeout(3600000)
        await pg.goto('http://127.0.0.1:8796/pb_vis.html'); await pg.wait_for_function('window.READY === true')
        await pg.evaluate(f'window.ELEVS = {json.dumps(ELEVS)}; window.AZSTEP = 360 / {AZ}')
        seen, back = await pg.evaluate(f'runVis("{tag}", {S})')
        await b.close(); return np.array(seen), np.array(back)
fs, bk = asyncio.run(main())
F = np.bincount(fid, weights=fs, minlength=k); B = np.bincount(fid, weights=bk, minlength=k)
np.savez_compressed(f'sh_vis_{L}.npz', front=F, back=B)
tot_front, tot_back = fs.sum(), bk.sum()
print(json.dumps({'lod': L, 'faces': int(k), 'seen>=1': int((F >= 1).sum()), 'seen>=4': int((F >= 4).sum()), 'never_seen': int((F == 0).sum()),
                  'back_pixels_share': round(float(tot_back / max(tot_front + tot_back, 1)), 5), 'faces_with_back_px': int((B >= 1).sum()), 'dirs': 1 + len(ELEVS) * AZ}))
