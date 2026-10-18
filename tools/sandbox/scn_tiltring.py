# Close-ups of the straight-down / tilted ring (its little ground grid) at a few tilts and turns:
# shots/tiltring_<tag>_p<pitch>_y<yaw>.png (TILT_TAG names the run).
import os, json
TAG = os.environ.get('TILT_TAG', 'x')
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G3 = 'SANDBOX.namespaces.GPS3D'
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    shots = []
    for pitch, yaw in ((89.9, 0), (89.9, 30), (60, 20), (45, 0), (45, 45)):
        await run_lua(f'local ns = {G3}; ns.SetTopDown({str(pitch > 89).lower()}, true); ns.cam.pitch = {pitch}; ns.cam.yaw = {yaw}; ns.Render(); ns.UpdateGrid()')
        await page.wait_for_timeout(400)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + G3 + '.topButton); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        name = f'tiltring_{TAG}_p{int(pitch)}_y{yaw}.png'
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + l * s - 6, 'y': y0 + h - t * s - 6, 'width': (rr - l) * s + 12, 'height': (t - b) * s + 12})
        shots.append(name)
    print('shots:', shots)
