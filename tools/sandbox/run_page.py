# Serves the sandbox site locally and drives it in headless Chromium (WebGL via SwiftShader).
# Usage: python3 run_page.py <scenario> [width height]
import asyncio, sys, os, threading, http.server, socketserver, functools, json, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
OUT = os.path.join(HERE, 'shots'); os.makedirs(OUT, exist_ok=True)
PORT = int(os.environ.get('SANDBOX_PORT', '8765'))  # another port when several sandboxes run at once

def wrap():
    body = open(os.path.join(SITE, 'index.html')).read()
    page = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')
    open(os.path.join(SITE, '_test.html'), 'w').write(page)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        if os.environ.get('CSP'):
            self.send_header('Content-Security-Policy', os.environ['CSP'])
        super().end_headers()
    def guess_type(self, path):
        if path.endswith('.wasm'): return 'application/wasm'
        return super().guess_type(path)

def serve():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', PORT), functools.partial(Quiet, directory=SITE)) as httpd:
        httpd.serve_forever()

async def main():
    wrap()
    threading.Thread(target=serve, daemon=True).start()
    scenario = sys.argv[1] if len(sys.argv) > 1 else 'basic'
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 1400
    H = int(sys.argv[3]) if len(sys.argv) > 3 else 900
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        ctx = await b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=float(os.environ.get('DSF', '1')), has_touch=(W < 700))
        page = await ctx.new_page()
        logs = []
        page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
        page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))
        async def route_cdn(route):
            url = route.request.url
            if 'wasmoon@1.16.0/dist/index.js' in url:
                await route.fulfill(path=os.path.join(SITE, 'wasmoon/index.js'), content_type='application/javascript')
            elif 'fengari-web@0.1.4' in url:
                await route.fulfill(path=os.path.join(SITE, 'wasmoon/fengari-web.js'), content_type='application/javascript')
            else:
                await route.abort()
        await page.route('https://cdn.jsdelivr.net/**', route_cdn)
        await page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
        await page.route('https://fonts.gstatic.com/**', lambda r: r.abort())
        if scenario == 'fengari':
            await page.add_init_script('Object.defineProperty(window, "WebAssembly", { value: undefined })')
        await page.goto(f'http://127.0.0.1:{PORT}/_test.html')
        if os.environ.get('CSP'):
            try:
                await page.wait_for_selector('#boot[hidden]', state='attached', timeout=20000)
            except Exception as e:
                await page.screenshot(path=os.path.join(OUT, 'csp_fail.png'))
                print('BOOT TIMEOUT; chat:', await page.locator('#log').inner_text()); print('boot:', await page.locator('#boot').inner_text())
                print('\n'.join(logs[-20:])); await b.close(); return
            await page.wait_for_timeout(1500)
            await page.fill('#cmdline', '/gps test'); await page.press('#cmdline', 'Enter')
            await page.wait_for_timeout(3000)
            await page.screenshot(path=os.path.join(OUT, 'csp.png'))
            print('--- chat (CSP) ---'); print(await page.locator('#log').inner_text())
            print('STATUS:', await page.locator('#status').inner_text())
            print('\n'.join(logs[-10:]))
            await b.close(); return
        await page.wait_for_function('window.__sandbox && window.__sandbox.lua() && document.getElementById("boot").hidden', timeout=60000)
        await page.wait_for_timeout(1500)
        async def shot(name):
            await page.screenshot(path=os.path.join(OUT, name))
        async def log_text():
            return await page.evaluate('document.getElementById("log").innerText')
        async def status():
            return await page.evaluate('document.getElementById("status").innerText')
        async def canvas_box():
            return await page.evaluate('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()')
        async def ev(js):
            return await page.evaluate(js)
        ns = {'page': page, 'shot': shot, 'log_text': log_text, 'status': status, 'canvas_box': canvas_box, 'ev': ev, 'logs': logs, 'asyncio': asyncio}
        exec(open(os.path.join(HERE, f'scn_{scenario}.py')).read() if os.path.exists(os.path.join(HERE, f'scn_{scenario}.py')) else 'async def run(): pass', ns)
        await ns['run']()
        print('STATUS:', await status())
        print('--- chat ---'); print(await log_text())
        print('--- console ---'); print('\n'.join(logs[-40:]))
        await b.close()

asyncio.run(main())
