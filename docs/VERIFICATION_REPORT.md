# Verification report

Run date: 2026-11-15/16 (latest run 2026-11-15T21:41Z UTC). Machine: Intel Core i5-7300U (4 threads), 7.6 GB RAM, Linux 6.8, Python 3.12.15 (uv venv), Node 24.22.1. CPU only; no GPU, no cloud service, no API keys. Base commit `74df238`. This report describes the working tree committed directly after it (see `git log`). Dependency versions are pinned in `backend/requirements.txt` and `frontend/package-lock.json`.

## Commands and results (all exit code 0)

| Check | Command | Result |
|---|---|---|
| Data pipeline | `python scripts/prepare_data.py --offline` | All source checksums verified; 7/7 sources AVAILABLE_VERIFIED; DEM 405 × 225, 100% valid |
| Static export | `python scripts/build_static_site.py` | 1.51 MB exported |
| Backend tests | `make test-backend` | **100 passed**, 0 failed, 0 xfail (9.7 s) |
| Frontend tests | `make test-frontend` | **5 passed** |
| Lint / types | `make lint` | ruff: all checks passed; mypy: no issues in 20 files; `tsc -b`: no errors |
| Static production build | `VITE_BASE=/ npm run build:static` | Built; 16 Python engine files copied; `dist/CNAME` = `midgardians.darelladero.tech` |
| Browser smoke, dev server | `make smoke` | Feasible plan; detour scenario Feasible → Feasible; enclosed habitat Feasible → **Infeasible** (`NO_ROUTE`); keyboard-only run reaches Routes; 0 px overflow at 390 px; 0 console errors; 0 failed API calls |
| Browser smoke, production static build | `scripts/browser_smoke.py --url <local static server>/` | Same results with the Python engine running in the browser (Pyodide), no backend server |

The backend suite includes:
- `test_handoff_acceptance.py` (21 tests named by the IDs in `06_TESTING_AND_ACCEPTANCE.md`)
- `test_contracts_v08.py` (24 tests for the `08_DOMAIN_AND_API_CONTRACTS.md` shapes)
- `test_static_bridge.py`, which checks that the in-browser engine returns identical routes and totals to the API server

## Acceptance gates (master prompt section 7)

| Gate | Evidence | Status |
|---|---|---|
| 1. Real data | `DATA_PROVENANCE.md`, `data/source_manifest.json`: USGS CTX DTM SHA-256 `16a1aa66…327b`, DOIs resolve, CRS and extent verified, sample elevations listed. Tests D-01, D-05 | Pass |
| 2. Alignment | Ortho and DEM share CRS and grid origin (0.000 m). DEM vs 252 rover-reported elevations: median 0.37 m, median absolute 1.55 m (supporting cross-check). Image cross-correlation inconclusive (disclosed). Geology PARTIAL (100-200 m). Tests D-03, `test_alignment_gate` | Pass, with disclosure |
| 3. Route | A* on real DEM cells. Synthetic tests T-01..T-07 and R-01..R-08; A* cost equals Dijkstra cost on 12 terrains | Pass |
| 4. Round trip | Directional time, activity, consumable and reserve. Reserve monotonicity on synthetic and real DEM (G-04); activity monotonicity (G-05) | Pass |
| 5. Contingency | Replan starts at the crew position (G-06); a detour beyond the allowance gives INFEASIBLE (G-07); continue mode (G-08); enclosed habitat gives an honest NO_ROUTE; event covering the crew is rejected | Pass |
| 6. Provenance | Every observation links to its source; five evidence labels; per-product source manifest | Pass |
| 7. App | UI uses only engine responses; smoke tests pass on the dev and static builds | Pass |
| 8. Integrity | Synthetic fixtures only in tests; no AI imagery; AI use disclosed in the app, meta tag and docs; no deployment URL claimed as live | Pass |
| 9. Submission | Form answers, 7-slide storyboard (title included), timed 30 s video script. No upload made | Drafts ready; human action needed |

## Real-DEM experiment log (default inputs unless stated)

Default mission: habitat (landing localization) → Wildcat Ridge (60 min activity) → habitat. Inputs: max slope 15°, flat speed 40 m/min, ascent rate 10 m/min, 420 min, reserve 25%.

| Scenario | Result |
|---|---|
| Outbound comparison | Shortest 2,875.6 m, gain 64.3 m, max 14.98°; terrain-aware 2,984.4 m, gain 58.1 m, max 12.54°; cell-set Jaccard 0.063 |
| Round trip, terrain-aware | FEASIBLE: 216.1 min of 315 usable; consumable 192.1 of 375 usable; 5,969 m |
| Round trip, shortest | FEASIBLE: 211.9 min, 5,751 m |
| Add the Three Forks depot | FEASIBLE: 268.7 min |
| Time budget 280 min | INFEASIBLE `INSUFFICIENT_TIME` |
| Reserve 0 / 0.25 / 0.40 / 0.48 / 0.50 / 0.60 | F / F / F / F / INFEASIBLE / INFEASIBLE |
| Max slope 8° | INFEASIBLE: the Wildcat Ridge cell itself exceeds the limit |
| Contingency at 163 min, 250 m zone | FEASIBLE → FEASIBLE; detour avoids every blocked cell |
| Zone (200 m) on the habitat | FEASIBLE → INFEASIBLE `GOAL_IMPASSABLE, BLOCKED_BY_SCENARIO_EVENT, NO_ROUTE` |

**Timing:**
- Server: one A* leg 55-75 ms; a full evaluate has a median of 0.21 s.
- Browser (Pyodide): first load about 15 s; replan under 1 s.

## Screenshots (`docs/screenshots/`, captured by `scripts/browser_smoke.py` from the running app)

| File | Shows |
|---|---|
| `00_guide.png` | First-visit guide |
| `01_plan_overview.png` | Step 1, Plan |
| `02_slope_layer.png` | Step 2, Routes, with the slope view |
| `03_geology_layer.png` | Geology view |
| `04_route_comparison.png` | Route cards and elevation profile |
| `05_feasibility.png` | Verdict, budgets and timeline |
| `06_contingency_replan.png` | Detour |
| `07_no_feasible_return.png` | Enclosed habitat, honest failure |
| `08_rover_photos.png` | Rover photos |
| `09_weather_history.png` | MEDA weather history |
| `10_data_sources.png` | Data sources |
| `11_mobile.png` | 390 px layout |

## Not verified / not done

- No public deployment yet. It needs the repository push and the Cloudflare DNS record, both human actions.
- No slides or video uploaded.
- No sub-pixel optical/DEM co-registration measurement.
- Starlette prints a deprecation warning about `httpx` in the test client; it is harmless.
