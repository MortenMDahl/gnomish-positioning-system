"""Merges a fresh building-mesh export (scripts/export_detail_node.ts) into an existing one (data/detail_*.json).

Usage: python scripts/merge_detail.py data/detail_0.json new.json [--all] [--out merged.json]

By default only the tiles where the new export drew caves and mines differently (its "underground" and
"undergroundWhole" lists, see scripts/browser_underground.js) are taken from it: replaced when the tile still has buildings, removed
when it no longer has any. Every other tile keeps its old strings, so a merge changes nothing but the
caves. --all takes every tile the new export visited. Writes the result over the old file unless --out
is given, and prints what changed.
"""
import json
import sys


def main(argv):
    take_all = '--all' in argv
    argv = [a for a in argv if a != '--all']
    out = None
    if '--out' in argv:
        i = argv.index('--out')
        out = argv[i + 1]
        del argv[i:i + 2]
    old_path, new_path = argv
    old, new = json.load(open(old_path)), json.load(open(new_path))
    keys = set(new.get('visited') or new['tiles']) if take_all else set(new.get('underground', {})) | set(new.get('undergroundWhole', {}))
    # only tiles of the maps the old file holds
    maps = {k.split('_')[0] for k in old['tiles']}
    keys = {k for k in keys if k.split('_')[0] in maps}
    stats = {s['key']: s for s in old['stats']}
    new_stats = {s['key']: s for s in new['stats']}
    replaced = removed = added = 0
    for k in sorted(keys):
        if k in new['tiles']:
            if k in old['tiles']:
                replaced += 1
            else:
                added += 1
            for f in ('tiles', 'low', 'far'):
                old[f][k] = new[f][k]
            stats[k] = new_stats[k]
        elif k in old['tiles']:
            removed += 1
            for f in ('tiles', 'low', 'far'):
                del old[f][k]
            stats.pop(k, None)
    order = [s['key'] for s in old['stats'] if s['key'] in stats]
    order += [k for k in stats if k not in set(order)]
    old['stats'] = [stats[k] for k in order]
    old.setdefault('merges', []).append({'from': new.get('exportedAt'), 'build': new.get('build'), 'tiles': len(keys), 'replaced': replaced, 'removed': removed, 'added': added, 'all': take_all})
    if not take_all:
        for field in ('underground', 'undergroundWhole'):
            und = old.setdefault(field, {})
            for k in keys:
                if k in new.get(field, {}):
                    und[k] = new[field][k]
                else:
                    und.pop(k, None)
    assert set(old['tiles']) == set(old['low']) == set(old['far']) == set(stats), 'tiles, low, far and stats disagree'
    json.dump(old, open(out or old_path, 'w'))
    print(f'{old_path}: {len(keys)} tiles from {new_path}: {replaced} replaced, {removed} removed, {added} added; {len(old["tiles"])} tiles now')


if __name__ == '__main__':
    main(sys.argv[1:])
