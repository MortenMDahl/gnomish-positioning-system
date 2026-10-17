-- GPS sandbox: a small World of Warcraft UI engine, enough to run Gnomish Positioning System and
-- GPS3D unchanged outside the game. Frames, textures (with SetVertexOffset), font strings, anchors,
-- frame levels and strata, clipping, mouse input, OnUpdate, events, timers, slash commands,
-- SavedVariables, GameTooltip and a ModelScene that draws simple stand-in models.
--
-- The host (sandbox.js) calls SANDBOX_* functions and gets back a draw list as one string.
-- Coordinates are UI units with the origin at the bottom left of the screen, y up, scale 1.

local S = { time = 0, W = 1024, H = 768, cx = 0, cy = 0, dirty = true, gen = 1, order = 0, epoch = 1 }
SANDBOX = S
local objects, frames = {}, {}
local floor, ceil, min, max, abs, sqrt, sin, cos, tan, pi = math.floor, math.ceil, math.min, math.max, math.abs, math.sqrt, math.sin, math.cos, math.tan, math.pi
local mtype = math.type
local tconcat = table.concat

------------------------------------------------------------------------------------------------
-- Lua 5.1 behaviour the game has and Lua 5.4 does not
------------------------------------------------------------------------------------------------
local rawformat = string.format
local function toint(v)
	if mtype(v) == "float" then
		if v ~= v or v == math.huge or v == -math.huge then return 0 end
		v = v < 0 and ceil(v) or floor(v)
		return math.tointeger(v) or 0
	end
	return v
end
-- %d with a fraction is an error in 5.4; WoW (5.1) truncates.
string.format = function(fmt, ...)
	local args = table.pack(...)
	local i = 0
	for spec in fmt:gmatch("%%[-+ #0]*%d*%.?%d*([%a%%])") do
		if spec ~= "%" then
			i = i + 1
			if (spec == "d" or spec == "i" or spec == "x" or spec == "X" or spec == "c" or spec == "o") and type(args[i]) == "number" then
				args[i] = toint(args[i])
			end
		end
	end
	return rawformat(fmt, table.unpack(args, 1, args.n))
end
format = string.format
local rawtostring = tostring
tostring = function(v)
	if type(v) == "number" then return rawformat("%.14g", v) end
	return rawtostring(v)
end
unpack = table.unpack
loadstring = load
math.pow = function(a, b) return a ^ b end
math.mod = math.fmod
table.getn = function(t) return #t end
strtrim = function(s, chars) s = s or ""; return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
strsplit = function(sep, s, limit)
	local out, pos = {}, 1
	while true do
		if limit and #out == limit - 1 then out[#out + 1] = s:sub(pos) break end
		local a, b = s:find(sep, pos, true)
		if not a then out[#out + 1] = s:sub(pos) break end
		out[#out + 1] = s:sub(pos, a - 1)
		pos = b + 1
	end
	return table.unpack(out)
end
strlower, strupper, strlen, strsub, strfind, strmatch, gsub = string.lower, string.upper, string.len, string.sub, string.find, string.match, string.gsub
tinsert, tremove, sort = table.insert, table.remove, table.sort
wipe = function(t) for k in pairs(t) do t[k] = nil end return t end
issecretvalue = nil

------------------------------------------------------------------------------------------------
-- Chat, errors
------------------------------------------------------------------------------------------------
S.chat = {}
local function chat(line) S.chat[#S.chat + 1] = line end
S.chatLine = chat
print = function(...)
	local parts = {}
	for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
	chat(tconcat(parts, " "))
end
-- Lua errors go to the error handler (the game's shows them; addons may hook it with seterrorhandler)
local function defaultHandler(err) chat("|cffff4040Lua error:|r " .. tostring(err)) end
local function report(err)
	local h = S.errorHandler or defaultHandler
	local ok, e2 = pcall(h, err)
	if not ok then defaultHandler(err); defaultHandler("in the error handler: " .. tostring(e2)) end
end
function seterrorhandler(f) S.errorHandler = f end
function geterrorhandler() return S.errorHandler or defaultHandler end
function debugstack(start) return debug.traceback("", (start or 1) + 1) end
local function call(f, ...)
	if not f then return end
	local ok, a, b, c, d = xpcall(f, function(e) return debug.traceback(tostring(e), 2) end, ...)
	if not ok then report(a) return end
	return a, b, c, d
end
S.call = call
local warned = {}
local function notSimulated(kind, name)
	local key = kind .. ":" .. name
	if not warned[key] then
		warned[key] = true
		chat(("|cffffa040[sandbox]|r %s:%s is not simulated (call ignored)"):format(kind, name))
	end
end

------------------------------------------------------------------------------------------------
-- Classes
------------------------------------------------------------------------------------------------
local classes = {}
-- Methods resolve through plain tables (fast); a method the sandbox lacks resolves, at the end of
-- the chain, to a stub that reports it once and does nothing.
local function missing(_, k)
	if type(k) == "string" and k:match("^[A-Z]") then
		return function(self)
			local mt = type(self) == "table" and getmetatable(self)
			notSimulated(mt and mt._class or "?", k)
		end
	end
	return nil
end
local function class(name, base)
	local c = { _class = name }
	c.__index = c
	setmetatable(c, { __index = base or missing })
	classes[name] = c
	return c
end
local Object = class("Object")
local Region = class("Region", Object)
local Texture = class("Texture", Region)
local FontString = class("FontString", Region)
local Frame = class("Frame", Region)
local Button = class("Button", Frame)
local EditBox = class("EditBox", Frame)
local ModelScene = class("ModelScene", Frame)
local Actor = class("Actor", Object)
local function rawget2(t, k) return rawget(t, k) end

local function new(cls, parent, name)
	S.order = S.order + 1
	local o = setmetatable({ _parent = parent, _shown = true, _alpha = 1, _points = {}, _order = S.order, _scripts = {} }, cls)
	objects[#objects + 1] = o
	if name then o._name = name; _G[name] = o end
	S.dirty = true
	return o
end

local function touch() S.dirty = true end
-- Layout cache: a region's rectangle stays valid until its own anchors or size change, or those of
-- something it is anchored to (each region remembers who is anchored to it).
local function invalidate(o)
	if o._rvalid == false then return end
	o._rvalid = false
	local deps = o._deps
	if deps then for d in pairs(deps) do invalidate(d) end end
end
local function relayout(o) S.dirty = true; invalidate(o or S.UIParent) end

-- Object basics
function Object:GetName() return self._name end
function Object:GetObjectType() return getmetatable(self)._class end
function Object:IsObjectType(t)
	local c = getmetatable(self)
	while type(c) == "table" do
		if c._class == t then return true end
		local m = getmetatable(c)
		c = m and m.__index
	end
	return false
end
function Object:GetParent() return self._parent end
function Object:SetParent(p) self._parent = p; relayout(self) end
function Object:SetAlpha(a) self._alpha = a; self._sv = (self._sv or 0) + 1; touch() end
function Object:GetAlpha() return self._alpha end
function Object:Show() self:SetShown(true) end
function Object:Hide() self:SetShown(false) end
function Object:IsShown() return self._shown end
function Object:IsVisible()
	local o = self
	while o do if not o._shown then return false end; o = o._parent end
	return true
end

------------------------------------------------------------------------------------------------
-- Anchors and layout
------------------------------------------------------------------------------------------------
local POINTS = { TOPLEFT = { 0, 1 }, TOP = { 0.5, 1 }, TOPRIGHT = { 1, 1 }, LEFT = { 0, 0.5 }, CENTER = { 0.5, 0.5 }, RIGHT = { 1, 0.5 }, BOTTOMLEFT = { 0, 0 }, BOTTOM = { 0.5, 0 }, BOTTOMRIGHT = { 1, 0 } }

function Region:SetPoint(point, a, b, c, d)
	point = point:upper()
	assert(POINTS[point], "SetPoint: unknown anchor point " .. tostring(point))
	local rel, relPoint, x, y
	if type(a) == "number" then
		rel, relPoint, x, y = nil, point, a, b or 0
	elseif type(b) == "number" then
		rel, relPoint, x, y = a, point, b, c or 0
	else
		rel, relPoint, x, y = a, b and b:upper() or point, c or 0, d or 0
	end
	if type(rel) == "string" then rel = _G[rel] end
	rel = rel or self._parent or S.UIParent
	assert(POINTS[relPoint], "SetPoint: unknown relative point " .. tostring(relPoint))
	for i, p in ipairs(self._points) do
		if p[1] == point then table.remove(self._points, i) break end
	end
	self._points[#self._points + 1] = { point, rel, relPoint, x, y }
	local deps = rel._deps
	if not deps then deps = {}; rel._deps = deps end
	deps[self] = true
	relayout(self)
end
function Region:ClearAllPoints() self._points = {}; relayout(self) end
function Region:SetAllPoints(rel)
	rel = rel or self._parent
	self._points = {}
	self:SetPoint("TOPLEFT", rel, "TOPLEFT", 0, 0)
	self:SetPoint("BOTTOMRIGHT", rel, "BOTTOMRIGHT", 0, 0)
end
function Region:GetPoint(i)
	local p = self._points[i or 1]
	if p then return p[1], p[2], p[3], p[4], p[5] end
end
function Region:GetNumPoints() return #self._points end
function Region:SetSize(w, h) self._w, self._h = w, h; relayout(self) end
function Region:SetWidth(w) self._w = w; relayout(self) end
function Region:SetHeight(h) self._h = h; relayout(self) end

local function intrinsicSize(o)
	if o._isText then
		local w = S.measure(o._text or "", o._font)
		return o._w or w, o._h or (o._font.size + 2)
	end
	return o._w or 0, o._h or 0
end

-- Returns left, bottom, right, top, or nil when the region has no usable anchors.
local function rect(o)
	if o._rvalid then
		if not o._l then return nil end
		return o._l, o._b, o._r, o._t
	end
	o._rvalid = true
	o._l = nil
	if o == S.UIParent then
		o._l, o._b, o._r, o._t = 0, 0, S.W, S.H
		return 0, 0, S.W, S.H
	end
	if #o._points == 0 then return nil end
	local left, right, cx, bottom, top, cy
	for _, p in ipairs(o._points) do
		local rl, rb, rr, rt = rect(p[2])
		if not rl then return nil end
		local rp = POINTS[p[3]]
		local ax, ay = rl + (rr - rl) * rp[1] + p[4], rb + (rt - rb) * rp[2] + p[5]
		local mp = POINTS[p[1]]
		if mp[1] == 0 then left = ax elseif mp[1] == 1 then right = ax else cx = ax end
		if mp[2] == 0 then bottom = ay elseif mp[2] == 1 then top = ay else cy = ay end
	end
	local w, h = intrinsicSize(o)
	if left and right then
	elseif left then right = left + w
	elseif right then left = right - w
	elseif cx then left, right = cx - w / 2, cx + w / 2
	else return nil end
	if bottom and top then
	elseif bottom then top = bottom + h
	elseif top then bottom = top - h
	elseif cy then bottom, top = cy - h / 2, cy + h / 2
	else return nil end
	o._l, o._b, o._r, o._t = left, bottom, right, top
	return left, bottom, right, top
end
S.rect = rect

function Region:GetLeft() local l = rect(self); return l end
function Region:GetRight() local _, _, r = rect(self); return r end
function Region:GetTop() local _, _, _, t = rect(self); return t end
function Region:GetBottom() local _, b = rect(self); return b end
function Region:GetCenter() local l, b, r, t = rect(self); if l then return (l + r) / 2, (b + t) / 2 end end
function Region:GetRect() local l, b, r, t = rect(self); if l then return l, b, r - l, t - b end end
function Region:GetSize()
	local l, b, r, t = rect(self)
	if l then return r - l, t - b end
	return intrinsicSize(self)
end
function Region:GetWidth() local w = self:GetSize(); return w end
function Region:GetHeight() local _, h = self:GetSize(); return h end
function Region:GetEffectiveScale() return 1 end
function Region:GetScale() return 1 end
function Region:SetScale() touch() end
function Region:IsMouseOver()
	local l, b, r, t = rect(self)
	return l and S.cx >= l and S.cx <= r and S.cy >= b and S.cy <= t or false
end
function Region:SetShown(show)
	show = not not show
	if self._shown == show then return end
	self._shown = show
	touch()
end

------------------------------------------------------------------------------------------------
-- Textures
------------------------------------------------------------------------------------------------
local LAYERS = { BACKGROUND = 1, BORDER = 2, ARTWORK = 3, OVERLAY = 4, HIGHLIGHT = 5 }

local function newTexture(parent, layer, sub)
	local t = new(Texture, parent)
	t._layer = LAYERS[layer or "ARTWORK"] or 3
	t._sub = sub or 0
	t._color = { 1, 1, 1, 1 }
	parent._regions[#parent._regions + 1] = t
	parent._sortOK = false
	return t
end

function Texture:SetTexture(file)
	if type(file) == "string" then file = file:lower():gsub("/", "\\") end
	self._file = file
	self._sv = (self._sv or 0) + 1
	touch()
	return file ~= nil
end
function Texture:GetTexture() return self._file end
function Texture:GetTextureFileID() return type(self._file) == "number" and self._file or nil end
function Texture:SetColorTexture(r, g, b, a)
	self._file = "interface\\buttons\\white8x8"
	self._color = { r, g, b, a or 1 }
	self._sv = (self._sv or 0) + 1
	touch()
end
function Texture:SetVertexColor(r, g, b, a) self._color = { r, g, b, a or 1 }; self._sv = (self._sv or 0) + 1; touch() end
function Texture:GetVertexColor() local c = self._color; return c[1], c[2], c[3], c[4] end
function Texture:SetTexCoord(...)
	local n = select("#", ...)
	if n == 4 then
		local l, r, t, b = ...
		self._tc = { l, t, l, b, r, t, r, b }
	elseif n == 8 then
		self._tc = { ... }
	else
		error("SetTexCoord takes 4 or 8 numbers")
	end
	self._sv = (self._sv or 0) + 1
	touch()
end
function Texture:GetTexCoord() local c = self._tc or { 0, 0, 0, 1, 1, 0, 1, 1 }; return table.unpack(c) end
function Texture:SetVertexOffset(i, x, y)
	local v = self._vo
	if not v then v = { 0, 0, 0, 0, 0, 0, 0, 0 }; self._vo = v end
	v[i * 2 - 1], v[i * 2] = x, y
	S.dirty = true
end
function Texture:GetVertexOffset(i) local v = self._vo; if not v then return 0, 0 end return v[i * 2 - 1], v[i * 2] end
function Texture:SetRotation(r) self._rot = r; self._sv = (self._sv or 0) + 1; touch() end
function Texture:GetRotation() return self._rot or 0 end
function Texture:SetGradient(orientation, minColor, maxColor)
	self._grad = { orientation:upper(), minColor, maxColor }
	self._sv = (self._sv or 0) + 1
	touch()
end
local function setDrawLayer(self, layer, sub)
	local nl, ns = LAYERS[layer] or 3, sub or 0
	if nl ~= self._layer or ns ~= self._sub then
		self._layer, self._sub = nl, ns
		self._parent._sortOK = false
		S.dirty = true
	end
end
Texture.SetDrawLayer = setDrawLayer
function Texture:GetDrawLayer() for k, v in pairs(LAYERS) do if v == self._layer then return k, self._sub end end end
function Texture:SetBlendMode() end
function Texture:SetDesaturated() end
function Texture:SetHorizTile() end
function Texture:SetVertTile() end
function Texture:SetSnapToPixelGrid() end
function Texture:SetTexelSnappingBias() end
function Texture:IsObjectLoaded() return S.isLoaded(self._file) end
-- Atlases: drawn from "atlas:<name>" (the page maps the ones GPS uses to images in ui/).
local ATLAS_SIZE = {
	["ui-hud-minimap-zoom-in"] = { 17, 17 }, ["ui-hud-minimap-zoom-out"] = { 17, 17 },
	["redbutton-exit"] = { 24, 24 },
}
function Texture:SetAtlas(name, useAtlasSize)
	if type(name) ~= "string" then return false end
	self._atlas = name
	self:SetTexture("atlas:" .. name:lower())
	self:SetTexCoord(0, 1, 0, 1)
	local size = ATLAS_SIZE[name:lower()]
	if useAtlasSize and size then self:SetSize(size[1], size[2]) end
	return true
end
function Texture:GetAtlas() return self._atlas end
function Texture:SetParent(p)
	local old = self._parent
	if old == p then return end
	local regs = old._regions
	for i = #regs, 1, -1 do if regs[i] == self then table.remove(regs, i) break end end
	old._sortOK = false
	self._parent = p
	p._regions[#p._regions + 1] = self
	p._sortOK = false
	invalidate(self)
	S.dirty = true
end

------------------------------------------------------------------------------------------------
-- Font strings
------------------------------------------------------------------------------------------------
local FONTS = {
	GameFontNormal = { size = 12, color = { 1, 0.82, 0, 1 } },
	GameFontNormalSmall = { size = 10, color = { 1, 0.82, 0, 1 } },
	GameFontNormalLarge = { size = 16, color = { 1, 0.82, 0, 1 } },
	GameFontNormalHuge = { size = 20, color = { 1, 0.82, 0, 1 } },
	GameFontNormalTiny = { size = 9, color = { 1, 0.82, 0, 1 } },
	GameFontNormalTiny2 = { size = 8, color = { 1, 0.82, 0, 1 } },
	GameFontHighlight = { size = 12, color = { 1, 1, 1, 1 } },
	GameFontHighlightSmall = { size = 10, color = { 1, 1, 1, 1 } },
	GameFontHighlightLarge = { size = 16, color = { 1, 1, 1, 1 } },
	GameFontDisable = { size = 12, color = { 0.5, 0.5, 0.5, 1 } },
	GameFontDisableSmall = { size = 10, color = { 0.5, 0.5, 0.5, 1 } },
	GameTooltipText = { size = 12, color = { 1, 1, 1, 1 } },
	GameTooltipHeaderText = { size = 14, color = { 1, 1, 1, 1 } },
	ChatFontNormal = { size = 13, color = { 1, 1, 1, 1 } },
	NumberFontNormal = { size = 12, color = { 1, 1, 1, 1 } },
}
for name, f in pairs(FONTS) do f.name = name; _G[name] = f end
local DEFAULT_FONT = FONTS.GameFontNormal

local function newFontString(parent, layer, inherits)
	local fs = new(FontString, parent)
	fs._isText = true
	fs._layer = LAYERS[layer or "ARTWORK"] or 3
	fs._sub = 0
	local font = type(inherits) == "string" and FONTS[inherits] or type(inherits) == "table" and inherits or DEFAULT_FONT
	fs._font = font
	fs._color = { font.color[1], font.color[2], font.color[3], font.color[4] }
	fs._justify = 1
	parent._regions[#parent._regions + 1] = fs
	parent._sortOK = false
	return fs
end
function FontString:SetText(t)
	t = t ~= nil and tostring(t) or ""
	if t ~= self._text then self._text = t; relayout(self) end
end
function FontString:SetFormattedText(fmt, ...) self:SetText(string.format(fmt, ...)) end
function FontString:GetText() return self._text end
function FontString:SetTextColor(r, g, b, a) self._color = { r, g, b, a or 1 }; touch() end
function FontString:GetTextColor() local c = self._color; return c[1], c[2], c[3], c[4] end
function FontString:SetFontObject(f) if type(f) == "string" then f = FONTS[f] end; self._font = f or DEFAULT_FONT; self._baseFont = nil; relayout(self) end
function FontString:GetFontObject() return self._baseFont or self._font end
-- Text scale: drawn and measured at the font's size times the scale.
function FontString:SetTextScale(scale)
	local base = self._baseFont or self._font
	if scale == 1 then self._font, self._baseFont = base, nil
	else self._baseFont = base; self._font = { size = base.size * scale, color = base.color, name = base.name } end
	relayout(self)
end
function FontString:GetTextScale() local b = self._baseFont; return b and self._font.size / b.size or 1 end
function FontString:SetFont(_, size) self._font = { size = size or 12, color = self._font.color, name = "custom" }; self._baseFont = nil; relayout(self) end
function FontString:SetJustifyH(j) self._justify = ({ LEFT = 0, CENTER = 1, RIGHT = 2 })[j:upper()] or 1; touch() end
function FontString:SetJustifyV() end
function FontString:SetWordWrap(w) self._wrap = w; touch() end
function FontString:SetNonSpaceWrap() end
function FontString:SetMaxLines() end
function FontString:SetShadowColor() end
function FontString:SetShadowOffset() end
FontString.SetDrawLayer = setDrawLayer
function FontString:GetStringWidth() return S.measure(self._text or "", self._font) end
function FontString:GetStringHeight() return self._font.size + 2 end
function FontString:GetUnboundedStringWidth() return S.measure(self._text or "", self._font) end
FontString.SetParent = Texture.SetParent

S.measureCache = {}
function S.measure(text, font)
	if text == "" then return 0 end
	local key = font.size .. "\1" .. text
	local w = S.measureCache[key]
	if not w then
		w = SANDBOX_MEASURE and SANDBOX_MEASURE(text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""), font.size) or #text * font.size * 0.55
		S.measureCache[key] = w
	end
	return w
end

------------------------------------------------------------------------------------------------
-- Frames
------------------------------------------------------------------------------------------------
local STRATA = { WORLD = 0, BACKGROUND = 1, LOW = 2, MEDIUM = 3, HIGH = 4, DIALOG = 5, FULLSCREEN = 6, FULLSCREEN_DIALOG = 7, TOOLTIP = 8 }

local function initFrame(f, parent)
	f._regions = {}
	f._children = {}
	f._level = parent and (parent._level + 1) or 0
	f._events = {}
	f._mouse = false
	if parent then parent._children[#parent._children + 1] = f end
	frames[#frames + 1] = f
end

local function fireShowHide(f, shown)
	-- OnShow/OnHide for this frame and its visible children, as the game does
	local s = f._scripts[shown and "OnShow" or "OnHide"]
	if s then call(s, f) end
	for _, c in ipairs(f._children) do
		if c._shown then fireShowHide(c, shown) end
	end
end

function Frame:SetShown(show)
	show = not not show
	if self._shown == show then return end
	local wasVisible = self:IsVisible()
	self._shown = show
	touch()
	if wasVisible ~= self:IsVisible() then fireShowHide(self, show) end
end
function Frame:SetScript(event, f) self._scripts[event] = f end
function Frame:GetScript(event) return self._scripts[event] end
function Frame:HookScript(event, f)
	local old = self._scripts[event]
	self._scripts[event] = old and function(...) old(...); return f(...) end or f
end
function Frame:HasScript() return true end
function Frame:RegisterEvent(e) self._events[e] = true end
function Frame:UnregisterEvent(e) self._events[e] = nil end
function Frame:UnregisterAllEvents() self._events = {} end
function Frame:IsEventRegistered(e) return self._events[e] == true end
function Frame:CreateTexture(name, layer, inherits, sub)
	local t = newTexture(self, layer, sub)
	if name then t._name = name; _G[name] = t end
	return t
end
function Frame:CreateFontString(name, layer, inherits)
	local fs = newFontString(self, layer, inherits)
	if name then fs._name = name; _G[name] = fs end
	return fs
end
function Frame:SetFrameLevel(l) self._level = l; touch() end
function Frame:GetFrameLevel() return self._level end
function Frame:SetFrameStrata(s) self._strata = s:upper(); touch() end
function Frame:GetFrameStrata()
	local o = self
	while o do if o._strata then return o._strata end; o = o._parent end
	return "MEDIUM"
end
function Frame:Raise() self._level = self._level + 1; touch() end
function Frame:Lower() end
function Frame:SetToplevel() end
function Frame:EnableMouse(on) self._mouse = not not on end
function Frame:IsMouseEnabled() return self._mouse end
-- (the game splits mouse input into clicks and motion; the sandbox keeps one switch for both)
function Frame:IsMouseClickEnabled() return self._mouse end
function Frame:IsMouseMotionEnabled() return self._mouse end
function Frame:SetMouseClickEnabled(on) self._mouse = not not on end
function Frame:SetMouseMotionEnabled(on) self._mouse = not not on end
function Frame:SetMouseClickEnabled(on) self._mouse = not not on end
function Frame:SetMouseMotionEnabled() end
function Frame:EnableMouseWheel(on) self._wheel = not not on end
function Frame:IsMouseWheelEnabled() return self._wheel end
function Frame:EnableKeyboard() end
function Frame:SetPropagateKeyboardInput() end
function Frame:SetClipsChildren(on) self._clips = not not on; touch() end
function Frame:DoesClipChildren() return self._clips end
function Frame:SetMovable(on) self._movable = on end
function Frame:IsMovable() return self._movable end
function Frame:SetResizable(on) self._resizable = on end
function Frame:IsResizable() return self._resizable end
function Frame:SetResizeBounds(a, b, c, d) self._bounds = { a, b, c, d } end
function Frame:SetMinResize(a, b) self._bounds = { a, b, 1e5, 1e5 } end
function Frame:SetClampedToScreen(on) self._clamped = on end
function Frame:SetHitRectInsets() end
function Frame:SetUserPlaced() end
function Frame:RegisterForDrag(...) self._drag = {}; for _, b in ipairs({ ... }) do self._drag[b] = true end end
function Frame:RegisterForClicks() end
function Frame:GetChildren() return table.unpack(self._children) end
function Frame:GetRegions() return table.unpack(self._regions) end
function Frame:SetID(id) self._id = id end
function Frame:GetID() return self._id or 0 end
function Frame:SetAttribute(k, v) self._attr = self._attr or {}; self._attr[k] = v end
function Frame:GetAttribute(k) return self._attr and self._attr[k] end

local function absTopLeft(f)
	local l, b, r, t = rect(f)
	f:ClearAllPoints()
	f:SetPoint("TOPLEFT", S.UIParent, "BOTTOMLEFT", l, t)
	f._w, f._h = r - l, t - b
end
function Frame:StartMoving()
	if not self._movable then return end
	local l, _, _, t = rect(self)
	if not l then return end
	S.moving = { frame = self, dx = S.cx - l, dy = S.cy - t }
end
function Frame:StartSizing(point)
	if not self._resizable then return end
	absTopLeft(self)
	local l, b, r, t = rect(self)
	S.sizing = { frame = self, point = (point or "BOTTOMRIGHT"):upper(), dx = S.cx - r, dy = S.cy - b }
end
function Frame:StopMovingOrSizing()
	if S.moving and S.moving.frame == self then S.moving = nil end
	if S.sizing and S.sizing.frame == self then S.sizing = nil end
end

-- BackdropTemplate
local function applyTemplate(f, template)
	if not template then return end
	for t in template:gmatch("[^,%s]+") do
		if t == "BackdropTemplate" then
			f.SetBackdrop = function(self, info) self._backdrop = info; touch() end
			f.GetBackdrop = function(self) return self._backdrop end
			f.SetBackdropColor = function(self, r, g, b, a) self._bdColor = { r, g, b, a or 1 }; touch() end
			f.SetBackdropBorderColor = function(self, r, g, b, a) self._bdBorder = { r, g, b, a or 1 }; touch() end
			f.ApplyBackdrop = function() end
		elseif t == "MapCanvasFrameScrollContainerTemplate" then
			S.makeMapScroll(f) -- the stand-in for Blizzard's map (below)
		elseif t == "POIButtonTemplate" then
			S.makePOIButton(f) -- the stand-in for Blizzard's quest button (below)
		elseif S.xmlTemplates and S.xmlTemplates[t] then
			S.xmlTemplates[t](f) -- templates a test or the page defines (other addons' XML)
		end
	end
end

-- Edit boxes: the text is kept and its first lines drawn; focus and highlight are remembered.
local EDIT_LINES = 60
function EditBox:SetMultiLine(v) self._multi = v end
function EditBox:SetAutoFocus(v) self._autoFocus = v end
function EditBox:SetMaxLetters(n) self._maxLetters = n end
function EditBox:SetTextInsets() end
function EditBox:SetFontObject(f)
	if not self._fs then self._fs = self:CreateFontString(nil, "ARTWORK"); self._fs:SetPoint("TOPLEFT"); self._fs:SetJustifyH("LEFT") end
	self._fs:SetFontObject(f)
end
function EditBox:SetText(t)
	self._editText = tostring(t or "")
	if not self._fs then self:SetFontObject("GameFontHighlightSmall") end
	local shown, n = {}, 0
	for line in (self._editText .. "\n"):gmatch("(.-)\n") do
		n = n + 1
		if n > EDIT_LINES then break end
		shown[n] = line
	end
	self._fs:SetText(table.concat(shown, "\n"))
end
function EditBox:GetText() return self._editText or "" end
function EditBox:SetFocus() S.focus = self end
function EditBox:ClearFocus() if S.focus == self then S.focus = nil end end
function EditBox:HasFocus() return S.focus == self end
function EditBox:HighlightText(a, b) self._highlight = { a or 0, b or -1 } end
function EditBox:GetNumLetters() return #(self._editText or "") end
function Frame:SetScrollChild(child)
	self._scrollChild = child
	child:ClearAllPoints()
	child:SetPoint("TOPLEFT", self, "TOPLEFT", 0, 0)
end
function Frame:GetScrollChild() return self._scrollChild end
function Frame:SetVerticalScroll(v) self._vs = v; touch() end
function Frame:GetVerticalScroll() return self._vs or 0 end
function Frame:SetHorizontalScroll(v) self._hs = v; touch() end
function Frame:GetHorizontalScroll() return self._hs or 0 end

-- Buttons
function Button:SetNormalTexture(file)
	if not self._normal then self._normal = newTexture(self, "ARTWORK"); self._normal:SetAllPoints(self) end
	self._normal:SetTexture(file)
end
function Button:SetHighlightTexture(file)
	if not self._highlight then self._highlight = newTexture(self, "HIGHLIGHT"); self._highlight:SetAllPoints(self) end
	self._highlight:SetTexture(file)
end
function Button:SetPushedTexture(file)
	if not self._pushed then self._pushed = newTexture(self, "ARTWORK"); self._pushed:SetAllPoints(self); self._pushed._isPushed = true end
	self._pushed:SetTexture(file)
end
function Button:SetNormalAtlas(name)
	if not self._normal then self._normal = newTexture(self, "ARTWORK"); self._normal:SetAllPoints(self) end
	self._normal:SetAtlas(name)
end
function Button:SetHighlightAtlas(name)
	if not self._highlight then self._highlight = newTexture(self, "HIGHLIGHT"); self._highlight:SetAllPoints(self) end
	self._highlight:SetAtlas(name)
end
function Button:SetPushedAtlas(name)
	if not self._pushed then self._pushed = newTexture(self, "ARTWORK"); self._pushed:SetAllPoints(self); self._pushed._isPushed = true end
	self._pushed:SetAtlas(name)
end
function Button:GetNormalTexture() return self._normal end
function Button:GetHighlightTexture() return self._highlight end
function Button:GetPushedTexture() return self._pushed end
function Button:SetText(t)
	if not self._fs then self._fs = newFontString(self, "OVERLAY", "GameFontNormal"); self._fs:SetPoint("CENTER") end
	self._fs:SetText(t)
end
function Button:GetText() return self._fs and self._fs._text end
function Button:Click(button) local s = self._scripts.OnClick; if s then call(s, self, button or "LeftButton", false) end end
function Button:Enable() self._disabled = nil end
function Button:Disable() self._disabled = true end
function Button:IsEnabled() return not self._disabled end
function Button:SetEnabled(on) self._disabled = not on end
function Button:LockHighlight() end
function Button:UnlockHighlight() end
function Button:SetButtonState() end
function Button:SetFontString(fs) self._fs = fs end
function Button:GetFontString() return self._fs end

------------------------------------------------------------------------------------------------
-- ModelScene with stand-in models
------------------------------------------------------------------------------------------------
function ModelScene:CreateActor()
	local a = new(Actor, self)
	a._pos, a._yaw, a._pitch, a._roll, a._scale = { 0, 0, 0 }, 0, 0, 0, 1
	self._actors[#self._actors + 1] = a
	return a
end
function ModelScene:SetCameraPosition(x, y, z) self._cam.pos = { x, y, z }; touch() end
function ModelScene:GetCameraPosition() local p = self._cam.pos; return p[1], p[2], p[3] end
function ModelScene:SetCameraOrientationByYawPitchRoll(y, p, r) self._cam.yaw, self._cam.pitch, self._cam.roll = y, p, r; touch() end
function ModelScene:SetCameraFieldOfView(f) self._cam.fov = f; touch() end
function ModelScene:GetCameraFieldOfView() return self._cam.fov end
function ModelScene:SetCameraNearClip(n) self._cam.near = n end
function ModelScene:SetCameraFarClip(f) self._cam.far = f end
function ModelScene:GetCameraNearClip() return self._cam.near end
function ModelScene:GetCameraFarClip() return self._cam.far end
function ModelScene:SetLightVisible(v) self._light.visible = v end
function ModelScene:SetLightDirection(x, y, z) local l = sqrt(x * x + y * y + z * z); self._light.dir = { x / l, y / l, z / l } end
function ModelScene:SetLightAmbientColor() end
function ModelScene:SetLightDiffuseColor() end
function ModelScene:SetLightType() end
function ModelScene:SetLightPosition() end
function ModelScene:SetFogNear() end
function ModelScene:SetFogFar() end
function ModelScene:SetFogColor() end
function ModelScene:ClearFog() end
function ModelScene:SetViewInsets() end
function ModelScene:SetDrawLayer() end
-- Blizzard's convention: forward = (cosP cosY, cosP sinY, -sinP); right and up follow from it.
local function sceneBasis(cam)
	local Y, P = cam.yaw, cam.pitch
	local fx, fy, fz = cos(P) * cos(Y), cos(P) * sin(Y), -sin(P)
	local rx, ry, rz = sin(Y), -cos(Y), 0
	local ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx
	return fx, fy, fz, rx, ry, rz, ux, uy, uz
end
function ModelScene:GetCameraForward() local f = { sceneBasis(self._cam) }; return f[1], f[2], f[3] end
function ModelScene:GetCameraRight() local f = { sceneBasis(self._cam) }; return f[4], f[5], f[6] end
function ModelScene:GetCameraUp() local f = { sceneBasis(self._cam) }; return f[7], f[8], f[9] end
function ModelScene:Project3DPointTo2D(x, y, z)
	local l, b, r, t = rect(self)
	if not l then return nil end
	local fx, fy, fz, rx, ry, rz, ux, uy, uz = sceneBasis(self._cam)
	local p = self._cam.pos
	local dx, dy, dz = x - p[1], y - p[2], z - p[3]
	local d = dx * fx + dy * fy + dz * fz
	if d <= 0 then return nil end
	local F = ((t - b) / 2) / tan(self._cam.fov / 2)
	return ((dx * rx + dy * ry + dz * rz) * F / d + (r - l) / 2) / (r - l), ((dx * ux + dy * uy + dz * uz) * F / d + (t - b) / 2) / (t - b), d
end

function Actor:SetModelByUnit(unit) self._model = "unit:" .. tostring(unit); touch(); return true end
-- File models load after S.modelLoadDelay seconds (0 by default). Buildings (WMOs, by GPS3D_API.ModelInfo)
-- never load while SANDBOX_WMO is false: the case where the game refuses them.
function Actor:SetModelByFileID(id)
	self._model = "file:" .. tostring(id); self._fileID = id; self._loadAt = S.time + (S.modelLoadDelay or 0); touch()
	S.modelLoads = (S.modelLoads or 0) + 1
	return true
end
local infoMemo = {}
local function modelInfo(id)
	local m = id and infoMemo[id]
	if m then return m[1], m[2], m[3], m[4] end
	local f = rawget(_G, "GPS3D_API") and GPS3D_API.ModelInfo
	if not (f and id) then return nil end
	local r, lo, hi, wmo = f(id)
	if r then infoMemo[id] = { r, lo, hi, wmo } end
	return r, lo, hi, wmo
end
function Actor:SetModelByCreatureDisplayID(id) self._model = "display:" .. tostring(id); touch(); return true end
function Actor:ClearModel() self._model = nil; self._fileID = nil; touch() end
function Actor:IsLoaded()
	if not self._model then return false end
	if self._fileID then
		if S.time < (self._loadAt or 0) then return false end
		local _, _, _, wmo = modelInfo(self._fileID)
		if wmo and SANDBOX_WMO == false then return false end
	end
	return true
end
-- Model-space box (Vector3DMixin-like tables); zeros until loaded, as the game's would be.
function Actor:GetActiveBoundingBox()
	local r, lo, hi = 0, 0, 0
	if self:IsLoaded() then
		if self._fileID then
			r, lo, hi = modelInfo(self._fileID)
			if not r then r, lo, hi = 1, 0, 2 end
		else r, lo, hi = 0.5, 0, 1.8 end
	end
	local function v(x, y, z) return { x = x, y = y, z = z, GetXYZ = function(t) return t.x, t.y, t.z end } end
	return v(-r, -r, lo), v(r, r, hi)
end
function Actor:GetModelFileID() return self._fileID end
function Actor:SetPosition(x, y, z) self._pos = { x, y, z }; touch() end
function Actor:GetPosition() local p = self._pos; return p[1], p[2], p[3] end
function Actor:SetYaw(y) self._yaw = y; touch() end
function Actor:GetYaw() return self._yaw end
function Actor:SetPitch(p) self._pitch = p; touch() end
function Actor:SetRoll(r) self._roll = r; touch() end
function Actor:SetScale(s) self._scale = s; touch() end
function Actor:GetScale() return self._scale end
function Actor:SetShown(v) self._shown = not not v; touch() end
function Actor:SetAlpha(a) self._alpha = a; touch() end
function Actor:SetAnimation() end
function Actor:SetSpellVisualKit() end
function Actor:SetUseCenterForOrigin() end

------------------------------------------------------------------------------------------------
-- CreateFrame
------------------------------------------------------------------------------------------------
function CreateFrame(kind, name, parent, template)
	if type(parent) == "string" then parent = _G[parent] end
	parent = parent or S.UIParent
	local cls = classes[kind] or Frame
	if kind == "CheckButton" then cls = Button end
	local f = new(cls, parent, name)
	initFrame(f, parent)
	if cls == Button then f._mouse = true end
	if cls == ModelScene then
		f._actors = {}
		f._cam = { pos = { 0, 0, 0 }, yaw = 0, pitch = 0, roll = 0, fov = 0.9, near = 0.2, far = 100 }
		f._light = { visible = true, dir = { 0, 0, -1 } }
	end
	applyTemplate(f, template)
	if kind == "QuestPOIFrame" then S.makeQuestPOIFrame(f) end
	if template and template:find("ModelSceneActorTemplate") then return f end
	return f
end

S.UIParent = setmetatable({ _shown = true, _alpha = 1, _points = {}, _order = 0, _scripts = {} }, Frame)
initFrame(S.UIParent, nil)
S.UIParent._strata = "MEDIUM"
UIParent = S.UIParent
WorldFrame = S.UIParent

------------------------------------------------------------------------------------------------
-- Game API stand-ins
------------------------------------------------------------------------------------------------
S.player = { X = 0, Y = 0, Z = 0, map = 0, facing = 0, zone = "", subzone = "", mapUI = nil, mapX = nil, mapY = nil }
function UnitPosition(unit)
	if unit ~= "player" then return nil end
	local p = S.player
	if p.map == nil then return nil end
	return p.X, p.Y, p.Z, p.map
end
function GetPlayerFacing() return S.player.facing end
-- Zone texts: from the zone data (zones.lua) where it covers your position, else what the host says
-- (a dungeon, or a map the data does not cover).
function S.zoneTexts()
	local p = S.player
	if p.map ~= nil and p.X and S.zoneAt then
		local zone, sub = S.zoneAt(p.map, p.X, p.Y)
		if zone then return zone, sub or "" end
	end
	return p.zone, p.subzone
end
function GetZoneText() return (S.zoneTexts()) end
function GetSubZoneText() return select(2, S.zoneTexts()) end
function GetRealZoneText() return (S.zoneTexts()) end
function GetMinimapZoneText() local z, sub = S.zoneTexts(); return sub ~= "" and sub or z end
function SANDBOX_ZONETEXT() local z, sub = S.zoneTexts(); return (z or "") .. "\t" .. (sub or "") end
function IsInInstance() if S.player.map == nil then return true, "party" end return false, "none" end
function UnitName() return "Sandbox" end
function UnitClass() return "Warrior", "WARRIOR" end
function UnitRace() return "Human", "Human" end
function UnitExists(u) return u == "player" end
function GetCursorPosition() return S.cx, S.cy end
function GetScreenWidth() return S.W end
function GetScreenHeight() return S.H end
function GetTime() return S.time end
function time() return os.time() end
function date(...) return os.date(...) end
function debugprofilestop() return os.clock() * 1000 end
function GetFramerate() return S.fps or 60 end
function GetBuildInfo() return "1.60.1", "sandbox", "Oct 2026", 16001 end
function GetLocale() return "enUS" end
function InCombatLockdown() return false end
function IsShiftKeyDown() return false end
function IsControlKeyDown() return false end
function IsAltKeyDown() return false end
-- the TOC fields the host passes (SANDBOX_ADDONMETA), else nothing
S.addonMeta = {}
function GetAddOnMetadata(addon, key) return S.addonMeta[addon] and S.addonMeta[addon][key] end
function SANDBOX_ADDONMETA(addon, key, value) S.addonMeta[addon] = S.addonMeta[addon] or {}; S.addonMeta[addon][key] = value end
C_AddOns = { IsAddOnLoaded = function(n) return S.loadedAddons[n] == true end, GetAddOnMetadata = GetAddOnMetadata }
function UpdateAddOnMemoryUsage() end
function GetAddOnMemoryUsage() return 0 end -- unknown here (the game measures each addon)
IsAddOnLoaded = C_AddOns.IsAddOnLoaded
S.loadedAddons = {}

-- Mixins and vectors (Blizzard's SharedXML has these)
function Mixin(object, ...)
	for i = 1, select("#", ...) do
		for k, v in pairs((select(i, ...))) do object[k] = v end
	end
	return object
end
function CreateFromMixins(...) return Mixin({}, ...) end
-- The game's post-hook: the original runs first and its results are returned; the hook then sees the
-- same arguments. (Taint, the reason for the "secure" in its name, is not simulated.)
function hooksecurefunc(t, name, hook)
	if type(t) == "string" then t, name, hook = _G, t, name end
	local orig = t[name]
	assert(type(orig) == "function", "hooksecurefunc: " .. tostring(name) .. " is not a function")
	t[name] = function(...)
		local r = table.pack(orig(...))
		hook(...)
		return table.unpack(r, 1, r.n)
	end
end
local function vec2(x, y) return { x = x, y = y, GetXY = function(v) return v.x, v.y end } end
CreateVector2D = vec2
C_AddOns.LoadAddOn = function() return true end

-- uiMaps, stand-ins for a few of the game's maps (not the game's data): name, parent, and for maps
-- that lie in the world a box in world yards (top = north X, bottom, left = west Y, right) on a
-- continent; dungeon floors share a group. Child maps are found by their boxes (or `at`, a box in
-- the parent's 0..1 coordinates, for the continents on the world map).
S.uiMaps = {
	[947] = { name = "Azeroth", parent = 0, mapType = 1 },
	[1415] = { name = "Eastern Kingdoms", parent = 947, continent = 0, box = { 4800, -15800, 4600, -5800 }, at = { 0.56, 0.12, 0.96, 0.92 } },
	[1414] = { name = "Kalimdor", parent = 947, continent = 1, box = { 11800, -11800, 3800, -7400 }, at = { 0.04, 0.14, 0.40, 0.90 } },
	[1453] = { name = "Stormwind City", parent = 1415, continent = 0, box = { -8250, -9150, 1250, 250 } },
	[1436] = { name = "Westfall", parent = 1415, continent = 0, box = { -9550, -11750, 2300, 250 } },
	[1429] = { name = "Elwynn Forest", parent = 1415, continent = 0, box = { -8250, -10150, 1050, -1550 } },
	[1426] = { name = "Dun Morogh", parent = 1415, continent = 0, box = { -4500, -6400, 1300, -1800 } },
	[1411] = { name = "Durotar", parent = 1414, continent = 1, box = { 1900, -1100, -3800, -5600 } },
	[291] = { name = "The Deadmines", parent = 1436, group = 1, floor = 1, floorName = "The Deadmines" },
	[292] = { name = "The Deadmines", parent = 1436, group = 1, floor = 2, floorName = "Ironclad Cove" },
}
S.uiMapOrder = { 1453, 1436, 1429, 1426, 1411, 1415, 1414, 947, 291, 292 } -- smallest first
local function inBox(b, X, Y) return X <= b[1] and X >= b[2] and Y <= b[3] and Y >= b[4] end
local function toMap(b, X, Y) return (b[3] - Y) / (b[3] - b[4]), (b[1] - X) / (b[1] - b[2]) end
local function toWorld(b, x, y) return b[1] - y * (b[1] - b[2]), b[3] - x * (b[3] - b[4]) end
S.uiMapToWorld = toWorld
S.uiMapFromWorld = toMap

C_Map = {}
-- The zone you are in (from your position), or what the host says (in a dungeon).
function C_Map.GetBestMapForUnit(unit)
	local p = S.player
	if unit == "player" and p.map ~= nil and p.X and S.mapAt then
		local id = S.mapAt(p.map, p.X, p.Y)
		if id then return id end
	end
	if unit == "player" and p.map ~= nil and p.X then
		for _, id in ipairs(S.uiMapOrder) do
			local m = S.uiMaps[id]
			if m.box and m.continent == p.map and not m.at and inBox(m.box, p.X, p.Y) then return id end
		end
		for _, id in ipairs(S.uiMapOrder) do
			local m = S.uiMaps[id]
			if m.box and m.continent == p.map and inBox(m.box, p.X, p.Y) then return id end
		end
	end
	return p.mapUI
end
-- Your position on a map: worked out from the map's box; in a dungeon (no world position) what the
-- host gives for its map.
function C_Map.GetPlayerMapPosition(ui, unit)
	local p, m = S.player, S.uiMaps[ui]
	if not ui then return nil end
	if p.map ~= nil and p.X and m and m.box then
		if m.continent ~= p.map then return nil end
		local x, y = toMap(m.box, p.X, p.Y)
		return vec2(x, y)
	end
	if ui == p.mapUI and p.mapX ~= nil then return vec2(p.mapX, p.mapY) end
	return nil
end
function C_Map.GetWorldPosFromMapPos(ui, pos)
	local m = S.uiMaps[ui]
	if not (m and m.box and pos) then return nil end
	local X, Y = toWorld(m.box, pos.x, pos.y)
	return m.continent, vec2(X, Y)
end
function C_Map.GetMapPosFromWorldPos(continent, pos)
	local zone = S.mapAt and S.mapAt(continent, pos.x, pos.y)
	if zone then
		local x, y = toMap(S.uiMaps[zone].box, pos.x, pos.y)
		return zone, vec2(x, y)
	end
	for _, id in ipairs(S.uiMapOrder) do
		if S.mapAt and S.uiMaps[id].zoneArea then goto continue end -- zones only through the zone data

		local m = S.uiMaps[id]
		if m.box and m.continent == continent and inBox(m.box, pos.x, pos.y) then
			local x, y = toMap(m.box, pos.x, pos.y)
			return id, vec2(x, y)
		end
		::continue::
	end
	return nil
end
-- map types (Enum.UIMapType): Azeroth a world map, the two continents, dungeon floors; the rest zones
function S.uiMapType(id)
	local m = S.uiMaps[id]
	if not m then return 3 end
	return m.mapType or (m.group and 4) or (m.continent and m.at and 2) or 3
end
function C_Map.GetMapInfo(id)
	local m = S.uiMaps[id]
	if not m then return { mapID = id, name = S.player.zone, parentMapID = 0, mapType = 3 } end
	return { mapID = id, name = m.name, parentMapID = m.parent, mapType = S.uiMapType(id) }
end
function C_Map.GetMapChildrenInfo(id, mapType, all)
	local out = {}
	local function add(parent)
		for _, cid in ipairs(S.uiMapOrder) do
			local c = S.uiMaps[cid]
			if c.parent == parent then
				if not mapType or S.uiMapType(cid) == mapType then out[#out + 1] = { mapID = cid, name = c.name, mapType = S.uiMapType(cid), parentMapID = parent } end
				if all then add(cid) end
			end
		end
	end
	add(id)
	return out
end
function C_Map.GetMapGroupID(id) local m = S.uiMaps[id]; return m and m.group end
function C_Map.GetMapGroupMembersInfo(group)
	local out = {}
	for id, m in pairs(S.uiMaps) do
		if m.group == group then out[#out + 1] = { mapID = id, relativeHeightIndex = m.floor, name = m.floorName } end
	end
	return out
end
function C_Map.GetMapArtLayers() return { { layerWidth = 1002, layerHeight = 668, minScale = 1, maxScale = 1, additionalZoomSteps = 0 } } end
MapUtil = {}
function MapUtil.GetDisplayableMapForPlayer() return C_Map.GetBestMapForUnit("player") or 947 end

------------------------------------------------------------------------------------------------
-- Zones (site/zones.lua, from make_zones.py): every zone of the two continents. The area of each
-- 33-yard chunk gives the zone and subzone at a point (zone texts, the zone map at a point); each
-- zone is a stand-in uiMap whose rectangle is the box around its chunks. Loaded after this file
-- (it calls SANDBOX_USEZONES); without it, the few made-up boxes above stand in.
------------------------------------------------------------------------------------------------
function SANDBOX_USEZONES()
	local Z = SANDBOX_ZONES
	local TILE = 1600 / 3
	S.areaRuns = {}
	for map, str in pairs(Z.runs) do
		local starts, vals, pos, n = {}, {}, 0, 0
		for v, c in str:gmatch("(%d+) (%d+)") do
			n = n + 1
			starts[n], vals[n] = pos, tonumber(v)
			pos = pos + tonumber(c)
		end
		S.areaRuns[map] = { starts = starts, vals = vals, n = n }
	end
	S.zoneUiMap, S.cityMaps = {}, {}
	for _, z in ipairs(Z.zones) do
		local id, area, name, map, box = z[1], z[2], z[3], z[4], z[5]
		local old = S.uiMaps[id]
		S.uiMaps[id] = { name = name, parent = map == 0 and 1415 or 1414, continent = map, box = box, zoneArea = area ~= 0 and area or nil, city = area == 0 or nil }
		if old and old.group then S.uiMaps[id].group = old.group end
		if area ~= 0 then S.zoneUiMap[area] = id else S.cityMaps[#S.cityMaps + 1] = id end
	end
	-- smallest first (the zone map at a point is the smallest that holds it), then the rest
	local order = {}
	for id, m in pairs(S.uiMaps) do order[#order + 1] = id end
	local function size(id) local b = S.uiMaps[id].box; return b and (b[1] - b[2]) * (b[3] - b[4]) or math.huge end
	table.sort(order, function(a, b) local sa, sb = size(a), size(b); if sa ~= sb then return sa < sb end return a < b end)
	S.uiMapOrder = order
	-- the area at a world point (0 or nil: none)
	function S.areaAt(map, X, Y)
		local r = S.areaRuns[map]
		if not (r and X and Y) then return nil end
		local cx, cy = math.floor((32 - Y / TILE) * 16), math.floor((32 - X / TILE) * 16)
		if cx < 0 or cy < 0 or cx > 1023 or cy > 1023 then return nil end
		local k = cy * 1024 + cx
		local lo, hi = 1, r.n
		while lo < hi do
			local mid = (lo + hi + 1) // 2
			if r.starts[mid] <= k then lo = mid else hi = mid - 1 end
		end
		local a = r.vals[lo]
		return a ~= 0 and a or nil
	end
	-- zone name and subzone name ("" in the zone itself) at a world point
	function S.zoneAt(map, X, Y)
		for _, id in ipairs(S.cityMaps) do
			local m = S.uiMaps[id]
			if m.continent == map and inBox(m.box, X, Y) then
				local a = S.areaAt(map, X, Y)
				local info = a and Z.areas[a]
				return m.name, info and info[1] ~= m.name and info[1] or ""
			end
		end
		local a = S.areaAt(map, X, Y)
		local info = a and Z.areas[a]
		if not info then return nil end
		local zone = Z.areas[info[2]]
		if not (zone and S.zoneUiMap[info[2]]) then return nil end
		return zone[1], a ~= info[2] and info[1] or ""
	end
	-- the zone map (uiMap ID) at a world point, or nil (the sea, or no data)
	function S.mapAt(map, X, Y)
		for _, id in ipairs(S.cityMaps) do
			local m = S.uiMaps[id]
			if m.continent == map and inBox(m.box, X, Y) then return id end
		end
		local a = S.areaAt(map, X, Y)
		local info = a and Z.areas[a]
		return info and S.zoneUiMap[info[2]]
	end
	S.placeQuests()
end

------------------------------------------------------------------------------------------------
-- Quests, stand-ins (not the game's data): a few quests in Elwynn Forest and Westfall with a point
-- and an objective area (an ellipse, in the zone's 0..1 coordinates of the stand-in uiMaps above),
-- the quest log calls GPS makes, super-tracking, Blizzard's quest button (POIButtonTemplate: a gold
-- disc with the quest's number, "?" when complete; click tracks) and the quest-area frame
-- (QuestPOIFrame: draws the area ellipses of the quests it is asked to, answers the hit-test).
------------------------------------------------------------------------------------------------
Enum = Enum or {}
Enum.UIMapType = { Cosmic = 0, World = 1, Continent = 2, Zone = 3, Dungeon = 4, Micro = 5, Orphan = 6 }
S.cvars = { questPOI = true }
function GetCVarBool(name) return S.cvars[name] end
function GetCVar(name) local v = S.cvars[name]; if v == nil then return nil end return v and "1" or "0" end
-- point: world X, Y; at: the area's middle (X, Y) and half-sizes in yards (north-south, east-west)
S.quests = {
	{ questID = 33, title = "Wolves Across the Border", zone = 1429, point = { -9067, -68 }, objectives = { { "Tough Wolf Meat: 3/8", false } }, at = { -9086, -68, 114, 117 } },
	{ questID = 7, title = "Kobold Camp Cleanup", zone = 1429, point = { -8839, -302 }, objectives = { { "Kobold Vermin slain: 6/10", false } }, at = { -8839, -328, 66, 78 } },
	{ questID = 60, title = "Kobold Candles", zone = 1429, point = { -9770, 140 }, objectives = { { "Large Candle: 2/8", false } }, at = { -9789, 140, 76, 91 } },
	{ questID = 176, title = "Wanted: \"Hogger\"", zone = 1429, point = { -9884, 608 }, objectives = { { "Huge Gnoll Claw: 0/1", false } }, at = { -9903, 634, 57, 78 } },
	{ questID = 62, title = "The Fargodeep Mine", zone = 1429, point = { -9466, 10 }, objectives = {}, complete = true },
	{ questID = 65, title = "The Defias Brotherhood", zone = 1436, point = { -10628, 1029 }, objectives = { { "Speak with Gryan Stoutmantle", false } } },
	{ questID = 38, title = "Westfall Stew", zone = 1436, point = { -10210, 1378 }, objectives = { { "Stringy Vulture Meat: 1/3", false } }, at = { -10232, 1378, 132, 144 } },
}
S.questByID = {}
for i, q in ipairs(S.quests) do q.index = i; S.questByID[q.questID] = q end
-- each quest's point (x, y) and area (middle x, y, half-sizes) in its zone's 0..1 coordinates
function S.placeQuests()
	for _, q in ipairs(S.quests) do
		local b = S.uiMaps[q.zone].box
		q.x, q.y = S.uiMapFromWorld(b, q.point[1], q.point[2])
		if q.at then
			local ax, ay = S.uiMapFromWorld(b, q.at[1], q.at[2])
			q.area = { ax, ay, q.at[4] / (b[3] - b[4]), q.at[3] / (b[1] - b[2]) }
		end
	end
end
S.placeQuests()
S.superTracked = 33
S.questStamp = 1
local function questsChanged(event)
	S.questStamp = S.questStamp + 1
	SANDBOX_FIRE(event or "QUEST_LOG_UPDATE")
end
C_QuestLog = {}
function C_QuestLog.GetQuestsOnMap(ui)
	local out = {}
	for _, q in ipairs(S.quests) do
		if q.zone == ui then out[#out + 1] = { questID = q.questID, x = q.x, y = q.y, mapID = ui, numObjectives = #q.objectives, isQuestStart = false, isDaily = false, isCombatAllyQuest = false, isMeta = false, inProgress = not q.complete, isMapIndicatorQuest = false } end
	end
	return out
end
function C_QuestLog.GetTitleForQuestID(id) local q = S.questByID[id]; return q and q.title end
function C_QuestLog.GetLogIndexForQuestID(id) local q = S.questByID[id]; return q and q.index end
function C_QuestLog.GetMaxNumQuests() return 35 end
function C_QuestLog.GetQuestObjectives(id)
	local q = S.questByID[id]
	if not q then return nil end
	local out = {}
	for _, o in ipairs(q.objectives) do out[#out + 1] = { text = o[1], type = "monster", finished = o[2] } end
	return out
end
function C_QuestLog.IsComplete(id) local q = S.questByID[id]; return q and q.complete or false end
function C_QuestLog.AddQuestWatch() end
function C_QuestLog.RemoveQuestWatch() end
function GetNumQuestLeaderBoards(index) local q = S.quests[index]; return q and #q.objectives or 0 end
function GetQuestLogLeaderBoard(i, index)
	local o = S.quests[index] and S.quests[index].objectives[i]
	if not o then return nil end
	return o[1], "monster", o[2]
end
C_SuperTrack = {}
function C_SuperTrack.GetSuperTrackedQuestID() return S.superTracked or 0 end
function C_SuperTrack.SetSuperTrackedQuestID(id) S.superTracked = id; questsChanged("SUPER_TRACKING_CHANGED") end
function C_SuperTrack.ClearAllSuperTracked() S.superTracked = nil; questsChanged("SUPER_TRACKING_CHANGED") end
POIButtonUtil = { Style = { QuestInProgress = 1, QuestComplete = 2, QuestDisabled = 3, Waypoint = 4 } }
function POIButtonUtil.GetStyle(id) local q = S.questByID[id]; return q and q.complete and 2 or 1 end

-- POIButtonTemplate, a stand-in: a 20 px button with a gold disc and the quest's number
local POI = {}
function POI:SetQuestID(id) self.questID = id end
function POI:GetQuestID() return self.questID end
function POI:SetSelected(v) self.selected = v and true or false end
function POI:IsSelected() return self.selected end
function POI:SetStyle(st) self.style = st end
function POI:GetStyle() return self.style end
function POI:EvaluateManagedHighlight() end
function POI:UpdateButtonStyle()
	local q = S.questByID[self.questID]
	self._label:SetText(self.style == 2 and "?" or tostring(q and q.index or ""))
	local c = self.selected and { 1, 0.82, 0.1 } or { 0.85, 0.7, 0.2 }
	self._normal:SetVertexColor(c[1], c[2], c[3], 1)
	self._ring:SetShown(self.selected)
end
function S.makePOIButton(f)
	Mixin(f, POI)
	f:SetSize(20, 20)
	f:SetNormalTexture("Interface\\WorldMap\\UI-QuestPoi-NumberIcons")
	f._ring = f:CreateTexture(nil, "OVERLAY")
	f._ring:SetTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
	f._ring:SetPoint("CENTER")
	f._ring:SetSize(30, 30)
	f._ring:Hide()
	f._label = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	f._label:SetPoint("CENTER", f, "CENTER", 0, 0)
	f._label:SetTextColor(0.12, 0.08, 0.02)
	f:SetScript("OnClick", function(self, button)
		if button ~= "LeftButton" then return end
		if self.selected then C_SuperTrack.ClearAllSuperTracked() else C_SuperTrack.SetSuperTrackedQuestID(self.questID) end
	end)
	f:Hide()
end

-- QuestPOIFrame, a stand-in: each drawn quest's area as an ellipse image placed by texture
-- coordinates over the whole frame (the frame is the zone's 0..1 rectangle)
local BLOB = {}
function BLOB:SetMapID(id) self._mapID = id end
function BLOB:GetMapID() return self._mapID end
function BLOB:SetFillTexture() end
function BLOB:SetBorderTexture() end
function BLOB:SetFillAlpha() end
function BLOB:SetBorderAlpha() end
function BLOB:SetBorderScalar() end
function BLOB:EnableMerging() end
function BLOB:EnableSmoothing() end
function BLOB:SetNumSplinePoints() end
function BLOB:SetMergeThreshold() end
function BLOB:DrawNone()
	for _, t in ipairs(self._blobs) do t:Hide() end
	self._drawn = {}
end
function BLOB:DrawBlob(id, draw)
	S.blobCalls = (S.blobCalls or 0) + 1
	local q = S.questByID[id]
	if not (draw and q and q.area and q.zone == self._mapID) then return end
	local n = #self._drawn + 1
	self._drawn[n] = q
	local t = self._blobs[n]
	if not t then
		t = self:CreateTexture(nil, "ARTWORK")
		t:SetTexture("Interface\\GPSSandbox\\QuestBlob")
		t:SetAllPoints(self)
		self._blobs[n] = t
	end
	local cx, cy, rx, ry = q.area[1], q.area[2], q.area[3], q.area[4]
	local l, top = (0 - (cx - rx)) / (2 * rx), (0 - (cy - ry)) / (2 * ry)
	t:SetTexCoord(l, l + 1 / (2 * rx), top, top + 1 / (2 * ry))
	t:Show()
end
function BLOB:DrawAll() end
function BLOB:UpdateMouseOverTooltip(x, y)
	for _, q in ipairs(self._drawn) do
		local a = q.area
		local dx, dy = (x - a[1]) / a[3], (y - a[2]) / a[4]
		if dx * dx + dy * dy <= 1 then return q.questID, #q.objectives end
	end
	return nil
end
function BLOB:GetNumTooltips() return 0 end
function S.makeQuestPOIFrame(f)
	Mixin(f, BLOB)
	f._blobs, f._drawn = {}, {}
end

------------------------------------------------------------------------------------------------
-- Blizzard's map canvas, a stand-in (for GPS's traditional map). Not Blizzard's code or art: the
-- map is a parchment-coloured sheet with its name, its child maps as boxes (click one to open it,
-- right-click for the map above), the wheel zooms and a drag pans when zoomed in, and your arrow is
-- drawn where Blizzard's map would draw it. It takes the calls GPS makes (MapCanvasMixin and the
-- MapCanvasFrameScrollContainerTemplate scroll frame); Blizzard's real map is checked in the game.
------------------------------------------------------------------------------------------------
do
	local PROVIDER_NAMES = {
		"MapExplorationDataProviderMixin", "MapHighlightDataProviderMixin", "BattlefieldFlagDataProviderMixin",
		"VehicleDataProviderMixin", "FogOfWarDataProviderMixin", "DeathMapDataProviderMixin",
		"ScenarioDataProviderMixin", "VignetteDataProviderMixin", "GossipDataProviderMixin",
		"FlightPointDataProviderMixin", "PetTamerDataProviderMixin", "DigSiteDataProviderMixin",
		"DungeonEntranceDataProviderMixin", "MapLinkDataProviderMixin", "SelectableGraveyardDataProviderMixin",
		"AreaPOIDataProviderMixin", "AreaPOIEventDataProviderMixin", "QuestSessionDataProviderMixin",
		"EncounterJournalDataProviderMixin", "GroupMembersDataProviderMixin",
		"QuestOfferDataProviderMixin", "BonusObjectiveDataProviderMixin", "WaypointLocationDataProviderMixin",
		"SuperTrackWaypointDataProviderMixin",
	}
	for _, name in ipairs(PROVIDER_NAMES) do _G[name] = { _name = name, OnAdded = function(self, map) self.owningMap = map end } end
	-- your quests on the sheet (stand-ins of Blizzard's QuestDataProvider and QuestBlobDataProvider):
	-- the quest buttons of the map shown, and the tracked quest's area
	QuestDataProviderMixin = { _name = "QuestDataProviderMixin", OnAdded = function(self, map) self.owningMap = map; self.pins = {} end }
	function QuestDataProviderMixin:LayoutPins(sc, cw, ch)
		local n = 0
		local zone = S.uiMapType(sc.mapID) == 3
		for _, info in ipairs(zone and C_QuestLog.GetQuestsOnMap(sc.mapID) or {}) do
			n = n + 1
			local pin = self.pins[n]
			if not pin then pin = CreateFrame("Button", nil, sc.Child, "POIButtonTemplate"); self.pins[n] = pin end
			pin:SetQuestID(info.questID)
			pin:SetSelected(info.questID == S.superTracked)
			pin:SetStyle(POIButtonUtil.GetStyle(info.questID))
			pin:UpdateButtonStyle()
			pin:SetFrameLevel(sc.Child:GetFrameLevel() + (pin.selected and 3 or 2))
			pin:ClearAllPoints()
			pin:SetPoint("CENTER", sc.Child, "TOPLEFT", info.x * cw, -info.y * ch)
			pin:Show()
		end
		for i = n + 1, #self.pins do self.pins[i]:Hide() end
	end
	QuestBlobDataProviderMixin = { _name = "QuestBlobDataProviderMixin", OnAdded = function(self, map) self.owningMap = map end }
	function QuestBlobDataProviderMixin:LayoutPins(sc, cw, ch)
		local q = S.questByID[S.superTracked or 0]
		if not self.tex then self.tex = sc.Child:CreateTexture(nil, "ARTWORK", nil, 2); self.tex:SetTexture("Interface\\GPSSandbox\\QuestBlobWhole") end
		if not (q and q.area and q.zone == sc.mapID) then self.tex:Hide() return end
		local a = q.area
		self.tex:ClearAllPoints()
		self.tex:SetPoint("TOPLEFT", sc.Child, "TOPLEFT", (a[1] - a[3]) * cw, -(a[2] - a[4]) * ch)
		self.tex:SetSize(2 * a[3] * cw, 2 * a[4] * ch)
		self.tex:Show()
	end
	AreaLabelDataProviderMixin = { _name = "AreaLabelDataProviderMixin", OnAdded = function(self, map) self.owningMap = map end, SetOffsetY = function(self, y) self.offsetY = y end }
	MapCanvasScrollControllerMixin = {}

	local ZOOM_STEP, ZOOM_MAX = 1.6, 3
	local PARCHMENT = { 0.80, 0.71, 0.53 }

	local M = {}
	MapCanvasMixin = M
	function M:OnLoad()
		-- Blizzard's OnLoad reaches into the frame's XML children: ScrollContainer (GetCanvas) and
		-- BorderFrame (EvaluateLockReasons); without them it fails, so the stand-in does too
		assert(self.ScrollContainer and self.ScrollContainer.Child, "MapCanvasMixin.OnLoad: no ScrollContainer")
		assert(self.BorderFrame, "MapCanvasMixin.OnLoad: no BorderFrame (EvaluateLockReasons needs it)")
		self.dataProviders = {}
		self.pinFrameLevelsManager = { maxLevel = 2000, AddFrameLevel = function(lm, _, range) lm.maxLevel = lm.maxLevel + (range or 1) end }
		self.flags = {}
	end
	function M:GetPinFrameLevelsManager() return self.pinFrameLevelsManager end
	function M:AddDataProvider(p) self.dataProviders[p] = true; if p.OnAdded then p:OnAdded(self) end end
	function M:RemoveDataProvider(p) self.dataProviders[p] = nil end
	function M:SetShouldZoomInOnClick(v) self.flags.zoomOnClick = v end
	function M:SetShouldPanOnClick(v) self.flags.panOnClick = v end
	function M:SetShouldNavigateOnClick(v) self.flags.navigate = v end
	function M:SetShouldZoomInstantly(v) self.flags.instant = v end
	function M:SetGlobalPinScale(s) self.pinScale = s end
	function M:SetMapID(id)
		if self.mapID == id then return end
		self.mapID = id
		self.ScrollContainer:SetMapID(id)
		self:OnMapChanged()
	end
	function M:GetMapID() return self.mapID or MapUtil.GetDisplayableMapForPlayer() end
	function M:OnMapChanged() end
	function M:OnShow() self.ScrollContainer:Layout() end
	function M:OnHide() end
	function M:OnEvent() end
	function M:OnUpdate()
		-- the game sends OnSizeChanged to anchored frames when their window is resized; the engine
		-- does not, so the stand-in notices the size itself
		local sc = self.ScrollContainer
		local w, h = sc:GetSize()
		if w ~= sc._lw or h ~= sc._lh or sc._qs ~= S.questStamp then sc._lw, sc._lh = w, h; sc:Layout() else sc:UpdateArrow() end
	end
	function M:OnFrameSizeChanged() self.ScrollContainer:Layout() end
	function M:ZoomIn() self.ScrollContainer:SetZoom(self.ScrollContainer.zoom + 1) end
	function M:ZoomOut() self.ScrollContainer:SetZoom(self.ScrollContainer.zoom - 1) end
	function M:ResetZoom() self.ScrollContainer:SetZoom(0) end
	function M:IsAtMaxZoom() return self.ScrollContainer.zoom >= ZOOM_MAX end
	function M:IsAtMinZoom() return self.ScrollContainer.zoom <= 0 end
	function M:GetCanvasZoomPercent() return self.ScrollContainer.zoom / ZOOM_MAX end
	function M:PanTo(x, y) local sc = self.ScrollContainer; sc.panX, sc.panY = x, y; sc:Layout() end
	function M:GetViewRect()
		local sc = self.ScrollContainer
		local half = 0.5 / ZOOM_STEP ^ sc.zoom
		local l, r, t, b = sc.panX - half, sc.panX + half, sc.panY - half, sc.panY + half
		return { left = l, right = r, top = t, bottom = b, GetCenter = function() return (l + r) / 2, (t + b) / 2 end }
	end
	function M:NavigateToParentMap()
		local info = C_Map.GetMapInfo(self:GetMapID())
		if info.parentMapID and info.parentMapID > 0 then self:SetMapID(info.parentMapID) end
	end
	function M:GetCanvas() return self.ScrollContainer.Child end
	function M:GetCanvasContainer() return self.ScrollContainer end

	-- the scroll frame: its Child is the map sheet, scaled by the zoom and moved by the pan
	local SC = {}
	function SC:SetMapID(id)
		self.mapID = id
		self.zoom, self.panX, self.panY = 0, 0.5, 0.5
		local m = S.uiMaps[id] or { name = C_Map.GetMapInfo(id).name }
		self.title:SetText(m.name .. (m.floorName and m.floorName ~= m.name and (" - " .. m.floorName) or ""))
		-- child maps: by `at`, or by their world boxes inside this map's box
		for _, b in ipairs(self.boxes) do b.tex:Hide(); b.fs:Hide() end
		local n = 0
		for _, cid in ipairs(S.uiMapOrder) do
			local c = S.uiMaps[cid]
			if c.parent == id then
				local l, t, r, bt
				if c.at then l, t, r, bt = c.at[1], c.at[2], c.at[3], c.at[4]
				elseif c.box and m.box then
					l, t = toMap(m.box, c.box[1], c.box[3])
					r, bt = toMap(m.box, c.box[2], c.box[4])
				end
				if l then
					n = n + 1
					local b = self.boxes[n]
					if not b then
						b = { tex = self.Child:CreateTexture(nil, "ARTWORK"), fs = self.Child:CreateFontString(nil, "OVERLAY", "GameFontNormal") }
						b.tex:SetColorTexture(0.55, 0.45, 0.28, 0.16) -- faint: zone boxes overlap
						b.fs:SetTextColor(0.25, 0.17, 0.08)
						self.boxes[n] = b
					end
					b.id, b.l, b.t, b.r, b.b = cid, l, t, r, bt
					b.fs:SetText(c.name)
					b.tex:Show(); b.fs:Show()
				end
			end
		end
		self.nBoxes = n
		self:Layout()
	end
	function SC:Layout()
		local w, h = self:GetSize()
		if not w or w <= 0 then return end
		local s = ZOOM_STEP ^ self.zoom
		local cw, ch = w * s, h * s
		-- keep the sheet covering the view
		local half = 0.5 / s
		self.panX = max(half, min(1 - half, self.panX or 0.5))
		self.panY = max(half, min(1 - half, self.panY or 0.5))
		self.Child:ClearAllPoints()
		self.Child:SetPoint("TOPLEFT", self, "TOPLEFT", w / 2 - self.panX * cw, -(h / 2 - self.panY * ch))
		self.Child:SetSize(cw, ch)
		for i = 1, self.nBoxes or 0 do
			local b = self.boxes[i]
			b.tex:ClearAllPoints()
			b.tex:SetPoint("TOPLEFT", self.Child, "TOPLEFT", b.l * cw, -b.t * ch)
			b.tex:SetSize((b.r - b.l) * cw, (b.b - b.t) * ch)
			b.fs:ClearAllPoints()
			b.fs:SetPoint("CENTER", b.tex, "CENTER", 0, 0)
		end
		local map = self:GetParent()
		for p in pairs(map and map.dataProviders or {}) do
			if p.LayoutPins then p:LayoutPins(self, cw, ch) end
		end
		self._qs = S.questStamp
		self:UpdateArrow()
	end
	function SC:SetZoom(z)
		self.zoom = max(0, min(ZOOM_MAX, z))
		self:Layout()
	end
	function SC:UpdateArrow()
		local pos = self.mapID and C_Map.GetPlayerMapPosition(self.mapID, "player")
		if not pos then self.arrow:Hide() return end
		local cw, ch = self.Child:GetSize()
		self.arrow:ClearAllPoints()
		self.arrow:SetPoint("CENTER", self.Child, "TOPLEFT", pos.x * cw, -pos.y * ch)
		self.arrow:SetRotation(S.player.facing or 0)
		self.arrow:Show()
	end
	-- the child map under the cursor (topmost box), or nil
	function SC:BoxAt()
		local l, b, r, t = rect(self.Child)
		if not l then return nil end
		local x, y = (S.cx - l) / (r - l), (t - S.cy) / (t - b)
		-- with the zone data: the zone under the cursor (boxes overlap; the data knows which it is)
		local m = S.uiMaps[self.mapID]
		if S.mapAt and m and m.box and m.continent then
			local X, Y = toWorld(m.box, x, y)
			local id = S.mapAt(m.continent, X, Y)
			if id and S.uiMaps[id].parent == self.mapID then return id end
			return nil
		end
		for i = self.nBoxes or 0, 1, -1 do
			local bx = self.boxes[i]
			if x >= bx.l and x <= bx.r and y >= bx.t and y <= bx.b then return bx.id end
		end
	end

	function S.makeMapScroll(f)
		Mixin(f, SC)
		f._clips = true
		f._mouse = true
		f._wheel = true
		f.Child = CreateFrame("Frame", nil, f)
		local sheet = f.Child:CreateTexture(nil, "BACKGROUND")
		sheet:SetAllPoints(f.Child)
		sheet:SetColorTexture(PARCHMENT[1], PARCHMENT[2], PARCHMENT[3], 1)
		f.title = f.Child:CreateFontString(nil, "OVERLAY", "GameFontNormalHuge")
		f.title:SetPoint("BOTTOM", f.Child, "BOTTOM", 0, 50)
		f.title:SetTextColor(0.30, 0.20, 0.08)
		f.arrow = f.Child:CreateTexture(nil, "OVERLAY")
		f.arrow:SetTexture("Interface\\Minimap\\MinimapArrow")
		f.arrow:SetSize(28, 28)
		f.arrow:Hide()
		f.boxes, f.nBoxes = {}, 0
		f.zoom, f.panX, f.panY = 0, 0.5, 0.5
		f:SetScript("OnMouseDown", function(self, button)
			self.down = { button = button, x = S.cx, y = S.cy, panX = self.panX, panY = self.panY }
			self:SetScript("OnUpdate", function()
				local d = self.down
				if not d or d.button ~= "LeftButton" then return end
				local cw, ch = self.Child:GetSize()
				if self.zoom > 0 and (abs(S.cx - d.x) > 3 or abs(S.cy - d.y) > 3) then
					d.moved = true
					self.panX = d.panX - (S.cx - d.x) / cw
					self.panY = d.panY + (S.cy - d.y) / ch
					self:Layout()
				end
			end)
		end)
		f:SetScript("OnMouseUp", function(self, button)
			local d = self.down
			self.down = nil
			self:SetScript("OnUpdate", nil)
			if not d or d.moved then return end
			local map = self:GetParent()
			if button == "RightButton" then
				map:NavigateToParentMap()
			elseif map.flags.navigate then
				local id = self:BoxAt()
				if id then map:SetMapID(id) end
			end
		end)
		f:SetScript("OnMouseWheel", function(self, delta) self:SetZoom(self.zoom + (delta > 0 and 1 or -1)) end)
	end
end

-- Colors
local ColorMixin = {}
ColorMixin.__index = ColorMixin
function ColorMixin:GetRGB() return self.r, self.g, self.b end
function ColorMixin:GetRGBA() return self.r, self.g, self.b, self.a end
function CreateColor(r, g, b, a) return setmetatable({ r = r, g = g, b = b, a = a or 1 }, ColorMixin) end

-- Timers
S.timers = {}
C_Timer = {}
function C_Timer.After(delay, f) S.timers[#S.timers + 1] = { at = S.time + delay, f = f } end
function C_Timer.NewTimer(delay, f) local t = { at = S.time + delay, f = f }; S.timers[#S.timers + 1] = t; return { Cancel = function() t.cancelled = true end } end
function C_Timer.NewTicker(delay, f, n)
	local t = { every = delay, at = S.time + delay, f = f, left = n }
	S.timers[#S.timers + 1] = t
	return { Cancel = function() t.cancelled = true end }
end

-- Slash commands and special frames
SlashCmdList = {}
UISpecialFrames = {}

------------------------------------------------------------------------------------------------
-- GameTooltip
------------------------------------------------------------------------------------------------
do
	local tip = CreateFrame("Frame", "GameTooltip", UIParent, "BackdropTemplate")
	tip:SetFrameStrata("TOOLTIP")
	tip:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border", edgeSize = 16, insets = { left = 4, right = 4, top = 4, bottom = 4 } })
	tip:SetBackdropColor(0.09, 0.09, 0.19, 0.92)
	tip:SetBackdropBorderColor(1, 1, 1, 1)
	tip:Hide()
	local lines = {}
	local function layout()
		local w, h = 0, 0
		for i, fs in ipairs(lines) do
			if fs:IsShown() then
				w = max(w, fs:GetStringWidth())
				h = h + fs._font.size + 3
			end
		end
		tip:SetSize(w + 20, h + 14)
	end
	local function line(i)
		local fs = lines[i]
		if not fs then
			fs = tip:CreateFontString(nil, "ARTWORK", i == 1 and "GameTooltipHeaderText" or "GameTooltipText")
			if i == 1 then fs:SetPoint("TOPLEFT", 10, -8) else fs:SetPoint("TOPLEFT", lines[i - 1], "BOTTOMLEFT", 0, -3) end
			lines[i] = fs
		end
		return fs
	end
	function tip:SetOwner(owner, anchor)
		self._owner = owner
		self:ClearAllPoints()
		anchor = anchor or "ANCHOR_RIGHT"
		if anchor == "ANCHOR_BOTTOM" then self:SetPoint("TOP", owner, "BOTTOM", 0, -4)
		elseif anchor == "ANCHOR_TOP" then self:SetPoint("BOTTOM", owner, "TOP", 0, 4)
		elseif anchor == "ANCHOR_LEFT" then self:SetPoint("RIGHT", owner, "LEFT", -4, 0)
		elseif anchor == "ANCHOR_CURSOR" then self:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", S.cx + 12, S.cy + 12)
		else self:SetPoint("LEFT", owner, "RIGHT", 4, 0) end
		for _, fs in ipairs(lines) do fs:Hide() end
		self._n = 0
	end
	function tip:SetText(text, r, g, b)
		self._n = 1
		local fs = line(1)
		fs:SetText(text)
		fs:SetTextColor(r or 1, g or 0.82, b or 0)
		if r == nil then fs:SetTextColor(1, 1, 1) end
		fs:Show()
		for i = 2, #lines do lines[i]:Hide() end
		layout()
	end
	function tip:AddLine(text, r, g, b)
		self._n = (self._n or 0) + 1
		local fs = line(self._n)
		fs:SetText(text)
		fs:SetTextColor(r or 1, g or 0.82, b or 0)
		fs:Show()
		layout()
	end
	function tip:ClearLines() for _, fs in ipairs(lines) do fs:Hide() end self._n = 0 end
	function tip:GetOwner() return self._owner end
	function tip:GetLines() -- for the tests: the shown lines' text, top to bottom
		local out = {}
		for i = 1, self._n or 0 do if lines[i] and lines[i]:IsShown() then out[#out + 1] = lines[i]:GetText() end end
		return out
	end
	function tip:IsOwned(f) return self._owner == f end
	function GameTooltip_Hide() tip:Hide() end
end

------------------------------------------------------------------------------------------------
-- Draw list
------------------------------------------------------------------------------------------------
-- Every visible texture becomes a quad (corners upper-left, lower-left, upper-right, lower-right),
-- every font string a text record, every ModelScene actor a few flat-shaded boxes. The host draws
-- them in this order. Strings (texture names, text) go in a dictionary sent once.
local dict, dictN, newDict = {}, 0, {}
local function sid(s)
	local id = dict[s]
	if not id then
		dictN = dictN + 1
		id = dictN
		dict[s] = id
		-- backslashes doubled first, so a path such as "Media\Needle" is not read back as a line break
		newDict[#newDict + 1] = id .. "\t" .. (s:gsub("\\", "\\\\"):gsub("\n", "\\n"))
	end
	return id
end

local function strataOf(f)
	local o = f
	while o do if o._strata then return STRATA[o._strata] or 3 end; o = o._parent end
	return 3
end

local function visibleFrames()
	local list = {}
	for _, f in ipairs(frames) do
		if f ~= S.UIParent and f:IsVisible() then list[#list + 1] = f end
	end
	for _, f in ipairs(list) do f._sStrata = strataOf(f) end
	table.sort(list, function(a, b)
		if a._sStrata ~= b._sStrata then return a._sStrata < b._sStrata end
		if a._level ~= b._level then return a._level < b._level end
		return a._order < b._order
	end)
	return list
end
S.visibleFrames = visibleFrames

local function clipOf(f)
	local l, b, r, t
	local o = f
	while o and o ~= S.UIParent do
		if o._clips then
			local ol, ob, orr, ot = rect(o)
			if ol then
				if l then l, b, r, t = max(l, ol), max(b, ob), min(r, orr), min(t, ot) else l, b, r, t = ol, ob, orr, ot end
			end
		end
		o = o._parent
	end
	return l, b, r, t
end

local out, n = {}, 0
local function push(...)
	for i = 1, select("#", ...) do n = n + 1; out[n] = select(i, ...) end
end
local Q = 4 -- positions in quarter pixels
local function px(v) return floor(v * Q + 0.5) end
local function uv(v) return floor(v * 65535 + 0.5) end
local function c8(v) v = floor(v * 255 + 0.5); if v < 0 then return 0 elseif v > 255 then return 255 end return v end

local clipIds, clipN
local function clipId(f)
	local l, b, r, t = clipOf(f)
	if not l then return 0 end
	local key = px(l) .. "," .. px(b) .. "," .. px(r) .. "," .. px(t)
	local id = clipIds[key]
	if not id then
		clipN = clipN + 1
		id = clipN
		clipIds[key] = id
		push(0, id, px(l), px(b), px(r), px(t))
	end
	return id
end

local DEFAULT_TC = { 0, 0, 0, 1, 1, 0, 1, 1 }
local function emitQuad(texId, clip, x1, y1, x2, y2, x3, y3, x4, y4, tc, r, g, b, a, grad)
	n = n + 1; out[n] = 1
	n = n + 1; out[n] = texId
	n = n + 1; out[n] = clip
	n = n + 1; out[n] = px(x1); n = n + 1; out[n] = px(y1)
	n = n + 1; out[n] = px(x2); n = n + 1; out[n] = px(y2)
	n = n + 1; out[n] = px(x3); n = n + 1; out[n] = px(y3)
	n = n + 1; out[n] = px(x4); n = n + 1; out[n] = px(y4)
	for i = 1, 8 do n = n + 1; out[n] = uv(tc[i]) end
	if grad then
		n = n + 1; out[n] = 1
		for i = 1, 16 do n = n + 1; out[n] = c8(grad[i]) end
	else
		n = n + 1; out[n] = 0
		n = n + 1; out[n] = c8(r); n = n + 1; out[n] = c8(g); n = n + 1; out[n] = c8(b); n = n + 1; out[n] = c8(a)
	end
end

local function rotateTC(tc, rot)
	if not rot or rot == 0 then return tc end
	-- the image turns counter-clockwise by rot around its centre
	local c, s = cos(rot), sin(rot)
	local outc = {}
	local corners = { { -0.5, 0.5 }, { -0.5, -0.5 }, { 0.5, 0.5 }, { 0.5, -0.5 } } -- UL, LL, UR, LR (y up)
	for i = 1, 4 do
		local x, y = corners[i][1], corners[i][2]
		local ix, iy = x * c + y * s, -x * s + y * c -- rotate by -rot
		outc[i * 2 - 1], outc[i * 2] = 0.5 + ix, 0.5 - iy
	end
	-- map through the texture's own coordinates (bilinear in the original quad)
	local res = {}
	for i = 1, 4 do
		local u, v = outc[i * 2 - 1], outc[i * 2]
		local top_u = tc[1] + (tc[5] - tc[1]) * u
		local top_v = tc[2] + (tc[6] - tc[2]) * u
		local bot_u = tc[3] + (tc[7] - tc[3]) * u
		local bot_v = tc[4] + (tc[8] - tc[4]) * u
		res[i * 2 - 1], res[i * 2] = top_u + (bot_u - top_u) * v, top_v + (bot_v - top_v) * v
	end
	return res
end

local function textureKey(file)
	if type(file) == "number" then return sid("fdid:" .. file) end
	return sid(file)
end

local function emitTexture(t, clip, alpha, hover, pushed)
	if not t._file then return end
	if t._layer == 5 and not hover then return end
	if t._isPushed and not pushed then return end
	if t._parent._pushed and t == t._parent._normal and pushed then return end
	local l, b, r, tp = rect(t)
	if not l then return end
	local x1, y1, x2, y2, x3, y3, x4, y4 = l, tp, l, b, r, tp, r, b
	local vo = t._vo
	if vo then
		x1, y1 = x1 + vo[1], y1 + vo[2]
		x2, y2 = x2 + vo[3], y2 + vo[4]
		x3, y3 = x3 + vo[5], y3 + vo[6]
		x4, y4 = x4 + vo[7], y4 + vo[8]
	end
	local c = t._color
	local a = (c[4] or 1) * t._alpha * alpha
	if a <= 0 then return end
	-- the host keeps each texture's image, coordinates and colours; send them only when they change
	local id = t._order
	if t._sentSV ~= t._sv or t._sentA ~= a or t._sentEpoch ~= S.epoch then
		t._sentSV, t._sentA, t._sentEpoch = t._sv, a, S.epoch
		local tc = rotateTC(t._tc or DEFAULT_TC, t._rot)
		local grad
		if t._grad then
			local o, mn, mx = t._grad[1], t._grad[2], t._grad[3]
			local function col(cc) return cc.r * c[1], cc.g * c[2], cc.b * c[3], (cc.a or 1) * a end
			local a1, a2, a3, a4 = col(mn)
			local b1, b2, b3, b4 = col(mx)
			if o == "VERTICAL" then
				grad = { b1, b2, b3, b4, a1, a2, a3, a4, b1, b2, b3, b4, a1, a2, a3, a4 }
			else
				grad = { a1, a2, a3, a4, a1, a2, a3, a4, b1, b2, b3, b4, b1, b2, b3, b4 }
			end
		end
		n = n + 1; out[n] = 3
		n = n + 1; out[n] = id
		n = n + 1; out[n] = textureKey(t._file)
		for i = 1, 8 do n = n + 1; out[n] = uv(tc[i]) end
		if grad then
			n = n + 1; out[n] = 1
			for i = 1, 16 do n = n + 1; out[n] = c8(grad[i]) end
		else
			n = n + 1; out[n] = 0
			n = n + 1; out[n] = c8(c[1]); n = n + 1; out[n] = c8(c[2]); n = n + 1; out[n] = c8(c[3]); n = n + 1; out[n] = c8(a)
		end
	end
	n = n + 1; out[n] = 4
	n = n + 1; out[n] = id
	n = n + 1; out[n] = clip
	n = n + 1; out[n] = floor(x1 * 4 + 0.5); n = n + 1; out[n] = floor(y1 * 4 + 0.5)
	n = n + 1; out[n] = floor(x2 * 4 + 0.5); n = n + 1; out[n] = floor(y2 * 4 + 0.5)
	n = n + 1; out[n] = floor(x3 * 4 + 0.5); n = n + 1; out[n] = floor(y3 * 4 + 0.5)
	n = n + 1; out[n] = floor(x4 * 4 + 0.5); n = n + 1; out[n] = floor(y4 * 4 + 0.5)
end
local function emitText(fs, clip, alpha)
	local text = fs._text
	if not text or text == "" then return end
	local l, b, r, t = rect(fs)
	if not l then return end
	local c = fs._color
	n = n + 1; out[n] = 2
	n = n + 1; out[n] = sid(text)
	n = n + 1; out[n] = clip
	n = n + 1; out[n] = fs._font.size
	n = n + 1; out[n] = px(l); n = n + 1; out[n] = px(b); n = n + 1; out[n] = px(r - l); n = n + 1; out[n] = px(t - b)
	n = n + 1; out[n] = c8(c[1]); n = n + 1; out[n] = c8(c[2]); n = n + 1; out[n] = c8(c[3]); n = n + 1; out[n] = c8((c[4] or 1) * fs._alpha * alpha)
	n = n + 1; out[n] = fs._justify
end

-- Backdrop: background fill and the 8-piece edge file (left, right, top, bottom, corners).
local function emitBackdrop(f, clip, alpha)
	local bd = f._backdrop
	if not bd then return end
	local l, b, r, t = rect(f)
	if not l then return end
	local ins = bd.insets or { left = 0, right = 0, top = 0, bottom = 0 }
	if bd.bgFile then
		local c = f._bdColor or { 1, 1, 1, 1 }
		emitQuad(sid(bd.bgFile:lower()), clip, l + ins.left, t - ins.top, l + ins.left, b + ins.bottom, r - ins.right, t - ins.top, r - ins.right, b + ins.bottom, DEFAULT_TC, c[1], c[2], c[3], c[4] * alpha)
	end
	if bd.edgeFile then
		local e = bd.edgeSize or 16
		local c = f._bdBorder or { 1, 1, 1, 1 }
		local id = sid(bd.edgeFile:lower())
		local function piece(i, x1, y1, x2, y2, rotated, len)
			-- piece i of 8 in the strip; rotated pieces (top, bottom) run sideways in the file,
			-- with the piece's left side (u0) on the window's outer edge
			local u0, u1 = (i - 1) / 8, i / 8
			local reps = len and len / e or 1
			if rotated == "bottom" then
				emitQuad(id, clip, x1, y2, x1, y1, x2, y2, x2, y1, { u1, reps, u0, reps, u1, 0, u0, 0 }, c[1], c[2], c[3], c[4] * alpha)
			elseif rotated then
				emitQuad(id, clip, x1, y2, x1, y1, x2, y2, x2, y1, { u0, reps, u1, reps, u0, 0, u1, 0 }, c[1], c[2], c[3], c[4] * alpha)
			else
				emitQuad(id, clip, x1, y2, x1, y1, x2, y2, x2, y1, { u0, 0, u0, reps, u1, 0, u1, reps }, c[1], c[2], c[3], c[4] * alpha)
			end
		end
		local h, w = t - b - 2 * e, r - l - 2 * e
		if h > 0 then
			piece(1, l, b + e, l + e, t - e, false, h)
			piece(2, r - e, b + e, r, t - e, false, h)
		end
		if w > 0 then
			piece(3, l + e, t - e, r - e, t, true, w)
			piece(4, l + e, b, r - e, b + e, "bottom", w)
		end
		piece(5, l, t - e, l + e, t)
		piece(6, r - e, t - e, r, t)
		piece(7, l, b, l + e, b + e)
		piece(8, r - e, b, r, b + e)
	end
end

-- Stand-in models: boxes in model space (x forward, y left, z up, yards).
local MODELS = {
	unit = {
		{ -0.18, -0.30, 0.00, 0.18, 0.30, 1.05, 0.25, 0.32, 0.62 },  -- legs and body
		{ -0.20, -0.36, 1.05, 0.20, 0.36, 1.50, 0.62, 0.20, 0.18 },  -- chest
		{ -0.14, -0.14, 1.52, 0.14, 0.14, 1.82, 0.93, 0.78, 0.64 },  -- head
		{ 0.14, -0.05, 1.62, 0.30, 0.05, 1.70, 0.93, 0.78, 0.64 },   -- nose: the way it faces
		{ -0.08, 0.36, 0.80, 0.08, 0.50, 1.45, 0.62, 0.20, 0.18 },   -- arms
		{ -0.08, -0.50, 0.80, 0.08, -0.36, 1.45, 0.62, 0.20, 0.18 },
	},
	tree = {
		{ -0.3, -0.3, 0, 0.3, 0.3, 3.0, 0.36, 0.25, 0.14 },
		{ -2.0, -2.0, 2.5, 2.0, 2.0, 7.5, 0.18, 0.42, 0.16 },
		{ -1.3, -1.3, 7.5, 1.3, 1.3, 9.5, 0.22, 0.50, 0.20 },
	},
	other = {
		{ -1, -1, 0, 1, 1, 2, 0.6, 0.6, 0.6 },
	},
}
local BOX_FACES = { -- corner indices (x,y,z bits) for 6 faces, counter-clockwise from outside
	{ 1, 3, 7, 5 }, { 0, 4, 6, 2 }, { 2, 6, 7, 3 }, { 0, 1, 5, 4 }, { 4, 5, 7, 6 }, { 0, 2, 3, 1 },
}
local whiteId
local function emitScene(sc, clip, alpha)
	local l, b, r, t = rect(sc)
	if not l then return end
	local cam = sc._cam
	local fx, fy, fz, rx, ry, rz, ux, uy, uz = sceneBasis(cam)
	local cp = cam.pos
	local F = ((t - b) / 2) / tan(cam.fov / 2)
	local cx, cy = (l + r) / 2, (b + t) / 2
	local L = sc._light.dir
	local faces = {}
	for _, a in ipairs(sc._actors) do
		if a._shown and a._model and a:IsLoaded() then
			local kind = a._model:match("^unit:") and "unit" or (a._fileID == 189927 and "tree") or "other"
			local boxes = MODELS[kind]
			-- the game's models (GPS3D's data): one box of the model's size, tan for buildings, green for the rest
			local r, lo, hi, wmo = modelInfo(a._fileID)
			if r and kind ~= "unit" then
				local q = r * 0.7
				if wmo then -- (some of the game's buildings reach far past their walls; the stand-in keeps to 40 yd)
					q = min(q, 40)
					boxes = { { -q, -q, lo, q, q, min(hi, lo + 40), 0.72, 0.62, 0.48 } }
				elseif hi - lo > r then -- tall: a trunk and a crown, like a tree
					local t, mid, c = max(0.3, r * 0.08), lo + (hi - lo) * 0.45, r * 0.45
					boxes = { { -t, -t, lo, t, t, mid, 0.36, 0.25, 0.14 }, { -c, -c, mid, c, c, hi, 0.24, 0.48, 0.22 } }
				else
					boxes = { { -q, -q, lo, q, q, hi, 0.55, 0.58, 0.50 } }
				end
			end
			-- Rz(yaw) Ry(pitch) Rx(roll), as GPS3D places them
			local cy_, sy_, cp_, sp_, cr_, sr_ = cos(a._yaw), sin(a._yaw), cos(a._pitch or 0), sin(a._pitch or 0), cos(a._roll or 0), sin(a._roll or 0)
			local R11, R12, R13 = cy_ * cp_, cy_ * sp_ * sr_ - sy_ * cr_, cy_ * sp_ * cr_ + sy_ * sr_
			local R21, R22, R23 = sy_ * cp_, sy_ * sp_ * sr_ + cy_ * cr_, sy_ * sp_ * cr_ - cy_ * sr_
			local R31, R32, R33 = -sp_, cp_ * sr_, cp_ * cr_
			local s = a._scale
			local p = a._pos
			for _, bx in ipairs(boxes) do
				local wv, sv = {}, {}
				local ok = true
				for i = 0, 7 do
					local mx = (i & 1 == 1) and bx[4] or bx[1]
					local my = (i & 2 == 2) and bx[5] or bx[2]
					local mz = (i & 4 == 4) and bx[6] or bx[3]
					local wx = p[1] + (R11 * mx + R12 * my + R13 * mz) * s
					local wy = p[2] + (R21 * mx + R22 * my + R23 * mz) * s
					local wz = p[3] + (R31 * mx + R32 * my + R33 * mz) * s
					local dx, dy, dz = wx - cp[1], wy - cp[2], wz - cp[3]
					local d = dx * fx + dy * fy + dz * fz
					if d <= cam.near then ok = false break end
					wv[i] = { wx, wy, wz }
					sv[i] = { cx + (dx * rx + dy * ry + dz * rz) * F / d, cy + (dx * ux + dy * uy + dz * uz) * F / d, d }
				end
				if ok then
					for _, fc in ipairs(BOX_FACES) do
						local A, B, C, D = sv[fc[1]], sv[fc[2]], sv[fc[3]], sv[fc[4]]
						local area = (B[1] - A[1]) * (C[2] - A[2]) - (C[1] - A[1]) * (B[2] - A[2])
						if area > 0 then
							local wa, wb, wc = wv[fc[1]], wv[fc[2]], wv[fc[3]]
							local e1x, e1y, e1z = wb[1] - wa[1], wb[2] - wa[2], wb[3] - wa[3]
							local e2x, e2y, e2z = wc[1] - wa[1], wc[2] - wa[2], wc[3] - wa[3]
							local nx, ny, nz = e1y * e2z - e1z * e2y, e1z * e2x - e1x * e2z, e1x * e2y - e1y * e2x
							local nl = sqrt(nx * nx + ny * ny + nz * nz)
							local lit = 0.55 + 0.45 * max(0, -(nx * L[1] + ny * L[2] + nz * L[3]) / nl)
							faces[#faces + 1] = { (A[3] + B[3] + C[3] + D[3]) / 4, A, D, B, C, bx[7] * lit, bx[8] * lit, bx[9] * lit, a._alpha or 1 }
						end
					end
				end
			end
		end
	end
	table.sort(faces, function(x, y) return x[1] > y[1] end)
	for _, fc in ipairs(faces) do
		-- quad corners: upper-left = A, lower-left = D, upper-right = B, lower-right = C
		emitQuad(whiteId, clip, fc[2][1], fc[2][2], fc[3][1], fc[3][2], fc[4][1], fc[4][2], fc[5][1], fc[5][2], DEFAULT_TC, fc[6], fc[7], fc[8], fc[9] * alpha)
	end
end

local function effectiveAlpha(f)
	local a, o = 1, f
	while o do a = a * (o._alpha or 1); o = o._parent end
	return a
end

local function regionBefore(a, b)
	if a._layer ~= b._layer then return a._layer < b._layer end
	if a._sub ~= b._sub then return a._sub < b._sub end
	return a._order < b._order
end
-- Regions by draw layer and sublevel (80 buckets); inside a bucket, the order they joined the frame
-- (creation order, unless a region was moved here with SetParent).
local function sortedRegions(f)
	if not f._sortOK then
		local buckets = {}
		for _, r in ipairs(f._regions) do
			local k = r._layer * 16 + r._sub + 8
			local bk = buckets[k]
			if not bk then bk = {}; buckets[k] = bk end
			bk[#bk + 1] = r
		end
		local keys = {}
		for k in pairs(buckets) do keys[#keys + 1] = k end
		table.sort(keys)
		local regs, n2 = {}, 0
		for _, k in ipairs(keys) do
			local bk = buckets[k]
			for _, r in ipairs(bk) do n2 = n2 + 1; regs[n2] = r end
		end
		f._sortedRegs, f._sortOK = regs, true
	end
	return f._sortedRegs
end

function S.drawList()
	n = 0 -- the output table is reused; concat only reads entries 1..n
	clipIds, clipN = {}, 0
	whiteId = sid("interface\\buttons\\white8x8")
	local hoverFrame = S.hover
	for _, f in ipairs(visibleFrames()) do
		local clip = clipId(f)
		local alpha = effectiveAlpha(f)
		emitBackdrop(f, clip, alpha)
		local hover = hoverFrame == f
		local pushed = S.pressed == f
		for _, rg in ipairs(sortedRegions(f)) do
			if rg._shown then
				if rg._isText then emitText(rg, clip, alpha) else emitTexture(rg, clip, alpha, hover, pushed) end
			end
		end
		if f._actors then emitScene(f, clip, alpha) end
	end
	local header = tconcat(newDict, "\n")
	newDict = {}
	return header .. "\n\1\n" .. tconcat(out, ",", 1, n)
end

------------------------------------------------------------------------------------------------
-- Input
------------------------------------------------------------------------------------------------
local function hitTest(predicate)
	local list = visibleFrames()
	for i = #list, 1, -1 do
		local f = list[i]
		if predicate(f) then
			local l, b, r, t = rect(f)
			if l and S.cx >= l and S.cx <= r and S.cy >= b and S.cy <= t then
				local cl, cb, cr, ct = clipOf(f._parent)
				if not cl or (S.cx >= cl and S.cx <= cr and S.cy >= cb and S.cy <= ct) then return f end
			end
		end
	end
end
S.hitTest = hitTest

local function updateHover()
	local f = hitTest(function(f) return f._mouse end)
	if f ~= S.hover then
		local old = S.hover
		S.hover = f
		if old and old._scripts.OnLeave then call(old._scripts.OnLeave, old) end
		if f and f._scripts.OnEnter then call(f._scripts.OnEnter, f) end
		touch()
	end
end

local function applyMoveSize()
	if S.moving then
		local m = S.moving
		local f = m.frame
		local l, b, r, t = rect(f)
		if l then
			f._w, f._h = r - l, t - b
			f._points = {}
			local nl, nt = S.cx - m.dx, S.cy - m.dy
			if f._clamped then
				nl = max(0, min(S.W - (r - l), nl))
				nt = max(t - b, min(S.H, nt))
			end
			f:SetPoint("TOPLEFT", S.UIParent, "BOTTOMLEFT", nl, nt)
		end
	end
	if S.sizing then
		local z = S.sizing
		local f = z.frame
		local l, b, r, t = rect(f)
		if l then
			local bounds = f._bounds or { 1, 1, 1e5, 1e5 }
			local nw = min(bounds[3] or 1e5, max(bounds[1] or 1, (S.cx - z.dx) - l))
			local nh = min(bounds[4] or 1e5, max(bounds[2] or 1, t - (S.cy - z.dy)))
			if abs(nw - (r - l)) > 0.01 or abs(nh - (t - b)) > 0.01 then
				f:SetSize(nw, nh)
				S.sizeChanged[f] = true
			end
		end
	end
end

function SANDBOX_MOUSE(kind, x, y, button, delta)
	if button == "" then button = nil end
	S.cx, S.cy = x, y
	if kind == "move" then
		applyMoveSize()
		if S.down and S.down.frame then
			local d = S.down
			if not d.dragging and d.frame._drag and d.frame._drag[d.button] and (abs(x - d.x) > 3 or abs(y - d.y) > 3) then
				d.dragging = true
				if d.frame._scripts.OnDragStart then call(d.frame._scripts.OnDragStart, d.frame, d.button) end
			end
		end
		updateHover()
	elseif kind == "down" then
		updateHover()
		local f = hitTest(function(f) return f._mouse end)
		S.down = { frame = f, button = button, x = x, y = y }
		if f then
			S.pressed = f
			if f._scripts.OnMouseDown then call(f._scripts.OnMouseDown, f, button) end
		end
		touch()
	elseif kind == "up" then
		local d = S.down
		S.down = nil
		S.pressed = nil
		if d and d.frame then
			local f = d.frame
			if d.dragging and f._scripts.OnDragStop then call(f._scripts.OnDragStop, f, button) end
			if f._scripts.OnMouseUp then call(f._scripts.OnMouseUp, f, button) end
			if getmetatable(f) == Button and f:IsMouseOver() and not f._disabled and f._scripts.OnClick then
				call(f._scripts.OnClick, f, button, true)
			end
		end
		updateHover()
		touch()
	elseif kind == "wheel" then
		local f = hitTest(function(f) return f._wheel end)
		if f and f._scripts.OnMouseWheel then call(f._scripts.OnMouseWheel, f, delta) end
	elseif kind == "leave" then
		S.cx, S.cy = -1e6, -1e6
		updateHover()
	end
end

function SANDBOX_KEY(key)
	if key == "ESCAPE" then
		for i = #UISpecialFrames, 1, -1 do
			local f = _G[UISpecialFrames[i]]
			if f and f:IsShown() then f:Hide() return true end
		end
	end
	return false
end

------------------------------------------------------------------------------------------------
-- Ticking
------------------------------------------------------------------------------------------------
S.sizeChanged = {}
function SANDBOX_TICK(dt, W, H)
	S.time = S.time + dt
	S.fps = dt > 0 and 1 / dt or 60
	if W ~= S.W or H ~= S.H then
		S.W, S.H = W, H
		relayout()
		for _, f in ipairs(frames) do if f._scripts.OnSizeChanged then S.sizeChanged[f] = true end end
	end
	-- timers
	local due = {}
	for i = #S.timers, 1, -1 do
		local t = S.timers[i]
		if t.cancelled then table.remove(S.timers, i)
		elseif S.time >= t.at then
			due[#due + 1] = t
			if t.every and (not t.left or t.left > 1) then
				t.at = t.at + t.every
				if t.left then t.left = t.left - 1 end
			else
				table.remove(S.timers, i)
			end
		end
	end
	for i = #due, 1, -1 do call(due[i].f, due[i]) end
	-- OnUpdate for visible frames, creation order
	for _, f in ipairs(frames) do
		local s = f._scripts.OnUpdate
		if s and f:IsVisible() then call(s, f, dt) end
	end
	-- size changes from sizing or the screen
	for f in pairs(S.sizeChanged) do
		S.sizeChanged[f] = nil
		if f._scripts.OnSizeChanged and f:IsVisible() then
			local w, h = f:GetSize()
			call(f._scripts.OnSizeChanged, f, w, h)
		end
	end
	if S.dirty then
		S.dirty = false
		return S.drawList()
	end
	return ""
end

function SANDBOX_FIRE(event, ...)
	for _, f in ipairs(frames) do
		if f._events[event] and f._scripts.OnEvent then call(f._scripts.OnEvent, f, event, ...) end
	end
end

function SANDBOX_FORCE()
	-- the host lost its caches (new GL context): resend everything, dictionary included
	S.epoch = S.epoch + 1
	for str, id in pairs(dict) do newDict[#newDict + 1] = id .. "\t" .. str:gsub("\n", "\\n") end
	S.dirty = true
end

-- The host passes -1 for "none" (map, mapUI, mapX): JavaScript nulls do not cross into Lua well.
function SANDBOX_PLAYER(X, Y, Z, map, facing, zone, subzone, mapUI, mapX, mapY)
	if map == -1 then map, X, Y, Z = nil, nil, nil, nil end
	if mapUI == -1 then mapUI = nil end
	if mapX == -1 then mapX, mapY = nil, nil end
	local p = S.player
	p.X, p.Y, p.Z, p.map, p.facing = X, Y, Z, map, facing
	p.zone, p.subzone = zone or "", subzone or ""
	p.mapUI, p.mapX, p.mapY = mapUI, mapX, mapY
end

function SANDBOX_CHAT()
	if #S.chat == 0 then return "" end
	local s = tconcat(S.chat, "\n")
	S.chat = {}
	return s
end

-- Runs a chat line: /commands go to SlashCmdList, the rest is printed.
function SANDBOX_SLASH(line)
	line = strtrim(line)
	local cmd, rest = line:match("^(/%S+)%s*(.-)$")
	if not cmd then chat(line) return end
	cmd = cmd:lower()
	if cmd == "/reload" or cmd == "/rl" then chat("|cffffa040[sandbox]|r use the Reload button") return end
	if cmd == "/run" or cmd == "/script" then
		local f, err = load(rest, "=/run")
		if not f then report(err) else call(f) end
		return
	end
	for key, handler in pairs(SlashCmdList) do
		for i = 1, 20 do
			local v = _G["SLASH_" .. key .. i]
			if not v then break end
			if v:lower() == cmd then call(handler, rest) return end
		end
	end
	chat("|cffff4040Unknown command:|r " .. cmd)
end

-- The game's Settings panel (Options > AddOns), as far as addons register into it: vertical-layout
-- categories, proxy settings, checkboxes, sliders, dropdowns, section headers and buttons, with the
-- argument checks of Blizzard_Settings_Shared (Forever build). The page draws the registered
-- categories (SANDBOX_SETTINGS) and changes values through them (SANDBOX_SETTING_SET).
S.settings = { categories = {}, byVar = {}, open = nil }
Settings = {
	VarType = { Boolean = "boolean", String = "string", Number = "number" },
	Default = { True = true, False = false },
}
MinimalSliderWithSteppersMixin = { Label = { Left = 1, Right = 2, Top = 3, Min = 4, Max = 5 } }
local function addInit(category, init)
	assert(category and category.layout, "not a registered category")
	tinsert(category.layout.initializers, init)
	return init
end
function Settings.RegisterVerticalLayoutCategory(name)
	assert(type(name) == "string")
	local layout = { initializers = {} }
	function layout:AddInitializer(init) tinsert(self.initializers, init) return init end
	local category = { name = name, layout = layout, ID = name }
	function category:GetID() return self.ID end
	function category:GetName() return self.name end
	return category, layout
end
function Settings.RegisterAddOnCategory(category)
	assert(category and category.layout)
	tinsert(S.settings.categories, category)
end
function Settings.RegisterProxySetting(category, variable, varType, name, default, getValue, setValue)
	assert(category and category.layout, "category")
	assert(type(variable) == "string" and not S.settings.byVar[variable], "variable must be a new string: " .. tostring(variable))
	assert(varType == "boolean" or varType == "number" or varType == "string", "variable type")
	assert(type(default) == varType, "default must be a " .. varType .. ": " .. variable)
	assert(type(getValue) == "function" and type(setValue) == "function", "get and set")
	local setting = { variable = variable, varType = varType, name = name, default = default }
	function setting:GetVariable() return self.variable end
	function setting:GetVariableType() return self.varType end
	function setting:GetName() return self.name end
	function setting:GetDefaultValue() return self.default end
	function setting:GetValue() return getValue() end
	function setting:SetValue(v)
		assert(type(v) == self.varType, "value type")
		setValue(v)
	end
	S.settings.byVar[variable] = setting
	return setting
end
function Settings.CreateCheckbox(category, setting, tooltip)
	assert(setting:GetVariableType() == "boolean")
	return addInit(category, { kind = "check", setting = setting, tooltip = tooltip })
end
function Settings.CreateSliderOptions(minValue, maxValue, rate)
	local options = { minValue = minValue or 0, maxValue = maxValue or 1, steps = rate and (maxValue - minValue) / rate or 100 }
	function options:SetLabelFormatter(label, fn) self.formatters = self.formatters or {}; self.formatters[label] = fn end
	return options
end
function Settings.CreateSlider(category, setting, options, tooltip)
	assert(setting:GetVariableType() == "number" and options ~= nil)
	return addInit(category, { kind = "slider", setting = setting, options = options, tooltip = tooltip })
end
function Settings.CreateControlTextContainer()
	local c = { data = {} }
	function c:Add(value, label, tooltip) tinsert(self.data, { value = value, label = label, text = label, tooltip = tooltip }) end
	function c:GetData() return self.data end
	return c
end
function Settings.CreateDropdown(category, setting, options, tooltip)
	assert(type(options) == "function")
	return addInit(category, { kind = "choice", setting = setting, options = options, tooltip = tooltip })
end
function Settings.OpenToCategory(id) S.settings.open = id end
function CreateSettingsListSectionHeaderInitializer(name, tooltip) return { kind = "header", name = name, tooltip = tooltip } end
function CreateSettingsButtonInitializer(name, buttonText, buttonClick, tooltip, addSearchTags)
	assert(addSearchTags ~= nil)
	return { kind = "button", name = name, text = buttonText, click = buttonClick, tooltip = tooltip }
end

local function json(v)
	local t = type(v)
	if t == "nil" then return "null"
	elseif t == "boolean" then return tostring(v)
	elseif t == "number" then return rawformat("%.17g", v)
	elseif t == "string" then
		return '"' .. v:gsub('[%c"\\]', function(ch) return rawformat("\\u%04x", ch:byte()) end) .. '"'
	elseif t == "table" then
		local parts = {}
		if #v > 0 or next(v) == nil then
			for i = 1, #v do parts[i] = json(v[i]) end
			return "[" .. tconcat(parts, ",") .. "]"
		end
		for k, val in pairs(v) do parts[#parts + 1] = json(tostring(k)) .. ":" .. json(val) end
		return "{" .. tconcat(parts, ",") .. "}"
	end
	return "null"
end
-- The registered AddOns categories with each control's current value, as JSON for the page.
function SANDBOX_SETTINGS()
	local out = {}
	for _, c in ipairs(S.settings.categories) do
		local controls = {}
		for _, init in ipairs(c.layout.initializers) do
			local e = { kind = init.kind, name = init.name, tooltip = init.tooltip, text = init.text }
			local st = init.setting
			if st then
				e.var, e.name, e.value, e.default = st.variable, st.name, st:GetValue(), st.default
				if init.kind == "choice" then
					e.options = {}
					for _, o in ipairs(init.options()) do tinsert(e.options, { value = o.value, label = o.label }) end
				elseif init.kind == "slider" then
					local o = init.options
					e.min, e.max, e.step = o.minValue, o.maxValue, (o.maxValue - o.minValue) / o.steps
					local fmt = o.formatters and o.formatters[MinimalSliderWithSteppersMixin.Label.Right]
					e.label = fmt and fmt(e.value) or tostring(e.value)
				end
			end
			tinsert(controls, e)
		end
		tinsert(out, { id = c.ID, name = c.name, controls = controls })
	end
	return json(out)
end
-- Changes a setting as the panel would (value as text from the page), or clicks the n-th button.
function SANDBOX_SETTING_SET(variable, value)
	local st = S.settings.byVar[variable]
	if not st then return end
	if st.varType == "boolean" then value = value == "true" or value == true
	elseif st.varType == "number" then value = tonumber(value) end
	call(st.SetValue, st, value)
end
function SANDBOX_SETTING_CLICK(categoryID, index)
	for _, c in ipairs(S.settings.categories) do
		if c.ID == categoryID then
			local init = c.layout.initializers[index]
			if init and init.kind == "button" then call(init.click) end
		end
	end
end
-- The debug log (GPS's GnomishPositioningSystemLog) for the page: "1" or "0" (on), then its lines.
function SANDBOX_DEBUGLOG()
	local l = GnomishPositioningSystemLog
	if not l then return "0\n" end
	return (l.on and "1" or "0") .. "\n" .. table.concat(l.lines or {}, "\n")
end
-- The category /gps options asked for, once (nil: none).
function SANDBOX_SETTINGS_TAKEOPEN()
	local id = S.settings.open
	S.settings.open = nil
	return id
end

-- Loads one addon file in the addon's namespace.
S.namespaces = {}
function SANDBOX_LOAD(addon, filename, source)
	local ns = S.namespaces[addon]
	if not ns then ns = {}; S.namespaces[addon] = ns end
	local f, err = load(source, "@" .. addon .. "/" .. filename)
	if not f then report(err) return false end
	local ok = xpcall(f, function(e) report(debug.traceback(tostring(e), 2)) end, addon, ns)
	return ok
end
function SANDBOX_LOADED(addon)
	S.loadedAddons[addon] = true
	SANDBOX_FIRE("ADDON_LOADED", addon)
end

-- SavedVariables: serialise and restore plain tables
local function ser(v, depth)
	local t = type(v)
	if t == "number" then return rawformat("%.17g", v)
	elseif t == "boolean" then return tostring(v)
	elseif t == "string" then return rawformat("%q", v)
	elseif t == "table" and depth < 20 then
		local parts = {}
		for k, val in pairs(v) do
			local ks = type(k) == "string" and ("[" .. rawformat("%q", k) .. "]") or ("[" .. ser(k, depth + 1) .. "]")
			local vs = ser(val, depth + 1)
			if vs then parts[#parts + 1] = ks .. "=" .. vs end
		end
		return "{" .. tconcat(parts, ",") .. "}"
	end
	return nil
end
function SANDBOX_SAVE(names)
	local parts = {}
	for name in names:gmatch("[^,]+") do
		local v = _G[name]
		if v ~= nil then parts[#parts + 1] = name .. "=" .. (ser(v, 0) or "nil") end
	end
	return tconcat(parts, "\n")
end
function SANDBOX_RESTORE(src)
	if not src or src == "" then return end
	local f = load(src, "=SavedVariables", "t", _G)
	if f then pcall(f) end
end

-- Loading state of a texture as the host reports it (set by the host as images load).
S.loaded = {}
function S.isLoaded(file)
	if file == nil then return false end
	local key = type(file) == "number" and ("fdid:" .. file) or file
	return S.loaded[key] == true
end
function SANDBOX_TEXLOADED(key) S.loaded[key] = true end
