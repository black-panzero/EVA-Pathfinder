import math

import numpy as np
import pytest
from app.domain.navigation import RoutePolicy, build_mask, diagnose_no_route, find_path, measure_route, validate_route
from app.domain.terrain import TerrainGrid

POL = RoutePolicy("shortest", max_slope_deg=15.0)


def rng_terrain(seed: int, shape=(35, 45)) -> TerrainGrid:
    rng = np.random.default_rng(seed)
    z = rng.normal(0, 1, shape).cumsum(axis=0).cumsum(axis=1) * 0.8  # rough but smooth-ish synthetic relief
    return TerrainGrid.synthetic(z, res_m=20.0, lat_deg=18.4)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("w", [0.0, 3.0])
def test_astar_matches_dijkstra_optimal_cost(seed, w):
    g = rng_terrain(seed)
    pol = RoutePolicy("p", max_slope_deg=25.0, slope_weight=w)
    mask = build_mask(g, pol)
    free = np.argwhere(mask.passable)
    a, b = tuple(free[0]), tuple(free[-1])
    astar = find_path(g, mask, pol, a, b)
    dij = find_path(g, mask, pol, a, b, use_heuristic=False)
    assert (astar.cells is None) == (dij.cells is None)
    if astar.cells:
        assert astar.cost == pytest.approx(dij.cost, rel=1e-9)
        assert astar.expanded <= dij.expanded
        assert validate_route(mask, astar.cells) == []


def test_wall_with_gap_forces_path_through_gap(flat_grid):
    blocked = np.zeros((flat_grid.height, flat_grid.width), bool)
    blocked[:, 30] = True
    blocked[35, 30] = False  # single gap
    mask = build_mask(flat_grid, POL, scenario_blocked=blocked)
    res = find_path(flat_grid, mask, POL, (5, 5), (5, 55))
    assert res.cells is not None
    assert (35, 30) in res.cells
    assert not any(blocked[c] for c in res.cells)


def test_full_wall_gives_no_route_and_diagnosis(flat_grid):
    blocked = np.zeros((flat_grid.height, flat_grid.width), bool)
    blocked[:, 30] = True
    mask = build_mask(flat_grid, POL, scenario_blocked=blocked)
    res = find_path(flat_grid, mask, POL, (5, 5), (5, 55))
    assert res.cells is None and res.reason == "NO_ROUTE"
    reasons = diagnose_no_route(flat_grid, POL, (5, 5), (5, 55), blocked, None)
    assert "NO_ROUTE" in reasons and "BLOCKED_BY_SCENARIO_EVENT" in reasons


def test_no_diagonal_corner_cutting():
    g = TerrainGrid.synthetic(np.zeros((3, 3)))
    blocked = np.zeros((3, 3), bool)
    blocked[0, 1] = blocked[1, 0] = True  # two orthogonal blockers around the diagonal (0,0)->(1,1)
    mask = build_mask(g, POL, scenario_blocked=blocked)
    res = find_path(g, mask, POL, (0, 0), (1, 1))
    assert res.cells is None  # the only exit is a diagonal squeeze, which is forbidden


def test_slope_limit_is_hard():
    # ridge of steep cells across the grid with a gentle saddle
    z = np.zeros((30, 40))
    z[:24, 20] = 200.0  # tall narrow ridge -> steep cells in columns 19-21, open in the south
    g = TerrainGrid.synthetic(z)
    mask = build_mask(g, POL)
    res = find_path(g, mask, POL, (5, 5), (5, 35))
    assert res.cells is not None
    assert all(g.slope_deg[c] <= POL.max_slope_deg for c in res.cells)
    assert max(r for r, _ in res.cells) >= 24  # detoured through the flat corridor


def test_unknown_blocked_by_default_and_penalize_reports_fraction(flat_grid):
    z = flat_grid.elevation_m.copy()
    z[:, 28:33] = np.nan  # data gap band
    g = TerrainGrid.synthetic(z)
    m_block = build_mask(g, POL)
    assert find_path(g, m_block, POL, (5, 5), (5, 55)).cells is None
    assert "UNMAPPED_TERRAIN" in diagnose_no_route(g, POL, (5, 5), (5, 55), None, None)
    pen = RoutePolicy("pen", max_slope_deg=15.0, unknown_policy="penalize", unknown_weight=1.0)
    m_pen = build_mask(g, pen)
    res = find_path(g, m_pen, pen, (5, 5), (5, 55))
    route = measure_route(g, m_pen, pen, res.cells, res.cost, "r")
    assert route.metrics.unknown_length_fraction > 0


def test_metrics_straight_line_and_cost_floor(flat_grid):
    mask = build_mask(flat_grid, POL)
    res = find_path(flat_grid, mask, POL, (10, 5), (10, 25))
    route = measure_route(flat_grid, mask, POL, res.cells, res.cost, "r")
    assert route.metrics.length_m == pytest.approx(20 * 20.0, rel=1e-6)
    assert route.metrics.elevation_gain_m == 0
    assert res.cost >= route.metrics.length_m - 1e-9  # every step cost >= its length


def test_elevation_gain_loss_symmetry():
    cols = np.arange(40) * 20.0
    z = np.tile(cols * 0.05, (10, 1))
    g = TerrainGrid.synthetic(z)
    mask = build_mask(g, POL)
    out = find_path(g, mask, POL, (5, 2), (5, 37))
    back = find_path(g, mask, POL, (5, 37), (5, 2))
    r1 = measure_route(g, mask, POL, out.cells, out.cost, "o")
    r2 = measure_route(g, mask, POL, back.cells, back.cost, "b")
    assert r1.metrics.elevation_gain_m == pytest.approx(r2.metrics.elevation_loss_m)
    assert r1.metrics.elevation_gain_m == pytest.approx(35 * 20.0 * 0.05)


def test_policy_rejects_negative_weights():
    with pytest.raises(ValueError):
        RoutePolicy("bad", max_slope_deg=15, slope_weight=-1)
    with pytest.raises(ValueError):
        RoutePolicy("bad", max_slope_deg=math.inf)


def test_deterministic(flat_grid):
    mask = build_mask(flat_grid, POL)
    a = find_path(flat_grid, mask, POL, (3, 3), (36, 56)).cells
    b = find_path(flat_grid, mask, POL, (3, 3), (36, 56)).cells
    assert a == b
