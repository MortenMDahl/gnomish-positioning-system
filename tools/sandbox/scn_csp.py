async def run():
    await ev('__sandbox.slash("/gps test")'); await page.wait_for_timeout(3000)
