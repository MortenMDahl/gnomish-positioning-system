# B3: GPS3D.lua's block decoder (Lua) against build_detail.py's decoder (Python), every block of every tile.
import sys, time
sys.path.insert(0, '/home/claude/gps')
import build_detail as bd
src = open('test_world.py').read().split("place(-8958.3, -190, 0, 0.3")[0]
exec(compile(src, 'setup', 'exec'))
TILE = 1600 / 3; BLOCK = TILE / 8; STEP = TILE / 512
L.execute('''
function BLOCKSUMS(map, tx, ty, bi, level)
  local g = SANDBOX.namespaces.GPS3D.BlockGeo(map, tx, ty, bi, level)
  local sx, sy, sh, sc, si = 0, 0, 0, 0, 0
  for k = 1, #g.vx do sx = sx + g.vx[k]; sy = sy + g.vy[k]; sh = sh + g.vh[k]; sc = sc + g.vc[k] * k end
  for k = 1, #g.idx do si = si + g.idx[k] * k end
  return #g.vx, g.nt, sx, sy, sh, sc, si, #g.pal
end''')
lua_sums = G.BLOCKSUMS
t0 = time.time(); blocks = bad = 0
for low, detail in ((1, G.SANDBOX.namespaces['GPS3D'].Detail), (2, G.SANDBOX.namespaces['GPS3D'].DetailLow), (3, G.SANDBOX.namespaces['GPS3D'].DetailFar)):
  for m in list(detail.keys()):
    for key in list(detail[m].keys()):
        s = detail[m][key]; tx, ty = key % 64, key // 64
        for bi, (base, verts, pal, tris) in bd.decode_tile(s).items():
            x0 = tx * TILE + (bi % 8) * BLOCK; y0 = -ty * TILE - (bi // 8) * BLOCK
            sx = sy = sh = sc = 0.0
            for k, (x, y, h, c) in enumerate(verts, 1):
                sx += x0 + x * STEP; sy += y0 - y * STEP; sh += h; sc += c * k
            si = 0
            for k, v in enumerate([v + 1 for t in tris for v in t], 1): si += v * k
            got = lua_sums(m, tx, ty, bi, low)
            want = (len(verts), len(tris), sx, sy, sh, sc, si, len(pal))
            blocks += 1
            if tuple(got) != want:
                bad += 1
                if bad < 5: print('MISMATCH', low, m, key, bi, tuple(got), want)
print(f'{blocks} blocks (fine, coarse and far) compared, {bad} differ ({time.time() - t0:.0f} s)')
