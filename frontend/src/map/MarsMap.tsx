import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Camera, Footprints, X } from "lucide-react";
import type { AreaInfo } from "../api/client";
import type { GeologyUnit, Photo, ScienceSite, StudyArea, XY } from "../api/types";

export type MapView = "ortho" | "elevation" | "slope" | "geology";
export type PickMode = "none" | "habitat" | "zone";
export interface MapRoute { id: string; points: [number, number][]; color: string; dashed?: boolean; label: string; weight?: number }

export interface MarsMapProps {
  sa: StudyArea;
  /** Other planning areas, drawn as clickable outlines. */
  areaOutlines: AreaInfo[];
  onSelectArea: (id: string) => void;
  view: MapView;
  setView: (v: MapView) => void;
  showTraverse: boolean;
  setShowTraverse: (v: boolean) => void;
  showPhotos: boolean;
  setShowPhotos: (v: boolean) => void;
  routes: MapRoute[];
  habitat: XY;
  stops: { id: string; name: string; point: XY }[];
  sites: ScienceSite[];
  photos: Photo[];
  zone: { center: [number, number]; radius_m: number } | null;
  crew: XY | null;
  pickMode: PickMode;
  onPick: (mode: PickMode, p: XY) => void;
  onCancelPick: () => void;
  onSelectPhoto: (id: string) => void;
  onSelectSite: (id: string) => void;
  focus: { x: number; y: number; n: number } | null;
  /** Fit the view to these points whenever fitKey changes (e.g. after routes are computed). */
  fitPoints: [number, number][];
  fitKey: string;
}

const OVERLAY_OPACITY: Record<Exclude<MapView, "ortho">, number> = { elevation: 0.7, slope: 0.62, geology: 0.5 };
const VIEWS: { id: MapView; label: string }[] = [{ id: "ortho", label: "Photo" }, { id: "elevation", label: "Elevation" }, { id: "slope", label: "Slope" }, { id: "geology", label: "Geology" }];
const DEG = 180 / Math.PI;

/** Planning-frame metres <-> planetocentric lon/lat on the Mars 2000 sphere. The source CRS is
 *  equirectangular with true scale at the equator, so this is an exact linear unit conversion. */
function frame(sa: StudyArea) {
  const R = sa.crs.sphere_radius_m;
  const lon = (x: number) => ((sa.grid.origin_easting_m + x) / R) * DEG;
  const lat = (y: number) => ((sa.grid.origin_northing_bottom_m + y) / R) * DEG;
  return {
    ll: (x: number, y: number) => L.latLng(lat(y), lon(x)),
    xy: (p: L.LatLng): XY => ({ x_m: (p.lng / DEG) * R - sa.grid.origin_easting_m, y_m: (p.lat / DEG) * R - sa.grid.origin_northing_bottom_m }),
    R,
  };
}

function ellipse(cx: number, cy: number, rGround: number, k: number): [number, number][] {
  const rx = rGround / k; // ground radius -> projected: E-W stretched by 1/cos(lat)
  return Array.from({ length: 64 }, (_, i) => {
    const t = (i / 64) * Math.PI * 2;
    return [cx + rx * Math.cos(t), cy + rGround * Math.sin(t)] as [number, number];
  });
}

function niceNumber(v: number): number {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const d = v / p;
  return (d >= 5 ? 5 : d >= 2 ? 2 : 1) * p;
}

function Legend({ view, units, routes, hasOutside }: { view: MapView; units: GeologyUnit[]; routes: MapRoute[]; hasOutside: boolean }) {
  return (
    <div className="map-card legend" aria-label="Map legend">
      {routes.map((r) => (
        <div key={r.id} className="lg-row"><i className={`lg-line ${r.dashed ? "dashed" : ""}`} style={{ borderColor: r.color }} />{r.label}</div>
      ))}
      <div className="lg-row"><i className="lg-hab" />Habitat (simulated)</div>
      <div className="lg-row"><i className="lg-site" />Science site in planning area</div>
      {hasOutside && <div className="lg-row"><i className="lg-site out" />Sample site elsewhere (context)</div>}
      <div className="lg-row"><i className="lg-area" />Planning area (routing)</div>
      {view === "slope" && (
        <div className="lg-ramp"><span>Slope, planning area</span><i className="ramp slope-ramp" /><span className="ramp-l num"><span>0°</span><span>15°</span><span>30°+</span></span></div>
      )}
      {view === "elevation" && (
        <div className="lg-ramp"><span>Elevation, planning area</span><i className="ramp elev-ramp" /><span className="ramp-l num"><span>−2611 m</span><span>−2356 m</span></span></div>
      )}
      {view === "geology" && (
        <div className="lg-units">
          {units.map((u) => <div key={u.symbol} className="lg-row"><i className="lg-sq" style={{ background: u.color }} /><span className="mono">{u.symbol}</span>{u.name.replace(" unit", "")}</div>)}
          <p>Planning area only; edges ±100-200 m</p>
        </div>
      )}
    </div>
  );
}

export function MarsMap(props: MarsMapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const overlays = useRef<Partial<Record<string, L.ImageOverlay>>>({});
  const dyn = useRef<L.LayerGroup | null>(null);
  const traverse = useRef<L.LayerGroup | null>(null);
  const firstFit = useRef(true);
  const introTimer = useRef<number | undefined>(undefined);
  const propsRef = useRef(props);
  propsRef.current = props;
  const [cursor, setCursor] = useState("");
  const [scale, setScale] = useState<{ px: number; label: string }>({ px: 80, label: "" });
  const [zoom, setZoom] = useState(1);

  const { sa } = props;
  const f = frame(sa);
  const [W, H] = sa.extent_xy_m;
  const k = sa.scale.east_west_ground_m_per_projected_m;
  const planBounds = L.latLngBounds(f.ll(0, 0), f.ll(W, H));
  const ctx = sa.context;
  const ctxBounds = ctx ? L.latLngBounds([ctx.lat_range_deg[0], ctx.lon_range_deg[0]], [ctx.lat_range_deg[1], ctx.lon_range_deg[1]]) : planBounds.pad(1.5);
  const inPlan = (p: XY) => p.x_m >= 0 && p.y_m >= 0 && p.x_m < W && p.y_m < H;

  const goTo = (target: "mars" | "jezero" | "plan") => {
    const m = map.current;
    if (!m) return;
    window.clearTimeout(introTimer.current);
    m.stop();
    if (target === "mars") m.flyToBounds(L.latLngBounds([-75, -180], [75, 180]), { duration: 1.2 });
    if (target === "jezero") m.flyToBounds(ctxBounds, { padding: [24, 24], duration: 1.2 });
    if (target === "plan") m.flyToBounds(planBounds, { padding: [24, 24], duration: 1.2 });
  };

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { crs: L.CRS.EPSG4326, minZoom: 0, maxZoom: 15, zoomSnap: 0.25, zoomControl: false, attributionControl: true, keyboard: true, worldCopyJump: false });
    L.control.zoom({ position: "bottomright" }).addTo(m);
    m.attributionControl.setPrefix(false);
    if (sa.global_basemap) {
      L.tileLayer(sa.global_basemap.url_template, {
        maxNativeZoom: sa.global_basemap.max_native_zoom, maxZoom: 15, minZoom: 0, noWrap: true, bounds: L.latLngBounds([-90, -180], [90, 180]),
        attribution: sa.global_basemap.attribution, className: "tiles-global",
      }).addTo(m);
    }
    if (ctx) L.imageOverlay(ctx.image_url, ctxBounds, { alt: "Jezero CTX orthomosaic (context)", className: "ov-context" }).addTo(m);
    m.attributionControl.addAttribution("CTX: USGS Astrogeology · NASA/JPL-Caltech/MSSS · Geology: USGS SIM 3464");
    for (const layer of sa.layers) overlays.current[layer.layer_id] = L.imageOverlay(layer.image_url, planBounds, { alt: layer.title, className: `ov-${layer.layer_id}` });
    overlays.current.ortho?.addTo(m);
    L.rectangle(planBounds, { color: "#ededed", weight: 1, dashArray: "4 4", fill: false, interactive: false }).addTo(m);
    for (const o of props.areaOutlines) {
      if (!o.lon_range_deg || !o.lat_range_deg) continue;
      const ob = L.latLngBounds([o.lat_range_deg[0], o.lon_range_deg[0]], [o.lat_range_deg[1], o.lon_range_deg[1]]);
      L.rectangle(ob, { color: "#a1a1a6", weight: 1, dashArray: "2 6", fill: true, fillOpacity: 0.04 })
        .bindTooltip(`${o.short_name} planning area · click to plan here`, { sticky: true })
        .on("click", () => { if (propsRef.current.pickMode === "none") propsRef.current.onSelectArea(o.study_area_id); }).addTo(m);
      // label at the other area's corner farthest from this area, so it never covers the active route
      const c = planBounds.getCenter();
      const corners = [ob.getNorthWest(), ob.getNorthEast(), ob.getSouthWest(), ob.getSouthEast()];
      const far = corners.reduce((a, b) => (Math.hypot(b.lat - c.lat, b.lng - c.lng) > Math.hypot(a.lat - c.lat, a.lng - c.lng) ? b : a));
      const east = far.lng > ob.getCenter().lng, north = far.lat > ob.getCenter().lat;
      L.marker(far, { icon: L.divIcon({ className: "area-label", html: `<span>${o.short_name}</span>`, iconSize: [140, 20], iconAnchor: [east ? 144 : -4, north ? -4 : 22] }), interactive: false, keyboard: false }).addTo(m);
    }
    m.fitBounds(L.latLngBounds([-75, -180], [75, 180]), { animate: false });
    const label = L.marker(planBounds.getCenter(), { icon: L.divIcon({ className: "place-label", html: "<span>Jezero Crater</span>", iconSize: [120, 20], iconAnchor: [-14, 10] }), interactive: false, keyboard: false });
    traverse.current = L.layerGroup();
    dyn.current = L.layerGroup().addTo(m);
    const update = () => {
      const z = m.getZoom();
      setZoom(z);
      if (z < 8.5) { if (!m.hasLayer(label)) label.addTo(m); } else if (m.hasLayer(label)) m.removeLayer(label);
      const lat = m.getCenter().lat;
      const groundPerPx = (360 / (512 * Math.pow(2, z))) / DEG * f.R * Math.cos(lat / DEG);
      const ground = groundPerPx * 80;
      const nice = niceNumber(ground);
      setScale({ px: (nice / ground) * 80, label: nice >= 1000 ? `${(nice / 1000).toLocaleString()} km` : `${nice} m` });
    };
    m.on("zoomend moveend", update);
    update();
    m.on("mousemove", (e: L.LeafletMouseEvent) => setCursor(`${e.latlng.lat.toFixed(4)}°N ${e.latlng.lng.toFixed(4)}°E`));
    m.on("click", (e: L.LeafletMouseEvent) => {
      const mode = propsRef.current.pickMode;
      if (mode === "none") return;
      const p = f.xy(e.latlng);
      if (inPlan(p)) propsRef.current.onPick(mode, p);
    });
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    map.current = m;
    return () => { window.clearTimeout(introTimer.current); ro.disconnect(); m.stop(); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    for (const id of ["elevation", "slope", "geology", "hillshade"]) {
      const ov = overlays.current[id];
      if (!ov) continue;
      if (id === props.view) { ov.addTo(m); ov.setOpacity(OVERLAY_OPACITY[id as keyof typeof OVERLAY_OPACITY] ?? 0.6); }
      else if (m.hasLayer(ov)) m.removeLayer(ov);
    }
  }, [props.view]);

  useEffect(() => {
    const m = map.current, g = traverse.current;
    if (!m || !g) return;
    g.clearLayers();
    if (props.showTraverse) {
      const pts = sa.rover_traverse.points.map((p) => (p.lat_deg !== undefined && p.lon_deg !== undefined ? L.latLng(p.lat_deg, p.lon_deg) : f.ll(p.x_m, p.y_m)));
      const last = sa.rover_traverse.points[sa.rover_traverse.points.length - 1];
      L.polyline(pts, { color: "#ededed", weight: 1.5, opacity: 0.75, dashArray: "1 5", lineCap: "round" })
        .bindTooltip(`Perseverance's actual path, sols ${sa.rover_traverse.points[0]?.sol}-${last?.sol} (NASA localizations)`, { sticky: true }).addTo(g);
      g.addTo(m);
    } else m.removeLayer(g);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.showTraverse, sa]);

  useEffect(() => {
    const g = dyn.current;
    if (!g) return;
    g.clearLayers();
    for (const r of props.routes) {
      const pts = r.points.map(([x, y]) => f.ll(x, y));
      L.polyline(pts, { color: "#0b0b0c", weight: (r.weight ?? 3) + 3, opacity: 0.6 }).addTo(g);
      L.polyline(pts, { color: r.color, weight: r.weight ?? 3, dashArray: r.dashed ? "6 6" : undefined, lineJoin: "round" }).bindTooltip(r.label, { sticky: true }).addTo(g);
    }
    if (props.zone) {
      const [cx, cy] = props.zone.center;
      L.polygon(ellipse(cx, cy, props.zone.radius_m, k).map(([x, y]) => f.ll(x, y)), { color: "#e5484d", weight: 1.5, fillColor: "#e5484d", fillOpacity: 0.22 })
        .bindTooltip(`Blocked zone (simulated), ${props.zone.radius_m} m radius`).addTo(g);
    }
    props.sites.forEach((s) => {
      const order = props.stops.findIndex((st) => st.id === s.id) + 1;
      const inside = s.in_planning_area !== false;
      L.marker(f.ll(s.x_m, s.y_m), {
        icon: L.divIcon({ className: `pin-site ${order ? "on" : ""} ${inside ? "" : "out"}`, html: `<span>${order || ""}</span>`, iconSize: order ? [22, 22] : inside ? [16, 16] : [14, 14] }),
        title: s.name, keyboard: true, zIndexOffset: inside ? 500 : 300,
      }).on("click", () => propsRef.current.onSelectSite(s.id))
        .bindTooltip(`${s.name}${s.sample_sol ? ` · sampled sol ${s.sample_sol}` : ""}${!inside ? " · outside planning area (context)" : order ? ` · stop ${order}` : " · click for details"}`).addTo(g);
    });
    L.marker(f.ll(props.habitat.x_m, props.habitat.y_m), {
      icon: L.divIcon({ className: "pin-hab", html: "<span>H</span>", iconSize: [26, 26] }), title: "Habitat (simulated)", keyboard: true, zIndexOffset: 600,
    }).bindTooltip("Habitat (simulated)").addTo(g);
    if (props.showPhotos) {
      for (const p of props.photos) {
        L.marker(f.ll(p.geolocation.x_m, p.geolocation.y_m), {
          icon: L.divIcon({ className: "pin-cam", html: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>`, iconSize: [20, 20] }),
          title: `Rover photo, sol ${p.sol}`, keyboard: true,
        }).on("click", () => propsRef.current.onSelectPhoto(p.photo_id)).bindTooltip(`Rover photo · sol ${p.sol} · click to view`).addTo(g);
      }
    }
    if (props.crew) {
      L.marker(f.ll(props.crew.x_m, props.crew.y_m), { icon: L.divIcon({ className: "pin-crew", html: "<span>C</span>", iconSize: [24, 24] }), title: "Crew (simulated)", zIndexOffset: 700 })
        .bindTooltip("Crew position (simulated)").addTo(g);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.routes, props.zone, props.sites, props.stops, props.habitat, props.photos, props.showPhotos, props.crew, k]);

  // First fit: fly in from the whole planet to the planned route. Later fits jump without animation.
  useEffect(() => {
    const m = map.current;
    if (!m || props.fitPoints.length < 2) return;
    const b = L.latLngBounds(props.fitPoints.map(([x, y]) => f.ll(x, y))).pad(0.25);
    window.clearTimeout(introTimer.current);
    if (firstFit.current) {
      firstFit.current = false;
      introTimer.current = window.setTimeout(() => { if (map.current === m) { m.stop(); m.flyToBounds(b, { duration: 2.4 }); } }, 400);
    } else { m.stop(); m.fitBounds(b, { animate: false }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.fitKey]);

  useEffect(() => {
    if (props.focus && map.current) map.current.stop(), map.current.flyTo(f.ll(props.focus.x, props.focus.y), Math.max(map.current.getZoom(), 12), { duration: 0.8 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.focus]);

  useEffect(() => {
    el.current?.classList.toggle("picking", props.pickMode !== "none");
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") propsRef.current.onCancelPick(); };
    if (props.pickMode !== "none") window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.pickMode]);

  const level = zoom < 6 ? "mars" : zoom < 10.5 ? "jezero" : "plan";
  return (
    <div className="map-wrap">
      <div ref={el} className="map" role="application" aria-label="Map of Mars zooming into Jezero Crater. Results are also listed as text in the panel." tabIndex={0} />
      <div className="map-top">
        <div className="map-card seg" role="radiogroup" aria-label="Zoom to">
          {([["mars", "Mars"], ["jezero", "Jezero"], ["plan", "Planning area"]] as const).map(([id, label]) => (
            <button key={id} type="button" role="radio" aria-checked={level === id} className={level === id ? "on" : ""} onClick={() => goTo(id)}>{label}</button>
          ))}
        </div>
        <div className="map-card seg" role="radiogroup" aria-label="Detail layer (planning area)">
          {VIEWS.map((v) => <button key={v.id} type="button" role="radio" aria-checked={props.view === v.id} className={props.view === v.id ? "on" : ""} onClick={() => props.setView(v.id)}>{v.label}</button>)}
        </div>
        <div className="map-card seg toggles">
          <button type="button" aria-pressed={props.showTraverse} className={props.showTraverse ? "on" : ""} onClick={() => props.setShowTraverse(!props.showTraverse)} title="Show Perseverance's actual path">
            <Footprints size={14} strokeWidth={1.75} aria-hidden="true" />Rover path
          </button>
          <button type="button" aria-pressed={props.showPhotos} className={props.showPhotos ? "on" : ""} onClick={() => props.setShowPhotos(!props.showPhotos)} title="Show rover photo locations">
            <Camera size={14} strokeWidth={1.75} aria-hidden="true" />Photos
          </button>
        </div>
      </div>
      {props.pickMode !== "none" && (
        <div className="pick-banner" role="status">
          {props.pickMode === "habitat" ? "Click inside the dashed planning area to place the habitat" : "Click inside the dashed planning area to centre the blocked zone"}
          <button type="button" className="icon-btn" onClick={props.onCancelPick} aria-label="Cancel"><X size={14} strokeWidth={1.75} /></button>
        </div>
      )}
      <Legend view={props.view} units={sa.geology_units?.units ?? []} routes={props.routes} hasOutside={props.sites.some((s) => s.in_planning_area === false)} />
      <div className="map-foot">
        <span className="scalebar"><i style={{ width: `${scale.px}px` }} />{scale.label}</span>
        <span className="mono">N ↑</span>
        {cursor && <span className="mono coords">{cursor}</span>}
      </div>
    </div>
  );
}
