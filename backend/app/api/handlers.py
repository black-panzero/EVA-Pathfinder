"""Framework-free request handlers shared by the FastAPI server and the in-browser (Pyodide)
static build, so both run exactly the same validation -> service -> DTO code path."""
from __future__ import annotations

import datetime as dt

from ..application.services import EventInput, MissionInput, MissionService, ServiceError, Stop
from ..domain.mission import ResourceBudget, TraversalProfile
from .schemas import EventIn, MissionRequest, ReplanRequest, ReportRequest, RouteCompareRequest


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


def compare(svc: MissionService, req: RouteCompareRequest) -> dict:
    prof = TraversalProfile("user-illustrative", req.profile.flat_speed_m_per_min, req.profile.ascent_rate_m_per_min, req.profile.max_slope_deg) if req.profile else None
    return svc.compare_routes((req.origin.x_m, req.origin.y_m), (req.goal.x_m, req.goal.y_m), req.max_slope_deg, req.slope_weight, prof)


def evaluate(svc: MissionService, req: MissionRequest) -> dict:
    return svc.evaluate(to_mission(req))


def replan(svc: MissionService, req: ReplanRequest) -> dict:
    return svc.replan(to_mission(req.mission), req.elapsed_min, _event(req.event), req.response_mode, req.consumable_loss_units)


def report(svc: MissionService, manifest: dict, req: ReportRequest) -> dict:
    ev = evaluate(svc, req.mission)
    rp = replan(svc, req.replan) if req.replan else None
    return {
        "report_type": "EVA Pathfinder mission evidence report", "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "study_area": {"id": manifest["study_area_id"], "name": manifest["name"], "crs": manifest["crs"]["name"]},
        "mission_evaluation": ev, "contingency": rp,
        "provenance": {"sources": [{k: s.get(k) for k in ("source_id", "title", "landing_page", "citation", "license")} for s in manifest["sources"]],
                       "artifacts": manifest["artifacts"], "alignment": manifest["alignment"]},
        "labels": {"observed": "DEM samples, optical pixels, rover photographs, MEDA archive values, rover localizations",
                   "derived": "slope, route geometry, length, elevation gain/loss, geology along route",
                   "assumed": "speeds, max slope, budgets, consumable rates, reserve",
                   "simulated": "habitat, crew, EVA timeline, blocked zone, consumable loss",
                   "unknown": "rocks and obstacles below 20 m, soil strength, real-time atmosphere"},
        "disclaimer": "Research prototype. Not certified for astronaut EVA navigation or life-support decisions.",
    }
