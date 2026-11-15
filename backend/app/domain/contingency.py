"""Scenario / Contingency context.

A `ContingencyScenario` applies explicitly SIMULATED changes to a copy of the terrain masks; the
authoritative DEM is never modified, and simulated hazards are never reported as observations.
`MissionTimeline` turns a computed plan into an ordered list of steps so a simulated "current
position" can be derived from elapsed mission time, with consumption already spent accounted for.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .mission import LegResult, ResourceBudget, TraversalProfile
from .navigation import Cell
from .terrain import TerrainGrid


@dataclass(frozen=True)
class BlockedZone:
    """Circular simulated blocked zone (e.g. a reported hazard closing a corridor)."""

    center_x_m: float
    center_y_m: float
    radius_m: float

    def mask(self, grid: TerrainGrid) -> np.ndarray:
        if not (math.isfinite(self.radius_m) and self.radius_m > 0):
            raise ValueError("radius_m must be > 0")
        rows = np.arange(grid.height)
        cols = np.arange(grid.width)
        cx = (cols + 0.5) * grid.res_m
        cy = (grid.height - rows - 0.5) * grid.res_m
        k = np.cos(np.radians(grid.lat_row_deg))[:, None]  # projected E-W metres -> ground metres
        dx = (cx[None, :] - self.center_x_m) * k
        dy = cy[:, None] - self.center_y_m
        return (dx * dx + dy * dy) <= self.radius_m * self.radius_m


@dataclass(frozen=True)
class TimelineStep:
    kind: str  # "traverse" | "activity"
    leg_or_stop_id: str
    cell: Cell  # cell reached at the END of this step (activity: the stop cell)
    start_min: float
    end_min: float
    consumable_start: float
    consumable_end: float


@dataclass
class MissionPosition:
    elapsed_min: float
    consumed: float
    cell: Cell
    phase: str  # "traverse" | "activity" | "complete" | "not_started"
    leg_or_stop_id: str
    completed_stop_ids: list[str] = field(default_factory=list)
    remaining_activity_min: float = 0.0


def build_timeline(legs: list[LegResult], stop_activity: dict[str, float], profile: TraversalProfile, budget: ResourceBudget) -> list[TimelineStep]:
    steps: list[TimelineStep] = []
    t = 0.0
    c = 0.0
    for leg in legs:
        if leg.route is None:
            break
        cells = leg.route.cells
        for i, (L, dz) in enumerate(zip(leg.route.step_lengths_m, leg.route.step_dz_m)):
            m = profile.step_minutes(L, dz)
            steps.append(TimelineStep("traverse", leg.leg_id, cells[i + 1], t, t + m, c, c + m * budget.consumable_rate_traverse_per_min))
            t += m
            c += m * budget.consumable_rate_traverse_per_min
        act = stop_activity.get(leg.to_id, 0.0)
        if act > 0:
            steps.append(TimelineStep("activity", leg.to_id, cells[-1], t, t + act, c, c + act * budget.consumable_rate_activity_per_min))
            t += act
            c += act * budget.consumable_rate_activity_per_min
    return steps


def locate(timeline: list[TimelineStep], legs: list[LegResult], elapsed_min: float, start_cell: Cell) -> MissionPosition:
    """Snap elapsed time to the last fully completed traverse step (conservative) or a point
    inside an activity. Consumption is the timeline value at that snapped instant."""
    if elapsed_min <= 0 or not timeline:
        return MissionPosition(0.0, 0.0, start_cell, "not_started", legs[0].leg_id if legs else "")
    completed: list[str] = []
    last_cell, last_t, last_c, last_id = start_cell, 0.0, 0.0, legs[0].leg_id
    for st in timeline:
        if st.kind == "activity":
            if elapsed_min < st.end_min:
                if elapsed_min <= st.start_min:
                    return MissionPosition(st.start_min, st.consumable_start, st.cell, "activity", st.leg_or_stop_id, completed, st.end_min - st.start_min)
                frac = (elapsed_min - st.start_min) / (st.end_min - st.start_min)
                cons = st.consumable_start + frac * (st.consumable_end - st.consumable_start)
                return MissionPosition(elapsed_min, cons, st.cell, "activity", st.leg_or_stop_id, completed, st.end_min - elapsed_min)
            completed.append(st.leg_or_stop_id)
            last_cell, last_t, last_c, last_id = st.cell, st.end_min, st.consumable_end, st.leg_or_stop_id
            continue
        if st.end_min > elapsed_min:
            return MissionPosition(last_t, last_c, last_cell, "traverse", st.leg_or_stop_id, completed)
        last_cell, last_t, last_c, last_id = st.cell, st.end_min, st.consumable_end, st.leg_or_stop_id
    return MissionPosition(last_t, last_c, last_cell, "complete", last_id, completed)


def point_along(cells: list[Cell], grid: TerrainGrid, fraction: float) -> tuple[float, float]:
    """Local x/y of the cell at `fraction` of the path's ground length."""
    if not cells:
        raise ValueError("empty path")
    fraction = min(max(fraction, 0.0), 1.0)
    lens = [grid.step_length_m(*a, *b) for a, b in zip(cells, cells[1:])]
    total = sum(lens)
    target = total * fraction
    acc = 0.0
    for i, L in enumerate(lens):
        if acc + L >= target:
            return grid.cell_center_xy(*cells[i + 1])
        acc += L
    return grid.cell_center_xy(*cells[-1])
