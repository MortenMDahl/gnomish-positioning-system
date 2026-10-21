"""Paints the open sea of the overview images in one colour, #081110 (8, 17, 16).

The overview atlases (Interface/AddOns/GnomishPositioningSystem/Overview/*.jpg) are rectangles of
64 px tiles. Three things are repainted, each only where it is needed, so running it again changes nothing:

1. Empty tiles (tiles a map does not have) and the padding beyond an atlas's used part. browser_export.js
   filled them with #0f2434 until 2026-10-17; the game's own minimap images show open sea as #081110, the
   colour GPS also uses behind the 2D map and the 3D view, so zoomed out the sea turned a lighter blue where
   the map's tiles ended. The padding (since 2026-10-19): the game filters an atlas's last used pixels with
   the padding next to them, which drew a faint blue line along the atlas's edge in the sea.

2. The sea's second tone (since 2026-10-21). The game's minimap images draw the open sea in two tones,
   #081110 and a darker #080d10 (8, 13, 16), split along diagonals across the tiles (big triangles, a tile
   or more across; 42 % of the open sea inside Kalimdor's tiles, 38 % in the Eastern Kingdoms', is the
   darker one). Zoomed out in the 3D view that showed as a sawtooth of darker and lighter triangles. Every
   pixel of the sea's tones (within 2 levels of either, or between them, as the JPEG's edges leave them) in a
   patch of at least 256 such pixels becomes #081110; coasts' own shading (further from both tones) is kept.

3. Lines at the world's edge (since 2026-10-21). Some minimap images carry a 4-5 px line in a solid colour
   along a side that has no tile next to it: a tan L north-east of Azshara (Kalimdor tiles 45-47 in row 20,
   their north sides, and the east side of tile 47), magenta round Kalimdor's test squares at tile 0, 0.
   A run of rows from such a side that are at least 90 % not sea, with sea behind them (95 % of the next 12
   rows, the corners left out), is painted #081110 (with 2 rows more for the JPEG's ringing).

The images are saved again with their own JPEG quantisation tables and chroma subsampling, so the rest
stays as it was (on Kalimdor's land 0.17 levels off on average, 1.9 % of its pixels more than 2 levels off,
from decoding and encoding once more).

Usage: python scripts/fill_overview_sea.py   (then scripts/build_globe.py --land: the planet's pages and its
list of tiles with land are made from these images)
"""
import os
import re

import numpy as np
from PIL import Image, JpegImagePlugin
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "Interface", "AddOns", "GnomishPositioningSystem")
SEA = (8, 17, 16)   # #081110, open sea in the game's minimap images
DARK = (8, 13, 16)  # #080d10, the open sea's second tone in the same images
PX = 64             # overview pixels per tile (ns.OverviewPx)
MIN_PATCH = 256     # a patch of the sea's tones at least this big is open sea (not a dark pixel on land)


def sea_tone(a):
    """Pixels of the open sea's tones: within 2 levels of #081110 or #080d10, or between the two."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (np.abs(r - 8) <= 2) & (np.abs(b - 16) <= 2) & (g >= DARK[1] - 2) & (g <= SEA[1] + 2)


def sea_like(a):
    """Pixels that look like open sea of either tone (looser: the JPEG's noise round lines and coasts)."""
    return (np.abs(a - np.array(SEA)).max(-1) <= 6) | (np.abs(a - np.array(DARK)).max(-1) <= 6)


def tone_patches(a):
    """The sea's tones in patches of at least MIN_PATCH pixels (8-connected)."""
    tone = sea_tone(a)
    lab, n = ndimage.label(tone, structure=np.ones((3, 3), int))
    if n == 0:
        return tone & False
    sizes = ndimage.sum(tone, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= MIN_PATCH
    return keep[lab]


def edge_lines(a, cols, rows, have, x0, y0):
    """Boxes (x0, y0, x1, y1) of lines along tile sides with no tile next to them."""
    boxes = []
    sea = sea_like(a)
    for r in range(rows):
        for c in range(cols):
            tx, ty = x0 + c, y0 + r
            if ty * 64 + tx not in have:
                continue
            t = sea[r * PX:(r + 1) * PX, c * PX:(c + 1) * PX]
            # per side: the tile's rows counted from that side, and the neighbour across it
            sides = (
                ("N", t, (tx, ty - 1)),
                ("S", t[::-1], (tx, ty + 1)),
                ("W", t.T, (tx - 1, ty)),
                ("E", t.T[::-1], (tx + 1, ty)),
            )
            for side, s, (nx, ny) in sides:
                if 0 <= nx < 64 and 0 <= ny < 64 and ny * 64 + nx in have:
                    continue
                k = 0
                while k < 8 and (~s[k]).mean() >= 0.9:
                    k += 1
                # (behind it, the corners left out: a line along the next side crosses them)
                if k == 0 or s[k + 1:k + 13, 8:-8].mean() < 0.95:
                    continue
                k += 2
                X0, Y0 = c * PX, r * PX
                if side == "N":
                    boxes.append((X0, Y0, X0 + PX, Y0 + k))
                elif side == "S":
                    boxes.append((X0, Y0 + PX - k, X0 + PX, Y0 + PX))
                elif side == "W":
                    boxes.append((X0, Y0, X0 + k, Y0 + PX))
                else:
                    boxes.append((X0 + PX - k, Y0, X0 + PX, Y0 + PX))
    return boxes


def main():
    src = open(os.path.join(ADDON, "Data", "MapTiles.lua"), encoding="utf-8").read()
    maps = re.findall(r'\[(\d+)\] = \{\s*name = "[^"]*".*?atlases = \{(.*?)\},\s*tiles = \{(.*?)\},\s*\},', src, re.S)
    files = painted = padded = toned = lined = 0
    for _, atlases, tiles in maps:
        have = {int(k) for k in re.findall(r"\[(\d+)\]=", tiles)}
        for name, x0, y0, cols, rows in re.findall(r'file = "([^"]+)", x0 = (\d+), y0 = (\d+), cols = (\d+), rows = (\d+)', atlases):
            x0, y0, cols, rows = int(x0), int(y0), int(cols), int(rows)
            path = os.path.join(ADDON, "Overview", name + ".jpg")
            im = Image.open(path)
            w, h = im.size
            empty = [(c, r) for r in range(rows) for c in range(cols) if (y0 + r) * 64 + (x0 + c) not in have]
            todo = [(c, r) for c, r in empty if max(abs(a - b) for a, b in zip(im.getpixel((c * PX + PX // 2, r * PX + PX // 2)), SEA)) > 2]
            # the padding right of and below the used part (its middle pixel tells whether it is done)
            pads = [box for box in ((cols * PX, 0, w, h), (0, rows * PX, w, h)) if box[0] < box[2] and box[1] < box[3]]
            pads_todo = [b for b in pads if max(abs(a - c) for a, c in zip(im.getpixel(((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)), SEA)) > 2]
            a = np.asarray(im.convert("RGB")).astype(int)
            lines = edge_lines(a, cols, rows, have, x0, y0)
            # the darker tone left in the open sea, 8 px or more from anything else (the JPEG's noise round
            # coasts leaves a few such pixels next to them, which painting again would only make again)
            inner = ndimage.binary_erosion(tone_patches(a), structure=np.ones((17, 17), bool))
            dark_left = int((inner & (np.abs(a - np.array(DARK)).max(-1) <= 1)).sum())
            if not todo and not pads_todo and not lines and dark_left < 50:
                continue
            for c, r in empty:
                a[r * PX:(r + 1) * PX, c * PX:(c + 1) * PX] = SEA
            for b in pads:
                a[b[1]:b[3], b[0]:b[2]] = SEA
            for b in lines:
                a[b[1]:b[3], b[0]:b[2]] = SEA
            patch = tone_patches(a)
            a[patch] = SEA
            out = Image.fromarray(a.astype(np.uint8), "RGB")
            # with the image's own quantisation tables and chroma subsampling
            out.save(path, qtables=im.quantization, subsampling=JpegImagePlugin.get_sampling(im), optimize=True)
            files += 1
            painted += len(empty)
            padded += len(pads) > 0
            toned += int(patch.sum())
            lined += len(lines)
    print(f"{files} overview images changed: {painted} empty tiles painted {SEA}, padding in {padded}, "
          f"{toned} pixels of the sea's tones made {SEA}, {lined} lines at the world's edge painted over")


if __name__ == "__main__":
    main()
