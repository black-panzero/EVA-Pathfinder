"""Pydantic v2 request schemas (API boundary). Finite, bounded numbers only."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class ReportRequest(Strict):
    mission: MissionRequest
    replan: ReplanRequest | None = None
