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

function engine<T>(endpoint: string, payload: unknown): Promise<T> {
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
    worker!.postMessage({ id, endpoint, body: JSON.stringify(payload), base });
  });
}

const staticGet = <T,>(name: string) => call<T>(`${base}static/api/${name}.json`);

export const api = STATIC_MODE
  ? {
      studyArea: () => staticGet<StudyArea>("study-area"),
      datasets: () => staticGet<DatasetsResponse>("datasets"),
      observations: () => staticGet<Observations>("observations"),
      scienceSites: () => staticGet<{ habitat: Habitat; sites: ScienceSite[] }>("science-sites"),
      defaultMission: () => staticGet<DefaultMission>("missions-default"),
      evaluate: (req: MissionRequest) => engine<EvaluateResponse>("missions/evaluate", req),
      replan: (req: ReplanRequest) => engine<ReplanResponse>("scenarios/replan", req),
      report: (mission: MissionRequest, replan: ReplanRequest | null) => engine<Record<string, unknown>>("reports", { mission, replan }),
    }
  : {
      studyArea: () => call<StudyArea>("/api/v1/study-area"),
      datasets: () => call<DatasetsResponse>("/api/v1/datasets"),
      observations: () => call<Observations>("/api/v1/observations"),
      scienceSites: () => call<{ habitat: Habitat; sites: ScienceSite[] }>("/api/v1/science-sites"),
      defaultMission: () => call<DefaultMission>("/api/v1/missions/default"),
      evaluate: (req: MissionRequest) => call<EvaluateResponse>("/api/v1/missions/evaluate", { method: "POST", body: JSON.stringify(req) }),
      replan: (req: ReplanRequest) => call<ReplanResponse>("/api/v1/scenarios/replan", { method: "POST", body: JSON.stringify(req) }),
      report: (mission: MissionRequest, replan: ReplanRequest | null) =>
        call<Record<string, unknown>>("/api/v1/reports", { method: "POST", body: JSON.stringify({ mission, replan }) }),
    };
