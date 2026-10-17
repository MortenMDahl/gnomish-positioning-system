# Options > AddOns in the page: opened with the header button and with /gps options, changed with
# the page's own controls (select, checkbox, slider, button), each change seen in the addon's saved
# settings and in what the map does. Screenshots go to shots/settings_*.png.
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    async def shown():
        return await lua('(GPS_MapFrame:IsShown() and "2D" or "") .. (GPS3D_Frame:IsShown() and "3D" or "") .. (GPS_WorldMapFrame:IsShown() and "Map" or "")')
    def row(name):
        return page.locator('#opts-list .opt').filter(has_text=name)
    await page.click('#btn-opts'); await page.wait_for_timeout(300)
    print('panel open (button):', await page.is_visible('#opts'))
    print('rows:', await page.locator('#opts-list .opt').count(), 'headers:', await page.locator('#opts-list h3').all_inner_texts())
    await row('Buildings').hover(); await page.wait_for_timeout(200)
    print('tip:', await page.inner_text('#opts-tip'))
    await shot('settings_panel.png')
    await row('Opens as').locator('select').select_option('3D'); await page.wait_for_timeout(200)
    print('Opens as 3D -> db.mode =', await lua('GnomishPositioningSystemDB.mode'))
    await row('Buildings').locator('input').uncheck(); await page.wait_for_timeout(200)
    print('Buildings off -> GPS3D_DB.detail =', await lua('GPS3D_DB.detail'))
    s = row('Building detail').locator('input[type=range]')
    await s.evaluate('(el) => { el.value = 2000; el.dispatchEvent(new Event("input")); el.dispatchEvent(new Event("change")); }'); await page.wait_for_timeout(200)
    print('Building detail 2000 -> GPS3D_DB.buildings =', await lua('GPS3D_DB.buildings'), 'label', await row('Building detail').locator('output').inner_text())
    await page.keyboard.press('Escape'); await page.wait_for_timeout(200)
    print('Escape closes it:', not await page.is_visible('#opts'))
    before = await shown()
    await page.keyboard.press('KeyM'); await page.wait_for_timeout(1500)
    if before: await page.keyboard.press('KeyM'); await page.wait_for_timeout(1500)
    print('open before:', repr(before), '- M opens:', await shown())
    await page.fill('#cmdline', '/gps options'); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(400)
    print('panel open (/gps options):', await page.is_visible('#opts'))
    await row('Window').locator('button').click(); await page.wait_for_timeout(300)
    print('Reset -> db.point[1] =', await lua('GnomishPositioningSystemDB.point[1]'), 'width', await lua('GnomishPositioningSystemDB.width'))
    await page.click('#opts-defaults'); await page.wait_for_timeout(300)
    print('Defaults -> mode', await lua('GnomishPositioningSystemDB.mode'), 'detail', await lua('GPS3D_DB.detail'), 'buildings', await lua('GPS3D_DB.buildings'))
    await shot('settings_defaults.png')
    await page.click('#opts-close')
