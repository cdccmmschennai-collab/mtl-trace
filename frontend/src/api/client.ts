import type {
  CanonicalPage,
  Comparison,
  Consolidation,
  Run,
  RunSource,
  Scope,
  ScopeValidationReport,
  Session,
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
  const body = res.status === 204 ? null : await res.json().catch(() => null);
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
  // ---- the one working session: scope → its single run
  /** Resolves to null before a scope has been loaded. */
  getSession: () => request<Session | null>("/api/session"),
  /** Dry run; the current session is untouched. */
  validateScope: (file: File) => upload<ScopeValidationReport>("/api/session/scope/validate", file),
  /** Replaces the whole session (scope, documents, results) with one built on this scope. */
  startSession: (file: File) => upload<Session>("/api/session/scope", file),
  resetSession: () => request<null>("/api/session", { method: "DELETE" }),
  getScope: (milestoneId: number) => request<Scope>(`/api/milestones/${milestoneId}/scope`),

  // ---- documents
  sourceTypes: () => request<SourceType[]>("/api/source-types"),
  getRun: (runId: number) => request<Run>(`/api/runs/${runId}`),
  uploadSource: (runId: number, file: File, fields: { source_type?: string } = {}) =>
    upload<RunSource>(`/api/runs/${runId}/sources`, file, fields),
  /** Resolves to the updated run. */
  removeSource: (runId: number, sourceId: number) =>
    request<Run>(`/api/runs/${runId}/sources/${sourceId}`, { method: "DELETE" }),
  /** Process an uploaded document again as the chosen type. */
  retypeSource: (runId: number, sourceId: number, sourceType: string) =>
    request<RunSource>(`/api/runs/${runId}/sources/${sourceId}/type`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: sourceType }),
    }),
  sourceRows: (runId: number, sourceId: number, offset: number, limit: number) =>
    request<SourceRowsPage>(`/api/runs/${runId}/sources/${sourceId}/rows?offset=${offset}&limit=${limit}`),

  // ---- consolidation & comparison
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
