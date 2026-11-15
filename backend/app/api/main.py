"""FastAPI application (Presentation context). Thin: validate -> application service -> DTO."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ..application.services import MissionService, ServiceError
from ..config import load_settings
from ..infrastructure.repositories import LAYER_FILES, DataUnavailable, StudyAreaRepository, code_version
from . import handlers
from .schemas import MissionRequest, ReplanRequest, ReportRequest, RouteCompareRequest

API_VERSION = "v1"
settings = load_settings()
app = FastAPI(title="EVA Pathfinder / EVA Guardian API", version="1.0.0",
              description="Return-aware Marswalk planning on real Jezero Crater terrain. Research prototype: not certified for EVA navigation or life support.")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@lru_cache(maxsize=1)
def repo() -> StudyAreaRepository:
    return StudyAreaRepository(settings)


def service() -> MissionService:
    lim = settings.mission_defaults.get("limits", {})
    return MissionService(repo(), code_version(settings.root), lim.get("max_stops", 3), lim.get("max_block_radius_m", 1000.0))


@app.exception_handler(ServiceError)
async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo raw input back (it may contain NaN/inf, which is not valid JSON).
    details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": "request validation failed", "details": details}})


@app.exception_handler(DataUnavailable)
async def _data_unavailable(_: Request, exc: DataUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": {"code": "DATA_UNAVAILABLE", "message": str(exc)}})


# ------------------------------------------------------------------------------------ GET
@app.get("/health")
def health() -> dict:
    try:
        r = repo()
        g = r.grid
        return {"status": "ok", "data_ready": True, "study_area_id": r.manifest["study_area_id"], "grid": [g.width, g.height], "code_version": code_version(settings.root), "time": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    except DataUnavailable as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "data_ready": False, "detail": str(exc)})  # type: ignore[return-value]


@app.get(f"/api/{API_VERSION}/datasets")
def datasets() -> dict:
    m = repo().manifest
    status = m["source_status"]
    out = []
    for s in m["sources"]:
        st = status.get(s["source_id"], {}).get("status", "UNAVAILABLE")
        if s["source_id"] == "usgs-sim3464-geology" and st == "AVAILABLE_VERIFIED":
            st = "PARTIAL"  # available but only regionally aligned (documented 100-200 m offsets)
        out.append({**{k: s.get(k) for k in ("source_id", "title", "category", "mission", "instrument", "producer", "landing_page", "url", "units", "license", "citation", "known_limitation")},
                    "verification_status": st, "files": status.get(s["source_id"], {}).get("files", [])})
    return {"datasets": out, "artifacts": m["artifacts"], "alignment": m["alignment"], "dem_stats": m["dem_stats"]}


@app.get(f"/api/{API_VERSION}/study-area")
def study_area() -> dict:
    r = repo()
    m = r.manifest
    g = r.grid
    return {"study_area_id": m["study_area_id"], "name": m["name"], "body": "Mars", "crs": m["crs"], "grid": m["grid"],
            "extent_xy_m": list(g.extent_xy_m), "scale": g.ground_scale_bar(), "dem_stats": m["dem_stats"],
            "habitat": r.science["habitat"], "layers": [{"layer_id": k, "title": v[1], "evidence_level": v[2], "image_url": f"/api/{API_VERSION}/layers/{k}/image", "bounds_xy_m": [[0, 0], list(g.extent_xy_m)]} for k, v in LAYER_FILES.items() if r.layer_path(k)],
            "rover_traverse": r.traverse, "geology_units": r.geology,
            "disclaimer": "Static historical orbital data. 20 m DEM cannot resolve rocks or human-scale hazards. Research prototype: not certified for EVA navigation or life support."}


@app.get(f"/api/{API_VERSION}/layers/{{layer_id}}")
def layer_meta(layer_id: str) -> dict:
    r = repo()
    if not r.layer_path(layer_id):
        raise ServiceError("LAYER_NOT_FOUND", f"unknown layer '{layer_id}'", 404)
    art = next((a for a in r.manifest["artifacts"] if a["artifact_id"] == layer_id), None)
    return {"layer_id": layer_id, "title": LAYER_FILES[layer_id][1], "evidence_level": LAYER_FILES[layer_id][2], "artifact": art, "image_url": f"/api/{API_VERSION}/layers/{layer_id}/image", "bounds_xy_m": [[0, 0], list(r.grid.extent_xy_m)]}


@app.get(f"/api/{API_VERSION}/layers/{{layer_id}}/image")
def layer_image(layer_id: str) -> FileResponse:
    p = repo().layer_path(layer_id)
    if not p:
        raise HTTPException(404, "layer not found")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get(f"/api/{API_VERSION}/science-sites")
def science_sites() -> dict:
    return repo().science


@app.get(f"/api/{API_VERSION}/observations")
def observations() -> dict:
    r = repo()
    photos = [{**p, "image_url": f"/api/{API_VERSION}/observations/photos/{p['photo_id']}"} for p in r.photos]
    meda = r.meda
    return {"photos": photos, "atmosphere": meda if meda else {"status": "NOT_INTEGRATED"}}


@app.get(f"/api/{API_VERSION}/observations/photos/{{photo_id}}")
def photo(photo_id: str) -> FileResponse:
    p = repo().photo_path(photo_id)
    if not p:
        raise HTTPException(404, "photo not found")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get(f"/api/{API_VERSION}/missions/default")
def default_mission() -> dict:
    """Default request payload built from config (inputs only; no precomputed results)."""
    d = settings.mission_defaults
    sci = repo().science
    tp, b = d["traversal_profile"], d["budgets"]
    return {
        "mission_name": d["mission_name"],
        "request": {
            "habitat": {"x_m": sci["habitat"]["x_m"], "y_m": sci["habitat"]["y_m"]},
            "stops": [{"stop_id": s["id"], "name": s["name"], "point": {"x_m": s["x_m"], "y_m": s["y_m"]}, "activity_min": s["default_activity_min"]} for s in sci["sites"][:1]],
            "route_choice": "terrain",
            "profile": {"flat_speed_m_per_min": tp["flat_speed_m_per_min"], "ascent_rate_m_per_min": tp["ascent_rate_m_per_min"], "max_slope_deg": tp["max_slope_deg"]},
            "budget": {k: b[k] for k in ("time_available_min", "consumable_initial_units", "consumable_rate_traverse_per_min", "consumable_rate_activity_per_min", "reserve_fraction")},
            "slope_weight": d["route_policies"]["terrain"]["slope_weight"], "unknown_policy": "block", "unknown_weight": 0.0,
        },
        "labels": {"consumable_label": b["consumable_label"], "profile_basis": tp["basis"], "note": d["_comment"]},
    }


# ------------------------------------------------------------------------------------ POST
@app.post(f"/api/{API_VERSION}/routes/compare")
def compare(req: RouteCompareRequest) -> dict:
    return handlers.compare(service(), req)


@app.post(f"/api/{API_VERSION}/missions/evaluate")
def evaluate(req: MissionRequest) -> dict:
    return handlers.evaluate(service(), req)


@app.post(f"/api/{API_VERSION}/scenarios/replan")
def replan(req: ReplanRequest) -> dict:
    return handlers.replan(service(), req)


@app.post(f"/api/{API_VERSION}/reports")
def report(req: ReportRequest) -> dict:
    return handlers.report(service(), repo().manifest, req)
