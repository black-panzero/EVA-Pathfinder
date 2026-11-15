# QUALITY GATES — TESTING, EVIDENCE & DEFINITION OF DONE

The goal is **reproducible correctness**, not unverified claims of astronaut safety. Both synthetic controlled test fixtures and one real NASA/USGS data smoke test are required; synthetic results must never be passed off as observed Mars facts.

## 1. Automated unit tests — terrain

| ID | Test | Expected behavior |
|---|---|---|
| T-01 | Flat constant DEM in metric coordinates | slope is approximately zero, boundaries handled |
| T-02 | Linear ramp `z = ax + by` | slope matches `atan(sqrt(a²+b²))` within numeric tolerance |
| T-03 | Nodata strip or NaN | masked cells excluded, no phantom passages |
| T-04 | Non-square pixel metric spacing | correct dx/dy and path lengths |
| T-05 | Rotated affine grid or unsupported CRS | valid affine computation or explicit rejection (never silent wrong distances) |
| T-06 | Route start outside crop | input validation error |
| T-07 | Map product with Earth CRS unexpectedly | reject or require explicit validated Mars transform |

## 2. Automated route tests

| ID | Test | Expected behavior |
|---|---|---|
| R-01 | Open 5x5 uniform grid | route is shortest under chosen neighborhood |
| R-02 | Known obstacle corridor | no path crosses any hard blocked cell |
| R-03 | Diagonal corner closure | cannot cut through two adjacent blocked orthogonal neighbors |
| R-04 | Completely separated start/goal | `NO_ROUTE` status, no fake geometry |
| R-05 | Small grid with terrain weights | A* agrees with Dijkstra cost (within numerical tolerance) |
| R-06 | Identical policies produce same route | report coincidence honestly; don't force different alternatives |
| R-07 | Lower-cost weights are nonnegative | heuristic admissible; computed total cost ≥ straight-line distance |
| R-08 | Elevation gain/loss | match hand-calculated path profile |
| R-09 | Path smoothing if enabled | revalidate no excluded cell traversal; otherwise disable smoothing |

Use seeded map fixtures with known values; compare route geometry, cost and state, not only a drawn SVG.

## 3. Guardian mission tests

| ID | Test | Expected behavior |
|---|---|---|
| G-01 | Outbound and return fit budgets | `FEASIBLE` under explicitly labeled model |
| G-02 | Outbound fits, return exceeds time | `INFEASIBLE` + `INSUFFICIENT_TIME` |
| G-03 | Insufficient illustrative consumable | `INFEASIBLE` + `INSUFFICIENT_CONSUMABLE` |
| G-04 | Increase reserve, other inputs same | feasible set cannot expand |
| G-05 | Increase scientific activity duration | total modeled time cannot decrease |
| G-06 | Block return after halfway and replan | starts at actual simulated current position, not original target |
| G-07 | New return route longer than remaining allowance | infeasible, not reassured |
| G-08 | Original outbound becomes blocked but alternate exists | recompute; log old/new route and reasons |
| G-09 | No reliable source map available | `UNKNOWN`/not ready, not `FEASIBLE` |
| G-10 | Negative budgets/NaN speed/invalid events | request rejected, no runtime exception |

Mission estimates are a **simplified modeling exercise**. Do not label as validated EVA physiology or NASA procedures.

## 4. Data/observations tests

| ID | Test | Expected behavior |
|---|---|---|
| D-01 | Real raw DEM open | non-empty valid cells; metadata and SHA-256 recorded |
| D-02 | DEM extent and science target | target inside valid study window; coordinates have Mars convention |
| D-03 | Optical/geology overlay | demonstrable spatial correspondence or explicitly disabled/unverified |
| D-04 | Height and slope calculation | spot-check elevation samples and slope gradients against independent method |
| D-05 | Source manifest | URL, product name, agency, original/derived, license review and caveat exist |
| D-06 | Rover image location | geolocated only with verified metadata; otherwise context-only label |
| D-07 | Atmospheric record | historical timestamp/sol and place/sensor displayed; never real-time claim |
| D-08 | Source not downloaded | status not labeled as available or verified |

## 5. API + UI acceptance

- API returns valid versioned schemas with units and deterministic reason codes. Limit request cell count/waypoint count and reject invalid projections/bounds.
- Browser displays **actual** source data layers and source names, not generated terrain presented as NASA imagery.
- Map selection -> backend route computation -> mission assessment -> contingency replanning occurs end to end.
- Distinct routes shown only when algorithms produce them; if coincident, a legitimate shared route is displayed.
- Route elevations and budget values match API outputs and provenance trail.
- Keyboard usable controls; readable legends, scales, statuses and alternative text; no color-only warnings.
- Check desktop layout; mobile/tablet usable as optional enhancement.
- No uncaught API/JS errors during demo script.
- Public assets attributed and licensed; optional external-host images don't block functionality.

## 6. Performance targets (aspirational; measure, never fabricate)

On a stated CPU-only machine and a 2–4 km region of 20 m DEM (typical ~100–200 cells per side): one candidate route calculation should be interactive and ideally under a few seconds. Record actual machine, input grid dimensions and timings. No performance claim without measurements.

## 7. Reproducibility package

`docs/VERIFICATION_REPORT.md` must include:

- Git commit SHA or source version; OS, Python/Node/dependency versions.
- NASA product title, source URL, file hash, crop bounds/CRS, valid percentages.
- Exact scenario config, start/goal coordinates, resource model parameters.
- Commands executed and actual stdout/test summary, timestamps and exit codes.
- Before/after route length and elevations, resource calculation, event type and status.
- Actual screenshots/recordings source; whether public link verified; things not completed.
- Methodology and critical limitations (20 m resolution, small hazards unresolved, simulated inputs).

## 8. Submission and integrity acceptance

- [ ] Project summary reflects actual code behavior, is <=1500 characters, and uses 50–200 words if possible.
- [ ] Full valid public project URL verified by independent access.
- [ ] Demo exists, publicly accessible, <=30 seconds video or <=7 slides (title included).
- [ ] NASA Data field contains actually used sources with complete HTTPS URLs.
- [ ] Third-party references and all image/code/text sources credited.
- [ ] AI/SI disclosure correct; SI-generated assets marked as guide requires.
- [ ] Human participant verified original work assertion before clicking Submit for Judging.

**DoD:** The project has a verifiable Mars-derived spatial foundation, reproducible navigation and Guardian results, an honest NASA-compliant description, and a functioning local interface. Public posting and actual submission require separate human confirmation.
