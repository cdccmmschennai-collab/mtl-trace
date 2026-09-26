import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { GitMerge, CheckCircle2, Download, ArrowRight, Database, FileText, AlertTriangle } from "lucide-react";
import { api } from "../../api/client";
import { useWorkingRun } from "../../api/useWorkingRun";
import { ErrorBanner, LockScopeFirst, NoSourcesYet } from "../../components/common";
import type { Consolidation, MilestoneDetail } from "../../types/api";

const WORKBOOK_KIND = "CONSOLIDATED_WORKBOOK";

interface Props {
  milestone: MilestoneDetail;
  onChanged: () => void;
}

export function ConsolidationTab({ milestone, onChanged }: Props) {
  const locked = milestone.scope_status === "LOCKED";
  const { run, reload, error, setError } = useWorkingRun(milestone.id, locked);
  const [cons, setCons] = useState<Consolidation | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!run) return;
    if (run.status !== "CONSOLIDATED") {
      setCons(null);
      return;
    }
    setCons(undefined);
    api.getConsolidation(run.id).then(setCons, (e: Error) => setError(e.message));
  }, [run, setError]);

  if (!locked) {
    return <LockScopeFirst milestoneId={milestone.id} reason="Consolidation is always built on the locked tag scope." />;
  }

  const usable = run?.sources.filter((s) => s.processing_status !== "FAILED" && s.source_type) ?? [];
  const skipped = run?.sources.filter((s) => !usable.includes(s)) ?? [];

  async function consolidate() {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      setCons(await api.consolidate(run.id));
      await reload();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const workbook = cons?.outputs.find((o) => o.kind === WORKBOOK_KIND);

  return (
    <section className="tab-body">
      <ErrorBanner message={error} />
      {run === undefined && <p className="muted">Loading run status…</p>}
      {(run === null || (run && run.sources.length === 0)) && <NoSourcesYet milestoneId={milestone.id} />}

      {run && run.sources.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <GitMerge size={20} style={{ color: "var(--accent)" }} />
            <h2 style={{ margin: 0 }}>Source Document Consolidation</h2>
          </div>
          <p className="muted">Consolidates extracted values from all active source documents onto the authoritative scope universe.</p>

          <dl className="facts" style={{ marginTop: 16 }}>
            {usable.map((s) => (
              <FactPair key={s.id} term={s.source_type_label ?? ""} value={s.original_filename} />
            ))}
          </dl>

          {skipped.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, color: "var(--warn)" }}>
              <AlertTriangle size={16} />
              <span>Not included (failed or unrecognised): {skipped.map((s) => s.original_filename).join(", ")}</span>
            </div>
          )}

          {cons === null && (
            <div className="actions" style={{ marginTop: 20 }}>
              <button className="btn btn-primary" disabled={busy || usable.length === 0} onClick={consolidate}>
                <GitMerge size={16} />
                {busy ? "Consolidating Data Engine…" : "Run Consolidation Engine"}
              </button>
            </div>
          )}
        </div>
      )}

      {run && cons === undefined && run.status === "CONSOLIDATED" && <p className="muted">Loading consolidated dataset…</p>}

      {cons && (
        <div className="card banner-locked" style={{ border: "1px solid var(--ok-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <CheckCircle2 size={24} style={{ color: "var(--ok)" }} />
            <h2 style={{ margin: 0, color: "var(--ok-hover)" }}>Consolidation Successfully Completed</h2>
          </div>

          <div className="stats-grid" style={{ margin: "16px 0" }}>
            <div className="stat-card">
              <div className="stat-icon" style={{ background: "var(--ok-bg)", color: "var(--ok)" }}>
                <Database size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{cons.canonical_row_count.toLocaleString()}</span>
                <span className="stat-label">Tags Consolidated</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <FileText size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{usable.length}</span>
                <span className="stat-label">Active Sources Included</span>
              </div>
            </div>
          </div>

          <div className="actions" style={{ marginTop: 16 }}>
            <Link className="btn btn-primary" to={`/milestones/${milestone.id}/comparison`}>
              Continue to Comparison
              <ArrowRight size={16} />
            </Link>
            {workbook && (
              <a className="btn" href={api.downloadUrl(cons.run_id, workbook.id)} download>
                <Download size={16} />
                Download Consolidated Workbook (.xlsx)
              </a>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function FactPair({ term, value }: { term: string; value: string }) {
  return (
    <>
      <dt>{term}</dt>
      <dd className="mono">{value}</dd>
    </>
  );
}
