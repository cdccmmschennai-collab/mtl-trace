import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  FileSpreadsheet,
  CheckCircle2,
  Lock,
  UploadCloud,
  FileCheck2,
  Search,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import { ApiError, api } from "../../api/client";
import { IssueList } from "../../components/IssueList";
import { ErrorBanner } from "../../components/common";
import type { MilestoneDetail, Scope, ScopeValidationReport } from "../../types/api";

interface Props {
  milestone: MilestoneDetail;
  onChanged: () => void;
}

export function ScopeTab({ milestone, onChanged }: Props) {
  const [scope, setScope] = useState<Scope | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ScopeValidationReport | null>(null);
  const [busy, setBusy] = useState<"validate" | "import" | "lock" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmLock, setConfirmLock] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadScope = useCallback(() => {
    api.getScope(milestone.id).then(setScope, (e: Error) => setError(e.message));
  }, [milestone.id]);

  useEffect(loadScope, [loadScope]);

  const locked = milestone.scope_status === "LOCKED";
  const hasScope = (scope?.tag_count ?? 0) > 0;

  function pickFile(f: File | null) {
    setFile(f);
    setReport(null);
    setError(null);
  }

  async function run(kind: "validate" | "import" | "lock", action: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (err) {
      if (err instanceof ApiError && err.report) setReport(err.report);
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const validate = () => run("validate", async () => setReport(await api.validateScope(milestone.id, file!)));

  const importScope = () =>
    run("import", async () => {
      await api.importScope(milestone.id, file!);
      pickFile(null);
      if (fileInput.current) fileInput.current.value = "";
      loadScope();
      onChanged();
    });

  const lock = () =>
    run("lock", async () => {
      await api.lockScope(milestone.id);
      setConfirmLock(false);
      loadScope();
      onChanged();
    });

  return (
    <section className="tab-body">
      <Steps milestone={milestone} hasFile={!!file} report={report} />
      <ErrorBanner message={error} />

      {locked && scope && (
        <div className="banner banner-locked card">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <ShieldCheck size={22} style={{ color: "var(--ok)" }} />
            <div>
              <strong style={{ fontSize: 16 }}>Final Scope Locked</strong>
              <p className="muted" style={{ margin: 0 }}>This tag universe is authoritative for all consolidation &amp; comparison operations.</p>
            </div>
          </div>
          <dl className="facts" style={{ marginTop: 16 }}>
            <dt>Milestone Code</dt>
            <dd className="mono">{milestone.milestone_code}</dd>
            <dt>Project</dt>
            <dd>{milestone.project_name || "—"}</dd>
            <dt>Total Scope Tags</dt>
            <dd className="strong mono">{scope.tag_count.toLocaleString()}</dd>
            <dt>Source Scope Workbook</dt>
            <dd className="mono">{scope.file_name}</dd>
          </dl>
          <div style={{ marginTop: 16 }}>
            <Link className="btn btn-primary" to={`/milestones/${milestone.id}/sources`}>
              Continue to Sources
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      )}

      {!locked && (
        <div className="card">
          <h2>{hasScope ? "Replace Draft Tag Scope" : "Upload Finalized Tag Scope"}</h2>
          <p className="muted">Upload the master scope workbook (.xlsx), validate structure and tags, then import.</p>

          <div
            className="file-dropzone"
            onClick={() => fileInput.current?.click()}
            style={{ margin: "16px 0" }}
          >
            <div className="file-dropzone-icon">
              <UploadCloud size={24} />
            </div>
            <div>
              <strong style={{ display: "block", fontSize: 14 }}>
                {file ? file.name : "Click to select scope file"}
              </strong>
              <span className="muted" style={{ fontSize: 12 }}>
                {file ? `${(file.size / 1024).toFixed(1)} KB` : "Supports Excel (.xlsx, .xlsm)"}
              </span>
            </div>
            <input
              ref={fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
              aria-label="Scope workbook"
              style={{ display: "none" }}
            />
          </div>

          <div className="actions">
            <button className="btn" disabled={!file || busy !== null} onClick={validate}>
              <FileCheck2 size={16} />
              {busy === "validate" ? "Validating Scope…" : "Validate Scope"}
            </button>
            <button
              className="btn btn-primary"
              disabled={!report?.valid || busy !== null}
              onClick={importScope}
              title={report?.valid ? "" : "Validate a file without errors first"}
            >
              <FileSpreadsheet size={16} />
              {busy === "import" ? "Importing Scope…" : report?.valid ? `Import ${report.tag_count} Tags` : "Import Scope"}
            </button>
          </div>

          {report && <ValidationReport report={report} />}
        </div>
      )}

      {!locked && hasScope && scope && (
        <div className="card card-lock">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <Lock size={20} style={{ color: "var(--accent)" }} />
            <h2 style={{ margin: 0 }}>Lock Scope Universe</h2>
          </div>
          <p>
            <strong>{scope.tag_count} tags</strong> imported from <em>{scope.file_name}</em>. Locking enforces this scope universe permanently for all document consolidation.
          </p>
          {!confirmLock ? (
            <button className="btn btn-primary" onClick={() => setConfirmLock(true)} disabled={busy !== null} style={{ marginTop: 8 }}>
              <Lock size={16} />
              Lock Scope Permanently…
            </button>
          ) : (
            <div className="confirm" role="alertdialog" aria-label="Confirm scope lock">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, color: "var(--err)" }}>
                <AlertTriangle size={18} />
                <strong>Lock {scope.tag_count} tags permanently?</strong>
              </div>
              <p className="muted">This action locks the tag scope universe and cannot be undone.</p>
              <div className="actions" style={{ marginTop: 12 }}>
                <button className="btn btn-danger" onClick={lock} disabled={busy !== null}>
                  <Lock size={16} />
                  {busy === "lock" ? "Locking…" : `Yes, Lock ${scope.tag_count} Tags`}
                </button>
                <button className="btn btn-ghost" onClick={() => setConfirmLock(false)} disabled={busy !== null}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {scope && hasScope && <ScopeTable scope={scope} />}
    </section>
  );
}

function Steps({ milestone, hasFile, report }: { milestone: MilestoneDetail; hasFile: boolean; report: ScopeValidationReport | null }) {
  const s = milestone.scope_status;
  const steps = [
    { label: "Select File", done: hasFile || s !== "NONE" },
    { label: "Validate Structure", done: !!report?.valid || s !== "NONE" },
    { label: "Import Scope", done: s !== "NONE" },
    { label: "Lock Scope", done: s === "LOCKED" },
  ];
  const current = steps.findIndex((x) => !x.done);
  return (
    <ol className="steps">
      {steps.map((x, i) => (
        <li key={x.label} className={x.done ? "done" : i === current ? "current" : ""}>
          <span className="step-n">{x.done ? "✓" : i + 1}</span>
          {x.label}
        </li>
      ))}
    </ol>
  );
}

function ValidationReport({ report }: { report: ScopeValidationReport }) {
  return (
    <div className={`report ${report.valid ? "report-ok" : "report-bad"}`}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {report.valid ? <CheckCircle2 size={18} style={{ color: "var(--ok)" }} /> : <AlertTriangle size={18} style={{ color: "var(--err)" }} />}
        <h3 style={{ margin: 0 }}>
          {report.valid ? `Validation Passed — ${report.tag_count} tags ready to import` : `Validation Failed — ${report.errors.length} issue(s) detected`}
        </h3>
      </div>
      <dl className="facts" style={{ marginTop: 10 }}>
        <dt>File</dt>
        <dd className="mono">{report.file_name}</dd>
        {report.sheet_name && (
          <>
            <dt>Target Sheet</dt>
            <dd className="mono">{report.sheet_name}</dd>
          </>
        )}
      </dl>
      <IssueList title="Errors (blocking import)" issues={report.errors} />
      <IssueList title="Warnings" issues={report.warnings} />
    </div>
  );
}

function ScopeTable({ scope }: { scope: Scope }) {
  const [filter, setFilter] = useState("");
  const rows = useMemo(() => {
    const q = filter.trim().toUpperCase();
    if (!q) return scope.tags;
    return scope.tags.filter((t) =>
      [t.s_no, t.tag_number, t.tag_description, t.equipment_description, t.size_rating].some((v) => v?.toUpperCase().includes(q)),
    );
  }, [scope.tags, filter]);

  return (
    <div className="card">
      <div className="table-head">
        <div>
          <h2>
            {scope.scope_status === "LOCKED" ? "Locked Tag Scope" : "Draft Tag Scope"}
          </h2>
          <p className="muted" style={{ margin: 0 }}>
            {scope.tag_count.toLocaleString()} tags registered from <span className="mono">{scope.file_name}</span>
          </p>
        </div>
        <div className="search-box">
          <Search size={15} className="search-icon" />
          <input className="filter" placeholder="Filter scope tags..." value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter tags" />
        </div>
      </div>

      {filter && (
        <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Showing {rows.length} of {scope.tag_count} tags
        </p>
      )}

      <div className="table-scroll">
        <table className="grid scope-grid">
          <thead>
            <tr>
              <th style={{ width: 80 }}>S.NO</th>
              <th>TAG NUMBER</th>
              <th>TAG DESCRIPTION</th>
              <th>EQUIPMENT DESCRIPTION</th>
              <th>SIZE &amp; RATING</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.scope_order}>
                <td className="mono muted">{t.s_no ?? ""}</td>
                <td className="mono strong" style={{ color: "var(--accent)" }}>{t.tag_number}</td>
                <td>{t.tag_description ?? "—"}</td>
                <td>{t.equipment_description ?? "—"}</td>
                <td className="mono" style={{ fontSize: 12 }}>{t.size_rating ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
