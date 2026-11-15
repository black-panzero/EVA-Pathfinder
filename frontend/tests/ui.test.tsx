import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AssessmentDTO, EvaluateResponse, LegDTO } from "../src/api/types";
import { AssessmentSummary } from "../src/components/GuardianPanel";
import { itinerary } from "../src/components/ElevationProfile";
import { RouteComparison } from "../src/components/RouteComparison";
import { fmt, fmtMin } from "../src/features/format";

const route = (len: number, z0: number, z1: number) => ({
  route_id: "r", policy: { policy_id: "p", max_slope_deg: 15, slope_weight: 0, unknown_policy: "block" },
  polyline_xy_m: [[0, 0], [len, 0]] as [number, number][],
  metrics: { length_m: len, elevation_gain_m: Math.max(0, z1 - z0), elevation_loss_m: Math.max(0, z0 - z1), max_derived_slope_deg: 5, mean_derived_slope_deg: 2, max_step_grade_deg: 3, unknown_length_fraction: 0, cell_count: 2, policy_cost: len },
  profile: [{ distance_m: 0, elevation_m: z0, slope_deg: 1, x_m: 0, y_m: 0 }, { distance_m: len, elevation_m: z1, slope_deg: 1, x_m: len, y_m: 0 }],
  geology_along_route: [], evidence_level: "DERIVED" as const,
});
const leg = (id: string, r: ReturnType<typeof route> | null, reasons: string[] = []): LegDTO => ({ leg_id: id, from: "a", to: "b", minutes: r ? 10 : null, consumable_units: r ? 10 : null, reason_codes: reasons, route: r });
const assessment = (status: AssessmentDTO["status"], reasons: string[], legs: LegDTO[]): AssessmentDTO => ({
  status, reason_codes: reasons, legs, activities: [],
  totals: { minutes: 100, consumable_units: 50, usable_time_min: 90, usable_consumable_units: 80, time_margin_min: -10, consumable_margin_units: 30, time_available_min: 120, consumable_initial_units: 100, reserve_fraction: 0.25, consumable_label: "Illustrative consumable" },
});
const plan = (a: AssessmentDTO): EvaluateResponse => ({ mission_name: "m", route_choice: "terrain", assessment: a, alternative: { route_choice: "shortest", status: a.status, reason_codes: [], total_minutes: 1, total_consumable_units: 1, total_length_m: 1, total_gain_m: 1 }, evidence: [], events: [], run_manifest: {}, disclaimer: "" });

describe("formatting", () => {
  it("formats minutes and missing values", () => {
    expect(fmtMin(135)).toBe("2 h 15 min");
    expect(fmtMin(null)).toBe("n/a");
    expect(fmt(Infinity, 0, "m")).toBe("n/a");
  });
});

describe("itinerary profile", () => {
  it("offsets each leg by the previous leg length (from backend metrics)", () => {
    const pts = itinerary([leg("1", route(100, 0, 10)), leg("2", route(100, 10, 0))]);
    expect(pts.map((p) => p.d)).toEqual([0, 100, 100, 200]);
  });
  it("stops at a leg without a route", () => {
    expect(itinerary([leg("1", route(100, 0, 10)), leg("2", null, ["NO_ROUTE"])]).length).toBe(2);
  });
});

describe("Guardian summary", () => {
  it("shows status as text and explains reason codes (colour is not the only cue)", () => {
    render(<AssessmentSummary a={assessment("INFEASIBLE", ["INSUFFICIENT_TIME"], [leg("1", route(100, 0, 0))])} />);
    expect(screen.getByText("INFEASIBLE")).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT_TIME")).toBeInTheDocument();
    expect(screen.getByText(/exceeds the time budget/)).toBeInTheDocument();
    expect(screen.getByText(/over limit/)).toBeInTheDocument();
  });
});

describe("Route comparison", () => {
  it("discloses coincident routes instead of hiding them", () => {
    const a = assessment("FEASIBLE", [], [leg("1", route(100, 0, 5)), leg("2", route(100, 5, 0))]);
    render(<RouteComparison plans={{ shortest: plan(a), terrain: plan(a) }} chosen="terrain" />);
    expect(screen.getByText(/same cell path/)).toBeInTheDocument();
    expect(screen.getAllByText("200 m").length).toBe(2);
  });
});
