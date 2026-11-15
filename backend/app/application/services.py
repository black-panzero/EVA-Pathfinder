"""Application services: orchestrate domain objects; no HTTP or raster I/O here.

PlanCandidateRoutes, EvaluateMarswalk, AdvanceSimulatedMission (via elapsed time),
InjectContingencyAndReplan and BuildMissionEvidenceReport from the specification are the public
methods of `MissionService`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np

from ..domain.contingency import BlockedZone, build_timeline, locate, point_along
from ..domain.evidence import STANDARD_ASSUMPTIONS, EventLog
from ..domain.mission import ActivityResult, FeasibilityAssessment, LegResult, ResourceBudget, TraversalProfile, assess, leg_cost
from ..domain.navigation import Cell, Route, RoutePolicy, TraversalMask, build_mask, diagnose_no_route, find_path, measure_route, validate_route
from ..domain.terrain import TerrainError, TerrainGrid


class TerrainSource(Protocol):
    @property
    def grid(self) -> TerrainGrid: ...
    @property
    def geology(self) -> dict | None: ...
    @property
    def geology_raster(self) -> np.ndarray | None: ...
    @property
    def dem_sha256(self) -> str: ...
    @property
    def manifest(self) -> dict: ...


# --------------------------------------------------------------------------- inputs (domain-level)
@dataclass(frozen=True)
class Stop:
    stop_id: str
    name: str
    x_m: float
    y_m: float
    activity_min: float


@dataclass(frozen=True)
class MissionInput:
    habitat_xy: tuple[float, float]
    stops: tuple[Stop, ...]
    route_choice: Literal["shortest", "terrain"]
    profile: TraversalProfile
    budget: ResourceBudget
    slope_weight: float
    unknown_policy: Literal["block", "penalize"] = "block"
    unknown_weight: float = 0.0


@dataclass(frozen=True)
class EventInput:
    radius_m: float
    center_xy: tuple[float, float] | None = None
    position_fraction: float = 0.5


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _r(v: float | None, n: int = 2) -> float | None:
    return None if v is None or not math.isfinite(v) else round(float(v), n)


class MissionService:
    def __init__(self, repo: TerrainSource, code_version: str, max_stops: int = 3, max_block_radius_m: float = 1000.0):
        self.repo = repo
        self.code_version = code_version
        self.max_stops = max_stops
        self.max_block_radius_m = max_block_radius_m

    @property
    def grid(self) -> TerrainGrid:
        return self.repo.grid

    # ------------------------------------------------------------------ helpers
    def cell_of(self, x: float, y: float, what: str) -> Cell:
        try:
            return self.grid.xy_to_cell(x, y)
        except TerrainError as exc:
            raise ServiceError(exc.code, f"{what}: {exc}") from exc

    def policies(self, max_slope: float, slope_weight: float, unknown_policy: str = "block", unknown_weight: float = 0.0) -> dict[str, RoutePolicy]:
        try:
            return {
                "shortest": RoutePolicy("shortest-feasible", max_slope, 0.0, unknown_policy, unknown_weight),  # type: ignore[arg-type]
                "terrain": RoutePolicy("terrain-aware", max_slope, slope_weight, unknown_policy, unknown_weight),  # type: ignore[arg-type]
            }
        except ValueError as exc:
            raise ServiceError("INVALID_POLICY", str(exc)) from exc

    def _route(self, mask: TraversalMask, policy: RoutePolicy, a: Cell, b: Cell, route_id: str, blocked: np.ndarray | None = None) -> tuple[Route | None, list[str], dict]:
        t0 = time.perf_counter()
        res = find_path(self.grid, mask, policy, a, b)
        info = {"runtime_ms": round((time.perf_counter() - t0) * 1000, 1), "expanded_cells": res.expanded}
        if res.cells is None:
            reasons = [res.reason or "NO_ROUTE"]
            if res.reason == "NO_ROUTE":
                reasons = diagnose_no_route(self.grid, policy, a, b, blocked, None)
            elif res.reason in ("START_IMPASSABLE", "GOAL_IMPASSABLE"):
                cell = a if res.reason.startswith("START") else b
                if mask.unknown[cell]:
                    reasons.append("UNMAPPED_TERRAIN")
                elif mask.blocked_by_slope[cell]:
                    reasons.append("SLOPE_EXCEEDS_LIMIT")
                elif mask.blocked_by_scenario[cell]:
                    reasons.append("BLOCKED_BY_SCENARIO_EVENT")
                reasons.append("NO_ROUTE")
            return None, reasons, info
        route = measure_route(self.grid, mask, policy, res.cells, res.cost, route_id)
        problems = validate_route(mask, route.cells)
        if problems:  # should be impossible; never hand back an invalid path
            raise ServiceError("INTERNAL_ROUTE_INVALID", "; ".join(problems[:5]), 500)
        return route, [], info

    def route_dto(self, route: Route, profile: TraversalProfile | None = None, info: dict | None = None, max_profile_points: int = 400) -> dict:
        g = self.grid
        m = route.metrics
        step = max(1, len(route.profile) // max_profile_points)
        prof = route.profile[::step]
        if prof[-1] is not route.profile[-1]:
            prof.append(route.profile[-1])
        geology = self._geology_along(route)
        out: dict[str, Any] = {
            "route_id": route.route_id, "policy": {"policy_id": route.policy.policy_id, "max_slope_deg": route.policy.max_slope_deg, "slope_weight": route.policy.slope_weight, "unknown_policy": route.policy.unknown_policy},
            "polyline_xy_m": [[round(x, 1), round(y, 1)] for x, y in route.polyline_xy(g)],
            "metrics": {"length_m": _r(m.length_m, 1), "elevation_gain_m": _r(m.elevation_gain_m, 1), "elevation_loss_m": _r(m.elevation_loss_m, 1),
                        "max_derived_slope_deg": _r(m.max_derived_slope_deg), "mean_derived_slope_deg": _r(m.mean_derived_slope_deg),
                        "max_step_grade_deg": _r(m.max_step_grade_deg), "unknown_length_fraction": _r(m.unknown_length_fraction, 4),
                        "cell_count": m.cell_count, "policy_cost": _r(m.policy_cost, 1)},
            "profile": [{"distance_m": _r(p.distance_m, 1), "elevation_m": _r(p.elevation_m), "slope_deg": _r(p.slope_deg), "x_m": _r(p.x_m, 1), "y_m": _r(p.y_m, 1)} for p in prof],
            "geology_along_route": geology,
            "evidence_level": "DERIVED",
        }
        if profile is not None:
            out["metrics"]["estimated_minutes"] = _r(sum(profile.step_minutes(L, dz) for L, dz in zip(route.step_lengths_m, route.step_dz_m)), 1)
        if info:
            out["compute"] = info
        return out

    def _geology_along(self, route: Route) -> list[dict]:
        raster, units = self.repo.geology_raster, self.repo.geology
        if raster is None or not units:
            return []
        lookup = {u["code"]: u for u in units["units"]}
        acc: dict[int, float] = {}
        for b, L in zip(route.cells[1:], route.step_lengths_m):
            acc[int(raster[b])] = acc.get(int(raster[b]), 0.0) + L
        total = sum(acc.values()) or 1.0
        return [{"symbol": lookup[k]["symbol"], "name": lookup[k]["name"], "length_fraction": round(v / total, 3)} for k, v in sorted(acc.items(), key=lambda kv: -kv[1]) if k in lookup]

    # ------------------------------------------------------------------ PlanCandidateRoutes
    def compare_routes(self, origin: tuple[float, float], goal: tuple[float, float], max_slope: float, slope_weight: float, profile: TraversalProfile | None = None, unknown_policy: str = "block") -> dict:
        a = self.cell_of(*origin, "origin")
        b = self.cell_of(*goal, "goal")
        if a == b:
            raise ServiceError("SAME_START_GOAL", "origin and goal fall in the same 20 m cell")
        log = EventLog()
        out_routes = []
        failures = {}
        cells_by_id = {}
        for key, pol in self.policies(max_slope, slope_weight, unknown_policy).items():
            mask = build_mask(self.grid, pol)
            route, reasons, info = self._route(mask, pol, a, b, key)
            if route is None:
                failures[key] = reasons
                continue
            cells_by_id[key] = route.cells
            out_routes.append(self.route_dto(route, profile, info))
            log.record("RouteComputed", route_id=key, length_m=round(route.metrics.length_m, 1))
        coincide = "shortest" in cells_by_id and "terrain" in cells_by_id and cells_by_id["shortest"] == cells_by_id["terrain"]
        overlap = None
        if len(cells_by_id) == 2:
            s1, s2 = set(cells_by_id["shortest"]), set(cells_by_id["terrain"])
            overlap = round(len(s1 & s2) / len(s1 | s2), 3)
        return {"routes": out_routes, "failures": failures, "routes_coincide": coincide, "cell_overlap_jaccard": overlap,
                "caveats": ["Routes follow 20 m DEM cell centres; slope is a 40 m-baseline approximation and cannot see rocks or small scarps.",
                            "Shortest-feasible minimises ground length subject to the same hard slope/no-data exclusions as the terrain-aware route."],
                "events": log.to_list()}

    # ------------------------------------------------------------------ EvaluateMarswalk
    def _plan(self, mi: MissionInput, choice: str, scenario_blocked: np.ndarray | None = None) -> tuple[list[LegResult], list[ActivityResult], dict[str, dict], RoutePolicy]:
        if not mi.stops:
            raise ServiceError("NO_STOPS", "at least one science stop is required")
        if len(mi.stops) > self.max_stops:
            raise ServiceError("TOO_MANY_STOPS", f"at most {self.max_stops} stops")
        pol = self.policies(mi.profile.max_slope_deg, mi.slope_weight, mi.unknown_policy, mi.unknown_weight)[choice]
        mask = build_mask(self.grid, pol, scenario_blocked)
        points = [("habitat", "Habitat", mi.habitat_xy)] + [(s.stop_id, s.name, (s.x_m, s.y_m)) for s in mi.stops] + [("habitat", "Habitat", mi.habitat_xy)]
        cells = [self.cell_of(*p[2], p[0]) for p in points]
        legs: list[LegResult] = []
        infos: dict[str, dict] = {}
        for i in range(len(points) - 1):
            leg_id = f"leg{i + 1}:{points[i][0]}->{points[i + 1][0]}"
            if cells[i] == cells[i + 1]:
                raise ServiceError("SAME_START_GOAL", f"{leg_id}: consecutive points share one 20 m cell")
            route, reasons, info = self._route(mask, pol, cells[i], cells[i + 1], leg_id, scenario_blocked)
            infos[leg_id] = info
            if route is None:
                legs.append(LegResult(leg_id, points[i][0], points[i + 1][0], None, math.inf, math.inf, tuple(reasons)))
            else:
                mins, cons = leg_cost(route, mi.profile, mi.budget)
                legs.append(LegResult(leg_id, points[i][0], points[i + 1][0], route, mins, cons))
        acts = [ActivityResult(s.stop_id, s.activity_min, s.activity_min * mi.budget.consumable_rate_activity_per_min) for s in mi.stops]
        return legs, acts, infos, pol

    def assessment_dto(self, a: FeasibilityAssessment, mi: MissionInput, infos: dict[str, dict] | None = None) -> dict:
        return {
            "status": a.status.value, "reason_codes": a.reasons,
            "totals": {"minutes": _r(a.total_minutes, 1), "consumable_units": _r(a.total_consumable, 1),
                       "usable_time_min": _r(a.usable_time_min, 1), "usable_consumable_units": _r(a.usable_consumable, 1),
                       "time_margin_min": _r(a.time_margin_min, 1), "consumable_margin_units": _r(a.consumable_margin, 1),
                       "time_available_min": mi.budget.time_available_min, "consumable_initial_units": mi.budget.consumable_initial_units,
                       "reserve_fraction": mi.budget.reserve_fraction, "consumable_label": mi.budget.consumable_label},
            "legs": [{"leg_id": leg.leg_id, "from": leg.from_id, "to": leg.to_id, "minutes": _r(leg.minutes, 1), "consumable_units": _r(leg.consumable, 1), "reason_codes": list(leg.reasons),
                      "route": self.route_dto(leg.route, mi.profile, (infos or {}).get(leg.leg_id)) if leg.route else None} for leg in a.legs],
            "activities": [{"stop_id": x.stop_id, "minutes": x.minutes, "consumable_units": _r(x.consumable, 1)} for x in a.activities],
            "evidence_level": "ILLUSTRATIVE_MODEL",
        }

    def evaluate(self, mi: MissionInput) -> dict:
        log = EventLog()
        log.record("MissionConfigured", stops=[s.stop_id for s in mi.stops], route_choice=mi.route_choice)
        legs, acts, infos, _ = self._plan(mi, mi.route_choice)
        a = assess(legs, acts, mi.budget)
        log.record("FeasibilityEvaluated", status=a.status.value, reasons=a.reasons)
        if a.status.value == "INFEASIBLE":
            log.record("MissionMarkedInfeasible", reasons=a.reasons)
        alt_choice = "terrain" if mi.route_choice == "shortest" else "shortest"
        alt_legs, alt_acts, _, _ = self._plan(mi, alt_choice)
        alt = assess(alt_legs, alt_acts, mi.budget)
        return {
            "mission_name": "Operation Delta Return", "route_choice": mi.route_choice,
            "assessment": self.assessment_dto(a, mi, infos),
            "alternative": {"route_choice": alt_choice, "status": alt.status.value, "reason_codes": alt.reasons, "total_minutes": _r(alt.total_minutes, 1),
                            "total_consumable_units": _r(alt.total_consumable, 1), "total_length_m": _r(sum(l.route.metrics.length_m for l in alt.legs if l.route), 1) if all(l.route for l in alt.legs) else None,
                            "total_gain_m": _r(sum(l.route.metrics.elevation_gain_m for l in alt.legs if l.route), 1) if all(l.route for l in alt.legs) else None},
            "evidence": [e.to_dict() for e in STANDARD_ASSUMPTIONS],
            "events": log.to_list(),
            "run_manifest": self.run_manifest(mi),
            "disclaimer": "Research prototype. Not certified for astronaut EVA navigation or life-support decisions.",
        }

    # ------------------------------------------------------------------ InjectContingencyAndReplan
    def replan(self, mi: MissionInput, elapsed_min: float, event: EventInput, response_mode: Literal["return_now", "continue"], consumable_loss: float = 0.0) -> dict:
        if not math.isfinite(elapsed_min) or elapsed_min < 0:
            raise ServiceError("INVALID_INPUT", "elapsed_min must be >= 0")
        if not (0 < event.radius_m <= self.max_block_radius_m):
            raise ServiceError("INVALID_INPUT", f"radius_m must be in (0, {self.max_block_radius_m}]")
        if not math.isfinite(consumable_loss) or consumable_loss < 0:
            raise ServiceError("INVALID_INPUT", "consumable_loss_units must be >= 0")
        log = EventLog()
        legs, acts, infos, pol = self._plan(mi, mi.route_choice)
        base = assess(legs, acts, mi.budget)
        if any(l.route is None for l in legs):
            raise ServiceError("BASELINE_INFEASIBLE", "the baseline plan has no complete route; fix the plan before running a contingency", 409)
        stop_act = {s.stop_id: s.activity_min for s in mi.stops}
        timeline = build_timeline(legs, stop_act, mi.profile, mi.budget)
        home = self.cell_of(*mi.habitat_xy, "habitat")
        pos = locate(timeline, legs, elapsed_min, home)
        log.record("ScienceStopReachedSimulated", completed_stops=pos.completed_stop_ids) if pos.completed_stop_ids else None
        if pos.phase == "complete":
            raise ServiceError("MISSION_ALREADY_COMPLETE", "elapsed time is past the end of the planned EVA")

        # Remaining waypoints from the current position (pre-event)
        remaining_stops: list[Stop] = []
        remaining_activity_here = 0.0
        if response_mode == "continue":
            done = set(pos.completed_stop_ids)
            for s in mi.stops:
                if s.stop_id in done:
                    continue
                if pos.phase == "activity" and s.stop_id == pos.leg_or_stop_id:
                    remaining_activity_here = pos.remaining_activity_min
                    continue
                remaining_stops.append(s)
        elif pos.phase == "activity":
            remaining_activity_here = 0.0  # abort activity immediately
        targets: list[tuple[str, Cell, float]] = [(s.stop_id, self.cell_of(s.x_m, s.y_m, s.stop_id), s.activity_min) for s in remaining_stops] + [("habitat", home, 0.0)]

        def plan_from(mask: TraversalMask, start: Cell, blocked: np.ndarray | None) -> tuple[list[LegResult], list[ActivityResult], dict]:
            out_legs: list[LegResult] = []
            out_acts: list[ActivityResult] = []
            inf: dict[str, dict] = {}
            cur, cur_id = start, "current-position"
            if remaining_activity_here > 0:
                out_acts.append(ActivityResult(pos.leg_or_stop_id + " (remaining)", remaining_activity_here, remaining_activity_here * mi.budget.consumable_rate_activity_per_min))
            for tid, cell, act in targets:
                leg_id = f"replan:{cur_id}->{tid}"
                if cell == cur:
                    cur_id = tid
                    continue
                route, reasons, info = self._route(mask, pol, cur, cell, leg_id, blocked)
                inf[leg_id] = info
                if route is None:
                    out_legs.append(LegResult(leg_id, cur_id, tid, None, math.inf, math.inf, tuple(reasons)))
                    break
                mins, cons = leg_cost(route, mi.profile, mi.budget)
                out_legs.append(LegResult(leg_id, cur_id, tid, route, mins, cons))
                if act > 0:
                    out_acts.append(ActivityResult(tid, act, act * mi.budget.consumable_rate_activity_per_min))
                cur, cur_id = cell, tid
            return out_legs, out_acts, inf

        base_mask = build_mask(self.grid, pol)
        pre_legs, pre_acts, _ = plan_from(base_mask, pos.cell, None)
        pre_cells = [c for l in pre_legs if l.route for c in l.route.cells]

        # Place the simulated blocked zone
        if event.center_xy is not None:
            center = event.center_xy
            self.cell_of(*center, "event center")
            placement = "user-specified"
        else:
            if len(pre_cells) < 2:
                raise ServiceError("NO_REMAINING_ROUTE", "no remaining path to place an event on")
            center = point_along(pre_cells, self.grid, event.position_fraction)
            placement = f"auto: {event.position_fraction:.2f} of the remaining pre-event path length"
        zone = BlockedZone(center[0], center[1], event.radius_m)
        blocked = zone.mask(self.grid)
        if blocked[pos.cell]:
            raise ServiceError("EVENT_COVERS_CREW", "the simulated blocked zone covers the crew's current position; move it or shrink it")
        affects = any(blocked[c] for c in pre_cells)
        log.record("ContingencyInjected", type="BLOCKED_ZONE", center_xy_m=[round(center[0], 1), round(center[1], 1)], radius_m=event.radius_m, affects_previous_route=affects, consumable_loss_units=consumable_loss)

        scen_mask = build_mask(self.grid, pol, blocked)
        new_legs, new_acts, new_infos = plan_from(scen_mask, pos.cell, blocked)
        used_cons = pos.consumed + consumable_loss
        new = assess(new_legs, new_acts, mi.budget, already_used_min=pos.elapsed_min, already_used_consumable=used_cons)
        pre = assess(pre_legs, pre_acts, mi.budget, already_used_min=pos.elapsed_min, already_used_consumable=used_cons)
        if new.status.value == "INFEASIBLE":
            log.record("MissionMarkedInfeasible", reasons=new.reasons)
        else:
            log.record("RouteReplanned", status=new.status.value)

        cx, cy = self.grid.cell_center_xy(*pos.cell)
        return {
            "baseline_status": base.status.value,
            "current_position": {"x_m": round(cx, 1), "y_m": round(cy, 1), "elapsed_min": _r(pos.elapsed_min, 1), "requested_elapsed_min": elapsed_min,
                                 "phase": pos.phase, "segment": pos.leg_or_stop_id, "completed_stops": pos.completed_stop_ids,
                                 "consumed_units": _r(pos.consumed, 1), "consumable_loss_units": consumable_loss,
                                 "snapping": "Position snaps back to the last fully completed 20 m step; elapsed time and consumption are taken at that instant."},
            "event": {"type": "BLOCKED_ZONE", "evidence_level": "SIMULATED_EVENT", "center_xy_m": [round(center[0], 1), round(center[1], 1)], "radius_m": event.radius_m,
                      "placement": placement, "blocked_cells": int(blocked.sum()), "affects_previous_route": affects},
            "response_mode": response_mode,
            "before": self._remaining_dto(pre, pre_legs, mi),
            "after": self._remaining_dto(new, new_legs, mi, new_infos),
            "status_change": f"{pre.status.value} -> {new.status.value}",
            "events": log.to_list(),
            "run_manifest": self.run_manifest(mi, extra={"elapsed_min": elapsed_min, "event": {"radius_m": event.radius_m, "center_xy": center}, "response_mode": response_mode, "consumable_loss": consumable_loss}),
        }

    def _remaining_dto(self, a: FeasibilityAssessment, legs: list[LegResult], mi: MissionInput, infos: dict | None = None) -> dict:
        d = self.assessment_dto(a, mi, infos)
        d["remaining_length_m"] = _r(sum(l.route.metrics.length_m for l in legs if l.route), 1) if all(l.route for l in legs) else None
        return d

    # ------------------------------------------------------------------ manifest / report
    def run_manifest(self, mi: MissionInput, extra: dict | None = None) -> dict:
        params = {
            "habitat_xy_m": mi.habitat_xy, "stops": [s.__dict__ for s in mi.stops], "route_choice": mi.route_choice,
            "profile": mi.profile.__dict__, "budget": mi.budget.__dict__, "slope_weight": mi.slope_weight, "unknown_policy": mi.unknown_policy, **(extra or {}),
        }
        blob = json.dumps(params, sort_keys=True, default=str)
        return {"code_version": self.code_version, "study_area_id": self.repo.manifest["study_area_id"], "dem_crop_sha256": self.repo.dem_sha256,
                "data_processing_version": self.repo.manifest["processing_version"], "parameters": json.loads(blob), "parameters_sha256": hashlib.sha256(blob.encode()).hexdigest(),
                "deterministic": True, "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
