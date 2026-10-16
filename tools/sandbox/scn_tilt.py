import os, json
VIEWS = json.loads(os.environ['VIEWS'])  # [[name, x, y, th_or_null(valley), yaw, pitch, dist], ...]
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await ev('Object.assign(__sandbox.player, {X: -9400, Y: -1300, map: 0, zone: "Elwynn Forest", sub: ""})'); await page.wait_for_timeout(1500)
    for name, x, y, th, yaw, pitch, dist in VIEWS:
        lua = f'''
local ns = SANDBOX.namespaces.GPS3D
local cam = ns.cam
ns.SetCamMode('free')
ns.SetTopDown(false, true)
cam.map = 0
local th = {'nil' if th is None else th}
if th == nil then
  local px, py = 18607, -25627
  for i = -700, 700, 50 do for j = -700, 700, 50 do local h = ns.GroundHeight(px + i, py + j) if h > 1 and (not th or h < th) then th = h end end end
end
cam.x, cam.y, cam.th, cam.yaw, cam.pitch, cam.dist = {x}, {y}, th, {yaw}, {pitch}, {dist}
ns.Render()
local _,_,_,_,_,_,_,_,cx,cy,cz = ns.CameraBasis()
print(("VIEW {name}: eye %.0f, ground under it %.0f, lift %.0f"):format(cz, ns.GroundHeight(cx, cy), ns.Lift()))
'''
        await ev(f'__sandbox.runLua({lua!r})'); await page.wait_for_timeout(3500)
        await shot(f't_{tag}_{name}.png')
    print('\n'.join(l for l in (await log_text()).split('\n') if 'VIEW' in l))
