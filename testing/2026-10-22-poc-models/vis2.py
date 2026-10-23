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
        await pg.goto('http://127.0.0.1:8792/vis2.html'); await pg.wait_for_function('window.READY === true')
        for name in sys.argv[1:]:
            seen, back = await pg.evaluate(f'runVis("{name}", 3072)')
            np.array(seen, np.uint32).tofile(f'{name}_front.u32'); np.array(back, np.uint32).tofile(f'{name}_back.u32')
            f, b = np.array(seen), np.array(back)
            print(name, 'triangles', len(f), 'front seen', int((f >= 2).sum()), 'back seen', int((b >= 2).sum()), 'seen at all', int(((f + b) >= 2).sum()), 'back only', int(((b >= 2) & (f < 2)).sum()))
        await b.close()
asyncio.run(main())
