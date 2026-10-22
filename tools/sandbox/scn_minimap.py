# GPS as the minimap (GPS3D's Minimap.lua, since 2026-10-22): the engine's stand-in of Blizzard's minimap at the
# top right, GPS's view in it at Razor Hill (Durotar), turned with you, Orgrimmar, Stormwind (with the sandbox's
# real minimap images and the buildings), zoomed in, straight down, and Blizzard's own minimap (the stand-in's
# plain ground) for comparison; a few blips (the game's, drawn flat) on top. Shots in shots/minimap_*.png.
# Usage: DSF=2 python3 run_page.py minimap 1400 900
async def run():
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    import json
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    async def box(obj):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + obj + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        return [float(v) for v in r.split(',')]
    async def mshot(name, pad=6):
        l, b, rr, t = await box('MinimapCluster')
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + (l - pad) * s, 'y': y0 + h - (t + pad) * s, 'width': (rr - l + 2 * pad) * s, 'height': (t - b + 2 * pad) * s})
    async def place(X, Y, m, facing, zone, sub):
        await ev(f'Object.assign(__sandbox.player, {{ X: {X}, Y: {Y}, map: {m}, facing: {facing}, zone: {json.dumps(zone)}, sub: {json.dumps(sub)} }})')
        await page.wait_for_timeout(2500)
    async def blips(points):
        # the game's blips, drawn flat by the Minimap widget: world X, Y and a colour
        await run_lua('SANDBOX.minimapBlips = {' + ','.join('{%f,%f,%f,%f,%f}' % p for p in points) + '}')
    await run_lua('SANDBOX_MINIMAP()')
    await run_lua('for _, f in ipairs({ GPS_MapFrame, GPS3D_Frame, GPS_WorldMapFrame }) do if f and f:IsShown() then f:Hide() end end')
    # Razor Hill, Durotar (Morten's mock-up: Durotar tilted, quest markers and his arrow)
    X, Y = 300, -4700
    await place(X, Y, 1, 0.8, 'Durotar', 'Razor Hill')
    await mshot('minimap_blizzard_durotar.png')
    await ev('__sandbox.slash("/gps minimap on")'); await page.wait_for_timeout(3000)
    await blips([(X + 60, Y - 20, 1, 0.85, 0.1), (X - 40, Y + 70, 1, 1, 0.2), (X + 120, Y + 90, 0.2, 1, 0.2)])
    await page.wait_for_timeout(800)
    await mshot('minimap_durotar.png')
    await shot('minimap_screen.png')
    await run_lua('SANDBOX.cvars.rotateMinimap = true'); await page.wait_for_timeout(1200)
    await mshot('minimap_durotar_rotate.png')
    await run_lua('SANDBOX.cvars.rotateMinimap = false; SANDBOX.minimapBlips = {}')
    await place(1630, -4380, 1, 0.0, 'Orgrimmar', '')
    await page.wait_for_timeout(2000)
    await mshot('minimap_orgrimmar.png')
    await place(-8830, 640, 0, 2.3, 'Stormwind City', 'Trade District')
    await page.wait_for_timeout(4000)
    await mshot('minimap_stormwind.png')
    await run_lua('Minimap_ZoomIn(); Minimap_ZoomIn(); Minimap_ZoomIn()'); await page.wait_for_timeout(2500)
    await mshot('minimap_stormwind_zoom3.png')
    await run_lua('Minimap_ZoomOut(); Minimap_ZoomOut(); Minimap_ZoomOut()')
    await ev('__sandbox.slash("/gps minimap off")'); await page.wait_for_timeout(1500)
    await mshot('minimap_blizzard_stormwind.png')
    await run_lua('SANDBOX.namespaces.GPS3D.minimap.SetTilt(0)')
    await ev('__sandbox.slash("/gps minimap on")'); await page.wait_for_timeout(2500)
    await mshot('minimap_stormwind_straightdown.png')
    await run_lua('SANDBOX.namespaces.GPS3D.minimap.SetTilt(35)')
    print('state:', await lua('SANDBOX.namespaces.GPS3D.minimap.State()'))
