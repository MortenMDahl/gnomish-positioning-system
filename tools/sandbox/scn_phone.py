async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    await shot('p1_phone_boot.png')
    cdp = await page.context.new_cdp_session(page)
    x0, y0, w, h = await canvas_box()
    cx, cy = x0 + w / 2, y0 + h / 2
    async def touch(kind, pts):
        await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(pts)]})
    # one-finger drag pans the 2D map
    before = await ev('(() => { const L = __sandbox.lua(); L.run("local v = SANDBOX.namespaces.GnomishPositioningSystem.view; SANDBOX_TMP = string.format(\'%.4f,%.4f,%.1f,%s\', v.cx, v.cy, v.scale, tostring(v.follow))"); return L.call("SANDBOX_GETTMP"); })()')
    await touch('touchStart', [(cx, cy)])
    for k in range(1, 11): await touch('touchMove', [(cx + k * 8, cy + k * 4)]); await page.wait_for_timeout(16)
    await touch('touchEnd', [])
    await page.wait_for_timeout(300)
    after = await ev('(() => { const L = __sandbox.lua(); L.run("local v = SANDBOX.namespaces.GnomishPositioningSystem.view; SANDBOX_TMP = string.format(\'%.4f,%.4f,%.1f,%s\', v.cx, v.cy, v.scale, tostring(v.follow))"); return L.call("SANDBOX_GETTMP"); })()')
    print('one-finger drag: view before', before, 'after', after)
    # pinch out (zoom in)
    await touch('touchStart', [(cx - 40, cy), (cx + 40, cy)])
    for k in range(1, 15): await touch('touchMove', [(cx - 40 - k * 8, cy), (cx + 40 + k * 8, cy)]); await page.wait_for_timeout(16)
    await touch('touchEnd', [])
    await page.wait_for_timeout(300)
    after2 = await ev('(() => { const L = __sandbox.lua(); L.run("local v = SANDBOX.namespaces.GnomishPositioningSystem.view; SANDBOX_TMP = string.format(\'%.4f,%.4f,%.1f,%s\', v.cx, v.cy, v.scale, tostring(v.follow))"); return L.call("SANDBOX_GETTMP"); })()')
    print('pinch out: view', after2)
    await shot('p2_phone_2d.png')
    # open 3D via the header button, then two-finger twist
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    yaw0 = await ev('(() => { const L = __sandbox.lua(); L.run("local c = SANDBOX.namespaces.GPS3D.cam; SANDBOX_TMP = string.format(\'%.2f,%.2f,%.1f\', c.yaw, c.pitch, c.dist)"); return L.call("SANDBOX_GETTMP"); })()')
    import math
    r = 60
    await touch('touchStart', [(cx - r, cy), (cx + r, cy)])
    for k in range(1, 13):
        a = k * math.radians(5)
        await touch('touchMove', [(cx - r * math.cos(a), cy - r * math.sin(a)), (cx + r * math.cos(a), cy + r * math.sin(a))]); await page.wait_for_timeout(40)
    for k in range(1, 8):
        a = math.radians(60)
        await touch('touchMove', [(cx - r * math.cos(a), cy - r * math.sin(a) - k * 6), (cx + r * math.cos(a), cy + r * math.sin(a) - k * 6)]); await page.wait_for_timeout(40)
    await touch('touchEnd', [])
    await page.wait_for_timeout(1500)
    yaw1 = await ev('(() => { const L = __sandbox.lua(); L.run("local c = SANDBOX.namespaces.GPS3D.cam; SANDBOX_TMP = string.format(\'%.2f,%.2f,%.1f,%s\', c.yaw, c.pitch, c.dist, SANDBOX.namespaces.GPS3D.CamMode())"); return L.call("SANDBOX_GETTMP"); })()')
    print('two-finger twist + slide: cam yaw,pitch,dist before', yaw0, 'after', yaw1)
    await shot('p3_phone_3d.png')
    await page.evaluate('document.querySelector(".side").scrollIntoView()')
    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    await page.wait_for_timeout(300)
    await shot('p4_phone_scrolled.png')
    sw = await ev('[document.documentElement.scrollWidth, window.innerWidth]')
    print('page width vs viewport', sw)
