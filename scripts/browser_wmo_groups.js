// Which group of a WMO each vertex belongs to, from what MapExplorer's loadModels hands over: the groups'
// vertices are laid out one group after another (in the order of ModelData.areas.groups), but where one
// group ends is not given. It is recovered here: no triangle joins two groups, so a group can only end
// where no triangle spans the boundary, and each group's vertices fill its bounding box
// (areas.groups[i].min/max, the box the WMO file stores: its vertices' bounds, widened a little).
// Loaded by browser_export_detail.js's users (the page, or scripts/export_detail_node.ts):
//   gpsWmoGroups.ranges(model)  -> [start of group 0, start of group 1, ..., vertex count], or null
//   gpsWmoGroups.interiorVertices(model) -> Uint8Array, 1 per vertex of an interior group, or null
// interiorVertices also uses the baked interior light (ModelData.baked, set only on interior groups'
// vertices): a group must not take a lit vertex unless it is interior, and when the boxes leave the
// ranges open, a stretch of vertices no triangle crosses counts as interior if any of its vertices is lit.
window.gpsWmoGroups = (() => {
	// the stored boxes are the vertices' bounds widened by 0.0278 on every side (a few by up to 0.11 on one)
	const EPS = 0.05, FILL = 3; // (a few boxes are up to 2.3 yards wider than their vertices)
	const lit = (m, v) => !!m.baked && (m.baked[v * 4] > 0 || m.baked[v * 4 + 1] > 0 || m.baked[v * 4 + 2] > 0);
	function ranges(m) {
		const groups = (m && m.areas && m.areas.groups) || [];
		const P = m && m.positions, I = m && m.indices;
		if (!P || !I || !groups.length) return null;
		const V = P.length / 3, G = groups.length;
		// where a group may end: no triangle has corners on both sides
		const span = new Int32Array(V + 2);
		for (let t = 0; t + 2 < I.length; t += 3) {
			const a = I[t], b = I[t + 1], c = I[t + 2];
			const lo = Math.min(a, b, c), hi = Math.max(a, b, c);
			if (hi > lo) { span[lo + 1]++; span[hi + 1]--; }
		}
		const cut = new Uint8Array(V + 1);
		for (let b = 0, run = 0; b <= V; b++) { run += span[b]; cut[b] = run === 0 ? 1 : 0; }
		const inBox = (k, v) => {
			const g = groups[k];
			for (let a = 0; a < 3; a++) {
				const x = P[v * 3 + a];
				if (x < g.min[a] - EPS || x > g.max[a] + EPS) return false;
			}
			return true;
		};
		const fills = (k, lo, hi) => { // the vertices' bounds are the box
			const g = groups[k];
			for (let a = 0; a < 3; a++) if (lo[a] - g.min[a] > FILL || g.max[a] - hi[a] > FILL) return false;
			return true;
		};
		const failed = new Set();
		const starts = new Array(G + 1);
		// depth-first: group k starts at vertex s; try every end where its vertices fill its box
		const place = (k, s) => {
			if (k === G) return s === V;
			const key = k * (V + 1) + s;
			if (failed.has(key)) return false;
			const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
			for (let e = s + 1; e <= V; e++) {
				const v = e - 1;
				if (!inBox(k, v) || (!groups[k].interior && lit(m, v))) break;
				for (let a = 0; a < 3; a++) { const x = P[v * 3 + a]; if (x < lo[a]) lo[a] = x; if (x > hi[a]) hi[a] = x; }
				if (cut[e] && fills(k, lo, hi)) {
					starts[k + 1] = e;
					if (place(k + 1, e)) return true;
				}
			}
			failed.add(key);
			return false;
		};
		starts[0] = 0;
		return place(0, 0) ? starts : null;
	}
	function interiorVertices(m) {
		if (!m || !m.positions || !m.indices) return null;
		const V = m.positions.length / 3, out = new Uint8Array(V);
		const r = ranges(m);
		if (r) {
			m.areas.groups.forEach((g, k) => { if (g.interior) out.fill(1, r[k], r[k + 1]); });
			return out;
		}
		if (!m.baked) return null;
		const I = m.indices, span = new Int32Array(V + 2);
		for (let t = 0; t + 2 < I.length; t += 3) {
			const lo = Math.min(I[t], I[t + 1], I[t + 2]), hi = Math.max(I[t], I[t + 1], I[t + 2]);
			if (hi > lo) { span[lo + 1]++; span[hi + 1]--; }
		}
		for (let b = 1, run = 0, start = 0; b <= V; b++) {
			run += span[b];
			if (run !== 0) continue;
			for (let v = start; v < b; v++) if (lit(m, v)) { out.fill(1, start, b); break; }
			start = b;
		}
		return out;
	}
	return { ranges, interiorVertices };
})();
