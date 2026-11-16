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

from app.api.main import app, repo  # noqa: E402
from app.infrastructure.repositories import LAYER_FILES  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

OUT = ROOT / "frontend" / "public" / "static"


def main() -> None:
    r = repo()
    if OUT.exists():
        shutil.rmtree(OUT)
    for sub in ("data", "api", "layers", "photos"):
        (OUT / sub).mkdir(parents=True)
    np.save(OUT / "data" / "dem_crop.npy", r.grid.elevation_m.astype("float32"))
    shutil.copy2(ROOT / "config" / "mission_defaults.json", OUT / "data" / "mission_defaults.json")
    for name in ("geology_units.npy", "geology_units.json", "manifest.json", "science_sites.json"):
        src = r.dir / name
        if src.exists():
            shutil.copy2(src, OUT / "data" / name)
    for lid, (fname, _t, _l) in LAYER_FILES.items():
        if r.layer_path(lid):
            shutil.copy2(r.dir / fname, OUT / "layers" / f"{lid}.png")
    for ph in r.photos:
        shutil.copy2(r.dir / ph["file"], OUT / "photos" / Path(ph["file"]).name)

    c = TestClient(app)
    sa = c.get("/api/v1/study-area").json()
    if sa.get("context"):
        shutil.copy2(r.dir / sa["context"]["file"], OUT / "layers" / sa["context"]["file"])
        sa["context"]["image_url"] = f"static/layers/{sa['context']['file']}"
    for layer in sa["layers"]:
        layer["image_url"] = f"static/layers/{layer['layer_id']}.png"
    obs = c.get("/api/v1/observations").json()
    for ph in obs["photos"]:
        ph["image_url"] = f"static/photos/{Path(ph['file']).name}"
    files = {
        "study-area.json": sa,
        "datasets.json": c.get("/api/v1/datasets").json(),
        "observations.json": obs,
        "science-sites.json": c.get("/api/v1/science-sites").json(),
        "missions-default.json": c.get("/api/v1/missions/default").json(),
    }
    for name, body in files.items():
        (OUT / "api" / name).write_text(json.dumps(body))
    limits = json.loads((ROOT / "config/mission_defaults.json").read_text()).get("limits", {})
    (OUT / "data" / "engine.json").write_text(json.dumps({"code_version": (ROOT / "VERSION").read_text().strip(), **limits}))
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"static export -> {OUT.relative_to(ROOT)} ({total / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
