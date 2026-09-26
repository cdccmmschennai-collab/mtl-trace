import type {
  CanonicalPage,
  Comparison,
  Consolidation,
  MilestoneDetail,
  MilestoneSummary,
  Run,
  RunSource,
  Scope,
  ScopeValidationReport,
  SourceRowsPage,
  SourceType,
} from "../types/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public report?: ScopeValidationReport,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    if (detail && typeof detail === "object" && "report" in detail) {
      throw new ApiError(res.status, detail.message, detail.report);
    }
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : res.statusText;
    throw new ApiError(res.status, message);
  }
  return body as T;
}

function upload<T>(path: string, file: File, fields: Record<string, string | undefined> = {}): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  for (const [k, v] of Object.entries(fields)) if (v) form.append(k, v);
  return request<T>(path, { method: "POST", body: form });
}

export const api = {
  listMilestones: () => request<MilestoneSummary[]>("/api/milestones"),
  getMilestone: (id: number) => request<MilestoneDetail>(`/api/milestones/${id}`),
  createMilestone: (body: { milestone_code: string; project_name?: string }) =>
    request<MilestoneDetail>("/api/milestones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getScope: (id: number) => request<Scope>(`/api/milestones/${id}/scope`),
  validateScope: (id: number, file: File) => upload<ScopeValidationReport>(`/api/milestones/${id}/scope/validate`, file),
  importScope: (id: number, file: File) =>
    upload<{ report: ScopeValidationReport; milestone: MilestoneDetail }>(`/api/milestones/${id}/scope`, file),
  lockScope: (id: number) => request<MilestoneDetail>(`/api/milestones/${id}/scope/lock`, { method: "POST" }),

  sourceTypes: () => request<SourceType[]>("/api/source-types"),
  listRuns: (milestoneId: number) => request<Run[]>(`/api/milestones/${milestoneId}/runs`),
  createRun: (milestoneId: number, notes?: string, baseRunId?: number | null) =>
    request<Run>(`/api/milestones/${milestoneId}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: notes || null, base_run_id: baseRunId ?? null }),
    }),
  getRun: (runId: number) => request<Run>(`/api/runs/${runId}`),
  uploadSource: (
    runId: number,
    file: File,
    fields: { source_type?: string },
  ) => upload<RunSource>(`/api/runs/${runId}/sources`, file, fields),
  sourceRows: (runId: number, sourceId: number, offset: number, limit: number) =>
    request<SourceRowsPage>(`/api/runs/${runId}/sources/${sourceId}/rows?offset=${offset}&limit=${limit}`),

  consolidate: (runId: number) => request<Consolidation>(`/api/runs/${runId}/consolidate`, { method: "POST" }),
  /** Resolves to null while the run has not been consolidated. */
  getConsolidation: (runId: number) =>
    request<Consolidation>(`/api/runs/${runId}/consolidation`).catch((e) => {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }),
  canonical: (runId: number, p: { offset: number; limit: number; filter: string; search: string }) =>
    request<CanonicalPage>(
      `/api/runs/${runId}/canonical?offset=${p.offset}&limit=${p.limit}&filter=${p.filter}` +
        (p.search ? `&search=${encodeURIComponent(p.search)}` : ""),
    ),
  compare: (runId: number) => request<Comparison>(`/api/runs/${runId}/compare`, { method: "POST" }),
  /** Resolves to null while the run has not been compared. */
  getComparison: (runId: number) =>
    request<Comparison>(`/api/runs/${runId}/comparison`).catch((e) => {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }),
  downloadUrl: (runId: number, outputId: number) => `/api/runs/${runId}/outputs/${outputId}/download`,
};
