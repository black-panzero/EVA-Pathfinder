"""Infrastructure adapters: load prepared, provenance-tracked data from disk.

Only files produced by scripts/prepare_data.py are read. Nothing here fetches remote URLs, so no
client-supplied parameter can trigger outbound requests (SSRF-safe by construction).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from functools import cached_property
from pathlib import Path

import numpy as np

from ..config import Settings
from ..domain.terrain import TerrainGrid

LAYER_FILES = {
    "ortho": ("ortho.png", "Optical: CTX orthomosaic (6 m)", "NASA_OBSERVATION"),
    "hillshade": ("hillshade.png", "Hillshade (from CTX DTM)", "DERIVED"),
    "elevation": ("elevation.png", "Elevation (CTX DTM 20 m)", "DERIVED"),
    "slope": ("slope.png", "Slope (derived from DTM)", "DERIVED"),
    "geology": ("geology.png", "Geologic units (USGS SIM 3464)", "DERIVED"),
}


class DataUnavailable(RuntimeError):
    pass


class StudyAreaRepository:
    def __init__(self, settings: Settings, area_id: str | None = None):
        self.settings = settings
        self.area_id = area_id or settings.study_area_id
        self.dir = settings.processed_dir_for(self.area_id)
        if not (self.dir / "manifest.json").exists():
            raise DataUnavailable(f"Prepared study area not found at {self.dir}. Run `make data` (scripts/prepare_data.py).")

    def _json(self, name: str):
        p = self.dir / name
        return json.loads(p.read_text()) if p.exists() else None

    @cached_property
    def manifest(self) -> dict:
        return self._json("manifest.json")

    @cached_property
    def grid(self) -> TerrainGrid:
        g = TerrainGrid.from_geotiff(self.dir / "dem_crop.tif", dataset_id=self.manifest["artifacts"][0]["source_ids"][0])
        if g.width * g.height > self.settings.max_cells:
            raise DataUnavailable("Study area exceeds configured max_cells")
        return g

    @cached_property
    def dem_sha256(self) -> str:
        return hashlib.sha256((self.dir / "dem_crop.tif").read_bytes()).hexdigest()

    @cached_property
    def science(self) -> dict:
        return self._json("science_sites.json")

    @cached_property
    def photos(self) -> list[dict]:
        return self._json("photos.json") or []

    @cached_property
    def meda(self) -> dict | None:
        return self._json("meda.json")

    @cached_property
    def traverse(self) -> dict:
        return self._json("rover_traverse.json") or {"points": []}

    @cached_property
    def geology(self) -> dict | None:
        return self._json("geology_units.json")

    @cached_property
    def geology_raster(self) -> np.ndarray | None:
        p = self.dir / "geology_units.npy"
        return np.load(p) if p.exists() else None

    def layer_path(self, layer_id: str) -> Path | None:
        if layer_id not in LAYER_FILES:
            return None
        p = self.dir / LAYER_FILES[layer_id][0]
        return p if p.exists() else None

    def photo_path(self, photo_id: str) -> Path | None:
        for ph in self.photos:
            if ph["photo_id"] == photo_id:
                p = (self.dir / ph["file"]).resolve()
                if self.dir.resolve() in p.parents and p.exists():
                    return p
        return None


def code_version(root: Path) -> str:
    version = (root / "VERSION").read_text().strip() if (root / "VERSION").exists() else "0.0.0"
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, timeout=2)
        if rev.returncode == 0 and rev.stdout.strip():
            return f"{version}+{rev.stdout.strip()}"
    except Exception:
        pass
    return f"{version}+nogit"
