# Algorithms and methods

Code: `backend/app/domain/` (`terrain.py`, `navigation.py`, `mission.py`, `contingency.py`).

## 1. Terrain grid and slope

- `TerrainGrid` holds the DEM (`float64`, NaN = no data), the north-up affine origin and cell size, the CRS, and two derived arrays:
  - `dx_row_m[r] = res · cos(lat_r)`: east-west ground length of a cell in row r (equirectangular, true scale at the equator).
  - `dy_m = res`: north-south ground length.
- Slope: `dz/dx = gradient_x(z) / dx_row`, `dz/dy = gradient_y(z) / dy`, `slope = atan(√(dz/dx² + dz/dy²))` in degrees. Central differences span a 40 m baseline, with one-sided differences at the border. Any NaN cell and its 4-neighbours get NaN slope (unknown).
- Unit tests check a tilted plane against the analytic value, the latitude scaling of east-west slope, the unscaled north-south slope, and NaN propagation.

## 2. Pathfinder (8-neighbour A*)

- Traversal mask: passable = known elevation and slope, slope ≤ `max_slope_deg`, and not blocked by the scenario. Unknown cells are impassable unless `unknown_policy = "penalize"`.
- Moves go to the 8 neighbours. A diagonal is allowed only if both orthogonal neighbours are passable, so the path never cuts a blocked corner.
- Step length: horizontal ground distance between cell centres. Diagonal steps use the mean `dx` of the two rows.
- Step cost: `length · (1 + w_s · max(slope_i, slope_j)/max_slope + w_u · unknown)`. All weights are ≥ 0.
- Heuristic: anisotropic octile distance using the smallest `dx` in the grid. Because every step costs at least its horizontal length, the heuristic is admissible and consistent, and A* returns least-cost paths. Tests compare the A* cost with Dijkstra's (`use_heuristic=False`) on 12 random synthetic terrains and two weight settings.
- Two policies share the same hard exclusions:
  - `shortest-feasible`: w_s = 0, minimum ground length.
  - `terrain-aware`: w_s = 3 by default.
- Post-validation (`validate_route`): every cell passable, every step 8-adjacent, no corner cut. An invalid path would be a server error and is never returned. Path smoothing is deliberately disabled (handoff test R-09): the returned path is exactly the validated cell sequence.
- Failure diagnosis: on `NO_ROUTE`, the search is re-run with one constraint relaxed at a time (slope limit, unknown policy, scenario block). This adds `SLOPE_EXCEEDS_LIMIT`, `UNMAPPED_TERRAIN` or `BLOCKED_BY_SCENARIO_EVENT`. A start or goal cell on impassable terrain gives `START_IMPASSABLE` / `GOAL_IMPASSABLE` with the cause.

## 3. Route metrics (from the same cell path)

Length (sum of step ground lengths), elevation gain and loss (sum of positive and negative differences between cell-centre elevations), maximum and length-weighted mean raster slope, maximum step grade, unknown-length fraction, and policy cost. The elevation profile uses the same samples. These are cell-centre samples of a 20 m DEM, not a continuous surface. Real micro-relief adds gain and loss that the DEM cannot see.

## 4. Guardian (mission feasibility)

- Itinerary: habitat → stop 1 … stop n → habitat. Each leg is planned separately with the selected policy, so outbound and return can differ.
- Leg time: `Σ (L / v_flat + max(dz, 0) / v_ascent)`. This is directional: climbing costs time and descending does not.
- Consumable: `traverse_minutes · rate_walk + activity_minutes · rate_stop`.
- `FEASIBLE` if and only if every leg has a route, `total_time ≤ T_available · (1 − reserve)`, and `total_consumable ≤ C_initial · (1 − reserve)`.
- `UNKNOWN` if those checks pass but any route crosses unknown cells (opt-in only).
- Otherwise `INFEASIBLE`, with reason codes.
- Monotonicity: reserve only lowers the usable thresholds, so raising it cannot turn INFEASIBLE into FEASIBLE. This is tested by a sweep on synthetic terrain and on the real DEM.

## 5. Contingency (simulated)

1. Compute the baseline plan and convert it into a timeline of traverse steps and activities.
2. Map the requested elapsed time to the crew position: the last completed step, or a point inside an activity. Read elapsed time and consumption at that instant. Add any simulated consumable loss.
3. Plan the remaining route before the event (return now, or continue the remaining stops and then return).
4. Place a circular blocked zone in ground metres. Either the user picks the centre on the map, or it is placed at a fraction of the remaining path length. Reject the event if it covers the crew.
5. Apply the zone to a copy of the traversal mask (the DEM is never modified) and replan from the current cell.
6. Assess with already-used time and consumable included. Report before and after, the status change, and an event log (`ContingencyInjected`, `RouteReplanned` / `MissionMarkedInfeasible`).

If no route exists, the response says `INFEASIBLE` with `NO_ROUTE` and `BLOCKED_BY_SCENARIO_EVENT`. No placeholder route is returned.

## 6. Determinism and run manifest

No randomness is used at runtime. Heap ties break on (f, g, cell index). Every evaluate or replan response includes a `run_manifest`: code version, study-area id, SHA-256 of `dem_crop.tif`, data processing version, an echo of all parameters, and the parameters' SHA-256. A test checks that two identical replan requests return identical polylines.

## 7. Performance (measured)

On an Intel Core i5-7300U (4 threads), with the 405 × 225 grid:
- One A* leg: about 55-75 ms, expanding 8-12 k cells.
- A full evaluate (two legs, both policies): median 0.207 s over 10 runs.
- A replan: about 0.16 s.
