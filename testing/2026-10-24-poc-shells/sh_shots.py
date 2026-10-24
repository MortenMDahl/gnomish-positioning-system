# Textured shell renders at the four views, each at its level (90: L0, 200: L1, 420 and 2,000: L2), beside the game
import json, sys
sys.path.insert(0, '.')
from sh_tview import shell_groups, VIEWS
for L in (0, 1, 2): json.dump(shell_groups(L), open(f'shtv_l{L}.json', 'w'))
pick = {'v90': 0, 'v200': 1, 'v420': 2, 'v2000': 2}
json.dump([{'m': f'shtv_l{L}.json', 'cam': VIEWS[v], 'out': f'shtv_{v}_l{L}.png', 'cull': 1, 'page': 'sh_tview.html'} for v, L in pick.items()], open('shtv_jobs4.json', 'w'))
