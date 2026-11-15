import { useState, type ReactNode } from "react";
import { CheckCircle2, ChevronDown, HelpCircle, Minus, Plus, XCircle } from "lucide-react";
import type { EvidenceLevel, Status } from "../api/types";

/** Signature detail: a provenance dot next to values, so every number says where it came from. */
const PROV: Record<EvidenceLevel, { label: string; cls: string; hint: string }> = {
  NASA_OBSERVATION: { label: "Observed", cls: "obs", hint: "Measured by a NASA/USGS instrument" },
  DERIVED: { label: "Derived", cls: "der", hint: "Computed by this software from observations" },
  ILLUSTRATIVE_MODEL: { label: "Assumed", cls: "asm", hint: "Scenario input you can change; not certified" },
  SIMULATED_EVENT: { label: "Simulated", cls: "sim", hint: "Hypothetical event or object" },
  SIMULATED: { label: "Simulated", cls: "sim", hint: "Hypothetical event or object" },
  UNKNOWN: { label: "Unknown", cls: "unk", hint: "Not resolvable with the available data" },
};

export function Prov({ level, label = true }: { level: EvidenceLevel; label?: boolean }) {
  const p = PROV[level] ?? PROV.UNKNOWN;
  return (
    <span className={`prov prov-${p.cls}`} title={p.hint}>
      <i aria-hidden="true" />
      {label ? p.label : <span className="sr-only">{p.label}</span>}
    </span>
  );
}

export const STATUS_TEXT: Record<Status, string> = { FEASIBLE: "Feasible", INFEASIBLE: "Infeasible", UNKNOWN: "Unknown" };

export function StatusBadge({ status, size = "md" }: { status: Status; size?: "md" | "lg" }) {
  const Icon = status === "FEASIBLE" ? CheckCircle2 : status === "INFEASIBLE" ? XCircle : HelpCircle;
  return (
    <span className={`status status-${status.toLowerCase()} status-${size}`}>
      <Icon size={size === "lg" ? 18 : 14} strokeWidth={1.75} aria-hidden="true" />
      {STATUS_TEXT[status]}
      <span className="sr-only"> ({status})</span>
    </span>
  );
}

export function Stepper({ label, value, onChange, step = 1, min = 0, max = 1e6, unit, hint }: {
  label: string; value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; unit?: string; hint?: string;
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, Math.round(v / step) * step));
  return (
    <label className="stepper">
      <span className="stepper-label">{label}{hint && <span className="hint">{hint}</span>}</span>
      <span className="stepper-ctl">
        <button type="button" aria-label={`Decrease ${label}`} onClick={() => onChange(clamp(value - step))}><Minus size={14} strokeWidth={1.75} /></button>
        <input type="number" inputMode="decimal" value={Number.isFinite(value) ? value : ""} step={step} min={min} max={max} aria-label={label}
          onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) onChange(v); }} />
        {unit && <span className="unit">{unit}</span>}
        <button type="button" aria-label={`Increase ${label}`} onClick={() => onChange(clamp(value + step))}><Plus size={14} strokeWidth={1.75} /></button>
      </span>
    </label>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} className={value === o.value ? "on" : ""} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Disclosure({ title, children, defaultOpen = false }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`disclosure ${open ? "open" : ""}`}>
      <button type="button" className="disclosure-h" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronDown size={16} strokeWidth={1.75} aria-hidden="true" />{title}
      </button>
      {open && <div className="disclosure-b">{children}</div>}
    </div>
  );
}

export function Bar({ label, used, usable, total, unit, level = "ILLUSTRATIVE_MODEL" }: { label: string; used: number | null; usable: number; total: number; unit: string; level?: EvidenceLevel }) {
  const u = used ?? Infinity;
  const pct = total > 0 ? Math.min(100, (Math.min(u, total) / total) * 100) : 0;
  const reservePct = total > 0 ? (usable / total) * 100 : 0;
  const over = u > usable;
  return (
    <div className="bar">
      <div className="bar-top">
        <span>{label} <Prov level={level} label={false} /></span>
        <span className={`num ${over ? "neg" : ""}`}>{Number.isFinite(u) ? `${Math.round(u)} of ${Math.round(usable)} ${unit}` : "no route"}{over ? " · over limit" : ""}</span>
      </div>
      <div className="bar-track" role="img" aria-label={`${label}: ${Number.isFinite(u) ? Math.round(u) : "unknown"} of ${Math.round(usable)} ${unit} usable after reserve, ${Math.round(total)} total`}>
        <div className={`bar-fill ${over ? "over" : ""}`} style={{ width: `${pct}%` }} />
        <div className="bar-reserve" style={{ left: `${reservePct}%` }} />
      </div>
      <div className="bar-foot"><span>Reserve starts at {Math.round(usable)}</span><span>{Math.round(total)} {unit} total</span></div>
    </div>
  );
}

export function StepHeader({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <header className="step-h">
      <p className="step-n">Step {n} of 5</p>
      <h2>{title}</h2>
      <p className="step-d">{children}</p>
    </header>
  );
}
