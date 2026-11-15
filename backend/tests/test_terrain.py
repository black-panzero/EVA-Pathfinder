import math

import numpy as np
import pytest
from app.domain.terrain import TerrainError, TerrainGrid, compute_slope_deg


def test_slope_of_tilted_plane_matches_analytic():
    # z rises 10 m per 100 m eastwards -> slope atan(0.1) = 5.7106 deg (at equator, dx = res)
    cols = np.arange(30) * 20.0
    z = np.tile(cols * 0.1, (20, 1))
    g = TerrainGrid.synthetic(z, res_m=20.0, lat_deg=0.0)
    interior = g.slope_deg[2:-2, 2:-2]
    assert np.allclose(interior, math.degrees(math.atan(0.1)), atol=1e-3)


def test_slope_uses_ground_metres_east_west_at_latitude():
    # same projected-metre gradient at 60 deg latitude: ground dx is res*cos(60)=10 m -> grade doubles
    cols = np.arange(30) * 20.0
    z = np.tile(cols * 0.1, (20, 1))
    g = TerrainGrid.synthetic(z, res_m=20.0, lat_deg=60.0)
    mid = g.slope_deg[10, 15]
    expected = math.degrees(math.atan(2.0 / (20.0 * math.cos(math.radians(g.lat_row_deg[10])))))
    assert mid == pytest.approx(expected, rel=1e-6)


def test_north_south_slope_unscaled():
    rows = np.arange(20)[:, None] * 20.0
    z = np.tile(rows * 0.2, (1, 30))
    g = TerrainGrid.synthetic(z, res_m=20.0, lat_deg=45.0)
    assert g.slope_deg[10, 10] == pytest.approx(math.degrees(math.atan(0.2)), rel=1e-9)


def test_nodata_propagates_to_slope():
    z = np.zeros((10, 10))
    z[5, 5] = np.nan
    s = compute_slope_deg(z, np.full(10, 20.0), 20.0)
    assert np.isnan(s[5, 5]) and np.isnan(s[5, 4]) and np.isnan(s[4, 5])
    assert np.isfinite(s[0, 0])


def test_xy_cell_roundtrip_and_bounds(flat_grid):
    for r, c in [(0, 0), (39, 59), (17, 23)]:
        x, y = flat_grid.cell_center_xy(r, c)
        assert flat_grid.xy_to_cell(x, y) == (r, c)
    with pytest.raises(TerrainError) as e:
        flat_grid.xy_to_cell(-1, 5)
    assert e.value.code == "OUT_OF_BOUNDS"
    with pytest.raises(TerrainError) as e:
        flat_grid.xy_to_cell(float("nan"), 5)
    assert e.value.code == "INVALID_COORDINATE"


def test_step_length_ground_metres():
    g = TerrainGrid.synthetic(np.zeros((5, 5)), res_m=20.0, lat_deg=60.0)
    assert g.step_length_m(2, 2, 2, 3) == pytest.approx(20.0 * math.cos(math.radians(g.lat_row_deg[2])))
    assert g.step_length_m(2, 2, 3, 2) == pytest.approx(20.0)
