# (proof of concept S1, 2026-10-24) draw-order check of everything drawn (the ground, old building blocks, building
# shells): per canvas pixel, the triangle truly nearest the camera (its plane hit by the view ray) against the one the
# depth buckets put on top. Wrong pixels by pair kind: a shell drawn where the ground is nearer (shells seen through
# a mountain), ground over a nearer shell, shell over shell, ground over ground; and pixels whose top bucket holds
# more than one triangle there (order not defined). Usage: [VIEWJSON='{"name": [x, y, dist, yaw, pitch, th|null]}']
# [CMDS="/gps3d ...;..."] [TAG=name] python3 order_all.py; pictures shots/orderall_<view><TAG>.png (grey: right,
# red: shell over nearer ground (not the city's floor; blue: over the city's floor poking up through it, FLOORCELLS), orange: ground over nearer shell, magenta: other wrong, yellow: undefined).
import os, sys, json
import numpy as np
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
from matplotlib.path import Path
VIEWS = json.loads(os.environ.get('VIEWJSON', '{"near": [16380, -25920, 90, 25, 40, 117.5], "close": [16426, -25896, 200, 25, 45, 117.5], "sw_s": [16420, -26000, 260, 90, 45, null], "sw_low": [16430, -26150, 220, 95, 45, null], "far": [16426, -25896, 2000, 25, 50, 117.5]}'))
TAG = os.environ.get('TAG', '')
FLOOR = set(json.load(open(os.environ['FLOORCELLS']))) if os.environ.get('FLOORCELLS') else set()
def is_floor(w):
    pts = list(w[:3]) + [w.mean(0)]
    return any(int(np.floor(-p[1] * 0.06)) * 4096 + int(np.floor(p[0] * 0.06)) in FLOOR for p in pts)
DUMP = '''function(ns)
  local st = ns.stats
  local out = {}
  for i = 1, st.nActive do
    local m = st.active[i]
    local kind = m.hk and 2 or (m.detail and 1 or 0)
    for _, t in ipairs(m.tris) do
      if t.shown and t.bucket then
        local ids = t.d and { t.a, t.b, t.c, t.d } or { t.a, t.b, t.c }
        local row = { kind, t.bucket }
        for _, k in ipairs(ids) do row[#row+1] = m.vx[k]; row[#row+1] = m.vy[k]; row[#row+1] = m.vh[k] end
        out[#out+1] = table.concat(row, ",")
      end
    end
  end
  local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis()
  local cw, ch = ns.canvas:GetSize()
  return table.concat(out, ";") .. "|" .. table.concat({cx,cy,cz,fx,fy,fz,rx,ry,ux,uy,uz, ns.Focal(), cw, ch}, ",")
end'''
res = {}
for vk, vv in VIEWS.items():
    x, y, d, yaw, pitch, th = vv[:6]; mp = vv[6] if len(vv) > 6 else 0  # (optional 7th: the map)
    g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
    g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
    G.SlashCmdList.GPS3D('shells on')
    for c in os.environ.get('CMDS', '').split(';'):
        c = c.strip()
        if c.startswith('/gps3d '): G.SlashCmdList.GPS3D(c[7:])
    L.eval('function(ns, mp, x, y, d, yaw, pitch, th) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = mp; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = th or ns.GroundHeight(x, y, mp); if ns.SnapLift then ns.SnapLift() end end')(ns3, mp, x, y, d, yaw, pitch, th)
    for _ in range(30): L.eval('function(ns) ns.Redraw() end')(ns3); g.tick(1)
    rows, camtxt = L.eval(DUMP)(ns3).split('|')
    cam = [float(v) for v in camtxt.split(',')]
    C = np.array(cam[0:3]); Fw = np.array(cam[3:6]); R = np.array([cam[6], cam[7], 0.0]); U = np.array(cam[8:11]); Fl = cam[11]
    W2, H2 = int(cam[12] / 2), int(cam[13] / 2)
    xs, ys = np.meshgrid(np.arange(-W2, W2) + 0.5, np.arange(-H2, H2) + 0.5)
    rays = Fw[None, None, :] * Fl + R[None, None, :] * xs[..., None] + U[None, None, :] * ys[..., None]
    near = np.full(xs.shape, np.inf); nearkind = np.full(xs.shape, -1); nearid = np.full(xs.shape, -1); topid = np.full(xs.shape, -1); info = []
    topb = np.full(xs.shape, -1); topcount = np.zeros(xs.shape, int); topdep = np.full(xs.shape, np.inf); topkind = np.full(xs.shape, -1)
    n = 0
    for r in rows.split(';'):
        if not r: continue
        v = [float(a) for a in r.split(',')]; kind, b = int(v[0]), int(v[1]); w = np.array(v[2:]).reshape(-1, 3)
        nn = np.cross(w[1] - w[0], w[2] - w[0]); ln = np.linalg.norm(nn)
        if ln < 1e-9: continue
        nn /= ln
        q = w - C; dz = q @ Fw
        if np.any(dz <= 1.6): continue  # (cut at the near plane: drawn by DrawClipped, left out here)
        sx, sy = (q @ R) * Fl / dz, (q @ U) * Fl / dz
        x0, x1, y0, y1 = sx.min(), sx.max(), sy.min(), sy.max()
        i0, i1 = max(0, int(np.floor(y0 + H2))), min(2 * H2, int(np.ceil(y1 + H2))); j0, j1 = max(0, int(np.floor(x0 + W2))), min(2 * W2, int(np.ceil(x1 + W2)))
        if i0 >= i1 or j0 >= j1: continue
        sub = (slice(i0, i1), slice(j0, j1))
        ins = Path(np.vstack([np.stack([sx, sy], 1), [[sx[0], sy[0]]]])).contains_points(np.stack([xs[sub].ravel(), ys[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
        if not ins.any(): continue
        n += 1
        ry = rays[sub]; den = ry @ nn
        with np.errstate(divide='ignore', invalid='ignore'): t = ((w[0] - C) @ nn) / den
        dep = np.where(ins & np.isfinite(t) & (t > 0), t, np.inf)
        better = dep < near[sub]
        if kind == 0 and FLOOR and is_floor(w): kind = 3  # (the city's floor: ground in a cell under the shells' tops)
        info.append((kind, b, w)); tid = len(info) - 1
        near[sub] = np.where(better, dep, near[sub]); nearkind[sub] = np.where(better, kind, nearkind[sub]); nearid[sub] = np.where(better, tid, nearid[sub])
        tb_ = topb[sub]; higher = ins & (b > tb_); equal = ins & (b == tb_)
        topcount[sub] = np.where(higher, 1, np.where(equal, topcount[sub] + 1, topcount[sub]))
        topid[sub] = np.where(higher, tid, topid[sub]); topb[sub] = np.where(higher, b, tb_); topdep[sub] = np.where(higher, dep, topdep[sub]); topkind[sub] = np.where(higher, kind, topkind[sub])
    drawn = topb >= 0
    TOL = 0.3 / (Fl * np.linalg.norm(Fw))
    wrong = drawn & np.isfinite(near) & (topdep - near > TOL) & (topcount == 1)
    undef = drawn & (topcount > 1)
    tot = max(int(drawn.sum()), 1)
    def share(m): return round(float(m.sum()) / tot * 100, 3)
    sh_over_gr = wrong & (topkind == 2) & (nearkind != 2) & (nearkind != 3)
    sh_over_floor = wrong & (topkind == 2) & (nearkind == 3)
    gr_over_sh = wrong & (topkind != 2) & (nearkind == 2)
    sh_sh = wrong & (topkind == 2) & (nearkind == 2)
    gr_gr = wrong & (topkind != 2) & (nearkind != 2)
    res[vk] = {'tris': n, 'px': tot, 'wrong_%': share(wrong), 'shell_over_nearer_ground_%': share(sh_over_gr), 'shell_over_city_floor_poking_through_%': share(sh_over_floor), 'ground_over_nearer_shell_%': share(gr_over_sh),
               'shell_shell_%': share(sh_sh), 'ground_ground_%': share(gr_gr), 'same_bucket_%': share(undef)}
    from PIL import Image
    img = np.zeros(xs.shape + (3,), np.uint8); img[drawn] = (90, 90, 90); img[undef] = (230, 210, 0); img[sh_over_floor] = (60, 120, 220)
    img[gr_gr | sh_sh] = (220, 0, 220); img[gr_over_sh] = (255, 140, 0); img[sh_over_gr] = (255, 0, 0)
    os.makedirs('shots', exist_ok=True); Image.fromarray(img[::-1]).save(f'shots/orderall_{vk}{TAG}.png')
    print(vk, json.dumps(res[vk]), flush=True)
    for pxy in [p for p in os.environ.get('DEBUGPX', '').split(';') if p]:
        ix, iy = (int(v) for v in pxy.split(','))
        ii = 2 * H2 - 1 - iy
        for name, tid in (('top', topid[ii, ix]), ('nearest', nearid[ii, ix])):
            if tid < 0: print('  ', pxy, name, 'none'); continue
            kind, b, w = info[tid]; m = w.mean(0); hd = np.hypot(m[0] - C[0], m[1] - C[1])
            print('  ', pxy, name, 'kind', kind, 'bucket', b, 'middle', np.round(m, 1), 'hd %.1f' % hd, 'corners', np.round(w, 1).tolist(), 'size %.0f' % np.ptp(w[:, :2], 0).max())
print('ORDERALL', json.dumps(res))
