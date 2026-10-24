# All buildings, phase 1 (S1e, 2026-10-24): every tile's whole-block shells (ab_tile.py) into one data addon per map
# (GPS3D_Shells<map>, load on demand): the pictures repacked from the tiles' own pages into shared 2,048 x 2,048 pages
# (tiles in Hilbert order, so a page holds one part of the map), and per tile its blocks as strings in the layout of
# sh_tolua.py. Per block also its 66.7-yd grid square (bx, by), so the old simplified blocks there give way.
# Usage: python3 ab_collect.py <work root> <addons dir> <sandbox site dir> [maps]
import sys, os, json, pickle, numpy as np
from PIL import Image
ROOT, OUT, SITE = sys.argv[1], sys.argv[2], sys.argv[3]
MAPS = [int(m) for m in sys.argv[4].split(',')] if len(sys.argv) > 4 else [0, 1]
PAGE, PAD, TILE = 2048, 2, 1600 / 3
BLK = TILE / 8
B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
def enc(v, n):
    v = int(v); assert 0 <= v < 64 ** n, (v, n)
    return ''.join(B64[(v >> (6 * (n - 1 - i))) & 63] for i in range(n))
def hilbert(n, x, y):
    d, s_ = 0, n // 2
    while s_ > 0:
        rx = 1 if (x & s_) > 0 else 0; ry = 1 if (y & s_) > 0 else 0
        d += s_ * s_ * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1: x, y = s_ - 1 - x, s_ - 1 - y
            x, y = y, x
        s_ //= 2
    return d
def level_string(fl, c, pw):
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
        out.append(enc(f['page'], pw))
        tc = np.clip(np.round(f['tc'] * 4095), 0, 4095).astype(int)
        out += [enc(x, 2) for x in tc.reshape(-1)]
    return ''.join(out)
summary = {}
for M in MAPS:
    tiles = sorted(d for d in os.listdir(ROOT) if d.startswith(f'{M}_') and os.path.exists(os.path.join(ROOT, d, 'sh_faces_4.pkl')))
    tiles += sorted(d + '/b' for d in os.listdir(ROOT) if d.startswith(f'{M}_') and os.path.exists(os.path.join(ROOT, d, 'b', 'sh_faces_4.pkl')))   # (S1f: lower layers)
    if not tiles: continue
    # every picture of every tile, with its pixels (padding included)
    pics = []; tdata = {}
    for k in tiles:
        _, tx, ty = (int(v) for v in k.split('/')[0].split('_'))
        S = pickle.load(open(os.path.join(ROOT, k, 'sh_faces_4.pkl'), 'rb'))
        pages = [np.asarray(Image.open(os.path.join(ROOT, k, 'pages', f'L4_{i}.png')).convert('RGB')) for i in range(S['npages'])]
        base = len(pics)
        for p in S['pics']:
            x, y, w, h = p['x'], p['y'], p['w'], p['h']
            img = pages[p['page']][max(0, y - PAD):y + h + PAD, max(0, x - PAD):x + w + PAD]
            pics.append(dict(tile=k, hk=hilbert(64, tx, ty), w=w, h=h, img=img, ox=x, oy=y, op=p['page']))
        tdata[k] = (S, base)
    # pack: shelves, page by page, tiles in Hilbert order (a page's worth at a time, tallest first within it)
    seq = sorted(range(len(pics)), key=lambda i: (pics[i]['hk'], pics[i]['tile']))
    page, kk, carry = 0, 0, []
    while kk < len(seq) or carry:
        grp, area = list(carry), sum((pics[i]['w'] + 2 * PAD) * (pics[i]['h'] + 2 * PAD) for i in carry)
        while kk < len(seq) and area < PAGE * PAGE * 0.85:
            i = seq[kk]; grp.append(i); area += (pics[i]['w'] + 2 * PAD) * (pics[i]['h'] + 2 * PAD); kk += 1
        x = y = sh = 0; rest = []
        for i in sorted(grp, key=lambda i: (-pics[i]['h'], -pics[i]['w'])):
            p = pics[i]; Wd, Hd = p['w'] + 2 * PAD, p['h'] + 2 * PAD
            if x + Wd > PAGE: x, y, sh = 0, y + sh, 0
            if y + Hd > PAGE: rest.append(i); continue
            p['page'], p['x'], p['y'] = page, x + PAD, y + PAD
            x += Wd; sh = max(sh, Hd)
        if len(rest) == len(grp): raise SystemExit('a picture does not fit an empty page')
        carry = rest
        if carry or kk < len(seq): page += 1
    npages = page + 1
    pw = 1 if npages <= 64 else 2
    imgs = [np.zeros((PAGE, PAGE, 3), np.uint8) for _ in range(npages)]
    used = [np.zeros((PAGE, PAGE), bool) for _ in range(npages)]
    for p in pics:
        im = p['img']; y0, x0 = p['y'] - PAD, p['x'] - PAD
        # (a picture at its tile page's edge has less padding: placed by its own top-left)
        dy, dx = min(PAD, p['oy']), min(PAD, p['ox'])
        y0, x0 = p['y'] - dy, p['x'] - dx
        hh, ww = min(im.shape[0], PAGE - y0), min(im.shape[1], PAGE - x0)
        imgs[p['page']][y0:y0 + hh, x0:x0 + ww] = im[:hh, :ww]; used[p['page']][y0:y0 + hh, x0:x0 + ww] = True
    from scipy import ndimage
    for im, u in zip(imgs, used):
        if u.any() and not u.all():
            _, (ii, jj) = ndimage.distance_transform_edt(~u, return_indices=True); im[:] = im[ii, jj]
    addon = f'GPS3D_Shells{M}'
    adir = os.path.join(OUT, addon); os.makedirs(os.path.join(adir, 'Shells'), exist_ok=True)
    sdir = os.path.join(SITE, 'shells'); os.makedirs(sdir, exist_ok=True)
    jbytes = 0
    for i, im in enumerate(imgs):
        Image.fromarray(im).save(os.path.join(adir, 'Shells', f'T{M}_{i}.jpg'), quality=88, optimize=True)
        Image.fromarray(im).save(os.path.join(sdir, f'T{M}_{i}.JPG'.replace('.JPG', '.jpg')), quality=88, optimize=True)
        jbytes += os.path.getsize(os.path.join(adir, 'Shells', f'T{M}_{i}.jpg'))
    # blocks per tile
    lines = ['-- Generated by ab_collect.py (proof of concept S1e, branch poc-shells): every building of this map as whole',
             '-- 66.7-yd block shells with baked pictures (phase 1 of ALL_BUILDINGS.md). Per tile: blocks { x, y, h, radius,',
             '-- grid square bx, by, string } (string layout: sh_tolua.py; page index %d character(s)). Pictures: Shells\\T<map>_<page>.jpg.' % pw,
             'local _, ns = ...', 'ns.ShellTiles = ns.ShellTiles or {}',
             'local T = {}',
             'ns.ShellTiles[%d] = { tiles = T, pages = %d, pw = %d, path = "Interface\\\\AddOns\\\\%s\\\\Shells\\\\T%%d_%%d.jpg" }' % (M, npages, pw, addon)]
    nblocks = nfaces = 0
    tent = {}
    for k in tiles:
        S, base = tdata[k]
        _, tx, ty = (int(v) for v in k.split('/')[0].split('_'))
        by_unit = {}
        for f in S['faces']:
            p = pics[base + f['pic']]
            tc = f['tc'].copy()
            tc[:, 0] += (p['x'] - p['ox']) / PAGE; tc[:, 1] += (p['y'] - p['oy']) / PAGE
            by_unit.setdefault(f['unit'], []).append(dict(c=f['c'], tc=tc, page=p['page']))
        ents = []
        for unit, fl in sorted(by_unit.items()):
            blk = -2 - unit; bx, by = blk // 1000 + 230, blk % 1000
            if by >= 500: bx += 1; by -= 1000   # (python's floor division of a negative by part)
            by += 300
            P = np.vstack([f['c'] for f in fl]); lo, hi = P.min(0), P.max(0); c = np.round((lo + hi) / 2 * 32) / 32
            r = float(np.linalg.norm(P - c, axis=1).max())
            ents.append('{%.3f,%.3f,%.3f,%.1f,%d,%d,"%s"}' % (c[0], c[1], c[2], r, bx, by, level_string(fl, c, pw)))
            nblocks += 1; nfaces += len(fl)
        tent.setdefault(ty * 64 + tx, []).extend(ents)
    for tk_, ents in sorted(tent.items()):
        lines.append('T[%d] = { %s }' % (tk_, ', '.join(ents)))
    open(os.path.join(adir, f'Shells_{M}.lua'), 'w').write('\n'.join(lines) + '\n')
    open(os.path.join(adir, 'Link.lua'), 'w').write('-- Hands this data addon\'s namespace to GPS3D (OnDemand.lua): the files after it write into GPS3D\'s namespace.\nGPS3D_API.LinkData(select(2, ...))\n')
    name = {0: 'Eastern Kingdoms', 1: 'Kalimdor'}.get(M, f'map {M}')
    open(os.path.join(adir, addon + '.toc'), 'w').write(f'''## Interface: 16001
## Title: GPS 3D data: {name}, building shells
## Notes: Every building of {name} as whole-block shells with pictures of the real buildings (GPS 3D proof of concept). Loaded by GPS 3D when its 3D view is on {name} with shells on (load on demand).
## Version: 0.7.0
## X-License: MIT
## LoadOnDemand: 1
## Dependencies: GPS3D

Link.lua
Shells_{M}.lua
''')
    summary[M] = dict(tiles=len(tiles), blocks=nblocks, faces=nfaces, pictures=len(pics), pages=npages, jpeg_bytes=jbytes, lua_bytes=os.path.getsize(os.path.join(adir, f'Shells_{M}.lua')))
    print(M, json.dumps(summary[M]), flush=True)
print('COLLECT', json.dumps(summary))
