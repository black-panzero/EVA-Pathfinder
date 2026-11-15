import type { ReactNode } from "react";
import type { EvidenceLevel, Status } from "../api/types";
import { LEVEL_LABEL } from "../features/format";

export function Badge({ level }: { level: EvidenceLevel }) {
  return <span className={`badge badge-${level.toLowerCase()}`}>{LEVEL_LABEL[level] ?? level}</span>;
}

export function StatusPill({ status }: { status: Status }) {
  const icon = status === "FEASIBLE" ? "✓" : status === "INFEASIBLE" ? "✕" : "?";
  return (
    <span className={`status status-${status.toLowerCase()}`}>
      <span aria-hidden="true">{icon}</span> {status}
    </span>
  );
}

export function Panel({ title, children, badge, id, actions }: { title: string; children: ReactNode; badge?: EvidenceLevel; id?: string; actions?: ReactNode }) {
  return (
    <section className="panel" aria-labelledby={id ? `${id}-h` : undefined}>
      <header className="panel-h">
        <h2 id={id ? `${id}-h` : undefined}>{title}</h2>
        {badge && <Badge level={badge} />}
        {actions}
      </header>
      <div className="panel-b">{children}</div>
    </section>
  );
}

export function NumberField({ label, value, onChange, step = 1, min, max, unit, hint }: { label: string; value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; unit?: string; hint?: string }) {
  return (
    <label className="field">
      <span className="field-l">{label}{unit && <em> ({unit})</em>}</span>
      <input type="number" value={Number.isFinite(value) ? value : ""} step={step} min={min} max={max}
        onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) onChange(v); }} />
      {hint && <span className="field-h">{hint}</span>}
    </label>
  );
}

export function BudgetBar({ label, used, usable, total, unit }: { label: string; used: number | null; usable: number; total: number; unit: string }) {
  const u = used ?? Infinity;
  const pct = total > 0 ? Math.min(100, (Math.min(u, total) / total) * 100) : 0;
  const reservePct = total > 0 ? (usable / total) * 100 : 0;
  const over = u > usable;
  return (
    <div className="budget">
      <div className="budget-top">
        <span>{label}</span>
        <span className={over ? "over" : ""}>{Number.isFinite(u) ? `${u.toFixed(0)} / ${usable.toFixed(0)} ${unit} usable` : "no route"}{over ? " (over limit)" : ""}</span>
      </div>
      <div className="budget-track" role="img" aria-label={`${label}: ${Number.isFinite(u) ? u.toFixed(0) : "unknown"} of ${usable.toFixed(0)} ${unit} usable after reserve; total ${total.toFixed(0)}`}>
        <div className={`budget-fill ${over ? "over" : ""}`} style={{ width: `${pct}%` }} />
        <div className="budget-reserve" style={{ left: `${reservePct}%` }} title="Reserve threshold" />
      </div>
      <div className="budget-foot"><span>0</span><span>reserve begins at {usable.toFixed(0)}</span><span>{total.toFixed(0)} {unit}</span></div>
    </div>
  );
}
