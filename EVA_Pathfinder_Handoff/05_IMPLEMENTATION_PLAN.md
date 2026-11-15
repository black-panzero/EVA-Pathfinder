# IMPLEMENTATION BOARD — BUILD ORDER, OWNERSHIP & TIME-BOXES

This file is a prioritized build board, not a promise about completion time. Use it to keep an autonomous coding agent focused on demonstrably working features. Deadline from guide: **November 15, 2026, 11:59 p.m. applicable event local time**.

## 1. Build gates

| Gate | Implement | Deliverable | Fallback |
|---|---|---|---|
| G0 | Repo health and tests | `README`, Python/React setup, synthetic tests | Backend CLI only |
| G1 | Mars DEM source | Real georeferenced clip, hash, validated metadata | Alternative official DEM; disclose blocked source |
| G2 | Map & science | Aligned optical + verified geologic context | Hillshade + documented imagery alignment limitation |
| G3 | Pathfinding | Valid A* with actual distance/elevation metrics | CLI computed route and PNG instead of UI |
| G4 | Guardian | Two-way travel budget & reserve | Single time budget (one illustrative consumable optional) |
| G5 | Contingency | Simulated blockage replan from current point | Clearly labeled blocking scenario report |
| G6 | UI and evidence | Interactive map, route comparison, result details | Simple local UI; static screenshots from real computed results |
| G7 | Submission | Public-ready source, docs, demo storyboard, SI disclosures | Manual human publication of accessible links |

**Stop adding optional features until G1–G5 pass.** 2D georeferenced visualization is more important than a cosmetic 3D twin.

## 2. Implementation workstreams

### W1 — Data engineering

- [ ] Download one Mars DEM from official product; record hash and metainformation.
- [ ] Establish Mars native metric coordinates, crop valid shared window.
- [ ] Compute slope, missing-data mask and route cost grid; export artifacts.
- [ ] Add orthorectified optical map and check alignment; cite it.
- [ ] Curate one geological target with sources.
- [ ] Optionally add actual rover photo and historical MEDA record.
- [ ] Record evidence and source provenance; no invented coordinates.

### W2 — Backend domain and algorithms

- [ ] Implement `TerrainGrid`, transform and hard-exclusions.
- [ ] Implement 4/8-neighbor A*, deterministic tie-break, admissible heuristic; Dijkstra test oracle.
- [ ] Metrics length, gain/loss, max slope, estimated travel time.
- [ ] Route alternatives with same hard constraints, distinct policy weights.
- [ ] Round-trip mission evaluator with explicit assumptions and resource reserve.
- [ ] Scenario overlay and mid-mission blockade replan; no-feasible return handling.
- [ ] Typed APIs with bounds/CRS validation, reason codes and evidence.

### W3 — Frontend and visualization

- [ ] Map display with scale, legend, data metadata; no default Earth geodesics.
- [ ] NASA imagery/slope/geology layer toggles with correct alignment/limitations.
- [ ] Habitat/science target selection and tooltips with provenance.
- [ ] Alternative route geometry + elevation plot + metrics table.
- [ ] Guardian feasibility and reserves; explicit simulated labels.
- [ ] Contingency controls; before/after path and explanatory status.
- [ ] Responsive layout, error/loading states, keyboard support.

### W4 — Validation / presentation / compliance

- [ ] Unit + property/metamorphic + integration + real data smoke tests.
- [ ] Log verification runs and environment rather than invent test pass counts.
- [ ] Read and comply with NASA rules, particularly AI/SI disclosure and image assets.
- [ ] Collect screenshots from working app; brief captions and credits.
- [ ] Export ≤7-slide storyboard or 30s video instructions.
- [ ] Draft actual-form summary (50–200 words, <=1500 characters), project details, SI use, NASA/other data, links placeholders.
- [ ] Review all claims and label incomplete items accurately.

## 3. Codex/Claude Code implementation instructions

1. Inspect environment and repo. Install only reasonable dependencies and document versions.
2. **Implement vertical slices:** data -> route CLI -> mission CLI -> minimal UI -> evidence. Do not build a 3D UI before algorithms.
3. Run tests after each slice. Update `docs/VERIFICATION_REPORT.md` with observed commands and outputs.
4. Maintain source-of-truth `docs/DECISIONS.md` and `docs/IMPLEMENTED_FEATURES.md` (working, partial, not started).
5. If data source access fails, make the test environment reproducible using clearly labeled **synthetic tests**, but never substitute that for NASA-derived public demonstration.
6. Prefer documented, reproducible outputs over fancy but brittle integrations.
7. No secrets, public NASA logo generation, unsupported astronaut health constants, or prefilled NASA submission statuses.

## 4. Suggested manual run book

1. `python scripts/prepare_data.py --region auto --source ...` (the agent must implement actual args and document them).
2. `pytest backend/tests` and `npm test`.
3. Start Python API, then frontend with documented commands.
4. Inspect valid 2D Mars raster with source panel.
5. Select start/goal, compare distance and terrain-aware routes.
6. Evaluate a sample four-hour **simulated** mission with stated movement assumptions and reserve.
7. Move simulated crew to a mid-route point and block part of original return path.
8. Replan; record new metrics or explicit infeasibility; open provenance drawer.
9. Capture real screenshot, source credits, repo link, demo storyboard.

## 5. Triage rules for deadline pressure

- First: real DEM + path computation + tests.
- Second: round-trip and contingency calculations.
- Third: science context and visual data layers.
- Fourth: mission-control UI and polished demo.
- Fifth: optional MEDA/photos.
- Last: 3D / LLM / rover integration (do not attempt for hackathon).

If lack of time forces a reduced result, the project description must state **what was actually built** and separate planned work from completed work.
