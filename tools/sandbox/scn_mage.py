import os
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await page.select_option('#teleport', 'sw-mage'); await page.click('#btn-go'); await page.wait_for_timeout(4500)
    await shot(f'm_{tag}_A_top.png')
    await ev('__sandbox.slash("/gps3d test")'); await page.wait_for_timeout(6000)
    await ev('__sandbox.slash("/gps3d top")'); await page.wait_for_timeout(3500)
    await shot(f'm_{tag}_B_tilt.png')
