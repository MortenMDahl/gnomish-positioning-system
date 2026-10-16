# Draws stand-ins for game art the sandbox has no copy of (the page shows these instead of the
# game's files; they only approximate the look, so judge layout here, art in the game):
#   minimap-background.png        Interface\Minimap\UI-Minimap-Background (dark disc behind a ring)
#   zoombutton-highlight.png      Interface\Minimap\UI-Minimap-ZoomButton-Highlight (hover glow)
#   atlas-redbutton-exit[-pressed].png, atlas-redbutton-highlight.png   the red close button atlases
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

disc(); glow()
redx('up'); redx('pressed'); redx('highlight')
