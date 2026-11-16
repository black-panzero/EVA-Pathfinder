import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import type { DatasetsResponse, EvaluateResponse, MedaSeries, Observations, ScienceSite, StudyArea } from "../../api/types";
import { Prov, StepHeader } from "../../components/ui";
import { fmt } from "../format";

type Tab = "science" | "photos" | "weather" | "sources" | "labels";

function MedaChart({ s }: { s: MedaSeries }) {
  const W = 400, H = 150, pad = { l: 44, r: 8, t: 8, b: 24 };
  const pts = s.hourly;
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.min)), hi = Math.max(...pts.map((p) => p.max));
  const sx = (h: number) => pad.l + (h / 24) * (W - pad.l - pad.r);
  const sy = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`${s.variable} hourly mean, ${lo.toFixed(0)} to ${hi.toFixed(0)} ${s.unit}`}>
      {[lo, (lo + hi) / 2, hi].map((v) => <g key={v}><line x1={pad.l} x2={W - pad.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={pad.l - 6} y={sy(v) + 4} textAnchor="end" className="tick">{v.toFixed(0)}</text></g>)}
      <path d={pts.map((p, i) => `${i ? "L" : "M"}${sx(p.lmst_hour + 0.5)},${sy(p.max)}`).join("") + pts.slice().reverse().map((p) => `L${sx(p.lmst_hour + 0.5)},${sy(p.min)}`).join("") + "Z"} className="band" />
      <polyline fill="none" stroke="#ff7a45" strokeWidth={1.75} strokeLinejoin="round" points={pts.map((p) => `${sx(p.lmst_hour + 0.5)},${sy(p.mean)}`).join(" ")} />
      {[0, 6, 12, 18, 24].map((h) => <text key={h} x={sx(h)} y={H - 6} textAnchor="middle" className="tick">{h}h</text>)}
    </svg>
  );
}

export function EvidenceStep({ sa, sites, obs, ds, plan, selectedPhoto, selectedSite }: {
  sa: StudyArea; sites: ScienceSite[]; obs: Observations | null; ds: DatasetsResponse | null; plan: EvaluateResponse | null; selectedPhoto: string | null; selectedSite?: { id: string; n: number } | null;
}) {
  const [tab, setTab] = useState<Tab>("science");
  useEffect(() => { if (selectedPhoto) setTab("photos"); }, [selectedPhoto]);
  useEffect(() => {
    if (!selectedSite) return;
    setTab("science");
    setTimeout(() => document.getElementById(`site-${selectedSite.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  }, [selectedSite]);
  const tabs: [Tab, string][] = [["science", "Science"], ["photos", "Rover photos"], ["weather", "Weather history"], ["sources", "Data sources"], ["labels", "Labels"]];
  const ev = ds?.alignment.dem_vs_rover_elevation;
  return (
    <>
      <StepHeader n={5} title="Review the evidence">
        Where every number comes from: the science behind each site, real rover photos, weather records and the source data
      </StepHeader>
      <div className="tabs" role="tablist" aria-label="Evidence">
        {tabs.map(([id, label]) => <button key={id} role="tab" type="button" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{label}</button>)}
      </div>
      <div role="tabpanel">
        {tab === "science" && (
          <>
            {sites.map((s) => (
              <article key={s.id} id={`site-${s.id}`} className={`card ${selectedSite?.id === s.id ? "sel" : ""}`}>
                <h3>{s.name} <Prov level={s.evidence_level} />{s.in_planning_area === false && <span className="meta">outside planning area</span>}</h3>
                {(s.samples?.length || s.sample_sol) && <p className="m num">{s.samples?.length ? `Samples: ${s.samples.join(", ")}` : ""}{s.sample_sol ? ` · collected sol ${s.sample_sol}` : ""}{s.campaign ? ` · ${s.campaign}` : ""}</p>}
                <p>{s.science_summary}</p>
                {s.mapped_geologic_unit && <p className="m">Mapped rock unit: <span className="mono">{s.mapped_geologic_unit.symbol}</span> {s.mapped_geologic_unit.name}, regional context</p>}
                <p className="m num">{s.lat_deg.toFixed(5)}°N {s.lon_deg.toFixed(5)}°E · rover site {s.site}, drive {s.drive}, sol {s.sol}</p>
                <ul className="links">{s.citations.map((c) => <li key={c.url}><a href={c.url} target="_blank" rel="noreferrer">{c.title}<ExternalLink size={12} strokeWidth={1.75} aria-hidden="true" /></a></li>)}</ul>
              </article>
            ))}
            <article className="card"><h3>Habitat <Prov level="SIMULATED" /></h3><p className="m">{sa.habitat.note}</p></article>
          </>
        )}
        {tab === "photos" && (obs?.photos.length ? obs.photos.map((p) => (
          <figure key={p.photo_id} className={`card photo ${selectedPhoto === p.photo_id ? "sel" : ""}`}>
            <img src={p.image_url} alt={`Perseverance Navcam raw image, sol ${p.sol}, at ${p.site_name}`} loading="lazy" />
            <figcaption>
              <span className="t">{p.site_name} <Prov level="NASA_OBSERVATION" /></span>
              <span className="m num">Navcam · sol {p.sol} · {p.date_taken_utc.slice(0, 10)} · looking {Math.round(parseFloat(p.mast_azimuth_deg))}° azimuth</span>
              <span className="m">Positioned by matching the image's rover site {p.geolocation.site} / drive {p.geolocation.drive} to NASA's position record</span>
              <a href={p.source_url} target="_blank" rel="noreferrer">NASA raw image page<ExternalLink size={12} strokeWidth={1.75} aria-hidden="true" /></a>
            </figcaption>
          </figure>
        )) : <p className="m">No geolocated rover photos ingested</p>)}
        {tab === "weather" && (obs?.atmosphere?.series ? (
          <>
            <p className="callout">Recorded by Perseverance on sol {obs.atmosphere.sol} at the Three Forks depot. History, not a forecast</p>
            {obs.atmosphere.series.map((s) => (
              <figure key={s.variable} className="card">
                <figcaption className="t">{s.variable === "PRESSURE" ? "Air pressure" : "Heat radiated by the ground"} <span className="meta">{s.unit} · hourly, local solar time</span> <Prov level="NASA_OBSERVATION" label={false} /></figcaption>
                <MedaChart s={s} />
              </figure>
            ))}
            <p className="note">{obs.atmosphere.aggregation}</p>
          </>
        ) : <p className="m">Historical weather not integrated</p>)}
        {tab === "sources" && ds && (
          <>
            <article className="card">
              <h3>How well the layers line up</h3>
              <dl className="kv">
                <dt>Photo vs elevation grid</dt><dd className="num">{ds.alignment.ortho_dem_grid_origin_difference_m.map((v) => v.toFixed(2)).join(", ")} m offset</dd>
                {ev && <><dt>Elevation vs {ev.n} rover readings</dt><dd className="num">{fmt(ev.median_abs_m, 2, "m")} median difference</dd></>}
                <dt>Geologic map</dt><dd>Partial, 100-200 m offsets</dd>
              </dl>
              <p className="note">An image-matching check was inconclusive because of shadows; it is reported, not hidden</p>
            </article>
            {ds.datasets.map((d) => (
              <article key={d.source_id} className="card">
                <h3>{d.title}</h3>
                <p className="m">{[d.mission, d.instrument].filter(Boolean).join(" · ")}</p>
                <p className="m"><span className={`vs vs-${d.verification_status.toLowerCase()}`}>{d.verification_status === "AVAILABLE_VERIFIED" ? "Verified" : d.verification_status === "PARTIAL" ? "Partial" : "Unavailable"}</span>
                  {d.files[0] && <span className="mono"> sha256 {d.files[0].sha256.slice(0, 12)}…</span>}</p>
                <a href={d.landing_page} target="_blank" rel="noreferrer">Source<ExternalLink size={12} strokeWidth={1.75} aria-hidden="true" /></a>
              </article>
            ))}
          </>
        )}
        {tab === "labels" && (
          <>
            {(plan?.evidence ?? []).map((e) => (
              <div key={e.item} className="label-row"><Prov level={e.level} /><span><span className="t">{e.item}</span><span className="m">{e.detail}</span></span></div>
            ))}
            {plan && <details className="disclosure-raw"><summary>Run manifest</summary><pre className="mono">{JSON.stringify(plan.run_manifest, null, 2)}</pre></details>}
          </>
        )}
      </div>
    </>
  );
}
