# Binary inputs for the visibility pass: triangles (9 floats each, GL axes X east, Y up, Z south) and the terrain
# under them (GPS's 16.7-yd grid, 1 yd lower) as an occluder
import sys, re, numpy as np
sys.path.insert(0, '/home/claude/gps/scripts')
from build_world import decode
from load import load
T = 1600 / 3
for name in ('stormwind', 'orgrimmar'):
    m = load(name); P, Tr = m['P'], m['T']
    gl = np.stack([P[:, 0], P[:, 2], -P[:, 1]], -1).astype(np.float32)
    gl[Tr].reshape(-1).astype(np.float32).tofile(f'{name}_tris.f32')
    mp = m['meta']['map']; cx, cz, R = m['meta']['cx'], m['meta']['cz'], m['meta']['R']
    src = open(f'/home/claude/gps/prototypes/GPS3D/Data/World_{mp}.lua').read()
    quads = []
    for ty in range(int((cz - R) // T) - 1, int((cz + R) // T) + 2):
        for tx in range(int((cx - R) // T) - 1, int((cx + R) // T) + 2):
            mm = re.search(r'\n\[%d\]="([^"]+)"' % (ty * 64 + tx), src)
            if not mm: continue
            h = np.array(decode(mm.group(1)[:3 + 33 * 33 * 2])).reshape(33, 33) - 1.0
            s = T / 32
            for r in range(32):
                for c in range(32):
                    x0, z0 = tx * T + c * s, ty * T + r * s
                    a = (x0, h[r, c], z0); b = (x0 + s, h[r, c + 1], z0); cc = (x0, h[r + 1, c], z0 + s); d = (x0 + s, h[r + 1, c + 1], z0 + s)
                    quads += [a, cc, b, b, cc, d]
    np.array(quads, np.float32).reshape(-1).tofile(f'{name}_ground.f32')
    open(f'{name}_box.txt', 'w').write(f'{cx} {cz} {R} {P[:, 2].min()} {P[:, 2].max()} {len(Tr)}')
    print(name, len(Tr), 'ground tris', len(quads) // 3)
