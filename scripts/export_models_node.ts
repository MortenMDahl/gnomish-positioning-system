// Runs scripts/browser_export_models.js outside the browser: MapExplorer's own reader (its storage
// worker's calls, in-process) on a World of Warcraft folder. From a MapExplorer checkout
// (https://github.com/coldensjo/ClassicWowMapExplorer, `npm install`, `npm install --no-save tsx`):
//   copy this file to tools/, then
//   npx tsx tools/export_models_node.ts "<WoW folder>" <path to this repo> <out.json> [map ids, comma separated]
// Without map ids it exports the maps GPS3D has terrain for (prototypes/GPS3D/Data/World_<map>.lua).
// Progress goes to stdout every 10 s.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { CascStorage } from '../src/casc/storage';
import { MapExplorer } from '../src/explorer/maps';
import { WorldLoader } from '../src/explorer/world';
import { NodeSource } from './nodeSource';

const [wowDir, repo, out, mapArg] = process.argv.slice(2);
if (!wowDir || !repo || !out) throw new Error('usage: export_models_node.ts <WoW folder> <repo> <out.json> [maps]');
const maps = mapArg
	? mapArg.split(',').map(Number)
	: readdirSync(join(repo, 'prototypes/GPS3D/Data')).map((f) => f.match(/^World_(\d+)\.lua$/)).filter(Boolean).map((m) => Number(m![1]));

const storage = await CascStorage.open(new NodeSource(wowDir), 'wow_classic_beta');
console.log(`storage: ${storage.stats.version} (${storage.stats.buildName}); maps ${maps.join(',')}`);
const world = new WorldLoader(new MapExplorer(storage));
// The worker's calls the export uses, answered in-process. The worker hands results over by
// transfer; here they are the loader's own objects, so the matrices are copied as the worker would.
const api: Record<string, (...a: any[]) => Promise<any>> = {
	listMaps: () => world.listMaps(),
	loadInstance: (id: number) => world.loadInstance(id),
	loadTileObjects: async (wdt: number, x: number, y: number) => (await world.loadTileObjects(wdt, x, y)).map((p) => ({ ...p, matrix: Array.from(p.matrix) })),
	loadModels: (list: any[]) => world.loadModels(list),
};
const quiet = console.warn; console.warn = () => {}; // MapExplorer warns about every model it can't read; the export counts them
(globalThis as any).window = { __gps: { call: (method: string, ...args: any[]) => api[method](...args) } };
new Function(readFileSync(join(repo, 'scripts/browser_export_models.js'), 'utf8'))();
const gm = (globalThis as any).window.gpsModels;
const timer = setInterval(() => console.log(gm.progress), 10000);
console.log(await gm.start({ maps }));
clearInterval(timer);
console.warn = quiet;
const result = gm.result();
result.build = storage.stats.version;
writeFileSync(out, JSON.stringify(result));
console.log(`wrote ${out}: ${JSON.stringify(result.stats)}; ${result.errors.length} errors`);
for (const e of result.errors.slice(0, 20)) console.log('  ' + e);
