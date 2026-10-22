-- Perf round A5: what each addon's data costs to load, in Lua 5.1 (the game's Lua), as the review J9
-- measured it (its loadtime.lua): every data file a TOC lists is parsed and run with the addon's
-- namespace, then the Lua heap is measured after a full collection.
-- Usage (from the repository root): lua5.1 testing/2026-10-22-perf-round/a5_loadtime.lua <runs> <toc> [<toc> ...]
-- For GPS3D.toc only the files under Data\ count (the code needs the game's API); for a data addon
-- every file but its Link.lua (which hands GPS3D's namespace over; here the data is kept in one table).
-- Prints per TOC: files, bytes, parse+run ms (the fastest of <runs>), heap kept (MB).
local runs = tonumber(arg[1]) or 3
local shared -- the namespace the data landed in (GPS3D's, through Link.lua in the game)
for i = 2, #arg do
	local toc = arg[i]
	local dir = toc:match("^(.*)[/\\][^/\\]+$") or "."
	local main = toc:match("GPS3D%.toc$") ~= nil
	local files, bytes = {}, 0
	for line in io.lines(toc) do
		line = line:gsub("\r", "")
		if line ~= "" and not line:match("^#") and not line:match("Link%.lua$") and (not main or line:match("^Data\\")) then
			local path = dir .. "/" .. line:gsub("\\", "/")
			local f = assert(io.open(path, "rb"))
			bytes = bytes + #f:read("*a")
			f:close()
			files[#files + 1] = path
		end
	end
	local best, mem = math.huge, 0
	for _ = 1, runs do
		local ns = {}
		shared = nil -- (the last run's data goes before the heap is measured)
		collectgarbage("collect"); collectgarbage("collect")
		local m0 = collectgarbage("count")
		local t0 = os.clock()
		for _, path in ipairs(files) do assert(loadfile(path))("addon", ns) end
		local dt = os.clock() - t0
		collectgarbage("collect"); collectgarbage("collect")
		mem = (collectgarbage("count") - m0) / 1024
		if dt < best then best = dt end
		shared = ns
	end
	shared = nil
	io.write(string.format("%-58s %3d files %6.1f MB on disk  %5.0f ms  %5.1f MB heap\n", toc, #files, bytes / 1048576, best * 1000, mem))
end
