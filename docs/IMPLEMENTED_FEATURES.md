# Implemented features

The working / not-implemented matrix required by `05_IMPLEMENTATION_PLAN.md` §3.4. Status reflects what was run and verified (see `VERIFICATION_REPORT.md`).

| Area | Feature | Status | Evidence |
|---|---|---|---|
| Data | USGS CTX DTM 20 m + ortho 6 m, cropped to the same grid, checksummed | Working | `scripts/prepare_data.py`, `data/processed/.../manifest.json` |
| Data | USGS SIM 3464 geology reprojected and rasterized (regional context) | Working (partial alignment, disclosed) | `geology_units.json`, UI legend caveat |
| Data | Science sites resolved from Perseverance site/drive records | Working | `config/science_sites.json`, `science_sites.json` |
| Data | Geolocated Navcam photos (sols 502, 684) | Working | `photos.json` |
| Data | MEDA sol 684 pressure and irradiance history | Working | `meda.json` |
| Terrain | Latitude-correct slope in ground metres; NaN-safe | Working | `test_terrain.py`, T-01..T-07 |
| Routing | 8-neighbour A*, no corner cutting, hard slope and no-data limits; shortest vs terrain-aware | Working | `test_navigation.py`, R-01..R-08 |
| Routing | Path smoothing | Not implemented (deliberate, R-09) | `ALGORITHM_METHODS.md` |
| Guardian | Round trip with directional time, activity time, consumable, reserve; FEASIBLE / INFEASIBLE / UNKNOWN with reason codes | Working | G-01..G-05 |
| Contingency | Replan from the simulated crew position with spent resources; blocked zone; honest no-route | Working | G-06..G-08 |
| API | FastAPI v1 endpoints; Pydantic validation; NaN-safe 422s | Working | `test_api_real_data.py` |
| API | 08 contract field names and request shapes | See `DECISIONS.md` "Handoff conformance pass" | `test_contracts_v08.py` |
| UI | Step-by-step workflow (Plan, Routes, Feasibility, Contingency, Evidence), first-visit guide, map view switcher, provenance labels | Working | `browser_smoke.py`, screenshots |
| UI | Keyboard operation, text status alongside colour, mobile layout | Working (smoke-tested) | `browser_smoke.py` |
| Deploy | Static build (Pyodide runs the same Python engine in the browser), parity-tested | Working locally | `test_static_bridge.py` |
| Deploy | Public GitHub Pages site at the custom domain | Not done: needs the repo push and DNS (human actions) | `README.md` |
| Submission | Form answers, storyboard, video script | Drafts ready | `SUBMISSION_FORM.md`, `NASA_SUBMISSION_DRAFT.md` |
| Submission | Slides or video uploaded | Not done: human action | |
| Out of scope | HiRISE terrain, 3D view, ROS 2, LLM commands, real-time weather | Not implemented (roadmap only) | |
