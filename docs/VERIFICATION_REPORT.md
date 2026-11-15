# Verification report

Run date: 2026-11-15. Machine: Intel Core i5-7300U (4 threads), 7.6 GB RAM, Ubuntu (Linux 6.8), Python 3.12.15 (uv venv), Node 24.22.1. CPU only; no GPU, no cloud, no API keys.

## Commands and results

| Check | Command | Result |
|---|---|---|
| Backend tests | `make test-backend` | **53 passed**, 0 failed (4.4 s) |
| Frontend tests | `make test-frontend` | **5 passed**, 0 failed |
| Lint / types | `make lint` (ruff, mypy, `tsc -b`) | ruff: all checks passed; mypy: no issues in 15 files; tsc: no errors |
| Production build | `make build` | built (JS 334 kB, gzip 103 kB) |
| Browser smoke | `make smoke` (Playwright Chromium against `make dev`) | Guardian status `FEASIBLE`; contingency `Status change: FEASIBLE -> FEASIBLE`; 0 console errors; 0 failed API calls; 0 px horizontal overflow at 390 px width |
| Data pipeline | `make data` (re-run offline) | All checksums verified; DEM 405 × 225, 100 % valid |

## Acceptance gates (master prompt section 7)

| Gate | Evidence | Status |
|---|---|---|
| 1. Real data | `DATA_PROVENANCE.md`: USGS CTX DTM, SHA-256 `16a1aa66…327b`, CRS and extent verified, sample elevations listed. Test `test_manifest_real_data_gate`. | Pass |
| 2. Alignment | Ortho and DEM: same CRS, grid origin difference 0.000 m (crop fails loudly otherwise). DEM vs 252 rover elevations: median Δ +0.37 m, median absolute 1.55 m (`test_alignment_gate`). Image cross-correlation inconclusive (disclosed). Geology PARTIAL with the USGS offset caveat in the UI. | Pass, with disclosure |
| 3. Route | A* on real DEM cells; synthetic tests prove walls block, gaps are used, corners are not cut, the slope limit is hard, no-data is blocked by default, and A* cost equals Dijkstra cost (12 terrains × 2 weights). | Pass |
| 4. Round trip | Outbound and return legs planned separately with directional time; reserve applied to time and consumable. Reserve monotonicity tested on synthetic grids (12 budget combos × 8 reserves) and on the real DEM. | Pass |
| 5. Contingency | Zone injected from the current simulated position; replanned route avoids every blocked cell (`test_replan_detours_and_accounts_for_spent_resources`); an enclosed habitat gives an honest `INFEASIBLE / NO_ROUTE` (`test_replan_honest_no_feasible_return_when_enclosed`); an event covering the crew is rejected. | Pass |
| 6. Provenance | Every observation carries a source link (`test_observations_are_geolocated_and_sourced`). Badges separate NASA observation, derived, illustrative model, simulated event and unknown. | Pass |
| 7. App | UI uses only API responses; browser smoke shows no console errors; desktop and mobile screenshots below. | Pass |
| 8. Integrity | No synthetic terrain shown as NASA data (synthetic fixtures only in tests, labelled `synthetic-fixture`); no AI imagery; no deployment URL claimed. | Pass |
| 9. Submission | `NASA_SUBMISSION_DRAFT.md` with a 7-slide storyboard. No video or slides were uploaded and no public links were created. | Draft ready, needs human action |

## Real-DEM experiment log (default inputs unless stated)

Default mission: habitat (landing localization) → Wildcat Ridge (60 min activity) → habitat; max slope 15°, flat speed 40 m/min, ascent 10 m/min, 420 min, reserve 25 %.

| Scenario | Result |
|---|---|
| Outbound route comparison | Shortest feasible: 2,875.6 m, gain 64.3 m, max slope 14.98°. Terrain-aware: 2,984.4 m, gain 58.1 m, max slope 12.54°. Cell-set Jaccard overlap 0.063 (the routes differ). |
| Round trip, terrain-aware | **FEASIBLE**: 216.1 min (80.4 out, 75.7 back, 60 activity) against 315 min usable; consumable 192.1 / 375 units usable. Round trip 5,969 m. |
| Round trip, shortest feasible | FEASIBLE: 211.9 min, 5,751 m, gain 81.3 m |
| Add Three Forks depot (45 min) | FEASIBLE: 268.7 min; legs 2,984 / 405 / 2,871 m |
| Time budget 280 min | INFEASIBLE `INSUFFICIENT_TIME` (216.1 > 210 usable) |
| Reserve sweep 0 / 0.25 / 0.40 / 0.48 / 0.50 / 0.60 | F / F / F / F / **INFEASIBLE** / INFEASIBLE (monotonic) |
| Max slope 8° (also 5, 4, 3°) | INFEASIBLE `GOAL_IMPASSABLE, SLOPE_EXCEEDS_LIMIT, NO_ROUTE, START_IMPASSABLE`: the Wildcat Ridge cell itself exceeds the limit |
| Contingency at 163 min (return leg), 250 m zone at 50 % of the remaining route | Crew at (5070, 2570) m, 162.6 min elapsed, 138.6 units used; zone centre (6090, 2510); remaining route 2,101.6 m → 2,032.9 m (the detour is shorter in metres but costlier under the slope-weighted policy); FEASIBLE → FEASIBLE, total 215.4 min |
| Same + 200 units simulated loss | INFEASIBLE → INFEASIBLE `INSUFFICIENT_CONSUMABLE` (391.4 > 375) |
| Zone (200 m) centred on the habitat | FEASIBLE → **INFEASIBLE** `GOAL_IMPASSABLE, BLOCKED_BY_SCENARIO_EVENT, NO_ROUTE` |

Timing: one A* leg takes 55-75 ms (8-12 k expanded cells); a full evaluate has a median of 0.207 s over 10 runs; a replan takes about 0.16 s.

## Screenshots (captured from the running app by `scripts/browser_smoke.py`)

- `docs/screenshots/01_plan_overview.png`: desktop plan view (CTX ortho, both routes, Guardian FEASIBLE)
- `docs/screenshots/02_slope_layer.png`: DEM-derived slope overlay
- `docs/screenshots/03_geology_layer.png`: SIM 3464 units at partial opacity
- `docs/screenshots/04_route_comparison.png`: metrics table and elevation profile
- `docs/screenshots/05_contingency_replan.png`: crew position, simulated blocked zone, replanned route
- `docs/screenshots/06_contingency_panel.png`: before/after assessment and event log
- `docs/screenshots/07_rover_photos.png`: geolocated Navcam images with NASA links
- `docs/screenshots/08_meda_history.png`: MEDA sol 684 pressure and irradiance (history)
- `docs/screenshots/09_sources_alignment.png`: dataset statuses and alignment checks
- `docs/screenshots/10_mobile.png`: 390 px mobile layout
- `docs/screenshots/11_no_feasible_return.png`: zone picked on the habitat gives FEASIBLE -> INFEASIBLE (`GOAL_IMPASSABLE, BLOCKED_BY_SCENARIO_EVENT, NO_ROUTE`), checked in the browser

## Not verified / not done

- No public deployment, video or slide upload (these are human actions).
- No sub-pixel optical/DEM co-registration measurement.
- Playwright check is a smoke test, not a full end-to-end suite.
- Starlette prints a deprecation warning about `httpx` in the test client. It is harmless and left as is.
