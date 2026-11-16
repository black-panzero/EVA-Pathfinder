#!/usr/bin/env python3
"""Export the prepared study area for the static (GitHub Pages) build.

Writes frontend/public/static/:
  data/   dem_crop.npy, geology_units.npy/json, manifest.json   (inputs for the in-browser engine)
  api/    study-area.json, datasets.json, observations.json, science-sites.json, missions-default.json
          (the server's GET responses: data and configuration only, no computed mission results)
  layers/ map overlay PNGs     photos/ rover photos
The Python engine source is copied separately at build time by frontend/scripts/copy-py.mjs.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.main import _repo_for, app, settings  # noqa: E402
from app.infrastructure.repositories import LAYER_FILES  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

OUT = ROOT / "frontend" / "public" / "static"


def export_area(c: TestClient, area_id: str) -> None:
    """One planning area -> static/areas/<id>/{data,api,layers,photos}. URLs are relative to the site root."""
    r = _repo_for(area_id)
    base = OUT / "areas" / area_id
    for sub in ("data", "api", "layers", "photos"):
        (base / sub).mkdir(parents=True)
    np.save(base / "data" / "dem_crop.npy", r.grid.elevation_m.astype("float32"))
    shutil.copy2(ROOT / "config" / "mission_defaults.json", base / "data" / "mission_defaults.json")
    for name in ("geology_units.npy", "geology_units.json", "manifest.json", "science_sites.json"):
        if (r.dir / name).exists():
            shutil.copy2(r.dir / name, base / "data" / name)
    for lid, (fname, _t, _l) in LAYER_FILES.items():
        if r.layer_path(lid):
            shutil.copy2(r.dir / fname, base / "layers" / f"{lid}.png")
    for ph in r.photos:
        shutil.copy2(r.dir / ph["file"], base / "photos" / Path(ph["file"]).name)
    q = f"?area={area_id}"
    rel = f"static/areas/{area_id}"
    sa = c.get("/api/v1/study-area" + q).json()
    if sa.get("context"):  # the whole-mosaic context image is identical for every area: export once, shared
        shared = OUT / "layers" / sa["context"]["file"]
        if not shared.exists():
            shutil.copy2(r.dir / sa["context"]["file"], shared)
        sa["context"]["image_url"] = f"static/layers/{sa['context']['file']}"
    for layer in sa["layers"]:
        layer["image_url"] = f"{rel}/layers/{layer['layer_id']}.png"
    obs = c.get("/api/v1/observations" + q).json()
    for ph in obs["photos"]:
        ph["image_url"] = f"{rel}/photos/{Path(ph['file']).name}"
    files = {
        "study-area.json": sa,
        "datasets.json": c.get("/api/v1/datasets" + q).json(),
        "observations.json": obs,
        "science-sites.json": c.get("/api/v1/science-sites" + q).json(),
        "missions-default.json": c.get("/api/v1/missions/default" + q).json(),
    }
    for name, body in files.items():
        (base / "api" / name).write_text(json.dumps(body))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "layers").mkdir(parents=True)
    c = TestClient(app)
    areas = c.get("/api/v1/areas").json()
    ready = [a for a in areas["areas"] if a["data_ready"]]
    if not ready:
        raise SystemExit("no prepared planning area; run scripts/prepare_data.py first")
    for a in ready:
        export_area(c, a["study_area_id"])
    (OUT / "areas.json").write_text(json.dumps({"areas": ready}))
    limits = settings.mission_defaults.get("limits", {})
    (OUT / "engine.json").write_text(json.dumps({"code_version": (ROOT / "VERSION").read_text().strip(), **limits}))
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"static export -> {OUT.relative_to(ROOT)} ({total / 1e6:.2f} MB, areas: {', '.join(a['study_area_id'] for a in ready)})")


if __name__ == "__main__":
    main()
