# A tour of the 3D view for Morten (2026-10-22): far views, close-ups with buildings, the planet.
# python3 run_page.py tour  -> shots/tour_*.png
VIEWS = [
    # name, map, gx, gy, dist, yaw, pitch
    ('hyjal_5000', 1, 38.6, 21.8, 5000, 30, 45),
    ('stormwind_3000', 0, 30.8, 48.6, 3000, 20, 45),
    ('stormwind_400', 0, 30.6, 48.4, 400, 30, 45),
    ('northshire_300', 0, 32.25, 48.7, 300, 200, 50),
    ('orgrimmar_250', 1, 40.2, 29.0, 250, 300, 45),
    ('orgrimmar_700', 1, 40.25, 28.9, 700, 330, 60),
    ('durotar_4000', 1, 41.5, 31.5, 4000, 0, 89.9),
    ('planet_90000', 0, 32.0, 40.0, 90000, 0, 89.9),
    ('planet_55000', 0, 30.0, 40.0, 55000, 0, 89.9),
]
import os
if os.environ.get('ONLY'): VIEWS = [v for v in VIEWS if v[0] in os.environ['ONLY'].split(',')]
async def run():
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    for name, m, gx, gy, d, yaw, pitch in VIEWS:
        top = 'true' if pitch > 89 else 'false'
        setup = ('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode(\'free\'); ns.SetTopDown(' + top + ', true); local cam = ns.cam; '
                 f'cam.map, cam.x, cam.y, cam.dist, cam.yaw, cam.pitch = {m}, {gx} * 1600 / 3, -{gy} * 1600 / 3, {d}, {yaw}, {pitch}; '
                 f'cam.th = ns.GroundHeight(cam.x, cam.y, {m}) or 0; if ns.SnapLift then ns.SnapLift() end; for i = 1, 120 do ns.Redraw() end')
        await ev(f'__sandbox.lua().run("{setup}")')
        await page.wait_for_timeout(4000)
        await ev('__sandbox.lua().run("for i = 1, 30 do SANDBOX.namespaces.GPS3D.Redraw() end")')
        await page.wait_for_timeout(1500)
        await shot(f'tour_{name}.png')
        print(name, await ev('__sandbox.lua().run("local st = SANDBOX.namespaces.GPS3D.stats; return (st.tris or 0) .. \' ground tris, \' .. (st.detail or 0) .. \' blocks\'")'))
