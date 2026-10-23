async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    await ev('Object.assign(__sandbox.player, { X: -8830, Y: 640, map: 0, facing: 0, zone: "Stormwind City", sub: "Trade District" })')
    await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
    await ev('__sandbox.slash("/gps3d detail off")'); await ev('__sandbox.slash("/gps3d poc stormwind diag")')
    await ev('__sandbox.lua().run("local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode(\'free\'); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; c.th = 117.5; if ns.SnapLift then ns.SnapLift() end; ns.Redraw()")')
    await page.wait_for_timeout(5000)
    r = await lua('(function() local l,b,r,t = SANDBOX.rect(SANDBOX.namespaces.GPS3D.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
    l, b, rr, t = [float(v) for v in r.split(',')]
    x0, y0, w, h = await canvas_box()
    await page.screenshot(path='shots/pocdiag_addon.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
    print('cam', await lua('(function() local ns = SANDBOX.namespaces.GPS3D; local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis(); local w,h = ns.canvas:GetSize(); return string.format("%.1f,%.1f,%.1f f %.1f %dx%d", cx, cy, cz, ns.Focal(), w, h) end)()'))
