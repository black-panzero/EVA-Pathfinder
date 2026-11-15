import itertools

import numpy as np
import pytest
from app.application.services import EventInput, MissionInput, MissionService, ServiceError, Stop
from app.domain.contingency import BlockedZone
from app.domain.mission import ResourceBudget, TraversalProfile
from app.domain.terrain import TerrainGrid

from .conftest import FakeRepo

PROFILE = TraversalProfile("t", flat_speed_m_per_min=40.0, ascent_rate_m_per_min=10.0, max_slope_deg=15.0)


def budget(**kw) -> ResourceBudget:
    base = dict(time_available_min=300.0, consumable_initial_units=400.0, consumable_rate_traverse_per_min=1.0, consumable_rate_activity_per_min=0.5, reserve_fraction=0.2)
    base.update(kw)
    return ResourceBudget(**base)


def make_service(z: np.ndarray | None = None) -> MissionService:
    grid = TerrainGrid.synthetic(np.zeros((50, 80)) if z is None else z, res_m=20.0, lat_deg=18.4)
    return MissionService(FakeRepo(grid), "test")


def mission(svc: MissionService, b: ResourceBudget | None = None, stops=None, choice="terrain") -> MissionInput:
    g = svc.grid
    home = g.cell_center_xy(25, 5)
    tgt = g.cell_center_xy(25, 70)
    return MissionInput(home, tuple(stops or [Stop("t1", "Target", tgt[0], tgt[1], 30.0)]), choice, PROFILE, b or budget(), slope_weight=3.0)


def test_round_trip_feasible_and_directional_time():
    cols = np.arange(80) * 20.0
    z = np.tile(cols * 0.05, (50, 1))  # gentle eastward climb
    svc = make_service(z)
    out = svc.evaluate(mission(svc))
    a = out["assessment"]
    assert a["status"] == "FEASIBLE"
    leg_out, leg_back = a["legs"]
    assert leg_out["minutes"] > leg_back["minutes"]  # climbing outbound costs more time
    assert a["totals"]["minutes"] == pytest.approx(leg_out["minutes"] + leg_back["minutes"] + 30.0, abs=0.2)


def test_insufficient_time_and_consumable():
    svc = make_service()
    a = svc.evaluate(mission(svc, budget(time_available_min=60.0)))["assessment"]
    assert a["status"] == "INFEASIBLE" and "INSUFFICIENT_TIME" in a["reason_codes"]
    a = svc.evaluate(mission(svc, budget(consumable_initial_units=20.0)))["assessment"]
    assert a["status"] == "INFEASIBLE" and "INSUFFICIENT_CONSUMABLE" in a["reason_codes"]


def test_raising_reserve_never_turns_infeasible_into_feasible():
    svc = make_service()
    reserves = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
    for t_avail, cons in itertools.product([70.0, 90.0, 120.0, 200.0], [60.0, 90.0, 150.0]):
        statuses = [svc.evaluate(mission(svc, budget(time_available_min=t_avail, consumable_initial_units=cons, reserve_fraction=r)))["assessment"]["status"] for r in reserves]
        seen_infeasible = False
        for s in statuses:
            if s == "INFEASIBLE":
                seen_infeasible = True
            elif seen_infeasible:
                pytest.fail(f"reserve increase made plan feasible again: {statuses}")


def test_unknown_terrain_gives_unknown_status_only_when_opted_in():
    z = np.zeros((50, 80))
    z[:, 38:42] = np.nan
    svc = make_service(z)
    blocked = svc.evaluate(mission(svc))["assessment"]
    assert blocked["status"] == "INFEASIBLE" and "UNMAPPED_TERRAIN" in blocked["reason_codes"]
    mi = mission(svc)
    opt_in = MissionInput(mi.habitat_xy, mi.stops, mi.route_choice, mi.profile, mi.budget, mi.slope_weight, unknown_policy="penalize", unknown_weight=2.0)
    a = svc.evaluate(opt_in)["assessment"]
    assert a["status"] == "UNKNOWN" and "UNMAPPED_TERRAIN" in a["reason_codes"]


def test_blocked_zone_uses_ground_distance():
    g = TerrainGrid.synthetic(np.zeros((60, 60)), lat_deg=60.0)
    cx, cy = g.cell_center_xy(30, 30)
    m = BlockedZone(cx, cy, 100.0).mask(g)
    rows, cols = np.nonzero(m)
    # E-W ground cell length is ~10 m at 60 deg, so the zone spans about twice as many columns as rows
    assert (cols.max() - cols.min()) > 1.7 * (rows.max() - rows.min())


def test_replan_detours_and_accounts_for_spent_resources():
    svc = make_service()
    mi = mission(svc)
    base = svc.evaluate(mi)["assessment"]
    out_min = base["legs"][0]["minutes"]
    res = svc.replan(mi, elapsed_min=out_min + 30.0 + 5.0, event=EventInput(radius_m=200.0), response_mode="return_now")
    assert res["current_position"]["phase"] == "traverse"
    assert res["current_position"]["consumed_units"] > 0
    assert res["event"]["affects_previous_route"] is True
    after = res["after"]
    assert after["status"] in ("FEASIBLE", "INFEASIBLE")
    assert after["remaining_length_m"] > res["before"]["remaining_length_m"]  # detour is longer
    poly = after["legs"][0]["route"]["polyline_xy_m"]
    zone = BlockedZone(*res["event"]["center_xy_m"], 200.0).mask(svc.grid)
    assert not any(zone[svc.grid.xy_to_cell(x, y)] for x, y in poly)
    # totals include what was already spent
    assert after["totals"]["minutes"] >= res["current_position"]["elapsed_min"]


def test_replan_honest_no_feasible_return_when_enclosed():
    svc = make_service()
    mi = mission(svc)
    home = mi.habitat_xy
    res = svc.replan(mi, elapsed_min=10.0, event=EventInput(radius_m=150.0, center_xy=home), response_mode="return_now")
    assert res["after"]["status"] == "INFEASIBLE"
    assert "NO_ROUTE" in res["after"]["reason_codes"]
    assert res["after"]["legs"][0]["route"] is None


def test_event_covering_crew_is_rejected():
    svc = make_service()
    mi = mission(svc)
    with pytest.raises(ServiceError) as e:
        svc.replan(mi, elapsed_min=0.0, event=EventInput(radius_m=100.0, center_xy=mi.habitat_xy), response_mode="return_now")
    assert e.value.code == "EVENT_COVERS_CREW"


def test_consumable_loss_can_flip_feasibility():
    svc = make_service()
    mi = mission(svc)
    ok = svc.replan(mi, elapsed_min=20.0, event=EventInput(radius_m=40.0, position_fraction=0.9), response_mode="return_now")
    assert ok["after"]["status"] == "FEASIBLE"
    bad = svc.replan(mi, elapsed_min=20.0, event=EventInput(radius_m=40.0, position_fraction=0.9), response_mode="return_now", consumable_loss=1000.0)
    assert bad["after"]["status"] == "INFEASIBLE" and "INSUFFICIENT_CONSUMABLE" in bad["after"]["reason_codes"]


def test_invalid_budget_rejected():
    with pytest.raises(ValueError):
        budget(reserve_fraction=1.0)
    with pytest.raises(ValueError):
        budget(time_available_min=-5)
