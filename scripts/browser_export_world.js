// Exports the 3D view's terrain for every map with ADT terrain, from MapExplorer's storage worker.
// Run in the MapExplorer page after scripts/browser_export.js has hooked the worker (window.__gps.call):
//   await gpsExportWorld()          -> downloads gps-world-heights.json (about 5 MB, 2 minutes)
// Then: python scripts/build_world.py path/to/gps-world-heights.json prototypes/GPS3D/Data
//
// Per tile: a 33 x 33 grid, every 4th of the ADT's 129 x 129 height vertices (16.7 yards apart), the
// higher of the ground, any liquid surface at that vertex, and sea level (0) on chunks flagged as sea.
// Encoded as 3 base64 characters (lowest height in half yards + 131072) and then 2 characters per
// height (half yards above that lowest height).
window.gpsExportWorld = async function gpsExportWorld({ onProgress = () => {} } = {}) {
	const call = window.__gps && window.__gps.call;
	if (!call) throw new Error('The storage worker is not hooked yet: run scripts/browser_export.js and move the camera once');
	const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
	const S = 33, STEP = 4, V = 129, CELL = (1600 / 3) / 128;
	const maps = {}, range = {}, clamped = {};
	for (const m of await call('listMaps')) {
		const inst = await call('loadInstance', m.id).catch(() => null);
		if (!inst || !inst.wdt) continue;
		const tiles = (inst.farTiles || []).filter((t) => t.hasAdt);
		if (!tiles.length) continue;
		const entry = maps[m.id] = { name: m.name, category: m.category, tiles: {} };
		for (const ft of tiles) {
			const nt = await call('loadNearTile', inst.wdt, ft.x, ft.y);
			const h = nt.heights, sea = nt.sea;
			const water = new Float32Array(V * V).fill(-Infinity);
			for (const lq of nt.liquids || []) {
				const P = lq.positions;
				for (let k = 0; k < P.length / 3; k++) {
					const c = Math.round(P[k * 3] / CELL), r = Math.round(P[k * 3 + 2] / CELL);
					if (c >= 0 && c < V && r >= 0 && r < V) { const i = r * V + c; if (P[k * 3 + 1] > water[i]) water[i] = P[k * 3 + 1]; }
				}
			}
			const q = new Int32Array(S * S);
			let lo = Infinity, hi = -Infinity;
			for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
				const r = j * STEP, c = i * STEP, idx = r * V + c;
				let w = water[idx];
				if (sea) for (const [cr, cc] of [[r - 1, c - 1], [r - 1, c], [r, c - 1], [r, c]]) {
					const ch = Math.floor(cr / 8), cw = Math.floor(cc / 8);
					if (ch >= 0 && ch < 16 && cw >= 0 && cw < 16 && sea[ch * 16 + cw] && w < 0) w = 0;
				}
				const qq = Math.round(Math.max(h[idx], w) * 2);
				q[j * S + i] = qq; if (qq < lo) lo = qq; if (qq > hi) hi = qq;
			}
			const base = lo + 131072;
			let s = B64[(base >> 12) & 63] + B64[(base >> 6) & 63] + B64[base & 63];
			for (let k = 0; k < S * S; k++) {
				let d = q[k] - lo;
				if (d > 4095) { d = 4095; clamped[m.id] = (clamped[m.id] || 0) + 1; }
				s += B64[d >> 6] + B64[d & 63];
			}
			range[m.id] = Math.max(range[m.id] || 0, (hi - lo) / 2);
			entry.tiles[ft.x + '_' + ft.y] = s;
		}
		onProgress(`${m.name}: ${tiles.length} tiles`);
	}
	const data = { exportedAt: new Date().toISOString(), format: 'base3+33x33x2 b64, half yards, max(ground, water, sea level 0 on sea chunks)', maps, range, clamped };
	const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
	const a = document.createElement('a');
	a.download = 'gps-world-heights.json';
	a.href = URL.createObjectURL(blob);
	document.body.append(a);
	a.click();
	a.remove();
	return { maps: Object.keys(maps).length, tiles: Object.values(maps).reduce((n, m) => n + Object.keys(m.tiles).length, 0), clamped };
};
