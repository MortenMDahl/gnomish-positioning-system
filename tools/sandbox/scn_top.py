async def run():
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    for place in ['goldshire', 'sw-trade']:
        await page.select_option('#teleport', place); await page.click('#btn-go'); await page.wait_for_timeout(3500)
        x0, y0, w, h = await canvas_box()
        await page.mouse.move(x0 + w / 2, y0 + h / 2)
        for _ in range(4): await page.mouse.wheel(0, 120); await page.wait_for_timeout(60)
        await page.wait_for_timeout(3000)
        await shot(f't_{place}_tilted.png')
        await ev('__sandbox.slash("/gps3d top")'); await page.wait_for_timeout(3500)
        await shot(f't_{place}_top.png')
        await ev('__sandbox.slash("/gps3d top")'); await page.wait_for_timeout(1500)
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(6000)
