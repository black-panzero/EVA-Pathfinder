"""Second planning area (crater rim): API area selection, honest results, and browser-engine parity."""
import json
import shutil

import numpy as np
import pytest
from fastapi.testclient import TestClient

from .conftest import ROOT

RIM = "jezero-crater-rim-v1"
RIM_DIR = ROOT / "data" / "processed" / RIM
requires_rim = pytest.mark.skipif(not (RIM_DIR / "manifest.json").exists(), reason="crater-rim area not prepared")
pytestmark = requires_rim


@pytest.fixture(scope="module")
def client():
    from app.api.main import app

    return TestClient(app)


def test_areas_listed_primary_first(client):
    areas = client.get("/api/v1/areas").json()["areas"]
    assert areas[0]["default"] and areas[0]["study_area_id"] == "jezero-delta-return-v1"
    rim = next(a for a in areas if a["study_area_id"] == RIM)
    assert rim["data_ready"] and rim["plannable_sites"] >= 9


def test_area_query_selects_grid_and_sites(client):
    sa = client.get(f"/api/v1/study-area?area={RIM}").json()
    assert sa["study_area_id"] == RIM and sa["grid"]["width"] == 414
    sites = client.get(f"/api/v1/science-sites?area={RIM}").json()["sites"]
    inside = {s["id"] for s in sites if s["in_planning_area"]}
    assert {"bunsen-peak", "cheyava-falls", "singita"} <= inside
    assert "wildcat-ridge" not in inside  # delta site is context here


def test_unknown_area_rejected(client):
    r = client.get("/api/v1/study-area?area=nowhere")
    assert r.status_code == 404 and r.json()["error"]["code"] == "AREA_NOT_FOUND"


def test_rim_default_mission_feasible_and_steep_site_honest(client):
    d = client.get(f"/api/v1/missions/default?area={RIM}").json()["request"]
    assert d["stops"][0]["stop_id"] == "bunsen-peak"
    a = client.post(f"/api/v1/missions/evaluate?area={RIM}", json=d).json()["assessment"]
    assert a["status"] == "FEASIBLE"
    sites = {s["id"]: s for s in client.get(f"/api/v1/science-sites?area={RIM}").json()["sites"]}
    ch = sites["cheyava-falls"]
    d15 = {**d, "stops": [{"stop_id": ch["id"], "name": ch["name"], "point": {"x_m": ch["x_m"], "y_m": ch["y_m"]}, "activity_min": 45}]}
    a15 = client.post(f"/api/v1/missions/evaluate?area={RIM}", json=d15).json()["assessment"]
    assert a15["status"] == "INFEASIBLE" and "SLOPE_EXCEEDS_LIMIT" in a15["reason_codes"]  # the site cell itself is >15 deg
    d20 = {**d15, "profile": {**d15["profile"], "max_slope_deg": 20}}
    assert client.post(f"/api/v1/missions/evaluate?area={RIM}", json=d20).json()["assessment"]["status"] == "FEASIBLE"


def test_default_area_unchanged_without_query(client):
    d = client.get("/api/v1/missions/default").json()["request"]
    assert d["stops"][0]["stop_id"] == "wildcat-ridge"


def test_bridge_parity_rim(tmp_path):
    from app import static_bridge
    from app.api.main import _repo_for, app

    r = _repo_for(RIM)
    np.save(tmp_path / "dem_crop.npy", r.grid.elevation_m.astype("float32"))
    for n in ("geology_units.npy", "geology_units.json", "manifest.json", "science_sites.json"):
        shutil.copy2(RIM_DIR / n, tmp_path / n)
    assert json.loads(static_bridge.init(str(tmp_path), "test", area_id=RIM))["ok"]
    c = TestClient(app)
    req = c.get(f"/api/v1/missions/default?area={RIM}").json()["request"]
    server = c.post(f"/api/v1/missions/evaluate?area={RIM}", json=req).json()
    bridge = json.loads(static_bridge.call("missions/evaluate", json.dumps(req), RIM))["data"]
    assert [l["route"]["polyline_xy_m"] for l in server["assessment"]["legs"]] == [l["route"]["polyline_xy_m"] for l in bridge["assessment"]["legs"]]
    assert server["assessment"]["totals"] == bridge["assessment"]["totals"]
    assert json.loads(static_bridge.call("missions/evaluate", json.dumps(req), "nowhere"))["status"] == 404
