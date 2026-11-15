import type { EvidenceLevel, StudyArea } from "../api/types";

export const fmt = (v: number | null | undefined, digits = 0, unit = ""): string =>
  v === null || v === undefined || !Number.isFinite(v) ? "n/a" : `${v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit ? ` ${unit}` : ""}`;

export const fmtMin = (m: number | null | undefined): string => {
  if (m === null || m === undefined || !Number.isFinite(m)) return "n/a";
  const h = Math.floor(m / 60);
  const mm = Math.round(m - h * 60);
  return h > 0 ? `${h} h ${mm.toString().padStart(2, "0")} min` : `${mm} min`;
};

/** Compact clock-style duration for figures, e.g. 3:36 h or 42 min. */
export const fmtHM = (m: number | null | undefined): string => {
  if (m === null || m === undefined || !Number.isFinite(m)) return "n/a";
  if (m < 60) return `${Math.round(m)} min`;
  const h = Math.floor(m / 60);
  return `${h}:${Math.round(m - h * 60).toString().padStart(2, "0")} h`;
};

export const LEVEL_LABEL: Record<EvidenceLevel, string> = {
  NASA_OBSERVATION: "NASA observation",
  DERIVED: "Derived",
  ILLUSTRATIVE_MODEL: "Illustrative model",
  SIMULATED_EVENT: "Simulated event",
  SIMULATED: "Simulated",
  UNKNOWN: "Unknown",
};

export const REASON_TEXT: Record<string, string> = {
  NO_ROUTE: "No route exists under the current constraints.",
  SLOPE_EXCEEDS_LIMIT: "A route would exist with a higher slope limit: the slope limit blocks the way.",
  INSUFFICIENT_TIME: "Planned time exceeds the time budget minus the reserve.",
  INSUFFICIENT_CONSUMABLE: "Planned use of the illustrative consumable exceeds the budget minus the reserve.",
  UNMAPPED_TERRAIN: "The route crosses or would need terrain with no elevation data.",
  DATA_UNALIGNED: "Data layers are not aligned well enough for this use.",
  BLOCKED_BY_SCENARIO_EVENT: "The simulated blocked zone removes every route that otherwise exists.",
  START_IMPASSABLE: "The start point lies on impassable terrain.",
  GOAL_IMPASSABLE: "The destination lies on impassable terrain.",
};

/** Local projected metres -> lon/lat (equirectangular, Mars 2000 sphere). Pure unit conversion. */
export function xyToLonLat(sa: StudyArea, x: number, y: number): [number, number] {
  const R = sa.crs.sphere_radius_m;
  const e = sa.grid.origin_easting_m + x;
  const n = sa.grid.origin_northing_bottom_m + y;
  return [(e / R) * (180 / Math.PI), (n / R) * (180 / Math.PI)];
}
