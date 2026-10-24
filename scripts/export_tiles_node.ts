// GPS3D shells (S1e, 2026-10-24): every WMO triangle of the given maps, per ADT tile (a triangle goes to the tile its
// centroid is in), for building the city shells offline. Per tile out/<map>_<x>_<y>.bin: chunks, one per WMO placement:
// int32 [uid, fdid, nv, nt], float32 positions nv*3 (GPS world: x east, y north = -z, h up), float32 uv nv*2,
// uint32 indices nt*3 (into this chunk), uint32 texture FileDataID per triangle. Opaque and alpha-keyed materials only.
// Textures: out/tex/<fdid>.rgba (one level <= 256 px, RGBA) and out/tex/index.json {fdid: [w, h]}.
// Usage: copy to tools/ in a MapExplorer checkout (as export_models_node.ts), then
//   npx tsx tools/export_tiles_node.ts "<WoW folder>" <out dir> <maps, e.g. 0,1> [--tiles 1_40_28,...] [--budget s]
// Both continents: about a minute, 1.2 GB (799 tiles, 3,783 placements, 2,816 textures; 2026-10-24). --budget stops
// starting tiles after that many seconds (done.json keeps what is done; a second run carries on).
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { CascStorage } from '../src/casc/storage';
import { MapExplorer } from '../src/explorer/maps';
import { WorldLoader } from '../src/explorer/world';
import { blpTexture } from '../src/formats/blp';
import { NodeSource } from './nodeSource';

const args = process.argv.slice(2);
const flag = (n: string) => { const i = args.indexOf(n); if (i < 0) return null; const v = args[i + 1]; args.splice(i, 2); return v; };
const tilesArg = flag('--tiles'), budget = Number(flag('--budget') ?? Infinity);
const [wowDir, out, mapArg] = args;
const maps = mapArg.split(',').map(Number);
const T0 = Date.now();
mkdirSync(join(out, 'tex'), { recursive: true });
const donePath = join(out, 'done.json');
const done: { placements: string[]; tiles: string[]; tex: string[] } = existsSync(donePath) ? JSON.parse(readFileSync(donePath, 'utf8')) : { placements: [], tiles: [], tex: [] };
const doneP = new Set(done.placements), doneT = new Set(done.tiles);
const storage = await CascStorage.open(new NodeSource(wowDir), 'wow_classic_beta');
const world = new WorldLoader(new MapExplorer(storage));
console.warn = () => {};
const TILE = 1600 / 3;
const texSeen = new Set<number>(done.tex.map(Number));
const save = () => { done.placements = [...doneP]; done.tiles = [...doneT]; done.tex = [...texSeen].map(String); writeFileSync(donePath, JSON.stringify(done)); };
let stop = false;
for (const map of maps) {
	const inst = await world.loadInstance(map);
	if (!inst || !inst.wdt) continue;
	let tiles = (inst.farTiles || []).filter((t: any) => t.hasAdt).map((t: any) => [t.x, t.y] as [number, number]);
	if (tilesArg) { const want = new Set(tilesArg.split(',')); tiles = tiles.filter(([x, y]) => want.has(`${map}_${x}_${y}`)); }
	for (const [tx, ty] of tiles) {
		const tk = `${map}_${tx}_${ty}`;
		if (doneT.has(tk)) continue;
		if ((Date.now() - T0) / 1000 > budget) { stop = true; break; }
		const objs = await world.loadTileObjects(inst.wdt, tx, ty);
		for (const o of objs) {
			if (o.kind !== 'wmo') continue;
			const pk = `${map}_${o.uid}`;
			if (doneP.has(pk)) continue;
			doneP.add(pk);
			const [m] = await world.loadModels([{ fdid: o.fdid, kind: 'wmo' }]).catch(() => [null]);
			if (!m || !m.positions || !m.indices) continue;
			const M = o.matrix, P = m.positions, n = P.length / 3;
			const W = new Float32Array(n * 3);
			for (let k = 0; k < n; k++) {
				const x = P[k * 3], y = P[k * 3 + 1], z = P[k * 3 + 2];
				W[k * 3] = M[0] * x + M[4] * y + M[8] * z + M[12];
				W[k * 3 + 1] = -(M[2] * x + M[6] * y + M[10] * z + M[14]);
				W[k * 3 + 2] = M[1] * x + M[5] * y + M[9] * z + M[13];
			}
			// triangles by tile (their centroid's)
			const per = new Map<string, number[]>();
			const texOf: number[] = [];
			for (const b of m.batches) {
				if ((b.material?.blend ?? 0) > 1) continue;
				const tex = b.material?.texture ?? 0;
				for (let t = b.start; t < b.start + b.count; t += 3) {
					const a = m.indices[t], bb = m.indices[t + 1], c = m.indices[t + 2];
					const cx = (W[a * 3] + W[bb * 3] + W[c * 3]) / 3, cy = (W[a * 3 + 1] + W[bb * 3 + 1] + W[c * 3 + 1]) / 3;
					const key = `${map}_${Math.floor(cx / TILE)}_${Math.floor(-cy / TILE)}`;
					let l = per.get(key); if (!l) { l = []; per.set(key, l); }
					l.push(a, bb, c, tex);
					if (tex) texSeen.add(tex);
				}
			}
			for (const [key, l] of per) {
				const nt = l.length / 4, remap = new Map<number, number>(), vs: number[] = [];
				const idx = new Uint32Array(nt * 3), tx2 = new Uint32Array(nt);
				for (let q = 0; q < nt; q++) {
					for (let k = 0; k < 3; k++) { const v = l[q * 4 + k]; let r = remap.get(v); if (r === undefined) { r = vs.length; remap.set(v, r); vs.push(v); } idx[q * 3 + k] = r; }
					tx2[q] = l[q * 4 + 3];
				}
				const nv = vs.length, pos = new Float32Array(nv * 3), uv = new Float32Array(nv * 2);
				vs.forEach((v, i) => { pos.set(W.subarray(v * 3, v * 3 + 3), i * 3); uv[i * 2] = m.uvs[v * 2] ?? 0; uv[i * 2 + 1] = m.uvs[v * 2 + 1] ?? 0; });
				const head = new Int32Array([o.uid, o.fdid, nv, nt]);
				appendFileSync(join(out, key + '.bin'), Buffer.concat([Buffer.from(head.buffer), Buffer.from(pos.buffer), Buffer.from(uv.buffer), Buffer.from(idx.buffer), Buffer.from(tx2.buffer)]));
			}
		}
		doneT.add(tk);
		if (doneT.size % 10 === 0) { save(); console.log(`${doneT.size} tiles, ${doneP.size} placements, ${Math.round((Date.now() - T0) / 1000)} s`); }
	}
	if (stop) break;
}
// textures
const idxPath = join(out, 'tex', 'index.json');
const tindex: Record<string, [number, number]> = existsSync(idxPath) ? JSON.parse(readFileSync(idxPath, 'utf8')) : {};
for (const f of texSeen) {
	if (tindex[f] || (Date.now() - T0) / 1000 > budget + 60) continue;
	try {
		const t = blpTexture(await storage.readFile(f), 256, false);
		const mip = t && t.mips[0];
		if (mip && t.format === 'rgba') { writeFileSync(join(out, 'tex', f + '.rgba'), mip.data); tindex[f] = [mip.width, mip.height]; }
		else tindex[f] = [0, 0];
	} catch { tindex[f] = [0, 0]; }
}
writeFileSync(idxPath, JSON.stringify(tindex));
save();
console.log(`DONE ${stop ? 'partial' : 'complete'}: ${doneT.size} tiles, ${doneP.size} placements, ${Object.keys(tindex).length} textures, ${Math.round((Date.now() - T0) / 1000)} s`);
