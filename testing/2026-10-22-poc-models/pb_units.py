# Whole buildings with facing groups (2026-10-23), as addon data (PocCity.lua): each building (or street cell) is a
# unit; its parts are grouped by which way they face (up, down, 8 compass sectors; parts drawn from both sides in a
# group of their own); a group facing away from the camera is skipped whole. In each group: parts biggest piece first,
# vertices in first-use order (the size floor takes a prefix). Each unit is its own function (Lua 5.1 constant limit).
import os, sys, json, numpy as np
os.environ['RANK'] = 'value'; os.environ.setdefault('VISTAG', 'pbvw')
src = open('pb_city.py').read(); exec(compile(src[:src.index('cells = {}')], 'pb_city_part', 'exec'))
z = np.load('pb_buildings.npz'); bld, st = z['bld'], z['street']
assert len(bld) == len(T2)
nrm = np.cross(V[T2[:, 1]] - V[T2[:, 0]], V[T2[:, 2]] - V[T2[:, 0]]); pa = np.linalg.norm(nrm, axis=1) / 2; nrm /= np.maximum(2 * pa[:, None], 1e-9)
sector = (np.floor((np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) + 360 + 22.5) / 45).astype(int) % 8) + 2
grp = np.where(BF == 1, 0, np.where(nrm[:, 2] > 0.8, 1, np.where(nrm[:, 2] < -0.8, 10, sector)))   # 0 both, 1 up, 2-9 sectors, 10 down
pparea = np.bincount(PC, weights=area if False else np.ones(len(PC)))  # (unused)
piece_area = parea[PC]                                   # each part's whole piece area (the size floor)
f = lambda a, fmt: ','.join(fmt % x for x in a)
out = ["-- Proof of concept data (branch poc-models): the game's own building models over the exported Stormwind square,",
       '-- as whole buildings with their parts grouped by facing (PocModels.lua, /gps3d poc city)', 'local _, ns = ...',
       'ns.PocCity = { map = 0, units = {} }', 'local U = ns.PocCity.units']
ngroups, nunits, gsizes = 0, 0, []
for u in np.unique(bld):
    m = np.nonzero(bld == u)[0]
    Vu = V[T2[m]].reshape(-1, 3); lo, hi = Vu.min(0), Vu.max(0); c = (lo + hi) / 2; r = float(np.linalg.norm(Vu - c, axis=1).max())
    groups = []
    for gi in np.unique(grp[m]):
        lst = m[grp[m] == gi]
        lst = lst[np.lexsort((PC[lst], -piece_area[lst]))]
        if gi == 0: ax, sa = (0.0, 0.0, 1.0), 2.0                  # (both sides: always)
        else:
            w = pa[lst][:, None]; axv = (nrm[lst] * w).sum(0); axv /= max(np.linalg.norm(axv), 1e-9)
            ang = np.arccos(np.clip(nrm[lst] @ axv, -1, 1)).max(); ax, sa = tuple(axv), float(np.sin(min(ang, np.pi / 2)))
        tri = T2[lst]; order, seen_v = [], {}
        for t in tri.reshape(-1):
            if t not in seen_v: seen_v[t] = len(order) + 1; order.append(t)
        tl = np.vectorize(seen_v.get)(tri)
        groups.append('{ ax = %.3f, ay = %.3f, az = %.3f, sa = %.3f, A = %.1f, v = {%s}, t = {%s}, uv = {%s}, f = {%s}, a = {%s} }' % (
            ax[0], ax[1], ax[2], sa, float(pa[lst].sum()), f(V[order].reshape(-1), '%.2f'), f(tl.reshape(-1), '%d'), f(UVc[lst].reshape(-1), '%.4f'), f(FD[lst], '%d'), f(piece_area[lst], '%.1f')))
        gsizes.append(len(lst))
    out.append('U[#U + 1] = (function() return { x = %.1f, y = %.1f, h = %.1f, r = %.1f, street = %s, g = { %s } } end)()' % (c[0], c[1], c[2], r, 'true' if st[m[0]] else 'false', ', '.join(groups)))
    ngroups += len(groups); nunits += 1
path = os.environ.get('OUT', '/home/claude/wt/poc/prototypes/GPS3D/PocCity.lua')
open(path, 'w').write('\n'.join(out) + '\n')
print(json.dumps({'units': nunits, 'groups': ngroups, 'parts': int(len(T2)), 'parts_both_sides': int((grp == 0).sum()), 'parts_per_group_median': float(np.median(gsizes)), 'lua_bytes': os.path.getsize(path)}))
