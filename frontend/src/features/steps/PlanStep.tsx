import { Check, Crosshair, Home, MapPin } from "lucide-react";
import type { MissionRequest, ScienceSite } from "../../api/types";
import { Disclosure, Prov, StepHeader, Stepper } from "../../components/ui";

export function PlanStep({ req, setReq, sites, picking, onPickHabitat, onFocus }: {
  req: MissionRequest; setReq: (r: MissionRequest) => void; sites: ScienceSite[];
  picking: boolean; onPickHabitat: () => void; onFocus: (x: number, y: number) => void;
}) {
  const p = req.profile, b = req.budget;
  const toggle = (s: ScienceSite) => {
    const on = req.stops.some((x) => x.stop_id === s.id);
    const stops = on ? req.stops.filter((x) => x.stop_id !== s.id) : [...req.stops, { stop_id: s.id, name: s.name, point: { x_m: s.x_m, y_m: s.y_m }, activity_min: s.default_activity_min }];
    if (stops.length) setReq({ ...req, stops });
  };
  const setAct = (id: string, v: number) => setReq({ ...req, stops: req.stops.map((s) => (s.stop_id === id ? { ...s, activity_min: v } : s)) });

  return (
    <>
      <StepHeader n={1} title="Plan the walk">
        Pick where the crew starts, which science sites to visit and the limits the walk must respect
      </StepHeader>

      <section className="group">
        <h3>Start point</h3>
        <div className="row-card">
          <Home size={18} strokeWidth={1.5} className="ic" aria-hidden="true" />
          <div className="grow">
            <div className="t">Habitat <Prov level="SIMULATED" /></div>
            <div className="m num">x {Math.round(req.habitat.x_m)} m · y {Math.round(req.habitat.y_m)} m</div>
          </div>
          <button type="button" className={`btn sm ${picking ? "active" : ""}`} onClick={onPickHabitat} aria-pressed={picking}>
            <Crosshair size={14} strokeWidth={1.75} aria-hidden="true" />{picking ? "Click the map" : "Move"}
          </button>
        </div>
        <p className="note">Placed at Perseverance's first position after landing, a flat, well-documented spot. No habitat exists on Mars</p>
      </section>

      <section className="group">
        <h3>Science stops <span className="meta">visited in this order</span></h3>
        <div className="site-list">
          {sites.map((s, i) => {
            const stop = req.stops.find((x) => x.stop_id === s.id);
            const order = req.stops.findIndex((x) => x.stop_id === s.id) + 1;
            return (
              <div key={s.id} className={`site ${stop ? "on" : ""}`}>
                <button type="button" className="site-main" role="checkbox" aria-checked={!!stop} onClick={() => toggle(s)} disabled={!!stop && req.stops.length === 1}
                  title={!!stop && req.stops.length === 1 ? "At least one stop is required" : undefined}>
                  <span className="check" aria-hidden="true">{stop ? <span className="num">{order}</span> : <Check size={12} strokeWidth={2} opacity={0} />}</span>
                  <span className="grow">
                    <span className="t">{s.name}</span>
                    <span className="m">{i === 0 ? "Organic-rich lake mudstone on the delta front" : "Backup cache of 10 sample tubes near the delta base"}</span>
                  </span>
                </button>
                <button type="button" className="icon-btn" aria-label={`Show ${s.name} on the map`} onClick={() => onFocus(s.x_m, s.y_m)}><MapPin size={16} strokeWidth={1.5} /></button>
                {stop && <div className="site-act"><Stepper label="Time at site" unit="min" value={stop.activity_min} min={0} max={600} step={5} onChange={(v) => setAct(s.id, v)} /></div>}
              </div>
            );
          })}
        </div>
      </section>

      <section className="group">
        <h3>Limits <Prov level="ILLUSTRATIVE_MODEL" /></h3>
        <div className="fields">
          <Stepper label="Steepest allowed slope" unit="°" value={p.max_slope_deg} min={1} max={60} step={1} onChange={(v) => setReq({ ...req, profile: { ...p, max_slope_deg: v } })} />
          <Stepper label="Time available" unit="min" value={b.time_available_min} min={0} max={1440} step={10} onChange={(v) => setReq({ ...req, budget: { ...b, time_available_min: v } })} />
          <Stepper label="Safety reserve" unit="%" value={Math.round(b.reserve_fraction * 100)} min={0} max={95} step={5} hint="kept back from time and supplies"
            onChange={(v) => setReq({ ...req, budget: { ...b, reserve_fraction: Math.min(0.95, Math.max(0, v / 100)) } })} />
        </div>
        <Disclosure title="More assumptions">
          <div className="fields">
            <Stepper label="Walking speed on flat ground" unit="m/min" value={p.flat_speed_m_per_min} min={1} max={500} step={1} onChange={(v) => setReq({ ...req, profile: { ...p, flat_speed_m_per_min: v } })} />
            <Stepper label="Climbing rate" unit="m/min" value={p.ascent_rate_m_per_min} min={0.5} max={200} step={0.5} onChange={(v) => setReq({ ...req, profile: { ...p, ascent_rate_m_per_min: v } })} />
            <Stepper label="Supplies at start" unit="units" value={b.consumable_initial_units} min={0} step={10} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_initial_units: v } })} />
            <Stepper label="Use while walking" unit="u/min" value={b.consumable_rate_traverse_per_min} min={0} step={0.1} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_rate_traverse_per_min: Math.round(v * 10) / 10 } })} />
            <Stepper label="Use at a site" unit="u/min" value={b.consumable_rate_activity_per_min} min={0} step={0.1} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_rate_activity_per_min: Math.round(v * 10) / 10 } })} />
            <Stepper label="Slope avoidance" value={req.slope_weight} min={0} max={100} step={0.5} hint="terrain-aware route only" onChange={(v) => setReq({ ...req, slope_weight: v })} />
          </div>
          <p className="note">Supplies are a generic illustrative consumable, not oxygen or suit data. Time uses distance ÷ walking speed plus climb ÷ climbing rate</p>
        </Disclosure>
      </section>
    </>
  );
}
