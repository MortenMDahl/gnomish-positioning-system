"""Turns the model-placement export (scripts/browser_export_models.js) into prototypes/GPS3D_Models/Models_<map>.lua,
the load-on-demand data addon GPS3D's OnDemand.lua loads the first time the 3D view shows the game's models
(props and trees on, or the game's buildings chosen; since 2026-10-22: 8 MB, about 30 ms in Lua 5.1, never
loaded with the default settings).

Usage: python scripts/build_models.py data/models.json [--root prototypes]

Per map, two things (base64 digits, most significant first, as the other data files):
  ns.ModelFiles[map]  the map's models, 15 characters each: FileDataID (5), kind (1: 0 M2, 1 WMO, 2 WMO that is a cave or mine),
                      radius across the ground (3), lowest and highest point (3 + 3; 1/16 yard, +131072),
                      all in model units (yards before the placement's scale).
  ns.Models[map][ty * 64 + tx]  "M1", placement count (3), then 19 characters per placement, biggest
                      first (size = max(radius, half the height) x scale): model index (2, 0-based, into
                      ModelFiles), x from the tile's west edge (3) and y from its north edge going south
                      (3) in 1/64 yard, height (3, 1/16 yard + 131072), yaw, pitch, roll (2 each: angle
                      = v / 4096 x 2 pi - pi) and scale (2: exp((v - 2048) / 256)).
Every placement is decoded again and compared with the export before the file is written (position
within 1/100 yard, angles within 0.1 degree, scale within 0.25 %), and the order checked: biggest
first by the size GPS3D computes from the stored numbers (so it can stop at the first one too small). Placements of models that could not
be read (no size) are left out. GPS3D_Models.toc is rewritten; GPS3D.toc lists no Models file.
"""
import json
import math
import os
import sys

from data_addons import drop_toc_lines, write_addon

ADDON = 'GPS3D_Models'

B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
TILE = 1600 / 3
PLACE_CHARS, MODEL_CHARS = 19, 15
OFF = 131072


def enc(v, n):
    v = int(v)
    assert 0 <= v < 64 ** n, (v, n)
    return ''.join(B64[(v // 64 ** k) % 64] for k in range(n - 1, -1, -1))


def num(s, pos, n):
    v = 0
    for c in s[pos:pos + n]:
        v = v * 64 + VAL[c]
    return v


def ang(a):
    return round((a + math.pi) / (2 * math.pi) * 4096) % 4096


def unang(v):
    return v / 4096 * 2 * math.pi - math.pi


def model_size(m, scale):
    return max(m[2], (m[4] - m[3]) / 2) * scale


def qscale(s):
    return min(4095, max(0, round(math.log(s) * 256) + 2048))


def stored_size(m, scale):
    """The size as GPS3D computes it from the stored (rounded) numbers, which sets the order."""
    r, lo, hi = round(m[2] * 16) / 16, (round(m[3] * 16)) / 16, (round(m[4] * 16)) / 16
    return max(r, (hi - lo) / 2) * math.exp((qscale(scale) - 2048) / 256)


def encode_map(mp):
    models = mp['models']
    assert len(models) <= 4096, len(models)
    files = ''.join(enc(m[0], 5) + enc(m[1], 1) + enc(round(m[2] * 16), 3) + enc(round(m[3] * 16) + OFF, 3) + enc(round(m[4] * 16) + OFF, 3) for m in models)
    tiles, dropped = {}, 0
    for key, pl in mp['tiles'].items():
        tx, ty = map(int, key.split('_'))
        keep = [p for p in pl if model_size(models[p[0]], p[7]) > 0]
        dropped += len(pl) - len(keep)
        keep.sort(key=lambda p: -stored_size(models[p[0]], p[7]))
        out = ['M1', enc(len(keep), 3)]
        for p in keep:
            mi, x, y, h, yaw, pitch, roll, s = p
            lx, ly = (x - tx * TILE) * 64, (-ty * TILE - y) * 64
            lx, ly = min(max(round(lx), 0), 64 * 533 + 21), min(max(round(ly), 0), 64 * 533 + 21)
            out.append(enc(mi, 2) + enc(lx, 3) + enc(ly, 3) + enc(round(h * 16) + OFF, 3) + enc(ang(yaw), 2) + enc(ang(pitch), 2) + enc(ang(roll), 2)
                       + enc(qscale(s), 2))
        if keep:
            tiles[ty * 64 + tx] = ''.join(out)
    return files, tiles, dropped


def angle_diff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def check_map(mp, files, tiles):
    """Decodes everything again and compares it with the export; returns the number of placements checked."""
    models = mp['models']
    assert len(files) == MODEL_CHARS * len(models)
    for i, m in enumerate(models):
        p = i * MODEL_CHARS
        assert num(files, p, 5) == m[0] and num(files, p + 5, 1) == m[1], ('model', i)
        assert abs(num(files, p + 6, 3) / 16 - m[2]) <= 1 / 32 + 1e-9
        assert abs((num(files, p + 9, 3) - OFF) / 16 - m[3]) <= 1 / 32 + 1e-9
        assert abs((num(files, p + 12, 3) - OFF) / 16 - m[4]) <= 1 / 32 + 1e-9
    want = {}
    for key, pl in mp['tiles'].items():
        tx, ty = map(int, key.split('_'))
        want[ty * 64 + tx] = sorted([p for p in pl if model_size(models[p[0]], p[7]) > 0], key=lambda p: -stored_size(models[p[0]], p[7]))
    checked = 0
    for k, s in tiles.items():
        tx, ty = k % 64, k // 64
        assert s[:2] == 'M1'
        n = num(s, 2, 3)
        assert len(s) == 5 + n * PLACE_CHARS, ('length', k)
        exp = want[k]
        assert len(exp) == n
        last = math.inf
        for i in range(n):
            q = 5 + i * PLACE_CHARS
            mi = num(s, q, 2)
            x = tx * TILE + num(s, q + 2, 3) / 64
            y = -ty * TILE - num(s, q + 5, 3) / 64
            h = (num(s, q + 8, 3) - OFF) / 16
            yaw, pitch, roll = unang(num(s, q + 11, 2)), unang(num(s, q + 13, 2)), unang(num(s, q + 15, 2))
            sc = math.exp((num(s, q + 17, 2) - 2048) / 256)
            e = exp[i]
            assert mi == e[0], ('model', k, i)
            assert abs(x - e[1]) < 0.01 and abs(y - e[2]) < 0.01 and abs(h - e[3]) < 0.04, ('position', k, i, (x, y, h), e[1:4])
            for a, b in ((yaw, e[4]), (pitch, e[5]), (roll, e[6])):
                assert angle_diff(a, b) < math.radians(0.1), ('angle', k, i, a, b)
            assert abs(sc / e[7] - 1) < 0.0025, ('scale', k, i, sc, e[7])
            size = stored_size(models[mi], e[7])
            assert size <= last, ('order', k, i)  # biggest first, as GPS3D computes the size
            last = size
            checked += 1
    return checked


def main(argv):
    root = 'prototypes'  # the addon folders: GPS3D and its data addons
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == '--root':
            root = argv[i + 1]; i += 2
        else:
            args.append(argv[i]); i += 1
    out = os.path.join(root, ADDON)
    os.makedirs(out, exist_ok=True)
    data = json.load(open(args[0]))
    stamp = data.get('exportedAt', '?')
    build = data.get('build', '?')
    names = []
    total = total_dropped = total_caves = 0
    for mid in sorted(data['maps'], key=int):
        mp = data['maps'][mid]
        files, tiles, dropped = encode_map(mp)
        checked = check_map(mp, files, tiles)
        total += checked
        total_dropped += dropped
        caves = sum(1 for pl in mp['tiles'].values() for p in pl if mp['models'][p[0]][1] == 2 and model_size(mp['models'][p[0]], p[7]) > 0)
        total_caves += caves
        name = f'Models_{mid}.lua'
        lines = [
            f'-- Generated by scripts/build_models.py from the model-placement export ({stamp}, game build {build}); do not edit.',
            f'-- Map {mid} ({mp["name"]}): {len(mp["models"])} models, {checked} placements on {len(tiles)} tiles (format: see build_models.py and GPS3D.lua, Models).',
            'local _, ns = ...',
            'ns.ModelFiles, ns.Models = ns.ModelFiles or {}, ns.Models or {}',
            f'ns.ModelFiles[{mid}] = "{files}"',
            f'local t = {{}}; ns.Models[{mid}] = t',
        ]
        for k in sorted(tiles):
            lines.append(f't[{k}]="{tiles[k]}"')
        text = '\n'.join(lines) + '\n'
        assert len(text) <= 6 * 1024 * 1024, (name, len(text))
        with open(os.path.join(out, name), 'w', newline='\n') as f:
            f.write(text)
        names.append(name)
        print(f'{name}: {checked} placements ({caves} caves and mines; {dropped} without a size left out), {len(mp["models"])} models, {len(tiles)} tiles, {len(text) / 1e6:.2f} MB')
    print(f'total: {total} placements checked and written ({total_caves} caves and mines), {total_dropped} left out, {len(names)} files')
    write_addon(root, ADDON, 'the game\'s models', 'Where the game\'s props, trees and buildings stand on every map (GPS 3D\'s models).', names)
    toc = drop_toc_lines(root, 'Data\\Models_')  # (GPS3D.toc listed them until 2026-10-22)
    print(f'{os.path.join(out, ADDON + ".toc")}: {len(names)} files; {toc}: no Models lines')


if __name__ == '__main__':
    main(sys.argv[1:])
