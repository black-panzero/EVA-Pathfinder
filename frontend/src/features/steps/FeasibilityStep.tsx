import { AlertTriangle } from "lucide-react";
import type { AssessmentDTO } from "../../api/types";
import { Bar, Prov, StatusBadge, StepHeader } from "../../components/ui";
import { fmt, fmtHM, fmtMin, REASON_TEXT } from "../format";

export function Reasons({ codes }: { codes: string[] }) {
  if (!codes.length) return null;
  return (
    <ul className="reasons">
      {codes.map((c) => (
        <li key={c}><AlertTriangle size={16} strokeWidth={1.5} aria-hidden="true" /><span><code>{c}</code> {REASON_TEXT[c] ?? ""}</span></li>
      ))}
    </ul>
  );
}

export function headline(a: AssessmentDTO): string {
  const m = a.totals.time_margin_min;
  if (a.status === "FEASIBLE") return `The crew gets back with ${Math.round(m ?? 0)} min to spare before the reserve`;
  if (a.status === "UNKNOWN") return "The plan fits the budget but crosses unmapped ground";
  if (a.legs.some((l) => !l.route)) return "No safe route exists under these limits";
  return "The walk does not fit the budget with the reserve kept back";
}

export function AssessmentBlock({ a, compact = false }: { a: AssessmentDTO; compact?: boolean }) {
  const t = a.totals;
  return (
    <div className="assessment">
      <div className="status-row" role="status" aria-live="polite"><StatusBadge status={a.status} size={compact ? "md" : "lg"} /></div>
      <Reasons codes={a.reason_codes} />
      <Bar label="Mission time" used={t.minutes} usable={t.usable_time_min} total={t.time_available_min} unit="min" />
      <Bar label="Supplies" used={t.consumable_units} usable={t.usable_consumable_units} total={t.consumable_initial_units} unit="units" />
    </div>
  );
}

export function FeasibilityStep({ a, names = {} }: { a: AssessmentDTO | null; names?: Record<string, string> }) {
  const nm = (id: string) => names[id] ?? id;
  if (!a) return <StepHeader n={3} title="Check feasibility">Compute routes first</StepHeader>;
  const t = a.totals;
  let clock = 0;
  const rows: { label: string; at: number; dur: number | null; dist?: number | null; kind: string }[] = [];
  a.legs.forEach((l, i) => {
    const last = i === a.legs.length - 1;
    rows.push({ label: last ? "Walk back to habitat" : `Walk to ${nm(l.to)}`, at: clock, dur: l.minutes, dist: l.route?.metrics.length_m, kind: "tl-walk" });
    clock += l.minutes ?? 0;
    const act = a.activities.find((x) => x.stop_id === l.to);
    if (act && !last) { rows.push({ label: `Science at ${nm(l.to)}`, at: clock, dur: act.minutes, kind: "tl-site" }); clock += act.minutes; }
  });

  return (
    <>
      <StepHeader n={3} title="Check feasibility">
        The whole round trip, including the walk home, is checked against time and supplies with the reserve kept back
      </StepHeader>

      <section className="verdict">
        <StatusBadge status={a.status} size="lg" />
        <p className="verdict-t">{headline(a)}</p>
        <div className="figure-row">
          <div className="figure">
            <span className="figure-l">Return margin <Prov level="ILLUSTRATIVE_MODEL" label={false} /></span>
            <span className={`figure-v num ${t.time_margin_min !== null && t.time_margin_min < 0 ? "neg" : ""}`}>{fmt(t.time_margin_min, 0)}<small>min</small></span>
          </div>
          <div className="figure">
            <span className="figure-l">Total time</span>
            <span className="figure-v num">{fmtHM(t.minutes)}</span>
          </div>
          <div className="figure">
            <span className="figure-l">Supplies left over</span>
            <span className={`figure-v num ${t.consumable_margin_units !== null && t.consumable_margin_units < 0 ? "neg" : ""}`}>{fmt(t.consumable_margin_units, 0)}<small>units</small></span>
          </div>
        </div>
        <Reasons codes={a.reason_codes} />
      </section>

      <section className="group">
        <h3>Budgets</h3>
        <Bar label="Mission time" used={t.minutes} usable={t.usable_time_min} total={t.time_available_min} unit="min" />
        <Bar label="Supplies" used={t.consumable_units} usable={t.usable_consumable_units} total={t.consumable_initial_units} unit="units" />
        <p className="note">The dashed mark is where the {Math.round(t.reserve_fraction * 100)}% reserve begins. A plan is feasible only if it ends before it</p>
      </section>

      <section className="group">
        <h3>Timeline <Prov level="SIMULATED" /></h3>
        <ol className="timeline">
          {rows.map((r, i) => (
            <li key={i} className={r.kind}>
              <span className="tl-at num">{fmtClock(r.at)}</span>
              <span className="tl-dot" aria-hidden="true" />
              <span className="tl-body">
                <span className="t">{r.label}</span>
                <span className="m num">{fmtMin(r.dur)}{r.dist !== undefined ? ` · ${fmt(r.dist, 0, "m")}` : ""}</span>
              </span>
            </li>
          ))}
          <li className="tl-end">
            <span className="tl-at num">{fmtClock(clock)}</span><span className="tl-dot" aria-hidden="true" />
            <span className="tl-body"><span className="t">Back at habitat</span></span>
          </li>
        </ol>
      </section>
    </>
  );
}

function fmtClock(m: number): string {
  if (!Number.isFinite(m)) return "--:--";
  const h = Math.floor(m / 60);
  return `${h}:${Math.round(m - h * 60).toString().padStart(2, "0")}`;
}
