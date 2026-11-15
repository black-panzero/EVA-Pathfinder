"""Framework-free request handlers shared by the FastAPI server and the in-browser (Pyodide)
static build, so both run exactly the same validation -> service -> DTO code path.

Each handler accepts the legacy request model AND the 08-contract model (see schemas.py
discriminated unions); 08 shapes are translated by translate_v08.py."""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..application import contracts
from ..application.services import EventInput, MissionInput, MissionService, ServiceError, Stop
from ..domain.mission import ResourceBudget, TraversalProfile
from . import translate_v08 as v08
from .schemas import (
    EventIn,
    MissionConfigRequest,
    MissionContractRequest,
    MissionRequest,
    ReplanContractRequest,
    ReplanRequest,
    ReportRequest,
    RouteCompareContractRequest,
    RouteCompareRequest,
)

_SHAPE_TAGS = {"legacy", "v08", "mission_config"}
_COORD_KEYS = {"origin", "destination", "goal", "habitat", "point", "current_grid_cell", "row", "col", "x_m", "y_m", "center", "blocked_cells", "map_point"}


def validation_error(errors: list[Any]) -> dict:
    """Shared 422 body (legacy code INVALID_INPUT + 08 contract_code)."""
    # Drop the union tag inserted by the shape discriminator so legacy loc paths are unchanged.
    details = [{"loc": [p for p in e.get("loc", []) if p not in _SHAPE_TAGS], "msg": e.get("msg", ""), "type": e.get("type", "")} for e in errors]
    coord = any(str(p) in _COORD_KEYS for d in details for p in d["loc"])
    return {"error": {"code": "INVALID_INPUT", "contract_code": "INVALID_COORDINATES" if coord else "INVALID_MISSION_CONFIGURATION",
                      "message": "request validation failed", "details": details}}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "contract_code": contracts.contract_code(code), "message": message}}


def to_mission(m: MissionRequest) -> MissionInput:
    try:
        return MissionInput(
            habitat_xy=(m.habitat.x_m, m.habitat.y_m),
            stops=tuple(Stop(s.stop_id, s.name, s.point.x_m, s.point.y_m, s.activity_min) for s in m.stops),
            route_choice=m.route_choice,
            profile=TraversalProfile("user-illustrative", m.profile.flat_speed_m_per_min, m.profile.ascent_rate_m_per_min, m.profile.max_slope_deg),
            budget=ResourceBudget(m.budget.time_available_min, m.budget.consumable_initial_units, m.budget.consumable_rate_traverse_per_min, m.budget.consumable_rate_activity_per_min, m.budget.reserve_fraction),
            slope_weight=m.slope_weight, unknown_policy=m.unknown_policy, unknown_weight=m.unknown_weight,
        )
    except ValueError as exc:
        raise ServiceError("INVALID_INPUT", str(exc)) from exc


def _event(e: EventIn) -> EventInput:
    return EventInput(e.radius_m, (e.center.x_m, e.center.y_m) if e.center else None, e.position_fraction)


def compare(svc: MissionService, req: RouteCompareRequest | RouteCompareContractRequest, defaults: dict | None = None) -> dict:
    if isinstance(req, RouteCompareContractRequest):
        return v08.compare(svc, req, defaults)
    prof = TraversalProfile("user-illustrative", req.profile.flat_speed_m_per_min, req.profile.ascent_rate_m_per_min, req.profile.max_slope_deg) if req.profile else None
    return svc.compare_routes((req.origin.x_m, req.origin.y_m), (req.goal.x_m, req.goal.y_m), req.max_slope_deg, req.slope_weight, prof)


def evaluate(svc: MissionService, req: MissionRequest | MissionContractRequest | MissionConfigRequest, defaults: dict | None = None) -> dict:
    if isinstance(req, MissionRequest):
        return svc.evaluate(to_mission(req))
    extra: list[dict] = []
    shape = "08"
    if isinstance(req, MissionConfigRequest):
        extra = v08.config_assumptions(req)
        shape = "handoff-mission-template"
        req = v08.config_to_contract(req)
    mi, assumptions = v08.to_mission(svc, req, defaults)
    out = svc.evaluate(mi)
    return v08.merge_contract_meta(out, extra + assumptions, req.mission_id, shape)


def replan(svc: MissionService, req: ReplanRequest | ReplanContractRequest, defaults: dict | None = None, default_mission: dict | None = None) -> dict:
    if isinstance(req, ReplanContractRequest):
        return v08.replan(svc, req, defaults, default_mission, to_mission)
    return svc.replan(to_mission(req.mission), req.elapsed_min, _event(req.event), req.response_mode, req.consumable_loss_units)


def report(svc: MissionService, manifest: dict, req: ReportRequest, defaults: dict | None = None, default_mission: dict | None = None) -> dict:
    ev = evaluate(svc, req.mission, defaults)
    rp = replan(svc, req.replan, defaults, default_mission) if req.replan else None
    final_status = rp["alternative"]["status"] if rp else ev["status"]
    sources = manifest.get("sources", [])
    status = manifest.get("source_status") or {}
    unknowns: list[Any] = ["Rocks, boulders and obstacles below the 20 m DEM resolution", "Soil strength / trafficability", "Real-time atmosphere and dust",
                           "Physiological validity of speeds, consumable rates and reserves"]
    if final_status == "UNKNOWN":
        unknowns.append("Route crosses DEM cells without elevation/slope (unknown terrain)")
    return {
        "report_type": "EVA Pathfinder mission evidence report", "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "study_area": {"id": manifest.get("study_area_id"), "name": manifest.get("name"), "crs": (manifest.get("crs") or {}).get("name")},
        "mission_evaluation": ev, "contingency": rp,
        "provenance": {"sources": [{k: s.get(k) for k in ("source_id", "title", "landing_page", "citation", "license")} for s in sources],
                       "artifacts": manifest.get("artifacts", []), "alignment": manifest.get("alignment")},
        "labels": {"observed": "DEM samples, optical pixels, rover photographs, MEDA archive values, rover localizations",
                   "derived": "slope, route geometry, length, elevation gain/loss, geology along route",
                   "assumed": "speeds, max slope, budgets, consumable rates, reserve",
                   "simulated": "habitat, crew, EVA timeline, blocked zone, consumable loss",
                   "unknown": "rocks and obstacles below 20 m, soil strength, real-time atmosphere"},
        "disclaimer": "Research prototype. Not certified for astronaut EVA navigation or life-support decisions.",
        # 08 contract fields
        "model_build_version": svc.code_version,
        "data_processing_version": manifest.get("processing_version"),
        "route_policy_version": contracts.ROUTE_POLICY_VERSION,
        "source_hashes": {
            "dem_crop_sha256": svc.repo.dem_sha256,
            "sources": {s["source_id"]: s.get("sha256") or (status.get(s["source_id"], {}).get("files") or [{}])[0].get("sha256") for s in sources},
            "artifacts": {a["artifact_id"]: a.get("checksum_sha256") for a in manifest.get("artifacts", [])},
        },
        "study_extent": svc.map_contract(),
        "computed_from_real_data": svc.computed_from_real_data(),
        "route_alternatives": {"selected": ev["assessment"], "alternative": ev["alternative"]},
        "resource_constraints": ev["assumptions"],
        "scenario_event": rp["event"] if rp else None,
        "final_status": final_status,
        "mission_state": rp["mission_state"] if rp else ev["mission_state"],
        "assumptions": ev["assumptions"],
        "unknowns": unknowns,
    }
