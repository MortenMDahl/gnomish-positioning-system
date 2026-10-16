// GPS browser export.
//
// Run in the MapExplorer page (https://coldensjo.github.io/ClassicWowMapExplorer/) after it has
// loaded your World of Warcraft folder with the Forever game version, by pasting this file into
// the browser's developer console. It hooks the page's storage worker, reads every map that has
// terrain tiles, and downloads gps-export.zip with:
//   export.json             every map's tiles and their minimap FileDataIDs, plus the overview atlases
//   Overview/<map>_<ax>_<ay>.jpg   zoomed-out overview images, 64 px per tile, 16x16 tiles per atlas
//   northshire_tin.json     (optional) the Northshire test tile as a simplified 1-yard height mesh
// Then run scripts/build_maptiles.py on the zip to write the addon's data files.

(function hookWorker() {
	window.__gps = window.__gps || { worker: null };
	if (window.__gps.patched) return;
	const orig = Worker.prototype.postMessage;
	Worker.prototype.postMessage = function (msg, ...rest) {
		if (!window.__gps.worker && msg && msg.method) {
			window.__gps.worker = this;
			const pending = new Map();
			let next = 1e9;
			this.addEventListener('message', (e) => {
				const m = e.data;
				const p = m && pending.get(m.id);
				if (!p) return;
				pending.delete(m.id);
				if ('error' in m) p.reject(new Error(m.error)); else p.resolve(m.result);
			});
			window.__gps.call = (method, ...args) => new Promise((resolve, reject) => {
				const id = next++;
				pending.set(id, { resolve, reject });
				orig.call(this, { id, method, args });
			});
		}
		return orig.call(this, msg, ...rest);
	};
	window.__gps.patched = true;
	// The hook catches the worker on the page's next request: move the camera (or press O) once.
})();

window.gpsExport = async function gpsExport({ overviewPx = 64, atlasTiles = 16, jpegQuality = 0.9, source = 'wow_classic_beta', tin = null, onProgress = () => {} } = {}) {
	const call = window.__gps && window.__gps.call;
	if (!call) throw new Error('The storage worker is not hooked yet: move the camera once, then run gpsExport() again');
	const pow2 = (n) => { let p = 1; while (p < n) p *= 2; return p; };
	const files = {};
	const maps = [];
	const listing = await call('listMaps');
	for (const m of listing) {
		const inst = await call('loadInstance', m.id).catch(() => null);
		if (!inst || !inst.wdt) continue;
		const summary = await call('loadMap', inst.wdt).catch(() => null);
		if (!summary) continue;
		const tiles = summary.tiles.filter((t) => t.files.minimap);
		if (!tiles.length) continue;
		const xs = tiles.map((t) => t.x), ys = tiles.map((t) => t.y);
		const minX = Math.min(...xs), minY = Math.min(...ys), maxX = Math.max(...xs), maxY = Math.max(...ys);
		const entry = { id: m.id, name: m.name, category: m.category, wdt: inst.wdt, minX, minY, maxX, maxY,
			tiles: tiles.map((t) => [t.x, t.y, t.files.minimap]), atlases: [] };
		for (let ay = 0; ay * atlasTiles <= maxY - minY; ay++) {
			for (let ax = 0; ax * atlasTiles <= maxX - minX; ax++) {
				const x0 = minX + ax * atlasTiles, y0 = minY + ay * atlasTiles;
				const inside = tiles.filter((t) => t.x >= x0 && t.x < x0 + atlasTiles && t.y >= y0 && t.y < y0 + atlasTiles);
				if (!inside.length) continue;
				const cols = Math.min(atlasTiles, maxX - x0 + 1), rows = Math.min(atlasTiles, maxY - y0 + 1);
				const canvas = document.createElement('canvas');
				canvas.width = pow2(cols * overviewPx);
				canvas.height = pow2(rows * overviewPx);
				const g = canvas.getContext('2d');
				g.fillStyle = '#0f2434';
				g.fillRect(0, 0, canvas.width, canvas.height);
				for (let i = 0; i < inside.length; i += 32) {
					const batch = inside.slice(i, i + 32).map((t) => [t.x, t.y]);
					const thumbs = await call('minimapThumbnails', inst.wdt, batch, overviewPx);
					for (const { x, y, image } of thumbs) {
						if (!image) continue;
						g.putImageData(new ImageData(new Uint8ClampedArray(image.rgba), image.width, image.height), (x - x0) * overviewPx, (y - y0) * overviewPx);
					}
				}
				const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', jpegQuality));
				const file = `${m.id}_${ax}_${ay}`;
				files[`Overview/${file}.jpg`] = new Uint8Array(await blob.arrayBuffer());
				entry.atlases.push({ file, x0, y0, cols, rows, width: canvas.width, height: canvas.height });
			}
		}
		maps.push(entry);
		onProgress(`${m.name}: ${tiles.length} tiles, ${entry.atlases.length} atlases`);
	}
	const enc = new TextEncoder();
	files['export.json'] = enc.encode(JSON.stringify({ exportedAt: new Date().toISOString(), source, overviewPx, atlasTiles, maps }));
	if (tin) files['northshire_tin.json'] = enc.encode(JSON.stringify(tin));
	const { zipSync } = await import('https://cdn.jsdelivr.net/npm/fflate@0.8.2/+esm');
	const zip = zipSync(files, { level: 0 });
	const url = URL.createObjectURL(new Blob([zip], { type: 'application/zip' }));
	const a = document.createElement('a');
	a.href = url;
	a.download = 'gps-export.zip';
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 60000);
	return { maps: maps.length, tiles: maps.reduce((n, m) => n + m.tiles.length, 0), atlases: maps.reduce((n, m) => n + m.atlases.length, 0), zipBytes: zip.length };
};
