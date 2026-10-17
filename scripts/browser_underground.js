// Which buildings (WMOs) are underground: caves and mines, whose rooms and rock lie in the ground. The
// building exports (browser_export_detail.js, browser_export_models.js) leave them out, so the 3D view
// keeps the ground there instead of raising it by the cave's rock and tunnels.
// Load it in the MapExplorer page before those scripts (after scripts/browser_export.js has hooked the
// worker: window.__gps.call); scripts/export_detail_node.ts and export_models_node.ts load it themselves.
//   await gpsUnderground.shares(wdt, matrix, groups) -> { rooms, shell }: shares below the ground (or null)
//   await gpsUnderground.isUnderground(wdt, matrix, groups)
//
// Share below the ground: of a set of WMO groups' bounding boxes (weighted by volume; 4 x 4 x 3 points
// spread inside each box, placed by the WMO's matrix), how much lies more than BELOW (1 yard) under the
// ground (the ADT's 129 x 129 heights, bilinear). A WMO is underground when
//   - its interior groups (rooms) are at least ROOMS (0.7) below the ground: over the 16 maps GPS3D has,
//     rooms fall in two groups (caves, mines, crypts and the like near 1, houses with cellars far below
//     0.7; 413 WMOs at 0.7, and the boxes agree with the rooms' own vertices on all but 6 of about 4,200), and
//   - its exterior groups are at least SHELL (0.15) below the ground (or it has none): a cave's or mine's
//     rock shell lies partly in the hillside, while a building standing on the ground over underground
//     rooms has its exterior above it (0 to 0.06; by their positions the ruins over the Undercity,
//     Karazhan, crypts, the Deadmines' entrance in Moonbrook); those are kept, 31 of the 413. WMOs without rooms are never
//     underground.
window.gpsUnderground = (() => {
	const call = (...a) => window.__gps.call(...a);
	const TILE = 1600 / 3, V = 129, STEP = TILE / 128;
	const ROOMS = 0.7, SHELL = 0.15, BELOW = 1, KEEP_TILES = 64;
	const heights = new Map(); // `${wdt}_${tx}_${ty}` -> 129 x 129 heights, or null (no tile)

	function remember(wdt, tx, ty, h) {
		const k = `${wdt}_${tx}_${ty}`;
		heights.delete(k);
		heights.set(k, h);
		while (heights.size > KEEP_TILES) heights.delete(heights.keys().next().value);
	}
	async function tileHeights(wdt, tx, ty) {
		const k = `${wdt}_${tx}_${ty}`;
		if (heights.has(k)) { const h = heights.get(k); remember(wdt, tx, ty, h); return h; }
		let h = null;
		try { h = (await call('loadNearTile', wdt, tx, ty)).heights || null; } catch { /* no tile there */ }
		remember(wdt, tx, ty, h);
		return h;
	}
	// ground height at MapExplorer's X (east), Z (south), or null
	async function ground(wdt, X, Z) {
		const tx = Math.floor(X / TILE), ty = Math.floor(Z / TILE);
		const h = await tileHeights(wdt, tx, ty);
		if (!h) return null;
		const fc = (X - tx * TILE) / STEP, fr = (Z - ty * TILE) / STEP;
		const c = Math.max(0, Math.min(127, Math.floor(fc))), r = Math.max(0, Math.min(127, Math.floor(fr)));
		const u = fc - c, v = fr - r;
		return h[r * V + c] * (1 - u) * (1 - v) + h[r * V + c + 1] * u * (1 - v) + h[(r + 1) * V + c] * (1 - u) * v + h[(r + 1) * V + c + 1] * u * v;
	}
	// a model's groups' boxes (from loadModels: ModelData.areas.groups, model space)
	function groups(model) {
		return ((model && model.areas && model.areas.groups) || []).map((g) => ({ interior: !!g.interior, min: Array.from(g.min), max: Array.from(g.max) }));
	}
	// share of the boxes (by volume) below the ground, for a placement matrix (column-major, model -> MapExplorer world)
	async function share(wdt, M, boxes) {
		let below = 0, total = 0;
		for (const b of boxes) {
			const dx = b.max[0] - b.min[0], dy = b.max[1] - b.min[1], dz = b.max[2] - b.min[2];
			const vol = Math.max(1, dx * dy * dz);
			let n = 0, under = 0;
			for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 3; k++) {
				const x = b.min[0] + (i + 0.5) / 4 * dx, y = b.min[1] + (j + 0.5) / 4 * dy, z = b.min[2] + (k + 0.5) / 3 * dz;
				const X = M[0] * x + M[4] * y + M[8] * z + M[12], Y = M[1] * x + M[5] * y + M[9] * z + M[13], Z = M[2] * x + M[6] * y + M[10] * z + M[14];
				const g = await ground(wdt, X, Z);
				if (g === null) continue;
				n++;
				if (Y < g - BELOW) under++;
			}
			if (n) { below += vol * under / n; total += vol; }
		}
		return total ? below / total : null;
	}
	async function shares(wdt, M, gs) {
		const rooms = gs.filter((g) => g.interior), outside = gs.filter((g) => !g.interior);
		const r = rooms.length ? await share(wdt, M, rooms) : null;
		return { rooms: r, shell: r !== null && r >= ROOMS && outside.length ? await share(wdt, M, outside) : null };
	}
	async function isUnderground(wdt, M, gs) {
		if (!gs || !gs.some((g) => g.interior)) return false;
		const s = await shares(wdt, M, gs);
		return s.rooms !== null && s.rooms >= ROOMS && (s.shell === null || s.shell >= SHELL);
	}
	return { shares, isUnderground, groups, remember, ground, ROOMS, SHELL, BELOW };
})();
