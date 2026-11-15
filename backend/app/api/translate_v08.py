"""Translate 08-contract request shapes (and the handoff mission template) into the existing
service inputs. Framework-free: used by the FastAPI server and the Pyodide bridge.

Resolution rules (documented contract behaviour):
- `dataset_id` may be the 08 alias (`ctx_dem_jezero_trn_2020`) or our source id; any other known
  source is rejected with UNALIGNED_SOURCE (not a routable DEM), unknown ids with SOURCE_UNAVAILABLE.
- `crs_id` (top level or on a map point) must equal the active map-contract crs_id, else CRS_MISMATCH.
- `{row, col}` grid cells are validated in bounds and against nodata (NO_DATA_COVERAGE).
- Values the 08 shape does not carry (ascent rate, slope weight, max slope) default to
  config/mission_defaults.json and every defaulted value is listed in `assumptions`.
- Replan `mission_id`: there is no mission store. An inline `mission` (any accepted mission shape)
  wins; otherwise a known default id (or no id) resolves to the config default mission
  (GET /api/v1/missions/default). Any other id is rejected (INVALID_MISSION_CONFIGURATION).
"""
from __future__ import annotations

from typing import Any

from ..application.contracts import DEM_SOURCE_ID, resolve_dataset_id
from ..application.services import EventInput, MissionInput, MissionService, PositionOverride, ServiceError, Stop
from ..domain.mission import ResourceBudget, TraversalProfile
from ..domain.terrain import TerrainError
from ..domain.values import MapGridCell, MapPoint
from .schemas import (
    BlockageEventIn,
    GridCellIn,
    MapPointIn,
    MissionConfigRequest,
    MissionContractRequest,
    MissionRequest,
    ReplanContractRequest,
    RouteCompareContractRequest,
    ScienceStopContractIn,
)

# Mirror of config/mission_defaults.json used only when the config file is not available
# (e.g. inside the Pyodide static build). A test asserts it matches the config file.
FALLBACK_DEFAULTS: dict[str, Any] = {
    "mission_name": "Operation Delta Return",
    "traversal_profile": {"profile_id": "illustrative-walk-naismith", "flat_speed_m_per_min": 40.0, "ascent_rate_m_per_min": 10.0, "max_slope_deg": 15.0},
    "budgets": {"time_available_min": 420.0, "consumable_initial_units": 500.0, "consumable_rate_traverse_per_min": 1.0,
                "consumable_rate_activity_per_min": 0.6, "reserve_fraction": 0.25, "consumable_label": "Illustrative consumable (generic units)"},
    "route_policies": {"shortest": {"policy_id": "shortest-feasible", "slope_weight": 0.0, "unknown_policy": "block", "unknown_weight": 0.0},
                       "terrain": {"policy_id": "terrain-aware", "slope_weight": 3.0, "unknown_policy": "block", "unknown_weight": 0.0}},
    "limits": {"max_stops": 3, "max_block_radius_m": 1000.0, "max_time_available_min": 1440.0},
}
DEFAULT_MISSION_IDS = frozenset({"operation-delta-return", "delta-return-01", "default"})
POLICY_TO_CHOICE = {"MIN_DISTANCE": "shortest", "TERRAIN_WEIGHTED": "terrain"}
CONFIG_BASIS = "default from config/mission_defaults.json (not supplied in the request)"


def _d(defaults: dict | None) -> dict:
    return defaults or FALLBACK_DEFAULTS


def _err(exc: TerrainError, what: str) -> ServiceError:
    msg = str(exc)
    return ServiceError(exc.code, msg if msg.startswith(f"{what}:") else f"{what}: {msg}")


# --------------------------------------------------------------------------- validation
def check_dataset(svc: MissionService, dataset_id: str | None) -> None:
    if dataset_id is None:
        return
    sid = resolve_dataset_id(dataset_id)
    if sid == svc.grid.dataset_id:
        return
    known = {s.get("source_id") for s in svc.repo.manifest.get("sources", [])}
    if sid in known and sid != DEM_SOURCE_ID:
        raise ServiceError("UNALIGNED_SOURCE", f"dataset '{dataset_id}' is not the routable DEM grid of this study area ({svc.grid.dataset_id})")
    raise ServiceError("SOURCE_UNAVAILABLE", f"dataset '{dataset_id}' is not loaded (active DEM: {svc.grid.dataset_id})", 404)


def check_crs(svc: MissionService, crs_id: str | None, what: str = "request") -> None:
    if crs_id is not None:
        try:
            MapPoint(0.0, 0.0, crs_id).require_crs(svc.crs_id)
        except TerrainError as exc:
            raise _err(exc, what) from exc


def location_xy(svc: MissionService, loc: GridCellIn | MapPointIn, what: str) -> tuple[float, float]:
    g = svc.grid
    try:
        if isinstance(loc, GridCellIn):
            return g.cell_center_xy(*MapGridCell(loc.row, loc.col).validate(g, what))
        check_crs(svc, loc.crs_id, what)
        r, c = svc.cell_of(loc.x_m, loc.y_m, what)
        MapGridCell(r, c).validate(g, what)  # nodata check
        return loc.x_m, loc.y_m
    except TerrainError as exc:
        raise _err(exc, what) from exc


def _stop_xy(svc: MissionService, s: ScienceStopContractIn) -> tuple[float, float]:
    if s.map_point is not None:
        return location_xy(svc, s.map_point, s.id)
    if s.row is not None and s.col is not None:
        return location_xy(svc, GridCellIn(row=s.row, col=s.col), s.id)
    assert s.x_m is not None and s.y_m is not None
    return location_xy(svc, MapPointIn(x_m=s.x_m, y_m=s.y_m, crs_id=s.crs_id), s.id)


# --------------------------------------------------------------------------- compare
def compare(svc: MissionService, req: RouteCompareContractRequest, defaults: dict | None = None) -> dict:
    d = _d(defaults)
    tp = d["traversal_profile"]
    check_dataset(svc, req.dataset_id)
    check_crs(svc, req.crs_id)
    a = location_xy(svc, req.origin, "origin")
    b = location_xy(svc, req.destination, "destination")
    assumptions: list[dict] = []
    max_slope = req.max_derived_slope_deg
    if max_slope is None:
        max_slope = tp["max_slope_deg"]
        assumptions.append({"item": "max_derived_slope_deg", "value": max_slope, "unit": "deg", "basis": CONFIG_BASIS})
    if req.traversal is not None:
        ascent = req.traversal.ascent_rate_m_per_min
        if ascent is None:
            ascent = tp["ascent_rate_m_per_min"]
            assumptions.append({"item": "ascent_rate_m_per_min", "value": ascent, "unit": "m/min", "basis": CONFIG_BASIS})
        speed = req.traversal.assumed_speed_m_per_min
    else:
        speed, ascent = tp["flat_speed_m_per_min"], tp["ascent_rate_m_per_min"]
        assumptions += [{"item": "assumed_speed_m_per_min", "value": speed, "unit": "m/min", "basis": CONFIG_BASIS + "; used only for model_minutes"},
                        {"item": "ascent_rate_m_per_min", "value": ascent, "unit": "m/min", "basis": CONFIG_BASIS + "; used only for model_minutes"}]
    if req.unknown_policy == "BLOCK" and req.weights.uncertainty > 0:
        assumptions.append({"item": "weights.uncertainty", "value": req.weights.uncertainty, "unit": None, "basis": "ignored: unknown_policy BLOCK excludes unknown cells"})
    try:
        prof = TraversalProfile("contract-illustrative", speed, ascent, max_slope)
    except ValueError as exc:
        raise ServiceError("INVALID_INPUT", str(exc)) from exc
    only = tuple(POLICY_TO_CHOICE[p] for p in req.policies)
    out = svc.compare_routes(a, b, max_slope, req.weights.slope, prof, req.unknown_policy.lower(), req.weights.uncertainty, only)
    out["requested_policies"] = list(req.policies)
    out["assumptions"] = assumptions
    out["request_shape"] = "08"
    return out


# --------------------------------------------------------------------------- missions
def config_to_contract(cfg: MissionConfigRequest) -> MissionContractRequest:
    """Handoff template (config/mission.delta-return.example.json) -> 08 evaluate request."""
    if cfg.origin is None or not cfg.science_stops:
        raise ServiceError("INVALID_MISSION_CONFIGURATION",
                           f"mission '{cfg.mission_id}' is a template (status {cfg.status}): set origin and at least one science stop from verified sites first")
    c = cfg.illustrative_consumable
    stops = []
    for s in cfg.science_stops:
        data = s.model_dump(exclude_none=True)
        data["activity_minutes"] = s.activity_minutes if s.activity_minutes is not None else cfg.activity_duration_min_assumed
        stops.append(ScienceStopContractIn.model_validate(data))
    traversal: dict[str, Any] = {"assumed_speed_m_per_min": cfg.speed_m_per_min_assumed, "consumable_name": c.name, "consumption_rate_per_min": c.rate_units_per_min_assumed}
    if cfg.ascent_rate_m_per_min_assumed is not None:
        traversal["ascent_rate_m_per_min"] = cfg.ascent_rate_m_per_min_assumed
    return MissionContractRequest.model_validate({
        "mission_id": cfg.mission_id, "dataset_id": cfg.dataset_id, "crs_id": cfg.crs_id,
        "origin": cfg.origin.model_dump(exclude_none=True), "science_stops": [s.model_dump(exclude_none=True) for s in stops],
        "traversal": traversal,
        "budget": {"max_minutes": cfg.max_duration_min_assumed, "initial_consumable_units": c.initial_units, "reserve_fraction": c.minimum_reserve_fraction},
        "terrain_policy": {"max_derived_slope_deg": cfg.max_derived_slope_deg_assumed, "unknown_policy": "BLOCK" if cfg.uncertainty_policy == "BLOCK_MISSING_DEM" else "PENALIZE"},
    })


def config_assumptions(cfg: MissionConfigRequest) -> list[dict]:
    out: list[dict] = [{"item": "crew_count_simulated", "value": cfg.crew_count_simulated, "unit": "persons", "basis": "SIMULATED: recorded only; the model does not scale with crew size"},
           {"item": "travel_mode", "value": cfg.travel_mode, "unit": None, "basis": "SIMULATED"}]
    if any(s.activity_minutes is None for s in cfg.science_stops):
        out.append({"item": "activity_minutes", "value": cfg.activity_duration_min_assumed, "unit": "min", "basis": "activity_duration_min_assumed from the mission template"})
    return out


def to_mission(svc: MissionService, req: MissionContractRequest, defaults: dict | None = None) -> tuple[MissionInput, list[dict]]:
    d = _d(defaults)
    tp = d["traversal_profile"]
    check_dataset(svc, req.dataset_id)
    check_crs(svc, req.crs_id)
    assumptions: list[dict] = []
    habitat = location_xy(svc, req.origin, "origin")
    stops = tuple(Stop(s.id, s.name or s.id, *_stop_xy(svc, s), s.activity_minutes) for s in req.science_stops)
    t, tpol = req.traversal, req.terrain_policy
    ascent = t.ascent_rate_m_per_min
    if ascent is None:
        ascent = tp["ascent_rate_m_per_min"]
        assumptions.append({"item": "ascent_rate_m_per_min", "value": ascent, "unit": "m/min", "basis": CONFIG_BASIS})
    max_slope = tpol.max_derived_slope_deg
    if max_slope is None:
        max_slope = tp["max_slope_deg"]
        assumptions.append({"item": "max_derived_slope_deg", "value": max_slope, "unit": "deg", "basis": CONFIG_BASIS})
    slope_w = tpol.slope_weight
    if slope_w is None:
        slope_w = d["route_policies"]["terrain"]["slope_weight"]
        assumptions.append({"item": "slope_weight", "value": slope_w, "unit": None, "basis": CONFIG_BASIS})
    act_rate = t.activity_consumption_rate_per_min
    if act_rate is None:
        act_rate = t.consumption_rate_per_min
        assumptions.append({"item": "activity_consumable_rate_per_min", "value": act_rate, "unit": f"{t.consumable_name}/min",
                            "basis": "08 single consumption_rate_per_min applied to both travel and activity"})
    try:
        mi = MissionInput(
            habitat_xy=habitat, stops=stops, route_choice=POLICY_TO_CHOICE[req.policy],  # type: ignore[arg-type]
            profile=TraversalProfile("contract-illustrative", t.assumed_speed_m_per_min, ascent, max_slope),
            budget=ResourceBudget(req.budget.max_minutes, req.budget.initial_consumable_units, t.consumption_rate_per_min, act_rate, req.budget.reserve_fraction, consumable_label=t.consumable_name),
            slope_weight=slope_w, unknown_policy=tpol.unknown_policy.lower(), unknown_weight=tpol.uncertainty_weight,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise ServiceError("INVALID_INPUT", str(exc)) from exc
    return mi, assumptions


def merge_contract_meta(out: dict, assumptions: list[dict], mission_id: str | None, shape: str) -> dict:
    out["assumptions"] = list(out.get("assumptions", [])) + assumptions
    out["mission_id"] = mission_id
    out["request_shape"] = shape
    return out


# --------------------------------------------------------------------------- replan
def default_mission_request(defaults: dict, science: dict | None) -> dict | None:
    """Legacy MissionRequest payload of the config default mission (also served by GET /missions/default)."""
    if not science or not science.get("sites"):
        return None
    tp, b = defaults["traversal_profile"], defaults["budgets"]
    return {
        "habitat": {"x_m": science["habitat"]["x_m"], "y_m": science["habitat"]["y_m"]},
        "stops": [{"stop_id": s["id"], "name": s["name"], "point": {"x_m": s["x_m"], "y_m": s["y_m"]}, "activity_min": s["default_activity_min"]} for s in science["sites"][:1]],
        "route_choice": "terrain",
        "profile": {"flat_speed_m_per_min": tp["flat_speed_m_per_min"], "ascent_rate_m_per_min": tp["ascent_rate_m_per_min"], "max_slope_deg": tp["max_slope_deg"]},
        "budget": {k: b[k] for k in ("time_available_min", "consumable_initial_units", "consumable_rate_traverse_per_min", "consumable_rate_activity_per_min", "reserve_fraction")},
        "slope_weight": defaults["route_policies"]["terrain"]["slope_weight"], "unknown_policy": "block", "unknown_weight": 0.0,
    }


def resolve_mission(svc: MissionService, req: ReplanContractRequest, defaults: dict | None, default_mission: dict | None,
                    legacy_to_mission: Any) -> tuple[MissionInput, list[dict], str]:
    """Returns (mission, assumptions, how it was resolved)."""
    m = req.mission
    if m is not None:
        if isinstance(m, MissionRequest):
            return legacy_to_mission(m), [], "inline mission (legacy shape)"
        if isinstance(m, MissionConfigRequest):
            mi, a = to_mission(svc, config_to_contract(m), defaults)
            return mi, config_assumptions(m) + a, "inline mission (handoff template)"
        mi, a = to_mission(svc, m, defaults)
        return mi, a, "inline mission (08 shape)"
    if req.mission_id is not None and req.mission_id not in DEFAULT_MISSION_IDS:
        raise ServiceError("UNKNOWN_MISSION", f"mission_id '{req.mission_id}' is not stored (no mission store); send the mission inline as 'mission' "
                                              f"or use one of {sorted(DEFAULT_MISSION_IDS)} for the config default mission")
    if default_mission is None:
        raise ServiceError("UNKNOWN_MISSION", "config default mission unavailable here; send the mission inline as 'mission'")
    return legacy_to_mission(MissionRequest.model_validate(default_mission)), [
        {"item": "mission", "value": req.mission_id or "default", "unit": None, "basis": "resolved to the config default mission (GET /api/v1/missions/default); no mission store"}
    ], "config default mission"


def replan(svc: MissionService, req: ReplanContractRequest, defaults: dict | None, default_mission: dict | None, legacy_to_mission: Any) -> dict:
    check_crs(svc, req.crs_id)
    mi, assumptions, how = resolve_mission(svc, req, defaults, default_mission, legacy_to_mission)
    g = svc.grid
    position = None
    if req.current_grid_cell is not None:
        try:
            cell = MapGridCell(req.current_grid_cell.row, req.current_grid_cell.col).validate(g, "current_grid_cell")
        except TerrainError as exc:
            raise _err(exc, "current_grid_cell") from exc
        assert req.already_elapsed_minutes is not None and req.already_used_consumable_units is not None
        known = {s.stop_id for s in mi.stops}
        bad = [s for s in req.completed_stop_ids if s not in known]
        if bad:
            raise ServiceError("INVALID_INPUT", f"completed_stop_ids not in mission: {bad}")
        position = PositionOverride(cell, req.already_elapsed_minutes, req.already_used_consumable_units, tuple(req.completed_stop_ids))
    ev = req.event
    if isinstance(ev, BlockageEventIn):
        cells = []
        for bc in ev.blocked_cells:
            if not g.in_bounds(bc.row, bc.col):
                raise ServiceError("OUT_OF_BOUNDS", f"event: blocked cell ({bc.row}, {bc.col}) is outside the {g.height}x{g.width} grid")
            cells.append((bc.row, bc.col))
        event = EventInput(0.0, None, 0.5, "SIMULATED_BLOCKAGE", tuple(cells))
    else:
        center = location_xy(svc, ev.center, "event center") if ev.center is not None else None
        event = EventInput(ev.radius_m, center, ev.position_fraction)
    elapsed = req.already_elapsed_minutes or 0.0
    out = svc.replan(mi, elapsed, event, req.response_mode.lower(), req.consumable_loss_units, position, req.scenario_id)  # type: ignore[arg-type]
    out["mission_resolution"] = how
    return merge_contract_meta(out, assumptions, req.mission_id, "08")
