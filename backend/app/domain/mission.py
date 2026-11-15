"""Mission Operations context (Guardian): itinerary, budgets, reserves and feasibility.

The resource model is an ILLUSTRATIVE SCENARIO model: every rate is a user-supplied input.
    leg time    = horizontal_length / flat_speed + ascent / ascent_rate   (Naismith-style, directional)
    consumption = traverse_minutes * traverse_rate + activity_minutes * activity_rate
    feasible iff every leg has a route AND total_time <= time_available * (1 - reserve)
                 AND total_consumption <= consumable_initial * (1 - reserve)
Increasing `reserve_fraction` can only shrink the usable budget, so it can never turn an
INFEASIBLE assessment into FEASIBLE with everything else fixed (tested).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .navigation import Route


class FeasibilityStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class ReasonCode(str, Enum):
    NO_ROUTE = "NO_ROUTE"
    SLOPE_EXCEEDS_LIMIT = "SLOPE_EXCEEDS_LIMIT"
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    INSUFFICIENT_CONSUMABLE = "INSUFFICIENT_CONSUMABLE"
    UNMAPPED_TERRAIN = "UNMAPPED_TERRAIN"
    DATA_UNALIGNED = "DATA_UNALIGNED"
    BLOCKED_BY_SCENARIO_EVENT = "BLOCKED_BY_SCENARIO_EVENT"
    START_IMPASSABLE = "START_IMPASSABLE"
    GOAL_IMPASSABLE = "GOAL_IMPASSABLE"


def _check_nonneg(**kw: float) -> None:
    for k, v in kw.items():
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"{k} must be a finite non-negative number")


@dataclass(frozen=True)
class TraversalProfile:
    profile_id: str
    flat_speed_m_per_min: float
    ascent_rate_m_per_min: float
    max_slope_deg: float

    def __post_init__(self) -> None:
        _check_nonneg(flat_speed_m_per_min=self.flat_speed_m_per_min, ascent_rate_m_per_min=self.ascent_rate_m_per_min)
        if self.flat_speed_m_per_min <= 0 or self.ascent_rate_m_per_min <= 0:
            raise ValueError("speeds must be > 0")

    def step_minutes(self, length_m: float, dz_m: float) -> float:
        return length_m / self.flat_speed_m_per_min + max(dz_m, 0.0) / self.ascent_rate_m_per_min


@dataclass(frozen=True)
class ResourceBudget:
    time_available_min: float
    consumable_initial_units: float
    consumable_rate_traverse_per_min: float
    consumable_rate_activity_per_min: float
    reserve_fraction: float
    consumable_label: str = "Illustrative consumable (generic units)"

    def __post_init__(self) -> None:
        _check_nonneg(time_available_min=self.time_available_min, consumable_initial_units=self.consumable_initial_units,
                      consumable_rate_traverse_per_min=self.consumable_rate_traverse_per_min,
                      consumable_rate_activity_per_min=self.consumable_rate_activity_per_min, reserve_fraction=self.reserve_fraction)
        if self.reserve_fraction >= 1:
            raise ValueError("reserve_fraction must be < 1")

    @property
    def usable_time_min(self) -> float:
        return self.time_available_min * (1.0 - self.reserve_fraction)

    @property
    def usable_consumable(self) -> float:
        return self.consumable_initial_units * (1.0 - self.reserve_fraction)


@dataclass(frozen=True)
class LegResult:
    leg_id: str
    from_id: str
    to_id: str
    route: Route | None
    minutes: float
    consumable: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActivityResult:
    stop_id: str
    minutes: float
    consumable: float


@dataclass
class FeasibilityAssessment:
    status: FeasibilityStatus
    reasons: list[str]
    total_minutes: float
    total_consumable: float
    usable_time_min: float
    usable_consumable: float
    time_margin_min: float
    consumable_margin: float
    legs: list[LegResult]
    activities: list[ActivityResult]
    assumptions: list[str] = field(default_factory=list)


def leg_cost(route: Route, profile: TraversalProfile, budget: ResourceBudget) -> tuple[float, float]:
    minutes = sum(profile.step_minutes(L, dz) for L, dz in zip(route.step_lengths_m, route.step_dz_m))
    return minutes, minutes * budget.consumable_rate_traverse_per_min


def assess(legs: list[LegResult], activities: list[ActivityResult], budget: ResourceBudget,
           already_used_min: float = 0.0, already_used_consumable: float = 0.0) -> FeasibilityAssessment:
    reasons: list[str] = []
    for leg in legs:
        for r in leg.reasons:
            if r not in reasons:
                reasons.append(r)
    routes_ok = all(leg.route is not None for leg in legs)
    total_min = already_used_min + sum(leg.minutes for leg in legs) + sum(a.minutes for a in activities)
    total_cons = already_used_consumable + sum(leg.consumable for leg in legs) + sum(a.consumable for a in activities)
    if routes_ok:
        if total_min > budget.usable_time_min + 1e-9:
            reasons.append(ReasonCode.INSUFFICIENT_TIME.value)
        if total_cons > budget.usable_consumable + 1e-9:
            reasons.append(ReasonCode.INSUFFICIENT_CONSUMABLE.value)
    unknown = routes_ok and any(leg.route is not None and leg.route.metrics.unknown_length_fraction > 0 for leg in legs)
    if unknown and ReasonCode.UNMAPPED_TERRAIN.value not in reasons:
        reasons.append(ReasonCode.UNMAPPED_TERRAIN.value)
    hard_fail = (not routes_ok) or ReasonCode.INSUFFICIENT_TIME.value in reasons or ReasonCode.INSUFFICIENT_CONSUMABLE.value in reasons
    status = FeasibilityStatus.INFEASIBLE if hard_fail else (FeasibilityStatus.UNKNOWN if unknown else FeasibilityStatus.FEASIBLE)
    return FeasibilityAssessment(
        status=status, reasons=reasons, total_minutes=total_min if routes_ok else math.inf, total_consumable=total_cons if routes_ok else math.inf,
        usable_time_min=budget.usable_time_min, usable_consumable=budget.usable_consumable,
        time_margin_min=(budget.usable_time_min - total_min) if routes_ok else -math.inf,
        consumable_margin=(budget.usable_consumable - total_cons) if routes_ok else -math.inf,
        legs=legs, activities=activities,
    )
