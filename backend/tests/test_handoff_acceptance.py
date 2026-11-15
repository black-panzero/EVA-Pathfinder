"""Handoff acceptance tests named after the spec IDs in
EVA_Pathfinder_Handoff/06_TESTING_AND_ACCEPTANCE.md.

Synthetic fixtures are clearly labelled synthetic; real-data checks use `requires_real_data`.
"""
import copy
import json
import math
import re

import numpy as np
import pytest
from app.application.services import EventInput, MissionInput, MissionService, Stop
from app.domain.contingency import BlockedZone
from app.domain.mission import ResourceBudget, TraversalProfile
from app.domain.navigation import RoutePolicy, build_mask, find_path, measure_route
from app.domain.terrain import TerrainError, TerrainGrid
from fastapi.testclient import TestClient

from .conftest import PROCESSED, FakeRepo, requires_real_data

PROFILE = TraversalProfile("t", flat_speed_m_per_min=40.0, ascent_rate_m_per_min=10.0, max_slope_deg=15.0)
DEM = PROCESSED / "dem_crop.tif"


def budget(**kw) -> ResourceBudget:
    base = dict(time_available_min=300.0, consumable_initial_units=400.0, consumable_rate_traverse_per_min=1.0, consumable_rate_activity_per_min=0.5, reserve_fraction=0.2)
    base.update(kw)
    return ResourceBudget(**base)


def make_service(z: np.ndarray | None = None) -> MissionService:
    grid = TerrainGrid.synthetic(np.zeros((50, 80)) if z is None else z, res_m=20.0, lat_deg=18.4)
    return MissionService(FakeRepo(grid), "test")


def mission(svc: MissionService, b: ResourceBudget | None = None, activity_min: float = 30.0, home_rc=(25, 5), tgt_rc=(25, 70)) -> MissionInput:
    g = svc.grid
    home = g.cell_center_xy(*home_rc)
    tgt = g.cell_center_xy(*tgt_rc)
    return MissionInput(home, (Stop("t1", "Target", tgt[0], tgt[1], activity_min),), "terrain", PROFILE, b or budget(), slope_weight=3.0)


def api_mission_body(n_stops: int = 1) -> dict:
    return {
        "habitat": {"x_m": 100.0, "y_m": 100.0},
        "stops": [{"stop_id": f"s{i}", "name": f"Stop {i}", "point": {"x_m": 300.0 + 40 * i, "y_m": 300.0}, "activity_min": 10.0} for i in range(n_stops)],
        "route_choice": "terrain",
        "profile": {"flat_speed_m_per_min": 40.0, "ascent_rate_m_per_min": 10.0, "max_slope_deg": 15.0},
        "budget": {"time_available_min": 300.0, "consumable_initial_units": 400.0, "consumable_rate_traverse_per_min": 1.0, "consumable_rate_activity_per_min": 0.5, "reserve_fraction": 0.2},
        "slope_weight": 3.0,
    }


@pytest.fixture(scope="module")
def client():
    from app.api.main import app

    return TestClient(app)


# ------------------------------------------------------------------------------------ terrain
def test_T01_flat_dem_zero_slope():
    g = TerrainGrid.synthetic(np.full((10, 10), 5.0))
    assert np.all(np.isfinite(g.slope_deg))
    assert np.allclose(g.slope_deg[1:-1, 1:-1], 0.0, atol=1e-9)
    assert np.allclose(g.slope_deg, 0.0, atol=1e-9)  # one-sided borders also flat


def _write_tif(path, transform, crs):
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", height=8, width=8, count=1, dtype="float32", transform=transform, crs=crs) as dst:
        dst.write(np.zeros((1, 8, 8), dtype="float32"))


@requires_real_data
def test_T05_rotated_affine_rejected(tmp_path):
    import rasterio
    from rasterio.transform import Affine

    with rasterio.open(DEM) as src:
        mars_crs = src.crs
    assert "Mars" in mars_crs.to_wkt()
    p = tmp_path / "rotated.tif"
    _write_tif(p, Affine(20, 5, 0, 0, -20, 0), mars_crs)
    with pytest.raises(TerrainError) as e:
        TerrainGrid.from_geotiff(p, "rotated")
    assert e.value.code == "UNSUPPORTED_PROJECTION"


def test_T07_earth_crs_rejected(tmp_path):
    from rasterio.transform import Affine

    p = tmp_path / "earth.tif"
    _write_tif(p, Affine(20, 0, 0, 0, -20, 0), "EPSG:4326")
    with pytest.raises(TerrainError) as e:
        TerrainGrid.from_geotiff(p, "earth")
    assert e.value.code == "UNSUPPORTED_PROJECTION"


# ------------------------------------------------------------------------------------ routes
def test_R01_open_5x5_shortest_diagonal():
    g = TerrainGrid.synthetic(np.zeros((5, 5)), res_m=20.0, lat_deg=0.0)
    pol = RoutePolicy("shortest", max_slope_deg=15.0)
    mask = build_mask(g, pol)
    res = find_path(g, mask, pol, (0, 0), (4, 4))
    assert res.cells is not None and len(res.cells) == 5
    route = measure_route(g, mask, pol, res.cells, res.cost, "r")
    assert route.metrics.length_m == pytest.approx(4 * math.sqrt(2) * 20.0, rel=1e-9)


def test_R06_identical_policies_reported_as_coincident():
    svc = make_service()
    g = svc.grid
    out = svc.compare_routes(g.cell_center_xy(10, 5), g.cell_center_xy(40, 70), max_slope=15.0, slope_weight=3.0)
    assert {r["route_id"] for r in out["routes"]} == {"shortest", "terrain"}
    assert out["routes_coincide"] is True
    assert out["cell_overlap_jaccard"] == 1.0


# ------------------------------------------------------------------------------------ guardian
def test_G05_activity_duration_never_decreases_total_time():
    svc = make_service()
    t30 = svc.evaluate(mission(svc, activity_min=30.0))["assessment"]["totals"]["minutes"]
    t60 = svc.evaluate(mission(svc, activity_min=60.0))["assessment"]["totals"]["minutes"]
    assert t60 >= t30
    # Tight budget sweep: totals non-decreasing and FEASIBLE -> INFEASIBLE is one-way.
    tight = budget(time_available_min=120.0, consumable_initial_units=1e5, reserve_fraction=0.0)
    totals, statuses = [], []
    for act in [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0]:
        a = svc.evaluate(mission(svc, tight, activity_min=act))["assessment"]
        totals.append(a["totals"]["minutes"])
        statuses.append(a["status"])
    assert totals == sorted(totals)
    assert "FEASIBLE" in statuses and "INFEASIBLE" in statuses
    first_bad = statuses.index("INFEASIBLE")
    assert all(s == "INFEASIBLE" for s in statuses[first_bad:])
    assert all(s == "FEASIBLE" for s in statuses[:first_bad])


def test_G06_replan_starts_at_current_position():
    svc = make_service()
    mi = mission(svc)
    out_min = svc.evaluate(mi)["assessment"]["legs"][0]["minutes"]
    res = svc.replan(mi, elapsed_min=out_min + 30.0 + 7.0, event=EventInput(radius_m=200.0), response_mode="return_now")
    cp = res["current_position"]
    assert cp["phase"] == "traverse"
    first = res["after"]["legs"][0]["route"]["polyline_xy_m"][0]
    assert first[0] == pytest.approx(cp["x_m"], abs=1e-6)
    assert first[1] == pytest.approx(cp["y_m"], abs=1e-6)
    # ... and not the original stop target
    tgt = mi.stops[0]
    assert (first[0], first[1]) != pytest.approx((tgt.x_m, tgt.y_m), abs=1.0)


def test_G07_detour_exceeding_allowance_is_infeasible():
    svc = make_service()
    g = svc.grid
    probe = mission(svc, budget(time_available_min=1440.0, consumable_initial_units=1e6, reserve_fraction=0.0))
    base_total = svc.evaluate(probe)["assessment"]["totals"]["minutes"]
    mi = mission(svc, budget(time_available_min=base_total + 0.5, consumable_initial_units=1e6, reserve_fraction=0.0))
    assert svc.evaluate(mi)["assessment"]["status"] == "FEASIBLE"
    # Large zone across the straight E-W corridor, midway along the outbound leg: any detour
    # around a 300 m radius disc adds hundreds of metres (many minutes at 40 m/min).
    center = g.cell_center_xy(25, 38)
    res = svc.replan(mi, elapsed_min=1.0, event=EventInput(radius_m=300.0, center_xy=center), response_mode="continue")
    assert res["event"]["affects_previous_route"] is True
    assert res["before"]["status"] == "FEASIBLE"
    after = res["after"]
    assert after["remaining_length_m"] > res["before"]["remaining_length_m"] + 100.0
    assert after["status"] == "INFEASIBLE"
    assert "INSUFFICIENT_TIME" in after["reason_codes"]


def test_G08_outbound_blocked_continue_recomputes_via_stop():
    svc = make_service()
    g = svc.grid
    mi = mission(svc)
    center = g.cell_center_xy(25, 38)
    radius = 150.0
    res = svc.replan(mi, elapsed_min=2.0, event=EventInput(radius_m=radius, center_xy=center), response_mode="continue")
    assert res["current_position"]["phase"] == "traverse"
    assert res["event"]["affects_previous_route"] is True
    after = res["after"]
    assert after["status"] in ("FEASIBLE", "UNKNOWN")
    legs = after["legs"]
    assert [leg["to"] for leg in legs] == ["t1", "habitat"]
    assert all(leg["route"] is not None for leg in legs)
    zone = BlockedZone(center[0], center[1], radius).mask(g)
    for leg in legs:
        for x, y in leg["route"]["polyline_xy_m"]:
            assert not zone[g.xy_to_cell(x, y)]
    stop = mi.stops[0]
    assert legs[0]["route"]["polyline_xy_m"][-1] == pytest.approx([stop.x_m, stop.y_m], abs=1e-6)
    assert legs[1]["route"]["polyline_xy_m"][-1] == pytest.approx(list(mi.habitat_xy), abs=1e-6)
    assert "t1" in [a["stop_id"] for a in after["activities"]]
    assert after["remaining_length_m"] > res["before"]["remaining_length_m"]
    # old vs new route and reasons are logged/reported
    names = [e["name"] for e in res["events"]]
    assert "ContingencyInjected" in names and "RouteReplanned" in names
    assert res["before"]["legs"] and res["status_change"]


def test_G09_map_unavailable_never_feasible(client, monkeypatch):
    from app.api import main
    from app.infrastructure.repositories import DataUnavailable

    def broken_repo():
        raise DataUnavailable("simulated: no prepared study area")

    monkeypatch.setattr(main, "repo", broken_repo)
    h = client.get("/health")
    assert h.status_code == 503 and h.json()["data_ready"] is False
    r = client.post("/api/v1/missions/evaluate", json=api_mission_body())
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "DATA_UNAVAILABLE"
    assert "FEASIBLE" not in json.dumps(body)


@pytest.mark.parametrize("event_patch", [{"radius_m": 0}, {"radius_m": -1}, {"radius_m": 5000}, {"radius_m": 100, "position_fraction": 1.5}])
def test_G10_invalid_replan_events_rejected(client, event_patch):
    body = {"mission": api_mission_body(), "elapsed_min": 10.0, "event": event_patch, "response_mode": "return_now"}
    r = client.post("/api/v1/scenarios/replan", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_API_limit_four_stops_rejected(client):
    r = client.post("/api/v1/missions/evaluate", json=api_mission_body(n_stops=4))
    assert r.status_code == 422


# ------------------------------------------------------------------------------------ data
@pytest.fixture(scope="module")
def real_grid():
    return TerrainGrid.from_geotiff(DEM, "real")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((PROCESSED / "manifest.json").read_text())


@requires_real_data
def test_D02_science_sites_inside_grid_and_mars_crs(real_grid, manifest):
    sci = json.loads((PROCESSED / "science_sites.json").read_text())
    assert sci["sites"]
    for s in sci["sites"]:
        r, c = real_grid.xy_to_cell(s["x_m"], s["y_m"])
        assert real_grid.in_bounds(r, c)
        assert np.isfinite(real_grid.elevation_m[r, c])
    assert "Mars" in manifest["crs"]["wkt"]


@requires_real_data
def test_D04_slope_matches_independent_central_difference(real_grid):
    g = real_grid
    z = g.elevation_m
    rng = np.random.default_rng(42)
    checked = 0
    while checked < 5:
        r = int(rng.integers(1, g.height - 1))
        c = int(rng.integers(1, g.width - 1))
        stencil = [z[r, c - 1], z[r, c + 1], z[r - 1, c], z[r + 1, c]]
        if not all(np.isfinite(stencil)):
            continue
        dzdx = (z[r, c + 1] - z[r, c - 1]) / (2.0 * g.dx_row_m[r])
        dzdy = (z[r + 1, c] - z[r - 1, c]) / (2.0 * g.dy_m)
        expected = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
        assert g.slope_deg[r, c] == pytest.approx(expected, abs=1e-6)
        checked += 1


@requires_real_data
def test_D05_manifest_sources_provenance_complete(manifest):
    assert manifest["sources"]
    for s in manifest["sources"]:
        sid = s["source_id"]
        assert str(s.get("url", "")).startswith("https://"), sid
        assert s.get("title"), sid
        assert s.get("license"), sid
        assert s.get("citation"), sid
    for s in manifest["sources"]:
        assert s.get("producer") or s.get("mission"), s["source_id"]


@requires_real_data
def test_D05_manifest_artifacts_provenance_complete(manifest):
    assert manifest["artifacts"]
    for a in manifest["artifacts"]:
        aid = a["artifact_id"]
        assert re.fullmatch(r"[0-9a-f]{64}", a.get("checksum_sha256") or ""), aid
        assert a.get("evidence_level"), aid
        assert a.get("limitations"), aid
        assert a.get("crs"), aid


@requires_real_data
def test_D07_atmosphere_is_historical_not_forecast(client):
    atm = client.get("/api/v1/observations").json()["atmosphere"]
    assert isinstance(atm["sol"], int)
    assert atm["series"] and all(s.get("unit") for s in atm["series"])
    scope = atm["scope"].lower()
    assert "not a forecast" in scope or "historical" in scope
    assert atm["evidence_level"] == "NASA_OBSERVATION"


@requires_real_data
def test_D08_unavailable_source_never_reported_verified(client, monkeypatch):
    from app.api import main

    r = main.repo()
    patched = copy.deepcopy(r.manifest)
    for st in patched["source_status"].values():
        st["status"] = "UNAVAILABLE"
    monkeypatch.setattr(r, "manifest", patched)
    d = client.get("/api/v1/datasets").json()
    assert d["datasets"]
    for ds in d["datasets"]:
        assert ds["verification_status"] == "UNAVAILABLE", ds["source_id"]
    # Missing status entry is also not reported as available
    del patched["source_status"]["usgs-m2020-trn-ctx-dtm-20m"]
    d = client.get("/api/v1/datasets").json()
    st = {x["source_id"]: x["verification_status"] for x in d["datasets"]}
    assert st["usgs-m2020-trn-ctx-dtm-20m"] == "UNAVAILABLE"
