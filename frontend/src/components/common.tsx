import { Link } from "react-router-dom";
import type { RunSummary, ScopeStatus } from "../types/api";

const SCOPE_LABEL: Record<ScopeStatus, string> = {
  NONE: "No scope",
  DRAFT: "Draft scope",
  LOCKED: "Scope locked",
};

export function ScopeBadge({ status }: { status: ScopeStatus }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{SCOPE_LABEL[status]}</span>;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="banner banner-error" role="alert">
      {message}
    </div>
  );
}

/** Plain-language progress of a milestone's current source set (runs are internal). */
export function progressLabel(latest: RunSummary | null): string {
  if (!latest) return "No sources yet";
  return latest.status === "CONSOLIDATED" ? "Consolidated" : latest.status === "CREATED" ? "No sources yet" : "Sources uploaded";
}

export function LockScopeFirst({ milestoneId, reason }: { milestoneId: number; reason: string }) {
  return (
    <section className="tab-body">
      <div className="card">
        <h2>Lock the scope first</h2>
        <p className="muted">{reason}</p>
        <Link className="btn btn-primary" to={`/milestones/${milestoneId}/scope`}>
          Go to Scope
        </Link>
      </div>
    </section>
  );
}

export function NoSourcesYet({ milestoneId }: { milestoneId: number }) {
  return (
    <div className="card">
      <h2>No source documents yet</h2>
      <p className="muted">Upload the source documents for this milestone first.</p>
      <Link className="btn btn-primary" to={`/milestones/${milestoneId}/sources`}>
        Go to Sources
      </Link>
    </div>
  );
}
