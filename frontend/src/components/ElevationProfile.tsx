import type { LegDTO } from "../api/types";
import { fmt } from "../features/format";

export interface ProfileSeries { label: string; color: string; dashed?: boolean; legs: LegDTO[] }

/** Concatenate the backend's per-leg DEM samples into one itinerary-length series. */
export function itinerary(legs: LegDTO[]): { d: number; z: number }[] {
  const out: { d: number; z: number }[] = [];
  let offset = 0;
  for (const leg of legs) {
    if (!leg.route) break;
    for (const p of leg.route.profile) if (p.elevation_m !== null) out.push({ d: offset + p.distance_m, z: p.elevation_m });
    offset += leg.route.metrics.length_m;
  }
  return out;
}

export function ElevationProfile({ series, height = 170 }: { series: ProfileSeries[]; height?: number }) {
  const data = series.map((s) => ({ ...s, pts: itinerary(s.legs) })).filter((s) => s.pts.length > 1);
  if (!data.length) return <p className="muted">No computed route to profile.</p>;
  const W = 640, H = height, pad = { l: 52, r: 12, t: 10, b: 28 };
  const all = data.flatMap((s) => s.pts);
  const dMax = Math.max(...all.map((p) => p.d));
  let zMin = Math.min(...all.map((p) => p.z)), zMax = Math.max(...all.map((p) => p.z));
  const zPad = Math.max(5, (zMax - zMin) * 0.1);
  zMin -= zPad; zMax += zPad;
  const sx = (d: number) => pad.l + (d / dMax) * (W - pad.l - pad.r);
  const sy = (z: number) => pad.t + (1 - (z - zMin) / (zMax - zMin)) * (H - pad.t - pad.b);
  const ticksX = Array.from({ length: 5 }, (_, i) => (dMax * i) / 4);
  const ticksZ = Array.from({ length: 4 }, (_, i) => zMin + ((zMax - zMin) * i) / 3);
  const desc = data.map((s) => `${s.label}: ${fmt(s.pts[s.pts.length - 1].d / 1000, 2)} km, elevation ${fmt(Math.min(...s.pts.map((p) => p.z)), 0)} to ${fmt(Math.max(...s.pts.map((p) => p.z)), 0)} m`).join("; ");
  return (
    <figure className="profile">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Elevation profile along the itinerary. ${desc}`}>
        {ticksZ.map((z) => (
          <g key={z}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(z)} y2={sy(z)} className="grid" />
            <text x={pad.l - 6} y={sy(z) + 4} textAnchor="end" className="tick">{z.toFixed(0)}</text>
          </g>
        ))}
        {ticksX.map((d) => (
          <text key={d} x={sx(d)} y={H - 8} textAnchor="middle" className="tick">{(d / 1000).toFixed(1)} km</text>
        ))}
        {data.map((s) => (
          <polyline key={s.label} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? "6 4" : undefined}
            points={s.pts.map((p) => `${sx(p.d).toFixed(1)},${sy(p.z).toFixed(1)}`).join(" ")} />
        ))}
        <text x={12} y={pad.t + 8} className="tick" transform={`rotate(-90 12 ${H / 2})`}>m (geoid)</text>
      </svg>
      <figcaption className="muted small">
        DEM samples at 20 m cell centres along each computed route (DERIVED). Legend: {data.map((s) => <span key={s.label} className="legend-item"><i style={{ background: s.color }} />{s.label}</span>)}
      </figcaption>
    </figure>
  );
}
