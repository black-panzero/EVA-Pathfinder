import { ArrowRight, Crosshair, Play } from "lucide-react";
import type { ReplanResponse } from "../../api/types";
import { Disclosure, Prov, Segmented, StatusBadge, StepHeader, Stepper } from "../../components/ui";
import { fmt, fmtMin } from "../format";
import { Reasons } from "./FeasibilityStep";

export interface ContingencyState {
  elapsed_min: number; radius_m: number; position_fraction: number; response_mode: "return_now" | "continue";
  consumable_loss_units: number; center: { x_m: number; y_m: number } | null;
}

export function ContingencyStep({ state, setState, planMinutes, onRun, onPickZone, picking, result, busy, error }: {
  state: ContingencyState; setState: (s: ContingencyState) => void; planMinutes: number | null; onRun: () => void;
  onPickZone: () => void; picking: boolean; result: ReplanResponse | null; busy: boolean; error: string | null;
}) {
  const maxT = Math.max(1, Math.floor(planMinutes ?? 0));
  const b = result?.before, a = result?.after;
  return (
    <>
      <StepHeader n={4} title="Test a contingency">
        Block part of the path mid-walk and see whether the crew can still get home from where they are
      </StepHeader>

      <section className="group">
        <h3>1 · When it happens <Prov level="SIMULATED" /></h3>
        <label className="slider">
          <span className="slider-top"><span>Time into the walk</span><span className="num">{fmtMin(state.elapsed_min)} of {fmtMin(planMinutes)}</span></span>
          <input type="range" min={0} max={maxT} step={1} value={Math.min(state.elapsed_min, maxT)} disabled={!planMinutes}
            onChange={(e) => setState({ ...state, elapsed_min: parseFloat(e.target.value) })} aria-valuetext={fmtMin(state.elapsed_min)} />
        </label>
      </section>

      <section className="group">
        <h3>2 · What is blocked</h3>
        <div className="fields">
          <Stepper label="Blocked zone radius" unit="m" value={state.radius_m} min={20} max={1000} step={10} onChange={(v) => setState({ ...state, radius_m: v })} />
        </div>
        {state.center ? (
          <div className="row-card">
            <Crosshair size={18} strokeWidth={1.5} className="ic" aria-hidden="true" />
            <div className="grow"><div className="t">Placed on the map</div><div className="m num">x {Math.round(state.center.x_m)} m · y {Math.round(state.center.y_m)} m</div></div>
            <button type="button" className="btn sm" onClick={() => setState({ ...state, center: null })}>Use route</button>
          </div>
        ) : (
          <label className="slider">
            <span className="slider-top"><span>Position along the remaining route</span><span className="num">{Math.round(state.position_fraction * 100)}%</span></span>
            <input type="range" min={0.05} max={0.95} step={0.05} value={state.position_fraction} onChange={(e) => setState({ ...state, position_fraction: parseFloat(e.target.value) })} />
          </label>
        )}
        <button type="button" className={`btn sm ghost ${picking ? "active" : ""}`} onClick={onPickZone} aria-pressed={picking}>
          <Crosshair size={14} strokeWidth={1.75} aria-hidden="true" />{picking ? "Click the map to place it" : "Place the zone on the map instead"}
        </button>
      </section>

      <section className="group">
        <h3>3 · How the crew responds</h3>
        <Segmented label="Crew response" value={state.response_mode} onChange={(v) => setState({ ...state, response_mode: v })}
          options={[{ value: "return_now", label: "Head home now" }, { value: "continue", label: "Finish stops, then home" }]} />
        <Disclosure title="Also lose supplies">
          <div className="fields"><Stepper label="Supplies lost" unit="units" value={state.consumable_loss_units} min={0} step={10} onChange={(v) => setState({ ...state, consumable_loss_units: v })} /></div>
        </Disclosure>
      </section>

      <button type="button" className="btn primary block" onClick={onRun} disabled={busy || !planMinutes}>
        <Play size={16} strokeWidth={1.75} aria-hidden="true" />{busy ? "Replanning…" : "Run scenario"}
      </button>
      {error && <p className="callout neg" role="alert">{error}</p>}

      {result && b && a && (
        <section className="group result">
          <div className="change" role="status">
            <StatusBadge status={b.status} /><ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" /><StatusBadge status={a.status} size="lg" />
          </div>
          <p className="verdict-t">
            {a.legs.some((l) => !l.route) ? "No route home avoids the blocked zone. The planner draws nothing rather than a false path"
              : a.status === "FEASIBLE" ? "A detour home exists and still fits the budget" : "A detour exists but breaks the budget"}
          </p>
          <Reasons codes={a.reason_codes} />
          <table className="tbl">
            <thead><tr><th scope="col" /><th scope="col">Before</th><th scope="col">After</th></tr></thead>
            <tbody>
              <tr><th scope="row">Distance still to walk</th><td className="num">{fmt(b.remaining_length_m, 0, "m")}</td><td className="num">{fmt(a.remaining_length_m, 0, "m")}</td></tr>
              <tr><th scope="row">Total mission time</th><td className="num">{fmtMin(b.totals.minutes)}</td><td className="num">{fmtMin(a.totals.minutes)}</td></tr>
              <tr><th scope="row">Return margin</th><td className="num">{fmt(b.totals.time_margin_min, 0, "min")}</td><td className="num">{fmt(a.totals.time_margin_min, 0, "min")}</td></tr>
              <tr><th scope="row">Supplies used</th><td className="num">{fmt(b.totals.consumable_units, 0)}</td><td className="num">{fmt(a.totals.consumable_units, 0)}</td></tr>
            </tbody>
          </table>
          <p className="note">
            Crew at x {result.current_position.x_m}, y {result.current_position.y_m} m after {fmtMin(result.current_position.elapsed_min)} ({result.current_position.phase}), {fmt(result.current_position.consumed_units, 0)} units used.
            Zone {result.event.radius_m} m, {result.event.affects_previous_route ? "crossing" : "not crossing"} the old path
          </p>
          <Disclosure title={`Event log (${result.events.length})`}>
            <ol className="events">{result.events.map((e, i) => <li key={i}><code>{e.name}</code> <span className="mono">{JSON.stringify(e.data)}</span></li>)}</ol>
          </Disclosure>
        </section>
      )}
    </>
  );
}
