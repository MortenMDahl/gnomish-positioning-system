import asyncio, json, sys, threading, http.server, socketserver, functools, os, numpy as np
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8792), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def main():
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(); pg.set_default_timeout(1800000)
        pg.on('console', lambda m: print('console', m.text))
        await pg.goto('http://127.0.0.1:8792/vis.html'); await pg.wait_for_function('window.READY === true')
        for name in sys.argv[1:]:
            seen = await pg.evaluate(f'runVis("{name}", 3072)')
            np.array(seen, np.uint32).tofile(f'{name}_seen.u32')
            s = np.array(seen); print(name, 'triangles', len(s), 'seen', int((s > 0).sum()), 'seen by 2+ px', int((s >= 2).sum()))
        await b.close()
asyncio.run(main())
