# Top-down over Goldshire, with and without the game's props: do the stand-ins stand where the
# minimap image shows trees and rocks? Shots: shots/models_top_on.png, models_top_off.png.
async def run():
    import json
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    await page.fill('#cmdline', '/gps 3d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    G3 = 'SANDBOX.namespaces.GPS3D'
    await run_lua('GPS3D_DB.modelRange = 1500; GPS3D_DB.modelCount = 1500; ' + G3 + '.SetCamMode("free"); ' + G3 + '.SetTopDown(true, true); ' + G3 + '.cam.x, ' + G3 + '.cam.y = 32.25 * 1600 / 3, -49.6 * 1600 / 3; ' + G3 + '.cam.th = 60; ' + G3 + '.cam.dist = 700; ' + G3 + '.cam.yaw = 0; ' + G3 + '.ModelsChanged(); ' + G3 + '.Render()')
    await page.mouse.move(5, 5); await page.wait_for_timeout(3000)
    await shot('models_top_on.png')
    await run_lua('GPS3D_DB.props = false; ' + G3 + '.ModelsChanged()')
    await page.wait_for_timeout(1500)
    await shot('models_top_off.png')
