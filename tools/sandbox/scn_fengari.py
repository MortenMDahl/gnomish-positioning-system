async def run():
    await page.click('#btn-3d'); await page.wait_for_timeout(3000)
    await page.check('#loop'); await page.wait_for_timeout(5000)
    print('fengari 3D walking:', await status())
    await shot('f2_fengari_3d.png')
