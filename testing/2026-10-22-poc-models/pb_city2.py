# The game's models for one city as a load-on-demand data addon (performance round 1, 2026-10-23).
# From pb_units' buildings and facing groups, with:
#   * 4-corner parts (pb_quads.merge_quads): wall rectangles as one texture instead of two;
#   * a compact format: every facing group's geometry is one string (GPS's 64-letter alphabet), decoded by the
#     addon only when the building is first drawn; only a small header per building and group is plain Lua.
# String layout of a group (all numbers unsigned, offset where noted; "nN" = N letters):
#   n3 vertices, n3 parts, n1 index width w (2 or 3), n2 palette size, palette fileIDs n4 each,
#   vertices: x, y, h as n3 each, (value / 32 yd) + 131072, relative to the building's middle,
#   parts: n1 corners (3 or 4), corners n<w> each (1-based), n2 palette index (1-based), n2 sqrt(piece area) * 32,
#          then UVs n3 each per corner (u then v), (value * 1024) + 131072, after moving the part's UVs by whole
#          repeats so its first corner lies in [0, 1).
# Usage: python3 pb_city2.py <out addon dir> [name]  (env QUADS=0 writes triangles only)
import os, sys, json, numpy as np
os.environ['RANK'] = 'value'; os.environ.setdefault('VISTAG', 'pbvw')
src = open('pb_city.py').read(); exec(compile(src[:src.index('cells = {}')], 'pb_city_part', 'exec'))
from pb_quads import merge_quads
OUT = sys.argv[1]; NAME = sys.argv[2] if len(sys.argv) > 2 else 'Stormwind'
QUADS = os.environ.get('QUADS', '1') == '1'
B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
def enc(v, n):
    v = int(v); assert 0 <= v < 64 ** n, (v, n)
    return ''.join(B64[(v >> (6 * (n - 1 - i))) & 63] for i in range(n))
z = np.load('pb_buildings.npz'); bld, st = z['bld'], z['street']
nrm = np.cross(V[T2[:, 1]] - V[T2[:, 0]], V[T2[:, 2]] - V[T2[:, 0]]); pa = np.linalg.norm(nrm, axis=1) / 2; nrm /= np.maximum(2 * pa[:, None], 1e-9)
sector = (np.floor((np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) + 360 + 22.5) / 45).astype(int) % 8) + 2
grp = np.where(BF == 1, 0, np.where(nrm[:, 2] > 0.8, 1, np.where(nrm[:, 2] < -0.8, 10, sector)))
piece_area = parea[PC]
UV3 = UVc.reshape(-1, 3, 2) if UVc.ndim == 2 else UVc
units_lua, totals = [], {'tris': 0, 'parts': 0, 'quads': 0, 'groups': 0, 'units': 0, 'max_uv_err': 0.0, 'max_v_err': 0.0}
qstats = {}
check = []     # (unit, group, decoded-reference) for the decode test: a sample of every 10th group, exact source values
for u in np.unique(bld):
    m = np.nonzero(bld == u)[0]
    Vu = V[T2[m]].reshape(-1, 3); lo, hi = Vu.min(0), Vu.max(0); c = (lo + hi) / 2; r = float(np.linalg.norm(Vu - c, axis=1).max())
    c = np.round(c * 32) / 32
    groups = []
    for gi in np.unique(grp[m]):
        lst = m[grp[m] == gi]
        lst = lst[np.lexsort((PC[lst], -piece_area[lst]))]
        if gi == 0: ax, sa = (0.0, 0.0, 1.0), 2.0
        else:
            w = pa[lst][:, None]; axv = (nrm[lst] * w).sum(0); axv /= max(np.linalg.norm(axv), 1e-9)
            ang = np.arccos(np.clip(nrm[lst] @ axv, -1, 1)).max(); ax, sa = tuple(axv), float(np.sin(min(ang, np.pi / 2)))
        if QUADS:
            parts, qs = merge_quads(lst, T2, V, UV3, PC, BF)
            for k, v in qs.items(): qstats[k] = qstats.get(k, 0) + v
        else:
            parts = [(tuple(int(v) for v in T2[p]), UV3[p].reshape(-1), int(p)) for p in lst]
        # vertices in first-use order
        order, seen_v = [], {}
        for corners, _, _ in parts:
            for v in corners:
                if v not in seen_v: seen_v[v] = len(order) + 1; order.append(v)
        Vg = V[order]
        q = np.round((Vg - c) * 32).astype(int) + 131072
        totals['max_v_err'] = max(totals['max_v_err'], float(np.abs((q - 131072) / 32 + c - Vg).max()))
        width = 2 if len(order) < 4096 else 3
        pal = sorted(set(int(FD[p]) for _, _, p in parts)); pidx = {f: i + 1 for i, f in enumerate(pal)}
        s = [enc(len(order), 3), enc(len(parts), 3), enc(width, 1), enc(len(pal), 2)] + [enc(f, 4) for f in pal]
        s += [enc(x, 3) for x in q.reshape(-1)]
        ref_uv = []
        for corners, uv, p in parts:
            uv = np.asarray(uv, float).reshape(-1, 2)
            uv = uv - np.floor(uv[0])
            qu = np.round(uv * 1024).astype(int) + 131072
            totals['max_uv_err'] = max(totals['max_uv_err'], float(np.abs((qu - 131072) / 1024 - uv).max()))
            s.append(enc(len(corners), 1)); s += [enc(seen_v[v], width) for v in corners]
            s.append(enc(pidx[int(FD[p])], 2)); s.append(enc(min(4095, round(np.sqrt(piece_area[p]) * 32)), 2))
            s += [enc(x, 3) for x in qu.reshape(-1)]
            totals['quads'] += len(corners) == 4
            ref_uv.append(uv)
        totals['parts'] += len(parts); totals['tris'] += len(lst)
        gs = ''.join(s)
        if (totals['groups'] % 10) == 0:
            check.append({'unit': len(units_lua) + 1, 'group': len(groups) + 1, 'v': Vg.round(4).tolist(), 'corners': [[seen_v[v] for v in cr] for cr, _, _ in parts],
                          'f': [int(FD[p]) for _, _, p in parts], 'a': [float(piece_area[p]) for _, _, p in parts], 'uv': [x.reshape(-1).round(5).tolist() for x in ref_uv]})
        groups.append('{%.3f,%.3f,%.3f,%.3f,%.1f,%d,"%s"}' % (ax[0], ax[1], ax[2], sa, float(pa[lst].sum()), len(parts), gs))
        totals['groups'] += 1
    units_lua.append('{%.2f,%.2f,%.2f,%.1f,%d,{%s}}' % (c[0], c[1], c[2], r, 1 if st[m[0]] else 0, ','.join(groups)))
    totals['units'] += 1
os.makedirs(OUT, exist_ok=True)
addon = os.path.basename(OUT.rstrip('/'))
xs = [float(l.split(',')[0][1:]) for l in units_lua]; ys = [float(l.split(',')[1]) for l in units_lua]
head = ['-- Generated by pb_city2.py (proof of concept, performance round 1): the game\'s own buildings of %s for GPS3D\'s' % NAME,
        '-- city models (PocModels.lua). A building: {x, y, h, radius, street, groups}; a facing group: {axis x, y, z,',
        '-- sin of its spread (2: drawn from both sides), area, parts, geometry string}. The strings are decoded when a',
        '-- building is first drawn (layout: pb_city2.py).',
        'local _, ns = ...', 'ns.PocCityData = ns.PocCityData or {}',
        'local U = {}', 'ns.PocCityData[%s] = { map = 0, box = { %.1f, %.1f, %.1f, %.1f }, units = U }' % (json.dumps(NAME), min(xs), max(xs), min(ys), max(ys))]
body = []
for i in range(0, len(units_lua), 50):  # (50 buildings per function: Lua 5.1's limit of 2^18 constants per function)
    body.append('do local u = { %s }; for k = 1, #u do U[#U + 1] = u[k] end end' % ', '.join(units_lua[i:i + 50]))
open(os.path.join(OUT, 'City_%s.lua' % NAME), 'w').write('\n'.join(head + body) + '\n')
open(os.path.join(OUT, 'Link.lua'), 'w').write("-- Hands this data addon's namespace to GPS3D (OnDemand.lua): the files after it write into GPS3D's namespace.\nGPS3D_API.LinkData(select(2, ...))\n")
open(os.path.join(OUT, addon + '.toc'), 'w').write('## Interface: 16001\n## Title: GPS 3D data: %s, the game\'s buildings\n## Notes: The game\'s own building models of %s for GPS 3D (proof of concept). Loaded by GPS 3D when its 3D view comes near the city (load on demand).\n## Version: 0.5.0\n## X-License: MIT\n## LoadOnDemand: 1\n## Dependencies: GPS3D\n\nLink.lua\nCity_%s.lua\n' % (NAME, NAME, NAME))
json.dump(check, open('city2_check_%s.json' % ('q' if QUADS else 't'), 'w'))
totals['bytes'] = os.path.getsize(os.path.join(OUT, 'City_%s.lua' % NAME)); totals['merge'] = qstats
totals['box'] = [min(xs), max(xs), min(ys), max(ys)]
print(json.dumps(totals))
