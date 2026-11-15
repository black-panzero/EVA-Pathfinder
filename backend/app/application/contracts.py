"""08 contract helpers (no HTTP, no raster I/O): map/CRS contract block, dataset id aliases,
contract error codes, provenance hashes. Shared by the FastAPI server and the Pyodide bridge."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from ..domain.terrain import TerrainGrid

DEM_SOURCE_ID = "usgs-m2020-trn-ctx-dtm-20m"
# 08 uses `ctx_dem_jezero_trn_2020` for the CTX DEM; it is an alias of our source id.
DATASET_ALIASES: dict[str, str] = {"ctx_dem_jezero_trn_2020": DEM_SOURCE_ID}
CONTRACT_ID_FOR_SOURCE: dict[str, str] = {v: k for k, v in DATASET_ALIASES.items()}
# Sources whose verification decides /health dataset_status (terrain, base imagery, site localizations).
CORE_SOURCE_IDS: tuple[str, ...] = (DEM_SOURCE_ID, "usgs-m2020-trn-ctx-ortho-6m", "nasa-m2020-waypoints")
ROUTE_POLICY_VERSION = "eva-route-policy/1.0 (8-neighbour A*, cost = length*(1 + w_s*slope/max + w_u*unknown))"
CRS_ID_PREFIX = "eva-local-eqc-mars2000-sphere"
MODEL_LIMITATIONS = [
    "20 m DEM cannot resolve human-scale obstacles (rocks, small scarps, soil strength).",
    "Slope is derived from a 40 m central-difference baseline on the DEM.",
    "Traversal speeds, consumable rates and reserves are illustrative inputs, not validated astronaut parameters.",
    "Static historical orbital data; no real-time hazards.",
]

# Legacy error.code -> 08 error.contract_code
_CONTRACT_CODES: dict[str, str] = {
    "INVALID_COORDINATE": "INVALID_COORDINATES", "INVALID_COORDINATES": "INVALID_COORDINATES", "OUT_OF_BOUNDS": "INVALID_COORDINATES",
    "SAME_START_GOAL": "INVALID_COORDINATES", "EVENT_COVERS_CREW": "INVALID_COORDINATES",
    "NO_DATA_COVERAGE": "NO_DATA_COVERAGE", "CRS_MISMATCH": "CRS_MISMATCH", "UNSUPPORTED_PROJECTION": "CRS_MISMATCH",
    "UNALIGNED_SOURCE": "UNALIGNED_SOURCE", "DATA_UNAVAILABLE": "SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE": "SOURCE_UNAVAILABLE",
    "LAYER_NOT_FOUND": "SOURCE_UNAVAILABLE", "UNSUPPORTED_DATA": "SOURCE_UNAVAILABLE",
    "INVALID_INPUT": "INVALID_MISSION_CONFIGURATION", "INVALID_POLICY": "INVALID_MISSION_CONFIGURATION", "NO_STOPS": "INVALID_MISSION_CONFIGURATION",
    "TOO_MANY_STOPS": "INVALID_MISSION_CONFIGURATION", "BASELINE_INFEASIBLE": "INVALID_MISSION_CONFIGURATION",
    "MISSION_ALREADY_COMPLETE": "INVALID_MISSION_CONFIGURATION", "NO_REMAINING_ROUTE": "NO_ROUTE",
    "INVALID_MISSION_CONFIGURATION": "INVALID_MISSION_CONFIGURATION", "UNKNOWN_MISSION": "INVALID_MISSION_CONFIGURATION",
}


def contract_code(code: str) -> str | None:
    return _CONTRACT_CODES.get(code)


def resolve_dataset_id(dataset_id: str) -> str:
    return DATASET_ALIASES.get(dataset_id, dataset_id)


def contract_dataset_id(source_id: str) -> str:
    return CONTRACT_ID_FOR_SOURCE.get(source_id, source_id)


def normalize_lon_180(lon: float) -> float:
    """Longitude in the 08 domain [-180, 180), east-positive."""
    v = ((lon + 180.0) % 360.0) - 180.0
    return 0.0 if v == 0 else v


def crs_id_for(manifest: dict) -> str:
    return f"{CRS_ID_PREFIX}:{manifest.get('study_area_id', 'unknown')}"


def source_status(manifest: dict, source_id: str) -> str:
    return (manifest.get("source_status") or {}).get(source_id, {}).get("status", "UNAVAILABLE")


def computed_from_real_data(manifest: dict, grid: TerrainGrid, dem_sha256: str) -> bool:
    """True only after confirmed ingestion: verified DEM source and the loaded crop matches the
    checksum recorded when the crop was prepared."""
    if grid.dataset_id != DEM_SOURCE_ID or source_status(manifest, DEM_SOURCE_ID) != "AVAILABLE_VERIFIED":
        return False
    art = next((a for a in manifest.get("artifacts", []) if a.get("artifact_id") == "dem-crop"), None)
    return bool(art and art.get("checksum_sha256") and art["checksum_sha256"] == dem_sha256)


def map_contract(manifest: dict, grid: TerrainGrid) -> dict:
    """08 section 1 coordinate/map contract for the active study area."""
    real = grid.dataset_id == DEM_SOURCE_ID
    w, h = grid.extent_xy_m
    lon0, lat0 = grid.cell_lonlat(grid.height - 1, 0)
    lon1, lat1 = grid.cell_lonlat(0, grid.width - 1)
    crs = manifest.get("crs") or {}
    return {
        "body": "Mars",
        "crs_id": crs_id_for(manifest),
        "crs_definition": "Local metric frame of the study-area crop: x_m = projected easting - west-edge easting, y_m = projected northing - south-edge northing, "
                          "in the source Equirectangular projection on the Mars 2000 sphere (R = 3396190 m, lat_ts = 0, lon_0 = 0).",
        "source_crs_name": crs.get("name") if real else "synthetic test fixture (no source CRS)",
        "projected_origin_m": {"easting_west_edge": grid.origin_e_m, "northing_south_edge": grid.origin_n_bottom_m},
        "coordinate_units": "m",
        "latitude_convention": "planetocentric",
        "longitude_direction": "east_positive",
        "longitude_domain": "-180_to_180",
        "raster_transform": "affine_as_read_from_source" if real else "synthetic_north_up",
        "source_dataset_id": contract_dataset_id(grid.dataset_id),
        "resolution_m": grid.res_m,
        "bounds_xy_m": [[0.0, 0.0], [w, h]],
        "lon_range_deg": [round(normalize_lon_180(lon0), 6), round(normalize_lon_180(lon1), 6)],
        "lat_range_deg": [round(lat0, 6), round(lat1, 6)],
        "grid_shape": {"rows": grid.height, "cols": grid.width},
        "status": source_status(manifest, DEM_SOURCE_ID) if real else "SYNTHETIC_FIXTURE",
    }


def config_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()


def finite_or_none(v: float | None, n: int = 2) -> float | None:
    return None if v is None or not math.isfinite(v) else round(float(v), n)
