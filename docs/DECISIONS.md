# Decisions and deviations

Date: 2026-11-15. Author of this build: AI coding agent (Claude Code), working from `01_MASTER_BUILD_PROMPT.md` and `02_PLATFORM_SPECIFICATION.md`.

## Handoff completeness

**Update 2026-11-16:** the full handoff set (03-08, challenge brief, AGENTS.md, CLAUDE.md, example configs, official 2026 guide PDF) arrived in `EVA_Pathfinder_Handoff/`. Four audit agents checked the build against every document; findings and fixes are listed under "Handoff conformance pass" below. The table describes the situation at initial build time.

The master prompt lists ten handoff files. At initial build time only two were present in the repository:

| Expected | Present? | Consequence |
|---|---|---|
| `01_MASTER_BUILD_PROMPT.md` | yes | followed |
| `02_PLATFORM_SPECIFICATION.md` | yes | followed |
| `README.md`, `03_NASA_RULES_AND_SUBMISSION.md`, `04_DATA_CATALOG_AND_PIPELINE.md`, `05_IMPLEMENTATION_PLAN.md`, `06_TESTING_AND_ACCEPTANCE.md`, `07_SUBMISSION_CONTENT_TEMPLATES.md`, `08_DOMAIN_AND_API_CONTRACTS.md`, `NASA_CHALLENGE_BRIEF.md`, `references/NASA_Space_Apps_Project_Submission_Guide_2026.pdf`, `AGENTS.md`/`CLAUDE.md` | **no** | Data URLs were found on the official USGS/NASA/PDS portals. Tests follow the acceptance gates in section 7 of the master prompt. API contracts follow section 10 of the specification. Submission fields in `NASA_SUBMISSION_DRAFT.md` follow the master prompt's description and must be checked against the official 2026 guide, which the agent did not have. |

## Decisions

1. **Study area.** A 405 x 225-cell window (8.1 x 4.5 km projected) of the USGS Mars 2020 TRN CTX DTM. It contains the Octavia E. Butler landing localization, Wildcat Ridge (delta front) and the Three Forks depot. The window offsets are multiples of 3 DEM pixels, so the crop edges fall exactly on 6 m orthomosaic pixel edges with no resampling.
2. **Coordinates are resolved, not typed.** Every waypoint comes from a NASA rover localization record selected by `site/drive` (`config/science_sites.json`). No science-site coordinate is hard-coded.
3. **Ground metres.** The source CRS is equirectangular with true scale at the equator. At about 18.45°N, one projected east-west metre is 0.9486 ground metres. All lengths, slopes, costs and the blocked-zone radius use ground metres. The scale bar is labelled "ground".
4. **Habitat location.** The habitat is placed at the rover's first localization after landing (site 3, drive 0, sol 13). It is a well-documented flat crater-floor point. The habitat itself is labelled SIMULATED everywhere.
5. **Default mission has one stop (Wildcat Ridge).** The Three Forks depot can be added in the UI (multi-stop is supported, maximum 3 stops).
6. **Time model.** A Naismith-style directional rule: horizontal length / flat speed plus ascent / ascent rate. It is traceable as a terrestrial rule of thumb, and every number is a user input labelled ILLUSTRATIVE MODEL.
7. **Consumable.** One generic "illustrative consumable" in generic units with walking and at-stop rates. It is deliberately not called oxygen.
8. **Unknown policy.** No-data blocks by default. An opt-in `penalize` policy lets routes cross unknown cells and then returns `UNKNOWN`, never `FEASIBLE`.
9. **Blocked zone.** A circle in ground metres. It is drawn as an ellipse in projected map space, which is the correct appearance. An event that covers the crew position is rejected (`EVENT_COVERS_CREW`) rather than silently moved.
10. **Position snapping.** A simulated elapsed time snaps back to the last fully completed 20 m step. Elapsed time and consumption are taken at that instant, which is conservative.
11. **Geology status PARTIAL.** USGS SIM 3464 metadata documents random 100-200 m offsets from the surface-operations CTX mosaic. The layer is shown at adjustable opacity with that caveat and is used only for regional context ("units along route").
12. **Optical/DEM alignment.** Both come from the same USGS TRN production, in the same CRS with identical grid origins (0.000 m difference). A gradient cross-correlation check peaked at a (2, 3)-cell shift, r = 0.375 vs 0.268 at zero. Shadows and illumination bias that method, so it is reported as **inconclusive**, not as a measured offset. The independent DEM-vs-rover elevation check is strong (median |Δ| 1.55 m over 252 localizations).
13. **Routes can coincide.** The UI discloses coincident routes instead of forcing them apart. On the default real-data mission they differ (cell-set Jaccard 0.063).
14. **Rover photos.** Only Navcam images whose `site/drive` metadata matches a published localization record are ingested. They are shown as ground views at that rover position, not as overhead footprints.
15. **MEDA.** One historical sol (684, during depot operations) of derived pressure (Pa) and upward long-wave irradiance (W/m²), aggregated hourly. Labelled as history, not a forecast. TIRS derived files contain irradiance, not air temperature, so no temperature is shown.
16. **No licence chosen for the code.** That is a human decision. `NOTICE.md` records data credits.
17. **Environment.** ROS 2 Humble on the host injects pytest plugins through `PYTHONPATH`. The Makefile runs Python with `PYTHONPATH` unset and plugin autoload disabled.

## Bugs found by the tests and fixed

- Central-difference slope skipped the centre cell, so a no-data cell got a finite slope and would have been treated as known terrain. Fixed: NaN cells and their 4-neighbours now get NaN slope, and the traversal mask also checks elevation directly.
- A request containing `NaN` produced a 500, because the validation error tried to echo NaN as JSON. Fixed: the validation handler returns 422 without echoing the input.
- In the browser, clicking a marker while in "pick zone" mode was swallowed by the marker, so the zone could not be placed on the habitat. Fixed: markers and paths ignore pointer events while picking. Verified with Playwright.

## Handoff conformance pass (2026-11-16)

Four parallel read-only audits checked the build against every handoff document. The verdict was that the core holds: real data, Mars CRS, validated routing, round-trip feasibility, honest contingency and provenance. No rebuild was needed; the gaps below were fixed.

| Document | Gap found | Fix |
|---|---|---|
| 03 + 2026 guide PDF | No title slide in the storyboard; video script lacked team/challenge intro; AI disclosure only in docs, not in the project; credits incomplete; stale or over-strong wording ("safety reserve", "Live demo") | 7-slide storyboard with title slide; timed 30 s script; disclosure in the app rail, the guide, a meta tag, `package.json` and `docs/SI_DISCLOSURE.md`; Pyodide, fonts, icons and test libraries credited; "planning reserve" wording; planned URL labelled not live |
| 04 data catalog | No per-product `data/source_manifest.json`; DOIs missing; DTM caveats missing; three sources marked verified without hashes; no georeferenced slope/coverage/ortho GeoTIFFs; MEDA quality info not reported | All added by `scripts/prepare_data.py`. Every derived value is unchanged byte for byte. The 8.1 × 4.5 km window (vs a 2-4 km suggestion) is kept and justified in `manifest.json` `deviations` |
| 05 plan | `docs/IMPLEMENTED_FEATURES.md` missing; smoothing status undocumented | Added; smoothing documented as deliberately disabled (R-09) |
| 06 tests | About 12 IDs without explicit tests; verification report stale | `backend/tests/test_handoff_acceptance.py` (21 tests). The new D-05 test caught a real gap: the pamphlet source had no producer. Fixed. Report refreshed |
| 08 contracts | Field names, request shapes and error codes differed from the contract | Added without breaking anything: both request shapes accepted, contract fields added to responses, `error.contract_code`, `map_contract`, row/col cells, `SIMULATED_BLOCKAGE`, mission template translation, `MissionState` enum (`test_contracts_v08.py`, 24 tests). Not done: an authority (IAU/EPSG) `crs_id` (a documented local-frame id is used instead), acquisition dates (not in the source metadata), and a persistent mission store |
| AGENTS.md / CLAUDE.md | Not at the repo root | Copied to the root together with the handoff documents 03-08 and the challenge brief |
| UI (user request) | Interface hard to navigate | Redesigned as a five-step workflow with a first-visit guide, a map view switcher and provenance dots. Keyboard and mobile operation are smoke-tested |

**Deploy:** the custom domain `midgardians.darelladero.tech` is set through `frontend/public/CNAME`, and the static build uses base path `/`.
