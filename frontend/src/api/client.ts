import type { DatasetsResponse, DefaultMission, EvaluateResponse, Habitat, MissionRequest, Observations, ReplanRequest, ReplanResponse, ScienceSite, StudyArea } from "./types";

/** Static build (GitHub Pages): GET data from exported JSON, computations in an in-browser Python engine. */
export const STATIC_MODE = import.meta.env.VITE_STATIC === "1";

export class ApiRequestError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiRequestError("NETWORK", "Cannot reach the EVA Pathfinder API. Is the backend running on port 8000?", 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    throw new ApiRequestError(err?.code ?? `HTTP_${res.status}`, err?.message ?? res.statusText, res.status);
  }
  return body as T;
}

// ---------------------------------------------------------------- static mode
const base = new URL(import.meta.env.BASE_URL, window.location.href).href;
let worker: Worker | null = null;
let seq = 0;
const pending = new Map<number, (r: string) => void>();

export interface AreaInfo { study_area_id: string; name: string; short_name: string; default: boolean; lon_range_deg?: [number, number]; lat_range_deg?: [number, number]; data_ready: boolean; plannable_sites?: number }

function engine<T>(endpoint: string, payload: unknown, area: string): Promise<T> {
  if (!worker) {
    worker = new Worker(new URL("./pyWorker.ts", import.meta.url), { type: "module" });
    worker.onmessage = (e: MessageEvent<{ id: number; result: string }>) => {
      pending.get(e.data.id)?.(e.data.result);
      pending.delete(e.data.id);
    };
  }
  const id = ++seq;
  return new Promise<T>((resolve, reject) => {
    pending.set(id, (raw) => {
      const r = JSON.parse(raw);
      if (r.ok) resolve(r.data as T);
      else reject(new ApiRequestError(r.error?.code ?? "ENGINE_ERROR", r.error?.message ?? "engine error", r.status ?? 0));
    });
    worker!.postMessage({ id, endpoint, body: JSON.stringify(payload), base, area });
  });
}

const staticGet = <T,>(area: string, name: string) => call<T>(`${base}static/areas/${area}/api/${name}.json`);
const q = (area: string) => `?area=${encodeURIComponent(area)}`;

/** Every call takes the planning-area id; routing happens inside one area at a time. */
export const api = STATIC_MODE
  ? {
      areas: () => call<{ areas: AreaInfo[] }>(`${base}static/areas.json`),
      studyArea: (a: string) => staticGet<StudyArea>(a, "study-area"),
      datasets: (a: string) => staticGet<DatasetsResponse>(a, "datasets"),
      observations: (a: string) => staticGet<Observations>(a, "observations"),
      scienceSites: (a: string) => staticGet<{ habitat: Habitat; sites: ScienceSite[] }>(a, "science-sites"),
      defaultMission: (a: string) => staticGet<DefaultMission>(a, "missions-default"),
      evaluate: (a: string, req: MissionRequest) => engine<EvaluateResponse>("missions/evaluate", req, a),
      replan: (a: string, req: ReplanRequest) => engine<ReplanResponse>("scenarios/replan", req, a),
      report: (a: string, mission: MissionRequest, replan: ReplanRequest | null) => engine<Record<string, unknown>>("reports", { mission, replan }, a),
    }
  : {
      areas: () => call<{ areas: AreaInfo[] }>("/api/v1/areas"),
      studyArea: (a: string) => call<StudyArea>("/api/v1/study-area" + q(a)),
      datasets: (a: string) => call<DatasetsResponse>("/api/v1/datasets" + q(a)),
      observations: (a: string) => call<Observations>("/api/v1/observations" + q(a)),
      scienceSites: (a: string) => call<{ habitat: Habitat; sites: ScienceSite[] }>("/api/v1/science-sites" + q(a)),
      defaultMission: (a: string) => call<DefaultMission>("/api/v1/missions/default" + q(a)),
      evaluate: (a: string, req: MissionRequest) => call<EvaluateResponse>("/api/v1/missions/evaluate" + q(a), { method: "POST", body: JSON.stringify(req) }),
      replan: (a: string, req: ReplanRequest) => call<ReplanResponse>("/api/v1/scenarios/replan" + q(a), { method: "POST", body: JSON.stringify(req) }),
      report: (a: string, mission: MissionRequest, replan: ReplanRequest | null) =>
        call<Record<string, unknown>>("/api/v1/reports" + q(a), { method: "POST", body: JSON.stringify({ mission, replan }) }),
    };
