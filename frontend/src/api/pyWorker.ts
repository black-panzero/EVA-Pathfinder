/// <reference lib="webworker" />
// Runs the EVA Pathfinder Python engine (same modules as the FastAPI server) in the browser via Pyodide.
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/";

type Req = { id: number; endpoint: string; body: string; base: string };
type PyBridge = { call: (endpoint: string, body: string) => string; init: (dir: string, ver: string, stops: number, radius: number) => string };
let bridge: Promise<PyBridge> | null = null;

async function boot(base: string): Promise<PyBridge> {
  const mod = await import(/* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`);
  const py = await mod.loadPyodide({ indexURL: PYODIDE_URL });
  await py.loadPackage(["numpy", "pydantic"]);
  const idx: { files: string[] } = await (await fetch(`${base}static/py/index.json`)).json();
  for (const f of idx.files) {
    const text = await (await fetch(`${base}static/py/${f}`)).text();
    const path = `/home/pyodide/${f}`;
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
    py.FS.writeFile(path, text);
  }
  py.FS.mkdirTree("/data");
  for (const f of ["dem_crop.npy", "geology_units.npy", "geology_units.json", "manifest.json", "mission_defaults.json", "science_sites.json"]) {
    const res = await fetch(`${base}static/data/${f}`);
    if (!res.ok) continue;
    py.FS.writeFile(`/data/${f}`, new Uint8Array(await res.arrayBuffer()));
  }
  const eng = await (await fetch(`${base}static/data/engine.json`)).json();
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  const b = py.pyimport("app.static_bridge") as PyBridge;
  b.init("/data", String(eng.code_version), eng.max_stops ?? 3, eng.max_block_radius_m ?? 1000);
  return b;
}

self.onmessage = async (e: MessageEvent<Req>) => {
  const { id, endpoint, body, base } = e.data;
  try {
    bridge ??= boot(base);
    const b = await bridge;
    (self as unknown as Worker).postMessage({ id, result: b.call(endpoint, body) });
  } catch (err) {
    bridge = null;
    (self as unknown as Worker).postMessage({ id, result: JSON.stringify({ ok: false, status: 0, error: { code: "ENGINE_LOAD_FAILED", message: `Could not start the in-browser engine: ${String(err)}` } }) });
  }
};
