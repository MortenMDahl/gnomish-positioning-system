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
local function report(err)
	chat("|cffff4040Lua error:|r " .. tostring(err))
end
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
function FontString:SetFontObject(f) if type(f) == "string" then f = FONTS[f] end; self._font = f or DEFAULT_FONT; relayout(self) end
function FontString:GetFontObject() return self._font end
function FontString:SetFont(_, size) self._font = { size = size or 12, color = self._font.color, name = "custom" }; relayout(self) end
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
		end
	end
end

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
function Actor:SetModelByFileID(id) self._model = "file:" .. tostring(id); self._fileID = id; touch(); return true end
function Actor:SetModelByCreatureDisplayID(id) self._model = "display:" .. tostring(id); touch(); return true end
function Actor:ClearModel() self._model = nil; self._fileID = nil; touch() end
function Actor:IsLoaded() return self._model ~= nil end
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
function GetZoneText() return S.player.zone end
function GetSubZoneText() return S.player.subzone end
function GetRealZoneText() return S.player.zone end
function GetMinimapZoneText() return S.player.subzone ~= "" and S.player.subzone or S.player.zone end
function IsInInstance() return false end
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
function GetAddOnMetadata() return nil end
C_AddOns = { IsAddOnLoaded = function(n) return S.loadedAddons[n] == true end, GetAddOnMetadata = function() return nil end }
IsAddOnLoaded = C_AddOns.IsAddOnLoaded
S.loadedAddons = {}

C_Map = {}
function C_Map.GetBestMapForUnit() return S.player.mapUI end
function C_Map.GetPlayerMapPosition(ui)
	if not ui or S.player.mapX == nil then return nil end
	return { x = S.player.mapX, y = S.player.mapY, GetXY = function(v) return v.x, v.y end }
end
function C_Map.GetWorldPosFromMapPos()
	local p = S.player
	if p.map == nil then return nil end
	return p.map, { GetXY = function() return p.X, p.Y end }
end
function C_Map.GetMapInfo(id) return { mapID = id, name = S.player.zone } end

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
		newDict[#newDict + 1] = id .. "\t" .. s:gsub("\n", "\\n")
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
		if a._shown and a._model then
			local kind = a._model:match("^unit:") and "unit" or (a._fileID == 189927 and "tree") or "other"
			local boxes = MODELS[kind]
			local cyaw, syaw, s = cos(a._yaw), sin(a._yaw), a._scale
			local p = a._pos
			for _, bx in ipairs(boxes) do
				local wv, sv = {}, {}
				local ok = true
				for i = 0, 7 do
					local mx = (i & 1 == 1) and bx[4] or bx[1]
					local my = (i & 2 == 2) and bx[5] or bx[2]
					local mz = (i & 4 == 4) and bx[6] or bx[3]
					local wx = p[1] + (mx * cyaw - my * syaw) * s
					local wy = p[2] + (mx * syaw + my * cyaw) * s
					local wz = p[3] + mz * s
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
