# The window look (option B, "minimap rings"): 2D and 3D, the rings, tooltips, the camera ring's
# cycle, the compass needle at a few headings, and the smallest window. Close-ups go to shots/look_*.png.
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    import json
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    async def centre(obj):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + obj + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        return x0 + (l + rr) / 2 * s, y0 + h - (b + t) / 2 * s
    async def click(obj):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.up(); await page.wait_for_timeout(300)
    async def hover(obj):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.wait_for_timeout(250)
    async def window_shot(name, frame):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + frame + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + l * s - 20, 'y': y0 + h - t * s - 4, 'width': (rr - l) * s + 24, 'height': (t - b) * s + 8})
    G2, G3 = 'SANDBOX.namespaces.GnomishPositioningSystem', 'SANDBOX.namespaces.GPS3D'
    await run_lua('if not GPS_MapFrame:IsShown() then GPS_Toggle() end'); await page.wait_for_timeout(1500)
    await hover(G2 + '.ui.modeSwitch'); await window_shot('look_2d_hover_mode.png', 'GPS_MapFrame')
    print('2D rings:', await lua('#' + G2 + '.ui.rings'), 'tooltip:', await lua('GameTooltip:IsShown() and GameTooltip:GetOwner() == ' + G2 + '.ui.modeSwitch'))
    await click(G2 + '.ui.modeSwitch'); await page.wait_for_timeout(2000)
    print('3D shown:', await lua('GPS3D_Frame:IsShown()'), 'mode', await lua(G3 + '.CamMode()'))
    for yaw in (0, 45, 135):
        await run_lua(G3 + '.cam.yaw = ' + str(yaw) + '; ' + G3 + '.Render()'); await page.wait_for_timeout(300)
        await window_shot(f'look_3d_yaw{yaw}.png', 'GPS3D_Frame')
        print('needle rotation at yaw', yaw, '=', await lua('string.format("%.4f", ' + G3 + '.compass.icon:GetRotation())'))
    modes = []
    for k in range(3):
        await click(G3 + '.camButton'); await page.wait_for_timeout(700)
        modes.append(await lua(G3 + '.CamMode()') + ':' + await lua(G3 + '.ui.footer:GetText()'))
    print('camera ring cycle:', ' | '.join(modes))
    await hover(G3 + '.camButton'); await window_shot('look_3d_hover_camera.png', 'GPS3D_Frame')
    await run_lua(G3 + '.SetCamMode("free")')
    await click(G3 + '.ui.me'); await page.wait_for_timeout(800)
    print('Me from free ->', await lua(G3 + '.CamMode()'))
    # smallest window
    await run_lua('GPS3D_Frame:SetSize(400, 300)'); await page.wait_for_timeout(600)
    await window_shot('look_3d_small.png', 'GPS3D_Frame')
    r = await lua('(function() local _, b = SANDBOX.rect(' + G3 + '.ui.me); local _, _, _, t = SANDBOX.rect(' + G3 + '.ui.zoomIn); return string.format("%.1f", b - t) end)()')
    print('smallest window: gap between the last ring and the zoom buttons:', r, 'px')
    # the self-tests' look lines (the art and icons report loaded)
    await ev('__sandbox.slash("/gps test")'); await page.wait_for_timeout(3500)
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(12000)
