-- Lua 5.1 (the game's Lua): parse + run time of a city data file and the heap it keeps. lua5.1 loadtime_city.lua <file> <runs>
local path, runs = arg[1], tonumber(arg[2]) or 3
local f = assert(io.open(path, "rb")); local bytes = #f:read("*a"); f:close()
local best, mem = math.huge, 0
for _ = 1, runs do
	local ns = {}
	collectgarbage("collect"); collectgarbage("collect")
	local m0 = collectgarbage("count")
	local t0 = os.clock()
	local chunk = assert(loadfile(path))
	chunk("City", ns)
	local t = (os.clock() - t0) * 1000
	collectgarbage("collect"); collectgarbage("collect")
	mem = (collectgarbage("count") - m0) / 1024
	if t < best then best = t end
	ns = nil
end
print(string.format("%s: %d bytes, parse+run %.0f ms (fastest of %d), heap kept %.1f MB", path:match("[^/]+$"), bytes, best, runs, mem))
