// Checks scripts/browser_wmo_groups.js (which WMO group each vertex belongs to) on made-up models shaped like
// MapExplorer's ModelData: groups laid out one after another, boxes widened as the WMO files store them,
// baked interior light on interior vertices only. Run: node tools/sandbox/test_wmo_groups.js
// (On the game's own caves and mines, through scripts/export_detail_node.ts's reader: 148 of 151 WMOs with
// every vertex right; 34 vertices of 3,966,814 wrong, all exterior ones taken as interior, none the other way.)
const fs = require('fs'), path = require('path');
global.window = {};
new Function(fs.readFileSync(path.join(__dirname, '../../scripts/browser_wmo_groups.js'), 'utf8'))();
const W = window.gpsWmoGroups;
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : ' ' + detail)); };

// a group: a grid of n x n vertices over [x0, x0 + size] x [y0, y0 + size] at height z, two triangles per cell
function group(x0, y0, z, size, n, interior, lit = interior, pad = 0.0278, extra = [0, 0, 0, 0, 0, 0]) {
	const P = [], T = [];
	for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) P.push(x0 + size * i / (n - 1), y0 + size * j / (n - 1), z + (i + j) % 2);
	for (let j = 0; j + 1 < n; j++) for (let i = 0; i + 1 < n; i++) { const a = j * n + i; T.push(a, a + 1, a + n, a + 1, a + n + 1, a + n); }
	return { P, T, interior, lit, box: { min: [x0 - pad - extra[0], y0 - pad - extra[1], z - pad - extra[2]], max: [x0 + size + pad + extra[3], y0 + size + pad + extra[4], z + 1 + pad + extra[5]] } };
}
function model(groups) {
	const positions = [], indices = [], baked = [], areas = [];
	let base = 0;
	const truth = [];
	for (const g of groups) {
		const n = g.P.length / 3;
		positions.push(...g.P);
		for (const t of g.T) indices.push(t + base);
		for (let v = 0; v < n; v++) baked.push(...(g.lit ? [0.3, 0.25, 0.2, 1] : [0, 0, 0, 0]));
		areas.push({ id: areas.length, interior: g.interior, min: g.box.min, max: g.box.max });
		for (let v = 0; v < n; v++) truth.push(g.interior ? 1 : 0);
		base += n;
	}
	return { m: { positions: new Float32Array(positions), indices: new Uint32Array(indices), baked: new Float32Array(baked), areas: { groups: areas } }, truth };
}
const same = (a, b) => a && a.length === b.length && Array.from(a).every((x, i) => x === b[i]);

// 1. an exterior shell and two tunnels, boxes widened by 0.0278 as stored
let { m, truth } = model([group(0, 0, 0, 40, 9, false), group(5, 5, -10, 10, 5, true), group(20, 5, -12, 10, 5, true)]);
check('ranges: exterior shell then two tunnels', same(W.ranges(m), [0, 81, 106, 131]), JSON.stringify(W.ranges(m)));
check('interior vertices: the tunnels and nothing else', same(W.interiorVertices(m), truth));

// 2. a box stored up to 2.3 yd wider than its vertices on some sides (seen in the game files)
({ m, truth } = model([group(0, 0, 0, 20, 6, true, true, 0.0278, [0, 0, 2.3, 0.4, 0, 0]), group(30, 0, 0, 20, 6, false)]));
check('a box much wider than its vertices: ranges still found', same(W.ranges(m), [0, 36, 72]), JSON.stringify(W.ranges(m)));

// 3. a tunnel inside the shell's box, the tunnel first: its unlit vertices would fit the shell's box too;
//    the boxes and the light keep them apart
({ m, truth } = model([group(5, 5, -5, 10, 4, true), group(0, 0, -10, 40, 6, false), group(10, 10, -8, 5, 3, true)]));
check('tunnel, shell around it, tunnel: every vertex right', same(W.interiorVertices(m), truth));

// 4. boxes that leave the ranges open (one stored box far too big): the light decides, by stretches no
//    triangle crosses
({ m, truth } = model([group(0, 0, 0, 20, 5, false, false, 0.0278, [0, 0, 0, 50, 50, 50]), group(5, 5, -6, 5, 4, true)]));
m.areas.groups[0].min = [-100, -100, -100];
check('ranges left open: null', W.ranges(m) === null, JSON.stringify(W.ranges(m)));
check('ranges left open: interior vertices from the light', same(W.interiorVertices(m), truth));

// 5. an interior group with no light at all and boxes that do not settle it: never taken as exterior? It is
//    (nothing marks it): the export then draws it as before, which is the safe side
({ m, truth } = model([group(0, 0, 0, 20, 5, false, false, 0.0278, [0, 0, 0, 50, 50, 50]), group(5, 5, -6, 5, 4, true, false)]));
m.areas.groups[0].min = [-100, -100, -100];
const iv = W.interiorVertices(m);
check('unlit interior with open ranges: counted as exterior (drawn as before), no exterior vertex taken as interior', iv && iv.every((x) => x === 0));

// 6. no groups or no indices: null, nothing throws
check('no groups: null', W.ranges({ positions: new Float32Array(3), indices: new Uint32Array(0), areas: { groups: [] } }) === null && W.interiorVertices(null) === null);

const n = results.filter(Boolean).length;
console.log(`${n} of ${results.length} checks passed`);
process.exit(n === results.length ? 0 : 1);
