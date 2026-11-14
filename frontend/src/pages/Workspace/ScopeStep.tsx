import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import {
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  FileSpreadsheet,
  Search,
  ShieldCheck,
  Spinner,
  TriangleAlert,
  Upload,
} from "../../components/icons";
import { ErrorLine, FileDrop, Status, Step } from "../../components/ui";
import { fmtSize, nf, plural } from "../../lib/format";
import type { Scope, ScopeValidationReport } from "../../types/api";
import { CHECK_COUNT, type Workspace } from "./useWorkspace";

const SCOPE_COLUMNS = ["S.NO", "TAG NUMBER", "TAG DESCRIPTION", "EQUIPMENT DESCRIPTION", "SIZE & RATING"];
const READ_ERRORS = ["UNSUPPORTED_FILE_TYPE", "UNREADABLE_WORKBOOK", "SCOPE_SHEET_AMBIGUOUS", "SCOPE_SHEET_NOT_FOUND"];
const COLUMN_ERRORS = ["MISSING_REQUIRED_COLUMNS", "DUPLICATE_HEADER"];

type Check = { label: string; state: "ok" | "warn" | "error"; detail: string };

/** The four checks shown to the user, read from the backend's validation report. */
function checksOf(r: ScopeValidationReport): Check[] {
  const codes = new Set(r.errors.map((e) => e.code));
  const unread = READ_ERRORS.some((c) => codes.has(c));
  const columnsBad = unread || COLUMN_ERRORS.some((c) => codes.has(c));
  const dups = r.errors.filter((e) => e.code === "DUPLICATE_TAG").length;
  return [
    { label: "Workbook read", state: unread ? "error" : "ok", detail: unread ? "not read" : `sheet ${r.sheet_name} · row ${r.header_row}` },
    {
      label: "Required columns found",
      state: columnsBad ? "error" : "ok",
      detail: unread ? "—" : `${Math.min(Object.keys(r.columns).length, SCOPE_COLUMNS.length)} of ${SCOPE_COLUMNS.length}`,
    },
    {
      label: "No duplicate tags",
      state: columnsBad || dups ? "error" : "ok",
      detail: columnsBad ? "—" : dups ? `${plural(dups, "duplicate")}` : `${nf(r.tag_count)} unique`,
    },
    {
      label: "No blocking errors",
      state: r.errors.length ? "error" : r.warnings.length ? "warn" : "ok",
      detail: r.errors.length ? plural(r.errors.length, "error") : r.warnings.length ? plural(r.warnings.length, "warning") : "none",
    },
  ];
}

export function ScopeStep({ ws }: { ws: Workspace }) {
  const { scopePhase: phase, milestone, report, hasSession } = ws;
  const replaceInput = useRef<HTMLInputElement>(null);
  const [showTags, setShowTags] = useState(false);

  const status = {
    empty: <Status tone="muted">{""}</Status>,
    selected: <Status tone="muted">File selected</Status>,
    validating: <Status tone="accent" kind="busy">Validating</Status>,
    validated: <Status tone="match" kind="done">Valid</Status>,
    invalid: <Status tone="mismatch" kind="error">Not valid</Status>,
    starting: <Status tone="accent" kind="busy">Loading</Status>,
    loaded: <Status tone="match" kind="done">Loaded</Status>,
  }[phase];

  const fileStage = ["selected", "validating", "validated", "invalid", "starting"].includes(phase);
  const n = ws.tagCount;
  const busy = phase === "validating" || phase === "starting";

  return (
    <Step id="st-scope" title="Finalized tag scope" status={status}>
      <div className="mt-step-content">
        {phase === "empty" && (
          <div className="mt-stack mt-in">
            <FileDrop
              className="mt-dropzone"
              accept=".xlsx,.xlsm"
              label="Drop scope workbook or browse files"
              onFiles={(f) => ws.pickScopeFile(f[0])}
            >
              <span className="mt-dropzone-icon">
                <FileSpreadsheet size={20} />
              </span>
              <span className="mt-dropzone-title">Drop scope workbook</span>
              <span className="mt-dropzone-sub">Excel · .xlsx or .xlsm · one workbook</span>
              <span className="mt-pill">Browse files</span>
            </FileDrop>
            <span className="mt-columns-hint mono">{SCOPE_COLUMNS.join(" · ")}</span>
          </div>
        )}

        {fileStage && ws.scopeFile && (
          <div className="mt-panel mt-in">
            <div className="mt-file-row">
              <FileSpreadsheet size={20} className="mt-ink-2" />
              <div className="mt-file-meta">
                <span className="mt-file-name mono">{ws.scopeFile.name}</span>
                <span className="mt-file-size mono">{fmtSize(ws.scopeFile.size)}</span>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={ws.clearScopeFile} disabled={busy}>
                {hasSession ? "Cancel" : "Replace"}
              </button>
            </div>
            <div className="mt-panel-section mt-pad">
              {phase === "selected" && (
                <button type="button" className="btn btn-primary" onClick={ws.validateScope}>
                  <ShieldCheck /> Validate scope
                </button>
              )}
              {phase === "validating" && !report && <CheckList checks={[]} pending={1} />}
              {report && phase !== "selected" && (
                <CheckList checks={checksOf(report).slice(0, ws.checksShown)} pending={Math.min(1, CHECK_COUNT - ws.checksShown)} />
              )}
              {(phase === "validated" || phase === "starting") && report && (
                <div className="mt-import-row mt-in">
                  <span className="mt-found">
                    <span className="mt-found-n">{nf(report.tag_count)}</span>tags found
                    {hasSession && <span className="mt-ink-label mt-replace-note">Replaces the current scope, documents and results.</span>}
                  </span>
                  <button type="button" className="btn btn-primary" onClick={ws.startSession} disabled={phase === "starting" || ws.processing}>
                    {phase === "starting" ? <Spinner size={15} /> : <Upload size={15} />}
                    {phase === "starting" ? "Loading" : `Use ${nf(report.tag_count)} tags`}
                  </button>
                </div>
              )}
              {phase === "invalid" && report && (
                <div className="mt-issues mt-in">
                  {report.errors.map((e, i) => (
                    <div key={i} className="mt-issue is-error">
                      <CircleAlert size={14} />
                      <span>{e.message}</span>
                    </div>
                  ))}
                  <span className="mt-issues-hint">
                    Correct the workbook and choose it again{hasSession ? "." : " with Replace."}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {phase === "loaded" && milestone && (
          <div className="mt-panel mt-file-row mt-in-mid">
            <FileSpreadsheet size={20} className="mt-ink-2" />
            <div className="mt-file-meta">
              <span className="mt-file-name mono">{milestone.scope_file_name}</span>
              <span className="mt-file-state">
                Finalized scope · <span className="tnum">{nf(n)}</span> tags
              </span>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowTags((s) => !s)} aria-expanded={showTags}>
              Tags {showTags ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => replaceInput.current?.click()}
              disabled={ws.processing || ws.consPhase === "running" || ws.cmpPhase === "running"}
            >
              New scope
            </button>
            <input
              ref={replaceInput}
              type="file"
              accept=".xlsx,.xlsm"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) ws.pickScopeFile(f);
              }}
            />
          </div>
        )}

        {showTags && milestone && phase === "loaded" && <ScopeTags milestoneId={milestone.id} version={milestone.scope_imported_at} />}

        <ErrorLine message={ws.scopeError} />
      </div>
    </Step>
  );
}

function CheckList({ checks, pending }: { checks: Check[]; pending: number }) {
  return (
    <div className="mt-checks">
      {checks.map((c) => (
        <div key={c.label} className="mt-check mt-in-fast">
          <span className={`mt-check-icon is-${c.state}`}>
            {c.state === "ok" ? <CircleCheck className="pop" /> : c.state === "warn" ? <TriangleAlert className="pop" /> : <CircleAlert className="pop" />}
          </span>
          <span className="mt-check-label">{c.label}</span>
          <span className="mt-check-detail mono">{c.detail}</span>
        </div>
      ))}
      {pending > 0 && (
        <div className="mt-check mt-in-fast">
          <span className="mt-check-icon is-busy">
            <Spinner />
          </span>
          <span className="mt-check-label">{checks.length === 0 ? "Workbook read" : "Checking"}</span>
          <span className="mt-check-detail" />
        </div>
      )}
    </div>
  );
}

function ScopeTags({ milestoneId, version }: { milestoneId: number; version: string | null }) {
  const [scope, setScope] = useState<Scope | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.getScope(milestoneId).then(setScope, (e: Error) => setError(e.message));
  }, [milestoneId, version]);

  const rows = useMemo(() => {
    const Q = q.trim().toUpperCase();
    const tags = scope?.tags ?? [];
    if (!Q) return tags;
    return tags.filter((t) =>
      [t.s_no, t.tag_number, t.tag_description, t.equipment_description, t.size_rating].some((v) => v?.toUpperCase().includes(Q)),
    );
  }, [scope, q]);

  return (
    <div className="mt-tags mt-in-fast">
      <div className="mt-tags-filter">
        <Search className="mt-faint" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter tags" aria-label="Filter scope tags" />
        <span className="mono mt-tags-count">
          {scope ? (q.trim() ? `${nf(rows.length)} of ${nf(scope.tag_count)}` : `${nf(scope.tag_count)} tags`) : ""}
        </span>
      </div>
      <div className="mt-tags-scroll">
        <table className="mt-table">
          <thead>
            <tr>
              <th className="mt-col-sno">S.No</th>
              <th>Tag number</th>
              <th>Tag description</th>
              <th>Equipment description</th>
              <th>Size &amp; rating</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.scope_order}>
                <td className="mt-ink-3 tnum">{t.s_no ?? ""}</td>
                <td className="mono mt-tag">{t.tag_number}</td>
                <td>{t.tag_description ?? ""}</td>
                <td className="mt-ink-2">{t.equipment_description ?? ""}</td>
                <td className="mt-ink-2 nowrap">{t.size_rating ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!scope && !error && <div className="mt-tags-empty">Loading tags…</div>}
        {error && <div className="mt-tags-empty">{error}</div>}
      </div>
    </div>
  );
}
