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
    # every planning area, primary first: config/study_area.json then config/study_area.*.json
    areas: tuple[dict, ...] = ()

    @property
    def processed_dir(self) -> Path:
        return self.processed_dir_for(self.study_area_id)

    def processed_dir_for(self, area_id: str) -> Path:
        override = os.environ.get("EVA_PROCESSED_DIR")
        if override and area_id == self.study_area_id:
            return Path(override)
        return self.root / "data" / "processed" / area_id

    def area(self, area_id: str | None) -> dict | None:
        target = area_id or self.study_area_id
        return next((a for a in self.areas if a["study_area_id"] == target), None)


def load_settings() -> Settings:
    defaults = json.loads((ROOT / "config" / "mission_defaults.json").read_text())
    area = json.loads((ROOT / "config" / "study_area.json").read_text())
    origins = tuple(o.strip() for o in os.environ.get("EVA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip())
    extra = [json.loads(p.read_text()) for p in sorted((ROOT / "config").glob("study_area.*.json"))]
    return Settings(study_area_id=area["study_area_id"], max_cells=area["max_cells"], cors_origins=origins, mission_defaults=defaults, areas=(area, *extra))
