# Building blocks close up (J2, 2026-10-21): every block in view within reach is drawn raised at every
# distance, the level lowered evenly over the view when the budget is short, and few pops while zooming.
# Reported in the game: close up only the blocks in the middle of the view stood up, the others nearby were
# flat minimap image, and moving the camera a little changed which (the budget went to a few fine blocks
# nearest the view's centre, and a block that did not fit at its level was left flat).
# Usage: python3 test_blocks.py          checks (exit 1 on a failure)
#        MEASURE=1 python3 test_blocks.py  only the measurements (for the code before the change)
import math, time, sys, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_world.py')).read().split("place(-8958.3, -190, 0, 0.3")[0]
# J2_GPS3D=<file>: load that GPS3D.lua instead of the site's copy (to measure the code before and after in turn)
if os.environ.get('J2_GPS3D'):
    src = src.replace("open(f'{SITE}/addons/{addon}/{f}').read()", "open(os.environ['J2_GPS3D'] if f == 'GPS3D.lua' else f'{SITE}/addons/{addon}/{f}').read()")
exec(compile(src, 'setup', 'exec'))
MEASURE = os.environ.get('MEASURE')
place(-8958.3, -190, 0, 0.3, 'Elwynn Forest', 'Northshire Valley')
G.SlashCmdList.GPS('')
tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame)
tick(10)
st, cam = ns2.stats, ns2.cam
G.GPS3D_DB.buildingModels = 'simple'; ns2.ModelsChanged()  # the simplified shapes are what this measures
G.SlashCmdList.GPS3D('buildings 4000')
BUDGET = 4000
# measured on the code before 2026-10-21 (MEASURE=1 on 8131b6d): pops while zooming at the four views below
BEFORE_ZOOM_EVENTS = [58, 100, 116, 91]

# Blocks in view within reach, measured on their own (the same box test as the drawing: the block's square,
# the tile's ground heights plus 150 yd for buildings, 40 px round the canvas), and which are drawn raised at
# what level (from the triangles drawn this frame). Compared with the frame before: blocks in view in both
# frames that appeared raised, went flat or changed level.
L.execute('''
local prev, cur, ranges = {}, {}, {}
-- a block's lowest and highest vertex, read from the fine level's string (kept by the test)
local function Range(tb, map, tx, ty, bi)
  local ns = SANDBOX.namespaces.GPS3D
  local key = (map * 4096 + ty * 64 + tx) * 64 + bi
  local r = ranges[key]
  if not r then
    local s, pos = tb.s, tb[bi]
    local base = (ns.Num(s, pos + 1, 3) - 131072) * 0.25
    local nv, np = ns.Num(s, pos + 4, 3), ns.Num(s, pos + 10, 1)
    local p, lo, hi = pos + 11 + np * 3, math.huge, -math.huge
    for _ = 1, nv do
      local v = ns.Num(s, p, 6)
      local dh = math.floor(v / 64) % 65536
      lo, hi = math.min(lo, dh), math.max(hi, dh)
      p = p + 6
    end
    r = { base + lo * 0.25, base + hi * 0.25 }
    ranges[key] = r
  end
  return r[1], r[2]
end
function J2_SNAP(track)
  local ns = SANDBOX.namespaces.GPS3D
  local cam, TILE, B = ns.cam, ns.TILE, ns.BLOCK
  local F = ns.Focal()
  local fx, fy, fz, rx, ry, ux, uy, uz, cx, cy, cz = ns.CameraBasis()
  local w, h = ns.canvas:GetSize()
  local halfW, halfH = w / 2 + 40, h / 2 + 40
  local drawn = {}
  for _, t in ipairs(ns.stats.visible) do
    local m = t.mesh
    if m.detail then local k = -m.key; local lv = k % 4; drawn[(k - lv) / 4] = lv end
  end
  -- the block's box (its square, its lowest and highest vertex) against the view's five planes (40 px round the canvas)
  local kx, ky = halfW / F, halfH / F
  local function inView(x0, x1, y0, y1, lo, hi)
    local near, left, right, below, above = true, true, true, true, true
    for c = 0, 7 do
      local px = (c % 2 == 0) and x0 or x1
      local py = (c % 4 < 2) and y0 or y1
      local ph = (c < 4) and lo or hi
      local dx, dy, dz = px - cx, py - cy, ph - cz
      local d = dx * fx + dy * fy + dz * fz
      local sx, sy = dx * rx + dy * ry, dx * ux + dy * uy + dz * uz
      if d > 1 then near = false end
      if sx > -kx * d then left = false end
      if sx < kx * d then right = false end
      if sy > -ky * d then below = false end
      if sy < ky * d then above = false end
    end
    return not (near or left or right or below or above)
  end
  local inview, raised, lv = 0, 0, { 0, 0, 0 }
  local far, sumd, nd = 0, { 0, 0, 0 }, { 0, 0, 0 } -- all blocks in view at the coarsest level; camera distance per level
  local flatD, raisedD = math.huge, 0 -- nearest flat block, furthest raised one (from the camera)
  local chosen = {} -- blocks the code chose to draw raised this frame (ns.blockList, e.lv > 0; none before 2026-10-21)
  for _, e in ipairs(ns.blockList) do if e.bk and e.lv and e.lv > 0 then chosen[e.bk] = true end end
  local pending = 0
  cur = {}
  local map = cam.map
  if cam.dist < 2500 then
    local R = 1000
    for ty = math.floor(-(cam.y + R) / TILE), math.floor(-(cam.y - R) / TILE) do
      for tx = math.floor((cam.x - R) / TILE), math.floor((cam.x + R) / TILE) do
        local tb = ns.TileBlocks(map, tx, ty)
        if tb then
          for bi = 0, 63 do
            if tb[bi] then
              local x0, y1 = tx * TILE + (bi % 8) * B, -ty * TILE - math.floor(bi / 8) * B
              local nx, ny = math.min(x0 + B, math.max(x0, cam.x)), math.min(y1, math.max(y1 - B, cam.y))
              if (nx - cam.x) ^ 2 + (ny - cam.y) ^ 2 < R * R and not (ns.ModelsCover and ns.ModelsCover(x0, y1))
                and inView(x0, x0 + B, y1 - B, y1, Range(tb, map, tx, ty, bi)) then
                local key = (map * 4096 + ty * 64 + tx) * 64 + bi
                local l = drawn[key] or 0
                cur[key] = l
                inview = inview + 1
                local tf = ns.TileBlocks(map, tx, ty, 3)
                far = far + tf.nt[bi]
                local lo, hi = Range(tb, map, tx, ty, bi)
                local dc = math.sqrt((x0 + B / 2 - cx) ^ 2 + (y1 - B / 2 - cy) ^ 2 + (math.min(hi, math.max(lo, cz)) - cz) ^ 2) -- (to the block's middle, at the camera's height within the block's)
                if l > 0 then
                  raised = raised + 1; lv[l] = lv[l] + 1; sumd[l] = sumd[l] + dc; nd[l] = nd[l] + 1
                  if dc > raisedD then raisedD = dc end
                else
                  if dc < flatD then flatD = dc end
                  if chosen[key] then pending = pending + 1 end
                end
              end
            end
          end
        end
      end
    end
  end
  local appear, gone, change = 0, 0, 0
  if track then
    for k, l in pairs(cur) do
      local p = prev[k]
      if p then
        if p == 0 and l > 0 then appear = appear + 1
        elseif p > 0 and l == 0 then gone = gone + 1
        elseif p ~= l then change = change + 1 end
      end
    end
  end
  prev = cur
  local function mean(l) return nd[l] > 0 and sumd[l] / nd[l] or -1 end
  return inview, raised, lv[1], lv[2], lv[3], appear, gone, change, far, mean(1), mean(2), mean(3), flatD, raisedD, pending
end
-- triangles of building meshes drawn this frame that were not drawn before (made this frame: the per-frame cap)
local seen = setmetatable({}, { __mode = "k" })
function J2_NEWTRIS()
  local ns = SANDBOX.namespaces.GPS3D
  local n, k, now = 0, 0, {}
  for _, t in ipairs(ns.stats.visible) do
    local m = t.mesh
    if m.detail and not seen[m] and not now[m] then now[m] = true; n = n + #m.tris; k = k + 1 end
  end
  for m in pairs(now) do seen[m] = true end
  return n, k
end
function J2_MEM() collectgarbage("collect"); collectgarbage("collect"); return collectgarbage("count") / 1024 end
''')

PLACES = [("Orgrimmar, Valley of Strength", 1630, -4380, 1), ("Stormwind, Trade District", -8830, 640, 0)]
def view(X, Y, m, dist, pitch, yaw=30):
    ns2.SetCamMode('free')
    ns2.SetTopDown(pitch >= 89, True)
    cam.map, cam.x, cam.y = m, 32 * TILE - Y, X - 32 * TILE
    cam.dist, cam.pitch, cam.yaw = dist, pitch, yaw
    cam.th = ns2.GroundHeight(cam.x, cam.y)

def settle():
    for _ in range(40):
        ns2.Render()
        if st.detailPending == 0: break
    ns2.Render()

def frame_ms(n=21, rounds=3):
    # the view turning back and forth by 0.3 degrees (every vertex moves); the lowest of 3 medians of 21 frames
    best = None
    for _ in range(rounds):
        G.J2_MEM()
        ts = []
        for k in range(n):
            cam.yaw = cam.yaw + (0.3 if k % 2 == 0 else -0.3)
            t = time.perf_counter(); ns2.Render(); ts.append((time.perf_counter() - t) * 1000)
        ts.sort()
        best = ts[n // 2] if best is None else min(best, ts[n // 2])
    return best

mem0 = G.J2_MEM()
rows = []
for name, X, Y, m in PLACES:
    place(X, Y, m, 1.0); tick(5)
    for pitch in (89.9, 45):
        for dist in (40, 80, 150, 300):
            view(X, Y, m, dist, pitch); settle()
            ms = frame_ms()
            view(X, Y, m, dist, pitch); settle()
            r = list(G.J2_SNAP(False))
            rows.append((name, pitch, dist, r[0], r[1], r[2], r[3], r[4], int(st.detailTris), ms, r[8], r[9:12], r[12], r[13], st.detailPx))
mem1 = G.J2_MEM()
print('\nplace                            tilt  dist  in view  raised  share   fine/coarse/far  tris   frame ms   all at far level')
for name, pitch, dist, iv, rs, l1, l2, l3, tris, ms, far, means, flatD, raisedD, T in rows:
    print(f'{name:32s} {("down" if pitch > 89 else "45"):>4s} {dist:5d} {iv:7d} {rs:7d} {100 * rs / max(iv, 1):5.0f} %  {l1:4d}/{l2:4d}/{l3:4d}  {tris:5d}  {ms:6.2f}   {far:6d} tris' + (f', threshold {T:.1f} px' if T else ''))
print(f'Lua memory after the views: {mem1:.0f} MB ({mem1 - mem0:+.0f} MB over the start)')

# zooming slowly, 2 % a frame, from 600 yd to the closest (15 yd), straight down and tilted, at both places
zoom = []
new_most, new_over = 0, 0  # most building triangles made in one frame; frames over the cap of 1,500 with more than one new block (one bigger block is allowed alone)
for name, X, Y, m in PLACES:
    for pitch in (89.9, 45):
        view(X, Y, m, 600, pitch); settle(); G.J2_SNAP(False); G.J2_NEWTRIS()
        frames, events, worst, flat, pend, fits_flat = 0, [0, 0, 0], 0, 0, 0, 0
        while cam.dist > 15:
            cam.dist = max(15, cam.dist * 0.98)
            ns2.Render()
            r = list(G.J2_SNAP(True))
            iv, rs, a, g, c = r[0], r[1], r[5], r[6], r[7]
            frames += 1
            events[0] += a; events[1] += g; events[2] += c
            worst = max(worst, a + g + c)
            flat += iv - rs
            pend += r[14]
            if r[8] <= BUDGET: fits_flat += iv - rs  # flat although every block fits at its coarsest level
            nt_, nb_ = G.J2_NEWTRIS()
            new_most = max(new_most, nt_)
            if nt_ > 1500 and nb_ > 1: new_over += 1
        zoom.append((name, pitch, frames, events, worst, flat / frames, pend / frames, fits_flat))
print(f'\nmost new building triangles in one frame while zooming: {new_most}; frames over 1,500 with more than one new block: {new_over}')
print('\nzoom 600 -> 15 yd, 2 % a frame: blocks in view that appear raised / go flat / change level (total), worst frame;')
print('flat blocks in view per frame (average; of them waiting to be made), flat blocks in frames where all fit at the coarsest level (total)')
for name, pitch, frames, ev, worst, flat, pend, ff in zoom:
    print(f'{name:32s} {("down" if pitch > 89 else "45"):>4s} {frames} frames: {ev[0]:4d} / {ev[1]:4d} / {ev[2]:4d} = {sum(ev):4d}, worst {worst:3d}, flat {flat:5.1f} ({pend:4.1f} waiting), {ff:4d}')
# the Mage Quarter tilted (scn_mage.py's view): steep triangles of the coarser levels drawn with the minimap image
# stretched down them (the purple streaks down its walls) against flat-coloured ones
view(-8980, 880, 0, 330, 45, 132); settle()
streaks = L.eval("""function()
  local ns = SANDBOX.namespaces.GPS3D
  local n = { 0, 0, 0 }; local stretched = { 0, 0, 0 }
  for _, t in ipairs(ns.stats.visible) do
    local m = t.mesh
    if m.detail then
      local lv = (-m.key) % 4
      local vx, vy, vh = m.vx, m.vy, m.vh
      local a, b, c = t.a, t.b, t.c
      local ex1, eh1, ez1 = vx[b] - vx[a], vh[b] - vh[a], -(vy[b] - vy[a])
      local ex2, eh2, ez2 = vx[c] - vx[a], vh[c] - vh[a], -(vy[c] - vy[a])
      local nx, nh, nz = eh1 * ez2 - ez1 * eh2, ez1 * ex2 - ex1 * ez2, ex1 * eh2 - eh1 * ex2
      local l = math.sqrt(nx * nx + nh * nh + nz * nz)
      if l > 0 and math.abs(nh / l) < 0.45 then
        n[lv] = n[lv] + 1
        if t.u1 and not (t.u1 == t.u2 and t.u2 == t.u3 and t.v1 == t.v2 and t.v2 == t.v3) then stretched[lv] = stretched[lv] + 1 end
      end
    end
  end
  return n[1], n[2], n[3], stretched[1], stretched[2], stretched[3], ns.stats.detail
end""")()
streaks = list(streaks)
print(f'\nMage Quarter tilted, 330 yd: {streaks[6]} blocks raised; steep triangles drawn fine/coarse/far {streaks[0]}/{streaks[1]}/{streaks[2]}, of them with the minimap stretched down them {streaks[3]}/{streaks[4]}/{streaks[5]}')
if MEASURE: sys.exit(0)

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS' if ok else 'FAIL'), name, detail)
fits = [r for r in rows if r[10] <= BUDGET]
over = [r for r in rows if r[10] > BUDGET]
check('every block in view within reach is drawn raised, close up and further out, straight down and tilted, at Orgrimmar and Stormwind (where all fit the budget at their coarsest level)',
      len(fits) >= 12 and all(r[4] == r[3] > 0 for r in fits), f'{len(fits)} views: ' + str([(r[0][:9], r[1], r[2], r[4], r[3]) for r in fits if r[4] < r[3]]))
check('where they do not (tilted, 300 yd: every block at the coarsest level is over the budget), the budget is used up and those nearest the camera are drawn raised',
      all(r[8] > BUDGET - 120 and r[13] <= r[12] for r in over), str([(r[0][:9], r[2], r[4], r[3], r[10], r[8], round(r[13]), round(r[12])) for r in over]))
check('building triangles within the budget in every view', all(r[8] <= BUDGET for r in rows), f'most {max(r[8] for r in rows)}')
def ordered(m):
    m = [v for v in m if v >= 0]
    return all(a < b for a, b in zip(m, m[1:]))
check('finer levels nearer the camera (mean camera distance of the fine, coarse, far blocks in that order); the fine level close up',
      all(ordered(r[11]) for r in rows) and all(r[5] > 0 for r in rows if r[2] == 40), str([(r[0][:9], r[1], r[2], [round(v) for v in r[11]]) for r in rows]))
before_events = BEFORE_ZOOM_EVENTS
check('zooming in slowly: fewer blocks pop (appear, go flat or change level) at every view, under half as many in all, at most 6 in any frame',
      all(sum(z[3]) <= b for z, b in zip(zoom, before_events)) and sum(sum(z[3]) for z in zoom) * 2 <= sum(before_events) and all(z[4] <= 6 for z in zoom),
      f'{[sum(z[3]) for z in zoom]} events (before {before_events}), worst frame {max(z[4] for z in zoom)} (before 17)')
check('zooming in slowly: no block in view flat in frames where all fit the budget at their coarsest level (a block whose mesh is still to be made shows another level of it meanwhile)',
      all(z[6] <= 1 and z[7] == 0 for z in zoom), f'{[round(z[6], 2) for z in zoom]} waiting a frame, {[z[7] for z in zoom]} flat in frames where all fit')
check('zooming in slowly: at most 1,500 building triangles made into textures in a frame (BUILD_LIMIT; a single bigger block alone)', new_most > 0 and new_over == 0, f'most {new_most}, frames over {new_over}')
check('coarser levels: no steep triangle shows the minimap image stretched down it (the Mage Quarter, tilted)', streaks[1] + streaks[2] > 100 and streaks[4] + streaks[5] == 0,
      f'{streaks[4]} of {streaks[1]} coarse, {streaks[5]} of {streaks[2]} far')
print(f'\n{sum(r[1] for r in results)} of {len(results)} checks passed')
sys.exit(0 if all(r[1] for r in results) else 1)
