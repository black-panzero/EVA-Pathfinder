# Demo runbook: Operation Delta Return

Expected values below come from the real-DEM runs in `VERIFICATION_REPORT.md`, with the default inputs.

## Start

```bash
make setup     # once: venv + npm packages
make data      # once: downloads (~400 MB raw, mostly the geology zip), verifies checksums, prepares data
make dev       # API on http://127.0.0.1:8000, UI on http://127.0.0.1:5173
```

Open http://127.0.0.1:5173. No internet is needed after `make data`.

## Click path (about 3 minutes)

1. **Orientation.** Point out the header (study area, lat/lon range, "DEM: USGS CTX 20 m · 100.0% valid", "6 sources verified by checksum") and the disclaimer bar. The map shows the real CTX orthomosaic. The H marker is the simulated habitat at the landing localization; the ▣ markers are rover photo positions.
2. **Plan.** On load, the Guardian panel shows **FEASIBLE**: 216 / 315 min usable and 192 / 375 consumable units usable. The orange route is terrain-aware; the dashed cyan route is shortest feasible.
3. **Compare routes.** In the Route comparison panel: round trip 5,751 m (shortest) vs 5,969 m (terrain-aware), max slope 15.0° vs 12.5°, and the elevation profile with the climb onto the delta front.
4. **Layers.** Tick *Slope* to show the steep delta scarp in red. Tick *Geologic units* and point out the legend caveat (100-200 m offsets, regional context). Tick *Perseverance traverse* to show the real rover path.
5. **Feasibility logic.** Set *Reserve* to 50 and click **Evaluate Marswalk**. The result is **INFEASIBLE** with `INSUFFICIENT_TIME`. Set it back to 25.
6. **Slope limit.** Set *Max slope* to 8 and evaluate. The result is INFEASIBLE with `SLOPE_EXCEEDS_LIMIT` and `GOAL_IMPASSABLE`, because the Wildcat Ridge cell itself is steeper than 8°. Set it back to 15 and evaluate.
7. **Contingency.** In the Contingency lab the progress slider defaults to about 30 % into the return leg (2 h 43 min). Leave the radius at 250 m and click **Inject blocked zone and replan**.
   - On the map: green C (simulated crew), red ellipse (simulated zone), green replanned route detouring south of the zone.
   - In the panel: before and after assessments, "Status change: FEASIBLE -> FEASIBLE", and the event log.
8. **Honest failure.** Click **Pick zone on map**, click on the H habitat, set the radius to 200 and inject again. The result is **FEASIBLE -> INFEASIBLE** with `NO_ROUTE` and `BLOCKED_BY_SCENARIO_EVENT`; no fake route is drawn.
9. **Evidence.** In Science & evidence:
   - *Science*: Wildcat Ridge text with NASA citations, and the mapped unit with its caveat.
   - *Rover photos*: Navcam from sols 502 and 684, geolocated by site/drive.
   - *Atmosphere (history)*: MEDA sol 684 pressure.
   - *Sources & alignment*: checksums and alignment statistics.
   - *Evidence labels*: the run manifest with the DEM SHA-256.
10. **Report.** Click **Download report JSON** to get a full provenance and result bundle.

## 30-second video cut (if recorded)

Steps 2 → 4 (slope) → 7 → 8, with captions "Real NASA/USGS terrain", "Computed, not drawn", "Simulated event, honest result".

## Troubleshooting

- "Cannot reach the API": run `make api` and check http://127.0.0.1:8000/health.
- `/health` returns 503 / `data_ready: false`: run `make data`.
- pytest fails with `lark` / `launch_testing` errors: a ROS installation is on `PYTHONPATH`. Use the Makefile targets, which unset it.
