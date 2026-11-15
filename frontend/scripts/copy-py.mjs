// Copy the framework-free Python engine into public/static/py for the in-browser (Pyodide) build.
// Same source files the FastAPI server runs; server-only modules (FastAPI app, rasterio repo, config) are excluded.
import { cpSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const src = join(root, "backend");
const out = join(root, "frontend", "public", "static", "py");
const files = [
  "app/__init__.py", "app/static_bridge.py",
  "app/api/__init__.py", "app/api/handlers.py", "app/api/schemas.py", "app/api/translate_v08.py",
  "app/application/__init__.py", "app/application/services.py", "app/application/contracts.py",
  "app/domain/__init__.py", "app/domain/terrain.py", "app/domain/navigation.py", "app/domain/mission.py",
  "app/domain/contingency.py", "app/domain/evidence.py", "app/domain/values.py",
];
rmSync(out, { recursive: true, force: true });
for (const f of files) {
  mkdirSync(dirname(join(out, f)), { recursive: true });
  cpSync(join(src, f), join(out, f));
}
writeFileSync(join(out, "index.json"), JSON.stringify({ files }));
console.log(`copied ${files.length} Python engine files -> ${out}`);
