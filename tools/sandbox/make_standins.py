# Draws stand-ins for game art the sandbox has no copy of (the page shows these instead of the
# game's files; they only approximate the look, so judge layout here, art in the game):
#   minimap-background.png        Interface\Minimap\UI-Minimap-Background (dark disc behind a ring)
#   zoombutton-highlight.png      Interface\Minimap\UI-Minimap-ZoomButton-Highlight (hover glow)
#   atlas-redbutton-exit[-pressed].png, atlas-redbutton-highlight.png   the red close button atlases
#   atlas-redbutton-expand[-pressed].png, atlas-redbutton-condense[-pressed].png   the maximize / minimize
#                                 button atlases (an arrow to the top right corner, or back from it)
#   questpoi.png                  Interface\WorldMap\UI-QuestPoi-NumberIcons (the quest button's disc; tinted)
#   questblob.png                 a quest's objective area (the game draws these itself, QuestPOIFrame)
#   atlas-ui-hud-minimap-frame.png   the minimap's ring (Camelot's UI-HUD-Minimap-Frame, 215 x 226 round a 198 px minimap)
#   atlas-ui-hud-minimap-zoom-in.png, -zoom-out.png   the minimap's zoom buttons
# Usage: python make_standins.py
import os
from PIL import Image, ImageDraw, ImageFilter
UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site', 'ui')
K = 8

def canvas(n): return Image.new('RGBA', (n * K, n * K), (0, 0, 0, 0))
def done(im, n, name): im.resize((n, n), Image.LANCZOS).save(os.path.join(UI, name)); print('wrote', name)

def disc():
    n = 64; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    for i in range(40):
        t = i / 39; r = S * 0.48 * (1 - t)
        v = int(10 + 30 * t)
        d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=(v, int(v * 0.95), int(v * 0.8), 255))
    done(im, n, 'minimap-background.png')

def glow():
    n = 32; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    d.ellipse([S * 0.12, S * 0.12, S * 0.88, S * 0.88], outline=(255, 220, 120, 200), width=int(S * 0.1))
    im = im.filter(ImageFilter.GaussianBlur(S * 0.04))
    done(im, n, 'zoombutton-highlight.png')

def redx(state):
    n = 32; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    if state == 'highlight':
        d.rounded_rectangle([S * 0.1, S * 0.1, S * 0.9, S * 0.9], S * 0.16, outline=(255, 200, 120, 160), width=int(S * 0.08))
        return done(im.filter(ImageFilter.GaussianBlur(S * 0.03)), n, 'atlas-redbutton-highlight.png')
    d.rounded_rectangle([S * 0.08, S * 0.08, S * 0.92, S * 0.92], S * 0.16, fill=(0, 0, 0, 255))
    d.rounded_rectangle([S * 0.12, S * 0.12, S * 0.88, S * 0.88], S * 0.13, fill=(110, 110, 110, 255))
    top, bot = ((150, 30, 24), (80, 10, 8)) if state == 'up' else ((90, 14, 10), (60, 8, 6))
    for i in range(30):
        t = i / 29; col = tuple(int(top[k] + (bot[k] - top[k]) * t) for k in range(3)) + (255,)
        y0 = S * (0.17 + 0.66 * t); d.rectangle([S * 0.17, y0, S * 0.83, y0 + S * 0.03], fill=col)
    o = S * (0.03 if state == 'pressed' else 0)
    for col, w in (((0, 0, 0, 255), S * 0.13), ((232, 200, 130, 255), S * 0.08)):
        d.line([S * 0.32 + o, S * 0.32 + o, S * 0.68 + o, S * 0.68 + o], fill=col, width=int(w))
        d.line([S * 0.68 + o, S * 0.32 + o, S * 0.32 + o, S * 0.68 + o], fill=col, width=int(w))
    done(im, n, 'atlas-redbutton-exit.png' if state == 'up' else 'atlas-redbutton-exit-pressed.png')

def redarrow(kind, state):
    # the red button as in redx, with a gold diagonal arrow: expand points to the top right corner,
    # condense back toward the middle
    n = 32; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    d.rounded_rectangle([S * 0.08, S * 0.08, S * 0.92, S * 0.92], S * 0.16, fill=(0, 0, 0, 255))
    d.rounded_rectangle([S * 0.12, S * 0.12, S * 0.88, S * 0.88], S * 0.13, fill=(110, 110, 110, 255))
    top, bot = ((150, 30, 24), (80, 10, 8)) if state == 'up' else ((90, 14, 10), (60, 8, 6))
    for i in range(30):
        t = i / 29; col = tuple(int(top[k] + (bot[k] - top[k]) * t) for k in range(3)) + (255,)
        y0 = S * (0.17 + 0.66 * t); d.rectangle([S * 0.17, y0, S * 0.83, y0 + S * 0.03], fill=col)
    o = S * (0.03 if state == 'pressed' else 0)
    a, b = (0.32, 0.68), (0.68, 0.32)               # tail, head (expand: toward the top right)
    if kind == 'condense': a, b = (0.70, 0.30), (0.36, 0.64)
    hx, hy = b; tx, ty = a
    ux, uy = (hx - tx), (hy - ty); L = (ux * ux + uy * uy) ** 0.5; ux, uy = ux / L, uy / L
    head = [(hx, hy), (hx - ux * 0.2 - uy * 0.12, hy - uy * 0.2 + ux * 0.12), (hx - ux * 0.2 + uy * 0.12, hy - uy * 0.2 - ux * 0.12)]
    for col, w, g in (((0, 0, 0, 255), S * 0.13, 0.035), ((232, 200, 130, 255), S * 0.07, 0)):
        d.line([tx * S + o, ty * S + o, (hx - ux * 0.1) * S + o, (hy - uy * 0.1) * S + o], fill=col, width=int(w))
        pts = [((x + (x - hx) * 0 ) * S + o, y * S + o) for x, y in head]
        if g:
            cx = sum(p[0] for p in pts) / 3; cy = sum(p[1] for p in pts) / 3
            pts = [(cx + (px - cx) * 1.35, cy + (py - cy) * 1.35) for px, py in pts]
        d.polygon(pts, fill=col)
    done(im, n, f'atlas-redbutton-{kind}' + ('' if state == 'up' else '-pressed') + '.png')

def questpoi():
    n = 32; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    d.ellipse([S * 0.08, S * 0.08, S * 0.92, S * 0.92], fill=(20, 14, 4, 255))
    d.ellipse([S * 0.15, S * 0.15, S * 0.85, S * 0.85], fill=(255, 255, 255, 255))
    done(im, n, 'questpoi.png')

def questblob():
    # transparent margin all round, so a stretched copy shows nothing outside the ellipse
    n = 128; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    d.ellipse([S * 0.04, S * 0.04, S * 0.96, S * 0.96], fill=(240, 200, 60, 70), outline=(255, 215, 80, 200), width=int(S * 0.025))
    done(im, n, 'questblob.png')

def minimapframe():
    # 215 x 226 like the atlas; the minimap (198 px) centred, a gold ring over its edge and a knob at the top
    W, H = 215 * 4, 226 * 4; im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx, cy, r = W / 2, H / 2, 99 * 4
    d.ellipse([cx - r - 9 * 4, cy - r - 9 * 4, cx + r + 9 * 4, cy + r + 9 * 4], outline=(40, 28, 10, 255), width=12 * 4)
    d.ellipse([cx - r - 7 * 4, cy - r - 7 * 4, cx + r + 7 * 4, cy + r + 7 * 4], outline=(196, 160, 82, 255), width=8 * 4)
    d.ellipse([cx - r - 4 * 4, cy - r - 4 * 4, cx + r + 4 * 4, cy + r + 4 * 4], outline=(240, 214, 140, 255), width=2 * 4)
    im.resize((215, 226), Image.LANCZOS).save(os.path.join(UI, 'atlas-ui-hud-minimap-frame.png')); print('wrote atlas-ui-hud-minimap-frame.png')

def zoombutton(sign):
    n = 17; im = canvas(n); d = ImageDraw.Draw(im); S = n * K
    d.ellipse([S * 0.05, S * 0.05, S * 0.95, S * 0.95], fill=(40, 28, 10, 255), outline=(196, 160, 82, 255), width=int(S * 0.1))
    d.rectangle([S * 0.28, S * 0.45, S * 0.72, S * 0.55], fill=(240, 214, 140, 255))
    if sign == 'in': d.rectangle([S * 0.45, S * 0.28, S * 0.55, S * 0.72], fill=(240, 214, 140, 255))
    done(im, n, 'atlas-ui-hud-minimap-zoom-%s.png' % sign)

disc(); glow(); questpoi(); questblob(); minimapframe(); zoombutton('in'); zoombutton('out')
for kind in ('expand', 'condense'):
    for state in ('up', 'pressed'): redarrow(kind, state)
redx('up'); redx('pressed'); redx('highlight')
