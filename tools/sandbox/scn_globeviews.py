# The planet from several places: shots/gv_<name>.png (the 3D window only).
import os, json
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G3 = 'SANDBOX.namespaces.GPS3D'
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    if os.environ.get('GV_W'):  # the window's size (default as the page opens it)
        await run_lua(f'GPS3D_Frame:SetSize({os.environ["GV_W"]}, {os.environ["GV_H"]})'); await page.wait_for_timeout(500)
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    pre = f'local ns = {G3}; ns.SetCamMode("free"); local L = ns.GlobeLayout; local X0, Y0, MX, MY = ns.GlobeCentres(); '
    views = [
        ('maelstrom', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX, MY); ns.cam.dist = 65000; ns.cam.yaw = 0'),
        ('kalimdor', 'local e = L[1]; ns.cam.map = 1; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(1, (e.x0 + e.x1) / 2, (e.y0 + e.y1) / 2); ns.cam.dist = 50000; ns.cam.yaw = 0'),
        ('turned', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX, MY); ns.cam.dist = 65000; ns.cam.yaw = 40'),
        ('bending', 'local e = L[0]; ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, e.x0 + 2000, (e.y0 + e.y1) / 2); ns.cam.dist = 30000; ns.cam.yaw = 0'),
        ('far', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX, MY); ns.cam.dist = 110000; ns.cam.yaw = 0'),
        ('backside', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX + 60000, MY); ns.cam.dist = 65000; ns.cam.yaw = 0'),
        # like Morten's of 2026-10-21: the whole planet from far out, the Maelstrom in the middle, the continents
        # toward the edges (clouds next to and over them, clouds near the edge)
        ('reported', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX, MY); ns.cam.dist = 62000; ns.cam.yaw = 0'),
        ('edge', 'ns.cam.map = 0; ns.cam.x, ns.cam.y = ns.GlobeFromPlane(0, MX - 16000, MY - 4000); ns.cam.dist = 62000; ns.cam.yaw = 0'),
    ]
    if os.environ.get('GV_VIEWS'): views = [v for v in views if v[0] in os.environ['GV_VIEWS'].split(',')]  # (only these)
    for name, code in views:
        await run_lua(pre + code + '; ns.Render()')
        await page.wait_for_timeout(1200)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + G3 + '.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/gv_{os.environ.get("GV_TAG", "")}{name}.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
    print('views', [v[0] for v in views])
