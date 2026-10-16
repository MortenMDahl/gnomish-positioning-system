async def run():
    print('boot:', [l for l in (await log_text()).splitlines() if 'loaded in' in l])
    await page.click('#btn-3d'); await page.wait_for_timeout(3000)
    await shot('b_00_northshire.png'); print('northshire', await status())
    for place in ['sw-trade', 'sw-cathedral', 'stormwind', 'ironforge', 'orgrimmar', 'lordaeron', 'thunderbluff', 'bootybay', 'stratholme']:
        await page.select_option('#teleport', place); await page.click('#btn-go')
        await page.wait_for_timeout(3500)
        await shot(f'b_{place}.png')
        print(place, await status())
    # Stormwind without buildings, same view
    await page.select_option('#teleport', 'sw-trade'); await page.click('#btn-go'); await page.wait_for_timeout(2500)
    await ev('__sandbox.slash("/gps3d detail off")'); await page.wait_for_timeout(1500)
    await shot('b_sw-trade_off.png')
    await ev('__sandbox.slash("/gps3d detail on")'); await page.wait_for_timeout(1500)
    await ev('__sandbox.slash("/gps3d buildings 8000")'); await page.wait_for_timeout(2500)
    await shot('b_sw-trade_8000.png'); print('8000:', await status())
    await ev('__sandbox.slash("/gps3d buildings 4000")')
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(6000)
