# AI Agent Handoff: Gnomish Positioning System (GPS)

This document provides a technical overview of the GPS project to help other AI agents understand the codebase and deployment workflow quickly.

## 🎯 Project Goal
Replace default World of Warcraft continent maps with high-resolution image tiles.

## 🏛️ Architecture & Core Components

### 1. Map Processing (`scripts/map_processor.py`)
- **Action**: Slices source images from `maps/` into 256x256 `.tga` tiles.
- **Output**: Writes tiles to `Interface/AddOns/GnomishPositioningSystem/Tiles/`.
- **Metadata**: Generates `MapData.lua` containing dimensions, rows, and columns for each MapID.
- **Requirement**: Source maps must be mapped to a numeric `mapID` in the `MAP_ID_MAPPING` dictionary.

### 2. WoW Addon (`Interface/AddOns/GnomishPositioningSystem/`)
- **Private Namespace**: All logic uses `local _, ns = ...` to prevent global pollution.
- **Mixins**: UI logic is encapsulated in `ns.MapOverlayMixin`.
- **Hooking**: Uses `hooksecurefunc(WorldMapFrame, "OnMapChanged", ...)` for safe, non-tainting interop.
- **Performance**:
    - **Tile Pooling**: Textures are reused from `ns.TilePool` during map changes to keep memory pressure (Garbage Collection) low.
    - **Throttling**: The overlay only updates on map changes, avoiding expensive `OnUpdate` polling.

## 📁 Directory Layout
- `maps/`: Source high-resolution PNG files.
- `scripts/`: Python utility scripts.
- `Interface/AddOns/GnomishPositioningSystem/`: The distribution-ready addon folder.

## 🚀 Deployment & Testing
After making changes to the addon or processing new maps, the folder should be exported to the World of Warcraft game directory for testing.

**Target Deployment Directory:**
`C:\Program Files (x86)\World of Warcraft\_anniversary_\Interface\AddOns`

### Common Workflow
1. Add/Update high-res images in `maps/`.
2. Run slicing script: `python scripts/map_processor.py`.
3. Copy the `GnomishPositioningSystem` folder to the target directory above.
4. In WoW, type `/reload` to see changes.

## 🛠️ Tech Stack
- **Python**: 3.x with `Pillow` (PIL) for image processing.
- **Lua**: 5.1/LuaJIT for the WoW client environment.
- **BLP/TGA**: Standard texture formats supported by WoW.
