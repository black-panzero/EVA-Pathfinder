# DOMAIN, API & DATA CONTRACTS — EVA PATHFINDER

The coding agent should implement type-safe, versioned Pydantic DTOs consistent with these examples. **Examples are schemas or synthetic examples** until real NASA coordinates are available. Never mistake them for observed Mars results.

## 1. Coordinate and map contract

```json
{
  "body": "Mars",
  "crs_id": "source_specific_mars_projected_crs",
  "coordinate_units": "m",
  "latitude_convention": "planetocentric",
  "longitude_direction": "east_positive",
  "longitude_domain": "-180_to_180",
  "raster_transform": "affine_as_read_from_source",
  "source_dataset_id": "ctx_dem_jezero_trn_2020",
  "resolution_m": 20,
  "status": "UNVERIFIED_EXAMPLE"
}
```

The actual CRS must come from the source GeoTIFF and be inspected before replacing `source_specific_*` placeholders. App interaction may use `{row, col}` on the selected grid as internally unambiguous locators; always convert to map metres via the dataset affine transform before showing physical distances.

## 2. Typed value objects and invariants

- `MapGridCell(row:int, col:int)` — validated inside grid; nodata excluded.
- `MapPoint(x_m:float,y_m:float,crs_id:str)` — map coordinates in body-specific projection; CRS match enforced.
- `ScienceSite(id, point, objective, sources, geolocation_accuracy)` — contextual if only regional location known.
- `TerrainPolicy(max_derived_slope_deg, unknown_policy, slope_weight, uncertainty_weight)` — all weights nonnegative; no arbitrary safety ratings.
- `TraversalProfile(assumed_speed_m_min, activity_consumable_rate_per_min, travel_consumable_rate_per_min, consumable_unit, reserve_fraction)` — explicitly simulated and unit-bearing.
- `MissionPlan(origin, stops, budget, route_policy, source_manifest_ids)` — origin and stops bounded.
- `Route(path_cells, geometry, metrics, confidence, evidence)` — no invalid cell crossing, geometric and numerical consistency.
- `MissionAssessment(status, reason_codes, time_minutes, consumable_remaining, reserve_requirements, outbound, return, assumptions, evidence)`.
- `ContingencyEvent(kind, affected_cells/geometry, current_position, event_time_or_progress, assumptions)` — scenario only.
- `MissionExecution(state, consumed_so_far, current_position, immutable_event_log)`.

Domain errors: `INVALID_COORDINATES`, `CRS_MISMATCH`, `NO_DATA_COVERAGE`, `UNALIGNED_SOURCE`, `NO_ROUTE`, `INSUFFICIENT_TIME`, `INSUFFICIENT_CONSUMABLE`, `INVALID_MISSION_CONFIGURATION`, `SOURCE_UNAVAILABLE`.

## 3. HTTP API design

### `GET /health`

Returns `{"status":"ready"|"degraded","dataset_status":"AVAILABLE_VERIFIED"|"PARTIAL"|"UNAVAILABLE"}` based on real state, not hardcoded success.

### `GET /api/v1/datasets`

List available source IDs and metadata: product, mission, instrument, body, CRS, bounds, resolution/units, status, source URL, file hash, creation/acquisition date, limitations.

### `GET /api/v1/science-sites`

`{"sites":[{"id":"site-01","objective":"observe documented delta geological context","location_status":"contextual_or_verified","map_point":null,"source_urls":["https://..."],"notes":"..."}]}`

If `map_point` is null, the UI must not pretend there is a precisely pinned site; the team/agent must choose a verified or explicitly hypothetical map point within the valid crop for a mission.

### `POST /api/v1/routes/compare`

**Request, synthetic grid-cell example:**

```json
{
  "dataset_id": "ctx_dem_jezero_trn_2020",
  "origin": {"row": 12, "col": 14},
  "destination": {"row": 90, "col": 111},
  "max_derived_slope_deg": 25.0,
  "unknown_policy": "BLOCK",
  "policies": ["MIN_DISTANCE", "TERRAIN_WEIGHTED"],
  "weights": {"slope": 2.0, "uncertainty": 1.0}
}
```

The sample row/column values are **not yet validated as a real scientific mission**. Return calculated routes when the requested grid exists and coordinates are valid; otherwise return typed errors.

**Response structure:**

```json
{
  "dataset_id": "ctx_dem_jezero_trn_2020",
  "computed_from_real_data": false,
  "route_candidates": [],
  "reason_codes": ["SOURCE_UNAVAILABLE"],
  "evidence": [],
  "model_limitations": ["20 m DEM cannot resolve human-scale obstacles"]
}
```

For success, return `route_candidates` with policy, `polyline_map_m`, `path_cells`, `distance_m`, `elevation_gain_m`, `elevation_loss_m`, `max_derived_slope_deg`, `unknown_fraction`, `model_minutes`, `total_cost`, `reason_codes`; `computed_from_real_data` must be true **only after confirmed ingestion**.

### `POST /api/v1/missions/evaluate`

**Request structure:**

```json
{
  "dataset_id": "ctx_dem_jezero_trn_2020",
  "origin": {"row": 12, "col": 14},
  "science_stops": [{"id": "site-01", "row": 90, "col": 111, "activity_minutes": 20}],
  "traversal": {
    "assumed_speed_m_per_min": 30.0,
    "consumable_name": "illustrative_resource_units",
    "consumption_rate_per_min": 1.0
  },
  "budget": {"max_minutes": 240.0, "initial_consumable_units": 240.0, "reserve_fraction": 0.25},
  "terrain_policy": {"max_derived_slope_deg": 25.0, "unknown_policy": "BLOCK"}
}
```

**CAUTION:** All model numbers are illustrative coding test inputs, not validated astronaut parameters. Actual evaluation must compute outbound AND return geometry and sum activity costs and previous consumption.

**Response success/failure schema:**

```json
{
  "status": "FEASIBLE_OR_INFEASIBLE_OR_UNKNOWN",
  "reason_codes": [],
  "outbound_route_id": null,
  "return_route_id": null,
  "total_duration_min": null,
  "estimated_consumable_remaining_units": null,
  "minimum_required_reserve_units": null,
  "assumptions": [],
  "evidence": [],
  "warnings": []
}
```

### `POST /api/v1/scenarios/replan`

```json
{
  "mission_id": "delta-return-01",
  "scenario_id": "blocked-corridor-01",
  "current_grid_cell": {"row": 60, "col": 60},
  "already_elapsed_minutes": 75.0,
  "already_used_consumable_units": 75.0,
  "event": {"kind": "SIMULATED_BLOCKAGE", "blocked_cells": [{"row": 61, "col": 60}]}
}
```

Validate current position and event location against active dataset; a blocked path may or may not force a different route depending on placement. For the documented demo fixture, choose a blockage that deterministically intersects the active return route. Return baseline vs alternative, reason codes, remaining budget, and evidence that blockage was simulated.

### `POST /api/v1/reports`

Returns a machine-readable mission audit: source manifest, model build version, source hashes, study extent/CRS, route alternatives and metrics, mission resource constraints, scenario event, final status, assumptions and unknowns. Optionally PDF/JSON export if implemented; JSON is MVP.

## 4. Events and status transitions

`PLANNED -> ROUTE_EVALUATED -> READY_UNDER_MODEL -> OUTBOUND_SIMULATED -> SCIENCE_SIMULATED -> RETURNING_SIMULATED -> COMPLETED_SIMULATED`.

Any step may transition to `REPLANNING` following scenario injection; then to `READY_UNDER_MODEL`, `INFEASIBLE`, or `UNKNOWN` with reasons. Use **simulated** state names rather than implying astronaut tracking.

## 5. Data versioning and provenance

For every computed route, include `route_policy_version`, `source_artifact_hash`, `config_hash`, study area bounds, Mars CRS and dataset status; all events append to a serializable trace for reproducibility. A scenario must never change authoritative raw DEM bytes.
