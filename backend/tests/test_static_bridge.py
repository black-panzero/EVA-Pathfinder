"""The static (Pyodide) bridge must give the same results as the FastAPI server."""
import json
import shutil

import numpy as np
from fastapi.testclient import TestClient

from .conftest import PROCESSED, requires_real_data

pytestmark = requires_real_data


def test_bridge_matches_server(tmp_path):
    from app import static_bridge
    from app.api.main import app, repo

    r = repo()
    np.save(tmp_path / "dem_crop.npy", r.grid.elevation_m.astype("float32"))
    for n in ("geology_units.npy", "geology_units.json", "manifest.json"):
        shutil.copy2(PROCESSED / n, tmp_path / n)
    assert json.loads(static_bridge.init(str(tmp_path), "test"))["ok"]

    c = TestClient(app)
    req = c.get("/api/v1/missions/default").json()["request"]
    server = c.post("/api/v1/missions/evaluate", json=req).json()
    bridge = json.loads(static_bridge.call("missions/evaluate", json.dumps(req)))
    assert bridge["ok"]
    s_legs, b_legs = server["assessment"]["legs"], bridge["data"]["assessment"]["legs"]
    assert [l["route"]["polyline_xy_m"] for l in s_legs] == [l["route"]["polyline_xy_m"] for l in b_legs]
    assert server["assessment"]["totals"] == bridge["data"]["assessment"]["totals"]
    assert server["run_manifest"]["dem_crop_sha256"] == bridge["data"]["run_manifest"]["dem_crop_sha256"]

    body = {"mission": req, "elapsed_min": 163, "event": {"radius_m": 250}, "response_mode": "return_now"}
    s_rp = c.post("/api/v1/scenarios/replan", json=body).json()
    b_rp = json.loads(static_bridge.call("scenarios/replan", json.dumps(body)))["data"]
    assert s_rp["after"]["legs"][0]["route"]["polyline_xy_m"] == b_rp["after"]["legs"][0]["route"]["polyline_xy_m"]
    assert s_rp["status_change"] == b_rp["status_change"]


def test_bridge_errors(tmp_path):
    from app import static_bridge

    bad = json.loads(static_bridge.call("missions/evaluate", json.dumps({"habitat": {"x_m": -1, "y_m": 0}})))
    assert not bad["ok"] and bad["status"] in (422, 503)
    assert json.loads(static_bridge.call("nope", "{}"))["ok"] is False
