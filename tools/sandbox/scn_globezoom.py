# Zooms out from 12,000 to 80,000 yards in steps of 4 % and saves the 3D view's ground (the window's canvas
# inside the title band and the rings) at each step: shots/gz_<TAG>_<i>.png and gz_<TAG>.json (distances,
# the planet view's state). GZ_W, GZ_H: the window's size (default 900 x 650); GZ_TILT: a tilt to start from.
import os, json
TAG = os.environ.get('GZ_TAG', 'x')
W, H = int(os.environ.get('GZ_W', '900')), int(os.environ.get('GZ_H', '650'))
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G3 = 'SANDBOX.namespaces.GPS3D'
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await run_lua(f'GPS3D_Frame:SetSize({W}, {H}); {G3}.Render()')
    if os.environ.get('GZ_TILT'):  # tilted as you set it: the view straightens between 14,000 and 18,000 yd
        await run_lua(f'{G3}.SetTopDown(false, true); {G3}.cam.pitch = {float(os.environ["GZ_TILT"])}; {G3}.Render()')
    await page.wait_for_timeout(800)
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    d, i, out = 12000.0, 0, []
    # warm up: visit every distance once so images are loaded before the measured pass
    for warm in (12000, 18000, 25000, 40000, 80000):
        await run_lua(f'{G3}.cam.dist = {warm}; {G3}.Render()'); await page.wait_for_timeout(900)
    while d <= 80000:
        await run_lua(f'{G3}.cam.dist = {d}; {G3}.Render()')
        await page.wait_for_timeout(450)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + G3 + '.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        # inside the title band (64 px) and footer (30 px), left of the rings (50 px)
        clip = {'x': x0 + (l + 4) * s, 'y': y0 + h - (t - 64) * s, 'width': (rr - l - 54) * s, 'height': (t - b - 94) * s}
        await page.screenshot(path=f'shots/gz_{TAG}_{i:03d}.png', clip=clip)
        st = await lua(f'(function() local st = {G3}.GlobeFrameState.stats; return string.format("%s,%s,%s,%s,%s", tostring({G3}.GlobeOn()), tostring(st.t), tostring(st.pages), tostring(st.k), tostring(st.n)) end)()')
        out.append({'i': i, 'dist': d, 'state': st})
        i += 1
        d *= 1.04
    json.dump({'scale': s, 'steps': out}, open(f'shots/gz_{TAG}.json', 'w'))
    print('steps', i)
