# The planet view's zoom, seen in the page: zooms out from 12,000 to 80,000 yd in steps of 4 % (scn_globezoom.py,
# headless Chromium) at three window sizes and checks that nothing jumps. Each frame is compared with the frame
# before shrunk by the step about the view's centre: what is left is what changed beyond the zoom itself. A jump is
# one step changing much more than both its neighbours; fades (the sea turning blue, the clouds coming in) rise
# and fall over many steps. Also the hand-over (18,000 yd) step against the steps before it.
# Run: python3 tools/sandbox/check_globezoom.py   (needs run_page.py's Chromium and site/wasmoon)
import json, os, subprocess, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = [('small', 400, 300, 1280, 900, None), ('default', 900, 650, 1280, 900, None), ('large', 1500, 950, 1920, 1200, None), ('tilted', 900, 650, 1280, 900, 50)]
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + detail if detail else ''))


def residuals(tag, W, H):
    meta = json.load(open(os.path.join(HERE, 'shots', f'gz_{tag}.json')))
    s, rows, prev = meta['scale'], [], None
    for st in meta['steps']:
        a = np.asarray(Image.open(os.path.join(HERE, 'shots', f'gz_{tag}_{st["i"]:03d}.png')).convert('RGB')).astype(np.float32)
        if prev is not None:
            h, w = a.shape[:2]
            sc = w / ((W - 58) * s)
            cx, cy = ((W / 2) - 4) * s * sc, ((H / 2) - 64) * s * sc
            k = 1 / 1.04
            p = np.asarray(Image.fromarray(prev.astype(np.uint8)).transform((w, h), Image.AFFINE, (1 / k, 0, cx - cx / k, 0, 1 / k, cy - cy / k), resample=Image.BILINEAR)).astype(np.float32)
            m = np.zeros((h, w), bool)
            m[int(cy - cy * k) + 3:int(cy + (h - cy) * k) - 3, int(cx - cx * k) + 3:int(cx + (w - cx) * k) - 3] = True
            rows.append((st['dist'], float(np.abs(p - a).mean(axis=2)[m].mean())))
        prev = a
    return rows


for tag, W, H, vw, vh, tilt in SIZES:
    env = dict(os.environ, GZ_TAG=f'chk_{tag}', GZ_W=str(W), GZ_H=str(H))
    if tilt: env['GZ_TILT'] = str(tilt)
    subprocess.run([sys.executable, os.path.join(HERE, 'run_page.py'), 'globezoom', str(vw), str(vh)], env=env, cwd=HERE, capture_output=True, timeout=900)
    rows = residuals(f'chk_{tag}', W, H)
    worst, at = 0, 0
    for i in range(1, len(rows) - 1):
        ratio = rows[i][1] / max(rows[i - 1][1], rows[i + 1][1], 0.3)
        if ratio > worst: worst, at = ratio, rows[i][0]
    check(f'{tag} window ({W} x {H}{", tilted %d" % tilt if tilt else ""}): no step jumps (each at most 1.8 x its larger neighbour)', worst <= 1.8, f'worst {worst:.2f} at {at:.0f} yd')
    ho = [r for r in rows if r[0] > 18000][0]
    before = [r[1] for r in rows if 15000 < r[0] <= 18000]
    check(f'{tag} window: the hand-over step (to {ho[0]:.0f} yd) no bigger than 1.6 x the steps before it', ho[1] <= 1.6 * max(before), f'{ho[1]:.2f} vs {max(before):.2f}')

print(f'{sum(results)} of {len(results)} checks passed')
sys.exit(0 if all(results) else 1)
