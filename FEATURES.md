# Feature list

Ideas to build, found while testing. Newest at the bottom; move an item to "Done" with the commit when it ships.

## To build

1. **Map picker from the title.** Clicking the map's name at the top left opens a menu of every map, sorted in folders (for example Continents, Kalimdor and Eastern Kingdoms zones, Dungeons, Raids, Battlegrounds, Forever's own maps), to jump straight to one instead of stepping through them with `<` `>`; easy to go back and forth between folders and maps. (2026-10-21)
2. **GPS as the minimap.** Use the tilted 3D view as the minimap: a small GPS view in place of the game's minimap, with your quests and arrow, as a setting such as "Use GPS as minimap" in GPS's settings. (2026-10-21)
3. **Steep cliffs without streaks.** The 3D ground is coloured from the top-down minimap images, which have no detail on steep faces, so steep cliffs (Orgrimmar's canyon) show stretched streaks; a rock colour or texture for steep faces would help. (2026-10-21)
4. **An uneven ground mesh.** Precompute for every tile an uneven mesh, dense along cliffs and ridges and sparse on flat ground and sea, at several levels (as the building blocks are), so the same triangle budget shows far more relief zoomed out (Mount Hyjal). The step chosen per tile by its roughness (2026-10-21, J1) is the first part of this. (2026-10-21, Morten's idea)

## Done

1. **Full screen.** A button next to the close button (X), with the art of Blizzard's own maximize / minimize arrow, makes the GPS window fill the screen in every mode (2D, 3D, traditional map), and back to exactly its saved place and size; remembered over a reload; `/gps fullscreen`. (2026-10-21, branch J6)
2. **Map key: GPS or Blizzard's map.** A globe button left of the maximize arrow on Blizzard's Map & Quest Log, and one next to the full-screen button in GPS's windows, choose what the game's map key (M) opens: GPS (in whichever mode it opens) or Blizzard's map, and switch at once. Also on the settings page ("Map key opens") and `/gps mapkey gps|blizzard`. Done with override bindings on the map key's keys, so nothing of Blizzard's is replaced. (2026-10-21, branch J6)
