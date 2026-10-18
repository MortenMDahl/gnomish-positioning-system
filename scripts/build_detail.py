"""Turns the building-mesh exports (scripts/browser_export_detail.js) into prototypes/GPS3D/Data/Detail_<map>.lua.

Usage: python scripts/build_detail.py data/detail_0.json [data/detail_rest.json ...] [--out prototypes/GPS3D/Data]

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

B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
BS = 64  # raster steps per block side
PART_BYTES = 6 * 1024 * 1024  # largest data file


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
    out_dir = 'prototypes/GPS3D/Data'
    if '--out' in args:
        i = args.index('--out')
        out_dir = args[i + 1]
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
            with open(os.path.join(out_dir, name), 'w', newline='\n') as f:
                f.write(text)
            written.append((name, len(part), len(text)))
    for name, n, size in written:
        print(f'{name}: {n} tiles, {size / 1024:.0f} KB')
    total = sum(w[2] for w in written)
    print(f'{len(by_map)} maps in {len(written)} files, {len(tiles)} tiles, {n_blocks} blocks, {n_tris} triangles (coarse: {n_low}, far: {n_far}), {total / 1024 / 1024:.2f} MB; all blocks checked')
    # the TOC's Detail lines, rewritten where they were (a new part file is loaded; one no longer made is not)
    toc = os.path.join(out_dir, '..', 'GPS3D.toc')
    if os.path.exists(toc):
        lines = open(toc, encoding='utf-8').read().split('\n')
        is_detail = lambda l: l.startswith('Data\\Detail_') and l.endswith('.lua')
        at = next((i for i, l in enumerate(lines) if is_detail(l)), None)
        if at is None:
            at = next((i for i, l in enumerate(lines) if l.startswith('Data\\Models_') or l == 'GPS3D.lua'), len(lines))
        lines = [l for l in lines if not is_detail(l)]
        lines[at:at] = ['Data\\' + name for name, *_ in written]
        open(toc, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
        print(f'{os.path.normpath(toc)}: {len(written)} Detail lines')
    stale = sorted(set(os.path.basename(f) for f in glob.glob(os.path.join(out_dir, 'Detail_*.lua'))) - {name for name, *_ in written})
    if stale:
        print('not made any more (delete them; the TOC no longer lists them): ' + ', '.join(stale))


if __name__ == '__main__':
    main()
