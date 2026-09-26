import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, XCircle, ArrowRight } from "lucide-react";
import { api } from "../../api/client";
import { openRunForUpload, useWorkingRun } from "../../api/useWorkingRun";
import { IssueList } from "../../components/IssueList";
import { ErrorBanner, LockScopeFirst } from "../../components/common";
import type { MilestoneDetail, Run, RunSource, SourceType } from "../../types/api";

const ATTRIBUTE_LABELS: Record<string, string> = {
  MAKE: "MAKE",
  MODEL: "MODEL",
  SERIAL_NUMBER: "SERIAL",
  PART_NUMBER: "PART",
};

const STATUS_LABEL: Record<RunSource["processing_status"], string> = {
  PROCESSED: "Processed",
  PROCESSED_WITH_WARNINGS: "Processed (Warnings)",
  FAILED: "Failed",
};

interface Props {
  milestone: MilestoneDetail;
  onChanged: () => void;
}

export function SourcesTab({ milestone, onChanged }: Props) {
  const locked = milestone.scope_status === "LOCKED";
  const { run, setRun, error, setError } = useWorkingRun(milestone.id, locked);
  const [types, setTypes] = useState<SourceType[]>([]);

  useEffect(() => {
    if (locked) api.sourceTypes().then(setTypes, (e: Error) => setError(e.message));
  }, [locked, setError]);

  if (!locked) {
    return <LockScopeFirst milestoneId={milestone.id} reason="Source documents are checked against the locked tag scope universe." />;
  }

  const sources = run?.sources ?? [];

  return (
    <section className="tab-body">
      <ErrorBanner message={error} />
      {run === undefined && <p className="muted">Loading workspace run…</p>}
      {run !== undefined && (
        <UploadCard
          milestoneId={milestone.id}
          run={run}
          types={types}
          onUploaded={(r) => {
            setRun(r);
            onChanged();
          }}
        />
      )}

      {sources.length > 0 && (
        <div className="card">
          <div className="table-head">
            <div>
              <h2>Uploaded Source Documents</h2>
              <p className="muted" style={{ margin: 0 }}>{sources.length} document(s) uploaded for consolidation</p>
            </div>
            <Link className="btn btn-primary" to={`/milestones/${milestone.id}/consolidation`}>
              Continue to Consolidation
              <ArrowRight size={16} />
            </Link>
          </div>
          <div className="table-container">
            <table className="grid">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Source Type</th>
                  <th>Status</th>
                  <th className="num">Rows</th>
                  <th className="num">Tags Found</th>
                  <th className="num">In Scope</th>
                  <th className="num">Outside Scope</th>
                  <th>Extracted Attributes</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <FileText size={16} className="muted" />
                        <span className="strong mono">{s.original_filename}</span>
                      </div>
                    </td>
                    <td>{s.source_type_label ?? "Not recognised"}</td>
                    <td>
                      <StatusBadge status={s.processing_status} />
                    </td>
                    <td className="num mono">{s.row_count ?? "—"}</td>
                    <td className="num mono">{s.unique_tag_count ?? "—"}</td>
                    <td className="num mono" style={{ color: "var(--ok)", fontWeight: 600 }}>{s.matched_tag_count ?? "—"}</td>
                    <td className="num mono">{s.unmatched_tag_count ?? "—"}</td>
                    <td className="small">
                      {Object.entries(ATTRIBUTE_LABELS)
                        .filter(([k]) => k in s.attribute_counts)
                        .map(([k, label]) => `${label}: ${s.attribute_counts[k]}`)
                        .join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {sources
            .filter((s) => s.errors.length || s.warnings.length)
            .map((s) => (
              <details key={s.id} className="detail-list" open={s.processing_status === "FAILED"} style={{ marginTop: 14 }}>
                <summary style={{ fontSize: 13, color: s.processing_status === "FAILED" ? "var(--err)" : "var(--warn)" }}>
                  {s.original_filename}: {s.errors.length} error(s), {s.warnings.length} warning(s)
                </summary>
                <IssueList title="Errors" issues={s.errors} />
                <IssueList title="Warnings" issues={s.warnings} />
              </details>
            ))}
        </div>
      )}
    </section>
  );
}

function StatusBadge({ status }: { status: RunSource["processing_status"] }) {
  const cls = status === "PROCESSED" ? "badge-locked" : status === "FAILED" ? "badge-failed" : "badge-draft";
  const Icon = status === "PROCESSED" ? CheckCircle2 : status === "FAILED" ? XCircle : AlertTriangle;
  return (
    <span className={`badge ${cls}`}>
      <Icon size={12} />
      {STATUS_LABEL[status]}
    </span>
  );
}

function UploadCard({
  milestoneId,
  run,
  types,
  onUploaded,
}: {
  milestoneId: number;
  run: Run | null;
  types: SourceType[];
  onUploaded: (r: Run) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const reopens = run?.status === "CONSOLIDATED";

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const target = await openRunForUpload(milestoneId, run);
      await api.uploadSource(target.id, file, { source_type: type || undefined });
      setFile(null);
      setType("");
      if (input.current) input.current.value = "";
      onUploaded(await api.getRun(target.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <UploadCloud size={20} style={{ color: "var(--accent)" }} />
        <h2 style={{ margin: 0 }}>Upload Source Document</h2>
      </div>
      {reopens && (
        <p className="text-warn" style={{ fontSize: 13, marginBottom: 12 }}>
          Note: Source documents are currently consolidated. Adding a new file will require re-consolidation.
        </p>
      )}

      <div className="upload-grid">
        <label>
          <span>Source File (.xlsx)</span>
          <input ref={input} type="file" accept=".xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Source document" />
        </label>
        <label>
          <span>Source Document Type</span>
          <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Source type">
            <option value="">Detect Automatically</option>
            {types.map((t) => (
              <option key={t.code} value={t.code} disabled={!t.adapter_available}>
                {t.label}
                {t.adapter_available ? "" : " — not yet available"}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={error} />
      <div className="actions" style={{ marginTop: 12 }}>
        <button className="btn btn-primary" disabled={!file || busy} onClick={submit}>
          <UploadCloud size={16} />
          {busy ? "Processing Document…" : "Upload & Process Document"}
        </button>
      </div>
    </div>
  );
}
