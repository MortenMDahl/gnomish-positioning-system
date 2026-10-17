# Every zone in the page (zones.lua): the 2D map zoomed out over the Eastern Kingdoms with the title
# following the middle of the view, Booty Bay (title and footer from your position), and the
# traditional map's stand-in sheet of the Eastern Kingdoms with all its zones. Shots: shots/zones_*.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def run_lua(code):
        await ev('__sandbox.lua().run(' + json.dumps(code) + ')')
    G1 = 'SANDBOX.namespaces.GnomishPositioningSystem'
    await page.fill('#cmdline', '/gps 2d'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(800)
    for name, X, Y in [('stranglethorn', -12500, -500), ('hinterlands', 200, -4000), ('silverpine', 600, 1400)]:
        await run_lua(G1 + '.view.follow = false; ' + G1 + f'.view.cx, {G1}.view.cy = 32 - ({Y}) / (1600 / 3), 32 - ({X}) / (1600 / 3); ' + G1 + '.view.scale = 40; ' + G1 + '.Layout()')
        await page.mouse.move(5, 5); await page.wait_for_timeout(1200)
        print(name, 'title:', await lua(G1 + '.ui.title:GetText()'), '| footer:', await lua(G1 + '.ui.footer:GetText()'))
        await shot(f'zones_2d_{name}.png')
    await page.select_option('#teleport', 'bootybay'); await page.click('#btn-go'); await page.wait_for_timeout(1500)
    await run_lua(G1 + '.FollowPlayer()'); await page.wait_for_timeout(1000)
    print('booty bay title:', await lua(G1 + '.ui.title:GetText()'), '| footer:', await lua(G1 + '.ui.footer:GetText()'), '| readout:', await page.inner_text('#you'))
    await page.fill('#cmdline', '/gps map'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1000)
    await run_lua(G1 + '.mapWindow.SetMap(1415)'); await page.wait_for_timeout(1500)
    await shot('zones_map_ek.png')
