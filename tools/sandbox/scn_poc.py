# (proof of concept, branch poc-models) today's building blocks vs simplified 3D models at fixed cameras; cost while
# turning (Render's own Lua ms and textures shown, 20 redraws each)
async def run():
    import json, statistics
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    async def shot_canvas(path):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(SANDBOX.namespaces.GPS3D.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=path, clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
    places = {
        'sw': ((-8830, 640, 0, 'Stormwind City', 'Trade District'), {'high': (16400, -25880, 420, 25, 62), 'close': (16426, -25896, 200, 25, 45)}),
        'org': ((1630, -4380, 1, 'Orgrimmar', ''), {'high': (21446, -15437, 420, 200, 62), 'close': (21446, -15437, 200, 200, 45)}),
    }
    out = {}
    for pk, ((X, Y, m, z, sub), views) in places.items():
        await ev(f'Object.assign(__sandbox.player, {{ X: {X}, Y: {Y}, map: {m}, facing: 0, zone: {json.dumps(z)}, sub: {json.dumps(sub)} }})')
        await page.wait_for_timeout(1500)
        await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
        name = 'stormwind' if pk == 'sw' else 'orgrimmar'
        for vk, (x, y, dist, yaw, pitch) in views.items():
            for var in (('today', '3000roof', '8000roof', '20000roof', '8000') if vk == 'high' else ('today', '8000roof', '20000roof', 'tex')):
                if var == 'today':
                    await ev('__sandbox.slash("/gps3d poc off")'); await ev('__sandbox.slash("/gps3d detail on")')
                else:
                    await ev('__sandbox.slash("/gps3d detail off")')
                    if var == 'tex': await ev(f'__sandbox.slash("/gps3d poc {name} tex")')
                    else:
                        size = var.replace('roof', ''); mode = 'roof' if 'roof' in var else 'flat'
                        await ev(f'__sandbox.slash("/gps3d poc {name} {size} {mode}")')
                await run_lua(f'local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = {m}; c.x, c.y, c.dist, c.yaw, c.pitch = {x}, {y}, {dist}, {yaw}, {pitch}; c.th = SANDBOX_TH_{pk} or ns.GroundHeight({x}, {y}); SANDBOX_TH_{pk} = c.th; if ns.SnapLift then ns.SnapLift() end; ns.Redraw()')
                await page.wait_for_timeout(4500)
                await run_lua('SANDBOX.namespaces.GPS3D.Redraw()'); await page.wait_for_timeout(1500)
                await shot_canvas(f'shots/poc_{pk}_{vk}_{var}.png')
                cam = await lua('(function() local ns = SANDBOX.namespaces.GPS3D; local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis(); return string.format("%.1f,%.1f,%.1f", cx, cy, cz) end)()')
                ms, shown = [], []
                for k in range(20):
                    r = await lua(f'(function() local ns = SANDBOX.namespaces.GPS3D; ns.cam.yaw = ns.cam.yaw + 0.5; ns.Redraw(); return string.format("%f,%d,%d", ns.stats.ms, ns.stats.shown, (ns.stats.detailTris or 0)) end)()')
                    a, b_, c_ = r.split(','); ms.append(float(a)); shown.append(int(b_))
                await run_lua(f'local c = SANDBOX.namespaces.GPS3D.cam; c.yaw = {yaw}')
                out[f'{pk}_{vk}_{var}'] = {'ms': round(statistics.median(ms), 2), 'shown': int(statistics.median(shown)), 'cam': cam}
                print('POC', pk, vk, var, out[f'{pk}_{vk}_{var}'])
        await ev('__sandbox.slash("/gps3d poc off")'); await ev('__sandbox.slash("/gps3d detail on")')
    print('POCJSON', json.dumps(out))
