async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    await page.click('#btn-3d'); await page.wait_for_timeout(2000)
    pos = await ev('(() => { const L = __sandbox.lua(); L.run("local b = SANDBOX.namespaces.GPS3D.modeButtons.behind; local l,bb,r,t = SANDBOX.rect(b); SANDBOX_TMP = string.format(\'%f,%f\', (l+r)/2, (bb+t)/2)"); return L.call("SANDBOX_GETTMP"); })()')
    ux, uy = [float(v) for v in pos.split(',')]
    x0, y0, w, h = await canvas_box()
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    await page.mouse.move(x0 + ux * s, y0 + h - uy * s); await page.mouse.down(); await page.mouse.up()
    await page.wait_for_timeout(800)
    cx, cy = x0 + w / 2, y0 + h / 2
    await page.mouse.move(cx, cy)
    for _ in range(9): await page.mouse.wheel(0, -120); await page.wait_for_timeout(50)
    await page.check('#loop')
    await page.wait_for_timeout(4000)
    await shot('b1_behind_close.png')
    print('walking in Behind:', await status())
    print(await ev('(() => { const L = __sandbox.lua(); L.run("local c = SANDBOX.namespaces.GPS3D.cam; SANDBOX_TMP = string.format(\'yaw %.1f pitch %.1f dist %.1f mode %s\', c.yaw, c.pitch, c.dist, SANDBOX.namespaces.GPS3D.CamMode())"); return L.call("SANDBOX_GETTMP"); })()'))
    await page.uncheck('#loop')
    await page.wait_for_timeout(500)
