"""Paints the empty tiles of the overview images in the open sea's colour.

The overview atlases (Interface/AddOns/GnomishPositioningSystem/Overview/*.jpg) are rectangles of
64 px tiles; tiles a map does not have were filled with #0f2434 by browser_export.js until
2026-10-17. The game's own minimap images show open sea as #081110 (8, 17, 16), so zoomed out the sea
turned a lighter blue where the map's tiles ended. This repaints those empty tiles #081110, the colour
GPS now also uses behind the 2D map and the 3D view (browser_export.js fills new exports with it).

Only the empty tiles change; the images are saved with their own JPEG quantisation ("keep"), so the
rest stays as it was. Running it again changes nothing visible.

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
    files = painted = 0
    for _, atlases, tiles in maps:
        have = {int(k) for k in re.findall(r"\[(\d+)\]=", tiles)}
        for name, x0, y0, cols, rows in re.findall(r'file = "([^"]+)", x0 = (\d+), y0 = (\d+), cols = (\d+), rows = (\d+)', atlases):
            x0, y0, cols, rows = int(x0), int(y0), int(cols), int(rows)
            path = os.path.join(ADDON, "Overview", name + ".jpg")
            im = Image.open(path)
            empty = [(c, r) for r in range(rows) for c in range(cols) if (y0 + r) * 64 + (x0 + c) not in have]
            todo = [(c, r) for c, r in empty if max(abs(a - b) for a, b in zip(im.getpixel((c * PX + PX // 2, r * PX + PX // 2)), SEA)) > 2]
            if not todo:
                continue
            im.load()
            for c, r in empty:
                im.paste(SEA, (c * PX, r * PX, (c + 1) * PX, (r + 1) * PX))
            im.save(path, quality="keep", subsampling="keep", optimize=True)
            files += 1
            painted += len(empty)
    print(f"{painted} empty tiles painted {SEA} in {files} overview images")


if __name__ == "__main__":
    main()
