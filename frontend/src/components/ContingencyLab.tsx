import type { ReplanResponse } from "../api/types";
import { fmt, fmtMin } from "../features/format";
import { Badge, NumberField, Panel } from "./common";
import { AssessmentSummary } from "./GuardianPanel";

export interface ContingencyState {
  elapsed_min: number; radius_m: number; position_fraction: number; response_mode: "return_now" | "continue";
  consumable_loss_units: number; center: { x_m: number; y_m: number } | null;
}

export function ContingencyLab({ state, setState, planMinutes, onInject, onPickZone, picking, result, busy, error }: {
  state: ContingencyState; setState: (s: ContingencyState) => void; planMinutes: number | null; onInject: () => void;
  onPickZone: () => void; picking: boolean; result: ReplanResponse | null; busy: boolean; error: string | null;
}) {
  const maxT = Math.max(1, Math.floor(planMinutes ?? 0));
  return (
    <Panel title="Contingency lab" id="contingency" badge="SIMULATED_EVENT">
      <div className="grid2">
        <label className="field span2">
          <span className="field-l">Simulated mission progress: {fmtMin(state.elapsed_min)} of {fmtMin(planMinutes)}</span>
          <input type="range" min={0} max={maxT} step={1} value={Math.min(state.elapsed_min, maxT)} disabled={!planMinutes}
            onChange={(e) => setState({ ...state, elapsed_min: parseFloat(e.target.value) })} aria-valuetext={fmtMin(state.elapsed_min)} />
        </label>
        <NumberField label="Blocked zone radius" unit="m, ground" value={state.radius_m} min={20} max={1000} step={10} onChange={(v) => setState({ ...state, radius_m: v })} />
        <label className="field">
          <span className="field-l">Crew response</span>
          <select value={state.response_mode} onChange={(e) => setState({ ...state, response_mode: e.target.value as ContingencyState["response_mode"] })}>
            <option value="return_now">Abort: return to habitat now</option>
            <option value="continue">Continue remaining stops, then return</option>
          </select>
        </label>
        <label className="field span2">
          <span className="field-l">Zone position: {state.center ? `picked on map (${state.center.x_m.toFixed(0)}, ${state.center.y_m.toFixed(0)}) m` : `${Math.round(state.position_fraction * 100)}% along the remaining route`}</span>
          <input type="range" min={0.05} max={0.95} step={0.05} value={state.position_fraction} disabled={!!state.center}
            onChange={(e) => setState({ ...state, position_fraction: parseFloat(e.target.value) })} />
        </label>
        <NumberField label="Simulated consumable loss" unit="units" value={state.consumable_loss_units} min={0} step={10} onChange={(v) => setState({ ...state, consumable_loss_units: v })} />
        <div className="btn-row">
          <button type="button" className={picking ? "btn active" : "btn"} onClick={onPickZone} aria-pressed={picking}>{picking ? "Click the map…" : "Pick zone on map"}</button>
          {state.center && <button type="button" className="btn ghost" onClick={() => setState({ ...state, center: null })}>Use route position</button>}
        </div>
      </div>
      <button type="button" className="btn primary wide" onClick={onInject} disabled={busy || !planMinutes}>{busy ? "Replanning…" : "Inject blocked zone and replan"}</button>
      {error && <p className="bad" role="alert">{error}</p>}
      {result && (
        <div className="replan">
          <p className="small"><Badge level="SIMULATED_EVENT" /> Zone centre ({result.event.center_xy_m[0].toFixed(0)}, {result.event.center_xy_m[1].toFixed(0)}) m, {result.event.blocked_cells} cells blocked, {result.event.affects_previous_route ? "crosses the previous remaining route" : "does not cross the previous remaining route"}. Placement: {result.event.placement}.</p>
          <p className="small">Crew at ({result.current_position.x_m}, {result.current_position.y_m}) m, {fmtMin(result.current_position.elapsed_min)} elapsed ({result.current_position.phase}, {result.current_position.segment}); consumed {fmt(result.current_position.consumed_units, 0)} units{result.current_position.consumable_loss_units ? ` + ${result.current_position.consumable_loss_units} lost` : ""}.</p>
          <div className="before-after">
            <div><h3>Before event (remaining plan)</h3><p className="small">Remaining distance {fmt(result.before.remaining_length_m, 0, "m")}</p><AssessmentSummary a={result.before} compact /></div>
            <div><h3>After event (replanned)</h3><p className="small">Remaining distance {fmt(result.after.remaining_length_m, 0, "m")}</p><AssessmentSummary a={result.after} compact /></div>
          </div>
          <p className="status-change" role="status">Status change: <strong>{result.status_change}</strong></p>
          <details>
            <summary>Event log ({result.events.length})</summary>
            <ol className="events">{result.events.map((e, i) => <li key={i}><code>{e.name}</code> {JSON.stringify(e.data)}</li>)}</ol>
          </details>
        </div>
      )}
    </Panel>
  );
}
