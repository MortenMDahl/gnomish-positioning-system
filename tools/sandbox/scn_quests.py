# Your quests in the page: the 2D map near Northshire (markers, the tracked quest's area), a marker
# hovered (tooltip, its area too), the 3D view zoomed out over Elwynn, and the traditional map's
# stand-in. The quest log, the quest buttons and the areas are the sandbox's stand-ins (7 quests in
# Elwynn and Westfall). Shots: shots/quests_*.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G1 = 'SANDBOX.namespaces.GnomishPositioningSystem'
    await run_lua(G1 + '.db.mode = "2D"')
    await page.fill('#cmdline', '/gps 2d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(800)
    await run_lua(G1 + '.view.follow = false; ' + G1 + '.view.cx, ' + G1 + '.view.cy = 32.2, 49.0; ' + G1 + '.view.scale = 300; ' + G1 + '.Layout()')
    await page.mouse.move(5, 5); await page.wait_for_timeout(2500)
    print('2D markers shown:', await lua('(function() local n = 0; for _, p in ipairs(' + G1 + '.quests.pins2D) do if p:IsShown() then n = n + 1 end end; return n end)()'))
    await shot('quests_2d.png')
    # hover the Kobold Camp marker (quest 7)
    xy = await lua('(function() for _, p in ipairs(' + G1 + '.quests.pins2D) do if p.gpsQuestID == 7 then local l, b, r, t = SANDBOX.rect(p); return string.format("%f,%f", (l + r) / 2, (b + t) / 2) end end end)()')
    x, y = [float(v) for v in xy.split(',')]
    s = await ev('(() => { const r = document.getElementById("gl").getBoundingClientRect(); return Math.max(0.6, Math.min(1, r.width / 560, r.height / 520)); })()')
    x0, y0, w, h = await canvas_box()
    await page.mouse.move(x0 + x * s, y0 + h - y * s); await page.wait_for_timeout(600)
    print('tooltip:', await lua('table.concat(GameTooltip:GetLines(), " | ")'))
    await shot('quests_2d_hover.png')
    await page.mouse.move(x0 + x * s, y0 + h - y * s); await page.mouse.down(); await page.mouse.up(); await page.wait_for_timeout(800)
    print('tracked after click:', await lua('C_SuperTrack.GetSuperTrackedQuestID()'))
    await page.mouse.move(5, 5); await page.wait_for_timeout(500)
    await shot('quests_2d_tracked.png')
    await page.fill('#cmdline', '/gps 3d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    G3 = 'SANDBOX.namespaces.GPS3D'
    await run_lua(G3 + '.SetCamMode("free"); ' + G3 + '.SetTopDown(false, true); ' + G3 + '.cam.dist = 2200; ' + G3 + '.Render()')
    await page.wait_for_timeout(3000)
    print('3D markers shown:', await lua('(function() local n = 0; for _, p in ipairs(' + G3 + '.questPins) do if p:IsShown() then n = n + 1 end end; return n end)()'))
    await shot('quests_3d.png')
    # the tracked quest's objective area on the ground (QuestAreas.lua): quest 33's waisted area, from
    # above and tilted
    await run_lua('C_SuperTrack.SetSuperTrackedQuestID(33)')
    await page.wait_for_timeout(800)
    await run_lua(G3 + '.SetTopDown(true, true); ' + G3 + '.cam.x, ' + G3 + '.cam.y = 32.2 * 1600 / 3, -48.97 * 1600 / 3; ' + G3 + '.cam.dist = 900; ' + G3 + '.Render()')
    await page.wait_for_timeout(2500)
    await run_lua(G3 + '.Render()'); await page.wait_for_timeout(800)
    print('3D area:', await lua('string.format("%d areas, %d fill, %d border pieces; hovered %s", ' + G3 + '.questAreas.nShapes, ' + G3 + '.questAreas.nFill, ' + G3 + '.questAreas.nEdge, tostring(' + G1 + '.quests.hovered))'))
    await shot('quests_3d_area.png')
    await run_lua(G3 + '.SetTopDown(false, true); ' + G3 + '.cam.pitch = 48; ' + G3 + '.cam.yaw = 35; ' + G3 + '.cam.dist = 650; ' + G3 + '.Render()')
    await page.wait_for_timeout(1500)
    await shot('quests_3d_area_tilted.png')
    await page.fill('#cmdline', '/gps map'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    await shot('quests_map.png')
