# /gps3d probe in the page (GPS3D's Probe.lua): part 1 left out (PROBE_FULL=1 runs it, about a minute),
# a shot of the test picture of parts 2 and 3 (shots/probe_picture.png) and of the view after the probe
# (shots/probe_after.png, the same as before it: shots/probe_before.png).
import os
async def run():
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await page.select_option('#teleport', 'sw-trade'); await page.click('#btn-go'); await page.wait_for_timeout(4000)
    await shot('probe_before.png')
    if not os.environ.get('PROBE_FULL'):
        await ev('__sandbox.runLua("SANDBOX.namespaces.GPS3D.probe.SETTINGS = {}")')
    await ev('__sandbox.slash("/gps3d probe")')
    for _ in range(240):
        await page.wait_for_timeout(500)
        if 'TAKE A SCREENSHOT' in await log_text(): break
    await page.wait_for_timeout(1500)
    await shot('probe_picture.png')
    for _ in range(240):
        await page.wait_for_timeout(500)
        if ' done in ' in await log_text(): break
    await page.wait_for_timeout(2000)
    await shot('probe_after.png')
