# The open sea in the 3D view and in its hand-over to the planet (2026-10-21): screenshots of the window's
# canvas (inside the title band, the footer and the rings) at the views Morten reported: Kalimdor's north
# (Teldrassil, Hyjal) straight down and tilted, north-east of Azshara, and NE Azshara zoomed out through the
# hand-over. Saves shots/sv_<TAG>_<name>.png and shots/sv_<TAG>.json (each view's planet state).
# SV_TAG names the run; SV_NOCLOUDS=1 hides the planet's clouds; SV_2D=1 adds the
# 2D map over Kalimdor's north (sv_<TAG>_map2d.png); SV_VIEWS overrides the views: "name:map:gx:gy:dist:pitch:yaw;..." (pitch 0 = straight down).
import os, json
TAG = os.environ.get('SV_TAG', 'x')
W, H = int(os.environ.get('SV_W', '900')), int(os.environ.get('SV_H', '650'))
DEFAULT = ';'.join([
    'teld_down:1:29:12:9000:0:0', 'teld_tilt:1:29:13:9000:45:0', 'teld_far:1:30:13:12000:0:0',
    'azs_down:1:45:21:6000:0:0', 'azs_far:1:45:21:10000:0:0', 'azs_tilt:1:45:22:9000:45:30',
    'ho_14000:1:44:22:14000:0:0', 'ho_17000:1:44:22:17000:0:0', 'ho_19000:1:44:22:19000:0:0',
    'ho_22000:1:44:22:22000:0:0', 'ho_26000:1:44:22:26000:0:0', 'ho_30000:1:44:22:30000:0:0',
])
VIEWS = [v.split(':') for v in os.environ.get('SV_VIEWS', DEFAULT).split(';') if v]
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G3 = 'SANDBOX.namespaces.GPS3D'
    await page.click('#btn-3d'); await page.wait_for_timeout(2500)
    await run_lua(f'GPS3D_Frame:SetSize({W}, {H}); {G3}.Render()')
    await page.wait_for_timeout(800)
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    out = {}
    for name, m, gx, gy, dist, pitch, yaw in VIEWS:
        code = (f'local ns = {G3}; GPS3D_API.Show(nil, {{ map = {m}, gx = {gx}, gy = {gy} }}); '
                f'ns.cam.dist = {dist}; ns.cam.yaw = {yaw}; ')
        if float(pitch) > 0:
            code += f'ns.SetTopDown(false, true); ns.cam.pitch = {pitch}; '
        else:
            code += 'ns.SetTopDown(true, true); '
        code += 'ns.Render()'
        await run_lua(code)
        await page.wait_for_timeout(1500)
        await run_lua(f'{G3}.Render()')
        await page.wait_for_timeout(1200)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + G3 + '.canvas); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        clip = {'x': x0 + (l + 4) * s, 'y': y0 + h - (t - 64) * s, 'width': (rr - l - 54) * s, 'height': (t - b - 94) * s}
        if os.environ.get('SV_NOCLOUDS'):  # the planet's clouds and their shadows hidden (they drift over the sea measured)
            await run_lua(f'{G3}.globeFrames[4]:SetAlpha(0)')  # (the sky's frame: clouds, their shadows, the storm, the glow)
            await page.wait_for_timeout(600)
        await page.screenshot(path=f'shots/sv_{TAG}_{name}.png', clip=clip)
        st = await lua(f'(function() local st = {G3}.GlobeFrameState.stats; return string.format("%s,%s,%s,%s,%s,%s", tostring({G3}.GlobeOn()), tostring(st.atlas), tostring(st.pages), tostring(st.k), tostring({G3}.cam.dist), tostring({G3}.cam.map)) end)()')
        # pairs of screen points on either side of an edge in the sea north-east of Azshara: the ground's last tiles
        # against the sea beyond them (tiles 45-47 of row 20 against row 19; tile 47 of row 20 against 48; tile 48
        # of row 23 against 49), and a coastal tile's sea against the open-sea tile next to it (47 and 48 of row 23);
        # the planet's projection once it draws (GlobeProject), else the ground's (Project)
        T = 1600 / 3
        pairs = [((45.5, 20.5), (45.5, 19.5)), ((46.5, 20.5), (46.5, 19.5)), ((47.5, 20.5), (47.5, 19.5)),
                 ((47.5, 20.5), (48.5, 20.5)), ((48.5, 23.5), (49.5, 23.5)), ((47.85, 23.5), (48.5, 23.5))]
        pts = []
        for k, pair in enumerate(pairs):
            for side, (x, y) in zip(('in', 'out'), pair):
                pr = await lua(f'(function() local ns = {G3}; local px, py; if ns.GlobeOn() then px, py = ns.GlobeProject(ns.GlobeToPlane(ns.cam.map, {x * T}, {-y * T})) else px, py = ns.Project({x * T}, {-y * T}, 0) end; if not px then return "" end; return string.format("%f,%f", px, py) end)()')
                if pr:
                    X, Y = [float(v) for v in pr.split(',')]
                    pts.append([k, side, ((l + rr) / 2 + X - (l + 4)) * s, ((t - 64) - ((b + t) / 2 + Y)) * s])
        # along the old tan line (north side of tiles 45-47 in row 20, east side of tile 47: 2.5 px of 64 in)
        # (each with a point 0.4 tile further out, in the open sea, to compare with)
        line = [(45.05 + 0.1 * i, 20.04) for i in range(30)] + [(47.96, 20.05 + 0.1 * i) for i in range(10)]
        line = line + [(x, y - 0.4) for x, y in line[:30]] + [(x + 0.4, y) for x, y in line[30:]]
        code = 'local ns = %s; local o = {}; local T = 1600 / 3; for _, p in ipairs({%s}) do local px, py; ' % (G3, ', '.join('{%f, %f}' % q for q in line))
        code += 'if ns.GlobeOn() then px, py = ns.GlobeProject(ns.GlobeToPlane(ns.cam.map, p[1] * T, -p[2] * T)) else px, py = ns.Project(p[1] * T, -p[2] * T, 0) end; '
        code += 'if px then o[#o + 1] = string.format("%.2f,%.2f", px, py) end end; return table.concat(o, ";")'
        lp = await lua('(function() ' + code + ' end)()')
        lpts = []
        for q in (lp.split(';') if lp else []):
            X, Y = [float(v) for v in q.split(',')]
            lpts.append([((l + rr) / 2 + X - (l + 4)) * s, ((t - 64) - ((b + t) / 2 + Y)) * s])
        lpts = [p + q for p, q in zip(lpts[:40], lpts[40:])] if len(lpts) == 80 else []
        out[name] = {'state': st, 'scale': s, 'edge': pts, 'line': lpts}
    if os.environ.get('SV_2D'):  # the 2D map over Kalimdor's north, zoomed out (the overview images; 24 px a tile)
        G1 = 'SANDBOX.namespaces.GnomishPositioningSystem'
        await run_lua(f'GPS3D_Frame:Hide(); GPS_MapFrame:Show(); {G1}.view.follow = false; {G1}.view.map = 1; {G1}.view.cx, {G1}.view.cy = 36, 18; {G1}.view.scale = 24; {G1}.ShowMap(1, true)')
        await page.mouse.move(5, 5); await page.wait_for_timeout(2500)
        await run_lua(f'GPS_MapFrame:SetSize({W}, {H}); {G1}.view.cx, {G1}.view.cy = 36, 18; {G1}.view.scale = 24; {G1}.ShowMap(1, true)')
        await page.wait_for_timeout(2500)
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(GPS_MapFrame); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        clip = {'x': x0 + (l + 4) * s, 'y': y0 + h - (t - 64) * s, 'width': (rr - l - 54) * s, 'height': (t - b - 94) * s}
        await page.screenshot(path=f'shots/sv_{TAG}_map2d.png', clip=clip)
        out['map2d'] = {'state': '2D map, Kalimdor north, 24 px a tile', 'scale': s}
    json.dump(out, open(f'shots/sv_{TAG}.json', 'w'), indent=1)
    print('views', len(VIEWS))
