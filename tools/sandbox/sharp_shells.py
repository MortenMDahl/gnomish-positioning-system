# (proof of concept S1, building shells) how sharp the shells' pictures are on screen. Per canvas pixel: the shell face
# truly nearest the camera (its plane hit by the view ray), and how many screen pixels one pixel of its picture covers
# along the direction where the picture is stretched most (magnification; 1 or less is as sharp as the canvas, 3 is a
# picture blown up three times). From the screen-to-face Jacobian, so walls seen at a slant count right. Also the
# picture pages the frame draws from (each 2,048 x 2,048: what has to be in texture memory for that view).
# Picture density per level: PPY (px a yard, levels 0-4, as baked). Views as perf_shells.py, orbit height TH (117.5).
# Usage: PPY=3,2,2,1,0.75 [PX="14 7 4.5 1.2"] [TAG=name] python3 sharp_shells.py
import os, sys, json
import numpy as np
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
from matplotlib.path import Path
VIEWS0 = {'closeup': (16380, -25920, 45, 25, 40), 'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62), 'far': (16426, -25896, 2000, 25, 50)}
VIEWS = {k: v for k, v in VIEWS0.items() if k in os.environ.get('VIEWSEL', ','.join(VIEWS0)).split(',')}
PPY = [float(v) for v in os.environ.get('PPY', '3,2,2,1,0.75').split(',')]
PX = os.environ.get('PX', '')
TH = float(os.environ.get('TH', '117.5'))
TAG = os.environ.get('TAG', 'base')
DUMP = '''function(ns)
  local out = {}
  local S = ns.shells
  local files = {}
  local function add(m, u)
    for k, t in ipairs(m.tris) do
      if t.shown then
        files[t.tex.file or "?"] = (files[t.tex.file or "?"] or 0) + 1
        local ids = t.d and { t.a, t.b, t.c, t.d } or { t.a, t.b, t.c }
        local row = { m.lvl, u.street and 1 or 0 }
        for _, i in ipairs(ids) do row[#row+1] = m.px[i]; row[#row+1] = m.py[i]; row[#row+1] = m.vx[i]; row[#row+1] = m.vy[i]; row[#row+1] = m.vh[i] end
        out[#out+1] = table.concat(row, ",")
      end
    end
  end
  for _, u in ipairs(S.city.units) do for l = 0, 4 do local m = u.mesh[l]; if m and not m.hidden then add(m, u) end end end
  for _, u in ipairs(S.city.blocks) do local m = u.mesh[4]; if m and not m.hidden then add(m, u) end end
  local fl = {}
  for f, n in pairs(files) do fl[#fl+1] = f .. "=" .. n end
  local fx,fy,fz,rx,ry,ux,uy,uz,cx,cy,cz = ns.CameraBasis()
  local cw, ch = ns.canvas:GetSize()
  return table.concat(out, ";") .. "|" .. table.concat({cx,cy,cz,fx,fy,fz,rx,ry,ux,uy,uz, ns.Focal(), cw, ch}, ",") .. "|" .. table.concat(fl, ";")
end'''
BANDS = (1.5, 3.0)
res = {}
for vk, (x, y, d, yaw, pitch) in VIEWS.items():
    g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
    g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
    G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('shells on')
    if PX: G.SlashCmdList.GPS3D('shells px ' + PX)
    L.eval('''function(ns, m, x, y, d, yaw, pitch, TH) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = TH; if ns.SnapLift then ns.SnapLift() end end''')(ns3, 0, x, y, d, yaw, pitch, TH)
    for _ in range(30): L.eval('function(ns) ns.Redraw() end')(ns3); g.tick(1)
    txt = L.eval(DUMP)(ns3)
    rows, camtxt, filetxt = txt.split('|'); cam = [float(v) for v in camtxt.split(',')]
    C = np.array(cam[0:3]); Fw = np.array(cam[3:6]); R = np.array([cam[6], cam[7], 0.0]); U = np.array(cam[8:11]); Fl = cam[11]
    W2, H2 = int(cam[12] / 2), int(cam[13] / 2)
    xs, ys = np.meshgrid(np.arange(-W2, W2) + 0.5, np.arange(-H2, H2) + 0.5)
    rays = Fw[None, None, :] * Fl + R[None, None, :] * xs[..., None] + U[None, None, :] * ys[..., None]
    near = np.full(xs.shape, np.inf); mag = np.zeros(xs.shape); lvl = np.full(xs.shape, -1); street = np.zeros(xs.shape, bool)
    nf = 0
    for r in rows.split(';'):
        if not r: continue
        v = [float(a) for a in r.split(',')]; lv, st = int(v[0]), int(v[1]); v = v[2:]; k = len(v) // 5
        sc = np.array([[v[5 * i], v[5 * i + 1]] for i in range(k)]); wc = np.array([[v[5 * i + 2], v[5 * i + 3], v[5 * i + 4]] for i in range(k)])
        n = np.cross(wc[1] - wc[0], wc[2] - wc[0]); nn = np.linalg.norm(n)
        if nn < 1e-9: continue
        n /= nn; nf += 1
        x0, y0 = sc.min(0); x1, y1 = sc.max(0)
        i0, i1 = max(0, int(np.floor(y0 + H2))), min(2 * H2, int(np.ceil(y1 + H2))); j0, j1 = max(0, int(np.floor(x0 + W2))), min(2 * W2, int(np.ceil(x1 + W2)))
        if i0 >= i1 or j0 >= j1: continue
        sub = (slice(i0, i1), slice(j0, j1))
        ins = Path(np.vstack([sc, sc[:1]])).contains_points(np.stack([xs[sub].ravel(), ys[sub].ravel()], 1)).reshape(i1 - i0, j1 - j0)
        if not ins.any(): continue
        ry = rays[sub]; den = ry @ n
        with np.errstate(divide='ignore', invalid='ignore'):
            t = ((wc[0] - C) @ n) / den
        ok = ins & np.isfinite(t) & (t > 0) & (np.abs(den) > 1e-9)
        if not ok.any(): continue
        better = ok & (t < near[sub])
        if not better.any(): continue
        # screen-to-face Jacobian: dP/dx = t (R - r (R.n)/(r.n)), dP/dy likewise with U; picture px = PPY * |dP|
        with np.errstate(divide='ignore', invalid='ignore'):
            dx = t[..., None] * (R[None, None, :] - ry * ((R @ n) / den)[..., None])
            dy = t[..., None] * (U[None, None, :] - ry * ((U @ n) / den)[..., None])
        a, b, c = (dx * dx).sum(-1), (dx * dy).sum(-1), (dy * dy).sum(-1)
        smin = np.sqrt(np.maximum((a + c) / 2 - np.sqrt(((a - c) / 2) ** 2 + b * b), 1e-12))   # smallest yd per screen px
        m = 1.0 / (PPY[lv] * smin)                                                             # screen px per picture px
        near[sub] = np.where(better, t, near[sub]); mag[sub] = np.where(better, m, mag[sub])
        lvl[sub] = np.where(better, lv, lvl[sub]); street[sub] = np.where(better, st == 1, street[sub])
    drawn = lvl >= 0
    out = {'canvas': [int(cam[12]), int(cam[13])], 'focal': round(Fl, 1), 'faces': nf, 'shell_px': int(drawn.sum())}
    for name, sel in (('buildings', drawn & ~street), ('streets', drawn & street)):
        mm = mag[sel]
        if mm.size == 0: continue
        out[name] = {'px': int(mm.size), 'median': round(float(np.median(mm)), 2), 'p90': round(float(np.percentile(mm, 90)), 2),
                     'sharp<=1.5': round(float((mm <= BANDS[0]).mean()), 3), 'soft1.5-3': round(float(((mm > BANDS[0]) & (mm <= BANDS[1])).mean()), 3), 'blurry>3': round(float((mm > BANDS[1]).mean()), 3),
                     'by_level': {str(l): round(float((lvl[sel] == l).mean()), 3) for l in range(5) if (lvl[sel] == l).any()},
                     'level_mag_median_p90': {str(l): [round(float(np.median(mag[sel & (lvl == l)])), 2), round(float(np.percentile(mag[sel & (lvl == l)], 90)), 2)] for l in range(5) if (sel & (lvl == l)).any()}}
    pages = sorted(f.split('=')[0].split('\\')[-1] for f in filetxt.split(';') if f)
    out['pages'] = pages; out['pages_n'] = len(pages)
    res[vk] = out
    # picture: magnification per pixel (green sharp, yellow soft, red blurry; streets darker)
    from PIL import Image
    img = np.zeros(xs.shape + (3,), np.uint8)
    col = np.where((mag <= BANDS[0])[..., None], np.array([60, 200, 90]), np.where((mag <= BANDS[1])[..., None], np.array([235, 200, 60]), np.array([230, 60, 50])))
    img[drawn] = (col[drawn] * np.where(street[drawn], 0.55, 1.0)[:, None]).astype(np.uint8)
    os.makedirs('shots', exist_ok=True); Image.fromarray(img[::-1]).save(f'shots/sharp_{TAG}_{vk}.png')
    print(vk, json.dumps(out), flush=True)
print('SHARPJSON', json.dumps(res))
