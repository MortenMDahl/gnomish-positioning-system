// Detailed meshes (buildings raised into the ground) for GPS3D, for every tile of the world that has
// buildings (WMOs), from MapExplorer's storage worker.
// Run in the MapExplorer page after scripts/browser_export.js has hooked the worker (window.__gps.call):
//   gpsDetail.start({ maps: [0] })    -> runs in the background; gpsDetail.progress shows where it is
//   gpsDetail.download()              -> gps-detail.json (three strings per tile: tiles, low, far; see below)
//   await gpsDetail.tile(0, 32, 48)   -> one tile, with statistics (for trying settings)
// Then: python scripts/build_detail.py path/to/gps-detail.json prototypes/GPS3D/Data
//
// Per tile: a 513 x 513 height raster (1.04 yards apart) of the highest of the ground (the ADT's 129 x 129
// heights), water (liquids; sea level on sea chunks) and every WMO's geometry and liquids; the WMO's
// texture colour is kept where a wall is (WMO faces steeper than about 78 degrees, wallSlope); every WMO
// face raises the surface, steep roofs and spires included. The
// raster becomes a triangle mesh (greedy Delaunay refinement, mapbox/delatin) within maxError yards near
// buildings (within 4 samples of a raised WMO or a wall) and groundError yards elsewhere: the ground
// away from buildings only needs to be about as good as the 3D view's 16.7-yard grid.
// Each block is meshed three times: fine (every sample), coarse (every 4th sample, coarseError) and far
// (every 8th, farError).
// Tiles where no building rises more than 1.5 yards above the ground over at least minRaised samples,
// and blocks with fewer than minBlock such samples, are left out (the 3D view's grid covers them).
//
// String per tile: "D2", block count (2 chars), then per block: block index (1 char: by * 8 + bx; a block
// is 64 x 64 raster steps = 66.7 yards), base (3 chars: lowest height in quarter yards + 131072), vertex
// count (3), triangle count (3), palette size (1), palette (3 chars per colour: 6 bits r, g, b), vertices
// (6 chars = 36 bits: x 7 | y 7 | height above base in quarter yards 16 | colour 6, 0 = ground), then
// triangle corners (2 chars each, 3 when the block has more than 4095 vertices; 0-based). x east and
// y south in raster steps (TILE / 512 yards) from the block's north-west corner. Triangles wind as the
// Northshire mesh: (b - a) x (c - a) < 0 in (x east, y south).
window.gpsDetail = (() => {
	const call = (...a) => window.__gps.call(...a);
	const TILE = 1600 / 3, N = 512, S = N + 1, CELL = TILE / N, V = 129, LQ = TILE / 128;
	const B = 8, BS = N / B, BW = BS + 1; // blocks per tile side, samples per block side
	const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
	const enc = (v, n) => { let s = ''; for (let k = n - 1; k >= 0; k--) s += B64[Math.floor(v / 64 ** k) % 64]; return s; };
	let Delatin = null;
	let WEIGHT = null; // per raster sample: 1 / allowed error (set before each mesh is made)
	function orient(ax, ay, bx, by, cx, cy) { return (bx - cx) * (ay - cy) - (by - cy) * (ax - cx); }
	// delatin, with the error at each sample scaled by WEIGHT (tight near buildings, loose elsewhere)
	async function weightedDelatin() {
		const D = (await import('https://cdn.jsdelivr.net/npm/delatin@0.2.0/+esm')).default;
		class W extends D {}
		W.prototype._findCandidate = function (p0x, p0y, p1x, p1y, p2x, p2y, t) {
			const minX = Math.min(p0x, p1x, p2x), minY = Math.min(p0y, p1y, p2y);
			const maxX = Math.max(p0x, p1x, p2x), maxY = Math.max(p0y, p1y, p2y);
			let w00 = orient(p1x, p1y, p2x, p2y, minX, minY);
			let w01 = orient(p2x, p2y, p0x, p0y, minX, minY);
			let w02 = orient(p0x, p0y, p1x, p1y, minX, minY);
			const a01 = p1y - p0y, b01 = p0x - p1x, a12 = p2y - p1y, b12 = p1x - p2x, a20 = p0y - p2y, b20 = p2x - p0x;
			const a = orient(p0x, p0y, p1x, p1y, p2x, p2y);
			const z0 = this.heightAt(p0x, p0y) / a, z1 = this.heightAt(p1x, p1y) / a, z2 = this.heightAt(p2x, p2y) / a;
			let maxError = 0, mx = 0, my = 0;
			const width = this.width;
			for (let y = minY; y <= maxY; y++) {
				let dx = 0;
				if (w00 < 0 && a12 !== 0) dx = Math.max(dx, Math.floor(-w00 / a12));
				if (w01 < 0 && a20 !== 0) dx = Math.max(dx, Math.floor(-w01 / a20));
				if (w02 < 0 && a01 !== 0) dx = Math.max(dx, Math.floor(-w02 / a01));
				let w0 = w00 + a12 * dx, w1 = w01 + a20 * dx, w2 = w02 + a01 * dx;
				let wasInside = false;
				for (let x = minX + dx; x <= maxX; x++) {
					if (w0 >= 0 && w1 >= 0 && w2 >= 0) {
						wasInside = true;
						const z = z0 * w0 + z1 * w1 + z2 * w2;
						const dz = Math.abs(z - this.heightAt(x, y)) * WEIGHT[width * y + x];
						if (dz > maxError) { maxError = dz; mx = x; my = y; }
					} else if (wasInside) break;
					w0 += a12; w1 += a20; w2 += a01;
				}
				w00 += b12; w01 += b20; w02 += b01;
			}
			if (mx === p0x && my === p0y || mx === p1x && my === p1y || mx === p2x && my === p2y) maxError = 0;
			this._candidates[2 * t] = mx;
			this._candidates[2 * t + 1] = my;
			this._queuePush(t, maxError);
		};
		return W;
	}
	const models = new Map(); let modelBytes = 0;
	const MODEL_BUDGET = 900e6;
	const colours = new Map();

	async function model(fdid) {
		if (models.has(fdid)) { const m = models.get(fdid); models.delete(fdid); models.set(fdid, m); return m; }
		const [m] = await call('loadModels', [{ fdid, kind: 'wmo' }]).catch(() => [null]);
		let keep = null;
		if (m && m.positions && m.indices) {
			keep = {
				positions: m.positions, indices: m.indices,
				batches: (m.batches || []).filter((b) => (b.material?.blend ?? 0) <= 1).map((b) => ({ start: b.start, count: b.count, tex: b.material?.texture ?? 0 })),
				liquids: (m.liquids || []).map((l) => ({ positions: l.positions, indices: l.indices })),
			};
			keep.bytes = m.positions.byteLength + m.indices.byteLength;
		}
		models.set(fdid, keep);
		modelBytes += keep ? keep.bytes : 0;
		while (modelBytes > MODEL_BUDGET && models.size > 1) {
			const [k, v] = models.entries().next().value;
			models.delete(k);
			modelBytes -= v ? v.bytes : 0;
		}
		return keep;
	}

	async function colourOf(fdid) {
		if (colours.has(fdid)) return colours.get(fdid);
		let c = [0.6, 0.58, 0.52];
		try {
			const [t] = await call('loadTextures', [fdid], false);
			const tex = t && t.texture;
			const mip = tex && tex.mips && tex.mips[0];
			if (mip && tex.format === 'rgba') {
				const d = mip.data, step = Math.max(1, Math.floor(d.length / 4 / 4096));
				let r = 0, g = 0, b = 0, w = 0;
				for (let p = 0; p < d.length / 4; p += step) { const a = d[p * 4 + 3] / 255; r += d[p * 4] * a; g += d[p * 4 + 1] * a; b += d[p * 4 + 2] * a; w += a; }
				if (w > 0) c = [r / w / 255, g / w / 255, b / w / 255];
			}
		} catch { /* keep the default stone colour */ }
		colours.set(fdid, c);
		return c;
	}

	// Rasterize triangles (local raster coordinates) into H, keeping the highest; returns samples raised.
	function rasterTri(H, src, ax, az, ay, bx, bz, by, cx, cz, cy, col) {
		const x0 = Math.max(0, Math.ceil(Math.min(ax, bx, cx))), x1 = Math.min(N, Math.floor(Math.max(ax, bx, cx)));
		if (x0 > x1) return;
		const z0 = Math.max(0, Math.ceil(Math.min(az, bz, cz))), z1 = Math.min(N, Math.floor(Math.max(az, bz, cz)));
		if (z0 > z1) return;
		const d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz);
		if (Math.abs(d) < 1e-9) return;
		for (let j = z0; j <= z1; j++) {
			for (let i = x0; i <= x1; i++) {
				const w1 = ((bz - cz) * (i - cx) + (cx - bx) * (j - cz)) / d;
				const w2 = ((cz - az) * (i - cx) + (ax - cx) * (j - cz)) / d;
				const w3 = 1 - w1 - w2;
				if (w1 < -1e-4 || w2 < -1e-4 || w3 < -1e-4) continue;
				const y = w1 * ay + w2 * by + w3 * cy;
				const k = j * S + i;
				if (y > H[k]) { H[k] = y; src[k] = col; }
			}
		}
	}

	// Near-vertical triangle: stamp its colour along its footprint (wall colour for nearby samples).
	function stampWall(wall, wallTop, ax, az, ay, bx, bz, by, cx, cz, cy, col) {
		const top = Math.max(ay, by, cy);
		const pts = [[ax, az], [bx, bz], [cx, cz]];
		for (let e = 0; e < 3; e++) {
			const [px, pz] = pts[e], [qx, qz] = pts[(e + 1) % 3];
			const len = Math.hypot(qx - px, qz - pz), n = Math.max(1, Math.ceil(len * 2));
			for (let s = 0; s <= n; s++) {
				const x = px + (qx - px) * s / n, z = pz + (qz - pz) * s / n;
				for (const i of [Math.floor(x), Math.ceil(x)]) for (const j of [Math.floor(z), Math.ceil(z)]) {
					if (i < 0 || i > N || j < 0 || j > N) continue;
					const k = j * S + i;
					if (top > wallTop[k]) { wallTop[k] = top; wall[k] = col; }
				}
			}
		}
	}

	async function tile(map, tx, ty, { maxError = 1, groundError = 4, coarseError = 2, farError = 3, wallSlope = 0.2, near = 4, minRaised = 40, minBlock = 16, wdt = null, objects = null } = {}) {
		const T0 = performance.now();
		if (!Delatin) Delatin = await weightedDelatin();
		if (!wdt) wdt = (await call('loadInstance', map)).wdt;
		const objs = objects || await call('loadTileObjects', wdt, tx, ty);
		const seen = new Set();
		const wmos = objs.filter((o) => o.kind === 'wmo' && !seen.has(o.uid) && seen.add(o.uid));
		if (!wmos.length) return { key: `${map}_${tx}_${ty}`, skipped: 'no WMO' };
		const nt = await call('loadNearTile', wdt, tx, ty);
		const h = nt.heights, sea = nt.sea;
		const water = new Float32Array(V * V).fill(-Infinity);
		for (const lq of nt.liquids || []) {
			const P = lq.positions;
			for (let k = 0; k < P.length / 3; k++) {
				const c = Math.round(P[k * 3] / LQ), r = Math.round(P[k * 3 + 2] / LQ);
				if (c >= 0 && c < V && r >= 0 && r < V) { const i = r * V + c; if (P[k * 3 + 1] > water[i]) water[i] = P[k * 3 + 1]; }
			}
		}
		const G = new Float32Array(V * V);
		for (let r = 0; r < V; r++) for (let c = 0; c < V; c++) {
			const idx = r * V + c;
			let w = water[idx];
			if (sea) for (const [cr, cc] of [[r - 1, c - 1], [r - 1, c], [r, c - 1], [r, c]]) {
				const ch = Math.floor(cr / 8), cw = Math.floor(cc / 8);
				if (ch >= 0 && ch < 16 && cw >= 0 && cw < 16 && sea[ch * 16 + cw] && w < 0) w = 0;
			}
			G[idx] = Math.max(h[idx], w);
		}
		const H = new Float32Array(S * S), base = new Float32Array(S * S);
		for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) {
			const fr = j / 4, fc = i / 4, r0 = Math.min(127, Math.floor(fr)), c0 = Math.min(127, Math.floor(fc));
			const u = fc - c0, v = fr - r0;
			const g00 = G[r0 * V + c0], g10 = G[r0 * V + c0 + 1], g01 = G[(r0 + 1) * V + c0], g11 = G[(r0 + 1) * V + c0 + 1];
			const k = j * S + i;
			H[k] = base[k] = g00 * (1 - u) * (1 - v) + g10 * u * (1 - v) + g01 * (1 - u) * v + g11 * u * v;
		}
		const src = new Uint16Array(S * S), wall = new Uint16Array(S * S), wallTop = new Float32Array(S * S).fill(-Infinity);
		const texIds = [0];
		const texIndex = new Map();
		let wmoTris = 0;
		const TL = performance.now();
		for (const o of wmos) {
			const m = await model(o.fdid);
			if (!m) continue;
			const M = o.matrix, P = m.positions, n = P.length / 3;
			const L = new Float32Array(n * 3); // raster x, raster z, height
			let inside = false;
			for (let k = 0; k < n; k++) {
				const x = P[k * 3], y = P[k * 3 + 1], z = P[k * 3 + 2];
				const X = M[0] * x + M[4] * y + M[8] * z + M[12];
				const Y = M[1] * x + M[5] * y + M[9] * z + M[13];
				const Z = M[2] * x + M[6] * y + M[10] * z + M[14];
				const lx = (X - tx * TILE) / CELL, lz = (Z - ty * TILE) / CELL;
				L[k * 3] = lx; L[k * 3 + 1] = lz; L[k * 3 + 2] = Y;
				if (lx >= -1 && lx <= N + 1 && lz >= -1 && lz <= N + 1) inside = true;
			}
			if (!inside) continue;
			const I = m.indices;
			for (const b of m.batches) {
				let col = texIndex.get(b.tex);
				if (col === undefined) { col = texIds.length; texIds.push(b.tex); texIndex.set(b.tex, col); }
				for (let t = b.start; t < b.start + b.count; t += 3) {
					const a = I[t] * 3, bb = I[t + 1] * 3, c = I[t + 2] * 3;
					const ax = L[a], az = L[a + 1], ay = L[a + 2], bx = L[bb], bz = L[bb + 1], by = L[bb + 2], cx = L[c], cz = L[c + 1], cy = L[c + 2];
					if (Math.max(ax, bx, cx) < 0 || Math.min(ax, bx, cx) > N || Math.max(az, bz, cz) < 0 || Math.min(az, bz, cz) > N) continue;
					wmoTris++;
					// steepness: footprint area vs 3D area (in yards)
					const e1x = (bx - ax) * CELL, e1z = (bz - az) * CELL, e1y = by - ay, e2x = (cx - ax) * CELL, e2z = (cz - az) * CELL, e2y = cy - ay;
					const nx = e1y * e2z - e1z * e2y, ny = e1z * e2x - e1x * e2z, nz = e1x * e2y - e1y * e2x;
					const area = Math.hypot(nx, ny, nz);
					if (area < 1e-6) continue;
					// every face raises the surface (steep roofs and spires too); near-vertical ones are also walls
					rasterTri(H, src, ax, az, ay, bx, bz, by, cx, cz, cy, col);
					if (Math.abs(ny) / area < wallSlope) stampWall(wall, wallTop, ax, az, ay, bx, bz, by, cx, cz, cy, col);
				}
			}
			for (const lq of m.liquids) {
				const Q = lq.positions, J = lq.indices, nq = Q.length / 3;
				const LQV = new Float32Array(nq * 3);
				for (let k = 0; k < nq; k++) {
					const x = Q[k * 3], y = Q[k * 3 + 1], z = Q[k * 3 + 2];
					LQV[k * 3] = (M[0] * x + M[4] * y + M[8] * z + M[12] - tx * TILE) / CELL;
					LQV[k * 3 + 1] = (M[2] * x + M[6] * y + M[10] * z + M[14] - ty * TILE) / CELL;
					LQV[k * 3 + 2] = M[1] * x + M[5] * y + M[9] * z + M[13];
				}
				for (let t = 0; t < J.length; t += 3) {
					const a = J[t] * 3, bb = J[t + 1] * 3, c = J[t + 2] * 3;
					rasterTri(H, src, LQV[a], LQV[a + 1], LQV[a + 2], LQV[bb], LQV[bb + 1], LQV[bb + 2], LQV[c], LQV[c + 1], LQV[c + 2], 0);
				}
			}
		}
		let raised = 0;
		for (let k = 0; k < S * S; k++) if (src[k] && H[k] - base[k] > 1.5) raised++;
		const key = `${map}_${tx}_${ty}`;
		if (raised < minRaised) return { key, skipped: 'nothing raised', raised, wmos: wmos.length };
		const TD = performance.now();
		// allowed error: maxError within `near` samples of a building (raised WMO or wall), groundError elsewhere
		const mark = new Uint8Array(S * S);
		for (let k = 0; k < S * S; k++) if ((src[k] && H[k] - base[k] > 1.5) || wall[k]) mark[k] = 1;
		const rowMax = new Uint8Array(S * S);
		for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) {
			let m = 0;
			for (let d = -near; d <= near && !m; d++) { const ii = i + d; if (ii >= 0 && ii <= N && mark[j * S + ii]) m = 1; }
			rowMax[j * S + i] = m;
		}
		WEIGHT = new Float32Array(S * S);
		for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) {
			let m = 0;
			for (let d = -near; d <= near && !m; d++) { const jj = j + d; if (jj >= 0 && jj <= N && rowMax[jj * S + i]) m = 1; }
			WEIGHT[j * S + i] = m ? 1 / maxError : 1 / groundError;
		}
		// one mesh per block of 64 x 64 samples (66.7 yards; 8 x 8 blocks per tile) that has buildings
		// one mesh per block of 64 x 64 samples (66.7 yards; 8 x 8 blocks per tile) that has buildings,
		// three times: fine (every sample, maxError near buildings), coarse and far (below), for blocks
		// further from the view
		const colourIndexOf = async (k, palette, palIndex) => {
			// colour only where a wall stands (roofs and other surfaces show the minimap in the 3D view)
			const t = wall[k] && wallTop[k] > H[k] - 3 ? wall[k] : 0;
			if (!t) return 0;
			const c = await colourOf(texIds[t]);
			const ck = c.map((x) => Math.max(0, Math.min(63, Math.round(x * 63))));
			const id = ck.join(',');
			let p = palIndex.get(id);
			if (p === undefined) {
				if (palette.length < 63) { palette.push(ck); p = palette.length; }
				else { // nearest existing colour
					let best = 1, bd = Infinity;
					palette.forEach((pc, i) => { const dd = (pc[0] - ck[0]) ** 2 + (pc[1] - ck[1]) ** 2 + (pc[2] - ck[2]) ** 2; if (dd < bd) { bd = dd; best = i + 1; } });
					p = best;
				}
				palIndex.set(id, p);
			}
			return p;
		};
		// mesh of a block: data (side x side), weights, sample spacing in raster steps; returns the encoded block
		const meshBlock = async (bx, by, data, weights, side, spacing, heightOf, sampleOf) => {
			const tileWeight = WEIGHT;
			WEIGHT = weights;
			const tin = new Delatin(data, side, side);
			tin.run(1);
			WEIGHT = tileWeight;
			const coords = tin.coords, tris = tin.triangles, nv = coords.length / 2, nt = tris.length / 3;
			const palette = [], palIndex = new Map(), vcol = new Uint8Array(nv), q = new Int32Array(nv);
			let qmin = Infinity;
			for (let v = 0; v < nv; v++) {
				q[v] = Math.round(heightOf(coords[v * 2], coords[v * 2 + 1]) * 4);
				if (q[v] < qmin) qmin = q[v];
				vcol[v] = await colourIndexOf(sampleOf(coords[v * 2], coords[v * 2 + 1]), palette, palIndex);
			}
			const iw = nv > 4095 ? 3 : 2;
			const parts = [enc(by * B + bx, 1) + enc(qmin + 131072, 3) + enc(nv, 3) + enc(nt, 3) + enc(palette.length, 1)];
			for (const c of palette) parts.push(B64[c[0]] + B64[c[1]] + B64[c[2]]);
			for (let v = 0; v < nv; v++) {
				const dh = Math.min(65535, q[v] - qmin);
				parts.push(enc(((coords[v * 2] * spacing * 128 + coords[v * 2 + 1] * spacing) * 65536 + dh) * 64 + vcol[v], 6)); // 36 bits
			}
			// delatin winds every triangle the same way as the Northshire mesh (cross product of x east, y south < 0)
			for (let t = 0; t < nt * 3; t++) parts.push(enc(tris[t], iw));
			return { str: parts.join(''), nv, nt };
		};
		const blocks = [], lows = [], fars = [], blockStats = [];
		let nvAll = 0, ntAll = 0, ntLow = 0, ntFar = 0;
		for (let by = 0; by < B; by++) for (let bx = 0; bx < B; bx++) {
			const sub = new Float32Array(BW * BW), subW = new Float32Array(BW * BW);
			let marks = 0;
			for (let j = 0; j < BW; j++) for (let i = 0; i < BW; i++) {
				const k = (by * BS + j) * S + bx * BS + i;
				sub[j * BW + i] = H[k]; subW[j * BW + i] = WEIGHT[k]; marks += mark[k];
			}
			if (marks < minBlock) continue;
			const at = (i, j) => (by * BS + j) * S + bx * BS + i;
			const fine = await meshBlock(bx, by, sub, subW, BW, 1, (i, j) => H[at(i, j)], (i, j) => at(i, j));
			// coarser levels: every sp-th sample (r > 0 would take the highest within r around it, which
			// keeps spires but makes buildings fatter than their roofs on the minimap): coarse (sp 4, 4.2
			// yards) and far (sp 8, 8.3 yards)
			const level = async (sp, r, err, ground) => {
				const W = BS / sp + 1;
				const low = new Float32Array(W * W), lowW = new Float32Array(W * W), lowK = new Int32Array(W * W);
				for (let j = 0; j < W; j++) for (let i = 0; i < W; i++) {
					let best = -Infinity, bestK = at(i * sp, j * sp);
					for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
						const ii = bx * BS + i * sp + di, jj = by * BS + j * sp + dj;
						if (ii < 0 || ii > N || jj < 0 || jj > N) continue;
						const k = jj * S + ii;
						if (H[k] > best) { best = H[k]; bestK = k; }
					}
					low[j * W + i] = best;
					lowK[j * W + i] = bestK;
					lowW[j * W + i] = WEIGHT[at(i * sp, j * sp)] > 1 / groundError + 1e-6 ? 1 / err : 1 / ground;
				}
				return meshBlock(bx, by, low, lowW, W, sp, (i, j) => low[j * W + i], (i, j) => lowK[j * W + i]);
			};
			const coarse = await level(4, 0, coarseError, groundError * 1.5);
			const far = await level(8, 0, farError, groundError * 2);
			blocks.push(fine.str);
			lows.push(coarse.str);
			fars.push(far.str);
			blockStats.push(fine.nt);
			nvAll += fine.nv; ntAll += fine.nt; ntLow += coarse.nt; ntFar += far.nt;
		}
		const TE = performance.now();
		if (!blocks.length) return { key, skipped: 'no block with buildings', raised, wmos: wmos.length };
		const str = 'D2' + enc(blocks.length, 2) + blocks.join('');
		const low = 'D2' + enc(lows.length, 2) + lows.join('');
		const farStr = 'D2' + enc(fars.length, 2) + fars.join('');
		return {
			key, str, low, far: farStr, blocks: blocks.length, nv: nvAll, ntri: ntAll, ntriLow: ntLow, ntriFar: ntFar, maxBlockTris: Math.max(...blockStats), raised, wmos: wmos.length, wmoTris, bytes: str.length, bytesLow: low.length,
			ms: { load: Math.round(TL - T0), raster: Math.round(TD - TL), mesh: Math.round(TE - TD), total: Math.round(performance.now() - T0) },
		};
	}

	const state = { running: false, progress: '', done: 0, total: 0, tiles: {}, low: {}, far: {}, stats: [], errors: [] };
	async function start({ maps = null, maxError = 1, groundError = 4, minRaised = 40 } = {}) {
		if (state.running) return 'already running';
		state.running = true; state.tiles = {}; state.low = {}; state.far = {}; state.stats = []; state.errors = []; state.done = 0;
		try {
			const list = [];
			for (const m of await call('listMaps')) {
				if (maps && !maps.includes(m.id)) continue;
				const inst = await call('loadInstance', m.id).catch(() => null);
				if (!inst || !inst.wdt) continue;
				for (const ft of (inst.farTiles || []).filter((t) => t.hasAdt)) list.push([m.id, inst.wdt, ft.x, ft.y]);
			}
			state.total = list.length;
			const t0 = performance.now();
			for (const [map, wdt, x, y] of list) {
				try {
					const r = await tile(map, x, y, { maxError, groundError, minRaised, wdt });
					if (r.str) { state.tiles[r.key] = r.str; state.low[r.key] = r.low; state.far[r.key] = r.far; const { str, low, far, ...rest } = r; state.stats.push(rest); }
				} catch (e) { state.errors.push(`${map}_${x}_${y}: ${e && e.message || e}`); }
				state.done++;
				const el = (performance.now() - t0) / 1000;
				state.progress = `${state.done}/${state.total} tiles, ${Object.keys(state.tiles).length} with buildings, ${Math.round(el)} s, models cached ${Math.round(modelBytes / 1e6)} MB`;
			}
		} finally { state.running = false; }
		return state.progress;
	}
	function download(name = 'gps-detail.json') {
		const data = { exportedAt: new Date().toISOString(), format: 'D2, see scripts/browser_export_detail.js', tiles: state.tiles, low: state.low, far: state.far, stats: state.stats, errors: state.errors };
		const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
		const a = document.createElement('a');
		a.download = name; a.href = URL.createObjectURL(blob);
		document.body.append(a); a.click(); a.remove();
		return { tiles: Object.keys(state.tiles).length, bytes: blob.size };
	}
	return { tile, start, download, state, get progress() { return state.progress; } };
})();
