import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, Download, GitCompare } from "lucide-react";
import { api } from "../../api/client";
import { useWorkingRun } from "../../api/useWorkingRun";
import { ErrorBanner, LockScopeFirst } from "../../components/common";
import type { Comparison, ComparisonStatus, MilestoneDetail } from "../../types/api";

const STATUSES: { name: ComparisonStatus; color: string }[] = [
  { name: "MATCH", color: "var(--ok)" },
  { name: "MISMATCH", color: "var(--warn)" },
  { name: "REVIEW REQUIRED", color: "var(--accent)" },
];

/** Result counts of a comparison. Counts are tag × attribute rows; blank rows carry no FINAL and no STATUS. */
export function StatusCounts({ cmp }: { cmp: Comparison }) {
  const rows = cmp.scope_tag_count * cmp.attributes.length;
  return (
    <>
      <div className="stats" style={{ margin: "16px 0 8px" }}>
        <div className="stat">
          <div className="stat-value">{cmp.scope_tag_count.toLocaleString()}</div>
          <div className="stat-label">Total Tags</div>
        </div>
        {STATUSES.map((s) => (
          <div className="stat" key={s.name}>
            <div className="stat-value" style={{ color: s.color }}>{(cmp.totals[s.name] ?? 0).toLocaleString()}</div>
            <div className="stat-label">{s.name}</div>
          </div>
        ))}
        <div className="stat">
          <div className="stat-value">{cmp.no_source_value.toLocaleString()}</div>
          <div className="stat-label">Blank (no source value)</div>
        </div>
      </div>
      <p className="stat-note">
        Counts are per tag and attribute: {cmp.scope_tag_count.toLocaleString()} tags × {cmp.attributes.length} attributes ={" "}
        {rows.toLocaleString()} rows.
      </p>
    </>
  );
}

export function ResultsTab({ milestone }: { milestone: MilestoneDetail }) {
  const locked = milestone.scope_status === "LOCKED";
  const { run, error, setError } = useWorkingRun(milestone.id, locked);
  const [cmp, setCmp] = useState<Comparison | null | undefined>(undefined);

  useEffect(() => {
    if (run === undefined) return;
    if (!run || run.status !== "CONSOLIDATED") {
      setCmp(null);
      return;
    }
    api.getComparison(run.id).then(setCmp, (e: Error) => setError(e.message));
  }, [run, setError]);

  if (!locked) {
    return <LockScopeFirst milestoneId={milestone.id} reason="Results are produced from the locked tag scope." />;
  }

  return (
    <section className="tab-body">
      <ErrorBanner message={error} />
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <BarChart3 size={20} style={{ color: "var(--accent)" }} />
          <h2 style={{ margin: 0 }}>Comparison Results &amp; Final Workbook</h2>
        </div>

        {cmp === undefined && <p className="muted">Loading comparison results…</p>}

        {cmp === null && (
          <>
            <p className="muted" style={{ marginBottom: 16 }}>No comparison has been run yet.</p>
            <Link className="btn btn-primary" to={`/milestones/${milestone.id}/comparison`}>
              <GitCompare size={16} />
              Go to Comparison
            </Link>
          </>
        )}

        {cmp && (
          <>
            <p className="muted">
              Sources compared, in priority order: {cmp.source_types.map((t) => t.label).join(", ")}.
            </p>
            <StatusCounts cmp={cmp} />
            <div className="actions" style={{ marginTop: 16 }}>
              {cmp.output && (
                <a className="btn btn-primary" href={api.downloadUrl(cmp.run_id, cmp.output.id)} download>
                  <Download size={16} />
                  Download Comparison Excel (.xlsx)
                </a>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
