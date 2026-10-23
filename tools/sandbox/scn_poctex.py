async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    places = {'sw': ((-8830, 640, 0, 'Stormwind City', 'Trade District'), 'stormwind', {'close': (16426, -25896, 200, 25, 45, 117.5), 'high': (16400, -25880, 420, 25, 62, 117.5)}),
              'org': ((1630, -4380, 1, 'Orgrimmar', ''), 'orgrimmar', {'close': (21446, -15437, 200, 200, 45, None), 'high': (21446, -15437, 420, 200, 62, None)})}
    for pk, ((X, Y, m, z, sub), name, views) in places.items():
        await ev(f'Object.assign(__sandbox.player, {{ X: {X}, Y: {Y}, map: {m}, facing: 0, zone: {json.dumps(z)}, sub: {json.dumps(sub)} }})')
        await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
        await ev('__sandbox.slash("/gps3d detail off")')
        for vk, (x, y, d, yaw, pitch, th) in views.items():
            for var in ('tex3000', 'tex8000'):
                await ev(f'__sandbox.slash("/gps3d poc {name} {var}")')
                ths = str(th) if th else 'SANDBOX_THO or ns.GroundHeight(%d, %d)' % (x, y)
                await ev('__sandbox.lua().run(' + json.dumps(f'local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = {m}; c.x, c.y, c.dist, c.yaw, c.pitch = {x}, {y}, {d}, {yaw}, {pitch}; c.th = {ths}; SANDBOX_THO = c.th; if ns.SnapLift then ns.SnapLift() end; ns.Redraw()') + ')')
                await page.wait_for_timeout(5000)
                r = await lua('(function() local l,b,r,t = SANDBOX.rect(SANDBOX.namespaces.GPS3D.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
                l, b, rr, t = [float(v) for v in r.split(',')]
                x0, y0, w, h = await canvas_box()
                await page.screenshot(path=f'shots/poc_{pk}_{vk}_{var}.png', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
                print('cam', pk, vk, var, await lua('(function() local ns = SANDBOX.namespaces.GPS3D; local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis(); return string.format("%.1f,%.1f,%.1f", cx, cy, cz) end)()'))
