# Mount Hyjal from 5,000 yd tilted 45 degrees (test_terrain.py's far view), for comparing the ground's mesh
# before and after a change (J8, 2026-10-22: the uneven per-tile meshes). TAG names the shots:
#   TAG=after python3 run_page.py j8hyjal   -> shots/j8_after_hyjal.png, and j8_after_hyjal_tris.png with
#   each ground triangle with an image shaded a little lighter or darker, so the mesh shows (open sea left as it is)
import os
async def run():
    tag = os.environ.get('TAG', 'x')
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    setup = ('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode(\'free\'); ns.SetTopDown(false, true); local cam = ns.cam; '
             'cam.map, cam.x, cam.y, cam.dist, cam.yaw, cam.pitch = 1, 38.6 * 1600 / 3, -21.8 * 1600 / 3, 5000, 30, 45; '
             'cam.th = ns.GroundHeight(cam.x, cam.y, 1); for i = 1, 80 do ns.Redraw() end')
    await ev(f'__sandbox.lua().run("{setup}")')
    await page.wait_for_timeout(3000)
    await shot(f'j8_{tag}_hyjal.png')
    tint = ('local st = SANDBOX.namespaces.GPS3D.stats; for i, t in ipairs(st.visible) do if t.mesh and not t.mesh.detail and t.u1 then '
            'local k = (t.a * 7919 + t.b * 104729 + t.c * 1299709 + t.mesh.tx * 31 + t.mesh.ty * 17) % 97 / 96; '
            'local v = 0.45 + 0.55 * k; t.tex:SetVertexColor(v, v, v) end end; SANDBOX.namespaces.GPS3D.Redraw()')
    await ev(f'__sandbox.lua().run("{tint}")')
    await page.wait_for_timeout(2000)
    await shot(f'j8_{tag}_hyjal_tris.png')
    print(await ev('__sandbox.lua().run("local st = SANDBOX.namespaces.GPS3D.stats; return st.tris .. \' grid triangles, \' .. st.tiles .. \' tiles\'")'))
