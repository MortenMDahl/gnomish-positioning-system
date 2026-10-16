local addonName, ns = ...

-- Localize standard APIs for performance
local CreateFrame = CreateFrame
local UIParent = UIParent
local table_wipe = table.wipe
local next = next
local math_min = math.min
local math_max = math.max

-- Private Namespace Components
ns.TilePool = {}
ns.ActiveTiles = {}

-- Mixin for the Standalone Map Frame
ns.MapFrameMixin = {}

function ns.MapFrameMixin:OnLoad()
    -- Frame Setup
    self:SetSize(800, 600)
    self:SetPoint("CENTER")
    self:SetClampedToScreen(true)
    self:SetMovable(true)
    self:EnableMouse(true)
    self:EnableMouseWheel(true)
    self:SetResizable(true)
    if self.SetResizeBounds then
        self:SetResizeBounds(400, 300, 2000, 2000)
    end
    
    -- Background
    local bg = self:CreateTexture(nil, "BACKGROUND")
    bg:SetAllPoints()
    bg:SetColorTexture(0, 0, 0, 0.8)
    
    -- Title/Header for dragging
    local header = CreateFrame("Frame", nil, self)
    header:SetPoint("TOPLEFT")
    header:SetPoint("TOPRIGHT")
    header:SetHeight(24)
    header:EnableMouse(true)
    header:RegisterForDrag("LeftButton")
    header:SetScript("OnDragStart", function() self:StartMoving() end)
    header:SetScript("OnDragStop", function() self:StopMovingOrSizing() end)
    
    local title = header:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    title:SetPoint("CENTER")
    title:SetText("Gnomish Positioning System")

    local close = CreateFrame("Button", nil, header, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", 0, 0)
    
    -- Canvas for Tiles
    self.canvas = CreateFrame("Frame", nil, self)
    self.canvas:SetPoint("TOPLEFT", 0, -24)
    self.canvas:SetPoint("BOTTOMRIGHT", 0, 0)
    self.canvas:EnableMouse(true)

    -- State
    self.zoomLevel = 1.0
    self.offsetX = 0
    self.offsetY = 0
    self.dragging = false
    self.currentMapID = nil

    -- Scripts
    self:SetScript("OnMouseWheel", function(_, delta) self:OnMouseWheel(delta) end)
    self.canvas:SetScript("OnMouseDown", function(_, button)
        if button == "LeftButton" then
            self:StartPanning()
        end
    end)
    self.canvas:SetScript("OnMouseUp", function() self:StopPanning() end)
    self.canvas:SetScript("OnHide", function() self:StopPanning() end)
    
    -- Map Cycling (Simple selector for now)
    self.canvas:SetScript("OnMouseUp", function(_, button)
        if button == "RightButton" then
            self:CycleMap()
        else
            self:StopPanning()
        end
    end)

    self:Hide()
end

function ns.MapFrameMixin:CycleMap()
    local maps = {}
    for mapID, _ in pairs(ns.MapData) do
        table.insert(maps, mapID)
    end
    table.sort(maps)
    
    local nextIndex = 1
    for i, id in ipairs(maps) do
        if id == self.currentMapID then
            nextIndex = (i % #maps) + 1
            break
        end
    end
    self:UpdateMap(maps[nextIndex])
end

function ns.MapFrameMixin:OnMouseWheel(delta)
    local oldZoom = self.zoomLevel
    self.zoomLevel = math_max(0.1, math_min(20.0, self.zoomLevel + delta * 0.1 * self.zoomLevel))
    
    if oldZoom ~= self.zoomLevel then
        self:UpdateTiles()
    end
end

function ns.MapFrameMixin:StartPanning()
    self.dragging = true
    local startX, startY = GetCursorPosition()
    local scale = self:GetEffectiveScale()
    self.lastMouseX = startX / scale
    self.lastMouseY = startY / scale

    self:SetScript("OnUpdate", function()
        if not self.dragging then return end
        local curX, curY = GetCursorPosition()
        local s = self:GetEffectiveScale()
        curX, curY = curX / s, curY / s
        
        self.offsetX = self.offsetX + (curX - self.lastMouseX)
        self.offsetY = self.offsetY + (curY - self.lastMouseY)
        
        self.lastMouseX = curX
        self.lastMouseY = curY
        self:UpdateTiles()
    end)
end

function ns.MapFrameMixin:StopPanning()
    self.dragging = false
    self:SetScript("OnUpdate", nil)
end

function ns.MapFrameMixin:UpdateMap(mapID)
    self.currentMapID = mapID or self.currentMapID
    if not self.currentMapID then
        -- Default to first available map
        self.currentMapID = next(ns.MapData)
    end
    
    -- Reset Zoom/Pan
    self.zoomLevel = 1.0
    self.offsetX = 0
    self.offsetY = 0
    
    self:UpdateTiles()
end

function ns.MapFrameMixin:GetTile()
    local tile = next(ns.TilePool)
    if tile then
        ns.TilePool[tile] = nil
    else
        tile = self.canvas:CreateTexture(nil, "OVERLAY")
    end
    return tile
end

function ns.MapFrameMixin:ReleaseTiles()
    for tile, _ in pairs(ns.ActiveTiles) do
        tile:Hide()
        tile:ClearAllPoints()
        ns.TilePool[tile] = true
    end
    table_wipe(ns.ActiveTiles)
end

function ns.MapFrameMixin:UpdateTiles()
    self:ReleaseTiles()
    
    local data = ns.MapData[self.currentMapID]
    if not data then return end

    local canvasWidth, canvasHeight = self.canvas:GetSize()
    
    -- Base scale to fit continent to canvas
    local baseScale = math_min(canvasWidth / data.width, canvasHeight / data.height)
    local totalScale = baseScale * self.zoomLevel
    
    -- Center position
    local startX = (canvasWidth / 2) - (data.width * totalScale / 2) + self.offsetX
    local startY = (-canvasHeight / 2) + (data.height * totalScale / 2) + self.offsetY
    
    for r = 0, data.rows - 1 do
        for c = 0, data.cols - 1 do
            local tileX = startX + (c * data.tileSize * totalScale)
            local tileY = startY - (r * data.tileSize * totalScale)
            local tileSize = data.tileSize * totalScale

            if tileX + tileSize > 0 and tileX < canvasWidth and tileY - tileSize < 0 and tileY > -canvasHeight then
                local tile = self:GetTile()
                local texturePath = string.format("Interface\\AddOns\\GnomishPositioningSystem\\Tiles\\%d_%d_%d.tga", self.currentMapID, r, c)
                
                tile:SetTexture(texturePath)
                tile:SetSize(tileSize, tileSize)
                tile:SetPoint("TOPLEFT", self.canvas, "TOPLEFT", tileX, tileY)
                tile:Show()
                
                ns.ActiveTiles[tile] = true
            end
        end
    end
end

-- Initialize the standalone frame
local GPS_MainFrame = CreateFrame("Frame", "GPS_MainFrame", UIParent)
Mixin(GPS_MainFrame, ns.MapFrameMixin)
GPS_MainFrame:OnLoad()

-- Slash Command
SLASH_GPS1 = "/gps"
SlashCmdList["GPS"] = function()
    if GPS_MainFrame:IsShown() then
        GPS_MainFrame:Hide()
    else
        GPS_MainFrame:Show()
        GPS_MainFrame:UpdateMap()
    end
end

print("|cFF00FF00[GPS]|r Standalone frame loaded. Type /gps to toggle.")
