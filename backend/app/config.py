from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    study_area_id: str = "jezero-delta-return-v1"
    max_cells: int = 250_000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    mission_defaults: dict = field(default_factory=dict)

    @property
    def processed_dir(self) -> Path:
        override = os.environ.get("EVA_PROCESSED_DIR")
        return Path(override) if override else self.root / "data" / "processed" / self.study_area_id


def load_settings() -> Settings:
    defaults = json.loads((ROOT / "config" / "mission_defaults.json").read_text())
    area = json.loads((ROOT / "config" / "study_area.json").read_text())
    origins = tuple(o.strip() for o in os.environ.get("EVA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip())
    return Settings(study_area_id=area["study_area_id"], max_cells=area["max_cells"], cors_origins=origins, mission_defaults=defaults)
