async def run():
    await ev('__sandbox.slash("/gps test")'); await page.wait_for_timeout(3000)
    print('A:', (await log_text())[-600:])
    await ev('__sandbox.runLua("GPS_Toggle()")'); await page.wait_for_timeout(300)
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(6000)
    print('B:', (await log_text())[-900:])
    print(await ev('__sandbox.stats()'))
