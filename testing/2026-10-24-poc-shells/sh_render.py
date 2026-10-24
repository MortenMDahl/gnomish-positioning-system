import asyncio, json, sys, threading, http.server, socketserver, functools, os
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
def serve():
    socketserver.TCPServer.allow_reuse_address = True
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(('127.0.0.1', 8794), functools.partial(Q, directory=HERE)) as h: h.serve_forever()
async def main():
    threading.Thread(target=serve, daemon=True).start()
    jobs = json.load(open(sys.argv[1]))
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        for j in jobs:
            w, h = j.get('w', 898), j.get('h', 648)
            pg = await b.new_page(viewport={'width': w, 'height': h})
            q = f"m={j['m']}&w={w}&h={h}&fov={j.get('fov', 50)}&cam=" + json.dumps(j['cam']) + ('&cull=1' if j.get('cull') else '') + ('&bf=1' if j.get('bf') else '')
            await pg.goto('http://127.0.0.1:8794/' + j.get('page', 'pb_view.html') + '?' + q)
            await pg.wait_for_function('window.DONE === true', timeout=600000); await pg.screenshot(path=j['out']); await pg.close(); print('ok', j['out'], flush=True)
        await b.close()
asyncio.run(main())
