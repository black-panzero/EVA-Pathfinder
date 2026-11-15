"""API + real-DEM smoke tests. Skipped (not faked) when the real study area is not prepared."""
import json

import pytest
from fastapi.testclient import TestClient

from .conftest import PROCESSED, requires_real_data

pytestmark = requires_real_data


@pytest.fixture(scope="module")
def client():
    from app.api.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def default_req(client):
    return client.get("/api/v1/missions/default").json()["request"]


def test_health_reports_real_data(client):
    h = client.get("/health").json()
    assert h["data_ready"] is True and h["grid"] == [405, 225]


def test_manifest_real_data_gate():
    m = json.loads((PROCESSED / "manifest.json").read_text())
    dem = next(a for a in m["artifacts"] if a["artifact_id"] == "dem-crop")
    assert dem["checksum_sha256"] and len(dem["checksum_sha256"]) == 64
    assert m["source_status"]["usgs-m2020-trn-ctx-dtm-20m"]["status"] == "AVAILABLE_VERIFIED"
    assert m["dem_stats"]["valid_fraction"] > 0.99
    assert -2700 < m["dem_stats"]["min_m"] < m["dem_stats"]["max_m"] < -2300  # Jezero floor/delta elevations
    assert "Mars" in m["crs"]["wkt"]


def test_alignment_gate():
    m = json.loads((PROCESSED / "manifest.json").read_text())
    al = m["alignment"]
    assert max(abs(v) for v in al["ortho_dem_grid_origin_difference_m"]) < 1.0
    ev = al["dem_vs_rover_elevation"]
    assert ev["n"] > 50 and abs(ev["median_dem_minus_rover_m"]) < 5.0 and ev["median_abs_m"] < 5.0


def test_datasets_and_layers(client):
    d = client.get("/api/v1/datasets").json()
    st = {x["source_id"]: x["verification_status"] for x in d["datasets"]}
    assert st["usgs-m2020-trn-ctx-dtm-20m"] == "AVAILABLE_VERIFIED"
    assert st["usgs-sim3464-geology"] == "PARTIAL"
    sa = client.get("/api/v1/study-area").json()
    assert {l["layer_id"] for l in sa["layers"]} >= {"ortho", "slope", "geology", "elevation"}
    r = client.get("/api/v1/layers/ortho/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get("/api/v1/layers/../../etc/passwd/image").status_code == 404


def test_observations_are_geolocated_and_sourced(client):
    o = client.get("/api/v1/observations").json()
    assert o["photos"], "expected at least one geolocated rover photo"
    for p in o["photos"]:
        assert p["source_url"].startswith("https://mars.nasa.gov/")
        assert "site" in p["geolocation"] and "drive" in p["geolocation"]
        assert client.get(p["image_url"]).status_code == 200
    assert o["atmosphere"]["series"][0]["unit"] == "Pa"


def test_evaluate_default_mission(client, default_req):
    r = client.post("/api/v1/missions/evaluate", json=default_req)
    assert r.status_code == 200
    a = r.json()["assessment"]
    assert a["status"] in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")
    for leg in a["legs"]:
        m = leg["route"]["metrics"]
        assert m["length_m"] > 0 and m["max_derived_slope_deg"] <= default_req["profile"]["max_slope_deg"] + 1e-6
    assert r.json()["run_manifest"]["dem_crop_sha256"]


def test_compare_routes_real_dem(client, default_req):
    body = {"origin": default_req["habitat"], "goal": default_req["stops"][0]["point"], "max_slope_deg": 15, "slope_weight": 3}
    out = client.post("/api/v1/routes/compare", json=body).json()
    ids = {r["route_id"]: r for r in out["routes"]}
    assert set(ids) == {"shortest", "terrain"}
    assert ids["shortest"]["metrics"]["length_m"] <= ids["terrain"]["metrics"]["length_m"] + 1e-6


def test_deterministic_replan(client, default_req):
    body = {"mission": default_req, "elapsed_min": 200, "event": {"radius_m": 250}, "response_mode": "return_now"}
    a = client.post("/api/v1/scenarios/replan", json=body).json()
    b = client.post("/api/v1/scenarios/replan", json=body).json()
    assert a["after"]["legs"][0]["route"]["polyline_xy_m"] == b["after"]["legs"][0]["route"]["polyline_xy_m"]
    assert a["event"]["affects_previous_route"] is True


def test_reserve_monotonic_real_dem(client, default_req):
    statuses = []
    for r in [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 0.95]:
        req = json.loads(json.dumps(default_req))
        req["budget"]["reserve_fraction"] = r
        statuses.append(client.post("/api/v1/missions/evaluate", json=req).json()["assessment"]["status"])
    first_bad = statuses.index("INFEASIBLE") if "INFEASIBLE" in statuses else len(statuses)
    assert all(s == "INFEASIBLE" for s in statuses[first_bad:])


@pytest.mark.parametrize("patch", [
    {"habitat": {"x_m": -5, "y_m": 10}},
    {"habitat": {"x_m": 99999, "y_m": 10}},
    {"budget": {"time_available_min": -1, "consumable_initial_units": 1, "consumable_rate_traverse_per_min": 1, "consumable_rate_activity_per_min": 1, "reserve_fraction": 0.2}},
    {"budget": {"time_available_min": 100, "consumable_initial_units": 1, "consumable_rate_traverse_per_min": 1, "consumable_rate_activity_per_min": 1, "reserve_fraction": 1.0}},
    {"unexpected": 1},
])
def test_invalid_inputs_rejected(client, default_req, patch):
    req = {**default_req, **patch}
    r = client.post("/api/v1/missions/evaluate", json=req)
    assert r.status_code == 422


def test_nan_rejected(client, default_req):
    raw = json.dumps(default_req).replace('"reserve_fraction": 0.25', '"reserve_fraction": NaN')
    r = client.post("/api/v1/missions/evaluate", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_report_contains_provenance(client, default_req):
    r = client.post("/api/v1/reports", json={"mission": default_req}).json()
    assert r["provenance"]["sources"] and r["mission_evaluation"]["assessment"]["status"]
    assert "not certified" in r["disclaimer"].lower()
