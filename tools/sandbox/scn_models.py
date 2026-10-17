# The game's own models in the page: the 3D view tilted over Goldshire (props and trees as green boxes
# of their real size and turn, buildings as tan boxes, the simplified building blocks giving way inside
# the model distance), then the game refusing buildings (WMOs): the simplified shapes come back.
# Shots: shots/models_*.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    await page.fill('#cmdline', '/gps 3d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    G3 = 'SANDBOX.namespaces.GPS3D'
    await run_lua(G3 + '.SetCamMode("free"); ' + G3 + '.SetTopDown(false, true); ' + G3 + '.cam.x, ' + G3 + '.cam.y = 32.3 * 1600 / 3, -49.55 * 1600 / 3; ' + G3 + '.cam.th = ' + G3 + '.GroundHeight(' + G3 + '.cam.x, ' + G3 + '.cam.y); ' + G3 + '.cam.dist = 260; ' + G3 + '.cam.pitch = 50; ' + G3 + '.cam.yaw = 20; ' + G3 + '.Render()')
    await page.mouse.move(5, 5); await page.wait_for_timeout(4000)
    print('state:', await lua(G3 + '.ModelsState()'))
    await shot('models_goldshire.png')
    await ev('[...document.querySelectorAll(".quick button")].find((b) => b.textContent === "game refuses WMOs").click()'); await page.wait_for_timeout(11000)
    print('state:', await lua(G3 + '.ModelsState()'))
    await shot('models_refused.png')
    await ev('[...document.querySelectorAll(".quick button")].find((b) => b.textContent === "props off").click()'); await page.wait_for_timeout(1500)
    print('state:', await lua(G3 + '.ModelsState()'))
    await shot('models_props_off.png')
