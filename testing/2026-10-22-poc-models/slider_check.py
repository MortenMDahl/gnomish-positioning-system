# The model sliders: on the settings list, applied, saved in GPS3D_DB and read back by a new session
import os, sys
os.chdir('/home/claude/wt/poc/tools/sandbox'); sys.path.insert(0, '.')
os.environ['NO_MUTANTS'] = '1'; sys.argv = [os.path.abspath('test_minimap.py')]
src = open('test_minimap.py').read(); src = src[:src.index('results = []')]
__file__ = os.path.abspath('test_minimap.py'); exec(compile(src, __file__, 'exec'))
g = Game(minimap=False); L, G, ns3 = g.L, g.G, g.ns3
keys = L.eval('function() local o = {} for _, e in ipairs(GPS3D_API.settings) do if e.key and e.key:find("Poc") then o[#o + 1] = e.key .. "=" .. e.name .. " [" .. tostring(e.min) .. ".." .. tostring(e.max) .. "]" end end return table.concat(o, "; ") end')()
print('settings:', keys)
setv = L.eval('function(key, v) for _, e in ipairs(GPS3D_API.settings) do if e.key == key then e.set(v); return e.get() end end end')
print('set smallest part 7.3 ->', setv('GPS3D_PocMinArea', 7.3), '; parts per frame 6200 ->', setv('GPS3D_PocBudget', 6200), '; distance 95 ->', setv('GPS3D_PocRadius', 95))
g.at(-8830, 640, 0, 0, 'x', ''); g.tick(2); G.SlashCmdList.GPS('3d'); g.tick(3); G.SlashCmdList.GPS3D('poc city')
L.execute('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; ns.Redraw()')
p1 = ns3.poc.stats.parts; setv('GPS3D_PocBudget', 2000); L.execute('SANDBOX.namespaces.GPS3D.Redraw()'); p2 = ns3.poc.stats.parts
print('parts drawn at 6200 / 2000:', p1, '/', p2)
saved = g.saved() if hasattr(g, 'saved') else None
db = L.eval('function() return string.format("%s %s %s", GPS3D_DB.pocMin, GPS3D_DB.pocBudget, GPS3D_DB.pocRadius) end')()
print('GPS3D_DB:', db)
sv = str(G.SANDBOX_SAVE('GnomishPositioningSystemDB,GPS3D_DB'))
g2 = Game(sv, minimap=False)
print('after a reload:', g2.L.eval('function() local o = {} for _, e in ipairs(GPS3D_API.settings) do if e.key and e.key:find("Poc") then o[#o + 1] = e.key .. "=" .. tostring(e.get()) end end return table.concat(o, " ") end')())
