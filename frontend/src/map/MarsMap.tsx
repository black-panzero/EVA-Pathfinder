import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Photo, ScienceSite, StudyArea, XY } from "../api/types";
import { xyToLonLat } from "../features/format";

export type LayerId = "ortho" | "hillshade" | "elevation" | "slope" | "geology";
export type PickMode = "none" | "habitat" | "zone";

export interface MapRoute { id: string; points: [number, number][]; color: string; dashed?: boolean; label: string; weight?: number }

export interface MarsMapProps {
  sa: StudyArea;
  layers: Record<LayerId, { visible: boolean; opacity: number }>;
  showTraverse: boolean;
  showPhotos: boolean;
  routes: MapRoute[];
  habitat: XY;
  stops: { id: string; name: string; point: XY }[];
  sites: ScienceSite[];
  photos: Photo[];
  zone: { center: [number, number]; radius_m: number } | null;
  crew: XY | null;
  pickMode: PickMode;
  onPick: (mode: PickMode, p: XY) => void;
  onSelectPhoto: (id: string) => void;
}

const ll = (x: number, y: number) => L.latLng(y, x);

function ellipse(cx: number, cy: number, rGround: number, k: number): L.LatLng[] {
  // ground radius -> projected radii: E-W projected = ground / cos(lat), N-S unchanged
  const rx = rGround / k;
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

export function MarsMap(props: MarsMapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const overlays = useRef<Partial<Record<LayerId, L.ImageOverlay>>>({});
  const dyn = useRef<L.LayerGroup | null>(null);
  const traverse = useRef<L.LayerGroup | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  const [cursor, setCursor] = useState<string>("Move the pointer over the map for coordinates");
  const [scale, setScale] = useState<{ px: number; label: string }>({ px: 100, label: "" });

  const { sa } = props;
  const [W, H] = sa.extent_xy_m;
  const k = sa.scale.east_west_ground_m_per_projected_m;

  // init once
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 3, zoomSnap: 0.25, attributionControl: true, keyboard: true });
    const bounds = L.latLngBounds(ll(0, 0), ll(W, H));
    m.fitBounds(bounds);
    m.setMaxBounds(bounds.pad(0.25));
    m.attributionControl.setPrefix(false);
    m.attributionControl.addAttribution("CTX DTM/orthomosaic: USGS Astrogeology, NASA/JPL-Caltech/MSSS; geology: USGS SIM 3464; rover data: NASA/JPL-Caltech");
    for (const layer of sa.layers) {
      overlays.current[layer.layer_id as LayerId] = L.imageOverlay(layer.image_url, bounds, { alt: layer.title, className: `ov-${layer.layer_id}` });
    }
    traverse.current = L.layerGroup();
    dyn.current = L.layerGroup().addTo(m);
    const updateScale = () => {
      const unitsPer100px = 100 / Math.pow(2, m.getZoom());
      const ground = unitsPer100px * k;
      const nice = niceNumber(ground);
      setScale({ px: (nice / ground) * 100, label: nice >= 1000 ? `${nice / 1000} km` : `${nice} m` });
    };
    m.on("zoomend", updateScale);
    updateScale();
    m.on("mousemove", (e: L.LeafletMouseEvent) => {
      const x = e.latlng.lng, y = e.latlng.lat;
      if (x < 0 || y < 0 || x > W || y > H) return setCursor("Outside study area");
      const [lon, lat] = xyToLonLat(sa, x, y);
      setCursor(`x ${x.toFixed(0)} m, y ${y.toFixed(0)} m | ${lat.toFixed(5)}°N ${lon.toFixed(5)}°E`);
    });
    m.on("click", (e: L.LeafletMouseEvent) => {
      const mode = propsRef.current.pickMode;
      const x = e.latlng.lng, y = e.latlng.lat;
      if (mode !== "none" && x >= 0 && y >= 0 && x < W && y < H) propsRef.current.onPick(mode, { x_m: x, y_m: y });
    });
    map.current = m;
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // base layers
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    (Object.keys(overlays.current) as LayerId[]).forEach((id, i) => {
      const ov = overlays.current[id]!;
      const cfg = props.layers[id];
      if (cfg?.visible) {
        if (!m.hasLayer(ov)) ov.addTo(m);
        ov.setOpacity(cfg.opacity);
        ov.setZIndex(i + 1);
      } else if (m.hasLayer(ov)) m.removeLayer(ov);
    });
  }, [props.layers]);

  // rover traverse
  useEffect(() => {
    const m = map.current, g = traverse.current;
    if (!m || !g) return;
    g.clearLayers();
    if (props.showTraverse) {
      L.polyline(sa.rover_traverse.points.map((p) => ll(p.x_m, p.y_m)), { color: "#f5f0e6", weight: 1.5, opacity: 0.8, dashArray: "2 4" })
        .bindTooltip("Perseverance traverse (NASA rover localizations)").addTo(g);
      g.addTo(m);
    } else m.removeLayer(g);
  }, [props.showTraverse, sa]);

  // dynamic overlays
  useEffect(() => {
    const g = dyn.current;
    if (!g) return;
    g.clearLayers();
    for (const r of props.routes) {
      L.polyline(r.points.map(([x, y]) => ll(x, y)), { color: "#111", weight: (r.weight ?? 4) + 3, opacity: 0.55 }).addTo(g);
      L.polyline(r.points.map(([x, y]) => ll(x, y)), { color: r.color, weight: r.weight ?? 4, dashArray: r.dashed ? "8 6" : undefined }).bindTooltip(r.label, { sticky: true }).addTo(g);
    }
    if (props.zone) {
      const [cx, cy] = props.zone.center;
      L.polygon(ellipse(cx, cy, props.zone.radius_m, k), { color: "#ff4d4d", weight: 2, fillColor: "#ff4d4d", fillOpacity: 0.25, dashArray: "4 3" })
        .bindTooltip(`SIMULATED blocked zone, radius ${props.zone.radius_m} m (ground)`).addTo(g);
    }
    for (const s of props.sites) {
      const used = props.stops.some((st) => st.id === s.id);
      L.circleMarker(ll(s.x_m, s.y_m), { radius: used ? 9 : 6, color: "#ffd166", weight: 2, fillColor: used ? "#ffd166" : "#3a3020", fillOpacity: 0.9 })
        .bindTooltip(`${s.name}: rover localization sol ${s.sol} (site ${s.site}/drive ${s.drive})`).addTo(g);
    }
    for (const st of props.stops.filter((st) => !props.sites.some((s) => s.id === st.id))) {
      L.circleMarker(ll(st.point.x_m, st.point.y_m), { radius: 8, color: "#ffd166", weight: 2, fillColor: "#ffd166", fillOpacity: 0.6 }).bindTooltip(st.name).addTo(g);
    }
    L.marker(ll(props.habitat.x_m, props.habitat.y_m), {
      icon: L.divIcon({ className: "hab-icon", html: "<span>H</span>", iconSize: [26, 26] }),
      title: "Hypothetical habitat (simulated)", keyboard: true,
    }).bindTooltip("Hypothetical habitat (SIMULATED)").addTo(g);
    if (props.showPhotos) {
      for (const p of props.photos) {
        L.marker(ll(p.geolocation.x_m, p.geolocation.y_m), {
          icon: L.divIcon({ className: "cam-icon", html: "<span>▣</span>", iconSize: [20, 20] }), title: `Rover photo sol ${p.sol}`, keyboard: true,
        }).on("click", () => propsRef.current.onSelectPhoto(p.photo_id)).bindTooltip(`Navcam sol ${p.sol} at rover site ${p.geolocation.site}/drive ${p.geolocation.drive}`).addTo(g);
      }
    }
    if (props.crew) {
      L.marker(ll(props.crew.x_m, props.crew.y_m), { icon: L.divIcon({ className: "crew-icon", html: "<span>C</span>", iconSize: [24, 24] }), title: "Simulated crew position" })
        .bindTooltip("Simulated crew position").addTo(g);
    }
  }, [props.routes, props.zone, props.sites, props.stops, props.habitat, props.photos, props.showPhotos, props.crew, k]);

  useEffect(() => {
    el.current?.classList.toggle("picking", props.pickMode !== "none");
  }, [props.pickMode]);

  return (
    <div className="map-wrap">
      <div ref={el} className="map" role="application" aria-label="Map of the Jezero Crater study area. All plan results are also listed as text in the side panels." tabIndex={0} />
      <div className="map-hud" aria-hidden="true">
        <div className="north">N ↑</div>
        <div className="scalebar"><div style={{ width: `${scale.px}px` }} /> <span>{scale.label} ground</span></div>
      </div>
      <div className="map-readout" aria-live="off">{cursor}</div>
    </div>
  );
}
