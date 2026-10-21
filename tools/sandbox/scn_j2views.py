import os
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await page.select_option('#teleport', 'orgrimmar'); await page.click('#btn-go'); await page.wait_for_timeout(4500)
    for dist in (80, 150):
        await ev(f'__sandbox.lua().run("local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode(\'free\'); ns.SetTopDown(false, true); ns.cam.pitch, ns.cam.dist, ns.cam.yaw = 45, {dist}, 200; for i = 1, 40 do ns.Redraw() end")')
        await page.wait_for_timeout(2500)
        await shot(f'j2_{tag}_org{dist}.png')
