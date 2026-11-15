import { useEffect, useState } from "react";
import type { DatasetsResponse, EvaluateResponse, MedaSeries, Observations, ScienceSite, StudyArea } from "../api/types";
import { fmt } from "../features/format";
import { Badge, Panel } from "./common";

type Tab = "science" | "photos" | "atmosphere" | "sources" | "labels";

function MedaChart({ s }: { s: MedaSeries }) {
  const W = 560, H = 150, pad = { l: 50, r: 10, t: 10, b: 26 };
  const pts = s.hourly;
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.min)), hi = Math.max(...pts.map((p) => p.max));
  const sx = (h: number) => pad.l + (h / 24) * (W - pad.l - pad.r);
  const sy = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${s.variable} hourly mean on this sol, ${lo.toFixed(1)} to ${hi.toFixed(1)} ${s.unit}`}>
      <path d={pts.map((p, i) => `${i ? "L" : "M"}${sx(p.lmst_hour + 0.5)},${sy(p.max)}`).join("") + pts.slice().reverse().map((p) => `L${sx(p.lmst_hour + 0.5)},${sy(p.min)}`).join("") + "Z"} className="band" />
      <polyline fill="none" stroke="#ffb703" strokeWidth={2} points={pts.map((p) => `${sx(p.lmst_hour + 0.5)},${sy(p.mean)}`).join(" ")} />
      {[0, 6, 12, 18, 24].map((h) => <text key={h} x={sx(h)} y={H - 8} textAnchor="middle" className="tick">{h}h</text>)}
      {[lo, (lo + hi) / 2, hi].map((v) => <text key={v} x={pad.l - 6} y={sy(v) + 4} textAnchor="end" className="tick">{v.toFixed(0)}</text>)}
    </svg>
  );
}

export function EvidencePanel({ sa, sites, obs, ds, plan, selectedPhoto, onSelectPhoto, onDownloadReport }: {
  sa: StudyArea; sites: ScienceSite[]; obs: Observations | null; ds: DatasetsResponse | null; plan: EvaluateResponse | null;
  selectedPhoto: string | null; onSelectPhoto: (id: string) => void; onDownloadReport: () => void;
}) {
  const [tab, setTab] = useState<Tab>("science");
  const tabs: [Tab, string][] = [["science", "Science"], ["photos", "Rover photos"], ["atmosphere", "Atmosphere (history)"], ["sources", "Sources & alignment"], ["labels", "Evidence labels"]];
  useEffect(() => { if (selectedPhoto) setTab("photos"); }, [selectedPhoto]);
  return (
    <Panel title="Science & evidence" id="evidence" actions={<button type="button" className="btn ghost small-btn" onClick={onDownloadReport} disabled={!plan}>Download report JSON</button>}>
      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" type="button" aria-selected={tab === id} className={tab === id ? "tab on" : "tab"} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <div role="tabpanel" className="tabpanel">
        {tab === "science" && sites.map((s) => (
          <article key={s.id} className="card">
            <h3>{s.name} <Badge level={s.evidence_level} /></h3>
            <p>{s.science_summary}</p>
            <p className="small muted">Location: {s.location_basis} ({s.lat_deg.toFixed(5)}°N, {s.lon_deg.toFixed(5)}°E; rover geoid elevation {fmt(s.rover_elev_geoid_m, 1, "m")}, DEM {fmt(s.dem_elev_m, 1, "m")}).</p>
            {s.mapped_geologic_unit && <p className="small">Mapped unit at this point: <strong>{s.mapped_geologic_unit.symbol}</strong> {s.mapped_geologic_unit.name}. <span className="muted">{s.mapped_geologic_unit.caveat}</span></p>}
            <ul className="cites">{s.citations.map((c) => <li key={c.url}><a href={c.url} target="_blank" rel="noreferrer">{c.title}</a></li>)}</ul>
          </article>
        ))}
        {tab === "science" && (
          <article className="card">
            <h3>Habitat <Badge level="SIMULATED" /></h3>
            <p className="small">{sa.habitat.note}</p>
          </article>
        )}
        {tab === "photos" && (obs?.photos.length ? obs.photos.map((p) => (
          <article key={p.photo_id} className={`card photo ${selectedPhoto === p.photo_id ? "sel" : ""}`} onClick={() => onSelectPhoto(p.photo_id)}>
            <img src={p.image_url} alt={`Perseverance ${p.instrument} raw image, sol ${p.sol}, near ${p.site_name}`} loading="lazy" />
            <div>
              <h3>{p.site_name}: sol {p.sol} <Badge level="NASA_OBSERVATION" /></h3>
              <p className="small">{p.instrument}, {p.date_taken_utc} UTC; mast azimuth {p.mast_azimuth_deg}°, elevation {p.mast_elevation_deg}°.</p>
              <p className="small muted">Geolocation: {p.geolocation.basis}. The photo shows the view from the rover, not an overhead footprint.</p>
              <p className="small">Credit: {p.credit}. <a href={p.source_url} target="_blank" rel="noreferrer">NASA raw image page</a></p>
            </div>
          </article>
        )) : <p className="muted">No geolocated rover photos ingested.</p>)}
        {tab === "atmosphere" && (obs?.atmosphere?.series ? (
          <div>
            <p className="small"><Badge level="NASA_OBSERVATION" /> {obs.atmosphere.scope}</p>
            {obs.atmosphere.series.map((s) => (
              <figure key={s.variable} className="card">
                <figcaption><strong>{s.instrument}: {s.variable.replace(/_/g, " ").toLowerCase()}</strong> ({s.unit}), hourly mean with min-max band, by local mean solar time. File {s.file}.</figcaption>
                <MedaChart s={s} />
                {s.note && <p className="small muted">{s.note}</p>}
              </figure>
            ))}
            <p className="small muted">{obs.atmosphere.aggregation}</p>
          </div>
        ) : <p className="muted">Historical MEDA data not yet integrated.</p>)}
        {tab === "sources" && ds && (
          <div>
            <h3>Alignment checks</h3>
            <ul className="small">
              <li>Optical vs DEM: same CRS and grid origin (difference {ds.alignment.ortho_dem_grid_origin_difference_m.map((v) => v.toFixed(3)).join(", ")} m). Both come from the same USGS Mars 2020 TRN production.</li>
              <li>DEM vs {ds.alignment.dem_vs_rover_elevation.n} rover-reported geoid elevations: median difference {ds.alignment.dem_vs_rover_elevation.median_dem_minus_rover_m} m, median absolute {ds.alignment.dem_vs_rover_elevation.median_abs_m} m (5-95%: {ds.alignment.dem_vs_rover_elevation.p05_m} to {ds.alignment.dem_vs_rover_elevation.p95_m} m).</li>
              <li>Image-gradient cross-correlation peaked at a shift of {ds.alignment.registration_check.best_shift_cells.rows} rows, {ds.alignment.registration_check.best_shift_cells.cols} cols (r {ds.alignment.registration_check.best_correlation} vs {ds.alignment.registration_check.zero_shift_correlation} at zero). Shadows bias this check, so the result is <strong>inconclusive</strong>, not a measured offset.</li>
              <li>Geology: <strong>{ds.alignment.geology_status}</strong>. {ds.alignment.geology_note}</li>
            </ul>
            <h3>Datasets</h3>
            {ds.datasets.map((d) => (
              <article key={d.source_id} className="card">
                <h4>{d.title} <span className={`vs vs-${d.verification_status.toLowerCase()}`}>{d.verification_status}</span></h4>
                <p className="small">{[d.mission, d.instrument, d.producer].filter(Boolean).join(" · ")}</p>
                <p className="small"><a href={d.landing_page} target="_blank" rel="noreferrer">Source page</a>{d.units ? ` · Units: ${d.units}` : ""}{d.license ? ` · ${d.license}` : ""}</p>
                {d.files.slice(0, 2).map((f) => <p key={f.path} className="small mono">sha256 {f.sha256.slice(0, 16)}… {f.path.split("/").pop()}</p>)}
                {d.citation && <p className="small muted">{d.citation}</p>}
              </article>
            ))}
          </div>
        )}
        {tab === "labels" && (
          <div>
            {(plan?.evidence ?? []).map((e) => (
              <div key={e.item} className="label-row"><Badge level={e.level} /> <strong>{e.item}</strong> <span className="muted small">{e.detail}</span></div>
            ))}
            {plan && <details><summary>Run manifest</summary><pre className="mono small">{JSON.stringify(plan.run_manifest, null, 2)}</pre></details>}
          </div>
        )}
      </div>
    </Panel>
  );
}
