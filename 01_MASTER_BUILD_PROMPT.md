# MASTER BUILD PROMPT — EVA Pathfinder / EVA Guardian

**Audience:** Codex, Claude Code, or an autonomous software-engineering agent inside a writable project repository.  
**Challenge:** NASA Space Apps Challenge 2026 — *Interplanetary Survival Guide: Martian Map*.  
**Status:** Build specification, **not** a claim that software has been implemented.  
**Product:** EVA Pathfinder (integrated Marswalk map); EVA Guardian (return-aware mission feasibility and contingency engine).  
**Core mission:** Operation Delta Return, a hypothetical EVA based on verified Jezero Crater terrain and science context.

## 0. READ FIRST AND FOLLOW THE ORDER

Before writing code, read every file in this handoff:

1. `README.md` — navigation and expected outputs.
2. `02_PLATFORM_SPECIFICATION.md` — product, UX, visualizations, DDD, DDA, OOP, architecture, and API.
3. `03_NASA_RULES_AND_SUBMISSION.md` — rules derived from the official user-provided 2026 submission guide and user's form.
4. `04_DATA_CATALOG_AND_PIPELINE.md` — data URLs, Mars CRS constraints, extraction and provenance.
5. `05_IMPLEMENTATION_PLAN.md` — strict priorities, task sequence, fallbacks.
6. `06_TESTING_AND_ACCEPTANCE.md` — test cases, quality gates, verifiable done definition.
7. `07_SUBMISSION_CONTENT_TEMPLATES.md` — human-reviewable form fields and demo outline.
8. `08_DOMAIN_AND_API_CONTRACTS.md` — domain language and JSON contracts.
9. `NASA_CHALLENGE_BRIEF.md` and `references/NASA_Space_Apps_Project_Submission_Guide_2026.pdf` — authoritative provided requirements.
10. `AGENTS.md` or `CLAUDE.md` — tool-specific operational rules (aligned with this file).

**Instruction precedence:** safety and legal instructions > NASA rule/source constraints > acceptance tests > architecture > preferred UI implementation. If documents conflict, explain the conflict in `docs/DECISIONS.md`, preserve truthful behavior, and favor an actual working core.

## 1. EXECUTION INSTRUCTION

Build the product end-to-end in this repository, not just architecture notes, mockups, or pseudocode. Create and run the code; integrate real NASA/USGS observations where obtainable; test the behavior; create reproducible documentation and submission assets. Work autonomously using sensible defaults. Do not claim deployment, download success, tests, screenshots, or presentation assets that have not actually been completed. Never fabricate NASA samples or mission results.

Do not ask the operator for routine implementation decisions. Ask only if a blocking choice requires private credentials, unavailable permissions, ownership/confirmation of human-authored concepts, or external public-account actions. There are no credentials required for the basic prototype.

**Priority is a verified core, not feature count.** A polished fake planet map, generic chatbot, invented astronaut telemetry, or pre-drawn route does not satisfy the task.

## 2. PRODUCT REQUIREMENTS

### User stories

- As a mission planner, I can open a **real, georeferenced Jezero terrain map** with optical imagery, topography/slope, geological context, and provenance controls.
- I can select a habitat origin and one or more science targets within validated common data coverage.
- I can view at least two defensibly computed routes: minimum feasible distance and a terrain/uncertainty-aware alternative (they may coincide; if so, disclose this rather than force different paths).
- I can inspect route distance (m), elevation gain/loss (m), maximum raster-derived slope (degrees), route duration estimate (min), and unknown-coverage fraction.
- I can see a round-trip mission feasibility determination with configurable elapsed time and a single illustrative consumable, including a required reserve. Do not present consumable models as astronaut-certified.
- I can inject one simulated blocked corridor from an actual point along the current route; the engine recalculates a route from the current position using the new map and resource balances.
- I can inspect the evidence trail: observation type, mission/instrument, dataset, resolution, observation date where available, units, and whether a result is observed, derived, assumed, simulated, or unknown.
- I can view at least one NASA rover photograph tied to a verified location or clearly labeled contextual rather than falsely geolocated.
- I can see one curated geologic science waypoint with genuine scientific context and a citation.
- I can view a brief atmospheric context panel using a documented historical MEDA record **only if actually ingested**; otherwise clearly label it not yet integrated.
- On desktop or mobile, I can operate the map with keyboard-accessible controls and readable status text; the map alone is not the only way to understand decisions.

### Nonfunctional requirements

- Entire core operates on a standard CPU-only laptop (8 GB RAM target, 16 GB preferred) and can use a single small CPU server or run locally.
- No mandatory paid cloud, proprietary API key, GPU, LLM, training pipeline, ROS 2, or SLAM.
- No internet required after preparation if a local dataset is cached and the app is launched locally.
- Deterministic route planning for fixed data/config; persist run manifest including code version, DEM checksum, assumptions, and coordinates.
- Store raw third-party data as immutable (prefer gitignored `data/raw`) and check source usage terms. Version metadata and derived small samples in the repo when permitted.
- All frontend decisions come from backend computed outputs; no hardcoded results masquerading as algorithms.
- Stable JSON API, typed schemas, input validation, localized error handling, safe request bounds, and zero dependence on an LLM for navigation.

## 3. TECH STACK (DEFAULT)

- **Frontend:** React + TypeScript + Vite; map with Leaflet `CRS.Simple` (pixel/local-map coordinates, explicitly labeled) or another Mars CRS-aware renderer, plus SVG/canvas route/elevation overlays; responsive CSS. Do NOT use Earth Web Mercator geodesics on Mars.
- **Backend:** Python 3.11+ + FastAPI + Pydantic v2; domain modules organized into contexts.
- **Geospatial:** rasterio, GDAL as needed, numpy, pyproj with explicit Mars CRS config, shapely for spatial overlays as appropriate, pandas for curated records.
- **Algorithms:** custom or well-tested 8-neighbor A*; Dijkstra baseline/test oracle; slope and unknown-terrain masking; deterministic resource and contingency evaluation.
- **Testing:** pytest, ruff, mypy (where practical), Vitest/React Testing Library, Playwright or a browser smoke test.
- **Documentation:** Markdown and explicit source manifest; single command or documented separate commands to start backend and frontend.
- **Deployment:** optional static frontend + CPU-only API, or full local dev demonstration; do not invent a public URL.

Prefer standard components over fancy dependencies. Do not introduce distributed services, queues, authentication, databases, model training, real spacecraft autonomy, or a 3D game engine unless all P0 criteria pass first.

## 4. DATA FIRST — REQUIRED AND OPTIONAL

**Required demonstrable NASA mission provenance:**

1. **Topographic:** USGS Astrogeology Mars 2020 Terrain Relative Navigation CTX DTM Mosaic (derived from MRO CTX), ~20 m per pixel; source `https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic`; downloadable TIFF listed in `04_DATA_CATALOG_AND_PIPELINE.md`.
2. **Optical:** Mars 2020 Terrain Relative Navigation CTX orthorectified image mosaic (~6 m/pixel) or legitimately usable Mars Trek imagery, georeferenced to the same area.
3. **Geological:** USGS Geologic Map of Jezero Crater and Nili Planum (Sun & Stack, 2020) with accurately geolocated units or at minimum a documented geologic waypoint and reference. Explain whether feature alignment is regional contextual rather than meter-accurate.

**Recommended if time:** NASA Perseverance raw images and PDS MEDA derived/calibrated historical measurements. Optical, topographic and geological are three distinct data categories; merely displaying three separate image files without aligned context is not sufficient.

**Preprocessing must:** capture exact product links, attribution, file checksum, native projection/units, nodata masks, bounding box, image-to-DEM transform, source dates (when known), and any transformations. DEM and image map coordinates must match within documented spatial error; fail loudly on mismatch.

**Absolutely never:** replace real Mars raster elevations with random heights while labeling them NASA data; treat 20 m cells as astronaut-scale obstacle detection; apply EPSG:3857 or terrestrial WGS84 distances; treat archived MEDA readings as live forecasts; claim a photo is at the mission waypoint without geolocation evidence.

### Data-download blocked fallback

If downloading a specific dataset fails, retry source-discovery using official mirrors, follow the verified data portal, and record the failure. You may run algorithms/tests on a **clearly labeled synthetic terrain fixture**, but the public scientific demonstration must not be portrayed as NASA-derived until real source data is in place. Preserve honest project status in the submission drafts. Favor a real DEM with a simpler background overlay over an attractive fake map.

## 5. IMPLEMENTATION PHASES (DO THESE IN ORDER)

### Phase A — Inspect, plan, initialize
- Review all handoff docs; inspect repository; write `docs/DECISIONS.md` with assumptions and any deviations.
- Create project structure, dependency manifests and lockfiles where supported, backend/frontend test runners, `.env.example` without secrets.
- Add data attribution/provenance JSON schema and avoid checking in unsupported large assets.
- Ensure initial `make test` (or equivalent) runs meaningful synthetic fixtures.

### Phase B — NASA data ingestion and mapping
- Download the source DEM and verify its metadata (coordinates, extent, pixels, units, nodata, hash).
- Choose a **real valid crop in common data coverage**; never hardcode guessed science-site coordinates.
- Compute DEM-derived gradients using real metric cell dimensions; maintain missing data mask.
- Obtain aligned optical imagery or provide a clear fallback to a labelled DEM hillshade with explanation. Add a geologic target sourced from official data and evidence reference.
- Generate a local tile set or a web-friendly clipped raster representation and source manifest. Verify layer alignment with known coordinates.
- Produce a data inspection report (extent, size, percent valid, min/max elevation and sample overlay).

### Phase C — Pathfinder
- Implement A* with 8-neighbor motion, diagonal corner-cutting prevention, nonnegative symmetric/appropriate directed costs, hard slope limits, bounds and no-data exclusions.
- Define distance-only feasible vs terrain-preference cost functions, and calculate total route metrics from the same underlying path geometry.
- Ensure admissible heuristic for the cost function (or use Dijkstra to avoid incorrect optimality claims).
- Calculate elevation gain/loss and path segments in **metres**; distinguish cell-center sampling from true continuous terrain and explain limitations.
- Validate routes against blocked cells after any smoothing (or omit smoothing in MVP).

### Phase D — Guardian
- Define a `MissionPlan` with origin, waypoint(s), movement assumptions, available time, optional consumable budget and reserve fraction.
- Compute outbound + science activity + return. Directional uphill/downhill speed or consumption may be supported, but no pseudo-scientific constants unless traceable; use explicit user-supplied illustrative values.
- Return a typed `FEASIBLE`, `INFEASIBLE`, or `UNKNOWN` status with enumerated reasons and unit-bearing metrics. Unknown coverage cannot silently pass as certain safe terrain.
- Evaluate a selected simulated failure at a specific current position; update resource balances for travel already completed and run return planning on updated cost grid.
- If a feasible revised path cannot be demonstrated, return an explicit failure/status rather than a reassuring fake route.

### Phase E — Frontend
- Build mission command center layout with top-level Mission Overview, Map Layers, Route Comparison, Mission Resource Panel, Contingency Lab and Evidence/Science panel.
- Support zoom, pan, toggles (imagery, elevation, slope, exclusions, geology/context, rover photos), start/goal selection, route line, elevation graph, units, legend, and clear source credits.
- Use route-state and mission-state API responses, not frontend guessed metrics.
- Show `NASA OBSERVATION`, `DERIVED`, `ILLUSTRATIVE MODEL`, `SIMULATED EVENT`, or `UNKNOWN` badges/labels without implying NASA certification.
- Ensure demo works on common laptop viewport; provide clear mobile layout if possible.

### Phase F — Test, report, publish-ready
- Execute all checks in `06_TESTING_AND_ACCEPTANCE.md`; capture output in `docs/VERIFICATION_REPORT.md` with evidence. Tests must use deterministic small fixtures alongside at least one real DEM smoke test.
- Create one reproducible sample mission on real cropped data, make screenshot(s) from running app if possible, and write `docs/DEMO_RUNBOOK.md` detailing exact clicks and expected outputs.
- Prepare submission-ready drafts according to `07_SUBMISSION_CONTENT_TEMPLATES.md`, filling **only observed facts**; include source URLs and an accurate SI disclosure.
- Produce a slide deck of max 7 slides **only if a slide authoring tool exists**; otherwise provide a 7-slide Markdown storyboard ready for conversion. A 30s screencast can be made when recording tools and a functioning UI are available. Never claim that either has been uploaded unless verified.
- Update root README with run commands, sources, methodology, caveats, credits, AI disclosures and working/unimplemented matrix.

## 6. REQUIRED OUTPUT TREE (MINIMUM)

```text
backend/app/{api,domain,application,infrastructure}/
backend/tests/
frontend/src/{components,features,map,api}/
frontend/tests/
scripts/prepare_data.py
scripts/inspect_data.py
config/
data/raw/          # ignored / downloaded; provenance retained
data/processed/    # small, attributed, reproducible; large files ignored
docs/DECISIONS.md
docs/DATA_PROVENANCE.md
docs/ALGORITHM_METHODS.md
docs/ASSUMPTIONS_AND_LIMITATIONS.md
docs/VERIFICATION_REPORT.md
docs/DEMO_RUNBOOK.md
docs/NASA_SUBMISSION_DRAFT.md
README.md
LICENSE/NOTICE as appropriate
```

Also maintain a CLI or Make targets: `setup`, `data`, `test`, `lint`, `dev`, and `build` (or clearly documented npm/python equivalents). The app must not require cloud credentials to run locally.

## 7. HIGH-VALUE ACCEPTANCE CRITERIA — NONNEGOTIABLE

1. **Real data gate:** `docs/DATA_PROVENANCE.md` identifies an actual accessible NASA/USGS Mars instrument product, verified coordinate metadata, a checksum and real sample map/elevation values.
2. **Alignment gate:** optical vs topography map alignment is demonstrated or unaligned layer is intentionally disabled/disclosed.
3. **Route gate:** real terrain cell path computed by A* with distance, elevation and constraints; synthetic tests prove blocked regions cannot be traversed.
4. **Round trip gate:** two-way mission and configured reserve are checked; raising a reserve never turns infeasible into feasible with all else fixed.
5. **Contingency gate:** inject a new obstacle that affects the return, recompute from simulated present position and remaining resources, show changed route **or honest no-feasible-return**.
6. **Provenance gate:** every displayed NASA observation links to a real source; derived/model/simulated results are distinguished.
7. **App gate:** UI calls actual API, usable layout, works locally, no critical JS errors.
8. **Integrity gate:** no made-up experiments, false demo footage, bogus deployment URLs, unlabeled AI visuals, or unlicensed images.
9. **Submission gate:** the human can fill every field from docs; official limit of 7 slides OR 30s video is respected. Public links are for the team to create and verify, not fabricated by the agent.

## 8. ALGORITHM DETAILS

- Raster gradient: with correctly projected metric pixel dimensions (`dx`, `dy`) compute gradient `dz_dx`, `dz_dy` and `slope_deg = degrees(atan(sqrt(dz_dx**2 + dz_dy**2)))`; propagate nodata, use explicit boundary handling.
- A* directed step `i -> j`: validate both cells, check slope threshold for relevant traversed edge (local gradient is an approximation), reject diagonal cutting, compute `step_length_m` from affine transform and `cost = length * (1 + w_s * normalized_slope_penalty + w_u * unknown_penalty)` with nonnegative weights.
- Define unknown policy: by default **block** missing elevation; use optional cautious uncertainty penalty only for known-but-low-confidence mapped cells. Report coverage and uncertainty separately.
- Route alternatives: compute one minimal feasible-distance path and one terrain-weighted path with the same hard exclusions; validate both. Coincident paths are a valid outcome.
- Mission: `total_time = outbound_travel_time + science_time + return_travel_time`, `remaining = initial - consumed_so_far - expected_remaining`, `feasible iff all budgets >= reserves and paths exist`. Direction matters for slope/time modeling; no unjustified numeric environmental constants.
- Emergency: event modifies grid only in the simulated scenario and affects route segment from `current_position`; compute consumed resources for completed segments first.
- Explain: return structured `reason_codes`, e.g. `SLOPE_EXCEEDS_LIMIT`, `NO_ROUTE`, `INSUFFICIENT_TIME`, `INSUFFICIENT_CONSUMABLE`, `UNMAPPED_TERRAIN`, `DATA_UNALIGNED`. Preserve deterministic explanations.

## 9. SCIENCE AND SAFETY DISCLAIMERS

This is a mission-planning research prototype. It is **not certified for actual astronaut EVA navigation or life-support decisions**. 20 m DEMs cannot reveal every small obstacle; historical MEDA data is not a real-time forecast; geology is regional context; the habitat and mission events are simulated. Communicate this in UI, README and submission.

## 10. NASA SUBMISSION ETHICS / ORIGINALITY

The uploaded official 2026 guide states that SI tools may accelerate building but should not be used to originate the team's solution concept. These handoff documents were developed with AI assistance; the human team **must independently own, validate, and substantiate the specific project idea** before claiming it as its original work. Never falsely assert non-use of AI. Disclose the actual use of AI; mark generated visuals visibly; acknowledge generated code/data/audio in descriptive metadata; do not generate/modify NASA logos, flags or mission identifiers. Do not include likenesses of anyone under 18 in submitted media. No team member should sign the site's originality verification without confirming it is true.

## 11. LAST RESPONSE REQUIRED FROM THE CODING AGENT

Provide an evidence-backed completion report:

- What was built and which files changed.
- Real NASA datasets **actually downloaded** and exact provenance/CRS.
- How to start the app and replay the demo.
- Which tests ran, how many passed/failed, any known limitations.
- Screenshots/demos created and their verified paths.
- Missing pieces, blocked work, human actions (public repo/upload/submission/author approval).
- Where to find NASA submission draft and reference list.

**Execute the work. Do not finish with only a plan.**
