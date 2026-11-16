/// <reference lib="webworker" />
// Runs the EVA Pathfinder Python engine (same modules as the FastAPI server) in the browser via Pyodide.
// The interpreter and engine code load once; each planning area's data loads on first use.
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/";

type Req = { id: number; endpoint: string; body: string; base: string; area: string };
type PyBridge = {
  call: (endpoint: string, body: string, area: string) => string;
  init: (dir: string, ver: string, stops: number, radius: number, area: string) => string;
};
type Py = { FS: { mkdirTree: (p: string) => void; writeFile: (p: string, d: string | Uint8Array) => void }; runPython: (s: string) => void; pyimport: (m: string) => unknown };
let engine: Promise<{ py: Py; bridge: PyBridge; eng: { code_version: string; max_stops?: number; max_block_radius_m?: number } }> | null = null;
const areas = new Map<string, Promise<void>>();

async function boot(base: string) {
  const mod = await import(/* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`);
  const py = (await mod.loadPyodide({ indexURL: PYODIDE_URL })) as Py & { loadPackage: (p: string[]) => Promise<void> };
  await py.loadPackage(["numpy", "pydantic"]);
  const idx: { files: string[] } = await (await fetch(`${base}static/py/index.json`)).json();
  for (const f of idx.files) {
    const text = await (await fetch(`${base}static/py/${f}`)).text();
    const path = `/home/pyodide/${f}`;
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
    py.FS.writeFile(path, text);
  }
  const eng = await (await fetch(`${base}static/engine.json`)).json();
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  return { py, bridge: py.pyimport("app.static_bridge") as PyBridge, eng };
}

async function loadArea(base: string, area: string) {
  const { py, bridge, eng } = await engine!;
  const dir = `/data/${area}`;
  py.FS.mkdirTree(dir);
  for (const f of ["dem_crop.npy", "geology_units.npy", "geology_units.json", "manifest.json", "mission_defaults.json", "science_sites.json"]) {
    const res = await fetch(`${base}static/areas/${area}/data/${f}`);
    if (!res.ok) continue;
    py.FS.writeFile(`${dir}/${f}`, new Uint8Array(await res.arrayBuffer()));
  }
  bridge.init(dir, String(eng.code_version), eng.max_stops ?? 3, eng.max_block_radius_m ?? 1000, area);
}

self.onmessage = async (e: MessageEvent<Req>) => {
  const { id, endpoint, body, base, area } = e.data;
  try {
    engine ??= boot(base);
    const { bridge } = await engine;
    if (!areas.has(area)) areas.set(area, loadArea(base, area));
    await areas.get(area);
    (self as unknown as Worker).postMessage({ id, result: bridge.call(endpoint, body, area) });
  } catch (err) {
    engine = null;
    areas.clear();
    (self as unknown as Worker).postMessage({ id, result: JSON.stringify({ ok: false, status: 0, error: { code: "ENGINE_LOAD_FAILED", message: `Could not start the in-browser engine: ${String(err)}` } }) });
  }
};
