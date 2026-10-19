"""Paints the empty tiles of the overview images in the open sea's colour.

The overview atlases (Interface/AddOns/GnomishPositioningSystem/Overview/*.jpg) are rectangles of
64 px tiles; tiles a map does not have were filled with #0f2434 by browser_export.js until
2026-10-17. The game's own minimap images show open sea as #081110 (8, 17, 16), so zoomed out the sea
turned a lighter blue where the map's tiles ended. This repaints those empty tiles #081110, the colour
GPS now also uses behind the 2D map and the 3D view (browser_export.js fills new exports with it).

Since 2026-10-19 it also paints the padding beyond an atlas's used part (its last column and row of tiles
end before the image's power-of-two size; that part was #0f2434 too): the game filters the image's last
used pixels with the padding next to them, which drew a faint blue line along an atlas's edge in the sea,
and zoomed out on the 2D map, with both continents in view, many of those edges show.

Only the empty tiles and the padding change; the images are saved with their own JPEG quantisation
("keep"), so the rest stays as it was. Running it again changes nothing visible.

Usage: python scripts/fill_overview_sea.py
"""
import os
import re

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "Interface", "AddOns", "GnomishPositioningSystem")
SEA = (8, 17, 16)  # #081110, open sea in the game's minimap images
PX = 64            # overview pixels per tile (ns.OverviewPx)


def main():
    src = open(os.path.join(ADDON, "Data", "MapTiles.lua"), encoding="utf-8").read()
    maps = re.findall(r'\[(\d+)\] = \{\s*name = "[^"]*".*?atlases = \{(.*?)\},\s*tiles = \{(.*?)\},\s*\},', src, re.S)
    files = painted = padded = 0
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
            if not todo and not pads_todo:
                continue
            im.load()
            for c, r in empty:
                im.paste(SEA, (c * PX, r * PX, (c + 1) * PX, (r + 1) * PX))
            for b in pads:
                im.paste(SEA, b)
            im.save(path, quality="keep", subsampling="keep", optimize=True)
            files += 1
            painted += len(empty)
            padded += len(pads) > 0
    print(f"{painted} empty tiles painted {SEA}, padding painted in {padded}, in {files} overview images")


if __name__ == "__main__":
    main()
