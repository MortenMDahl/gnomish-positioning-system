# The cave just east of Northshire Valley (WMO 110497 at gx 34.218, gy 47.769) and the mine in Northshire
# (110750 at 32.247, 48.212), tilted and straight down, in Free mode looking at fixed points. OUT prefix: CAVE_TAG.
import os
TAG = os.environ.get('CAVE_TAG', 'x')
T = 1600 / 3
async def look(name, gx, gy, yaw, pitch, dist):
    x, y = gx * T, -gy * T
    await ev(f'''__sandbox.runLua(`local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown({str(pitch > 89).lower()}, true)
      local c = ns.cam; c.map, c.x, c.y, c.yaw, c.pitch, c.dist = 0, {x}, {y}, {yaw}, {pitch}, {dist}; c.th = ns.GroundHeight({x}, {y}, 0)`)''')
    await page.wait_for_timeout(2500)
    await shot(f'cave_{TAG}_{name}.png')
async def run():
    await ev('Object.assign(__sandbox.player, { X: -8410, Y: -1210, map: 0, facing: 1.57, zone: "Elwynn Forest", sub: "" })')
    await page.click('#btn-3d'); await page.wait_for_timeout(3000)
    await look('cave_tilt', 34.205, 47.775, 260, 45, 160)
    await look('cave_top', 34.205, 47.775, 0, 89.9, 220)
    await look('mine_tilt', 32.235, 48.212, 260, 45, 200)
    print(TAG, await status())
