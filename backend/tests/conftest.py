from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.terrain import TerrainGrid  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "jezero-delta-return-v1"


class FakeRepo:
    """In-memory TerrainSource over a clearly-labelled SYNTHETIC fixture."""

    def __init__(self, grid: TerrainGrid):
        self.grid = grid
        self.geology = None
        self.geology_raster = None
        self.dem_sha256 = "synthetic"
        self.manifest = {"study_area_id": "synthetic-fixture", "processing_version": "test"}


@pytest.fixture
def flat_grid() -> TerrainGrid:
    return TerrainGrid.synthetic(np.zeros((40, 60)), res_m=20.0, lat_deg=0.0)


@pytest.fixture
def real_data_available() -> bool:
    return (PROCESSED / "manifest.json").exists()


requires_real_data = pytest.mark.skipif(not (PROCESSED / "manifest.json").exists(), reason="real study area not prepared (run make data)")
