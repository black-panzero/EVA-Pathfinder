"""Evidence context: labels that separate observation from derivation, assumption and simulation."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from enum import Enum


class EvidenceLevel(str, Enum):
    NASA_OBSERVATION = "NASA_OBSERVATION"
    DERIVED = "DERIVED"
    ILLUSTRATIVE_MODEL = "ILLUSTRATIVE_MODEL"
    SIMULATED_EVENT = "SIMULATED_EVENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvidenceRecord:
    item: str
    level: EvidenceLevel
    source_ids: tuple[str, ...] = ()
    detail: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        d["source_ids"] = list(self.source_ids)
        return d


@dataclass
class DomainEvent:
    name: str
    at: str
    data: dict = field(default_factory=dict)


class EventLog:
    """Simple in-process, append-only domain event log (no message broker)."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record(self, name: str, **data: object) -> None:
        self._events.append(DomainEvent(name, dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), dict(data)))

    def to_list(self) -> list[dict]:
        return [{"name": e.name, "at": e.at, "data": e.data} for e in self._events]


STANDARD_ASSUMPTIONS = [
    EvidenceRecord("DEM elevations (CTX 20 m DTM)", EvidenceLevel.NASA_OBSERVATION, ("usgs-m2020-trn-ctx-dtm-20m",), "Stereo-derived from MRO CTX by USGS; 20 m posts."),
    EvidenceRecord("Slope, route geometry, length, elevation gain/loss", EvidenceLevel.DERIVED, ("usgs-m2020-trn-ctx-dtm-20m",), "Computed by this software from the DEM."),
    EvidenceRecord("Walking speed, ascent rate, maximum slope, time budget, consumable rates, reserve", EvidenceLevel.ILLUSTRATIVE_MODEL, (), "User-supplied scenario inputs; not astronaut-certified."),
    EvidenceRecord("Habitat, crew, EVA, science activity durations", EvidenceLevel.SIMULATED_EVENT, (), "Hypothetical mission 'Operation Delta Return'."),
    EvidenceRecord("Rocks, boulders, soil strength, real-time atmosphere", EvidenceLevel.UNKNOWN, (), "Not resolvable at 20 m and not measured for any future EVA."),
]
