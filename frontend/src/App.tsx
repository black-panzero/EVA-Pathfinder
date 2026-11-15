import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiRequestError, STATIC_MODE } from "./api/client";
import type { DatasetsResponse, EvaluateResponse, MissionRequest, Observations, ReplanRequest, ReplanResponse, ScienceSite, StudyArea, XY } from "./api/types";
import { ContingencyLab, type ContingencyState } from "./components/ContingencyLab";
import { EvidencePanel } from "./components/EvidencePanel";
import { GuardianPanel } from "./components/GuardianPanel";
import { LayerPanel, MissionInputs } from "./components/MissionInputs";
import { RouteComparison } from "./components/RouteComparison";
import { Badge, StatusPill } from "./components/common";
import { fmt } from "./features/format";
import { MarsMap, type LayerId, type MapRoute, type PickMode } from "./map/MarsMap";

type Plans = { shortest: EvaluateResponse | null; terrain: EvaluateResponse | null };
const DEFAULT_LAYERS: Record<LayerId, { visible: boolean; opacity: number }> = {
  ortho: { visible: true, opacity: 1 }, hillshade: { visible: false, opacity: 0.5 }, elevation: { visible: false, opacity: 0.6 },
  slope: { visible: false, opacity: 0.55 }, geology: { visible: false, opacity: 0.4 },
};
const errText = (e: unknown) => (e instanceof ApiRequestError ? `${e.code}: ${e.message}` : String(e));
const legsPolyline = (p: EvaluateResponse | null) => (p ? p.assessment.legs.flatMap((l) => l.route?.polyline_xy_m ?? []) : []);

export default function App() {
  const [sa, setSa] = useState<StudyArea | null>(null);
  const [obs, setObs] = useState<Observations | null>(null);
  const [ds, setDs] = useState<DatasetsResponse | null>(null);
  const [req, setReq] = useState<MissionRequest | null>(null);
  const [consumableLabel, setConsumableLabel] = useState("Illustrative consumable (generic units)");
  const [plans, setPlans] = useState<Plans>({ shortest: null, terrain: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [showTraverse, setShowTraverse] = useState(false);
  const [showPhotos, setShowPhotos] = useState(true);
  const [pick, setPick] = useState<PickMode>("none");
  const [cont, setCont] = useState<ContingencyState>({ elapsed_min: 0, radius_m: 250, position_fraction: 0.5, response_mode: "return_now", consumable_loss_units: 0, center: null });
  const [replan, setReplan] = useState<ReplanResponse | null>(null);
  const [replanReq, setReplanReq] = useState<ReplanRequest | null>(null);
  const [replanBusy, setReplanBusy] = useState(false);
  const [replanErr, setReplanErr] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);

  const evaluate = useCallback(async (r: MissionRequest) => {
    setBusy(true); setError(null); setReplan(null); setReplanReq(null);
    try {
      const [shortest, terrain] = await Promise.all([api.evaluate({ ...r, route_choice: "shortest" }), api.evaluate({ ...r, route_choice: "terrain" })]);
      setPlans({ shortest, terrain });
      const chosen = r.route_choice === "shortest" ? shortest : terrain;
      // default progress: 30% into the return leg (from backend leg/activity times)
      const a = chosen.assessment;
      const legs = a.legs;
      if (legs.every((l) => l.minutes !== null)) {
        const beforeReturn = legs.slice(0, -1).reduce((s, l) => s + (l.minutes ?? 0), 0) + a.activities.reduce((s, x) => s + x.minutes, 0);
        setCont((c) => ({ ...c, elapsed_min: Math.round(beforeReturn + 0.3 * (legs[legs.length - 1].minutes ?? 0)) }));
      }
    } catch (e) {
      setError(errText(e));
      setPlans({ shortest: null, terrain: null });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [s, o, d, def, sci] = await Promise.all([api.studyArea(), api.observations(), api.datasets(), api.defaultMission(), api.scienceSites()]);
        setSa(s); setObs(o); setDs(d); setSciSites(sci.sites); setReq(def.request); setConsumableLabel(def.labels.consumable_label);
        evaluate(def.request);
      } catch (e) {
        setError(errText(e));
      }
    })();
  }, [evaluate]);

  const [sciSites, setSciSites] = useState<ScienceSite[]>([]);

  const chosenPlan = req?.route_choice === "shortest" ? plans.shortest : plans.terrain;
  const otherPlan = req?.route_choice === "shortest" ? plans.terrain : plans.shortest;

  const onPick = (mode: PickMode, p: XY) => {
    if (!req) return;
    if (mode === "habitat") setReq({ ...req, habitat: p });
    if (mode === "zone") setCont((c) => ({ ...c, center: p }));
    setPick("none");
  };

  const inject = async () => {
    if (!req) return;
    const body: ReplanRequest = {
      mission: req, elapsed_min: cont.elapsed_min, response_mode: cont.response_mode, consumable_loss_units: cont.consumable_loss_units,
      event: { type: "BLOCKED_ZONE", radius_m: cont.radius_m, center: cont.center, position_fraction: cont.position_fraction },
    };
    setReplanBusy(true); setReplanErr(null);
    try {
      setReplan(await api.replan(body));
      setReplanReq(body);
    } catch (e) {
      setReplanErr(errText(e)); setReplan(null);
    } finally {
      setReplanBusy(false);
    }
  };

  const downloadReport = async () => {
    if (!req) return;
    try {
      const rep = await api.report(req, replanReq);
      const url = URL.createObjectURL(new Blob([JSON.stringify(rep, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = "eva-pathfinder-report.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errText(e));
    }
  };

  const mapRoutes: MapRoute[] = useMemo(() => {
    const out: MapRoute[] = [];
    if (replan) {
      out.push({ id: "before", points: replan.before.legs.flatMap((l) => l.route?.polyline_xy_m ?? []), color: "#9aa0a6", dashed: true, label: "Remaining route before event", weight: 3 });
      out.push({ id: "after", points: replan.after.legs.flatMap((l) => l.route?.polyline_xy_m ?? []), color: "#5dd39e", label: "Replanned route after simulated event", weight: 4 });
      out.push({ id: "chosen", points: legsPolyline(chosenPlan), color: "#ff8c42", label: "Original plan", weight: 2 });
    } else {
      if (otherPlan) out.push({ id: "other", points: legsPolyline(otherPlan), color: req?.route_choice === "shortest" ? "#ff8c42" : "#5ec8e5", dashed: true, label: req?.route_choice === "shortest" ? "Terrain-aware" : "Shortest feasible", weight: 3 });
      if (chosenPlan) out.push({ id: "chosen", points: legsPolyline(chosenPlan), color: req?.route_choice === "shortest" ? "#5ec8e5" : "#ff8c42", label: req?.route_choice === "shortest" ? "Shortest feasible (selected)" : "Terrain-aware (selected)" });
    }
    return out;
  }, [replan, chosenPlan, otherPlan, req?.route_choice]);

  if (!sa || !req) {
    return <main className="loading"><h1>EVA Pathfinder</h1><p role="status">{error ?? "Loading Jezero study area…"}</p></main>;
  }

  const verified = ds ? ds.datasets.filter((d) => d.verification_status === "AVAILABLE_VERIFIED").length : 0;
  const titles = Object.fromEntries(sa.layers.map((l) => [l.layer_id, { title: l.title, level: l.evidence_level }]));

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><strong>EVA Pathfinder</strong><span>/ Guardian</span></div>
        <div className="crumbs">
          <span>{sa.name}</span>
          <span className="muted">{sa.grid.lat_range_deg[0].toFixed(3)}–{sa.grid.lat_range_deg[1].toFixed(3)}°N, {sa.grid.lon_range_deg[0].toFixed(3)}–{sa.grid.lon_range_deg[1].toFixed(3)}°E</span>
          <span className="muted">DEM: USGS CTX 20 m · {fmt(sa.dem_stats.valid_fraction * 100, 1)}% valid</span>
          {ds && <span className="muted">{verified} sources verified by checksum</span>}
          {STATIC_MODE && <span className="muted">Static demo: the Python planning engine runs in your browser (Pyodide)</span>}
        </div>
        <div className="top-status">
          <Badge level="SIMULATED" /><span className="small">Operation Delta Return: simulated mission</span>
          {chosenPlan && <StatusPill status={chosenPlan.assessment.status} />}
        </div>
      </header>
      <p className="disclaimer" role="note">Research prototype. Not certified for astronaut EVA navigation or life-support decisions. A 20 m DEM cannot show rocks or human-scale hazards. Habitat, crew and events are simulated.</p>
      {error && <p className="bad banner" role="alert">{error}</p>}
      <div className="layout">
        <aside className="left">
          <LayerPanel layers={layers} setLayers={(l) => setLayers(l as typeof layers)} showTraverse={showTraverse} setShowTraverse={setShowTraverse} showPhotos={showPhotos} setShowPhotos={setShowPhotos}
            geologyUnits={sa.geology_units?.units ?? []} titles={titles} />
          <MissionInputs req={req} setReq={setReq} sites={sciSites} onEvaluate={() => evaluate(req)} busy={busy} pickingHabitat={pick === "habitat"}
            onPickHabitat={() => setPick(pick === "habitat" ? "none" : "habitat")} consumableLabel={consumableLabel} />
        </aside>
        <main className="center">
          <MarsMap sa={sa} layers={layers} showTraverse={showTraverse} showPhotos={showPhotos} routes={mapRoutes} habitat={req.habitat}
            stops={req.stops.map((s) => ({ id: s.stop_id, name: s.name, point: s.point }))} sites={sciSites} photos={obs?.photos ?? []}
            zone={replan ? { center: replan.event.center_xy_m, radius_m: replan.event.radius_m } : cont.center ? { center: [cont.center.x_m, cont.center.y_m], radius_m: cont.radius_m } : null}
            crew={replan ? { x_m: replan.current_position.x_m, y_m: replan.current_position.y_m } : null}
            pickMode={pick} onPick={onPick} onSelectPhoto={setPhoto} />
          <div className="map-legend small">
            <span className="legend-item"><i className="sw sw-terrain" />Terrain-aware</span>
            <span className="legend-item"><i className="sw sw-short dashed" />Shortest feasible</span>
            {replan && <span className="legend-item"><i className="sw sw-after" />Replanned</span>}
            {replan && <span className="legend-item"><i className="sw sw-before dashed" />Remaining (before event)</span>}
            <span className="legend-item"><i className="dot dot-site" />Science site (rover localization)</span>
            <span className="legend-item"><i className="dot dot-hab" />Habitat (simulated)</span>
            <span className="legend-item"><i className="dot dot-zone" />Blocked zone (simulated)</span>
          </div>
          <div className="below">
            <RouteComparison plans={plans} chosen={req.route_choice} />
            <ContingencyLab state={cont} setState={setCont} planMinutes={chosenPlan?.assessment.totals.minutes ?? null} onInject={inject}
              onPickZone={() => setPick(pick === "zone" ? "none" : "zone")} picking={pick === "zone"} result={replan} busy={replanBusy} error={replanErr} />
          </div>
        </main>
        <aside className="right">
          <GuardianPanel a={chosenPlan?.assessment ?? null} busy={busy} />
          <EvidencePanel sa={sa} sites={sciSites} obs={obs} ds={ds} plan={chosenPlan} selectedPhoto={photo} onSelectPhoto={setPhoto} onDownloadReport={downloadReport} />
        </aside>
      </div>
    </div>
  );
}

