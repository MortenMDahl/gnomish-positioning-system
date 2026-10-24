# (proof of concept S1) the building shells in the page: Stormwind's Trade District at 90 / 200 / 420 / 2,000 yd,
# shells against the old blocks (VARS=shells,blocks); shots/shells_<view>_<var>.png
import os
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    views = {'near': (16380, -25920, 90, 25, 40, 117.5), 'close': (16426, -25896, 200, 25, 45, 117.5), 'high': (16400, -25880, 420, 25, 62, 117.5), 'far': (16426, -25896, 2000, 25, 50, 117.5)}
    views = {k: v for k, v in views.items() if k in os.environ.get('VIEWS', ','.join(views)).split(',')}
    await ev('Object.assign(__sandbox.player, { X: -8830, Y: 640, map: 0, facing: 0, zone: "Stormwind City", sub: "Trade District" })')
    await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
    for vk, (x, y, d, yaw, pitch, th) in views.items():
        for var in os.environ.get('VARS', 'shells,blocks').split(','):
            if var.startswith('shells'):
                await ev('__sandbox.slash("/gps3d detail off")'); await ev('__sandbox.slash("/gps3d shells on")')
                px = {'shells': '14 7 4.5 1.2', 'shellsfine': '6 4 3 1.2'}[var]
                await ev(f'__sandbox.slash("/gps3d shells px {px}")')
            else: await ev('__sandbox.slash("/gps3d shells off")'); await ev('__sandbox.slash("/gps3d detail on")')
            await ev('__sandbox.lua().run(' + json.dumps(f'local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = {x}, {y}, {d}, {yaw}, {pitch}; c.th = {th}; if ns.SnapLift then ns.SnapLift() end; ns.Redraw()') + ')')
            await page.wait_for_timeout(9000)
            await ev('__sandbox.lua().run("SANDBOX.namespaces.GPS3D.Redraw()")'); await page.wait_for_timeout(2500)
            r = await lua('(function() local l,b,r,t = SANDBOX.rect(SANDBOX.namespaces.GPS3D.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
            l, b, rr, t = [float(v) for v in r.split(',')]
            x0, y0, w, h = await canvas_box()
            await page.screenshot(path=f'shots/shells_{vk}_{var}.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
            print('shot', vk, var, await lua('SANDBOX.namespaces.GPS3D.shells.Status()'), flush=True)
