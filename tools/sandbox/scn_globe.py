# The planet view: screenshots from close up to the whole planet (shots/globe_<TAG>_<dist>.png), the view
# following you in Northshire. GLOBE_TAG names the run, GLOBE_DISTS the distances (comma-separated yards).
import os, json
TAG = os.environ.get('GLOBE_TAG', 'x')
DISTS = [int(d) for d in os.environ.get('GLOBE_DISTS', '8000,14000,18000,18500,22000,30000,45000,70000').split(',')]
async def run():
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G3 = 'SANDBOX.namespaces.GPS3D'
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    shots = []
    for d in DISTS:
        await run_lua(f'local ns = {G3}; ns.cam.dist = {d}; ns.Render()')
        await page.wait_for_timeout(int(os.environ.get('GLOBE_WAIT', '900')))
        x0, y0, w, h = await canvas_box()
        name = f'globe_{TAG}_{d}.png'
        await page.screenshot(path=f'shots/{name}', clip={'x': x0, 'y': y0, 'width': w, 'height': h})
        shots.append(name)
    print('shots:', shots)
