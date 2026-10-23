# Whole buildings: per view and budget, buildings on screen / drawn whole / not drawn / partly drawn (must be 0), and
# the parts skipped as facing away; plus the same for a building close to the camera turning round it
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3)
G.SlashCmdList.GPS3D('detail off'); print(G.SlashCmdList.GPS3D('poc city')); G.SlashCmdList.GPS3D('poc min 0'); G.SlashCmdList.GPS3D('poc radius 400')
setcam = L.eval('''function(ns, m, x, y, d, yaw, pitch) ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = m; c.x, c.y, c.dist, c.yaw, c.pitch = x, y, d, yaw, pitch; c.th = ns.GroundHeight(x, y, m); if ns.SnapLift then ns.SnapLift() end; ns.Redraw(); ns.Redraw() end''')
partly = L.eval('''function(ns)
  local fr = 0; for _, u in ipairs(ns.poc.city.units) do for _, m in ipairs(u.groups) do if (m.active or 0) > fr then fr = m.active end end end
  local whole, part = 0, 0
  for _, u in ipairs(ns.poc.city.units) do
    local any, all = false, true
    for _, m in ipairs(u.groups) do if (m.want or 0) > 0 then if m.active == fr and m.nt == m.want then any = true else all = false end end end
    if any then if all then whole = whole + 1 else part = part + 1 end end
  end
  return whole, part end''')
VIEWS = {'near': (16380, -25920, 90, 25, 40), 'close': (16426, -25896, 200, 25, 45), 'high': (16400, -25880, 420, 25, 62)}
for vk, (x, y, d, yaw, pitch) in VIEWS.items():
    for b in ('4000', '8000'):
        G.SlashCmdList.GPS3D('poc budget ' + b); setcam(ns3, 0, x, y, d, yaw, pitch)
        st = ns3.poc.stats; whole, part = partly(ns3)
        print(vk, b, 'on screen', st.onScreen, 'drawn whole', whole, 'partly', part, 'not drawn', st.skipped, 'parts', st.parts, 'back-facing parts skipped', st.backParts, 'in groups', st.backGroups, 'front parts of all on-screen buildings', st.frontTotal, f'(back sides save {100 * st.backParts / (st.backParts + st.frontTotal):.0f}%)', flush=True)
