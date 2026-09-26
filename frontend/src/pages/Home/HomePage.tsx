import { useEffect, useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, FolderPlus, Search, Database, FileSpreadsheet, Layers, ArrowRight } from "lucide-react";
import { api } from "../../api/client";
import { ErrorBanner, ScopeBadge, formatDate, progressLabel } from "../../components/common";
import type { MilestoneSummary } from "../../types/api";

export function HomePage() {
  const [milestones, setMilestones] = useState<MilestoneSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api.listMilestones().then(setMilestones, (e: Error) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!milestones) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return milestones;
    return milestones.filter(
      (m) =>
        m.milestone_code.toLowerCase().includes(q) ||
        (m.project_name && m.project_name.toLowerCase().includes(q)),
    );
  }, [milestones, filter]);

  const lockedCount = milestones?.filter((m) => m.scope_status === "LOCKED").length ?? 0;
  const totalTags = milestones?.reduce((acc, m) => acc + (m.tag_count || 0), 0) ?? 0;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Milestone Workspace</h1>
          <p className="muted">Engineering data consolidation, tag scope locking, and attribute comparison.</p>
        </div>
        <Link className="btn btn-primary" to="/milestones/new">
          <Plus size={16} />
          New Milestone
        </Link>
      </div>

      <ErrorBanner message={error} />

      {milestones && milestones.length > 0 && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">
              <Layers size={20} />
            </div>
            <div className="stat-content">
              <span className="stat-value">{milestones.length}</span>
              <span className="stat-label">Total Milestones</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "var(--ok-bg)", color: "var(--ok)" }}>
              <FileSpreadsheet size={20} />
            </div>
            <div className="stat-content">
              <span className="stat-value">{lockedCount}</span>
              <span className="stat-label">Locked Scopes</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "#e0e7ff", color: "#4f46e5" }}>
              <Database size={20} />
            </div>
            <div className="stat-content">
              <span className="stat-value">{totalTags.toLocaleString()}</span>
              <span className="stat-label">Total Tags in Scope</span>
            </div>
          </div>
        </div>
      )}

      {milestones === null && !error && (
        <div className="card">
          <p className="muted">Loading milestones…</p>
        </div>
      )}

      {milestones?.length === 0 && (
        <div className="empty">
          <div className="empty-icon">
            <FolderPlus size={28} />
          </div>
          <h2>No milestones yet</h2>
          <p className="muted">Create a milestone to import its finalized tag scope and consolidate engineering source files.</p>
          <Link className="btn btn-primary" to="/milestones/new" style={{ marginTop: 8 }}>
            <Plus size={16} />
            Create First Milestone
          </Link>
        </div>
      )}

      {milestones && milestones.length > 0 && (
        <div className="card">
          <div className="table-head">
            <h2>Milestones Directory</h2>
            <div className="search-box">
              <Search size={15} className="search-icon" />
              <input
                className="filter"
                placeholder="Search milestone or project..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </div>
          </div>

          <div className="table-container">
            <table className="grid grid-clickable">
              <thead>
                <tr>
                  <th>Milestone Code</th>
                  <th>Project Name</th>
                  <th className="num">Scope Tags</th>
                  <th>Scope Status</th>
                  <th>Created Date</th>
                  <th>Progress</th>
                  <th style={{ width: 40 }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((m) => (
                  <tr key={m.id} onClick={() => navigate(`/milestones/${m.id}/scope`)}>
                    <td>
                      <Link to={`/milestones/${m.id}/scope`} className="strong mono" onClick={(e) => e.stopPropagation()}>
                        {m.milestone_code}
                      </Link>
                    </td>
                    <td>{m.project_name ?? "—"}</td>
                    <td className="num mono">{m.tag_count ? m.tag_count.toLocaleString() : "—"}</td>
                    <td>
                      <ScopeBadge status={m.scope_status} />
                    </td>
                    <td className="muted">{formatDate(m.created_at)}</td>
                    <td className="muted">{m.scope_status === "LOCKED" ? progressLabel(m.latest_run) : "—"}</td>
                    <td>
                      <ArrowRight size={16} className="muted" />
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="muted" style={{ textAlign: "center", padding: "24px" }}>
                      No milestones matching &quot;{filter}&quot;
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}
