# Shards: of the parts drawn, how many belong to a piece (roof slope, wall face, beam side) that is only partly drawn
# (some of its parts in on-screen cells dropped; parts off screen do not count). Triangle version vs piece version, same views and budgets.
import os, sys, shutil, json
SP = '/tmp/claude-0/-home-claude/02c73231-da1f-5c67-9fe6-c007a09f80c0/scratchpad/poc'
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
VIEWS = {'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62)}
res = {}
for ver in ('tri', 'value'):
    shutil.copy(f'{SP}/PocCity_{ver}.lua', 'site/addons/GPS3D/PocCity.lua')
    g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
    g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
    G.SlashCmdList.GPS3D('detail off'); G.SlashCmdList.GPS3D('poc city'); G.SlashCmdList.GPS3D('poc min 0'); G.SlashCmdList.GPS3D('poc radius 400')
    count = L.eval('''function(ns)
      local total, drawn, nd = {}, {}, 0
      local fr = ns.poc.city.cells[1] and 0; for _, m in ipairs(ns.poc.city.cells) do fr = math.max(fr, m.seen or 0) end
      for _, m in ipairs(ns.poc.city.cells) do local g = m.d.g; if m.seen == fr then
        for k = 1, #g do total[g[k]] = (total[g[k]] or 0) + 1 end
        for k = 1, m.nt or 0 do drawn[g[k]] = (drawn[g[k]] or 0) + 1; nd = nd + 1 end end
      end
      local partial = 0
      for p, n in pairs(drawn) do if n < total[p] then partial = partial + n end end
      return nd, partial end''')
    setcam = L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end; ns.Redraw(); ns.Redraw() end''')
    for vk, (x, y, d, yaw, pitch) in VIEWS.items():
        for b in ('4000', '8000'):
            G.SlashCmdList.GPS3D('poc budget ' + b); setcam(ns3, 0, x, y, d, yaw, pitch)
            nd, partial = count(ns3)
            res[f'{ver}_{vk}_{b}'] = (int(nd), int(partial), round(100 * partial / max(nd, 1), 1))
            print(ver, vk, b, 'parts drawn', int(nd), 'in partly drawn pieces', int(partial), f'({100 * partial / max(nd, 1):.1f}%)', flush=True)
json.dump(res, open(f'{SP}/shards.json', 'w'))
