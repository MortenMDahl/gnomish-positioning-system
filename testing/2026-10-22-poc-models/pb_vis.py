# Finer visibility for a region: ID renders (front/back) from many directions at high resolution; the region's
# triangles plus 25 yd of context around it as occluders. Writes per-triangle pixel counts for the whole city array.
import asyncio, json, sys, threading, http.server, socketserver, functools, os, numpy as np
from playwright.async_api import async_playwright
from load import load
HERE = os.path.dirname(os.path.abspath(__file__))
x0, y0, R, S, tag = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
ELEVS, AZ = json.loads(sys.argv[6]) if len(sys.argv) > 6 else [80, 65, 50, 35, 20, 10], int(sys.argv[7]) if len(sys.argv) > 7 else 24
m = load('stormwind'); P = m['P']; T = m['T']; cen = P[T].mean(1)
ctx = np.nonzero((np.abs(cen[:, 0] - x0) < R + 25) & (np.abs(cen[:, 1] - y0) < R + 25))[0]
reg = (np.abs(cen[ctx, 0] - x0) < R) & (np.abs(cen[ctx, 1] - y0) < R)
gl = np.stack([P[:, 0], P[:, 2], -P[:, 1]], -1).astype(np.float32)
gl[T[ctx]].reshape(-1).tofile(f'{tag}_tris.f32')
WATER = os.environ.get('WATER')   # (the canals' water level: a plane hiding what lies under it, as the game's water does)
if WATER:
    w, e = float(WATER), R + 1200
    q = [(x0 - e, w, -(y0 - e)), (x0 + e, w, -(y0 - e)), (x0 - e, w, -(y0 + e)), (x0 + e, w, -(y0 - e)), (x0 + e, w, -(y0 + e)), (x0 - e, w, -(y0 + e))]
    np.array(q, np.float32).reshape(-1).tofile(f'{tag}_ground.f32')
else: np.zeros(0, np.float32).tofile(f'{tag}_ground.f32')
hh = P[T[ctx]][..., 2]
open(f'{tag}_box.txt', 'w').write(f'{x0} {-y0} {R + 25} {hh.min()} {hh.max()} {len(ctx)}')
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8795), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def main():
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(); pg.set_default_timeout(3600000)
        await pg.goto('http://127.0.0.1:8795/pb_vis.html'); await pg.wait_for_function('window.READY === true')
        await pg.evaluate(f'window.ELEVS = {json.dumps(ELEVS)}; window.AZSTEP = 360 / {AZ}')
        seen, back = await pg.evaluate(f'runVis("{tag}", {S})')
        await b.close()
        return np.array(seen), np.array(back)
f, bk = asyncio.run(main())
F = np.zeros(len(T), np.uint32); B = np.zeros(len(T), np.uint32); F[ctx] = f; B[ctx] = bk
inreg = np.zeros(len(T), bool); inreg[ctx[reg]] = True
np.savez_compressed(f'{tag}_vis.npz', front=F, back=B, region=inreg)
print(json.dumps({'region_tris': int(inreg.sum()), 'seen>=1': int(((F + B)[inreg] >= 1).sum()), 'front>=1': int((F[inreg] >= 1).sum()), 'back_only': int(((B[inreg] >= 1) & (F[inreg] == 0)).sum()), 'dirs': 1 + len(ELEVS) * AZ}))
