# Runs the sandbox engine + both addons in Lua 5.4 (as wasmoon will), drives it like the page does,
# and renders draw lists to PNG so the engine can be checked before the browser version.
import lupa.lua54 as lupa54, math, time, sys, os
from PIL import Image, ImageDraw
SITE = os.path.join(os.path.dirname(__file__), 'site')
L = lupa54.LuaRuntime()
G = L.globals()
G.SANDBOX_MEASURE = lambda text, size: len(text) * size * 0.55
L.execute(open(f'{SITE}/engine.lua').read())
for addon, files in [('GnomishPositioningSystem', ['Data/MapTiles.lua', 'Core.lua']), ('GPS3D', ['Data/Northshire.lua', 'GPS3D.lua'])]:
    for f in files:
        ok = G.SANDBOX_LOAD(addon, f, open(f'{SITE}/addons/{addon}/{f}').read())
        print('load', addon, f, ok)
    G.SANDBOX_LOADED(addon)
G.SANDBOX_FIRE('PLAYER_LOGIN')
TILE = 1600 / 3
def player(x, y, facing=0.0, z=0):
    gx, gy = 32 + x / TILE, 48 - y / TILE
    G.SANDBOX_PLAYER((32 - gy) * TILE, (32 - gx) * TILE, z, 0, facing, 'Elwynn Forest', 'Northshire Valley', 1429, 0.48, 0.41)
player(190, -425, 0.3)
W, H = 1280, 800
def tick(dt=1/60, n=1):
    s = ''
    for _ in range(n):
        r = G.SANDBOX_TICK(dt, W, H)
        if r: s = r; parse(r)
    return s
def chat():
    c = G.SANDBOX_CHAT()
    if c: print('CHAT>', c.replace('\n', '\nCHAT> '))
dictionary = {}
STATIC = {}
last = None
def parse(s):
    global last
    if not s: return last
    head, body = s.split('\n\x01\n', 1)
    for line in head.split('\n'):
        if line:
            i, t = line.split('\t', 1); dictionary[int(i)] = t
    nums = [int(x) for x in body.split(',')] if body else []
    items, clips, i = [], {}, 0
    while i < len(nums):
        k = nums[i]
        if k == 0:
            clips[nums[i+1]] = [v / 4 for v in nums[i+2:i+6]]; i += 6
        elif k == 1:
            tex, clip = dictionary[nums[i+1]], nums[i+2]
            pos = [v / 4 for v in nums[i+3:i+11]]; uvs = [v / 65535 for v in nums[i+11:i+19]]
            mode = nums[i+19]
            if mode == 0: cols = nums[i+20:i+24]; i += 24
            else: cols = nums[i+20:i+36]; i += 36
            items.append(('q', tex, clip, pos, uvs, mode, cols))
        elif k == 3:
            oid, tex = nums[i+1], dictionary[nums[i+2]]; uvs = [v / 65535 for v in nums[i+3:i+11]]; mode = nums[i+11]
            if mode == 0: cols = nums[i+12:i+16]; i += 16
            else: cols = nums[i+12:i+28]; i += 28
            STATIC[oid] = (tex, uvs, mode, cols)
        elif k == 4:
            oid, clip = nums[i+1], nums[i+2]; pos = [v / 4 for v in nums[i+3:i+11]]; i += 11
            tex, uvs, mode, cols = STATIC[oid]
            items.append(('q', tex, clip, pos, uvs, mode, cols))
        elif k == 2:
            items.append(('t', dictionary[nums[i+1]], nums[i+2], nums[i+3], [v / 4 for v in nums[i+4:i+8]], nums[i+8:i+12], nums[i+12])); i += 13
        else:
            raise ValueError(f'bad record {k} at {i}')
    last = (items, clips)
    return last
IMG = {}
def img(tex):
    if tex in IMG: return IMG[tex]
    p = None
    t = tex.replace('\\', '/')
    if tex.startswith('fdid:'):
        p = None
    elif 'overview/' in t: p = f"{SITE}/overview/{t.split('/')[-1]}"
    elif 'minimaparrow' in t: p = f'{SITE}/ui/minimaparrow.png'
    elif 'ui-tooltip-border' in t: p = f'{SITE}/ui/ui-tooltip-border.png'
    elif 'trackingborder' in t: p = f'{SITE}/ui/minimap-trackingborder.png'
    elif 'sizegrabber' in t: p = f"{SITE}/ui/sizegrabber-{t.split('-')[-1]}.png"
    IMG[tex] = Image.open(p).convert('RGBA') if p else None
    return IMG[tex]
def render(name, dl):
    items, clips = dl
    im = Image.new('RGBA', (W, H), (40, 40, 40, 255)); d = ImageDraw.Draw(im)
    for it in items:
        if it[0] == 'q':
            _, tex, clip, pos, uvs, mode, cols = it
            P = [(pos[0], H - pos[1]), (pos[2], H - pos[3]), (pos[6], H - pos[7]), (pos[4], H - pos[5])]  # UL LL LR UR
            col = tuple(cols[:4]) if mode == 0 else tuple(cols[:4])
            src = img(tex)
            if src is not None and abs(P[0][0]-P[1][0]) < 1 and abs(P[0][1]-P[3][1]) < 1:
                l, t_ = P[0]; r, b = P[2]
                if r - l >= 1 and b - t_ >= 1 and r > 0 and l < W:
                    u0, v0, u1, v1 = uvs[0], uvs[1], uvs[6], uvs[7]
                    sw, sh = src.size
                    box = (int(min(u0,u1)*sw), int(min(v0,v1)*sh), max(int(min(u0,u1)*sw)+1, int(max(u0,u1)*sw)), max(int(min(v0,v1)*sh)+1,int(max(v0,v1)*sh)))
                    try:
                        piece = src.crop(box).resize((int(r-l), int(b-t_)))
                        tint = Image.new('RGBA', piece.size, col)
                        piece = Image.composite(piece, Image.new('RGBA', piece.size, (0,0,0,0)), piece) if False else piece
                        im.alpha_composite(piece, (int(l), int(t_))) if 0 <= l and 0 <= t_ else None
                    except Exception as e:
                        pass
                    continue
            d.polygon(P, fill=col if src is None else (200, 200, 200, 255) if tex.startswith('fdid') else col, outline=None)
        else:
            _, text, clip, size, (l, b, w, h), col, j = it
            d.text((l, H - b - h), text, fill=tuple(col))
    im.save(name); return im

# open GPS (2D)
G.SlashCmdList.GPS('')
tick(1/60, 3); dl = last; chat()
print('2D items', len(dl[0]), 'textures', sum(1 for i in dl[0] if i[0]=='q'), 'texts', [i[1] for i in dl[0] if i[0]=='t'][:12])
render('t_2d.png', dl)
# click 3D
ui = G.GPS_MapFrame
def click_frame(fr):
    l, b, r, t = G.SANDBOX.rect(fr)
    x, y = (l + r) / 2, (b + t) / 2
    G.SANDBOX_MOUSE('move', x, y, None, 0); G.SANDBOX_MOUSE('down', x, y, 'LeftButton', 0); G.SANDBOX_MOUSE('up', x, y, 'LeftButton', 0)
# find mode3D button via namespace
ns1 = G.SANDBOX.namespaces['GnomishPositioningSystem']
click_frame(ns1.ui.mode3D)
t0 = time.time(); s = tick(1/60, 1); t1 = time.time(); dl = last; chat()
print('3D: GPS shown', ui.IsShown(ui), 'GPS3D shown', G.GPS3D_Frame.IsShown(G.GPS3D_Frame), 'items', len(dl[0]), 'tick+draw ms', round((t1-t0)*1000), 'len', len(s))
render('t_3d.png', dl)
# measure steady-state draw list cost
ns2 = G.SANDBOX.namespaces['GPS3D']
times = []
for k in range(10):
    ns2.cam.yaw = (ns2.cam.yaw + 5) % 360; ns2.Render()
    t0 = time.time(); s = tick(1/60); times.append((time.time()-t0)*1000)
print('3D frame (render already done, drawlist only) ms:', [round(x) for x in times], 'string', len(s))
t0 = time.time()
for k in range(10):
    ns2.cam.yaw = (ns2.cam.yaw + 5) % 360; ns2.Render(); tick(1/60)
print('3D render+drawlist per frame ms', round((time.time()-t0)*100))
# drag the 3D canvas (grab pan)
cv = ns2.canvas; l, b, r, t = G.SANDBOX.rect(cv); cx, cy = (l + r) / 2, (b + t) / 2
G.SANDBOX_MOUSE('down', cx, cy, 'LeftButton', 0)
for k in range(10): G.SANDBOX_MOUSE('move', cx + k * 10, cy + k * 5, None, 0); tick()
G.SANDBOX_MOUSE('up', cx + 90, cy + 45, 'LeftButton', 0); tick(1/60, 20); chat()
print('after drag mode', ns2.CamMode())
G.SANDBOX_SLASH('/gps3d test'); tick(1/60, 200); chat()
G.SANDBOX_SLASH('/gps test'); tick(1/60, 200); chat()
G.SANDBOX_SLASH('/foo'); chat()
print('saved:', G.SANDBOX_SAVE('GnomishPositioningSystemDB,GPS3D_DB')[:300])
