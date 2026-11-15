"""Cartography & Terrain context.

`TerrainGrid` encapsulates the DEM raster, its affine geometry and the derived slope layer so
callers never pass raw arrays and transforms around separately.

Coordinate conventions
----------------------
* Source CRS: Equirectangular, Mars 2000 sphere (R = 3 396 190 m), latitude of true scale 0,
  central meridian 0. Projected easting E = R * lon_rad, northing N = R * lat_rad.
* Local frame used by the API: x_m = E - origin_easting, y_m = N - origin_northing_bottom
  (projected metres, north-up, origin at the south-west corner of the study area).
* True ground distances: north-south projected metres equal ground metres on the sphere; east-west
  ground metres are projected metres * cos(latitude). Every length, slope and cost in this package
  uses ground metres (`dx_row_m`, `dy_m`), never raw projected east-west metres and never EPSG:3857.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MARS_RADIUS_M = 3_396_190.0


class TerrainError(ValueError):
    """Raised for invalid coordinates or unsupported terrain data."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def compute_slope_deg(z: np.ndarray, dx_row_m: np.ndarray, dy_m: float) -> np.ndarray:
    """Slope in degrees using central differences (one-sided at the grid border).

    `dx_row_m` holds the east-west ground length of one cell for every row (it varies with
    latitude). NaN elevations propagate: any cell whose stencil touches NaN gets NaN slope.
    """
    if z.ndim != 2:
        raise ValueError("elevation must be 2-D")
    dzdx = np.gradient(z, axis=1) / dx_row_m[:, None]
    dzdy = np.gradient(z, axis=0) / dy_m
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    # Central differences skip the centre cell, so explicitly mark NaN cells and their 4-neighbours
    # (whose stencils include the NaN) as unknown.
    bad = ~np.isfinite(z)
    if bad.any():
        grow = bad.copy()
        grow[1:, :] |= bad[:-1, :]
        grow[:-1, :] |= bad[1:, :]
        grow[:, 1:] |= bad[:, :-1]
        grow[:, :-1] |= bad[:, 1:]
        slope[grow] = np.nan
    return slope


@dataclass
class TerrainGrid:
    dataset_id: str
    elevation_m: np.ndarray  # (rows, cols), NaN = unknown
    origin_e_m: float  # projected easting of the west edge
    origin_n_m: float  # projected northing of the north edge
    res_m: float  # projected cell size (square)
    crs_wkt: str = ""
    lat_row_deg: np.ndarray = field(init=False)
    dx_row_m: np.ndarray = field(init=False)
    dy_m: float = field(init=False)
    slope_deg: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        if self.elevation_m.ndim != 2:
            raise TerrainError("UNSUPPORTED_DATA", "elevation must be a 2-D array")
        self.elevation_m = self.elevation_m.astype("float64", copy=False)
        rows = np.arange(self.height)
        n_center = self.origin_n_m - (rows + 0.5) * self.res_m
        self.lat_row_deg = np.degrees(n_center / MARS_RADIUS_M)
        self.dx_row_m = self.res_m * np.cos(np.radians(self.lat_row_deg))
        self.dy_m = float(self.res_m)
        self.slope_deg = compute_slope_deg(self.elevation_m, self.dx_row_m, self.dy_m)

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_geotiff(cls, path: str | Path, dataset_id: str) -> TerrainGrid:
        import rasterio

        with rasterio.open(path) as src:
            t = src.transform
            if abs(t.b) > 1e-9 or abs(t.d) > 1e-9 or t.e >= 0 or not math.isclose(t.a, -t.e, rel_tol=1e-9):
                raise TerrainError("UNSUPPORTED_PROJECTION", "DEM must be north-up with square pixels")
            if src.crs is None or "Mars" not in src.crs.to_wkt():
                raise TerrainError("UNSUPPORTED_PROJECTION", "DEM CRS must be a Mars CRS")
            z = src.read(1).astype("float64")
            nod = src.nodata
            if nod is not None:
                z[np.isclose(z, nod)] = np.nan
            z[z < -1e30] = np.nan
            return cls(dataset_id=dataset_id, elevation_m=z, origin_e_m=t.c, origin_n_m=t.f, res_m=t.a, crs_wkt=src.crs.to_wkt())

    @classmethod
    def synthetic(cls, z: np.ndarray, res_m: float = 20.0, lat_deg: float = 0.0, dataset_id: str = "synthetic-fixture") -> TerrainGrid:
        """Clearly-labelled synthetic fixture for tests. Never presented as NASA data."""
        n_top = MARS_RADIUS_M * math.radians(lat_deg) + z.shape[0] * res_m / 2
        return cls(dataset_id=dataset_id, elevation_m=np.asarray(z, dtype=float), origin_e_m=0.0, origin_n_m=n_top, res_m=res_m)

    # ------------------------------------------------------------------ geometry
    @property
    def height(self) -> int:
        return int(self.elevation_m.shape[0])

    @property
    def width(self) -> int:
        return int(self.elevation_m.shape[1])

    @property
    def extent_xy_m(self) -> tuple[float, float]:
        return self.width * self.res_m, self.height * self.res_m

    @property
    def origin_n_bottom_m(self) -> float:
        return self.origin_n_m - self.height * self.res_m

    def contains_xy(self, x_m: float, y_m: float) -> bool:
        w, h = self.extent_xy_m
        return 0.0 <= x_m < w and 0.0 <= y_m < h

    def xy_to_cell(self, x_m: float, y_m: float) -> tuple[int, int]:
        if not (math.isfinite(x_m) and math.isfinite(y_m)):
            raise TerrainError("INVALID_COORDINATE", "coordinates must be finite numbers")
        if not self.contains_xy(x_m, y_m):
            raise TerrainError("OUT_OF_BOUNDS", f"point ({x_m:.1f}, {y_m:.1f}) m is outside the study area")
        col = int(x_m // self.res_m)
        row = self.height - 1 - int(y_m // self.res_m)
        return row, col

    def cell_center_xy(self, row: int, col: int) -> tuple[float, float]:
        return (col + 0.5) * self.res_m, (self.height - row - 0.5) * self.res_m

    def cell_lonlat(self, row: int, col: int) -> tuple[float, float]:
        x, y = self.cell_center_xy(row, col)
        e = self.origin_e_m + x
        n = self.origin_n_bottom_m + y
        return math.degrees(e / MARS_RADIUS_M), math.degrees(n / MARS_RADIUS_M)

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def step_length_m(self, r0: int, c0: int, r1: int, c1: int) -> float:
        """Horizontal ground length between two neighbouring cell centres."""
        dx = abs(c1 - c0) * 0.5 * (self.dx_row_m[r0] + self.dx_row_m[r1])
        dy = abs(r1 - r0) * self.dy_m
        return math.hypot(dx, dy)

    def sample_bilinear(self, x_m: float, y_m: float) -> float | None:
        """Bilinear elevation at a local point using cell-centre posts; None if any post is NaN."""
        fc = x_m / self.res_m - 0.5
        fr = (self.height * self.res_m - y_m) / self.res_m - 0.5
        c0, r0 = int(math.floor(fc)), int(math.floor(fr))
        if not (0 <= c0 < self.width - 1 and 0 <= r0 < self.height - 1):
            return None
        tc, tr = fc - c0, fr - r0
        q = self.elevation_m[r0:r0 + 2, c0:c0 + 2]
        if np.isnan(q).any():
            return None
        return float(q[0, 0] * (1 - tc) * (1 - tr) + q[0, 1] * tc * (1 - tr) + q[1, 0] * (1 - tc) * tr + q[1, 1] * tc * tr)

    def ground_scale_bar(self) -> dict:
        lat_c = float(self.lat_row_deg[self.height // 2])
        return {"east_west_ground_m_per_projected_m": math.cos(math.radians(lat_c)), "center_lat_deg": lat_c}
