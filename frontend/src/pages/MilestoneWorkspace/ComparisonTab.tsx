import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, GitCompare, GitMerge } from "lucide-react";
import { api } from "../../api/client";
import { useWorkingRun } from "../../api/useWorkingRun";
import { ErrorBanner, LockScopeFirst } from "../../components/common";
import type { Comparison, Consolidation, MilestoneDetail } from "../../types/api";
import { StatusCounts } from "./ResultsTab";

export function ComparisonTab({ milestone }: { milestone: MilestoneDetail }) {
  const locked = milestone.scope_status === "LOCKED";
  const { run, error, setError } = useWorkingRun(milestone.id, locked);
  const [cons, setCons] = useState<Consolidation | null | undefined>(undefined);
  const [cmp, setCmp] = useState<Comparison | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  const consolidated = run?.status === "CONSOLIDATED";

  useEffect(() => {
    if (!run || run.status !== "CONSOLIDATED") return;
    Promise.all([api.getConsolidation(run.id), api.getComparison(run.id)]).then(
      ([c, r]) => {
        setCons(c);
        setCmp(r);
      },
      (e: Error) => setError(e.message),
    );
  }, [run, setError]);

  if (!locked) {
    return <LockScopeFirst milestoneId={milestone.id} reason="Comparison runs on the locked tag scope." />;
  }

  async function compare() {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      setCmp(await api.compare(run.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tab-body">
      <ErrorBanner message={error} />
      {run === undefined && <p className="muted">Loading comparison state…</p>}
      {run !== undefined && !consolidated && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <GitMerge size={20} style={{ color: "var(--accent)" }} />
            <h2 style={{ margin: 0 }}>Consolidate First</h2>
          </div>
          <p className="muted" style={{ marginBottom: 16 }}>Comparison uses the consolidated data of all uploaded source documents.</p>
          <Link className="btn btn-primary" to={`/milestones/${milestone.id}/consolidation`}>
            <GitMerge size={16} />
            Go to Consolidation
          </Link>
        </div>
      )}
      {consolidated && (cons === undefined || cmp === undefined) && <p className="muted">Loading comparison state…</p>}
      {consolidated && cons && cmp !== undefined && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <GitCompare size={20} style={{ color: "var(--accent)" }} />
            <h2 style={{ margin: 0 }}>Attribute Comparison Engine</h2>
          </div>
          <p className="muted">
            Compares each attribute across the participating source documents for every tag in the locked scope. FINAL is
            taken from the highest-priority source holding a value; FINAL TAG is always the milestone tag.
          </p>

          <dl className="facts" style={{ marginTop: 16 }}>
            <dt>Participating sources</dt>
            <dd>
              {cons.source_types.map((t, i) => (
                <span className="badge badge-neutral chip" key={t.code}>
                  {i + 1}. {t.label}
                </span>
              ))}
            </dd>
            <dt>Attributes</dt>
            <dd>
              {cons.attributes.map((a) => (
                <span className="badge badge-neutral chip" key={a.code}>
                  {a.label}
                </span>
              ))}
            </dd>
          </dl>

          {cmp === null && (
            <div className="actions" style={{ marginTop: 20 }}>
              <button className="btn btn-primary" disabled={busy} onClick={compare}>
                <GitCompare size={16} />
                {busy ? "Comparing…" : "Run Comparison"}
              </button>
            </div>
          )}
        </div>
      )}

      {cmp && (
        <div className="card banner-locked">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <CheckCircle2 size={24} style={{ color: "var(--ok)" }} />
            <h2 style={{ margin: 0 }}>Comparison Completed</h2>
          </div>
          <StatusCounts cmp={cmp} />
          <div className="actions" style={{ marginTop: 16 }}>
            <Link className="btn btn-primary" to={`/milestones/${milestone.id}/results`}>
              View Results
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
