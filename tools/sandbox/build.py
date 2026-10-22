# Writes site/index.html from index.src.html: the addons' file lists from their TOCs (also written back into
# index.src.html) (site/addons/*/*.toc; GPS3D's
# load-on-demand data addons marked lod, since 2026-10-22), and the patched Fengari inlined.
import glob, json, os, re
H = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(H, 'index.src.html')).read()


def addon(name):
    text = open(os.path.join(H, 'site', 'addons', name, name + '.toc'), encoding='utf-8').read()
    files = [l.strip().replace('\\', '/') for l in text.splitlines() if l.strip() and not l.startswith('#')]
    entry = {'name': name, 'files': files}
    saved = re.search(r'^## SavedVariables: *(.+)$', text, re.M)
    if saved: entry['saved'] = ','.join(v.strip() for v in saved.group(1).split(','))
    if re.search(r'^## LoadOnDemand: *1', text, re.M): entry['lod'] = True
    return entry


names = ['GnomishPositioningSystem', 'GPS3D'] + sorted(os.path.basename(d) for d in glob.glob(os.path.join(H, 'site', 'addons', 'GPS3D_*')))
lines = ',\n'.join('  ' + json.dumps(addon(n), separators=(', ', ': ')) for n in names)
s = re.sub(r'(// ADDONS-BEGIN\n)const ADDONS = \[\n.*?\n\];\n(// ADDONS-END)', lambda m: m.group(1) + 'const ADDONS = [\n' + lines + ',\n];\n' + m.group(2), s, flags=re.S)
open(os.path.join(H, 'index.src.html'), 'w').write(s)  # (the list kept in the source too, as built)
f = open(os.path.join(H, 'site/wasmoon/fengari-web-csp.js')).read()
s = s.replace('<!--FENGARI-->', '<script>/* Fengari 0.1.4 (fengari-web), MIT licence, https://fengari.io. Two Function() calls replaced so it runs without eval. Used only when WebAssembly is not allowed. */\n' + f + '\n</script>')
open(os.path.join(H, 'site/index.html'), 'w').write(s)
print('built', len(s), 'addons:', ', '.join(n + (' (on demand)' if addon(n).get('lod') else '') for n in names))
