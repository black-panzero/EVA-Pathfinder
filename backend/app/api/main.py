"""FastAPI application (Presentation context). Thin: validate -> application service -> DTO."""
from __future__ import annotations

import datetime as dt
from contextvars import ContextVar
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ..application import contracts
from ..application.services import MissionService, ServiceError
from ..config import load_settings
from ..infrastructure.repositories import LAYER_FILES, DataUnavailable, StudyAreaRepository, code_version
from . import handlers
from .schemas import MissionBody, ReplanBody, ReportRequest, RouteCompareBody
from .translate_v08 import default_mission_request

API_VERSION = "v1"
# Whole-planet basemap: NASA Solar System Treks (Mars Trek) WMTS, equirectangular (plate carree) 2x1 tiles at level 0.
GLOBAL_BASEMAP = {
    "title": "Viking MDIM 2.1 colour mosaic, 232 m/px (NASA Mars Trek)",
    "url_template": "https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
    "max_native_zoom": 7,
    "attribution": "NASA/JPL-Caltech/USGS, Viking MDIM 2.1 via NASA Mars Trek",
    "source_url": "https://trek.nasa.gov/mars/",
    "evidence_level": "NASA_OBSERVATION",
    "note": "Context only; requires internet. Planning uses the USGS CTX data of the planning area.",
}
settings = load_settings()
app = FastAPI(title="EVA Pathfinder / EVA Guardian API", version="1.0.0",
              description="Return-aware Marswalk planning on real Jezero Crater terrain. Research prototype: not certified for EVA navigation or life support.")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


# Active planning area for the current request (?area=<study_area_id>; default: the primary area).
_current_area: ContextVar[str] = ContextVar("current_area", default=settings.study_area_id)


@app.middleware("http")
async def _select_area(request: Request, call_next):  # type: ignore[no-untyped-def]
    area_id = request.query_params.get("area") or settings.study_area_id
    if settings.area(area_id) is None:
        return JSONResponse(status_code=404, content=handlers.error_body("AREA_NOT_FOUND", f"unknown planning area '{area_id}'"))
    token = _current_area.set(area_id)
    try:
        return await call_next(request)
    finally:
        _current_area.reset(token)


@lru_cache(maxsize=8)
def _repo_for(area_id: str) -> StudyAreaRepository:
    return StudyAreaRepository(settings, area_id)


def repo() -> StudyAreaRepository:
    return _repo_for(_current_area.get())


def service() -> MissionService:
    lim = settings.mission_defaults.get("limits", {})
    return MissionService(repo(), code_version(settings.root), lim.get("max_stops", 3), lim.get("max_block_radius_m", 1000.0))


@app.exception_handler(ServiceError)
async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.to_error()})


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo raw input back (it may contain NaN/inf, which is not valid JSON).
    return JSONResponse(status_code=422, content=handlers.validation_error(list(exc.errors())))


@app.exception_handler(DataUnavailable)
async def _data_unavailable(_: Request, exc: DataUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content=handlers.error_body("DATA_UNAVAILABLE", str(exc)))


# ------------------------------------------------------------------------------------ GET
@app.get("/health")
def health() -> dict:
    try:
        r = repo()
        g = r.grid
        m = r.manifest
        core = {sid: contracts.source_status(m, sid) for sid in contracts.CORE_SOURCE_IDS}
        ds = "AVAILABLE_VERIFIED" if all(v == "AVAILABLE_VERIFIED" for v in core.values()) else "PARTIAL"
        ready = core[contracts.DEM_SOURCE_ID] == "AVAILABLE_VERIFIED"
        return {"status": "ready" if ready else "degraded", "dataset_status": ds, "core_sources": core, "data_ready": True,
                "study_area_id": m["study_area_id"], "grid": [g.width, g.height], "code_version": code_version(settings.root), "time": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    except DataUnavailable as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "dataset_status": "UNAVAILABLE", "data_ready": False, "detail": str(exc)})  # type: ignore[return-value]


@app.get(f"/api/{API_VERSION}/datasets")
def datasets() -> dict:
    r = repo()
    m = r.manifest
    g = r.grid
    status = m.get("source_status") or {}
    mc = contracts.map_contract(m, g)
    raster_arts: dict[str, dict] = {}
    for a in m["artifacts"]:
        for sid in a.get("source_ids", []):
            if a.get("resolution_m"):
                raster_arts.setdefault(sid, a)  # first raster artifact (dem-crop for the DEM)
    out = []
    for s in m["sources"]:
        sid = s["source_id"]
        st = status.get(sid, {}).get("status", "UNAVAILABLE")
        if sid == "usgs-sim3464-geology" and st == "AVAILABLE_VERIFIED":
            st = "PARTIAL"  # available but only regionally aligned (documented 100-200 m offsets)
        files = status.get(sid, {}).get("files", [])
        art = raster_arts.get(sid)
        limitation = s.get("known_limitation") or (art or {}).get("limitations")
        out.append({**{k: s.get(k) for k in ("source_id", "title", "category", "mission", "instrument", "producer", "landing_page", "url", "units", "license", "citation", "known_limitation")},
                    "verification_status": st, "files": files,
                    # 08 contract names
                    "id": contracts.contract_dataset_id(sid), "product": s.get("title"), "body": "Mars",
                    "crs": (m.get("crs") or {}).get("name") if art else None,
                    "crs_id": mc["crs_id"] if art else None,
                    "bounds": {"bounds_xy_m": mc["bounds_xy_m"], "lon_range_deg": mc["lon_range_deg"], "lat_range_deg": mc["lat_range_deg"], "crop": "study-area crop of the source"} if art else None,
                    "resolution_m": art.get("resolution_m") if art else None,
                    "file_sha256": s.get("sha256") or (files[0].get("sha256") if files else None),
                    "acquisition_date": s.get("acquisition_date"), "creation_date": s.get("creation_date"),
                    "processed_at": art.get("created_at") if art else None,
                    "status": st, "source_url": s.get("url") or s.get("landing_page"),
                    "limitations": [limitation] if limitation else []})
    return {"datasets": out, "artifacts": m["artifacts"], "alignment": m["alignment"], "dem_stats": m["dem_stats"],
            "map_contract": mc, "dataset_aliases": dict(contracts.DATASET_ALIASES)}


@app.get(f"/api/{API_VERSION}/study-area")
def study_area() -> dict:
    r = repo()
    m = r.manifest
    g = r.grid
    return {"study_area_id": m["study_area_id"], "name": m["name"], "body": "Mars", "crs": m["crs"], "grid": m["grid"],
            "extent_xy_m": list(g.extent_xy_m), "scale": g.ground_scale_bar(), "dem_stats": m["dem_stats"],
            "habitat": r.science["habitat"], "layers": [{"layer_id": k, "title": v[1], "evidence_level": v[2], "image_url": f"/api/{API_VERSION}/layers/{k}/image", "bounds_xy_m": [[0, 0], list(g.extent_xy_m)]} for k, v in LAYER_FILES.items() if r.layer_path(k)],
            "rover_traverse": r.traverse, "geology_units": r.geology,
            "disclaimer": "Static historical orbital data. 20 m DEM cannot resolve rocks or human-scale hazards. Research prototype: not certified for EVA navigation or life support.",
            "map_contract": contracts.map_contract(m, g),
            "context": ({**m["context"], "image_url": f"/api/{API_VERSION}/context/image"} if m.get("context") and (r.dir / m["context"]["file"]).exists() else None),
            "global_basemap": GLOBAL_BASEMAP}


@app.get(f"/api/{API_VERSION}/context/image")
def context_image() -> FileResponse:
    r = repo()
    ctx = r.manifest.get("context")
    p = (r.dir / ctx["file"]) if ctx else None
    if not p or not p.exists():
        raise HTTPException(404, "context image not prepared")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


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
    r = repo()
    g = r.grid
    crs_id = contracts.crs_id_for(r.manifest)
    sites = []
    for s in r.science.get("sites", []):
        point = None
        if s.get("x_m") is not None and s.get("y_m") is not None and g.contains_xy(s["x_m"], s["y_m"]):
            point = {"x_m": s["x_m"], "y_m": s["y_m"], "crs_id": crs_id}
        verified = point is not None and s.get("evidence_level") == "NASA_OBSERVATION"
        row_col = g.xy_to_cell(point["x_m"], point["y_m"]) if point else None
        sites.append({**s, "objective": s.get("science_summary"),
                      "location_status": "verified" if verified else "contextual",
                      "map_point": point, "grid_cell": {"row": row_col[0], "col": row_col[1]} if row_col else None,
                      "lon_deg_180": contracts.normalize_lon_180(s["lon_deg"]) if s.get("lon_deg") is not None else None,
                      "source_urls": [c["url"] for c in s.get("citations", []) if c.get("url")],
                      "notes": s.get("location_basis")})
    return {**r.science, "sites": sites, "map_contract": contracts.map_contract(r.manifest, g)}


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


@app.get(f"/api/{API_VERSION}/areas")
def areas() -> dict:
    """All planning areas (static config; routing runs inside one area at a time)."""
    out = []
    for a in settings.areas:
        aid = a["study_area_id"]
        try:
            r = _repo_for(aid)
            g = r.manifest["grid"]
            out.append({"study_area_id": aid, "name": a["name"], "short_name": a.get("short_name", a["name"]), "default": aid == settings.study_area_id,
                        "lon_range_deg": g["lon_range_deg"], "lat_range_deg": g["lat_range_deg"], "data_ready": True,
                        "plannable_sites": sum(1 for s in r.science["sites"] if s.get("in_planning_area", True))})
        except DataUnavailable:
            out.append({"study_area_id": aid, "name": a["name"], "short_name": a.get("short_name", a["name"]), "default": aid == settings.study_area_id, "data_ready": False})
    return {"areas": out}


@app.get(f"/api/{API_VERSION}/missions/default")
def default_mission() -> dict:
    """Default request payload built from config (inputs only; no precomputed results)."""
    d = settings.mission_defaults
    tp, b = d["traversal_profile"], d["budgets"]
    return {
        "mission_name": d["mission_name"],
        "request": default_mission_request(d, repo().science),
        "labels": {"consumable_label": b["consumable_label"], "profile_basis": tp["basis"], "note": d["_comment"]},
    }


def _default_mission() -> dict | None:
    return default_mission_request(settings.mission_defaults, repo().science)


# ------------------------------------------------------------------------------------ POST
@app.post(f"/api/{API_VERSION}/routes/compare")
def compare(req: RouteCompareBody) -> dict:
    """Accepts the legacy body ({origin, goal, ...} in local metres) or the 08 body ({origin, destination} as {row, col} or map points)."""
    return handlers.compare(service(), req, settings.mission_defaults)


@app.post(f"/api/{API_VERSION}/missions/evaluate")
def evaluate(req: MissionBody) -> dict:
    """Accepts the legacy body, the 08 body, or the handoff mission template (config/mission.delta-return.example.json, filled in)."""
    return handlers.evaluate(service(), req, settings.mission_defaults)


@app.post(f"/api/{API_VERSION}/scenarios/replan")
def replan(req: ReplanBody) -> dict:
    """Accepts the legacy body or the 08 body (current_grid_cell + already_elapsed_minutes + already_used_consumable_units, SIMULATED_BLOCKAGE cells)."""
    return handlers.replan(service(), req, settings.mission_defaults, _default_mission())


@app.post(f"/api/{API_VERSION}/reports")
def report(req: ReportRequest) -> dict:
    return handlers.report(service(), repo().manifest, req, settings.mission_defaults, _default_mission())
