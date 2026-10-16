# Frame cost with and without buildings (native Lua 5.4 + the sandbox engine), steady and while walking.
import math, time, sys
src = open('test_world.py').read().split("place(-8958.3, -190, 0, 0.3")[0]
exec(compile(src, 'setup', 'exec'))
place(-8958.3, -190, 0, 0.3, 'Elwynn Forest', 'Northshire Valley')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
st, cam, pl = ns2.stats, ns2.cam, ns2.player
def frames(n, turn=3):
    ts = []
    for k in range(n):
        cam.yaw = cam.yaw + turn
        t = time.perf_counter(); ns2.Render(); ts.append((time.perf_counter() - t) * 1000)
    return ts
def walk(X, Y, m, heading, yards, n):
    ts, blocks = [], []
    for k in range(n):
        x = X + math.cos(heading) * yards * k / n
        y = Y + math.sin(heading) * yards * k / n
        place(x, y, m, 1.0)
        t = time.perf_counter(); tick(1); ts.append((time.perf_counter() - t) * 1000)
        blocks.append(int(st.detail))
    return ts, blocks
rows = []
BUDGETS = [2000, 4000, 8000]
for name, X, Y, m in [('Stormwind Trade District', -8830, 640, 0), ('Orgrimmar', 1630, -4380, 1), ('Northshire Abbey', -8900, -160, 0), ('Goldshire', -9464, 62, 0), ('Open country (Westfall field)', -10300, 1500, 0)]:
    for detail in ['off'] + BUDGETS:
        G.SlashCmdList.GPS3D('detail ' + ('off' if detail == 'off' else 'on'))
        if detail != 'off': G.SlashCmdList.GPS3D('buildings %d' % detail)
        place(X, Y, m, 1.0); tick(5)
        for _ in range(8): tick(1)  # let pending blocks be made
        frames(2)
        ts = sorted(frames(40))
        rows.append((name, str(detail), ts[20], ts[-2], int(st.shown), int(st.detail), int(st.detailTris)))
for r in rows: print('%-30s buildings %-5s  steady %5.1f ms median %5.1f 2nd worst  shown %5d  blocks %3d  building tris %5d' % r)
G.SlashCmdList.GPS3D('detail on'); G.SlashCmdList.GPS3D('buildings 4000')
# walking 600 yards through Stormwind at running speed (7 yd/s, 30 fps -> 0.23 yd/frame would take 85 s;
# here 20 yd per frame, i.e. 85x faster, the worst case for building new blocks)
for (name, X, Y, m, hd), detail in [(w, d) for w in [('Stormwind', -8700, 400, 0, 1.0), ('Orgrimmar', 1500, -4500, 1, 0.8)] for d in ('off', 'on')]:
    G.SlashCmdList.GPS3D('detail ' + detail)
    name = name + ' buildings ' + detail
    place(X, Y, m, hd); tick(5)
    ts, blocks = walk(X, Y, m, hd, 600, 30)
    ts.sort()
    print(f'walk {name}: 30 frames x 20 yd: median {ts[15]:.1f} ms, worst {ts[-1]:.1f} ms, blocks {min(blocks)}-{max(blocks)}')
    place(X, Y, m, hd); tick(5)
    ts, blocks = walk(X, Y, m, hd, 600, 30 * 6); ts.sort()
    print(f'walk {name}: 180 frames x 3.3 yd: median {ts[90]:.1f} ms, worst {ts[-1]:.1f} ms, blocks {min(blocks)}-{max(blocks)}')
# decode + build cost of one block, Stormwind's densest
L.execute('''
function BLOCKCOST()
  local ns = SANDBOX.namespaces.GPS3D
  local t0 = os.clock()
  local n, tris = 0, 0
  local tb = ns.TileBlocks(0, 30, 48)
  for bi = 0, 63 do if tb[bi] then local g = ns.BlockGeo(0, 30, 48, bi); n = n + 1; tris = tris + g.nt end end
  return (os.clock() - t0) * 1000, n, tris
end''')
ms, n, tris = G.BLOCKCOST()
print(f'decode Stormwind tile 30_48: {n} blocks, {tris} triangles in {ms:.0f} ms ({ms / max(n,1):.1f} ms per block, {ms * 1000 / max(tris,1):.1f} us per triangle)')
