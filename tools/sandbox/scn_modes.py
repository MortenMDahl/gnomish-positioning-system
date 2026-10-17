# The three modes in the page: 2D -> 3D -> traditional map with the mode ring, the map window
# (Blizzard's map is a stand-in here), then into a dungeon (the traditional map opens, with floors)
# and out again (back to the mode chosen). Screenshots go to shots/modes_*.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    async def centre(obj):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + obj + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        return x0 + (l + rr) / 2 * s, y0 + h - (b + t) / 2 * s
    async def click(obj, button='left'):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.mouse.down(button=button); await page.mouse.up(button=button); await page.wait_for_timeout(400)
    async def hover(obj):
        x, y = await centre(obj); await page.mouse.move(x, y); await page.wait_for_timeout(300)
    async def window_shot(name, frame):
        r = await lua('(function() local l,b,r,t = SANDBOX.rect(' + frame + '); return string.format("%f,%f,%f,%f", l,b,r,t) end)()')
        l, b, rr, t = [float(v) for v in r.split(',')]
        x0, y0, w, h = await canvas_box()
        await page.screenshot(path=f'shots/{name}', clip={'x': x0 + l * s - 20, 'y': y0 + h - t * s - 4, 'width': (rr - l) * s + 24, 'height': (t - b) * s + 8})
    async def shown():
        return await lua('(GPS_MapFrame:IsShown() and "2D" or "") .. (GPS3D_Frame:IsShown() and "3D" or "") .. (GPS_WorldMapFrame:IsShown() and "Map" or "")')
    G1, G3 = 'SANDBOX.namespaces.GnomishPositioningSystem', 'SANDBOX.namespaces.GnomishPositioningSystem.mapWindow'
    await run_lua(G1 + '.db.mode = "2D"')
    print('start:', await shown())
    await page.mouse.move(5, 5); await page.wait_for_timeout(300)
    await window_shot('modes_2d.png', 'GPS_MapFrame')
    await click(G1 + '.ui.modeSwitch'); await page.wait_for_timeout(1500)
    print('after one click:', await shown())
    await page.mouse.move(5, 5); await page.wait_for_timeout(300)
    await window_shot('modes_3d.png', 'GPS3D_Frame')
    await click('SANDBOX.namespaces.GPS3D.ui.modeSwitch'); await page.wait_for_timeout(800)
    print('after two clicks:', await shown(), '| title', await lua(G3 + '.ui.title:GetText()'), '| subtitle', await lua(G3 + '.ui.subtitle:GetText()'))
    await hover(G3 + '.ui.modeSwitch'); await window_shot('modes_map_hover.png', 'GPS_WorldMapFrame')
    await page.mouse.move(5, 5); await page.wait_for_timeout(300)
    await window_shot('modes_map_elwynn.png', 'GPS_WorldMapFrame')
    # right-click on the map: the continent
    await click(G3 + '.map.ScrollContainer', 'right'); await page.wait_for_timeout(500)
    print('right-click on the map:', await lua(G3 + '.ui.title:GetText()'))
    await window_shot('modes_map_continent.png', 'GPS_WorldMapFrame')
    await click(G3 + '.ui.me'); await page.wait_for_timeout(500)
    # into the dungeon
    await page.select_option('#teleport', 'instance'); await page.click('#btn-go'); await page.wait_for_timeout(2500)
    print('in the dungeon:', await shown(), '| title', await lua(G3 + '.ui.title:GetText()'), '| subtitle', await lua(G3 + '.ui.subtitle:GetText()'), '| auto', await lua(G1 + '.autoMap'))
    await run_lua(G1 + '.db.mode = "2D"; GPS_WorldMapFrame:Hide()'); await page.wait_for_timeout(300)
    await page.keyboard.press('KeyM'); await page.wait_for_timeout(800)
    print('M in the dungeon (chosen 2D):', await shown(), '| auto', await lua(G1 + '.autoMap'))
    await window_shot('modes_dungeon.png', 'GPS_WorldMapFrame')
    await click(G3 + '.ui.next'); await page.wait_for_timeout(400)
    print('next floor:', await lua(G3 + '.ui.subtitle:GetText()'))
    await window_shot('modes_dungeon_floor2.png', 'GPS_WorldMapFrame')
    await page.select_option('#teleport', 'ns-front'); await page.click('#btn-go'); await page.wait_for_timeout(2500)
    print('out again:', await shown())
    await page.keyboard.press('Escape'); await page.wait_for_timeout(300)
    await ev('__sandbox.slash("/gps test")'); await page.wait_for_timeout(3500)
