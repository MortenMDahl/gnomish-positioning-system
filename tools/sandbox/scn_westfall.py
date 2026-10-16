import os
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await page.select_option('#teleport', 'westfall-ne'); await page.click('#btn-go'); await page.wait_for_timeout(4000)
    await shot(f'q_{tag}_top.png')
    x0, y0, w, h = await canvas_box(); await page.mouse.move(x0 + w / 2, y0 + h / 2)
    for _ in range(5): await page.mouse.wheel(0, 120); await page.wait_for_timeout(60)
    await page.wait_for_timeout(3000); await shot(f'q_{tag}_top_far.png')
    await ev('__sandbox.slash("/gps3d top")'); await page.wait_for_timeout(3500)
    await shot(f'q_{tag}_tilt_far.png')
