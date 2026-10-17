// The game's own models for GPS3D: where every building (WMO) and prop or tree (M2 doodad) stands on
// every map with terrain, from the tiles' _obj0 files, and how big each model is.
// Run in the MapExplorer page after scripts/browser_export.js has hooked the worker (window.__gps.call):
//   gpsModels.start({ maps: [0, 1] })  -> runs in the background; gpsModels.progress shows where it is
//   gpsModels.download()               -> gps-models.json
// (or run it outside the browser with scripts/export_models_node.ts, which gives it the same worker calls).
// Then: python scripts/build_models.py path/to/gps-models.json prototypes/GPS3D/Data
//
// Output, per map: models [[fileDataID, kind (0 M2, 1 WMO), radius, bottom, top], ...] (model units:
// radius = furthest vertex from the model's origin across the ground, bottom/top = lowest and highest
// vertex; 0, 0, 0 when the model could not be read) and tiles { "tx_ty": [[model index, x, y, h, yaw,
// pitch, roll, scale], ...] } in GPS3D's world coordinates (x east, y north, h up, yards; x = gx * TILE,
// y = -gy * TILE) with the rotation as yaw (about up, from east toward north), pitch (about the
// model's own y) and roll (about its own x), radians, applied in that order (R = Rz(yaw) Ry(pitch)
// Rx(roll)): the ModelScene actor's SetYaw / SetPitch / SetRoll. A placement is listed once, under the
// tile its origin is on (the game lists a big one under every tile it touches).
//
// MapExplorer's placement matrix maps model space (z up) to its world (x east, y up, z south):
// T(pos) RotY(ry - 90) RotZ(-rx) RotX(rz - 90) S(scale). In GPS3D's axes (x east, y north, z up) the
// same matrix is S(scale) times a plain rotation of model space, read back here column by column.
window.gpsModels = (() => {
	const call = (...a) => window.__gps.call(...a);
	const TILE = 1600 / 3;
	const r4 = (v) => Math.round(v * 1e4) / 1e4, r2 = (v) => Math.round(v * 100) / 100;

	// Placement matrix (column-major, MapExplorer's axes) -> [x, y, h, yaw, pitch, roll, scale] in GPS3D's.
	function decompose(M) {
		const g = (j) => [M[j * 4], -M[j * 4 + 2], M[j * 4 + 1]]; // column j in GPS3D's axes
		const c0 = g(0), c1 = g(1), c2 = g(2);
		const s = Math.hypot(...c0);
		// R[i][j]: row i of column j
		const R = (i, j) => [c0, c1, c2][j][i] / s;
		const yaw = Math.atan2(R(1, 0), R(0, 0));
		const pitch = Math.asin(Math.max(-1, Math.min(1, -R(2, 0))));
		const roll = Math.atan2(R(2, 1), R(2, 2));
		return [M[12], -M[14], M[13], yaw, pitch, roll, s];
	}
	// The other way, for checking: [x, y, h, yaw, pitch, roll, scale] -> MapExplorer's matrix.
	function compose([x, y, h, yaw, pitch, roll, s]) {
		const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch), cr = Math.cos(roll), sr = Math.sin(roll);
		const R = [ // Rz(yaw) Ry(pitch) Rx(roll), rows
			[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
			[sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
			[-sp, cp * sr, cp * cr],
		];
		const M = new Array(16).fill(0);
		for (let j = 0; j < 3; j++) { // GPS3D (east, north, up) -> MapExplorer (east, up, south)
			M[j * 4] = R[0][j] * s; M[j * 4 + 1] = R[2][j] * s; M[j * 4 + 2] = -R[1][j] * s;
		}
		M[12] = x; M[13] = h; M[14] = -y; M[15] = 1;
		return M;
	}

	const state = { running: false, progress: '', done: 0, total: 0, maps: {}, stats: {}, errors: [], worstError: 0 };
	const sizes = new Map(); // `${kind}:${fdid}` -> [radius, bottom, top]

	async function measure(list) {
		const todo = list.filter((m) => !sizes.has(`${m.kind}:${m.fdid}`));
		for (let i = 0; i < todo.length; i += 8) {
			const batch = todo.slice(i, i + 8);
			const res = await call('loadModels', batch.map((m) => ({ fdid: m.fdid, kind: m.kind }))).catch((e) => { state.errors.push(`models ${batch.map((m) => m.fdid)}: ${e && e.message || e}`); return []; });
			batch.forEach((m, k) => {
				const d = res[k];
				let r = 0, lo = 0, hi = 0;
				if (d && d.positions && d.positions.length) {
					const P = d.positions;
					lo = Infinity; hi = -Infinity;
					for (let v = 0; v < P.length; v += 3) {
						const rr = P[v] * P[v] + P[v + 1] * P[v + 1];
						if (rr > r) r = rr;
						if (P[v + 2] < lo) lo = P[v + 2];
						if (P[v + 2] > hi) hi = P[v + 2];
					}
					r = Math.sqrt(r);
				} else if (!d) state.errors.push(`model ${m.kind} ${m.fdid}: not readable`);
				sizes.set(`${m.kind}:${m.fdid}`, [r2(r), r2(lo), r2(hi)]);
			});
			state.progress = `${state.mapLabel}: measuring models ${Math.min(i + 8, todo.length)}/${todo.length}`;
		}
	}

	async function start({ maps = null, check = true } = {}) {
		if (state.running) return 'already running';
		Object.assign(state, { running: true, maps: {}, stats: {}, errors: [], done: 0, total: 0, worstError: 0 });
		const t0 = performance.now();
		try {
			const jobs = [];
			for (const m of await call('listMaps')) {
				if (maps && !maps.includes(m.id)) continue;
				const inst = await call('loadInstance', m.id).catch(() => null);
				if (!inst || !inst.wdt) continue;
				const tiles = (inst.farTiles || []).filter((t) => t.hasAdt);
				if (tiles.length) jobs.push({ id: m.id, name: m.name, wdt: inst.wdt, tiles });
			}
			state.total = jobs.reduce((n, j) => n + j.tiles.length, 0);
			for (const job of jobs) {
				state.mapLabel = `map ${job.id}`;
				const seen = new Set(), index = new Map(), models = [], out = {};
				let n = 0, nWmo = 0;
				for (const t of job.tiles) {
					let objs = [];
					try { objs = await call('loadTileObjects', job.wdt, t.x, t.y); } catch (e) { state.errors.push(`${job.id}_${t.x}_${t.y}: ${e && e.message || e}`); }
					for (const o of objs) {
						if ((o.kind !== 'm2' && o.kind !== 'wmo') || seen.has(`${o.kind}:${o.uid}`)) continue;
						seen.add(`${o.kind}:${o.uid}`);
						const key = `${o.kind}:${o.fdid}`;
						let mi = index.get(key);
						if (mi === undefined) { mi = models.length; index.set(key, mi); models.push({ fdid: o.fdid, kind: o.kind }); }
						const p = decompose(o.matrix);
						if (check) {
							const back = compose(p);
							for (let k = 0; k < 16; k++) {
								const err = Math.abs(back[k] - o.matrix[k]) / (k >= 12 ? 1 : Math.max(1, p[6]));
								if (err > state.worstError) state.worstError = err;
							}
						}
						const tx = Math.floor(p[0] / TILE), ty = Math.floor(-p[1] / TILE);
						const tk = `${tx}_${ty}`;
						(out[tk] = out[tk] || []).push([mi, r2(p[0]), r2(p[1]), r2(p[2]), r4(p[3]), r4(p[4]), r4(p[5]), r4(p[6])]);
						n++; if (o.kind === 'wmo') nWmo++;
					}
					state.done++;
					state.progress = `${state.done}/${state.total} tiles, map ${job.id}: ${n} placements, ${models.length} models, ${Math.round((performance.now() - t0) / 1000)} s`;
				}
				await measure(models);
				state.maps[job.id] = {
					name: job.name,
					models: models.map((m) => [m.fdid, m.kind === 'wmo' ? 1 : 0, ...sizes.get(`${m.kind}:${m.fdid}`)]),
					tiles: out,
				};
				state.stats[job.id] = { placements: n, wmos: nWmo, m2s: n - nWmo, models: models.length, tiles: Object.keys(out).length };
			}
			state.progress = `done: ${state.total} tiles in ${Math.round((performance.now() - t0) / 1000)} s, worst matrix error ${state.worstError.toExponential(2)}, ${state.errors.length} errors`;
		} finally { state.running = false; }
		return state.progress;
	}

	function result() {
		return { exportedAt: new Date().toISOString(), format: 'GPS models, see scripts/browser_export_models.js', maps: state.maps, stats: state.stats, errors: state.errors, worstMatrixError: state.worstError };
	}
	function download(name = 'gps-models.json') {
		const blob = new Blob([JSON.stringify(result())], { type: 'application/json' });
		const a = document.createElement('a');
		a.download = name; a.href = URL.createObjectURL(blob);
		document.body.append(a); a.click(); a.remove();
		return { maps: Object.keys(state.maps).length, bytes: blob.size };
	}
	return { start, download, result, decompose, compose, state, get progress() { return state.progress; } };
})();
