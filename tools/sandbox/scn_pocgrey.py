async def run():
    import json
    await ev('Object.assign(__sandbox.player, { X: -8830, Y: 640, map: 0, facing: 0, zone: "Stormwind City", sub: "Trade District" })')
    await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
    await ev('__sandbox.slash("/gps3d detail off")')
    for mode in ('grey', 'tex'):
        await ev(f'__sandbox.slash("/gps3d poc stormwind {mode}")')
        await ev('__sandbox.lua().run("local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode(\'free\'); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; c.th = ns.GroundHeight(16426, -25896); ns.Redraw()")')
        await page.wait_for_timeout(5000)
        await shot(f'pocdbg_{mode}.png')
