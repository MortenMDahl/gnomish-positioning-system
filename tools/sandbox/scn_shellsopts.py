# (proof of concept S1, 2026-10-24) the shells' five levels of detail on the page's Options panel: the sliders are
# there, moving one changes the levels (LodText and the units per level in a near view), "Defaults" puts them back.
# Shots: shots/shellsopts_panel.png, shellsopts_changed.png
import os
async def run():
    import json
    await ev('__sandbox.lua().run("function SANDBOX_GETTMP() return SANDBOX_TMP end")')
    async def lua(expr):
        return await ev('(() => { const L = __sandbox.lua(); L.run(' + json.dumps('SANDBOX_TMP = tostring(' + expr + ')') + '); return L.call("SANDBOX_GETTMP"); })()')
    await ev('Object.assign(__sandbox.player, { X: -8830, Y: 640, map: 0, facing: 0, zone: "Stormwind City", sub: "Trade District" })')
    await page.wait_for_timeout(1500); await ev('__sandbox.slash("/gps 3d")'); await page.wait_for_timeout(3000)
    await ev('__sandbox.slash("/gps3d shells on")')
    await ev('__sandbox.lua().run(' + json.dumps('local ns = SANDBOX.namespaces.GPS3D; ns.SetCamMode("free"); ns.SetTopDown(false, true); local c = ns.cam; c.map = 0; c.x, c.y, c.dist, c.yaw, c.pitch = 16426, -25896, 200, 25, 45; c.th = 117.5; ns.Redraw()') + ')')
    await page.wait_for_timeout(8000)
    st0 = await lua('SANDBOX.namespaces.GPS3D.shells.Status()')
    await page.click('#btn-opts'); await page.wait_for_timeout(800)
    rows = await ev('[...document.querySelectorAll("#opts-list .opt label, #opts-list .opt span")].map(e => e.textContent).filter(t => /^Shells/.test(t))')
    print('ROWS', json.dumps(rows))
    el = await page.query_selector('xpath=//label[normalize-space()="Shells level 2 from"]/following-sibling::div')
    if el: await el.scroll_into_view_if_needed()
    await page.screenshot(path='shots/shellsopts_panel.png')
    # level 2 from 70 to 250 yd, level 1 detail to set 1
    await ev('(() => { const r = document.querySelector(\'#opts-list input[type=range][data-var="GPS3D_ShellsFrom2"]\') || [...document.querySelectorAll("#opts-list .opt")].find(o => o.firstChild.textContent === "Shells level 2 from").querySelector("input"); r.value = 250; r.dispatchEvent(new Event("change")); })()')
    await page.wait_for_timeout(500)
    await ev('(() => { const r = [...document.querySelectorAll("#opts-list .opt")].find(o => o.firstChild.textContent === "Shells level 1 detail").querySelector("input"); r.value = 1; r.dispatchEvent(new Event("change")); })()')
    await page.wait_for_timeout(500)
    await ev('__sandbox.lua().run("SANDBOX.namespaces.GPS3D.Redraw()")'); await page.wait_for_timeout(6000)
    lod1 = await lua('SANDBOX.namespaces.GPS3D.shells.LodText()'); st1 = await lua('SANDBOX.namespaces.GPS3D.shells.Status()')
    label = await ev('[...document.querySelectorAll("#opts-list .opt")].filter(o => /^Shells level [12] /.test(o.firstChild.textContent)).map(o => o.firstChild.textContent + " = " + (o.querySelector("output") || {}).textContent).join(" | ")')
    await page.screenshot(path='shots/shellsopts_changed.png')
    await ev('(() => { const b = [...document.querySelectorAll("#opts-list .opt")].find(o => o.firstChild.textContent === "Shells levels").querySelector("button"); b.click(); })()')
    await page.wait_for_timeout(500)
    lod2 = await lua('SANDBOX.namespaces.GPS3D.shells.LodText()')
    print('BEFORE', st0); print('LABELS', label); print('CHANGED', lod1); print('STATUS', st1); print('DEFAULTS', lod2)
