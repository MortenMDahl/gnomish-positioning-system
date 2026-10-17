// Runs scripts/browser_export_detail.js outside the browser: MapExplorer's own reader (its storage
// worker's calls, in-process) on a World of Warcraft folder, with delatin 0.2.0 from npm (the version the
// browser script imports). From a MapExplorer checkout
// (https://github.com/coldensjo/ClassicWowMapExplorer, `npm install`, `npm install --no-save tsx delatin@0.2.0`):
//   copy this file to tools/ (it uses MapExplorer's own tools/nodeSource.ts, as export_models_node.ts does), then
//   npx tsx tools/export_detail_node.ts "<WoW folder>" <path to this repo> <out.json> [map ids, comma separated]
//     [--only <keys.json>] [--budget <seconds>] [--resume]
// Map ids: as in data/detail_0.json (0) and data/detail_rest.json (the others). --only: a JSON list of
// tile keys ("map_x_y") to export, the rest are not visited. --budget: stop starting tiles after that
// many seconds and write what is done (out.json lists the tiles visited and those remaining);
// --resume: carry on from out.json, skipping the tiles it has visited. Tiles go 8 at a time through
// gpsDetail.start, so the result is the same as one run in the browser.
// Then: python scripts/build_detail.py <out.json> ... (or merge it into data/detail_*.json first:
// scripts/merge_detail.py).
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import Delatin from 'delatin';
import { CascStorage } from '../src/casc/storage';
import { MapExplorer } from '../src/explorer/maps';
import { WorldLoader } from '../src/explorer/world';
import { NodeSource } from './nodeSource';

const args = process.argv.slice(2);
const flag = (name: string, takes: boolean) => {
	const i = args.indexOf(name);
	if (i < 0) return null;
	const v = takes ? args[i + 1] : 'yes';
	args.splice(i, takes ? 2 : 1);
	return v;
};
const onlyFile = flag('--only', true), budget = Number(flag('--budget', true) ?? Infinity), resume = !!flag('--resume', false);
const only: Set<string> | null = onlyFile ? new Set(JSON.parse(readFileSync(onlyFile, 'utf8'))) : null;
const [wowDir, repo, out, mapArg] = args;
if (!wowDir || !repo || !out) throw new Error('usage: export_detail_node.ts <WoW folder> <repo> <out.json> [maps] [--only keys.json] [--budget s] [--resume]');
const maps = mapArg ? mapArg.split(',').map(Number) : null;
const T0 = Date.now();

const storage = await CascStorage.open(new NodeSource(wowDir), 'wow_classic_beta');
const world = new WorldLoader(new MapExplorer(storage));
// The worker's calls the export uses, answered in-process (the worker would copy what it hands over;
// the export only reads it).
const api: Record<string, (...a: any[]) => Promise<any>> = {
	listMaps: () => world.listMaps(),
	loadInstance: (id: number) => world.loadInstance(id),
	loadTileObjects: async (wdt: number, x: number, y: number) => (await world.loadTileObjects(wdt, x, y)).map((p) => ({ ...p, matrix: Array.from(p.matrix) })),
	loadModels: (list: any[]) => world.loadModels(list),
	loadNearTile: (wdt: number, x: number, y: number, compressed?: boolean) => world.loadNearTile(wdt, x, y, !!compressed),
	loadTextures: (fdids: number[], compressed?: boolean) => world.loadTextures(fdids, !!compressed),
};
const quiet = console.warn; console.warn = () => {}; // MapExplorer warns about every model it can't read
(globalThis as any).window = { __gps: { call: (method: string, ...a: any[]) => api[method](...a), Delatin } };
for (const f of ['scripts/browser_underground.js', 'scripts/browser_wmo_groups.js', 'scripts/browser_export_detail.js']) new Function(readFileSync(join(repo, f), 'utf8'))();
const gd = (globalThis as any).window.gpsDetail;

const result = resume && existsSync(out) ? JSON.parse(readFileSync(out, 'utf8'))
	: { exportedAt: new Date().toISOString(), format: 'D2, see scripts/browser_export_detail.js', tiles: {}, low: {}, far: {}, stats: [], errors: [], underground: {}, undergroundWhole: {}, visited: [] };
const visited = new Set<string>(result.visited);
const todo: [number, string[]][] = [];
for (const m of await world.listMaps()) {
	if (maps && !maps.includes(m.id)) continue;
	const inst = await world.loadInstance(m.id).catch(() => null);
	if (!inst || !inst.wdt) continue;
	const keys = (inst.farTiles || []).filter((t: any) => t.hasAdt).map((t: any) => `${m.id}_${t.x}_${t.y}`).filter((k: string) => (!only || only.has(k)) && !visited.has(k));
	if (keys.length) todo.push([m.id, keys]);
}
let left = todo.reduce((n, [, k]) => n + k.length, 0);
console.log(`storage: ${storage.stats.version} (${storage.stats.buildName}); maps ${maps ? maps.join(',') : 'all'}; ${left} tiles to do, ${visited.size} done before`);
let lastLog = Date.now();
outer: for (const [map, keys] of todo) {
	for (let i = 0; i < keys.length; i += 8) {
		if ((Date.now() - T0) / 1000 > budget) break outer;
		const chunk = keys.slice(i, i + 8);
		await gd.start({ maps: [map], only: chunk });
		const r = gd.result();
		Object.assign(result.tiles, r.tiles); Object.assign(result.low, r.low); Object.assign(result.far, r.far); Object.assign(result.underground, r.underground); Object.assign(result.undergroundWhole, r.undergroundWhole);
		result.stats.push(...r.stats); result.errors.push(...r.errors);
		for (const k of chunk) visited.add(k);
		left -= chunk.length;
		if (Date.now() - lastLog > 10000) { lastLog = Date.now(); console.log(`${visited.size} tiles done, ${left} left, ${Object.keys(result.tiles).length} with buildings, ${Math.round((Date.now() - T0) / 1000)} s`); }
	}
}
console.warn = quiet;
result.visited = [...visited];
result.remaining = left;
result.build = storage.stats.version;
writeFileSync(out, JSON.stringify(result));
const count = (o: Record<string, number[]>) => new Set(Object.entries(o).flatMap(([key, uids]) => uids.map((u) => `${key.split('_')[0]}:${u}`))).size;
console.log(`wrote ${out}: ${visited.size} tiles visited, ${left} remaining; ${Object.keys(result.tiles).length} with buildings; caves and mines: ${count(result.underground)} with their exterior groups only, ${count(result.undergroundWhole)} left out whole; ${result.errors.length} errors`);
for (const e of result.errors.slice(0, 20)) console.log('  ' + e);
