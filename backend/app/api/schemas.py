"""Pydantic v2 request schemas (API boundary). Finite, bounded numbers only."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PointIn(Strict):
    x_m: float = Field(ge=0, le=100_000, description="Local x (projected metres east of study-area west edge)")
    y_m: float = Field(ge=0, le=100_000, description="Local y (projected metres north of study-area south edge)")


class ProfileIn(Strict):
    flat_speed_m_per_min: float = Field(gt=0, le=500)
    ascent_rate_m_per_min: float = Field(gt=0, le=200)
    max_slope_deg: float = Field(gt=0, le=60)


class BudgetIn(Strict):
    time_available_min: float = Field(ge=0, le=1440)
    consumable_initial_units: float = Field(ge=0, le=1e6)
    consumable_rate_traverse_per_min: float = Field(ge=0, le=1e4)
    consumable_rate_activity_per_min: float = Field(ge=0, le=1e4)
    reserve_fraction: float = Field(ge=0, lt=1)


class StopIn(Strict):
    stop_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=120)
    point: PointIn
    activity_min: float = Field(ge=0, le=600)


class RouteCompareRequest(Strict):
    origin: PointIn
    goal: PointIn
    max_slope_deg: float = Field(15.0, gt=0, le=60)
    slope_weight: float = Field(3.0, ge=0, le=100)
    profile: ProfileIn | None = None


class MissionRequest(Strict):
    habitat: PointIn
    stops: list[StopIn] = Field(min_length=1, max_length=3)
    route_choice: Literal["shortest", "terrain"] = "terrain"
    profile: ProfileIn
    budget: BudgetIn
    slope_weight: float = Field(3.0, ge=0, le=100)
    unknown_policy: Literal["block", "penalize"] = "block"
    unknown_weight: float = Field(0.0, ge=0, le=100)


class EventIn(Strict):
    type: Literal["BLOCKED_ZONE"] = "BLOCKED_ZONE"
    radius_m: float = Field(gt=0, le=1000)
    center: PointIn | None = None
    position_fraction: float = Field(0.5, ge=0, le=1)


class ReplanRequest(Strict):
    mission: MissionRequest
    elapsed_min: float = Field(ge=0, le=1440)
    event: EventIn
    response_mode: Literal["return_now", "continue"] = "return_now"
    consumable_loss_units: float = Field(0.0, ge=0, le=1e6)


# =============================================================================================
# 08 contract request shapes (EVA_Pathfinder_Handoff/08_DOMAIN_AND_API_CONTRACTS.md section 3).
# Accepted in ADDITION to the legacy shapes above; a key-based discriminator picks the model.
# =============================================================================================
ID_PATTERN = r"^[A-Za-z0-9_.:-]+$"


class GridCellIn(Strict):
    """08 `MapGridCell`: row/col on the active grid (bounds and nodata checked against the grid)."""

    row: int = Field(ge=0, le=100_000)
    col: int = Field(ge=0, le=100_000)


class MapPointIn(Strict):
    """08 `MapPoint`: local map metres; when crs_id is given it must equal the active map contract crs_id."""

    x_m: float = Field(ge=0, le=100_000)
    y_m: float = Field(ge=0, le=100_000)
    crs_id: str | None = Field(None, max_length=200)


Location = GridCellIn | MapPointIn


class WeightsIn(Strict):
    slope: float = Field(3.0, ge=0, le=100)
    uncertainty: float = Field(0.0, ge=0, le=100)


ContractPolicy = Literal["MIN_DISTANCE", "TERRAIN_WEIGHTED"]
UnknownPolicy = Literal["BLOCK", "PENALIZE"]


class TraversalIn(Strict):
    assumed_speed_m_per_min: float = Field(gt=0, le=500)
    consumable_name: str = Field("Illustrative consumable (generic units)", min_length=1, max_length=120)
    consumption_rate_per_min: float = Field(ge=0, le=1e4, description="Single rate: applied to both travel and activity unless activity_consumption_rate_per_min is set")
    activity_consumption_rate_per_min: float | None = Field(None, ge=0, le=1e4)
    ascent_rate_m_per_min: float | None = Field(None, gt=0, le=200, description="Missing -> config/mission_defaults.json default (recorded in assumptions)")


class RouteCompareContractRequest(Strict):
    dataset_id: str | None = Field(None, max_length=120)
    crs_id: str | None = Field(None, max_length=200)
    origin: Location
    destination: Location
    max_derived_slope_deg: float | None = Field(None, gt=0, le=60)
    unknown_policy: UnknownPolicy = "BLOCK"
    policies: list[ContractPolicy] = Field(["MIN_DISTANCE", "TERRAIN_WEIGHTED"], min_length=1, max_length=2)
    weights: WeightsIn = Field(default_factory=lambda: WeightsIn.model_validate({}))
    traversal: TraversalIn | None = None


class BudgetContractIn(Strict):
    max_minutes: float = Field(ge=0, le=1440)
    initial_consumable_units: float = Field(ge=0, le=1e6)
    reserve_fraction: float = Field(ge=0, lt=1)


class TerrainPolicyIn(Strict):
    max_derived_slope_deg: float | None = Field(None, gt=0, le=60)
    unknown_policy: UnknownPolicy = "BLOCK"
    slope_weight: float | None = Field(None, ge=0, le=100)
    uncertainty_weight: float = Field(0.0, ge=0, le=100)


class ScienceStopContractIn(Strict):
    id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    name: str | None = Field(None, min_length=1, max_length=120)
    row: int | None = Field(None, ge=0, le=100_000)
    col: int | None = Field(None, ge=0, le=100_000)
    x_m: float | None = Field(None, ge=0, le=100_000)
    y_m: float | None = Field(None, ge=0, le=100_000)
    map_point: MapPointIn | None = None
    crs_id: str | None = Field(None, max_length=200)
    activity_minutes: float = Field(ge=0, le=600)

    @model_validator(mode="after")
    def _one_location(self) -> ScienceStopContractIn:
        forms = [self.row is not None or self.col is not None, self.x_m is not None or self.y_m is not None, self.map_point is not None]
        if sum(forms) != 1:
            raise ValueError("science stop needs exactly one location: {row, col}, {x_m, y_m} or map_point")
        if forms[0] and (self.row is None or self.col is None):
            raise ValueError("science stop needs both row and col")
        if forms[1] and (self.x_m is None or self.y_m is None):
            raise ValueError("science stop needs both x_m and y_m")
        return self


class MissionContractRequest(Strict):
    mission_id: str | None = Field(None, min_length=1, max_length=64, pattern=ID_PATTERN)
    dataset_id: str | None = Field(None, max_length=120)
    crs_id: str | None = Field(None, max_length=200)
    origin: Location
    science_stops: list[ScienceStopContractIn] = Field(min_length=1, max_length=3)
    traversal: TraversalIn
    budget: BudgetContractIn
    terrain_policy: TerrainPolicyIn = Field(default_factory=lambda: TerrainPolicyIn.model_validate({}))
    policy: ContractPolicy = "TERRAIN_WEIGHTED"


class ScienceStopConfigIn(ScienceStopContractIn):
    activity_minutes: float | None = Field(None, ge=0, le=600)  # type: ignore[assignment]  # None -> activity_duration_min_assumed


class ConsumableConfigIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    initial_units: float = Field(ge=0, le=1e6)
    rate_units_per_min_assumed: float = Field(ge=0, le=1e4)
    minimum_reserve_fraction: float = Field(ge=0, lt=1)


class MissionConfigRequest(Strict):
    """config/mission.delta-return.example.json (handoff template), once origin/stops are filled in."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, populate_by_name=True)

    comment: str | None = Field(None, alias="$comment", max_length=2000)
    mission_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    title: str | None = Field(None, max_length=200)
    status: str | None = Field(None, max_length=64)
    target_body: Literal["Mars"] = "Mars"
    region: str | None = Field(None, max_length=300)
    dataset_id: str | None = Field(None, max_length=120)
    crs_id: str | None = Field(None, max_length=200)
    origin: Location | None
    science_stops: list[ScienceStopConfigIn] = Field(max_length=3)
    crew_count_simulated: int = Field(2, ge=1, le=10)
    travel_mode: Literal["WALKING_SIMULATED"] = "WALKING_SIMULATED"
    speed_m_per_min_assumed: float = Field(gt=0, le=500)
    ascent_rate_m_per_min_assumed: float | None = Field(None, gt=0, le=200)
    max_derived_slope_deg_assumed: float = Field(gt=0, le=60)
    max_duration_min_assumed: float = Field(ge=0, le=1440)
    activity_duration_min_assumed: float = Field(ge=0, le=600)
    illustrative_consumable: ConsumableConfigIn
    uncertainty_policy: Literal["BLOCK_MISSING_DEM", "PENALIZE_MISSING_DEM"] = "BLOCK_MISSING_DEM"
    notes: list[str] = Field(default_factory=list, max_length=50)


class BlockageEventIn(Strict):
    kind: Literal["SIMULATED_BLOCKAGE"]
    blocked_cells: list[GridCellIn] = Field(min_length=1, max_length=5000)


class BlockedZoneContractIn(Strict):
    kind: Literal["BLOCKED_ZONE"]
    radius_m: float = Field(gt=0, le=1000)
    center: MapPointIn | GridCellIn | None = None
    position_fraction: float = Field(0.5, ge=0, le=1)


def _mission_kind(v: Any) -> str:
    if isinstance(v, dict):
        if "illustrative_consumable" in v or "speed_m_per_min_assumed" in v:
            return "mission_config"
        if "science_stops" in v or ("origin" in v and "habitat" not in v):
            return "v08"
    elif isinstance(v, MissionConfigRequest):
        return "mission_config"
    elif isinstance(v, MissionContractRequest):
        return "v08"
    return "legacy"


MissionBody = Annotated[
    Annotated[MissionRequest, Tag("legacy")] | Annotated[MissionContractRequest, Tag("v08")] | Annotated[MissionConfigRequest, Tag("mission_config")],
    Discriminator(_mission_kind),
]


class ReplanContractRequest(Strict):
    mission_id: str | None = Field(None, min_length=1, max_length=64, pattern=ID_PATTERN)
    mission: MissionBody | None = Field(None, description="Inline mission (any accepted mission shape). If absent, mission_id resolves to the config default mission.")
    scenario_id: str | None = Field(None, min_length=1, max_length=64, pattern=ID_PATTERN)
    crs_id: str | None = Field(None, max_length=200)
    current_grid_cell: GridCellIn | None = None
    already_elapsed_minutes: float | None = Field(None, ge=0, le=1440)
    already_used_consumable_units: float | None = Field(None, ge=0, le=1e6)
    completed_stop_ids: list[str] = Field(default_factory=list, max_length=3)
    event: Annotated[BlockageEventIn | BlockedZoneContractIn, Field(discriminator="kind")]
    response_mode: Literal["return_now", "continue", "RETURN_NOW", "CONTINUE"] = "return_now"
    consumable_loss_units: float = Field(0.0, ge=0, le=1e6)

    @model_validator(mode="after")
    def _position_complete(self) -> ReplanContractRequest:
        if self.already_elapsed_minutes is None:
            raise ValueError("already_elapsed_minutes is required")
        if (self.current_grid_cell is None) != (self.already_used_consumable_units is None):
            raise ValueError("current_grid_cell and already_used_consumable_units must be given together "
                             "(omit both to derive the simulated position from the planned timeline)")
        return self


def _compare_kind(v: Any) -> str:
    if isinstance(v, dict):
        return "v08" if ("destination" in v or "policies" in v or "dataset_id" in v) and "goal" not in v else "legacy"
    return "v08" if isinstance(v, RouteCompareContractRequest) else "legacy"


def _replan_kind(v: Any) -> str:
    if isinstance(v, dict):
        legacy = "elapsed_min" in v or ("mission" in v and isinstance(v.get("event"), dict) and "kind" not in v["event"])
        return "legacy" if legacy else "v08"
    return "v08" if isinstance(v, ReplanContractRequest) else "legacy"


RouteCompareBody = Annotated[
    Annotated[RouteCompareRequest, Tag("legacy")] | Annotated[RouteCompareContractRequest, Tag("v08")],
    Discriminator(_compare_kind),
]
ReplanBody = Annotated[
    Annotated[ReplanRequest, Tag("legacy")] | Annotated[ReplanContractRequest, Tag("v08")],
    Discriminator(_replan_kind),
]


class ReportRequest(Strict):
    mission: MissionBody
    replan: ReplanBody | None = None
