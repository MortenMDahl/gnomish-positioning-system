import os
SETUP = r'''
local ns = SANDBOX.namespaces.GPS3D
local cam = ns.cam
local px, py = 18607, -25627
local best
for i = -700, 700, 25 do for j = -700, 700, 25 do
  local d = math.sqrt(i * i + j * j)
  if d > 450 and d < 650 then local h = ns.GroundHeight(px + i, py + j) if not best or h < best[3] then best = { px + i, py + j, h } end end
end end
local b = ns.modeButtons.free; b._scripts.OnClick(b)
if os.getenv and false then end
ns.SetTopDown(TOPDOWN, true)
cam.map = 0; if not TOPDOWN then cam.pitch = 45 end; cam.dist = DIST
cam.yaw = math.deg(math.atan(px - best[1], py - best[2])) % 360
cam.x, cam.y, cam.th = best[1], best[2], best[3]
ns.Render()
local e = select(11, ns.CameraBasis())
print(("HEIGHT valley ground %.0f, camera %.0f"):format(best[3], e))
'''
PAN = r'''
local ns = SANDBOX.namespaces.GPS3D
ns.cam.x, ns.cam.y = 18607, -25627
ns.Render()
'''
REPORT = r'''
local ns = SANDBOX.namespaces.GPS3D
local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
print(("HEIGHT %s: camera %.0f, ground under it %.0f, orbit height %.0f, dist %.0f"):format(TAGTXT, cz, ns.GroundHeight(cx, cy), ns.cam.th, ns.cam.dist))
'''
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await ev('Object.assign(__sandbox.player, {X: -9400, Y: -1300, map: 0, zone: "Elwynn Forest", sub: ""})'); await page.wait_for_timeout(1500)
    td = os.environ.get('TOPDOWN', '1') == '1'
    setup = SETUP.replace('TOPDOWN', 'true' if td else 'false').replace('DIST', os.environ.get('DIST', '600'))
    await ev(f'__sandbox.runLua({setup!r})'); await page.wait_for_timeout(3500)
    await ev(f'__sandbox.runLua({REPORT.replace("TAGTXT", repr("valley"))!r})')
    await shot(f'h_{tag}_A_valley.png')
    await ev(f'__sandbox.runLua({PAN!r})')
    x0, y0, w, h = await canvas_box()
    await page.mouse.move(x0 + w / 2, y0 + h / 2); await page.mouse.down()
    for k in range(1, 4): await page.mouse.move(x0 + w / 2 + 4 * k, y0 + h / 2); await page.wait_for_timeout(40)
    await page.mouse.up(); await page.wait_for_timeout(3500)
    await ev(f'__sandbox.runLua({REPORT.replace("TAGTXT", repr("over the mountain"))!r})')
    await shot(f'h_{tag}_B_mountain.png')
    for _ in range(30): await page.mouse.wheel(0, -120); await page.wait_for_timeout(40)
    await page.wait_for_timeout(3000)
    await ev(f'__sandbox.runLua({REPORT.replace("TAGTXT", repr("zoomed all the way in"))!r})')
    await shot(f'h_{tag}_C_zoomed.png')
    print('\n'.join(l for l in (await log_text()).split('\n') if 'HEIGHT' in l))
