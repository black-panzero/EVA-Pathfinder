import type { MissionRequest, ScienceSite } from "../api/types";
import { NumberField, Panel } from "./common";

export function MissionInputs({ req, setReq, sites, onEvaluate, busy, pickingHabitat, onPickHabitat, consumableLabel }: {
  req: MissionRequest; setReq: (r: MissionRequest) => void; sites: ScienceSite[]; onEvaluate: () => void; busy: boolean;
  pickingHabitat: boolean; onPickHabitat: () => void; consumableLabel: string;
}) {
  const toggleSite = (s: ScienceSite, on: boolean) => {
    const stops = on
      ? [...req.stops, { stop_id: s.id, name: s.name, point: { x_m: s.x_m, y_m: s.y_m }, activity_min: s.default_activity_min }]
      : req.stops.filter((x) => x.stop_id !== s.id);
    if (stops.length) setReq({ ...req, stops });
  };
  const setStop = (id: string, activity_min: number) => setReq({ ...req, stops: req.stops.map((s) => (s.stop_id === id ? { ...s, activity_min } : s)) });
  const p = req.profile, b = req.budget;
  return (
    <Panel title="Mission inputs" id="inputs" badge="ILLUSTRATIVE_MODEL">
      <fieldset>
        <legend>Habitat (simulated origin)</legend>
        <div className="grid2">
          <NumberField label="x" unit="m" value={Math.round(req.habitat.x_m)} onChange={(v) => setReq({ ...req, habitat: { ...req.habitat, x_m: v } })} />
          <NumberField label="y" unit="m" value={Math.round(req.habitat.y_m)} onChange={(v) => setReq({ ...req, habitat: { ...req.habitat, y_m: v } })} />
        </div>
        <button type="button" className={pickingHabitat ? "btn active" : "btn"} onClick={onPickHabitat} aria-pressed={pickingHabitat}>{pickingHabitat ? "Click the map…" : "Place habitat on map"}</button>
      </fieldset>
      <fieldset>
        <legend>Science stops (in visiting order)</legend>
        {sites.map((s) => {
          const stop = req.stops.find((x) => x.stop_id === s.id);
          return (
            <div key={s.id} className="stop-row">
              <label className="check"><input type="checkbox" checked={!!stop} onChange={(e) => toggleSite(s, e.target.checked)} disabled={!!stop && req.stops.length === 1} /> {s.name}</label>
              {stop && <NumberField label="Activity" unit="min" value={stop.activity_min} min={0} max={600} step={5} onChange={(v) => setStop(s.id, v)} />}
            </div>
          );
        })}
      </fieldset>
      <fieldset>
        <legend>Mobility (illustrative)</legend>
        <div className="grid2">
          <NumberField label="Flat speed" unit="m/min" value={p.flat_speed_m_per_min} min={1} step={1} onChange={(v) => setReq({ ...req, profile: { ...p, flat_speed_m_per_min: v } })} />
          <NumberField label="Ascent rate" unit="m/min" value={p.ascent_rate_m_per_min} min={0.5} step={0.5} onChange={(v) => setReq({ ...req, profile: { ...p, ascent_rate_m_per_min: v } })} />
          <NumberField label="Max slope" unit="°" value={p.max_slope_deg} min={1} max={60} step={0.5} onChange={(v) => setReq({ ...req, profile: { ...p, max_slope_deg: v } })} />
          <NumberField label="Slope weight" value={req.slope_weight} min={0} max={100} step={0.5} hint="terrain-aware policy" onChange={(v) => setReq({ ...req, slope_weight: v })} />
        </div>
        <label className="field"><span className="field-l">Route used for Guardian checks</span>
          <select value={req.route_choice} onChange={(e) => setReq({ ...req, route_choice: e.target.value as MissionRequest["route_choice"] })}>
            <option value="terrain">Terrain-aware</option><option value="shortest">Shortest feasible</option>
          </select>
        </label>
      </fieldset>
      <fieldset>
        <legend>Budgets (illustrative)</legend>
        <div className="grid2">
          <NumberField label="Time available" unit="min" value={b.time_available_min} min={0} max={1440} step={10} onChange={(v) => setReq({ ...req, budget: { ...b, time_available_min: v } })} />
          <NumberField label="Reserve" unit="%" value={Math.round(b.reserve_fraction * 100)} min={0} max={95} step={5} onChange={(v) => setReq({ ...req, budget: { ...b, reserve_fraction: Math.min(0.95, Math.max(0, v / 100)) } })} />
          <NumberField label="Consumable" unit="units" value={b.consumable_initial_units} min={0} step={10} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_initial_units: v } })} />
          <NumberField label="Use walking" unit="units/min" value={b.consumable_rate_traverse_per_min} min={0} step={0.1} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_rate_traverse_per_min: v } })} />
          <NumberField label="Use at stop" unit="units/min" value={b.consumable_rate_activity_per_min} min={0} step={0.1} onChange={(v) => setReq({ ...req, budget: { ...b, consumable_rate_activity_per_min: v } })} />
        </div>
        <p className="small muted">{consumableLabel}. These values are scenario inputs, not suit or physiology data.</p>
      </fieldset>
      <button type="button" className="btn primary wide" onClick={onEvaluate} disabled={busy}>{busy ? "Computing…" : "Evaluate Marswalk"}</button>
    </Panel>
  );
}

export function LayerPanel({ layers, setLayers, showTraverse, setShowTraverse, showPhotos, setShowPhotos, geologyUnits, titles }: {
  layers: Record<string, { visible: boolean; opacity: number }>; setLayers: (l: Record<string, { visible: boolean; opacity: number }>) => void;
  showTraverse: boolean; setShowTraverse: (v: boolean) => void; showPhotos: boolean; setShowPhotos: (v: boolean) => void;
  geologyUnits: { symbol: string; name: string; color: string }[]; titles: Record<string, { title: string; level: string }>;
}) {
  return (
    <Panel title="Map layers" id="layers">
      {Object.entries(layers).map(([id, cfg]) => (
        <div key={id} className="layer-row">
          <label className="check"><input type="checkbox" checked={cfg.visible} onChange={(e) => setLayers({ ...layers, [id]: { ...cfg, visible: e.target.checked } })} /> {titles[id]?.title ?? id}</label>
          <input type="range" min={0.1} max={1} step={0.05} value={cfg.opacity} aria-label={`${titles[id]?.title ?? id} opacity`} disabled={!cfg.visible}
            onChange={(e) => setLayers({ ...layers, [id]: { ...cfg, opacity: parseFloat(e.target.value) } })} />
        </div>
      ))}
      <label className="check"><input type="checkbox" checked={showTraverse} onChange={(e) => setShowTraverse(e.target.checked)} /> Perseverance traverse (rover localizations)</label>
      <label className="check"><input type="checkbox" checked={showPhotos} onChange={(e) => setShowPhotos(e.target.checked)} /> Rover photo locations</label>
      {layers.geology?.visible && geologyUnits.length > 0 && (
        <div className="legend">
          <p className="small muted">Geologic units (USGS SIM 3464). Regional context: offsets of 100-200 m from this base map are documented.</p>
          {geologyUnits.map((u) => <span key={u.symbol} className="legend-item"><i style={{ background: u.color }} />{u.symbol} {u.name}</span>)}
        </div>
      )}
      {layers.slope?.visible && (
        <div className="legend">
          <p className="small muted">Slope from 20 m DEM (degrees)</p>
          <div className="ramp slope-ramp" aria-hidden="true" /><div className="ramp-labels"><span>0</span><span>10</span><span>20</span><span>30+</span></div>
        </div>
      )}
    </Panel>
  );
}
