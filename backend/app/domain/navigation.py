"""Navigation context (Pathfinder): grid routing, route geometry and metrics.

Cost model for a directed step i -> j between 8-connected neighbours:
    cost = length_m * (1 + w_s * normalized_slope + w_u * unknown)
    normalized_slope = max(slope_i, slope_j) / max_slope_deg      (in [0, 1] for passable cells)
    unknown          = 1 if either cell is unknown (only when unknown_policy == "penalize") else 0
All weights are non-negative, so every step costs at least its horizontal ground length and the
octile ground-distance heuristic is admissible and consistent: A* returns least-cost paths.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from .terrain import TerrainGrid

Cell = tuple[int, int]
NEIGHBOURS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))


@dataclass(frozen=True)
class RoutePolicy:
    policy_id: str
    max_slope_deg: float
    slope_weight: float = 0.0
    unknown_policy: Literal["block", "penalize"] = "block"
    unknown_weight: float = 0.0

    def __post_init__(self) -> None:
        for name in ("max_slope_deg", "slope_weight", "unknown_weight"):
            v = getattr(self, name)
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if self.max_slope_deg <= 0 or self.max_slope_deg > 60:
            raise ValueError("max_slope_deg must be in (0, 60]")


@dataclass(frozen=True)
class TraversalMask:
    """Per-cell traversability for one (grid, policy, scenario) combination."""

    passable: np.ndarray  # bool
    unknown: np.ndarray  # bool: no elevation / slope, or scenario data gap
    blocked_by_slope: np.ndarray  # bool
    blocked_by_scenario: np.ndarray  # bool


def build_mask(grid: TerrainGrid, policy: RoutePolicy, scenario_blocked: np.ndarray | None = None, scenario_unknown: np.ndarray | None = None) -> TraversalMask:
    unknown = ~np.isfinite(grid.slope_deg) | ~np.isfinite(grid.elevation_m)
    if scenario_unknown is not None:
        unknown = unknown | scenario_unknown
    steep = np.isfinite(grid.slope_deg) & (grid.slope_deg > policy.max_slope_deg) & ~unknown
    blocked = scenario_blocked if scenario_blocked is not None else np.zeros_like(unknown)
    passable = ~steep & ~blocked
    if policy.unknown_policy == "block":
        passable &= ~unknown
    return TraversalMask(passable=passable, unknown=unknown, blocked_by_slope=steep, blocked_by_scenario=blocked.copy())


@dataclass
class SearchResult:
    cells: list[Cell] | None
    cost: float
    expanded: int
    reason: str | None = None


def _octile(dr: int, dc: int, dx_min: float, dy: float, diag: float) -> float:
    n_d = min(dr, dc)
    return n_d * diag + (dc - n_d) * dx_min + (dr - n_d) * dy


def find_path(grid: TerrainGrid, mask: TraversalMask, policy: RoutePolicy, start: Cell, goal: Cell, use_heuristic: bool = True) -> SearchResult:
    """8-neighbour A* (or Dijkstra when use_heuristic=False) with no diagonal corner cutting."""
    for name, cell in (("start", start), ("goal", goal)):
        if not grid.in_bounds(*cell):
            return SearchResult(None, math.inf, 0, f"{name.upper()}_OUT_OF_BOUNDS")
        if not mask.passable[cell]:
            return SearchResult(None, math.inf, 0, f"{name.upper()}_IMPASSABLE")
    H, W = grid.height, grid.width
    passable = mask.passable.ravel().tolist()
    unknown = mask.unknown.ravel().tolist()
    slope = np.nan_to_num(grid.slope_deg, nan=0.0).ravel().tolist()
    dx_row = grid.dx_row_m.tolist()
    dy = grid.dy_m
    dx_min = float(grid.dx_row_m.min())
    diag_min = math.hypot(dx_min, dy)
    inv_max = 1.0 / policy.max_slope_deg
    ws, wu = policy.slope_weight, policy.unknown_weight if policy.unknown_policy == "penalize" else 0.0
    s = start[0] * W + start[1]
    g_idx = goal[0] * W + goal[1]
    gr, gc = goal
    g_cost = {s: 0.0}
    parent: dict[int, int] = {}
    closed: set[int] = set()
    h0 = _octile(abs(start[0] - gr), abs(start[1] - gc), dx_min, dy, diag_min) if use_heuristic else 0.0
    heap = [(h0, 0.0, s)]
    expanded = 0
    while heap:
        _f, g, u = heapq.heappop(heap)
        if u in closed:
            continue
        if u == g_idx:
            break
        closed.add(u)
        expanded += 1
        ur, uc = divmod(u, W)
        for dr, dc in NEIGHBOURS:
            vr, vc = ur + dr, uc + dc
            if vr < 0 or vr >= H or vc < 0 or vc >= W:
                continue
            v = vr * W + vc
            if not passable[v] or v in closed:
                continue
            if dr and dc and not (passable[ur * W + vc] and passable[vr * W + uc]):
                continue  # no corner cutting past an impassable cell
            if dr and dc:
                length = math.hypot(0.5 * (dx_row[ur] + dx_row[vr]), dy)
            elif dc:
                length = dx_row[ur]
            else:
                length = dy
            pen = ws * max(slope[u], slope[v]) * inv_max
            if wu and (unknown[u] or unknown[v]):
                pen += wu
            ng = g + length * (1.0 + pen)
            if ng < g_cost.get(v, math.inf):
                g_cost[v] = ng
                parent[v] = u
                h = _octile(abs(vr - gr), abs(vc - gc), dx_min, dy, diag_min) if use_heuristic else 0.0
                heapq.heappush(heap, (ng + h, ng, v))
    if g_idx not in g_cost:
        return SearchResult(None, math.inf, expanded, "NO_ROUTE")
    path = [g_idx]
    while path[-1] != s:
        path.append(parent[path[-1]])
    path.reverse()
    return SearchResult([divmod(i, W) for i in path], g_cost[g_idx], expanded)


@dataclass(frozen=True)
class ProfileSample:
    distance_m: float
    elevation_m: float | None
    slope_deg: float | None
    x_m: float
    y_m: float


@dataclass(frozen=True)
class RouteMetrics:
    length_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_derived_slope_deg: float
    mean_derived_slope_deg: float
    max_step_grade_deg: float
    unknown_length_fraction: float
    cell_count: int
    policy_cost: float


@dataclass
class Route:
    route_id: str
    policy: RoutePolicy
    cells: list[Cell]
    metrics: RouteMetrics
    profile: list[ProfileSample] = field(default_factory=list)
    step_lengths_m: list[float] = field(default_factory=list)
    step_dz_m: list[float] = field(default_factory=list)

    def polyline_xy(self, grid: TerrainGrid) -> list[tuple[float, float]]:
        return [grid.cell_center_xy(r, c) for r, c in self.cells]


def measure_route(grid: TerrainGrid, mask: TraversalMask, policy: RoutePolicy, cells: list[Cell], cost: float, route_id: str) -> Route:
    z = grid.elevation_m
    sl = grid.slope_deg
    lengths, dzs = [], []
    gain = loss = 0.0
    unknown_len = 0.0
    max_grade = 0.0
    dist = 0.0
    x0, y0 = grid.cell_center_xy(*cells[0])
    prof = [ProfileSample(0.0, _f(z[cells[0]]), _f(sl[cells[0]]), x0, y0)]
    for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
        L = grid.step_length_m(r0, c0, r1, c1)
        dz = float(z[r1, c1] - z[r0, c0]) if np.isfinite(z[r1, c1]) and np.isfinite(z[r0, c0]) else 0.0
        lengths.append(L)
        dzs.append(dz)
        gain += max(dz, 0.0)
        loss += max(-dz, 0.0)
        if mask.unknown[r0, c0] or mask.unknown[r1, c1]:
            unknown_len += L
        if L > 0:
            max_grade = max(max_grade, math.degrees(math.atan(abs(dz) / L)))
        dist += L
        x, y = grid.cell_center_xy(r1, c1)
        prof.append(ProfileSample(dist, _f(z[r1, c1]), _f(sl[r1, c1]), x, y))
    slopes = [sl[c] for c in cells if np.isfinite(sl[c])]
    metrics = RouteMetrics(
        length_m=dist, elevation_gain_m=gain, elevation_loss_m=loss,
        max_derived_slope_deg=float(max(slopes)) if slopes else float("nan"),
        mean_derived_slope_deg=float(np.mean(slopes)) if slopes else float("nan"),
        max_step_grade_deg=max_grade, unknown_length_fraction=(unknown_len / dist) if dist > 0 else 0.0,
        cell_count=len(cells), policy_cost=cost,
    )
    return Route(route_id, policy, cells, metrics, prof, lengths, dzs)


def validate_route(mask: TraversalMask, cells: list[Cell]) -> list[str]:
    """Independent post-check: every cell passable, every step 8-adjacent, no corner cutting."""
    problems = []
    for i, c in enumerate(cells):
        if not mask.passable[c]:
            problems.append(f"cell {i} {c} is not passable")
    for i, (a, b) in enumerate(zip(cells, cells[1:])):
        dr, dc = b[0] - a[0], b[1] - a[1]
        if max(abs(dr), abs(dc)) != 1:
            problems.append(f"step {i} is not 8-adjacent")
        elif dr and dc and not (mask.passable[a[0], b[1]] and mask.passable[b[0], a[1]]):
            problems.append(f"step {i} cuts a blocked corner")
    return problems


def _f(v: float) -> float | None:
    return float(v) if np.isfinite(v) else None


def diagnose_no_route(grid: TerrainGrid, policy: RoutePolicy, start: Cell, goal: Cell, scenario_blocked: np.ndarray | None, scenario_unknown: np.ndarray | None) -> list[str]:
    """Explain a failed search by relaxing one constraint at a time (deterministic)."""
    reasons = ["NO_ROUTE"]
    relaxed_slope = RoutePolicy(policy.policy_id + "-relaxed", max_slope_deg=60.0, slope_weight=0.0, unknown_policy=policy.unknown_policy)
    m = build_mask(grid, relaxed_slope, scenario_blocked, scenario_unknown)
    if find_path(grid, m, relaxed_slope, start, goal).cells is not None:
        reasons.append("SLOPE_EXCEEDS_LIMIT")
    if policy.unknown_policy == "block":
        relaxed_unknown = RoutePolicy(policy.policy_id + "-unknown", max_slope_deg=policy.max_slope_deg, unknown_policy="penalize", unknown_weight=0.0)
        m2 = build_mask(grid, relaxed_unknown, scenario_blocked, scenario_unknown)
        if find_path(grid, m2, relaxed_unknown, start, goal).cells is not None:
            reasons.append("UNMAPPED_TERRAIN")
    if scenario_blocked is not None and scenario_blocked.any():
        m3 = build_mask(grid, policy, None, scenario_unknown)
        if find_path(grid, m3, policy, start, goal).cells is not None:
            reasons.append("BLOCKED_BY_SCENARIO_EVENT")
    return reasons
