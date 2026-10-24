# (proof of concept S1) draw-order check of the building shells: every pair of shell faces drawn this frame that
# overlap on screen; at a point of the overlap, the face truly nearer the camera (its plane hit by the view ray) must
# be in a later depth bucket than the other. Pairs in the wrong order, and in the same bucket (order not defined),
# weighted by their overlap in pixels, against all shell pixels on screen. Views as perf_shells.py.
import os, sys, json
import numpy as np, shapely
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
VIEWS0 = {'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62), 'far': (16426, -25896, 2000, 25, 50)}
VIEWS = {k: v for k, v in VIEWS0.items() if k in os.environ.get('VIEWSEL', ','.join(VIEWS0)).split(',')}
DUMP = '''function(ns)
  local out, fn = {}, nil
  local S = ns.shells
  local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis()
  local uidx = 0
  local function add(m, u)
    for _, t in ipairs(m.tris) do
      if t.shown then
        local ids = t.d and { t.a, t.b, t.c, t.d } or { t.a, t.b, t.c }
        local row = { t.bucket, uidx, u.street and 1 or 0, u.d or 0 }
        for _, i in ipairs(ids) do row[#row+1] = m.px[i]; row[#row+1] = m.py[i]; row[#row+1] = m.vx[i]; row[#row+1] = m.vy[i]; row[#row+1] = m.vh[i] end
        out[#out+1] = table.concat(row, ",")
      end
    end
  end
  for _, u in ipairs(S.city.units) do uidx = uidx + 1; for l = 0, 4 do local m = u.mesh[l]; if m and not m.hidden then add(m, u) end end end
  for _, u in ipairs(S.city.blocks) do uidx = uidx + 1; local m = u.mesh[4]; if m and not m.hidden then add(m, u) end end
  local cw, ch = ns.canvas:GetSize()
  return table.concat(out, ";") .. "|" .. table.concat({cx,cy,cz,fx,fy,fz,rx,ry,ux,uy,uz, ns.Focal(), cw, ch}, ",")
end'''
res = {}
for vk, (x, y, d, yaw, pitch) in VIEWS.items():
    g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
    g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
    G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on')
    L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end end''')(ns3, 0, x, y, d, yaw, pitch)
    for _ in range(25): L.eval('function(ns) ns.Redraw() end')(ns3); g.tick(1)
    txt = L.eval(DUMP)(ns3)
    rows, camtxt = txt.split('|'); cam = [float(v) for v in camtxt.split(',')]
    C = np.array(cam[0:3]); Fw = np.array(cam[3:6]); R = np.array([cam[6], cam[7], 0.0]); U = np.array(cam[8:11]); Fl = cam[11]
    faces = []; meta = []
    for r in rows.split(';'):
        v = [float(a) for a in r.split(',')]; b = int(v[0]); ui, street, ud = int(v[1]), int(v[2]), v[3]; v = [v[0]] + v[4:]; k = (len(v) - 1) // 5
        sc = np.array([[v[1 + 5 * i], v[2 + 5 * i]] for i in range(k)]); wc = np.array([[v[3 + 5 * i], v[4 + 5 * i], v[5 + 5 * i]] for i in range(k)])
        poly = shapely.Polygon(sc)
        if not poly.is_valid: poly = poly.buffer(0)
        if poly.area < 1e-3: continue
        n = np.cross(wc[1] - wc[0], wc[2] - wc[0]); n /= np.linalg.norm(n) + 1e-12
        dd = (wc - C) @ (Fw / np.linalg.norm(Fw))
        fh = np.array([Fw[0], Fw[1]]); fh = fh / max(np.linalg.norm(fh), 1e-9)
        gx, gy = wc[:, 0] - C[0], wc[:, 1] - C[1]
        hf = gx * fh[0] + gy * fh[1]; hr = np.hypot(gx, gy)
        meta.append({'centroid': dd.mean(), 'far': dd.max(), 'near': dd.min(), 'street': street, 'ud': ud, 'unit': ui,
                     'hf_c': hf.mean(), 'hf_min': hf.min(), 'hr_c': hr.mean(), 'hr_min': hr.min(), 'hr_c2': np.hypot(gx.mean(), gy.mean()), 'top': abs(n[2]) > 0.3, 'h': wc[:, 2].mean()})
        faces.append((b, poly, wc[0], n))
    W2, H2 = int(cam[12] / 2), int(cam[13] / 2)
    # per pixel of the canvas: the face painter's draws on top (highest bucket) and the face truly nearest
    xs, ys = np.meshgrid(np.arange(-W2, W2) + 0.5, np.arange(-H2, H2) + 0.5)
    topb = np.full(xs.shape, -1); topcount = np.zeros(xs.shape, int); topface = np.full(xs.shape, -1)
    near = np.full(xs.shape, np.inf); nearface = np.full(xs.shape, -1); topdep = np.full(xs.shape, np.inf)
    from matplotlib.path import Path
    masks = []
    rays = Fw[None, None, :] * Fl + R[None, None, :] * xs[..., None] + U[None, None, :] * ys[..., None]
    for k, (b, poly, p0, n) in enumerate(faces):
        x0, y0, x1, y1 = poly.bounds
        i0, i1 = max(0, int(np.floor(y0 + H2))), min(2 * H2, int(np.ceil(y1 + H2))); j0, j1 = max(0, int(np.floor(x0 + W2))), min(2 * W2, int(np.ceil(x1 + W2)))
        if i0 >= i1 or j0 >= j1: masks.append(None); continue
        sub = (slice(i0, i1), slice(j0, j1))
        pts = np.stack([xs[sub].ravel(), ys[sub].ravel()], 1)
        ext = np.asarray(poly.exterior.coords) if poly.geom_type == 'Polygon' else np.asarray(max(poly.geoms, key=lambda g: g.area).exterior.coords)
        ins = Path(ext).contains_points(pts).reshape(i1 - i0, j1 - j0)
        if not ins.any(): masks.append(None); continue
        ry = rays[sub]; den = ry @ n
        with np.errstate(divide='ignore', invalid='ignore'): t = ((p0 - C) @ n) / den
        dep = np.where(ins & np.isfinite(t) & (t > 0), t, np.inf)
        masks.append((sub, ins, dep))
        cur = near[sub]; better = dep < cur
        near[sub] = np.where(better, dep, cur); nearface[sub] = np.where(better, k, nearface[sub])
        tb = topb[sub]; higher = ins & (b > tb); equal = ins & (b == tb)
        topcount[sub] = np.where(higher, 1, np.where(equal, topcount[sub] + 1, topcount[sub]))
        topface[sub] = np.where(higher, k, topface[sub]); topb[sub] = np.where(higher, b, tb); topdep[sub] = np.where(higher, dep, topdep[sub])
    drawn = topb >= 0
    TOL = float(os.environ.get('ORDER_TOL', '0.3')) / (Fl * np.linalg.norm(Fw))   # (0.3 yd along the view axis, in the ray parameter's units)
    # orders simulated offline: the face with the smallest key is drawn last (on top)
    KEYS = {'centroid': lambda m: m['centroid'], 'farthest': lambda m: m['far'], 'nearest': lambda m: m['near'],
            'unit_k0.1': lambda m: m['ud'] + (m['centroid'] - m['ud']) * 0.1,
            'streets_first+centroid': lambda m: m['centroid'] - (0 if m['street'] else 1e5),
            'streets_first+farthest': lambda m: m['far'] - (0 if m['street'] else 1e5),
            'streets_first+centroid_minus_far': lambda m: (m['centroid'] + m['far']) / 2 - (0 if m['street'] else 1e5),
            'hfwd_centroid': lambda m: m['hf_c'], 'hfwd_min': lambda m: m['hf_min'], 'hrad_centroid': lambda m: m['hr_c2'], 'hrad_mean': lambda m: m['hr_c'], 'hrad_min': lambda m: m['hr_min'],
            'hrad_centroid-h': lambda m: m['hr_c2'] - 0.3 * m['h'], 'streets_first+hrad_centroid': lambda m: m['hr_c2'] - (0 if m['street'] else 1e5)}
    # unit-contiguous orders: a unit's key, then its faces by horizontal distance
    from collections import defaultdict
    gu = defaultdict(list)
    for m in meta: gu[m['unit']].append(m)
    umin = {u: min(m['hr_min'] for m in ms) for u, ms in gu.items()}
    ucen = {u: float(np.mean([m['hr_c2'] for m in ms])) for u, ms in gu.items()}
    umax = {u: max(m['hr_min'] for m in ms) for u, ms in gu.items()}
    utop = {u: max(m['h'] for m in ms) for u, ms in gu.items()}
    KEYS.update({
        'U:min': lambda m: umin[m['unit']] + 1e-4 * m['hr_c2'],
        'U:cen': lambda m: ucen[m['unit']] + 1e-4 * m['hr_c2'],
        'U:streets,min': lambda m: umin[m['unit']] - (0 if m['street'] else 1e5) + 1e-4 * m['hr_c2'],
        'U:streets,cen': lambda m: ucen[m['unit']] - (0 if m['street'] else 1e5) + 1e-4 * m['hr_c2'],
        'U:streets,min+max': lambda m: (umin[m['unit']] + umax[m['unit']]) / 2 - (0 if m['street'] else 1e5) + 1e-4 * m['hr_c2'],
    })
    sim = {}
    for kn, kf in KEYS.items():
        key = np.array([kf(m) for m in meta])
        best = np.full(xs.shape, np.inf); bface = np.full(xs.shape, -1); bdep = np.full(xs.shape, np.inf)
        for k2, (b, poly, p0, n) in enumerate(faces):
            if masks[k2] is None: continue
            sub, ins, dep = masks[k2]
            cur = best[sub]; take = ins & (key[k2] < cur)
            best[sub] = np.where(take, key[k2], cur); bface[sub] = np.where(take, k2, bface[sub]); bdep[sub] = np.where(take, dep, bdep[sub])
        okpix = bface >= 0
        wr = okpix & (bdep - near > TOL)
        uarr = np.array([m['unit'] for m in meta]); same_unit = wr & (uarr[np.maximum(bface, 0)] == uarr[np.maximum(nearface, 0)])
        sarr = np.array([m['street'] for m in meta]); dst = sarr[np.maximum(bface, 0)]; nst = sarr[np.maximum(nearface, 0)]
        tot_ = max(okpix.sum(), 1)
        sim[kn] = (round(float(wr.sum() / tot_), 4), round(float(same_unit.sum() / tot_), 4),
                   'drawn street/near bld %.4f, drawn bld/near street %.4f, both bld %.4f, both street %.4f' % tuple(float((wr & (dst == a) & (nst == b)).sum() / tot_) for a, b in ((1, 0), (0, 1), (0, 0), (1, 1))))

    # a pixel is wrong when the truly nearest face is not in the top bucket; undefined when it is, with others there too
    nb = np.array([f[0] for f in faces])
    nearb = np.where(nearface >= 0, nb[np.maximum(nearface, 0)], -1)
    wrong = drawn & (nearb < topb) & (topdep - near > TOL)
    undefined = drawn & (nearb == topb) & (topcount > 1)
    total = drawn.sum()
    res[vk] = {'faces': len(faces), 'shell_px': int(total), 'wrong_px': int(wrong.sum()), 'wrong_share': round(float(wrong.sum() / max(total, 1)), 4), 'same_bucket_px': int(undefined.sum()), 'same_share': round(float(undefined.sum() / max(total, 1)), 4), 'simulated_wrong_share': sim}
    from PIL import Image
    img = np.zeros(xs.shape + (3,), np.uint8); img[drawn] = (90, 90, 90); img[undefined] = (255, 200, 0); img[wrong] = (255, 0, 0)
    Image.fromarray(img[::-1]).save(f'shots/shells_order_{vk}.png')
    rng = np.random.default_rng(1); pal = rng.integers(40, 255, (len(faces) + 1, 3)).astype(np.uint8)
    a = pal[np.where(topface >= 0, topface, len(faces))]; a[topface < 0] = 0
    b = pal[np.where(nearface >= 0, nearface, len(faces))]; b[nearface < 0] = 0
    Image.fromarray(np.concatenate([a[::-1], b[::-1]], 1)).save(f'shots/shells_order_ids_{vk}.png')
    print(vk, res[vk], flush=True)
print('ORDERJSON', json.dumps(res))
