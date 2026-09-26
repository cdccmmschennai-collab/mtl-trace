import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Navigate, useParams } from "react-router-dom";
import { ArrowLeft, FileSpreadsheet, UploadCloud, GitMerge, GitCompare, BarChart3 } from "lucide-react";
import { api } from "../../api/client";
import { ErrorBanner, ScopeBadge, formatDate } from "../../components/common";
import type { MilestoneDetail } from "../../types/api";
import { ComparisonTab } from "./ComparisonTab";
import { ConsolidationTab } from "./ConsolidationTab";
import { ResultsTab } from "./ResultsTab";
import { ScopeTab } from "./ScopeTab";
import { SourcesTab } from "./SourcesTab";

const TABS = [
  { key: "scope", label: "Scope", icon: FileSpreadsheet },
  { key: "sources", label: "Sources", icon: UploadCloud },
  { key: "consolidation", label: "Consolidation", icon: GitMerge },
  { key: "comparison", label: "Comparison", icon: GitCompare },
  { key: "results", label: "Results", icon: BarChart3 },
] as const;

export function WorkspacePage() {
  const { id, tab } = useParams();
  const milestoneId = Number(id);
  const [milestone, setMilestone] = useState<MilestoneDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    api.getMilestone(milestoneId).then(setMilestone, (e: Error) => setError(e.message));
  }, [milestoneId]);

  useEffect(reload, [reload]);

  const active = TABS.find((t) => t.key === tab);
  if (!active) return <Navigate to={`/milestones/${milestoneId}/scope`} replace />;

  return (
    <main className="page">
      <Link to="/" className="back-link">
        <ArrowLeft size={16} />
        Back to Milestones
      </Link>
      <ErrorBanner message={error} />
      {milestone && (
        <>
          <header className="ws-head">
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h1 className="mono" style={{ margin: 0 }}>{milestone.milestone_code}</h1>
                <ScopeBadge status={milestone.scope_status} />
              </div>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                {milestone.project_name || "No project assigned"} · Created {formatDate(milestone.created_at)}
              </p>
            </div>
          </header>

          <nav className="tabs-nav" aria-label="Milestone workspace">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <NavLink key={t.key} to={`/milestones/${milestoneId}/${t.key}`} className="tab-link">
                  <Icon size={16} />
                  <span>{t.label}</span>
                </NavLink>
              );
            })}
          </nav>

          {active.key === "scope" && <ScopeTab milestone={milestone} onChanged={reload} />}
          {active.key === "sources" && <SourcesTab milestone={milestone} onChanged={reload} />}
          {active.key === "consolidation" && <ConsolidationTab milestone={milestone} onChanged={reload} />}
          {active.key === "comparison" && <ComparisonTab milestone={milestone} />}
          {active.key === "results" && <ResultsTab milestone={milestone} />}
        </>
      )}
    </main>
  );
}
