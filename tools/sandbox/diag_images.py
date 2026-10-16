import math
src = open('test_world.py').read().split("place(-8958.3, -190, 0, 0.3")[0]
exec(compile(src, 'setup', 'exec'))
place(-9800, 1400, 0, 0.3, 'Westfall', '')
G.SlashCmdList.GPS(''); tick(2)
G.GPS3D_API.Show(G.GPS_MapFrame, None); G.GPS_MapFrame.Hide(G.GPS_MapFrame); tick(30)
st, cam, pl = ns2.stats, ns2.cam, ns2.player
W, H = ns2.canvas.GetSize(ns2.canvas)
def run(label):
    ns2.Render()
    seen = {}
    for t in st.visible.values():
        m = t.mesh
        if m.detail: continue
        k = (int(m.tx), int(m.ty)); a, b, c = t.a, t.b, t.c
        on = any(abs(m.px[q]) < W/2 and abs(m.py[q]) < H/2 for q in (a, b, c))
        area = abs((m.px[b]-m.px[a])*(m.py[c]-m.py[a]) - (m.px[c]-m.px[a])*(m.py[b]-m.py[a]))/2
        s = seen.setdefault(k, [int(m.step), 'overview' if 'Overview' in str(t.tex.file) else 'minimap', 0, 0.0])
        if on: s[2] += 1; s[3] += area
    ov = [(k, v) for k, v in seen.items() if v[1] == 'overview' and v[2] > 0]
    tot = sum(v[3] for v in seen.values()); ova = sum(v[3] for k, v in ov)
    print(f'== {label}: tiles {len(seen)}, overview tiles on screen {len(ov)}, share of screen area drawn with the overview image {100*ova/max(tot,1):.0f}%')
    for k, v in sorted(ov, key=lambda kv: -kv[1][3])[:6]:
        # magnification: screen px per image px = sqrt(screen area of tile part / image area of that part); tile image 64 px for 533 yd
        print('   ', k, 'step', v[0], 'on-screen tris', v[2])
for dist, pitch in ((330, 89.9), (800, 89.9), (1500, 89.9), (3000, 89.9)):
    cam.dist, cam.pitch = dist, pitch; run(f'straight down, dist {dist}')
G.SlashCmdList.GPS3D('top'); tick(30)
for dist in (330, 800, 1500):
    cam.dist = dist; run(f'tilted {cam.pitch:.0f}, dist {dist}')
