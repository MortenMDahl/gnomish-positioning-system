"""Turns the building-mesh exports (scripts/browser_export_detail.js) into the load-on-demand data addons
prototypes/GPS3D_EK1..4, GPS3D_Kalimdor1..3 and GPS3D_Instances (Detail_<map>[_<part>].lua each), and
prototypes/GPS3D/Data/DetailParts.lua, the index GPS3D's OnDemand.lua loads them by (since 2026-10-22).

Usage: python scripts/build_detail.py data/detail_0.json [data/detail_rest.json ...] [--root prototypes]

Files of at most 6 MB (PART_BYTES), cut in tile order (rows of tiles, north to south): a map in several files
(the Eastern Kingdoms, Kalimdor) has one data addon per file, the maps in one file each (dungeons, raids,
battlegrounds) share GPS3D_Instances. Measured in Lua 5.1, one 6 MB file parses in about 25 ms, the
instances' 10.5 MB in about 40 ms: the hitch when the 3D view first comes within a tile of a part.

Each export holds three strings per tile with buildings ("D2" format, described in browser_export_detail.js
and GPS3D.lua): the fine meshes (ns.Detail), and coarser ones for blocks further away (ns.DetailLow,
vertices every 4 steps; ns.DetailFar, every 8 steps). Every string is decoded here and checked before
it is written: the block headers must add up to the string's length, every triangle corner must be a
vertex of its block, every vertex must lie in its block (and on its level's grid), and each block's
triangles must cover the block exactly once (areas add up to 64 x 64 steps) with one winding. Prints
sizes and the TOC lines.
"""
import glob
import json
import os
import sys

from data_addons import drop_toc_lines, write_addon

B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
BS = 64  # raster steps per block side
PART_BYTES = 6 * 1024 * 1024  # largest data file
CONTINENTS = {0: ('GPS3D_EK', 'Eastern Kingdoms', 'the Eastern Kingdoms'), 1: ('GPS3D_Kalimdor', 'Kalimdor', 'Kalimdor')}  # maps in several parts: an addon each
INSTANCES = 'GPS3D_Instances'  # maps in one part: together


def num(s, pos, n):
    v = 0
    for c in s[pos:pos + n]:
        v = v * 64 + VAL[c]
    return v


def decode_tile(s):
    """Returns {block index: (base, vertices [(x, y, height, colour)], palette, triangles [(a, b, c)])}."""
    assert s[:2] == 'D2', s[:8]
    blocks, pos = {}, 4
    for _ in range(num(s, 2, 2)):
        bi = num(s, pos, 1)
        base = (num(s, pos + 1, 3) - 131072) * 0.25
        nv, nt, npal = num(s, pos + 4, 3), num(s, pos + 7, 3), num(s, pos + 10, 1)
        p = pos + 11
        pal = [(num(s, p + 3 * k, 1) / 63, num(s, p + 3 * k + 1, 1) / 63, num(s, p + 3 * k + 2, 1) / 63) for k in range(npal)]
        p += 3 * npal
        verts = []
        for _ in range(nv):
            v = num(s, p, 6)
            col, v = v % 64, v // 64
            dh, v = v % 65536, v // 65536
            verts.append((v // 128, v % 128, base + dh * 0.25, col))
            p += 6
        iw = 3 if nv > 4095 else 2
        tris = []
        for _ in range(nt):
            tris.append(tuple(num(s, p + iw * k, iw) for k in range(3)))
            p += 3 * iw
        assert bi not in blocks, ('block twice', bi)
        blocks[bi] = (base, verts, pal, tris)
        pos = p
    assert pos == len(s), ('length', pos, len(s))
    return blocks


def check_block(verts, pal, tris):
    area, wind = 0.0, set()
    for x, y, h, col in verts:
        assert 0 <= x <= BS and 0 <= y <= BS, (x, y)
        assert col <= len(pal), (col, len(pal))
    for a, b, c in tris:
        assert max(a, b, c) < len(verts)
        (ax, ay, *_), (bx, by, *_), (cx, cy, *_) = verts[a], verts[b], verts[c]
        cross = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        wind.add(cross < 0)
        area += abs(cross) / 2
    assert wind == {True}, 'winding'
    assert abs(area - BS * BS) < 1e-6, ('area', area)


def main():
    args = sys.argv[1:]
    root = 'prototypes'  # the addon folders: GPS3D and its data addons
    if '--root' in args:
        i = args.index('--root')
        root = args[i + 1]
        del args[i:i + 2]
    srcs = args or ['data/detail_0.json', 'data/detail_rest.json']
    tiles, lows, fars, stamps = {}, {}, {}, []
    for src in srcs:
        data = json.load(open(src))
        stamps.append(data.get('exportedAt', '?'))
        assert not data.get('errors'), data['errors'][:5]
        for key, s in data['tiles'].items():
            assert key not in tiles, ('tile twice', key)
            tiles[key] = s
            lows[key] = data['low'][key]
            fars[key] = data['far'][key]
    by_map = {}
    n_blocks = n_tris = n_low = n_far = 0
    for key, s in tiles.items():
        m, x, y = (int(v) for v in key.split('_'))
        blocks = decode_tile(s)
        for _, verts, pal, tris in blocks.values():
            check_block(verts, pal, tris)
            n_tris += len(tris)
        for level, grid in ((lows, 4), (fars, 8)):
            lv = decode_tile(level[key])
            assert sorted(lv) == sorted(blocks), ('coarser blocks differ', key)
            for _, verts, pal, tris in lv.values():
                check_block(verts, pal, tris)
                assert all(v[0] % grid == 0 and v[1] % grid == 0 for v in verts), 'vertex off its grid'
                if grid == 4: n_low += len(tris)
                else: n_far += len(tris)
        n_blocks += len(blocks)
        by_map.setdefault(m, []).append((y * 64 + x, s, len(blocks), lows[key], fars[key]))
    written = []
    addons = {}  # addon -> (title, notes, files)
    index = {}  # map -> ([addon, ...], {tile key: addon's number}, {tile key: highest point of its buildings})
    for m in sorted(by_map):
        rows = sorted(by_map[m])
        # files of at most PART_BYTES (smaller files load in steps and fit hosting limits)
        parts, cur, size = [], [], 0
        for r in rows:
            if cur and size + len(r[1]) + len(r[3]) + len(r[4]) > PART_BYTES:
                parts.append(cur)
                cur, size = [], 0
            cur.append(r)
            size += len(r[1]) + len(r[3]) + len(r[4]) + 36
        parts.append(cur)
        for k, part in enumerate(parts, 1):
            name = f'Detail_{m}.lua' if len(parts) == 1 else f'Detail_{m}_{k}.lua'
            if len(parts) == 1:
                addon = INSTANCES
                addons.setdefault(addon, ['dungeons, raids, battlegrounds', 'Buildings of the dungeons, raids and battlegrounds (maps ', []])
                addons[addon][1] += ('' if addons[addon][1].endswith(' ') else ', ') + str(m)
            else:
                prefix, land, the_land = CONTINENTS.get(m, (f'GPS3D_Map{m}_', f'map {m}', f'map {m}'))
                addon = f'{prefix}{k}'
                rows = sorted({r[0] // 64 for r in part})
                addons[addon] = [f'{land}, buildings {k} of {len(parts)}', f'Buildings of {the_land}, tile rows {rows[0]} to {rows[-1]} (part {k} of {len(parts)}).', []]
            addons[addon][2].append(name)
            names, keys, tops = index.setdefault(m, ([], {}, {}))
            if addon not in names:
                names.append(addon)
            for r in part:
                keys[r[0]] = names.index(addon) + 1
                # the highest point of the tile's buildings (fine level), as GPS3D.lua's TileTop worked it out from
                # the string: per block its base, raised by its highest vertex (multiples of 0.25 yd: exact)
                tops[r[0]] = max(max([b[0]] + [v[2] for v in b[1]]) for b in decode_tile(r[1]).values())
            lines = [
                f'-- Generated by scripts/build_detail.py from the building-mesh export ({", ".join(stamps)}); do not edit.',
                f'-- Map {m}' + (f', part {k} of {len(parts)}' if len(parts) > 1 else '') + f': {len(part)} tiles with buildings, {sum(r[2] for r in part)} blocks of 66.7 yards (format: see GPS3D.lua, Buildings).',
                'local _, ns = ...',
                'ns.Detail, ns.DetailLow, ns.DetailFar = ns.Detail or {}, ns.DetailLow or {}, ns.DetailFar or {}',
                f'ns.Detail[{m}], ns.DetailLow[{m}], ns.DetailFar[{m}] = ns.Detail[{m}] or {{}}, ns.DetailLow[{m}] or {{}}, ns.DetailFar[{m}] or {{}}',
                f'local t, l, f = ns.Detail[{m}], ns.DetailLow[{m}], ns.DetailFar[{m}]',
            ]
            for key, s, _, low, far in part:
                lines += [f't[{key}]="{s}"', f'l[{key}]="{low}"', f'f[{key}]="{far}"']
            text = '\n'.join(lines) + '\n'
            os.makedirs(os.path.join(root, addon), exist_ok=True)
            with open(os.path.join(root, addon, name), 'w', newline='\n') as f:
                f.write(text)
            written.append((name, len(part), len(text)))
    for name, n, size in written:
        print(f'{name}: {n} tiles, {size / 1024:.0f} KB')
    total = sum(w[2] for w in written)
    print(f'{len(by_map)} maps in {len(written)} files, {len(tiles)} tiles, {n_blocks} blocks, {n_tris} triangles (coarse: {n_low}, far: {n_far}), {total / 1024 / 1024:.2f} MB; all blocks checked')
    # the data addons' TOCs (and Link.lua), and the index OnDemand.lua loads them by
    for addon, (title, notes, files) in addons.items():
        if addon == INSTANCES:
            notes += ').'
        write_addon(root, addon, title, notes, files)
        print(f'{addon}: {", ".join(files)}')
    lines = [
        '-- Generated by scripts/build_detail.py; do not edit.',
        '-- Which load-on-demand data addon holds the buildings of which tile (OnDemand.lua loads one when the 3D view comes',
        '-- within a tile of its tiles): per map the addons, per tile with buildings (ty * 64 + tx) its addon\'s number, and',
        '-- the highest point of its buildings in yards (GPS3D.lua\'s TileTop: the camera\'s ground checks, without the data).',
        'local _, ns = ...',
        'ns.DetailParts = {',
    ]
    for m in sorted(index):
        names, keys, tops = index[m]
        lines.append(f'[{m}] = {{ {", ".join(chr(34) + n + chr(34) for n in names)},')
        lines.append('\ttiles = { ' + ','.join(f'[{k}]={keys[k]}' for k in sorted(keys)) + ' },')
        lines.append('\ttops = { ' + ','.join(f'[{k}]={tops[k]!r}' for k in sorted(tops)) + ' } },')
    lines.append('}')
    parts_path = os.path.join(root, 'GPS3D', 'Data', 'DetailParts.lua')
    with open(parts_path, 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'{os.path.normpath(parts_path)}: {sum(len(k) for _, k, _ in index.values())} tiles in {len(addons)} data addons')
    # GPS3D.toc lists the index (where its Detail lines were until 2026-10-22), not the data files
    toc = drop_toc_lines(root, 'Data\\Detail_', 'Data\\DetailParts.lua', 'GPS3D.lua')
    print(f'{os.path.normpath(toc)}: lists Data\\DetailParts.lua')
    made = {name for name, *_ in written}
    stale = sorted(os.path.relpath(f, root) for f in glob.glob(os.path.join(root, 'GPS3D*', '**', 'Detail_*.lua'), recursive=True)
                   if os.path.basename(f) not in made or os.path.basename(os.path.dirname(f)) not in addons)
    if stale:
        print('not made any more (delete them; no TOC lists them): ' + ', '.join(stale))

if __name__ == '__main__':
    main()
