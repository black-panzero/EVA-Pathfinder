"""Contract vocabulary from EVA_Pathfinder_Handoff/08_DOMAIN_AND_API_CONTRACTS.md (section 2 and 4).

Thin, typed value objects and names layered over the existing engine. They do not replace the
engine types: `TerrainPolicy` IS `RoutePolicy`, `MissionAssessment` IS `FeasibilityAssessment`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from .mission import FeasibilityAssessment, FeasibilityStatus
from .navigation import Cell, RoutePolicy
from .terrain import TerrainError, TerrainGrid

TerrainPolicy = RoutePolicy
"""08 `TerrainPolicy(max_derived_slope_deg, unknown_policy, slope_weight, uncertainty_weight)`.
Field mapping: max_derived_slope_deg -> max_slope_deg, uncertainty_weight -> unknown_weight."""

MissionAssessment = FeasibilityAssessment
"""08 `MissionAssessment(status, reason_codes, time_minutes, consumable_remaining, ...)`."""


class DomainErrorCode(str, Enum):
    """08 section 2 domain error names (exposed as `error.contract_code`)."""

    INVALID_COORDINATES = "INVALID_COORDINATES"
    CRS_MISMATCH = "CRS_MISMATCH"
    NO_DATA_COVERAGE = "NO_DATA_COVERAGE"
    UNALIGNED_SOURCE = "UNALIGNED_SOURCE"
    NO_ROUTE = "NO_ROUTE"
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    INSUFFICIENT_CONSUMABLE = "INSUFFICIENT_CONSUMABLE"
    INVALID_MISSION_CONFIGURATION = "INVALID_MISSION_CONFIGURATION"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class MissionState(str, Enum):
    """08 section 4 simulated mission status machine."""

    PLANNED = "PLANNED"
    ROUTE_EVALUATED = "ROUTE_EVALUATED"
    READY_UNDER_MODEL = "READY_UNDER_MODEL"
    OUTBOUND_SIMULATED = "OUTBOUND_SIMULATED"
    SCIENCE_SIMULATED = "SCIENCE_SIMULATED"
    RETURNING_SIMULATED = "RETURNING_SIMULATED"
    COMPLETED_SIMULATED = "COMPLETED_SIMULATED"
    REPLANNING = "REPLANNING"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


def state_for_status(status: FeasibilityStatus | str) -> MissionState:
    """Terminal state after an evaluation or a replan (08: READY_UNDER_MODEL | INFEASIBLE | UNKNOWN)."""
    s = status.value if isinstance(status, FeasibilityStatus) else status
    return {"FEASIBLE": MissionState.READY_UNDER_MODEL, "INFEASIBLE": MissionState.INFEASIBLE}.get(s, MissionState.UNKNOWN)


class DomainEventName(str, Enum):
    """Names of the domain events recorded in `EventLog` (append-only trace)."""

    MISSION_CONFIGURED = "MissionConfigured"
    ROUTE_COMPUTED = "RouteComputed"
    FEASIBILITY_EVALUATED = "FeasibilityEvaluated"
    MISSION_MARKED_INFEASIBLE = "MissionMarkedInfeasible"
    SCIENCE_STOP_REACHED_SIMULATED = "ScienceStopReachedSimulated"
    CONTINGENCY_INJECTED = "ContingencyInjected"
    ROUTE_REPLANNED = "RouteReplanned"


@dataclass(frozen=True)
class MapGridCell:
    """`MapGridCell(row, col)`: validated inside the grid; nodata cells excluded."""

    row: int
    col: int

    def validate(self, grid: TerrainGrid, what: str = "cell") -> Cell:
        if not grid.in_bounds(self.row, self.col):
            raise TerrainError("OUT_OF_BOUNDS", f"{what}: grid cell ({self.row}, {self.col}) is outside the {grid.height}x{grid.width} grid")
        if not math.isfinite(float(grid.elevation_m[self.row, self.col])):
            raise TerrainError("NO_DATA_COVERAGE", f"{what}: grid cell ({self.row}, {self.col}) has no DEM elevation (nodata)")
        return self.row, self.col

    def to_dict(self) -> dict:
        return {"row": self.row, "col": self.col}


@dataclass(frozen=True)
class MapPoint:
    """`MapPoint(x_m, y_m, crs_id)`: map metres in the body-specific frame; CRS match enforced."""

    x_m: float
    y_m: float
    crs_id: str

    def require_crs(self, expected_crs_id: str) -> MapPoint:
        if self.crs_id != expected_crs_id:
            raise TerrainError("CRS_MISMATCH", f"point CRS '{self.crs_id}' does not match the active dataset CRS '{expected_crs_id}'")
        return self

    def to_dict(self) -> dict:
        return {"x_m": self.x_m, "y_m": self.y_m, "crs_id": self.crs_id}


@dataclass(frozen=True)
class ContingencyEvent:
    """`ContingencyEvent(kind, affected_cells/geometry, current_position, progress, assumptions)`. Scenario only."""

    kind: str  # "SIMULATED_BLOCKAGE" (explicit cells) | "BLOCKED_ZONE" (circle)
    affected_cells: tuple[Cell, ...] = ()
    center_xy_m: tuple[float, float] | None = None
    radius_m: float | None = None
    current_position: Cell | None = None
    elapsed_min: float | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def cells_mask(self, grid: TerrainGrid) -> np.ndarray:
        m = np.zeros((grid.height, grid.width), dtype=bool)
        for r, c in self.affected_cells:
            if not grid.in_bounds(r, c):
                raise TerrainError("OUT_OF_BOUNDS", f"blocked cell ({r}, {c}) is outside the grid")
            m[r, c] = True
        return m
