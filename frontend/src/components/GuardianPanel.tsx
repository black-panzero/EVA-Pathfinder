import { STATIC_MODE } from "../api/client";
import type { AssessmentDTO } from "../api/types";
import { fmt, fmtMin, REASON_TEXT } from "../features/format";
import { BudgetBar, Panel, StatusPill } from "./common";

export function ReasonList({ codes }: { codes: string[] }) {
  if (!codes.length) return <p className="muted small">No constraint violations under the stated model.</p>;
  return (
    <ul className="reasons">
      {codes.map((c) => <li key={c}><code>{c}</code> {REASON_TEXT[c] ?? ""}</li>)}
    </ul>
  );
}

export function AssessmentSummary({ a, compact = false }: { a: AssessmentDTO; compact?: boolean }) {
  const t = a.totals;
  return (
    <div className="assessment">
      <div className="status-row" role="status" aria-live="polite">
        <StatusPill status={a.status} />
        {!compact && <span className="muted small">under the stated illustrative model</span>}
      </div>
      <ReasonList codes={a.reason_codes} />
      <BudgetBar label="Mission time" used={t.minutes} usable={t.usable_time_min} total={t.time_available_min} unit="min" />
      <BudgetBar label={t.consumable_label} used={t.consumable_units} usable={t.usable_consumable_units} total={t.consumable_initial_units} unit="units" />
      {!compact && (
        <dl className="kv">
          <dt>Total planned time</dt><dd>{fmtMin(t.minutes)}</dd>
          <dt>Time margin after reserve</dt><dd>{fmt(t.time_margin_min, 0, "min")}</dd>
          <dt>Consumable margin after reserve</dt><dd>{fmt(t.consumable_margin_units, 0, "units")}</dd>
          <dt>Reserve</dt><dd>{fmt(t.reserve_fraction * 100, 0, "%")} of each budget</dd>
        </dl>
      )}
    </div>
  );
}

export function GuardianPanel({ a, busy }: { a: AssessmentDTO | null; busy: boolean }) {
  return (
    <Panel title="Guardian checks" id="guardian" badge="ILLUSTRATIVE_MODEL">
      {busy && <p className="muted" role="status">{STATIC_MODE && !a ? "Starting the Python planning engine in your browser (first load takes 10-30 s), then computing routes on the DEM…" : "Computing routes on the DEM…"}</p>}
      {a ? (
        <>
          <AssessmentSummary a={a} />
          <h3>Itinerary</h3>
          <table className="tbl">
            <thead><tr><th>Segment</th><th>Time</th><th>Distance</th><th>Gain</th></tr></thead>
            <tbody>
              {a.legs.map((l, i) => (
                <tr key={l.leg_id}>
                  <td>{i === a.legs.length - 1 ? "Return" : `Leg ${i + 1}`}: {l.from} → {l.to}{l.reason_codes.length ? <div className="bad small">{l.reason_codes.join(", ")}</div> : null}</td>
                  <td>{fmtMin(l.minutes)}</td>
                  <td>{fmt(l.route?.metrics.length_m, 0, "m")}</td>
                  <td>{fmt(l.route?.metrics.elevation_gain_m, 0, "m")}</td>
                </tr>
              ))}
              {a.activities.map((x) => (
                <tr key={x.stop_id} className="muted"><td>Science activity at {x.stop_id}</td><td>{fmtMin(x.minutes)}</td><td colSpan={2}>simulated</td></tr>
              ))}
            </tbody>
          </table>
        </>
      ) : !busy && <p className="muted">Evaluate a plan to see feasibility.</p>}
    </Panel>
  );
}
