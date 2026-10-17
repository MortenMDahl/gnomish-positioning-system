# The sea past a map's last tiles: the 2D map and the 3D view zoomed far out over the Eastern
# Kingdoms' west coast, where the minimap's open sea (#081110) meets the background. Before
# 2026-10-17 the background was lighter blue (2D) or a sky gradient (3D). Shots: shots/sea_*.png.
async def run():
    import json
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G1, G3 = 'SANDBOX.namespaces.GnomishPositioningSystem', 'SANDBOX.namespaces.GPS3D'
    await run_lua(G1 + '.view.follow = false; ' + G1 + '.view.map = 0; ' + G1 + '.view.cx, ' + G1 + '.view.cy = 22, 42; ' + G1 + '.view.scale = 14; ' + G1 + '.ShowMap(0, true)')
    await page.mouse.move(5, 5); await page.wait_for_timeout(2500)
    await shot('sea_2d.png')
    await run_lua('GPS3D_API.Show(GPS_MapFrame, { map = 0, gx = 24, gy = 42 }); GPS_MapFrame:Hide()')
    await page.wait_for_timeout(1500)
    await run_lua(G3 + '.cam.dist = 9000; ' + G3 + '.Render()'); await page.wait_for_timeout(3000)
    await shot('sea_3d_down.png')
    await run_lua(G3 + '.SetTopDown(false, true); ' + G3 + '.cam.pitch = 45; ' + G3 + '.cam.yaw = 270; ' + G3 + '.Render()'); await page.wait_for_timeout(3000)
    await shot('sea_3d_tilted.png')
