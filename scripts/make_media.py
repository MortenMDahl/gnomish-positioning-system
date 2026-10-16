# Draws the two small icons GPS ships in Interface/AddOns/GnomishPositioningSystem/Media/ (64x64
# 32-bit TGA, origin bottom-left, alpha) and PNG copies for the sandbox (tools/sandbox/site/ui/).
#   Needle.tga  the compass needle: dull red north half, grey south half, black outline, pointing up
#               (GPS3D turns it with Texture:SetRotation).
#   CamFollow.tga, CamBehind.tga, CamFree.tga  the camera-mode ring, one per mode (white, tinted
#               brass or gold with SetVertexColor): Follow, a dot (you) with the view circling it;
#               Behind, your arrow with the view's cone opening from behind it; Free, four arrows (move).
#   Cell.tga    one square of ground: a white outline (black edge) inset by 1/8 of the texture on each
#               side. GPS3D bends four of these with SetVertexOffset into a 2x2 grid seen the way the
#               camera sees the ground (turned with the view, in perspective when tilted).
# Drawn at 8x and scaled down for smooth edges. Usage: python scripts/make_media.py
import os, struct
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
MEDIA = os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem', 'Media')
SANDBOX_UI = os.path.join(ROOT, 'tools', 'sandbox', 'site', 'ui')
N, K = 64, 8  # final size, supersampling
S = N * K

def write_tga(img, path):
    img = img.convert('RGBA')
    w, h = img.size
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 8)  # uncompressed true colour, 8 alpha bits, bottom-left origin
    rows = []
    px = img.load()
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        rows.append(bytes(row))
    with open(path, 'wb') as f:
        f.write(header + b''.join(rows))

def needle():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    tip, half, waist = S * 0.06, S * 0.13, S * 0.94
    north = [(c, tip), (c + half, c), (c, c), ]
    d.polygon([(c, tip), (c + half, c), (c, c + half * 0.0), (c - half, c)], fill=(0, 0, 0, 255))
    # outline: draw the whole diamond in black slightly larger, then the halves inside
    o = S * 0.035
    d.polygon([(c, tip - o), (c + half + o, c), (c, waist + o), (c - half - o, c)], fill=(0, 0, 0, 230))
    d.polygon([(c, tip), (c + half, c), (c - half, c)], fill=(155, 42, 31, 255))      # north: dull red
    d.polygon([(c, tip), (c, c), (c - half, c)], fill=(118, 30, 22, 255))            # its shaded side
    d.polygon([(c, waist), (c + half, c), (c - half, c)], fill=(163, 158, 146, 255)) # south: grey
    d.polygon([(c, waist), (c, c), (c + half, c)], fill=(120, 116, 106, 255))        # its shaded side
    r = S * 0.045
    d.ellipse([c - r, c - r, c + r, c + r], fill=(201, 162, 74, 255), outline=(0, 0, 0, 255), width=int(S * 0.012))
    return im.resize((N, N), Image.LANCZOS)

def strokes(lines, closed_polys=(), black=0.11, white=0.055):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for width, col in ((int(S * black), (0, 0, 0, 210)), (int(S * white), (255, 255, 255, 255))):
        for poly in closed_polys:
            pts = [(x * S, y * S) for x, y in poly]
            d.line(pts + [pts[0]], fill=col, width=width, joint='curve')
            r = width / 2
            for x, y in pts: d.ellipse([x - r, y - r, x + r, y + r], fill=col)  # round corners
        for (x0, y0), (x1, y1) in lines:
            d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=col, width=width)
    return im.resize((N, N), Image.LANCZOS)

BLACK, WHITE = (0, 0, 0, 210), (255, 255, 255, 255)

def outlined(draw_fn, black=0.10, white=0.055):
    # draw_fn(d, width, colour, grow) draws the shapes; called twice: a black edge, then white on top
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    draw_fn(d, int(S * black), BLACK, S * (black - white) / 2)
    draw_fn(d, int(S * white), WHITE, 0)
    return im.resize((N, N), Image.LANCZOS)

def cam_follow():
    c = S / 2
    def draw(d, w, col, g):
        r = S * 0.11 + g                                     # you
        d.ellipse([c - r, c - r, c + r, c + r], fill=col)
        R = S * 0.33                                         # the view going round you
        d.arc([c - R, c - R, c + R, c + R], 200, 520 - 40, fill=col, width=w)
        # arrowhead at the arc's end (angle 120 degrees, PIL angles clockwise from east)
        import math
        t = math.radians(120)
        ex, ey = c + R * math.cos(t), c + R * math.sin(t)
        tx, ty = -math.sin(t), math.cos(t)                   # tangent, the way the arc runs
        nx, ny = math.cos(t), math.sin(t)
        L, H = S * 0.16 + g * 1.5, S * 0.11 + g * 1.5
        d.polygon([(ex + tx * L, ey + ty * L), (ex + nx * H, ey + ny * H), (ex - nx * H, ey - ny * H)], fill=col)
    return outlined(draw)

def cam_behind():
    def draw(d, w, col, g):
        # you: an arrow pointing up (the way you face)
        d.polygon([(S * 0.5, S * 0.08 - g), (S * 0.72 + g, S * 0.46 + g * 0.6), (S * 0.5, S * 0.38 + g * 0.3), (S * 0.28 - g, S * 0.46 + g * 0.6)], fill=col)
        # the view: a cone opening from a point behind you, looking past you
        ax, ay = S * 0.5, S * 0.9
        d.line([ax, ay, S * 0.2, S * 0.56], fill=col, width=w)
        d.line([ax, ay, S * 0.8, S * 0.56], fill=col, width=w)
        r = S * 0.07 + g
        d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=col)
    return outlined(draw)

def cam_free():
    c = S / 2
    def draw(d, w, col, g):
        L = S * 0.36
        d.line([c - L, c, c + L, c], fill=col, width=w)
        d.line([c, c - L, c, c + L], fill=col, width=w)
        H, T = S * 0.12 + g * 1.4, S * 0.44 + g
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tipx, tipy = c + dx * T, c + dy * T
            bx, by = c + dx * (T - H * 1.3), c + dy * (T - H * 1.3)
            d.polygon([(tipx, tipy), (bx - dy * H, by + dx * H), (bx + dy * H, by - dx * H)], fill=col)
    return outlined(draw)

def cell():
    p = 0.125  # inset: the outline's centre line runs at 1/8 and 7/8 of the texture
    # thick strokes: the square is drawn only a few pixels wide in the ring
    return strokes([], [[(p, p), (1 - p, p), (1 - p, 1 - p), (p, 1 - p)]], black=0.24, white=0.13)

os.makedirs(MEDIA, exist_ok=True)
for name, img in (('Needle', needle()), ('CamFollow', cam_follow()), ('CamBehind', cam_behind()), ('CamFree', cam_free()), ('Cell', cell())):
    write_tga(img, os.path.join(MEDIA, name + '.tga'))
    if os.path.isdir(SANDBOX_UI):
        img.save(os.path.join(SANDBOX_UI, 'media-' + name.lower() + '.png'))
    print('wrote', name)
