# The map-key globe and full screen (J6): the top right of the 2D and 3D windows (globe, full screen,
# close), the globe's tooltip, and each window at full screen and back. Shots in shots/mapkey_*.png.
# Usage: DSF=2 python3 run_page.py mapkey 1400 900
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    import json
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    async def box(obj):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + obj + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        return [float(v) for v in r.split(',')]
    async def centre(obj):
        l, b, rr, t = await box(obj)
        x0, y0, w, h = await canvas_box()
        return x0 + (l + rr) / 2 * s, y0 + h - (b + t) / 2 * s
    async def click(obj):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.up(); await page.wait_for_timeout(400)
    async def hover(obj):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.wait_for_timeout(300)
    async def corner_shot(name, frame, width=330, height=150):
        l, b, rr, t = await box(frame)
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + (rr - width) * s, 'y': y0 + h - t * s, 'width': width * s, 'height': height * s})
    async def window_shot(name, frame):
        l, b, rr, t = await box(frame)
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + l * s, 'y': y0 + h - t * s, 'width': (rr - l) * s, 'height': (t - b) * s})
    G2, G3 = 'SANDBOX.namespaces.GnomishPositioningSystem', 'SANDBOX.namespaces.GPS3D'
    await run_lua('GnomishPositioningSystemDB.fullScreen = false; if not GPS_MapFrame:IsShown() then GPS_Toggle() end'); await page.wait_for_timeout(1500)
    await corner_shot('mapkey_2d_topright.png', 'GPS_MapFrame')
    await hover(G2 + '.ui.globe'); await page.wait_for_timeout(200)
    await corner_shot('mapkey_2d_globe_tip.png', 'GPS_MapFrame', 520, 170)
    print('2D globe tooltip:', await lua('GameTooltip:IsShown() and GameTooltip:IsOwned(' + G2 + '.ui.globe)'))
    await hover(G2 + '.ui.fullScreen'); await page.wait_for_timeout(200)
    await corner_shot('mapkey_2d_full_tip.png', 'GPS_MapFrame', 520, 170)
    before = await box('GPS_MapFrame')
    await click(G2 + '.ui.fullScreen'); await page.wait_for_timeout(1500)
    await page.mouse.move(5, 5)
    print('2D full screen rect:', await box('GPS_MapFrame'), 'screen', await box('UIParent'))
    await window_shot('mapkey_2d_full.png', 'GPS_MapFrame')
    await corner_shot('mapkey_2d_full_topright.png', 'GPS_MapFrame')
    await click(G2 + '.ui.modeSwitch'); await page.wait_for_timeout(2500)
    await page.mouse.move(5, 5)
    print('3D (switched in full screen) rect:', await box('GPS3D_Frame'))
    await window_shot('mapkey_3d_full.png', 'GPS3D_Frame')
    await click(G3 + '.ui.fullScreen'); await page.wait_for_timeout(1500)
    await page.mouse.move(5, 5)
    print('3D back to', await box('GPS3D_Frame'), 'before full screen', before)
    await corner_shot('mapkey_3d_topright.png', 'GPS3D_Frame')
    await window_shot('mapkey_3d_window.png', 'GPS3D_Frame')
    await ev('__sandbox.slash("/gps mapkey gps")'); await page.wait_for_timeout(500)
    await corner_shot('mapkey_3d_topright_gps.png', 'GPS3D_Frame')
    print('globe gold (map key on GPS):', await lua(G3 + '.ui.globe.active'))
    await ev('__sandbox.slash("/gps mapkey blizzard")')
