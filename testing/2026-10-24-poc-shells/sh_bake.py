# Runs sh_bake.html over the pages of sh_bake_<lod>.json; writes shb_<lod>_<page>.png (raw, alpha 0 where empty).
import asyncio, json, sys, threading, http.server, socketserver, functools, os, base64, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
L = sys.argv[1]
B = json.load(open(f'sh_bake_{L}.json'))
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8797), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def main():
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(); pg.set_default_timeout(3600000)
        pg.on('console', lambda m: print('console:', m.text) if m.type == 'error' else None)
        await pg.goto('http://127.0.0.1:8797/sh_bake.html'); await pg.wait_for_function('window.READY === true')
        t0 = time.time(); nu = await pg.evaluate(f'initBake({B["page"]})'); print('units loaded', nu, round(time.time() - t0, 1), 's', flush=True)
        for i, jobs in enumerate(B['pages']):
            url, missing = await pg.evaluate('(j) => bakePage(j)', jobs)
            open(f'shb_{L}_{i}.png', 'wb').write(base64.b64decode(url.split(',')[1]))
            print('page', i, len(jobs), 'pictures, missing units', missing, round(time.time() - t0, 1), 's', flush=True)
        await b.close()
asyncio.run(main())
