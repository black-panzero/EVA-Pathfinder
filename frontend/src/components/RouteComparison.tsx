import type { EvaluateResponse } from "../api/types";
import { fmt, fmtMin } from "../features/format";
import { Panel, StatusPill } from "./common";
import { ElevationProfile } from "./ElevationProfile";

type Plans = { shortest: EvaluateResponse | null; terrain: EvaluateResponse | null };

function totals(p: EvaluateResponse | null) {
  if (!p) return null;
  const legs = p.assessment.legs;
  const ok = legs.every((l) => l.route);
  const sum = (f: (m: NonNullable<(typeof legs)[number]["route"]>["metrics"]) => number) => (ok ? legs.reduce((s, l) => s + f(l.route!.metrics), 0) : null);
  return {
    status: p.assessment.status, minutes: p.assessment.totals.minutes, length: sum((m) => m.length_m), gain: sum((m) => m.elevation_gain_m),
    loss: sum((m) => m.elevation_loss_m), maxSlope: ok ? Math.max(...legs.map((l) => l.route!.metrics.max_derived_slope_deg)) : null,
    meanSlope: ok ? legs.reduce((s, l) => s + l.route!.metrics.mean_derived_slope_deg * l.route!.metrics.length_m, 0) / (sum((m) => m.length_m) || 1) : null,
    unknown: ok ? Math.max(...legs.map((l) => l.route!.metrics.unknown_length_fraction)) : null,
    geology: legs[0]?.route?.geology_along_route ?? [],
  };
}

export function RouteComparison({ plans, chosen }: { plans: Plans; chosen: "shortest" | "terrain" }) {
  const s = totals(plans.shortest), t = totals(plans.terrain);
  const same = plans.shortest && plans.terrain && JSON.stringify(plans.shortest.assessment.legs.map((l) => l.route?.polyline_xy_m)) === JSON.stringify(plans.terrain.assessment.legs.map((l) => l.route?.polyline_xy_m));
  const rows: [string, (x: NonNullable<ReturnType<typeof totals>>) => string][] = [
    ["Feasibility", () => ""],
    ["Round-trip distance", (x) => fmt(x.length, 0, "m")],
    ["Elevation gain / loss", (x) => `${fmt(x.gain, 0)} / ${fmt(x.loss, 0)} m`],
    ["Max derived slope", (x) => fmt(x.maxSlope, 1, "°")],
    ["Length-weighted mean slope", (x) => fmt(x.meanSlope, 1, "°")],
    ["Unknown-coverage fraction", (x) => fmt((x.unknown ?? 0) * 100, 1, "%")],
    ["Total planned time", (x) => fmtMin(x.minutes)],
  ];
  return (
    <Panel title="Route comparison" id="routes" badge="DERIVED">
      <table className="tbl compare">
        <thead>
          <tr><th scope="col">Metric</th>
            <th scope="col"><i className="sw sw-short" /> Shortest feasible{chosen === "shortest" ? " (selected)" : ""}</th>
            <th scope="col"><i className="sw sw-terrain" /> Terrain-aware{chosen === "terrain" ? " (selected)" : ""}</th></tr>
        </thead>
        <tbody>
          {rows.map(([label, f]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{s ? (label === "Feasibility" ? <StatusPill status={s.status} /> : f(s)) : "…"}</td>
              <td>{t ? (label === "Feasibility" ? <StatusPill status={t.status} /> : f(t)) : "…"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {same && <p className="note">Both policies produced the same cell path for these inputs. That is a valid outcome and is reported as is.</p>}
      <ElevationProfile series={[
        ...(plans.shortest ? [{ label: "Shortest feasible", color: "#5ec8e5", dashed: true, legs: plans.shortest.assessment.legs }] : []),
        ...(plans.terrain ? [{ label: "Terrain-aware", color: "#ff8c42", legs: plans.terrain.assessment.legs }] : []),
      ]} />
      {t && t.geology.length > 0 && (
        <p className="small muted">Outbound leg crosses mapped units (regional context, ±100-200 m): {t.geology.map((g) => `${g.symbol} ${Math.round(g.length_fraction * 100)}%`).join(", ")}</p>
      )}
      <p className="small muted">Both routes use the same hard exclusions (slope limit, no-data). Cost = length × (1 + w × slope / limit); shortest uses w = 0. 20 m cells cannot show rocks or small scarps.</p>
    </Panel>
  );
}
