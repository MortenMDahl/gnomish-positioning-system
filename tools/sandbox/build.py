import os
H = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(H, 'index.src.html')).read()
f = open(os.path.join(H, 'site/wasmoon/fengari-web-csp.js')).read()
s = s.replace('<!--FENGARI-->', '<script>/* Fengari 0.1.4 (fengari-web), MIT licence, https://fengari.io. Two Function() calls replaced so it runs without eval. Used only when WebAssembly is not allowed. */\n' + f + '\n</script>')
open(os.path.join(H, 'site/index.html'), 'w').write(s)
print('built', len(s))
