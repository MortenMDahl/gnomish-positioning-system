# S1 shells: several baked sets in one city data addon (2026-10-24), so the 3D view can pick, per level of detail, which
# set it draws (Shells.lua's five levels: from a distance, a set; sliders on the settings page). A set is one bake
# of one shell level: its shape (the level's geometry: 0 finest .. 3 coarsest, 4 the 66.7-yd blocks) and its pictures'
# density. Per unit one string per unit set (layout as sh_tolua.py; "" where the unit has no faces in that set), per
# block one string of the block set; pages Shells\S<set>_<page>.jpg. Also the ground grid's cells under the shells'
# tops (sh_floorcells.py), which GPS3D.lua sorts as the city's floor.
# Usage: python3 sh_tolua_sets.py <sets.json> <addon dir> <sandbox site dir> [name]
#   sets.json: [{"var": "e_", "lvl": 1, "out": "shells_oute_", "name": "..."}, ...] (unit sets, finest first, then one
#   with "lvl": 4: the blocks), "lod": [[start yd, set index], ...] (the five levels' defaults), "floor": "sh_floorcells.json",
#   "floor_image": ["floor.jpg", "sh_floorimg.json"] (the ground's picture round and under the shells: sh_floorimg.py)
import sys, os, json, pickle, numpy as np
from PIL import Image
SPEC, OUT, SITE = sys.argv[1], sys.argv[2], sys.argv[3]; NAME = sys.argv[4] if len(sys.argv) > 4 else 'Stormwind'
spec = json.load(open(SPEC))
B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
BLK = 1600 / 3 / 8
SHAPE = {0: 0.35, 1: 0.75, 2: 1.5, 3: 3.0, 4: 6.0}  # the levels' simplification (yd), sh_build3.py
def enc(v, n):
    v = int(v); assert 0 <= v < 64 ** n, (v, n)
    return ''.join(B64[(v >> (6 * (n - 1 - i))) & 63] for i in range(n))
sets = spec['sets']
units_sets = [s for s in sets if s['lvl'] < 4]; block_set = [s for s in sets if s['lvl'] == 4]
assert len(block_set) == 1 and sets[-1]['lvl'] == 4
for s in sets: s['F'] = pickle.load(open(f"sh_faces_{s['var']}{s['lvl']}.pkl", 'rb'))
maxerr = [0.0]
def level_string(fl, c):
    vid, verts = {}, []
    for f in fl:
        for p in f['c']:
            q = tuple(np.round((p - c) * 32).astype(int))
            if q not in vid: vid[q] = len(verts) + 1; verts.append(q)
    w = 2 if len(verts) < 4096 else 3
    out = [enc(len(verts), 3), enc(len(fl), 3), enc(w, 1)]
    out += [enc(x + 131072, 3) for q in verts for x in q]
    for f in fl:
        out.append(enc(len(f['c']), 1))
        out += [enc(vid[tuple(np.round((p - c) * 32).astype(int))], w) for p in f['c']]
        out.append(enc(f['page'], 1))
        tc = np.clip(np.round(f['tc'] * 4095), 0, 4095).astype(int)
        out += [enc(x, 2) for x in tc.reshape(-1)]
        maxerr[0] = max(maxerr[0], float(np.abs(tc / 4095 - f['tc']).max()))
    return ''.join(out)
def middle(fls):
    P = np.vstack([f['c'] for f in fls]); lo, hi = P.min(0), P.max(0); c = np.round((lo + hi) / 2 * 32) / 32
    return c, float(np.linalg.norm(P - c, axis=1).max())
def block_of(x, y): return (int(np.floor(x / BLK)) - 230) * 1000 + (int(np.floor(-y / BLK)) - 300)
# blocks
B = block_set[0]
blocks = {}
for f in B['F']['faces']: blocks.setdefault(-2 - f['unit'], []).append(f)
bidx, lua_blocks = {}, []
for bid, fl in sorted(blocks.items()):
    c, r = middle(fl); bidx[bid] = len(lua_blocks) + 1
    lua_blocks.append('{%.3f,%.3f,%.3f,%.1f,"%s"}' % (c[0], c[1], c[2], r, level_string(fl, c)))
# units: the union over the unit sets
def key_of(f):
    if f['unit'] >= 0: return ('b', f['unit'])
    c = f['c'].mean(0); return ('s', int(np.floor(c[0] / 60)), int(np.floor(c[1] / 60)))
units = {}
for i, s in enumerate(units_sets):
    for f in s['F']['faces']: units.setdefault(key_of(f), [[] for _ in units_sets])[i].append(f)
lua_units, orphans, nfaces = [], 0, [0] * len(units_sets)
for k, per in sorted(units.items(), key=lambda kv: str(kv[0])):
    c, r = middle([f for fl in per for f in fl])
    b = bidx.get(block_of(c[0], c[1]), 0); orphans += b == 0
    strs = []
    for i, fl in enumerate(per):
        strs.append('"%s"' % (level_string(fl, c) if fl else '')); nfaces[i] += len(fl)
    lua_units.append('{%.3f,%.3f,%.3f,%.1f,%d,%d,%s}' % (c[0], c[1], c[2], r, b, 1 if k[0] == 's' else 0, ','.join(strs)))
os.makedirs(OUT, exist_ok=True)
addon = os.path.basename(OUT.rstrip('/'))
xs = [float(u.split(',')[0][1:]) for u in lua_units]; ys = [float(u.split(',')[1]) for u in lua_units]
floor_cells = json.load(open(spec['floor'])) if spec.get('floor') else []
fimg = ''
if spec.get('floor_image'):
    fj, fb = spec['floor_image']; fb = json.load(open(fb))
    fimg = ', floorImage = { file = "Interface\\\\AddOns\\\\%s\\\\Shells\\\\Floor.jpg", x0 = %.1f, x1 = %.1f, y0 = %.1f, y1 = %.1f }' % (addon, fb['x0'], fb['x1'], fb['y0'], fb['y1'])
    os.makedirs(os.path.join(OUT, 'Shells'), exist_ok=True)
    Image.open(fj).save(os.path.join(OUT, 'Shells', 'Floor.jpg'), quality=88, optimize=True)
    os.makedirs(os.path.join(SITE, spec.get('jpg', 'shells')), exist_ok=True)
    Image.open(fj).save(os.path.join(SITE, spec.get('jpg', 'shells'), 'FLOOR.jpg'), quality=88, optimize=True)
set_lines = ', '.join('{ lvl = %d, shape = %.2f, ppy = %g, pages = %d, name = %s }' % (s['lvl'], SHAPE[s['lvl']], s['F']['ppy'], s['F']['npages'], json.dumps(s.get('name', ''))) for s in sets)
head = ['-- Generated by sh_tolua_sets.py (proof of concept S1, branch poc-shells): %s\'s buildings as closed shells with baked faces,' % NAME,
        '-- several baked sets (shape, picture density) for Shells.lua\'s levels of detail. A unit: {x, y, h, radius, its block, street (1) or',
        '-- building (0), one string per unit set ("" if none)}; a block (66.7 yd, every building and street in it together): {x, y, h,',
        '-- radius, the block set\'s string}. A string\'s layout: sh_tolua.py. Pictures: Shells\\S<set>_<page>.jpg.',
        'local _, ns = ...', 'ns.ShellData = ns.ShellData or {}', 'local U, B = {}, {}',
        'ns.ShellData[%s] = { map = 0, box = { %.1f, %.1f, %.1f, %.1f }, sets = { %s }, lod = { %s }, path = "Interface\\\\AddOns\\\\%s\\\\Shells\\\\S%%d_%%d.jpg", units = U, blocks = B,' % (
            json.dumps(NAME), min(xs), max(xs), min(ys), max(ys), set_lines, ', '.join('{ %g, %d }' % (a, b) for a, b in spec['lod']), addon),
        '  floor = { %s }%s }' % (','.join(str(c) for c in floor_cells), fimg)]
body = ['do local u = { %s }; for k = 1, #u do U[#U + 1] = u[k] end end' % ', '.join(lua_units[i:i + 50]) for i in range(0, len(lua_units), 50)]
body += ['do local b = { %s }; for k = 1, #b do B[#B + 1] = b[k] end end' % ', '.join(lua_blocks[i:i + 50]) for i in range(0, len(lua_blocks), 50)]
open(os.path.join(OUT, f'Shells_{NAME}.lua'), 'w').write('\n'.join(head + body) + '\n')
JPG = os.path.join(SITE, spec.get('jpg', 'shells'))
os.makedirs(JPG, exist_ok=True)
jbytes = 0
for i, s in enumerate(sets, 1):
    for p in range(s['F']['npages']):
        dst = os.path.join(JPG, f'S{i}_{p}.jpg')
        Image.open(os.path.join(s['out'], f"L{s['lvl']}_{p}.png")).convert('RGB').save(dst, quality=88, optimize=True); jbytes += os.path.getsize(dst)
print(json.dumps({'units': len(lua_units), 'blocks': len(lua_blocks), 'units_without_block': orphans, 'sets': [(s['lvl'], s['F']['ppy'], s['F']['npages']) for s in sets],
                  'faces_per_unit_set': nfaces, 'floor_cells': len(floor_cells), 'lua_bytes': os.path.getsize(os.path.join(OUT, f'Shells_{NAME}.lua')), 'jpeg_bytes': jbytes, 'max_uv_err': maxerr[0]}))
