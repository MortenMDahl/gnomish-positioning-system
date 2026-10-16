async def run():
    x0, y0, w, h = await canvas_box()
    cx, cy = x0 + w / 2, y0 + h / 2
    # zoom out with the wheel over the map
    await page.mouse.move(cx, cy)
    for _ in range(6):
        await page.mouse.wheel(0, 120); await page.wait_for_timeout(60)
    await page.wait_for_timeout(800)
    await shot('02_2d_zoomed_out.png')
    # drag (pan)
    await page.mouse.move(cx, cy); await page.mouse.down(); 
    for k in range(10): await page.mouse.move(cx + k * 15, cy + k * 8); await page.wait_for_timeout(20)
    await page.mouse.up(); await page.wait_for_timeout(400)
    await shot('03_2d_panned.png')
    # Me button: find it via the engine
    me = await ev('''(() => { const L = __sandbox.lua(); L.run("local u = SANDBOX.namespaces.GnomishPositioningSystem.ui; local l,b,r,t = SANDBOX.rect(u.me); SANDBOX_TMP = string.format('%f,%f', (l+r)/2, (b+t)/2)"); L.run("function SANDBOX_GETTMP() return SANDBOX_TMP end"); return L.call("SANDBOX_GETTMP"); })()''')
    mx, my = [float(v) for v in me.split(',')]
    scale = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return r.width; })()')
    print('Me at UI', mx, my)
    async def click_ui(ux, uy, button='left'):
        sc = await ev('''(() => { const L = __sandbox.lua(); return 1; })()''')
        x0, y0, w, h = await canvas_box()
        s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
        px, py = x0 + ux * s, y0 + h - uy * s
        await page.mouse.move(px, py); await page.mouse.down(button=button); await page.mouse.up(button=button)
    await click_ui(mx, my); await page.wait_for_timeout(600)
    await shot('04_2d_me.png')
    # switch to 3D with the 2D/3D ring
    p3 = await ev('''(() => { const L = __sandbox.lua(); L.run("local u = SANDBOX.namespaces.GnomishPositioningSystem.ui; local l,b,r,t = SANDBOX.rect(u.modeSwitch); SANDBOX_TMP = string.format('%f,%f', (l+r)/2, (b+t)/2)"); return L.call("SANDBOX_GETTMP"); })()''')
    ux, uy = [float(v) for v in p3.split(',')]
    await click_ui(ux, uy); await page.wait_for_timeout(2500)
    await shot('05_3d_follow.png')
    print('after 3D:', await status())
    # right-drag to orbit
    x0, y0, w, h = await canvas_box(); cx, cy = x0 + w / 2, y0 + h / 2
    await page.mouse.move(cx, cy); await page.mouse.down(button='right')
    for k in range(12): await page.mouse.move(cx - k * 12, cy - k * 4); await page.wait_for_timeout(30)
    await page.mouse.up(button='right'); await page.wait_for_timeout(1500)
    await shot('06_3d_orbit.png')
    # walk forward 2 s with W
    await page.keyboard.down('KeyW'); await page.wait_for_timeout(2000); await page.keyboard.up('KeyW'); await page.wait_for_timeout(800)
    await shot('07_3d_walked.png')
    print('3D status:', await status())
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(3500)
