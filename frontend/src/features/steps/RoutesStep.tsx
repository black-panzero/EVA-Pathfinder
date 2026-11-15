import type { EvaluateResponse } from "../../api/types";
import { ElevationProfile } from "../../components/ElevationProfile";
import { Prov, StatusBadge, StepHeader } from "../../components/ui";
import { fmt, fmtHM } from "../format";

export type Plans = { shortest: EvaluateResponse | null; terrain: EvaluateResponse | null };
type Choice = "shortest" | "terrain";

export function routeTotals(p: EvaluateResponse | null) {
  if (!p) return null;
  const legs = p.assessment.legs;
  const ok = legs.every((l) => l.route);
  const sum = (k: "length_m" | "elevation_gain_m" | "elevation_loss_m") => (ok ? legs.reduce((s, l) => s + l.route!.metrics[k], 0) : null);
  const length = sum("length_m");
  return {
    status: p.assessment.status, minutes: p.assessment.totals.minutes, length, gain: sum("elevation_gain_m"), loss: sum("elevation_loss_m"),
    maxSlope: ok ? Math.max(...legs.map((l) => l.route!.metrics.max_derived_slope_deg)) : null,
    meanSlope: ok && length ? legs.reduce((s, l) => s + l.route!.metrics.mean_derived_slope_deg * l.route!.metrics.length_m, 0) / length : null,
    unknown: ok ? Math.max(...legs.map((l) => l.route!.metrics.unknown_length_fraction)) : null,
    geology: legs[0]?.route?.geology_along_route ?? [],
  };
}

const META: Record<Choice, { name: string; what: string; swatch: string }> = {
  terrain: { name: "Terrain-aware", what: "Avoids steep ground, even if longer", swatch: "sw-accent" },
  shortest: { name: "Shortest", what: "Least distance within the slope limit", swatch: "sw-alt" },
};

export function RoutesStep({ plans, chosen, onChoose }: { plans: Plans; chosen: Choice; onChoose: (c: Choice) => void }) {
  const same = plans.shortest && plans.terrain &&
    JSON.stringify(plans.shortest.assessment.legs.map((l) => l.route?.polyline_xy_m)) === JSON.stringify(plans.terrain.assessment.legs.map((l) => l.route?.polyline_xy_m));
  const t = routeTotals(plans[chosen]);
  return (
    <>
      <StepHeader n={2} title="Compare routes">
        Two routes computed on the real 20 m elevation map. Choose the one the feasibility check should use
      </StepHeader>

      <div className="route-cards" role="radiogroup" aria-label="Route used for the feasibility check">
        {(["terrain", "shortest"] as Choice[]).map((c) => {
          const r = routeTotals(plans[c]);
          return (
            <button key={c} type="button" role="radio" aria-checked={chosen === c} className={`route-card ${chosen === c ? "on" : ""}`} onClick={() => onChoose(c)}>
              <span className="route-card-h">
                <i className={`sw ${META[c].swatch}`} aria-hidden="true" />
                <span className="t">{META[c].name}</span>
                {r && <StatusBadge status={r.status} />}
              </span>
              <span className="m">{META[c].what}</span>
              {r ? (
                <dl className="figs">
                  <div><dt>Round trip</dt><dd className="num">{fmt(r.length !== null ? r.length / 1000 : null, 2, "km")}</dd></div>
                  <div><dt>Steepest</dt><dd className="num">{fmt(r.maxSlope, 1, "°")}</dd></div>
                  <div><dt>Climb</dt><dd className="num">{fmt(r.gain, 0, "m")}</dd></div>
                  <div><dt>Time</dt><dd className="num">{fmtHM(r.minutes)}</dd></div>
                </dl>
              ) : <span className="m">Computing…</span>}
            </button>
          );
        })}
      </div>
      {same && <p className="callout">Both policies produced the same cell path for these inputs. That is a valid outcome and is reported as is</p>}

      <section className="group">
        <h3>Elevation along the itinerary <Prov level="DERIVED" /></h3>
        <ElevationProfile series={[
          ...(plans.shortest ? [{ label: "Shortest", color: "#ededed", dashed: true, legs: plans.shortest.assessment.legs }] : []),
          ...(plans.terrain ? [{ label: "Terrain-aware", color: "#ff7a45", legs: plans.terrain.assessment.legs }] : []),
        ]} />
      </section>

      {t && (
        <section className="group">
          <h3>Selected route in detail <Prov level="DERIVED" /></h3>
          <dl className="kv">
            <dt>Descent</dt><dd className="num">{fmt(t.loss, 0, "m")}</dd>
            <dt>Average slope, by length</dt><dd className="num">{fmt(t.meanSlope, 1, "°")}</dd>
            <dt>Distance over unmapped ground</dt><dd className="num">{fmt((t.unknown ?? 0) * 100, 1, "%")}</dd>
          </dl>
          {t.geology.length > 0 && (
            <>
              <h4>Rock units crossed on the way out <Prov level="DERIVED" label={false} /></h4>
              <ul className="rank">
                {t.geology.map((g) => (
                  <li key={g.symbol}>
                    <span className="rank-l"><span className="mono">{g.symbol}</span> {g.name}</span>
                    <span className="rank-bar"><i style={{ width: `${g.length_fraction * 100}%` }} /></span>
                    <span className="num">{Math.round(g.length_fraction * 100)}%</span>
                  </li>
                ))}
              </ul>
              <p className="note">USGS geologic map, regional context only: unit edges may be off by 100-200 m</p>
            </>
          )}
        </section>
      )}
      <p className="note">Both routes obey the same hard limits. Cells are 20 m across, so rocks and small ledges are not visible to the planner</p>
    </>
  );
}
