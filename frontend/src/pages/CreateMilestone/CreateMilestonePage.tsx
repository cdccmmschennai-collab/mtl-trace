import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, FolderPlus, Check, X } from "lucide-react";
import { api } from "../../api/client";
import { ErrorBanner } from "../../components/common";

export function CreateMilestonePage() {
  const [code, setCode] = useState("");
  const [project, setProject] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const m = await api.createMilestone({
        milestone_code: code.trim(),
        project_name: project.trim() || undefined,
      });
      navigate(`/milestones/${m.id}/scope`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <Link to="/" className="back-link">
        <ArrowLeft size={16} />
        Back to Milestones
      </Link>

      <div className="card card-hero">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div className="brand-icon" style={{ width: 40, height: 40 }}>
            <FolderPlus size={22} />
          </div>
          <div>
            <h1>Create New Milestone</h1>
            <p className="muted">Initialize a milestone container for finalized tag scopes.</p>
          </div>
        </div>

        <form className="form" onSubmit={submit}>
          <label>
            <span>
              Milestone Identifier <em>Required</em>
            </span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. MTL-2026-001"
              autoFocus
              required
              maxLength={64}
              className="mono"
            />
            <small className="muted">Unique identifier. Use letters, digits, hyphen (-), underscore (_) or period (.).</small>
          </label>

          <label>
            <span>Project Name / Description</span>
            <input
              value={project}
              onChange={(e) => setProject(e.target.value)}
              placeholder="e.g. Central Processing Facility Upgrade"
              maxLength={200}
            />
          </label>

          <ErrorBanner message={error} />

          <div className="actions" style={{ marginTop: 8 }}>
            <button className="btn btn-primary" type="submit" disabled={busy || !code.trim()}>
              <Check size={16} />
              {busy ? "Creating Milestone…" : "Create Milestone"}
            </button>
            <Link to="/" className="btn btn-ghost">
              <X size={16} />
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}
