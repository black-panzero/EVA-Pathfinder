import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Camera, Footprints, Maximize2, X } from "lucide-react";
import type { GeologyUnit, Photo, ScienceSite, StudyArea, XY } from "../api/types";
import { xyToLonLat } from "../features/format";

export type MapView = "ortho" | "elevation" | "slope" | "geology";
export type PickMode = "none" | "habitat" | "zone";
export interface MapRoute { id: string; points: [number, number][]; color: string; dashed?: boolean; label: string; weight?: number }

export interface MarsMapProps {
  sa: StudyArea;
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
  focus: { x: number; y: number; n: number } | null;
  /** Fit the view to these points whenever fitKey changes (e.g. after routes are computed). */
  fitPoints: [number, number][];
  fitKey: string;
}

const OVERLAY_OPACITY: Record<Exclude<MapView, "ortho">, number> = { elevation: 0.7, slope: 0.62, geology: 0.5 };
const VIEWS: { id: MapView; label: string }[] = [{ id: "ortho", label: "Photo" }, { id: "elevation", label: "Elevation" }, { id: "slope", label: "Slope" }, { id: "geology", label: "Geology" }];
const ll = (x: number, y: number) => L.latLng(y, x);

function ellipse(cx: number, cy: number, rGround: number, k: number): L.LatLng[] {
  const rx = rGround / k; // ground radius -> projected: E-W stretched by 1/cos(lat)
  return Array.from({ length: 64 }, (_, i) => {
    const t = (i / 64) * Math.PI * 2;
    return ll(cx + rx * Math.cos(t), cy + rGround * Math.sin(t));
  });
}

function niceNumber(v: number): number {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const d = v / p;
  return (d >= 5 ? 5 : d >= 2 ? 2 : 1) * p;
}

function Legend({ view, units, routes }: { view: MapView; units: GeologyUnit[]; routes: MapRoute[] }) {
  return (
    <div className="map-card legend" aria-label="Map legend">
      {routes.map((r) => (
        <div key={r.id} className="lg-row"><i className={`lg-line ${r.dashed ? "dashed" : ""}`} style={{ borderColor: r.color }} />{r.label}</div>
      ))}
      <div className="lg-row"><i className="lg-hab" />Habitat (simulated)</div>
      <div className="lg-row"><i className="lg-site" />Science site</div>
      {view === "slope" && (
        <div className="lg-ramp">
          <span>Slope</span><i className="ramp slope-ramp" /><span className="ramp-l num"><span>0°</span><span>15°</span><span>30°+</span></span>
        </div>
      )}
      {view === "elevation" && (
        <div className="lg-ramp">
          <span>Elevation</span><i className="ramp elev-ramp" /><span className="ramp-l num"><span>−2611 m</span><span>−2356 m</span></span>
        </div>
      )}
      {view === "geology" && (
        <div className="lg-units">
          {units.map((u) => <div key={u.symbol} className="lg-row"><i className="lg-sq" style={{ background: u.color }} /><span className="mono">{u.symbol}</span>{u.name.replace(" unit", "")}</div>)}
          <p>Regional context, edges ±100-200 m</p>
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
  const propsRef = useRef(props);
  propsRef.current = props;
  const [cursor, setCursor] = useState("");
  const [scale, setScale] = useState<{ px: number; label: string }>({ px: 80, label: "" });

  const { sa } = props;
  const [W, H] = sa.extent_xy_m;
  const k = sa.scale.east_west_ground_m_per_projected_m;
  const bounds = L.latLngBounds(ll(0, 0), ll(W, H));

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 3, zoomSnap: 0.25, zoomControl: false, attributionControl: true, keyboard: true });
    L.control.zoom({ position: "bottomright" }).addTo(m);
    m.fitBounds(bounds, { padding: [8, 8] });
    m.setMaxBounds(bounds.pad(0.3));
    m.attributionControl.setPrefix(false);
    m.attributionControl.addAttribution("USGS Astrogeology · NASA/JPL-Caltech/MSSS · USGS SIM 3464");
    for (const layer of sa.layers) overlays.current[layer.layer_id] = L.imageOverlay(layer.image_url, bounds, { alt: layer.title, className: `ov-${layer.layer_id}` });
    overlays.current.ortho?.addTo(m);
    traverse.current = L.layerGroup();
    dyn.current = L.layerGroup().addTo(m);
    const updateScale = () => {
      const ground = (80 / Math.pow(2, m.getZoom())) * k;
      const nice = niceNumber(ground);
      setScale({ px: (nice / ground) * 80, label: nice >= 1000 ? `${nice / 1000} km` : `${nice} m` });
    };
    m.on("zoomend", updateScale);
    updateScale();
    m.on("mousemove", (e: L.LeafletMouseEvent) => {
      const x = e.latlng.lng, y = e.latlng.lat;
      if (x < 0 || y < 0 || x > W || y > H) return setCursor("");
      const [lon, lat] = xyToLonLat(sa, x, y);
      setCursor(`${lat.toFixed(4)}°N ${lon.toFixed(4)}°E`);
    });
    m.on("click", (e: L.LeafletMouseEvent) => {
      const mode = propsRef.current.pickMode;
      const x = e.latlng.lng, y = e.latlng.lat;
      if (mode !== "none" && x >= 0 && y >= 0 && x < W && y < H) propsRef.current.onPick(mode, { x_m: x, y_m: y });
    });
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    map.current = m;
    return () => { ro.disconnect(); m.remove(); map.current = null; };
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
      L.polyline(sa.rover_traverse.points.map((p) => ll(p.x_m, p.y_m)), { color: "#ededed", weight: 1.5, opacity: 0.7, dashArray: "1 5", lineCap: "round" })
        .bindTooltip("Perseverance's actual path").addTo(g);
      g.addTo(m);
    } else m.removeLayer(g);
  }, [props.showTraverse, sa]);

  useEffect(() => {
    const g = dyn.current;
    if (!g) return;
    g.clearLayers();
    for (const r of props.routes) {
      const pts = r.points.map(([x, y]) => ll(x, y));
      L.polyline(pts, { color: "#0b0b0c", weight: (r.weight ?? 3) + 3, opacity: 0.6 }).addTo(g);
      L.polyline(pts, { color: r.color, weight: r.weight ?? 3, dashArray: r.dashed ? "6 6" : undefined, lineJoin: "round" }).bindTooltip(r.label, { sticky: true }).addTo(g);
    }
    if (props.zone) {
      const [cx, cy] = props.zone.center;
      L.polygon(ellipse(cx, cy, props.zone.radius_m, k), { color: "#e5484d", weight: 1.5, fillColor: "#e5484d", fillOpacity: 0.22 })
        .bindTooltip(`Blocked zone (simulated), ${props.zone.radius_m} m radius`).addTo(g);
    }
    props.sites.forEach((s) => {
      const order = props.stops.findIndex((st) => st.id === s.id) + 1;
      L.marker(ll(s.x_m, s.y_m), {
        icon: L.divIcon({ className: `pin-site ${order ? "on" : ""}`, html: `<span>${order || ""}</span>`, iconSize: [22, 22] }),
        title: s.name, keyboard: true, zIndexOffset: 500,
      }).bindTooltip(`${s.name}${order ? ` · stop ${order}` : " · not selected"}`).addTo(g);
    });
    L.marker(ll(props.habitat.x_m, props.habitat.y_m), {
      icon: L.divIcon({ className: "pin-hab", html: "<span>H</span>", iconSize: [26, 26] }), title: "Habitat (simulated)", keyboard: true, zIndexOffset: 600,
    }).bindTooltip("Habitat (simulated)").addTo(g);
    if (props.showPhotos) {
      for (const p of props.photos) {
        L.marker(ll(p.geolocation.x_m, p.geolocation.y_m), {
          icon: L.divIcon({ className: "pin-cam", html: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>`, iconSize: [20, 20] }),
          title: `Rover photo, sol ${p.sol}`, keyboard: true,
        }).on("click", () => propsRef.current.onSelectPhoto(p.photo_id)).bindTooltip(`Rover photo · sol ${p.sol} · click to view`).addTo(g);
      }
    }
    if (props.crew) {
      L.marker(ll(props.crew.x_m, props.crew.y_m), { icon: L.divIcon({ className: "pin-crew", html: "<span>C</span>", iconSize: [24, 24] }), title: "Crew (simulated)", zIndexOffset: 700 })
        .bindTooltip("Crew position (simulated)").addTo(g);
    }
  }, [props.routes, props.zone, props.sites, props.stops, props.habitat, props.photos, props.showPhotos, props.crew, k]);

  useEffect(() => {
    const m = map.current;
    if (!m || props.fitPoints.length < 2) return;
    m.fitBounds(L.latLngBounds(props.fitPoints.map(([x, y]) => ll(x, y))).pad(0.25), { animate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.fitKey]);

  useEffect(() => {
    if (props.focus && map.current) map.current.flyTo(ll(props.focus.x, props.focus.y), 0, { duration: 0.5 });
  }, [props.focus]);

  useEffect(() => {
    el.current?.classList.toggle("picking", props.pickMode !== "none");
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") propsRef.current.onCancelPick(); };
    if (props.pickMode !== "none") window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.pickMode]);

  return (
    <div className="map-wrap">
      <div ref={el} className="map" role="application" aria-label="Map of the Jezero Crater study area. Results are also listed as text in the panel." tabIndex={0} />
      <div className="map-top">
        <div className="map-card seg" role="radiogroup" aria-label="Map view">
          {VIEWS.map((v) => <button key={v.id} type="button" role="radio" aria-checked={props.view === v.id} className={props.view === v.id ? "on" : ""} onClick={() => props.setView(v.id)}>{v.label}</button>)}
        </div>
        <div className="map-card seg toggles">
          <button type="button" aria-pressed={props.showTraverse} className={props.showTraverse ? "on" : ""} onClick={() => props.setShowTraverse(!props.showTraverse)} title="Show Perseverance's actual path">
            <Footprints size={14} strokeWidth={1.75} aria-hidden="true" />Rover path
          </button>
          <button type="button" aria-pressed={props.showPhotos} className={props.showPhotos ? "on" : ""} onClick={() => props.setShowPhotos(!props.showPhotos)} title="Show rover photo locations">
            <Camera size={14} strokeWidth={1.75} aria-hidden="true" />Photos
          </button>
          <button type="button" onClick={() => map.current?.flyToBounds(bounds, { padding: [8, 8], duration: 0.4 })} title="Fit the whole study area" aria-label="Fit the whole study area">
            <Maximize2 size={14} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
      </div>
      {props.pickMode !== "none" && (
        <div className="pick-banner" role="status">
          {props.pickMode === "habitat" ? "Click the map to place the habitat" : "Click the map to centre the blocked zone"}
          <button type="button" className="icon-btn" onClick={props.onCancelPick} aria-label="Cancel"><X size={14} strokeWidth={1.75} /></button>
        </div>
      )}
      <Legend view={props.view} units={sa.geology_units?.units ?? []} routes={props.routes} />
      <div className="map-foot">
        <span className="scalebar"><i style={{ width: `${scale.px}px` }} />{scale.label}</span>
        <span className="mono">N ↑</span>
        {cursor && <span className="mono coords">{cursor}</span>}
      </div>
    </div>
  );
}
