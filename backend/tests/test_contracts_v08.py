"""08 domain/API contract conformance (EVA_Pathfinder_Handoff/08_DOMAIN_AND_API_CONTRACTS.md).

The 08 shapes are ADDITIVE: legacy request shapes and response keys must keep working.
Real-data tests are skipped (not faked) when the study area is not prepared; synthetic-grid
tests use a clearly-labelled synthetic fixture.
"""
import copy
import json
import shutil

import numpy as np
import pytest
from app.api import handlers
from app.api.schemas import RouteCompareContractRequest
from app.api.translate_v08 import FALLBACK_DEFAULTS
from app.application.services import MissionService, ServiceError
from app.domain.navigation import RoutePolicy
from app.domain.terrain import TerrainError, TerrainGrid
from app.domain.values import DomainEventName, MapGridCell, MapPoint, MissionAssessment, MissionState, TerrainPolicy
from fastapi.testclient import TestClient

from .conftest import PROCESSED, ROOT, FakeRepo, requires_real_data

DATASET = "ctx_dem_jezero_trn_2020"
MAP_CONTRACT_KEYS = {"body", "crs_id", "coordinate_units", "longitude_direction", "longitude_domain", "resolution_m", "source_dataset_id", "status"}
CANDIDATE_KEYS = {"policy", "polyline_map_m", "path_cells", "distance_m", "elevation_gain_m", "elevation_loss_m", "max_derived_slope_deg", "unknown_fraction",
                  "model_minutes", "total_cost", "reason_codes", "route_policy_version", "source_artifact_hash", "config_hash"}
EVAL_KEYS = {"status", "reason_codes", "outbound_route_id", "return_route_id", "total_duration_min", "estimated_consumable_remaining_units",
             "minimum_required_reserve_units", "assumptions", "evidence", "warnings"}


@pytest.fixture(scope="module")
def client():
    from app.api.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def sites():
    return json.loads((PROCESSED / "science_sites.json").read_text())


@pytest.fixture(scope="module")
def legacy_req(client):
    return client.get("/api/v1/missions/default").json()["request"]


def _home_and_site(sites):
    h, s = sites["habitat"]["cell"], sites["sites"][0]
    return {"row": h[0], "col": h[1]}, s


def compare_body(sites, **kw):
    home, s = _home_and_site(sites)
    body = {"dataset_id": DATASET, "origin": home, "destination": {"row": s["cell"][0], "col": s["cell"][1]}, "max_derived_slope_deg": 25.0,
            "unknown_policy": "BLOCK", "policies": ["MIN_DISTANCE", "TERRAIN_WEIGHTED"], "weights": {"slope": 2.0, "uncertainty": 1.0}}
    body.update(kw)
    return body


def evaluate_body(sites, **kw):
    home, s = _home_and_site(sites)
    body = {"dataset_id": DATASET, "origin": home, "science_stops": [{"id": s["id"], "row": s["cell"][0], "col": s["cell"][1], "activity_minutes": 20}],
            "traversal": {"assumed_speed_m_per_min": 30.0, "consumable_name": "illustrative_resource_units", "consumption_rate_per_min": 1.0},
            "budget": {"max_minutes": 240.0, "initial_consumable_units": 240.0, "reserve_fraction": 0.25},
            "terrain_policy": {"max_derived_slope_deg": 25.0, "unknown_policy": "BLOCK"}}
    body.update(kw)
    return body


# ------------------------------------------------------------------------------- 1. health
@requires_real_data
def test_1_health_ready_and_dataset_status(client):
    h = client.get("/health").json()
    assert h["status"] == "ready" and h["dataset_status"] == "AVAILABLE_VERIFIED" and h["data_ready"] is True


@requires_real_data
def test_1_health_partial_when_core_source_unverified(client, monkeypatch):
    from app.api import main

    r = main.repo()
    patched = copy.deepcopy(r.manifest)
    patched["source_status"]["usgs-m2020-trn-ctx-ortho-6m"]["status"] = "UNAVAILABLE"
    monkeypatch.setattr(r, "manifest", patched)
    h = client.get("/health").json()
    assert h["dataset_status"] == "PARTIAL" and h["status"] == "ready"  # DEM still verified
    patched["source_status"]["usgs-m2020-trn-ctx-dtm-20m"]["status"] = "UNAVAILABLE"
    assert client.get("/health").json()["status"] == "degraded"


def test_1_health_unavailable_branch(client, monkeypatch):
    from app.api import main
    from app.infrastructure.repositories import DataUnavailable

    def broken():
        raise DataUnavailable("simulated")

    monkeypatch.setattr(main, "repo", broken)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded" and r.json()["dataset_status"] == "UNAVAILABLE" and r.json()["data_ready"] is False
    e = client.post("/api/v1/routes/compare", json={"origin": {"x_m": 1, "y_m": 1}, "goal": {"x_m": 100, "y_m": 100}}).json()["error"]
    assert e["code"] == "DATA_UNAVAILABLE" and e["contract_code"] == "SOURCE_UNAVAILABLE"


# ------------------------------------------------------------------------------- 2. map contract
@requires_real_data
def test_2_map_contract_on_study_area_datasets_and_routes(client, sites):
    sa = client.get("/api/v1/study-area").json()
    mc = sa["map_contract"]
    assert MAP_CONTRACT_KEYS <= set(mc)
    assert mc["body"] == "Mars" and mc["coordinate_units"] == "m" and mc["longitude_direction"] == "east_positive"
    assert mc["longitude_domain"] == "-180_to_180" and all(-180 <= v < 180 for v in mc["lon_range_deg"])
    assert mc["source_dataset_id"] == DATASET and mc["resolution_m"] == 20.0 and mc["status"] == "AVAILABLE_VERIFIED"
    assert client.get("/api/v1/datasets").json()["map_contract"] == mc
    out = client.post("/api/v1/routes/compare", json=compare_body(sites)).json()
    assert out["map_contract"]["crs_id"] == mc["crs_id"]
    for r in out["routes"]:
        assert r["map_contract"]["crs_id"] == mc["crs_id"]
    ev = client.post("/api/v1/missions/evaluate", json=evaluate_body(sites)).json()
    for leg in ev["assessment"]["legs"]:
        assert set(leg["route"]["map_contract"]) >= MAP_CONTRACT_KEYS


# ------------------------------------------------------------------------------- 3. datasets
@requires_real_data
def test_3_dataset_contract_fields_and_alias(client):
    d = client.get("/api/v1/datasets").json()
    dem = next(x for x in d["datasets"] if x["source_id"] == "usgs-m2020-trn-ctx-dtm-20m")
    for k in ("id", "product", "body", "crs", "bounds", "resolution_m", "file_sha256", "acquisition_date", "creation_date", "status", "source_url", "limitations"):
        assert k in dem, k
    assert dem["id"] == DATASET and dem["resolution_m"] == 20.0 and len(dem["file_sha256"]) == 64
    assert dem["status"] == dem["verification_status"] == "AVAILABLE_VERIFIED" and dem["source_url"].startswith("https://")
    assert dem["acquisition_date"] is None  # not known -> null, not invented
    geo = next(x for x in d["datasets"] if x["source_id"] == "usgs-sim3464-geology")
    assert geo["status"] == "PARTIAL" and geo["limitations"]
    assert d["dataset_aliases"][DATASET] == "usgs-m2020-trn-ctx-dtm-20m"


# ------------------------------------------------------------------------------- 4. science sites
@requires_real_data
def test_4_science_site_contract_fields(client):
    out = client.get("/api/v1/science-sites").json()
    crs = out["map_contract"]["crs_id"]
    for s in out["sites"]:
        assert {"id", "name", "x_m", "y_m", "citations"} <= set(s)  # legacy keys kept
        assert s["objective"] and s["location_status"] in ("verified", "contextual") and s["notes"]
        assert s["source_urls"] and all(u.startswith("https://") for u in s["source_urls"])
        if s["in_planning_area"]:
            assert s["map_point"] == {"x_m": s["x_m"], "y_m": s["y_m"], "crs_id": crs}
            assert [s["grid_cell"]["row"], s["grid_cell"]["col"]] == s["cell"]
        else:  # off the routing grid: 08 allows map_point null; position still given as lon/lat
            assert s["map_point"] is None and s["grid_cell"] is None and s["location_status"] == "contextual"
            assert -180 <= s["lon_deg_180"] <= 180


# ------------------------------------------------------------------------------- 5/6. compare
@requires_real_data
def test_5_6_compare_08_shape(client, sites):
    r = client.post("/api/v1/routes/compare", json=compare_body(sites))
    assert r.status_code == 200
    out = r.json()
    assert out["dataset_id"] == DATASET and out["computed_from_real_data"] is True
    assert out["reason_codes"] == [] and out["model_limitations"] and out["evidence"]
    pols = {c["policy"]: c for c in out["route_candidates"]}
    assert set(pols) == {"MIN_DISTANCE", "TERRAIN_WEIGHTED"}
    for c in pols.values():
        assert CANDIDATE_KEYS <= set(c)
        assert c["max_derived_slope_deg"] <= 25.0 + 1e-6 and c["model_minutes"] > 0
        assert len(c["path_cells"]) == len(c["polyline_map_m"])
        assert len(c["source_artifact_hash"]) == 64 and len(c["config_hash"]) == 64
    assert pols["MIN_DISTANCE"]["distance_m"] <= pols["TERRAIN_WEIGHTED"]["distance_m"] + 1e-6
    # missing traversal -> config default profile recorded as assumption
    assert any(a["item"] == "assumed_speed_m_per_min" for a in out["assumptions"])
    one = client.post("/api/v1/routes/compare", json=compare_body(sites, policies=["TERRAIN_WEIGHTED"])).json()
    assert [c["policy"] for c in one["route_candidates"]] == ["TERRAIN_WEIGHTED"]


@requires_real_data
def test_5_compare_08_shape_with_map_points_and_penalize(client, sites):
    s = sites["sites"][0]
    crs = client.get("/api/v1/study-area").json()["map_contract"]["crs_id"]
    body = compare_body(sites, origin={"x_m": sites["habitat"]["x_m"], "y_m": sites["habitat"]["y_m"], "crs_id": crs},
                        destination={"x_m": s["x_m"], "y_m": s["y_m"]}, unknown_policy="PENALIZE")
    out = client.post("/api/v1/routes/compare", json=body).json()
    assert {r["policy"]["unknown_policy"] for r in out["routes"]} == {"penalize"}


@requires_real_data
def test_5_compare_legacy_shape_unchanged(client, legacy_req):
    body = {"origin": legacy_req["habitat"], "goal": legacy_req["stops"][0]["point"], "max_slope_deg": 15, "slope_weight": 3}
    out = client.post("/api/v1/routes/compare", json=body).json()
    assert {"routes", "failures", "routes_coincide", "cell_overlap_jaccard", "caveats", "events"} <= set(out)
    assert {r["route_id"] for r in out["routes"]} == {"shortest", "terrain"}
    assert {"route_id", "policy", "polyline_xy_m", "metrics", "profile"} <= set(out["routes"][0])
    assert isinstance(out["routes"][0]["policy"], dict)
    assert all(c["model_minutes"] is None for c in out["route_candidates"])  # legacy body has no profile


# ------------------------------------------------------------------------------- 5/6. evaluate
@requires_real_data
def test_5_6_evaluate_08_shape(client, sites):
    r = client.post("/api/v1/missions/evaluate", json=evaluate_body(sites))
    assert r.status_code == 200
    out = r.json()
    assert EVAL_KEYS <= set(out)
    assert out["status"] in ("FEASIBLE", "INFEASIBLE", "UNKNOWN") and out["status"] == out["assessment"]["status"]
    assert out["outbound_route_id"].startswith("leg1:") and out["return_route_id"].endswith("->habitat")
    assert out["minimum_required_reserve_units"] == 60.0
    assert out["estimated_consumable_remaining_units"] == pytest.approx(240.0 - out["assessment"]["totals"]["consumable_units"], abs=0.2)
    assert out["mission_state"] in ("READY_UNDER_MODEL", "INFEASIBLE", "UNKNOWN")
    items = {a["item"]: a for a in out["assumptions"]}
    assert items["ascent_rate_m_per_min"]["value"] == FALLBACK_DEFAULTS["traversal_profile"]["ascent_rate_m_per_min"]
    assert any(a["item"] == "ascent_rate_m_per_min" and "config/mission_defaults.json" in a["basis"] for a in out["assumptions"])
    # single 08 rate -> both travel and activity rates; consumable_name -> consumable_label
    assert items["travel_consumable_rate_per_min"]["value"] == items["activity_consumable_rate_per_min"]["value"] == 1.0
    assert out["assessment"]["totals"]["consumable_label"] == "illustrative_resource_units"


@requires_real_data
def test_6_evaluate_infeasible_no_route_does_not_crash(client, sites):
    body = evaluate_body(sites, terrain_policy={"max_derived_slope_deg": 0.5, "unknown_policy": "BLOCK"})
    r = client.post("/api/v1/missions/evaluate", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "INFEASIBLE" and out["mission_state"] == "INFEASIBLE"
    assert out["total_duration_min"] is None and out["estimated_consumable_remaining_units"] is None
    assert out["null_reasons"]["total_duration_min"]
    if out["outbound_route_id"] is None:
        assert "NO_ROUTE" in out["null_reasons"]["outbound_route_id"] or out["null_reasons"]["outbound_route_id"]


@requires_real_data
def test_5_evaluate_legacy_shape_unchanged(client, legacy_req):
    out = client.post("/api/v1/missions/evaluate", json=legacy_req).json()
    assert {"mission_name", "route_choice", "assessment", "alternative", "evidence", "events", "run_manifest", "disclaimer"} <= set(out)
    assert EVAL_KEYS <= set(out)


# ------------------------------------------------------------------------------- 5/6. replan
@requires_real_data
def test_5_6_replan_08_shape_blockage_on_return_route(client, sites, legacy_req):
    # Find the active return route from a reported mid-return position, then block a cell on it.
    ev = client.post("/api/v1/missions/evaluate", json=legacy_req).json()
    ret = ev["assessment"]["legs"][-1]["route"]["path_cells"]
    cur, blocked = ret[len(ret) // 3], ret[len(ret) // 2]
    body = {"mission_id": "delta-return-01", "scenario_id": "blocked-corridor-01", "current_grid_cell": {"row": cur[0], "col": cur[1]},
            "already_elapsed_minutes": 75.0, "already_used_consumable_units": 75.0, "completed_stop_ids": [legacy_req["stops"][0]["stop_id"]],
            "event": {"kind": "SIMULATED_BLOCKAGE", "blocked_cells": [{"row": blocked[0], "col": blocked[1]}]}}
    r = client.post("/api/v1/scenarios/replan", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["scenario_id"] == "blocked-corridor-01" and out["mission_resolution"] == "config default mission"
    assert out["position_source"] == "caller_reported" and out["current_grid_cell"] == {"row": cur[0], "col": cur[1]}
    assert out["event"]["kind"] == "SIMULATED_BLOCKAGE" and out["event"]["affects_previous_route"] is True
    assert "BLOCKED_BY_SCENARIO_EVENT" in out["reason_codes"]
    assert blocked not in out["alternative"]["path_cells"] and blocked in out["baseline"]["path_cells"]
    assert out["alternative"]["path_cells"][0] == cur
    rb = out["remaining_budget"]
    assert rb["elapsed_min"] == 75.0 and rb["consumed_units"] == 75.0
    assert out["mission_state_trace"][0] == "RETURNING_SIMULATED" and out["mission_state_trace"][1] == "REPLANNING"
    assert out["mission_state"] in ("READY_UNDER_MODEL", "INFEASIBLE", "UNKNOWN")
    assert {"before", "after", "status_change"} <= set(out)
    assert any(e["level"] == "SIMULATED_EVENT" for e in out["evidence"])


@requires_real_data
def test_5_replan_08_inline_mission_and_errors(client, sites):
    home, _ = _home_and_site(sites)
    body = {"mission": evaluate_body(sites), "current_grid_cell": home, "already_elapsed_minutes": 10.0, "already_used_consumable_units": 10.0,
            "event": {"kind": "SIMULATED_BLOCKAGE", "blocked_cells": [{"row": home["row"] + 2, "col": home["col"]}]}, "response_mode": "CONTINUE"}
    out = client.post("/api/v1/scenarios/replan", json=body).json()
    assert out["mission_resolution"].startswith("inline mission (08")
    assert out["response_mode"] == "continue"
    bad = client.post("/api/v1/scenarios/replan", json={**body, "event": {"kind": "SIMULATED_BLOCKAGE", "blocked_cells": [{"row": 99999, "col": 0}]}}).json()
    assert bad["error"]["contract_code"] == "INVALID_COORDINATES"
    crew = client.post("/api/v1/scenarios/replan", json={**body, "event": {"kind": "SIMULATED_BLOCKAGE", "blocked_cells": [home]}}).json()
    assert crew["error"]["code"] == "EVENT_COVERS_CREW"
    unknown = {k: v for k, v in body.items() if k != "mission"} | {"mission_id": "not-stored"}
    e = client.post("/api/v1/scenarios/replan", json=unknown).json()["error"]
    assert e["contract_code"] == "INVALID_MISSION_CONFIGURATION"
    partial = {k: v for k, v in body.items() if k != "already_used_consumable_units"}
    assert client.post("/api/v1/scenarios/replan", json=partial).status_code == 422
    # BLOCKED_ZONE circle still accepted in 08 shape (timeline-derived position)
    circle = {"mission_id": "default", "already_elapsed_minutes": 30.0, "event": {"kind": "BLOCKED_ZONE", "radius_m": 200}}
    c = client.post("/api/v1/scenarios/replan", json=circle).json()
    assert c["position_source"] == "planned_timeline" and c["event"]["type"] == "BLOCKED_ZONE"


@requires_real_data
def test_5_replan_legacy_shape_unchanged(client, legacy_req):
    body = {"mission": legacy_req, "elapsed_min": 200, "event": {"radius_m": 250}, "response_mode": "return_now"}
    out = client.post("/api/v1/scenarios/replan", json=body).json()
    assert {"baseline_status", "current_position", "event", "response_mode", "before", "after", "status_change", "events", "run_manifest"} <= set(out)
    assert out["event"]["type"] == "BLOCKED_ZONE" and out["event"]["radius_m"] == 250
    assert {"scenario_id", "baseline", "alternative", "reason_codes", "remaining_budget"} <= set(out)


# ------------------------------------------------------------------------------- 6. reports
@requires_real_data
def test_6_report_contract_fields(client, legacy_req, sites):
    body = {"mission": evaluate_body(sites), "replan": {"mission": legacy_req, "elapsed_min": 200, "event": {"radius_m": 250}}}
    r = client.post("/api/v1/reports", json=body).json()
    for k in ("model_build_version", "source_hashes", "study_extent", "scenario_event", "final_status", "unknowns", "assumptions", "provenance", "mission_evaluation"):
        assert k in r, k
    assert len(r["source_hashes"]["dem_crop_sha256"]) == 64 and r["source_hashes"]["sources"]["usgs-m2020-trn-ctx-dtm-20m"]
    assert r["study_extent"]["bounds_xy_m"] and r["scenario_event"]["evidence_level"] == "SIMULATED_EVENT"
    assert r["final_status"] == r["contingency"]["alternative"]["status"]


# ------------------------------------------------------------------------------- 7. errors
@requires_real_data
def test_7_error_contract_codes(client, sites, legacy_req):
    e = client.post("/api/v1/routes/compare", json=compare_body(sites, crs_id="IAU_2015:49900")).json()["error"]
    assert e["code"] == e["contract_code"] == "CRS_MISMATCH"
    s = sites["sites"][0]
    e = client.post("/api/v1/routes/compare", json=compare_body(sites, destination={"x_m": s["x_m"], "y_m": s["y_m"], "crs_id": "EPSG:4326"})).json()["error"]
    assert e["contract_code"] == "CRS_MISMATCH"
    e = client.post("/api/v1/routes/compare", json=compare_body(sites, origin={"row": 100000, "col": 1})).json()["error"]
    assert e["code"] == "OUT_OF_BOUNDS" and e["contract_code"] == "INVALID_COORDINATES"
    e = client.post("/api/v1/routes/compare", json=compare_body(sites, dataset_id="usgs-sim3464-geology")).json()["error"]
    assert e["contract_code"] == "UNALIGNED_SOURCE"
    r = client.post("/api/v1/routes/compare", json=compare_body(sites, dataset_id="no-such-dataset"))
    assert r.status_code == 404 and r.json()["error"]["contract_code"] == "SOURCE_UNAVAILABLE"
    # legacy errors keep code and gain contract_code
    r = client.post("/api/v1/missions/evaluate", json={**legacy_req, "habitat": {"x_m": -5, "y_m": 10}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_INPUT" and r.json()["error"]["contract_code"] == "INVALID_COORDINATES"
    assert r.json()["error"]["details"][0]["loc"] == ["body", "habitat", "x_m"]  # union tag not leaked into loc
    r = client.post("/api/v1/missions/evaluate", json={**legacy_req, "budget": {**legacy_req["budget"], "reserve_fraction": 1.0}})
    assert r.json()["error"]["contract_code"] == "INVALID_MISSION_CONFIGURATION"
    r = client.post("/api/v1/routes/compare", json={"origin": legacy_req["habitat"], "goal": legacy_req["habitat"]})
    assert r.json()["error"]["code"] == "SAME_START_GOAL" and r.json()["error"]["contract_code"] == "INVALID_COORDINATES"


def test_7_no_data_coverage_on_synthetic_grid():
    z = np.zeros((20, 30))
    z[10, 20] = np.nan
    svc = MissionService(FakeRepo(TerrainGrid.synthetic(z, res_m=20.0, lat_deg=18.4)), "test")
    req = RouteCompareContractRequest.model_validate({"origin": {"row": 2, "col": 2}, "destination": {"row": 10, "col": 20}})
    with pytest.raises(ServiceError) as e:
        handlers.compare(svc, req)
    assert e.value.contract_code == "NO_DATA_COVERAGE"
    ok = handlers.compare(svc, RouteCompareContractRequest.model_validate({"origin": {"row": 2, "col": 2}, "destination": {"row": 15, "col": 25}}))
    assert ok["computed_from_real_data"] is False and ok["map_contract"]["status"] == "SYNTHETIC_FIXTURE"
    assert ok["route_candidates"] and ok["dataset_id"] == "synthetic-fixture"


# ------------------------------------------------------------------------------- 8. domain language
def test_8_domain_value_objects():
    g = TerrainGrid.synthetic(np.zeros((5, 5)))
    assert MapGridCell(1, 2).validate(g) == (1, 2)
    with pytest.raises(TerrainError) as e:
        MapGridCell(5, 0).validate(g)
    assert e.value.code == "OUT_OF_BOUNDS"
    with pytest.raises(TerrainError) as e:
        MapPoint(1.0, 1.0, "other").require_crs("mine")
    assert e.value.code == "CRS_MISMATCH"
    assert TerrainPolicy is RoutePolicy
    from app.domain.mission import FeasibilityAssessment

    assert MissionAssessment is FeasibilityAssessment
    assert [s.value for s in MissionState][:7] == ["PLANNED", "ROUTE_EVALUATED", "READY_UNDER_MODEL", "OUTBOUND_SIMULATED", "SCIENCE_SIMULATED",
                                                    "RETURNING_SIMULATED", "COMPLETED_SIMULATED"]
    assert {"REPLANNING", "INFEASIBLE", "UNKNOWN"} <= {s.value for s in MissionState}


def test_8_event_names_are_formalized():
    svc = MissionService(FakeRepo(TerrainGrid.synthetic(np.zeros((20, 30)), lat_deg=18.4)), "test")
    out = handlers.compare(svc, RouteCompareContractRequest.model_validate({"origin": {"row": 2, "col": 2}, "destination": {"row": 15, "col": 25}}))
    names = {e["name"] for e in out["events"]}
    assert names and names <= {n.value for n in DomainEventName}


# ------------------------------------------------------------------------------- 9. mission template
def _filled_template(sites) -> dict:
    tpl = json.loads((ROOT / "EVA_Pathfinder_Handoff" / "config" / "mission.delta-return.example.json").read_text())
    home, s = _home_and_site(sites)
    tpl["origin"] = home
    tpl["science_stops"] = [{"id": s["id"], "name": s["name"], "row": s["cell"][0], "col": s["cell"][1]}]
    return tpl


@requires_real_data
def test_9_mission_template_translation(client, sites):
    tpl = _filled_template(sites)
    r = client.post("/api/v1/missions/evaluate", json=tpl)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["request_shape"] == "handoff-mission-template" and out["mission_id"] == tpl["mission_id"]
    assert EVAL_KEYS <= set(out)
    c = tpl["illustrative_consumable"]
    assert out["assessment"]["totals"]["consumable_label"] == c["name"]
    assert out["minimum_required_reserve_units"] == pytest.approx(c["initial_units"] * c["minimum_reserve_fraction"])
    items = {a["item"]: a["value"] for a in out["assumptions"]}
    assert items["activity_minutes"] == tpl["activity_duration_min_assumed"] and items["crew_count_simulated"] == 2
    assert out["assessment"]["activities"][0]["minutes"] == tpl["activity_duration_min_assumed"]
    # also usable inline in a replan
    rp = {"mission": tpl, "already_elapsed_minutes": 5.0, "event": {"kind": "BLOCKED_ZONE", "radius_m": 100}, "response_mode": "continue"}
    assert client.post("/api/v1/scenarios/replan", json=rp).json()["mission_resolution"] == "inline mission (handoff template)"


def test_9_unfilled_template_rejected(client):
    tpl = json.loads((ROOT / "EVA_Pathfinder_Handoff" / "config" / "mission.delta-return.example.json").read_text())
    r = client.post("/api/v1/missions/evaluate", json=tpl)
    assert r.status_code in (422, 503)
    if r.status_code == 422:
        assert r.json()["error"]["contract_code"] == "INVALID_MISSION_CONFIGURATION"


def test_fallback_defaults_match_config():
    cfg = json.loads((ROOT / "config" / "mission_defaults.json").read_text())
    for section in ("budgets", "route_policies", "limits"):
        assert FALLBACK_DEFAULTS[section] == cfg[section], section
    for k, v in FALLBACK_DEFAULTS["traversal_profile"].items():
        assert cfg["traversal_profile"][k] == v


# ------------------------------------------------------------------------------- static bridge
@requires_real_data
def test_bridge_accepts_08_shapes(tmp_path, sites):
    from app import static_bridge
    from app.api.main import repo

    np.save(tmp_path / "dem_crop.npy", repo().grid.elevation_m.astype("float32"))
    for n in ("geology_units.npy", "geology_units.json", "manifest.json", "science_sites.json"):
        shutil.copy2(PROCESSED / n, tmp_path / n)
    assert json.loads(static_bridge.init(str(tmp_path), "test"))["ok"]
    out = json.loads(static_bridge.call("routes/compare", json.dumps(compare_body(sites))))
    assert out["ok"] and {c["policy"] for c in out["data"]["route_candidates"]} == {"MIN_DISTANCE", "TERRAIN_WEIGHTED"}
    ev = json.loads(static_bridge.call("missions/evaluate", json.dumps(_filled_template(sites))))
    assert ev["ok"] and ev["data"]["status"]
    bad = json.loads(static_bridge.call("routes/compare", json.dumps(compare_body(sites, crs_id="x"))))
    assert not bad["ok"] and bad["error"]["contract_code"] == "CRS_MISMATCH"
    v = json.loads(static_bridge.call("missions/evaluate", json.dumps({"habitat": {"x_m": -1, "y_m": 0}})))
    assert v["status"] == 422 and v["error"]["code"] == "INVALID_INPUT" and v["error"]["contract_code"]
