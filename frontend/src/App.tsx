import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, Check, Download, GitCompareArrows, HelpCircle, ShieldCheck, SlidersHorizontal, TriangleAlert } from "lucide-react";
import { api, ApiRequestError, STATIC_MODE } from "./api/client";
import type { DatasetsResponse, EvaluateResponse, MissionRequest, Observations, ReplanRequest, ReplanResponse, ScienceSite, StudyArea, XY } from "./api/types";
import { Guide } from "./components/Guide";
import { StatusBadge } from "./components/ui";
import { fmt, fmtMin } from "./features/format";
import { ContingencyStep, type ContingencyState } from "./features/steps/ContingencyStep";
import { EvidenceStep } from "./features/steps/EvidenceStep";
import { FeasibilityStep } from "./features/steps/FeasibilityStep";
import { PlanStep } from "./features/steps/PlanStep";
import { type Plans, routeTotals, RoutesStep } from "./features/steps/RoutesStep";
import { MarsMap, type MapRoute, type MapView, type PickMode } from "./map/MarsMap";

type StepId = 1 | 2 | 3 | 4 | 5;
const STEPS: { id: StepId; title: string; icon: typeof Check }[] = [
  { id: 1, title: "Plan", icon: SlidersHorizontal },
  { id: 2, title: "Routes", icon: GitCompareArrows },
  { id: 3, title: "Feasibility", icon: ShieldCheck },
  { id: 4, title: "Contingency", icon: TriangleAlert },
  { id: 5, title: "Evidence", icon: BookOpen },
];
const GUIDE_KEY = "eva-pathfinder-guide-v1";
const errText = (e: unknown) => (e instanceof ApiRequestError ? `${e.message} (${e.code})` : String(e));
const poly = (p: EvaluateResponse | null) => (p ? p.assessment.legs.flatMap((l) => l.route?.polyline_xy_m ?? []) : []);
const seenGuide = () => { try { return localStorage.getItem(GUIDE_KEY) === "1"; } catch { return false; } };

function Mark() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" className="mark">
      <circle cx="5" cy="17" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7.5 16 C 11 14, 11 8, 15 7.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2.2 2.2" />
      <circle cx="18" cy="7" r="2.5" fill="#ff7a45" />
    </svg>
  );
}

export default function App() {
  const [sa, setSa] = useState<StudyArea | null>(null);
  const [obs, setObs] = useState<Observations | null>(null);
  const [ds, setDs] = useState<DatasetsResponse | null>(null);
  const [req, setReq] = useState<MissionRequest | null>(null);
  const [sites, setSites] = useState<ScienceSite[]>([]);
  const [plans, setPlans] = useState<Plans>({ shortest: null, terrain: null });
  const [planKey, setPlanKey] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<StepId>(1);
  const [view, setView] = useState<MapView>("ortho");
  const [showTraverse, setShowTraverse] = useState(false);
  const [showPhotos, setShowPhotos] = useState(true);
  const [pick, setPick] = useState<PickMode>("none");
  const [cont, setCont] = useState<ContingencyState>({ elapsed_min: 0, radius_m: 250, position_fraction: 0.5, response_mode: "return_now", consumable_loss_units: 0, center: null });
  const [replan, setReplan] = useState<ReplanResponse | null>(null);
  const [replanReq, setReplanReq] = useState<ReplanRequest | null>(null);
  const [replanBusy, setReplanBusy] = useState(false);
  const [replanErr, setReplanErr] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [guide, setGuide] = useState(!seenGuide());
  const [focus, setFocus] = useState<{ x: number; y: number; n: number } | null>(null);

  // inputs that change routes (route_choice only selects between the two computed plans)
  const inputKey = req ? JSON.stringify({ ...req, route_choice: undefined }) : "";
  const stale = !!planKey && planKey !== inputKey;

  const evaluate = useCallback(async (r: MissionRequest) => {
    setBusy(true); setError(null); setReplan(null); setReplanReq(null);
    try {
      const [shortest, terrain] = await Promise.all([api.evaluate({ ...r, route_choice: "shortest" }), api.evaluate({ ...r, route_choice: "terrain" })]);
      setPlans({ shortest, terrain });
      setPlanKey(JSON.stringify({ ...r, route_choice: undefined }));
      const a = (r.route_choice === "shortest" ? shortest : terrain).assessment;
      if (a.legs.every((l) => l.minutes !== null)) {
        const beforeReturn = a.legs.slice(0, -1).reduce((s, l) => s + (l.minutes ?? 0), 0) + a.activities.reduce((s, x) => s + x.minutes, 0);
        setCont((c) => ({ ...c, elapsed_min: Math.round(beforeReturn + 0.3 * (a.legs[a.legs.length - 1].minutes ?? 0)) }));
      }
      return true;
    } catch (e) {
      setError(errText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [s, o, d, def, sci] = await Promise.all([api.studyArea(), api.observations(), api.datasets(), api.defaultMission(), api.scienceSites()]);
        setSa(s); setObs(o); setDs(d); setReq(def.request); setSites(sci.sites);
        evaluate(def.request);
      } catch (e) {
        setError(errText(e));
      }
    })();
  }, [evaluate]);

  const chosen = req?.route_choice ?? "terrain";
  const chosenPlan = plans[chosen];
  const otherPlan = plans[chosen === "terrain" ? "shortest" : "terrain"];
  const a = chosenPlan?.assessment ?? null;

  const closeGuide = () => { setGuide(false); try { localStorage.setItem(GUIDE_KEY, "1"); } catch { /* private mode */ } };
  const onPick = (mode: PickMode, p: XY) => {
    if (!req) return;
    if (mode === "habitat") setReq({ ...req, habitat: p });
    if (mode === "zone") setCont((c) => ({ ...c, center: p }));
    setPick("none");
  };
  const runScenario = async () => {
    if (!req) return;
    const body: ReplanRequest = {
      mission: req, elapsed_min: cont.elapsed_min, response_mode: cont.response_mode, consumable_loss_units: cont.consumable_loss_units,
      event: { type: "BLOCKED_ZONE", radius_m: cont.radius_m, center: cont.center, position_fraction: cont.position_fraction },
    };
    setReplanBusy(true); setReplanErr(null);
    try { setReplan(await api.replan(body)); setReplanReq(body); } catch (e) { setReplanErr(errText(e)); setReplan(null); } finally { setReplanBusy(false); }
  };
  const downloadReport = async () => {
    if (!req) return;
    try {
      const rep = await api.report(req, replanReq);
      const url = URL.createObjectURL(new Blob([JSON.stringify(rep, null, 2)], { type: "application/json" }));
      const el = document.createElement("a");
      el.href = url; el.download = "eva-pathfinder-report.json"; el.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(errText(e)); }
  };
  const next = async () => {
    if (!req) return;
    if (step === 1 && (stale || !chosenPlan)) { if (await evaluate(req)) setStep(2); return; }
    setStep((s) => (Math.min(5, s + 1) as StepId));
  };

  const mapRoutes: MapRoute[] = useMemo(() => {
    if (replan && step === 4) {
      return [
        { id: "before", points: replan.before.legs.flatMap((l) => l.route?.polyline_xy_m ?? []), color: "#85858b", dashed: true, label: "Old path home", weight: 2 },
        { id: "after", points: replan.after.legs.flatMap((l) => l.route?.polyline_xy_m ?? []), color: "#4cc38a", label: "New path home", weight: 3 },
      ];
    }
    const out: MapRoute[] = [];
    const altLabel = chosen === "terrain" ? "Shortest" : "Terrain-aware";
    if (otherPlan) out.push({ id: "alt", points: poly(otherPlan), color: "#ededed", dashed: true, label: altLabel, weight: 2 });
    if (chosenPlan) out.push({ id: "sel", points: poly(chosenPlan), color: "#ff7a45", label: `${chosen === "terrain" ? "Terrain-aware" : "Shortest"} (selected)`, weight: 3 });
    return out;
  }, [replan, step, chosenPlan, otherPlan, chosen]);

  if (!sa || !req) {
    return (
      <main className="boot">
        <Mark /><h1>EVA Pathfinder</h1>
        <p role="status" className={error ? "neg" : "m"}>{error ?? "Loading the Jezero Crater study area…"}</p>
      </main>
    );
  }

  const t = routeTotals(chosenPlan);
  const summaries: Record<StepId, string> = {
    1: `${req.stops.length} stop${req.stops.length > 1 ? "s" : ""} · ${req.profile.max_slope_deg}° limit · ${req.budget.time_available_min} min`,
    2: t ? `${fmt(t.length !== null ? t.length / 1000 : null, 2, "km")} round trip` : busy ? "Computing…" : "Not computed",
    3: a ? (a.status === "FEASIBLE" ? `${Math.round(a.totals.time_margin_min ?? 0)} min margin` : a.reason_codes[0]?.toLowerCase().replace(/_/g, " ") ?? a.status.toLowerCase()) : "Waiting for routes",
    4: replan ? replan.status_change.replace("->", "→").toLowerCase() : "Not run",
    5: ds ? `${ds.datasets.length} sources` : "",
  };
  const done = (id: StepId) => (id === 1 && !!chosenPlan && !stale) || (id === 2 && !!chosenPlan && step > 2) || (id === 3 && step > 3) || (id === 4 && !!replan);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><Mark /><span>EVA Pathfinder</span></div>
        <div className="crumb"><span>Jezero Crater, Mars</span><span className="m">Operation Delta Return · simulated mission</span></div>
        <div className="top-actions">
          {a && !stale && <StatusBadge status={a.status} />}
          <button type="button" className="btn sm ghost" onClick={() => setGuide(true)}><HelpCircle size={14} strokeWidth={1.75} aria-hidden="true" />How it works</button>
          <button type="button" className="btn sm" onClick={downloadReport} disabled={!chosenPlan}><Download size={14} strokeWidth={1.75} aria-hidden="true" />Report</button>
        </div>
      </header>

      <nav className="rail" aria-label="Planning steps">
        <ol>
          {STEPS.map(({ id, title, icon: Icon }) => (
            <li key={id}>
              <button type="button" className={`rail-item ${step === id ? "on" : ""}`} aria-current={step === id ? "step" : undefined} onClick={() => setStep(id)}>
                <span className={`rail-n ${done(id) ? "done" : ""}`} aria-hidden="true">{done(id) ? <Check size={12} strokeWidth={2.25} /> : id}</span>
                <span className="rail-body">
                  <span className="rail-t"><Icon size={14} strokeWidth={1.5} aria-hidden="true" />{title}</span>
                  <span className="rail-s">{summaries[id]}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
        <div className="rail-foot">
          <p className="m">Real NASA/USGS terrain at 20 m. Habitat, crew and events are simulated</p>
          <p className="m">Research prototype, not certified for EVA navigation</p>
          {STATIC_MODE && <p className="m">The planning engine runs in your browser</p>}
          <p className="m">Code and docs written with AI assistance (Claude Code by Anthropic), reviewed by team Midgardians. No AI-generated imagery</p>
        </div>
      </nav>

      <main className="stage">
        <MarsMap sa={sa} view={view} setView={setView} showTraverse={showTraverse} setShowTraverse={setShowTraverse} showPhotos={showPhotos} setShowPhotos={setShowPhotos}
          routes={mapRoutes} habitat={req.habitat} stops={req.stops.map((s) => ({ id: s.stop_id, name: s.name, point: s.point }))} sites={sites} photos={obs?.photos ?? []}
          zone={step === 4 ? (replan ? { center: replan.event.center_xy_m, radius_m: replan.event.radius_m } : cont.center ? { center: [cont.center.x_m, cont.center.y_m], radius_m: cont.radius_m } : null) : null}
          crew={step === 4 && replan ? { x_m: replan.current_position.x_m, y_m: replan.current_position.y_m } : null}
          pickMode={pick} onPick={onPick} onCancelPick={() => setPick("none")} onSelectPhoto={(id) => { setPhoto(id); setStep(5); }} focus={focus}
          fitPoints={[...poly(plans.terrain), ...poly(plans.shortest), [req.habitat.x_m, req.habitat.y_m], ...sites.map((s) => [s.x_m, s.y_m] as [number, number])]} fitKey={planKey} />
      </main>

      <aside className="panel" aria-label={`Step ${step}`}>
        <div className="panel-scroll">
          {error && <p className="callout neg" role="alert">{error}</p>}
          {busy && <p className="callout" role="status">{STATIC_MODE && !chosenPlan ? "Starting the planning engine in your browser, this takes 10-30 s the first time…" : "Computing routes on the elevation map…"}</p>}
          {step === 1 && <PlanStep req={req} setReq={setReq} sites={sites} picking={pick === "habitat"} onPickHabitat={() => setPick(pick === "habitat" ? "none" : "habitat")}
            onFocus={(x, y) => setFocus({ x, y, n: Date.now() })} />}
          {step === 2 && <RoutesStep plans={plans} chosen={chosen} onChoose={(c) => setReq({ ...req, route_choice: c })} />}
          {step === 3 && <FeasibilityStep a={a} names={Object.fromEntries(sites.map((s) => [s.id, s.name]))} />}
          {step === 4 && <ContingencyStep state={cont} setState={setCont} planMinutes={a?.totals.minutes ?? null} onRun={runScenario} onPickZone={() => setPick(pick === "zone" ? "none" : "zone")}
            picking={pick === "zone"} result={replan} busy={replanBusy} error={replanErr} />}
          {step === 5 && <EvidenceStep sa={sa} sites={sites} obs={obs} ds={ds} plan={chosenPlan} selectedPhoto={photo} />}
        </div>
        <footer className="panel-foot">
          {stale && step > 1 && <span className="m">Inputs changed. <button type="button" className="link" onClick={() => evaluate(req)}>Recompute</button></span>}
          <button type="button" className="btn ghost" onClick={() => setStep((s) => (Math.max(1, s - 1) as StepId))} disabled={step === 1}><ArrowLeft size={16} strokeWidth={1.75} aria-hidden="true" />Back</button>
          {step < 5 && (
            <button type="button" className="btn primary" onClick={next} disabled={busy}>
              {step === 1 ? (stale || !chosenPlan ? "Compute routes" : "See routes") : `Next: ${STEPS[step].title}`}<ArrowRight size={16} strokeWidth={1.75} aria-hidden="true" />
            </button>
          )}
        </footer>
      </aside>
      <Guide open={guide} onClose={closeGuide} />
      <p className="sr-only" aria-live="polite">{a ? `Plan ${a.status.toLowerCase()}, total ${fmtMin(a.totals.minutes)}` : ""}</p>
    </div>
  );
}
