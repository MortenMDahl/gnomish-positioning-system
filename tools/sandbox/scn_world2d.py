# The 2D map zoomed out: both continents side by side, as on Blizzard's world map (shots/w2d_<name>.png).
import json
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    await page.wait_for_timeout(1500)
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    G = 'SANDBOX.namespaces.GnomishPositioningSystem'
    pre = f'local ns = {G}; local v = ns.view; v.follow = false; ns.db.follow = false; local L = ns.WorldLayout; '
    views = [
        ('both', 'ns.ShowMap(0, true); local kx, ky = ns.WorldGridOn(1, L[1].tx1 + 1, (L[1].ty0 + L[1].ty1) / 2, 0); v.cx, v.cy = (kx + L[0].tx0) / 2, ky - 1; v.scale = 7'),
        ('coast', 'ns.ShowMap(0, true); local kx, ky = ns.WorldGridOn(1, L[1].tx1 + 1, (L[1].ty0 + L[1].ty1) / 2, 0); v.cx, v.cy = (kx + L[0].tx0) / 2, ky; v.scale = 20'),
    ]
    for name, code in views:
        await run_lua(pre + code + '; ns.Layout()')
        await page.wait_for_timeout(1500)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + G + '.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(x) for x in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/w2d_{name}.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
    print('views', [v[0] for v in views])
