// DTOs mirroring backend responses. The frontend never computes mission metrics itself.
export type EvidenceLevel = "NASA_OBSERVATION" | "DERIVED" | "ILLUSTRATIVE_MODEL" | "SIMULATED_EVENT" | "SIMULATED" | "UNKNOWN";
export type Status = "FEASIBLE" | "INFEASIBLE" | "UNKNOWN";
export type XY = { x_m: number; y_m: number };

export interface ProfileIn { flat_speed_m_per_min: number; ascent_rate_m_per_min: number; max_slope_deg: number }
export interface BudgetIn {
  time_available_min: number; consumable_initial_units: number;
  consumable_rate_traverse_per_min: number; consumable_rate_activity_per_min: number; reserve_fraction: number;
}
export interface StopIn { stop_id: string; name: string; point: XY; activity_min: number }
export interface MissionRequest {
  habitat: XY; stops: StopIn[]; route_choice: "shortest" | "terrain"; profile: ProfileIn; budget: BudgetIn;
  slope_weight: number; unknown_policy: "block" | "penalize"; unknown_weight: number;
}
export interface ReplanRequest {
  mission: MissionRequest; elapsed_min: number;
  event: { type: "BLOCKED_ZONE"; radius_m: number; center?: XY | null; position_fraction: number };
  response_mode: "return_now" | "continue"; consumable_loss_units: number;
}

export interface RouteMetrics {
  length_m: number; elevation_gain_m: number; elevation_loss_m: number; max_derived_slope_deg: number;
  mean_derived_slope_deg: number; max_step_grade_deg: number; unknown_length_fraction: number;
  cell_count: number; policy_cost: number; estimated_minutes?: number;
}
export interface ProfilePoint { distance_m: number; elevation_m: number | null; slope_deg: number | null; x_m: number; y_m: number }
export interface RouteDTO {
  route_id: string; policy: { policy_id: string; max_slope_deg: number; slope_weight: number; unknown_policy: string };
  polyline_xy_m: [number, number][]; metrics: RouteMetrics; profile: ProfilePoint[];
  geology_along_route: { symbol: string; name: string; length_fraction: number }[];
  compute?: { runtime_ms: number; expanded_cells: number }; evidence_level: EvidenceLevel;
}
export interface LegDTO { leg_id: string; from: string; to: string; minutes: number | null; consumable_units: number | null; reason_codes: string[]; route: RouteDTO | null }
export interface AssessmentDTO {
  status: Status; reason_codes: string[];
  totals: {
    minutes: number | null; consumable_units: number | null; usable_time_min: number; usable_consumable_units: number;
    time_margin_min: number | null; consumable_margin_units: number | null; time_available_min: number;
    consumable_initial_units: number; reserve_fraction: number; consumable_label: string;
  };
  legs: LegDTO[]; activities: { stop_id: string; minutes: number; consumable_units: number }[];
  remaining_length_m?: number | null;
}
export interface EvidenceItem { item: string; level: EvidenceLevel; source_ids: string[]; detail: string }
export interface DomainEvent { name: string; at: string; data: Record<string, unknown> }
export interface EvaluateResponse {
  mission_name: string; route_choice: string; assessment: AssessmentDTO;
  alternative: { route_choice: string; status: Status; reason_codes: string[]; total_minutes: number | null; total_consumable_units: number | null; total_length_m: number | null; total_gain_m: number | null };
  evidence: EvidenceItem[]; events: DomainEvent[]; run_manifest: Record<string, unknown>; disclaimer: string;
}
export interface ReplanResponse {
  baseline_status: Status;
  current_position: { x_m: number; y_m: number; elapsed_min: number; requested_elapsed_min: number; phase: string; segment: string; completed_stops: string[]; consumed_units: number; consumable_loss_units: number; snapping: string };
  event: { type: string; evidence_level: EvidenceLevel; center_xy_m: [number, number]; radius_m: number; placement: string; blocked_cells: number; affects_previous_route: boolean };
  response_mode: string; before: AssessmentDTO; after: AssessmentDTO; status_change: string; events: DomainEvent[]; run_manifest: Record<string, unknown>;
}

export interface SitePoint {
  id: string; name: string; x_m: number; y_m: number; lon_deg: number; lat_deg: number; sol: number; site: number; drive: number;
  evidence_level: EvidenceLevel; rover_elev_geoid_m?: number; dem_elev_m?: number | null;
}
export interface ScienceSite extends SitePoint {
  kind: string; location_basis: string; science_summary: string; default_activity_min: number;
  citations: { title: string; url: string }[];
  mapped_geologic_unit?: { symbol: string; name: string; caveat: string } | null;
}
export interface Habitat extends SitePoint { note: string; citation: string }
export interface LayerInfo { layer_id: string; title: string; evidence_level: EvidenceLevel; image_url: string; bounds_xy_m: [[number, number], [number, number]] }
export interface GeologyUnit { code: number; symbol: string; name: string; note: string; color: string; cells: number }
export interface StudyArea {
  study_area_id: string; name: string; body: string;
  crs: { name: string; sphere_radius_m: number; latitude_convention: string; longitude_convention: string; local_frame: string; east_west_scale_factor_at_center: number };
  grid: { width: number; height: number; res_m: number; origin_easting_m: number; origin_northing_bottom_m: number; origin_northing_top_m: number; lon_range_deg: [number, number]; lat_range_deg: [number, number] };
  extent_xy_m: [number, number]; scale: { east_west_ground_m_per_projected_m: number; center_lat_deg: number };
  dem_stats: { valid_fraction: number; min_m: number; max_m: number; slope_deg_p50: number; slope_deg_p95: number; slope_deg_max: number };
  habitat: Habitat; layers: LayerInfo[];
  rover_traverse: { source_id: string; points: { x_m: number; y_m: number; sol: number; site: number; drive: number }[] };
  geology_units: { units: GeologyUnit[]; coverage_fraction: number } | null; disclaimer: string;
}
export interface Photo {
  photo_id: string; image_url: string; site_id: string; site_name: string; instrument: string; sol: number;
  date_taken_utc: string; date_taken_mars: string; mast_azimuth_deg: string; mast_elevation_deg: string; caption: string;
  credit: string; source_url: string; full_res_url: string; geolocation: { basis: string; x_m: number; y_m: number; lon_deg: number; lat_deg: number; site: number; drive: number };
  evidence_level: EvidenceLevel;
}
export interface MedaSeries { variable: string; unit: string; instrument: string; file: string; hourly: { lmst_hour: number; mean: number; min: number; max: number; n: number }[]; note?: string }
export interface Observations {
  photos: Photo[];
  atmosphere: { status?: "NOT_INTEGRATED"; sol?: number; scope?: string; aggregation?: string; series?: MedaSeries[] };
}
export interface Dataset {
  source_id: string; title: string; category: string; mission?: string; instrument?: string; producer?: string; landing_page: string; url: string;
  units?: string; license?: string; citation?: string; known_limitation?: string; verification_status: "AVAILABLE_VERIFIED" | "PARTIAL" | "UNAVAILABLE";
  files: { path: string; sha256: string; bytes: number }[];
}
export interface DatasetsResponse {
  datasets: Dataset[];
  artifacts: { artifact_id: string; file: string; source_ids: string[]; checksum_sha256: string; evidence_level: string; limitations: string; resolution_m: number | null; units: string }[];
  alignment: {
    ortho_dem_grid_origin_difference_m: [number, number];
    registration_check: { best_shift_cells: { rows: number; cols: number }; best_correlation: number; zero_shift_correlation: number; method: string };
    dem_vs_rover_elevation: { n: number; median_dem_minus_rover_m: number; median_abs_m: number; p05_m: number; p95_m: number };
    geology_status: string; geology_note: string;
  };
}
export interface DefaultMission { mission_name: string; request: MissionRequest; labels: { consumable_label: string; profile_basis: string; note: string } }
export interface ApiError { error: { code: string; message: string; details?: unknown } }
