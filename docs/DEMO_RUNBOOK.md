# Demo runbook: Operation Delta Return

Expected values below come from the real-DEM runs in `VERIFICATION_REPORT.md`, with the default inputs.

## Start

```bash
make setup     # once: venv + npm packages
make data      # once: downloads (~400 MB raw, mostly the geology zip), verifies checksums, prepares data
               # (scripts/prepare_data.py; only flag is --offline = never download, use cached raw files)
make dev       # API on http://127.0.0.1:8000, UI on http://127.0.0.1:5173
```

Open http://127.0.0.1:5173. No internet is needed after `make data`.

## Click path (about 3 minutes)

The left rail lists five steps, and each step has **Back / Next** buttons at the bottom of the right panel. The map stays visible throughout.

1. **Guide.** On first visit a short "How it works" guide explains the five steps. Click **Start planning**. It can be reopened from the top bar.
2. **Plan (step 1).**
   - Point out the start point (H, simulated habitat at Perseverance's landing position) and the science stops (Wildcat Ridge is selected).
   - Show the three limits: steepest slope 15°, time 420 min, reserve 25%. Further assumptions sit under "More assumptions".
   - Routes are computed automatically on load. Click **See routes**.
3. **Routes (step 2).**
   - Two route cards: terrain-aware 5.97 km, steepest 12.5°; shortest 5.75 km, steepest 15.0°.
   - On the map toolbar click **Slope**. The red delta scarp shows why the routes bend. Click **Geology** to show the units (the legend notes the ±100-200 m offset), then **Photo** to go back.
   - The elevation profile shows the climb onto the delta front. Click **Next: Feasibility**.
4. **Feasibility (step 3).** The panel shows **Feasible** and "The crew gets back with 99 min to spare before the reserve". Below that are the budget bars with the dashed reserve mark, then the timeline.
5. **Break it.** Go **Back** to step 1 and set **Safety reserve** to 50. Click **Compute routes**, then go to Feasibility: it shows **Infeasible** with `INSUFFICIENT_TIME`. Set the reserve back to 25 and recompute.
6. **Contingency (step 4).**
   - Leave the defaults: 2 h 43 min into the walk, 250 m zone at 50% of the remaining route, "Head home now".
   - Click **Run scenario**. The map shows the green C (crew), a red simulated zone and a green new path home. The panel shows the before/after table.
7. **Honest failure.**
   - Click **Place the zone on the map instead**, click on the H, set the radius to 200 and **Run scenario**.
   - Result: Feasible → **Infeasible** with `NO_ROUTE` and `BLOCKED_BY_SCENARIO_EVENT`. No path is drawn.
8. **Evidence (step 5).** Use the tabs:
   - **Science**: cited NASA sources.
   - **Rover photos**: Navcam from sols 502 and 684. Camera markers on the map open these too.
   - **Weather history**: MEDA sol 684.
   - **Data sources**: checksums and alignment.
   - **Labels**: the run manifest.
9. **Report.** Click **Report** in the top bar to download the JSON evidence bundle.

## 30-second video cut (if recorded)

See the timed script in `docs/NASA_SUBMISSION_DRAFT.md` ("30-second video script"). It opens with the team and challenge and ends with limits and future work, as the 2026 guide asks.

## Troubleshooting

- "Cannot reach the API": run `make api` and check http://127.0.0.1:8000/health.
- `/health` returns 503 / `data_ready: false`: run `make data`.
- pytest fails with `lark` / `launch_testing` errors: a ROS installation is on `PYTHONPATH`. Use the Makefile targets, which unset it.
