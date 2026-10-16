async def run():
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    for place in ['goldshire', 'orgrimmar', 'ns-front']:
        await page.select_option('#teleport', place); await page.click('#btn-go'); await page.wait_for_timeout(1500)
        await page.check('#loop'); await page.wait_for_timeout(5000)
        print(place, 'walking:', await status())
        await page.uncheck('#loop'); await page.wait_for_timeout(500)
    print('footer:', await ev('(() => { const L = __sandbox.lua(); L.run("SANDBOX_TMP = SANDBOX.namespaces.GPS3D.ui.footer:GetText()"); L.run("function SANDBOX_GETTMP() return SANDBOX_TMP end"); return L.call("SANDBOX_GETTMP"); })()'))
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(12000)
