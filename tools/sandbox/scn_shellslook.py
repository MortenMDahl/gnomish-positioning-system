# (proof of concept S1) the building shells from given views: VIEWJSON='{"name": [x, y, dist, yaw, pitch, th or null], ...}', TAG; shots/look_<name><TAG>.png
import os
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    views = json.loads(os.environ['VIEWJSON'])
    await ev('Object.assign(__sandbox.player, { X: -8830, Y: 640, map: 0, facing: 0, zone: "Stormwind City", sub: "Trade District" })')
    await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
    for cmd in os.environ.get('CMDS', '').split(';'):
        if cmd.strip(): await ev(f'__sandbox.slash({json.dumps(cmd.strip())})')
    for vk, (x, y, d, yaw, pitch, th) in views.items():
        thl = 'ns.GroundHeight(c.x, c.y, 0)' if th is None else str(th)
        await ev('__sandbox.lua().run(' + json.dumps(f'local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = {x}, {y}, {d}, {yaw}, {pitch}; c.th = {thl}; if ns.SnapLift then ns.SnapLift() end; ns.Redraw()') + ')')
        await page.wait_for_timeout(8000)
        await ev('__sandbox.lua().run("SANDBOX.namespaces.GPS3D.Redraw()")'); await page.wait_for_timeout(2000)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(SANDBOX.namespaces.GPS3D.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/look_{vk}{os.environ.get("TAG", "")}.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
        print('shot', vk, await lua('SANDBOX.namespaces.GPS3D.shells.Status()'), await lua('tostring(select(3, SANDBOX.namespaces.GPS3D.Budgets()))'), flush=True)
