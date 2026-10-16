async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def uirect(expr):
        r = await ev('(() => { const L = __sandbox.lua(); L.run("local o = ' + expr + '; local l,b,r,t = SANDBOX.rect(o); SANDBOX_TMP = string.format(\'%f,%f,%f,%f\', l,b,r,t)"); return L.call("SANDBOX_GETTMP"); })()')
        return [float(v) for v in r.split(',')]
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    x0, y0, w, h = await canvas_box()
    def scr(ux, uy): return x0 + ux * s, y0 + h - uy * s
    ui = 'SANDBOX.namespaces.GnomishPositioningSystem.ui'
    f0 = await uirect('GPS_MapFrame')
    # drag the title band
    l, b, r, t = await uirect(ui + '.band')
    px, py = scr(l + 300, (b + t) / 2)
    await page.mouse.move(px, py); await page.mouse.down()
    for k in range(1, 9): await page.mouse.move(px - k * 10, py + k * 5); await page.wait_for_timeout(20)
    await page.mouse.up(); await page.wait_for_timeout(200)
    f1 = await uirect('GPS_MapFrame')
    print('move: frame', [round(v) for v in f0], '->', [round(v) for v in f1])
    # resize with the grip
    l, b, r, t = await uirect(ui + '.grip')
    px, py = scr((l + r) / 2, (b + t) / 2)
    await page.mouse.move(px, py); await page.mouse.down()
    for k in range(1, 9): await page.mouse.move(px - k * 12, py - k * 6); await page.wait_for_timeout(20)
    await page.mouse.up(); await page.wait_for_timeout(300)
    f2 = await uirect('GPS_MapFrame')
    print('resize: frame', [round(v) for v in f1], '->', [round(v) for v in f2])
    # next map
    l, b, r, t = await uirect(ui + '.next')
    px, py = scr((l + r) / 2, (b + t) / 2)
    await page.mouse.move(px, py); await page.mouse.down(); await page.mouse.up(); await page.wait_for_timeout(500)
    sub = await ev('(() => { const L = __sandbox.lua(); L.run("SANDBOX_TMP = ' + ui + '.subtitle:GetText()"); return L.call("SANDBOX_GETTMP"); })()')
    print('after >:', sub)
    await shot('w1_moved_resized_next.png')
    # close with x, then Escape test: reopen via M, Esc closes
    l, b, r, t = await uirect(ui + '.close')
    px, py = scr((l + r) / 2, (b + t) / 2)
    await page.mouse.move(px, py); await page.mouse.down(); await page.mouse.up(); await page.wait_for_timeout(200)
    shown1 = await ev('(() => { const L = __sandbox.lua(); L.run("SANDBOX_TMP = tostring(GPS_MapFrame:IsShown())"); return L.call("SANDBOX_GETTMP"); })()')
    await page.keyboard.press('KeyM'); await page.wait_for_timeout(200)
    shown2 = await ev('(() => { const L = __sandbox.lua(); L.run("SANDBOX_TMP = tostring(GPS_MapFrame:IsShown())"); return L.call("SANDBOX_GETTMP"); })()')
    await page.keyboard.press('Escape'); await page.wait_for_timeout(200)
    shown3 = await ev('(() => { const L = __sandbox.lua(); L.run("SANDBOX_TMP = tostring(GPS_MapFrame:IsShown())"); return L.call("SANDBOX_GETTMP"); })()')
    print('close x ->', shown1, '| M ->', shown2, '| Esc ->', shown3)
    # walking: W for 1 s moves the arrow/player north
    p0 = await ev('[__sandbox.player.X, __sandbox.player.Y]')
    await page.keyboard.down('KeyW'); await page.wait_for_timeout(1000); await page.keyboard.up('KeyW')
    p1 = await ev('[__sandbox.player.X, __sandbox.player.Y]')
    print('walk 1 s:', [round(v, 1) for v in p0], '->', [round(v, 1) for v in p1])
    # teleport to dungeon
    await page.select_option('#teleport', 'instance'); await page.click('#btn-go'); await page.wait_for_timeout(300)
    await page.keyboard.press('KeyM'); await page.wait_for_timeout(500)
    await ev('__sandbox.slash("/gps where")'); await page.wait_for_timeout(300)
