# Stormwind in the page as it now opens (the sandbox answering the building check as a game that
# refuses WMOs): simplified buildings plus the game's props. Shot: shots/models_stormwind.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    await page.fill('#cmdline', '/gps 3d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    G3 = 'SANDBOX.namespaces.GPS3D'
    await run_lua(G3 + '.SetCamMode("free"); ' + G3 + '.SetTopDown(false, true); ' + G3 + '.cam.x, ' + G3 + '.cam.y = 30.75 * 1600 / 3, -48.45 * 1600 / 3; ' + G3 + '.cam.th = ' + G3 + '.GroundHeight(' + G3 + '.cam.x, ' + G3 + '.cam.y); ' + G3 + '.cam.dist = 450; ' + G3 + '.cam.pitch = 50; ' + G3 + '.cam.yaw = 30; ' + G3 + '.Render()')
    await page.mouse.move(5, 5); await page.wait_for_timeout(12000)
    print('state:', await lua(G3 + '.ModelsState()'))
    await shot('models_stormwind.png')
