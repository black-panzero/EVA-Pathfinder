"""Entry point for the static (GitHub Pages) build. Runs inside Pyodide (CPython on WebAssembly)
in the browser. Uses the same domain, application, schema and handler modules as the FastAPI server;
only the data loading differs (pre-exported NumPy arrays instead of GeoTIFF via rasterio)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from .api import handlers
from .api.schemas import MissionRequest, ReplanRequest, ReportRequest, RouteCompareRequest
from .application.services import MissionService, ServiceError
from .domain.terrain import TerrainGrid


class StaticRepo:
    """TerrainSource backed by files exported by scripts/build_static_site.py."""

    def __init__(self, data_dir: str | Path):
        d = Path(data_dir)
        self.manifest = json.loads((d / "manifest.json").read_text())
        g = self.manifest["grid"]
        z = np.load(d / "dem_crop.npy").astype("float64")
        z[~np.isfinite(z)] = np.nan
        self.grid = TerrainGrid(dataset_id="usgs-m2020-trn-ctx-dtm-20m", elevation_m=z, origin_e_m=g["origin_easting_m"],
                                origin_n_m=g["origin_northing_top_m"], res_m=g["res_m"], crs_wkt=self.manifest["crs"]["wkt"])
        geo = d / "geology_units.npy"
        self.geology_raster = np.load(geo) if geo.exists() else None
        gj = d / "geology_units.json"
        self.geology = json.loads(gj.read_text()) if gj.exists() else None
        art = next(a for a in self.manifest["artifacts"] if a["artifact_id"] == "dem-crop")
        self.dem_sha256 = art["checksum_sha256"]  # checksum of dem_crop.tif recorded at preparation time


_state: dict = {}


def init(data_dir: str, code_version: str, max_stops: int = 3, max_block_radius_m: float = 1000.0) -> str:
    repo = StaticRepo(data_dir)
    _state["repo"] = repo
    _state["svc"] = MissionService(repo, code_version + "+pyodide", max_stops, max_block_radius_m)
    return json.dumps({"ok": True, "grid": [repo.grid.width, repo.grid.height]})


_ROUTES = {
    "routes/compare": (RouteCompareRequest, lambda svc, req: handlers.compare(svc, req)),
    "missions/evaluate": (MissionRequest, lambda svc, req: handlers.evaluate(svc, req)),
    "scenarios/replan": (ReplanRequest, lambda svc, req: handlers.replan(svc, req)),
    "reports": (ReportRequest, lambda svc, req: handlers.report(svc, _state["repo"].manifest, req)),
}


def call(endpoint: str, body_json: str) -> str:
    if "svc" not in _state:
        return json.dumps({"ok": False, "status": 503, "error": {"code": "DATA_UNAVAILABLE", "message": "engine not initialised"}})
    if endpoint not in _ROUTES:
        return json.dumps({"ok": False, "status": 404, "error": {"code": "NOT_FOUND", "message": endpoint}})
    model, fn = _ROUTES[endpoint]
    try:
        req = model.model_validate_json(body_json)
        return json.dumps({"ok": True, "data": fn(_state["svc"], req)}, default=str)
    except ValidationError as exc:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        return json.dumps({"ok": False, "status": 422, "error": {"code": "INVALID_INPUT", "message": "request validation failed", "details": details}})
    except ServiceError as exc:
        return json.dumps({"ok": False, "status": exc.status, "error": {"code": exc.code, "message": exc.message}})
