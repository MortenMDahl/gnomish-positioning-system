# The debug log in the page: the Debug log panel turns it on, the map is used, a note is added, and the
# panel shows the lines (the same text the game saves on /reload). Shot: shots/debug_panel.png.
async def run():
    await page.click('#btn-log'); await page.wait_for_timeout(300)
    print('before:', await page.inner_text('#dlog-status'))
    await page.click('#dlog-on'); await page.wait_for_timeout(300)
    await page.click('#dlog-x')
    for cmd in ['/gps 2d', '/gps 3d', '/gps map', '/gps debug mark the arrow looked wrong here']:
        await page.fill('#cmdline', cmd); await page.press('#cmdline', 'Enter'); await page.wait_for_timeout(1500)
    await page.click('#btn-log'); await page.wait_for_timeout(1500)
    print('after:', await page.inner_text('#dlog-status'))
    text = await page.input_value('#dlog-text')
    print('\n'.join(text.split('\n')[:6])); print('...'); print('\n'.join(text.split('\n')[-4:]))
    await shot('debug_panel.png')
    await page.click('#dlog-copy'); await page.wait_for_timeout(300)
    print('copy button:', await page.inner_text('#dlog-copy'))
