import { CircleCheck, Combine, Download, SourceTypeIcon, Spinner, TriangleAlert } from "../../components/icons";
import { ErrorLine, Status, Step, type StepState } from "../../components/ui";
import { api } from "../../api/client";
import { fmtWhen, nf, plural } from "../../lib/format";
import type { Workspace } from "./useWorkspace";

const WORKBOOK_KIND = "CONSOLIDATED_WORKBOOK";

export function ConsolidationStep({ ws, state, onDownloaded }: { ws: Workspace; state: StepState; onDownloaded: (file: string) => void }) {
  const { consPhase: phase, cons } = ws;
  const scopeTags = ws.tagCount;

  const status =
    phase === "done" ? (
      <Status tone="match" kind="done">Complete</Status>
    ) : phase === "running" ? (
      <Status tone="accent" kind="busy">Consolidating</Status>
    ) : phase === "stale" ? (
      <Status tone="review" kind="warn">Out of date</Status>
    ) : (
      <Status tone="accent">Ready</Status>
    );

  // Before consolidating: each usable document's own coverage. After: the consolidated coverage per source type.
  const rows = cons
    ? cons.coverage.map((c) => ({ key: c.source_type, code: c.source_type, label: c.label, n: c.in_scope_tags, of: cons.scope_tag_count }))
    : ws.usable.map((s) => ({
        key: String(s.id),
        code: s.source_type,
        label: s.source_type_label ?? "",
        n: s.matched_tag_count ?? 0,
        of: scopeTags,
      }));

  const included = cons ? cons.documents.filter((d) => d.included).length : ws.usable.length;
  const workbook = cons?.outputs.find((o) => o.kind === WORKBOOK_KIND);
  const barTone = phase === "done" || phase === "running" ? "is-accent" : "is-idle";

  return (
    <Step id="st-cons" title="Consolidate sources" state={state} status={status}>
      <div className="mt-panel mt-step-content mt-in-mid">
        {phase === "stale" && (
          <div className="mt-stale">
            <TriangleAlert size={14} /> Documents changed. Consolidate again.
          </div>
        )}
        {phase === "done" && cons && (
          <div className="mt-done-head">
            <div className="mt-done-title">
              <CircleCheck size={20} className="tone-match pop" />
              <div className="mt-col">
                <span className="mt-done-label">Consolidation complete</span>
                <span className="mt-done-sub">
                  <span className="tnum">{nf(cons.canonical_row_count)}</span> tags consolidated from {plural(included, "source document")}{" "}
                  <span className="mono mt-when">· {fmtWhen(cons.consolidated_at)}</span>
                </span>
              </div>
            </div>
            {workbook && (
              <a
                className="btn btn-secondary btn-sm-32"
                href={api.downloadUrl(cons.run_id, workbook.id)}
                download
                onClick={() => onDownloaded(workbook.file_name)}
              >
                <Download size={15} /> Consolidated workbook
              </a>
            )}
          </div>
        )}
        <div className="mt-pad mt-stack-12">
          {phase === "running" && (
            <div className="mt-running">
              <span className="mt-running-label">
                <Spinner size={15} />
                Building consolidated dataset
              </span>
            </div>
          )}
          {rows.map((r) => (
            <div key={r.key} className="mt-cov-row">
              <span className="mt-ink-3 mt-flex">
                <SourceTypeIcon code={r.code} size={16} />
              </span>
              <span className="mt-cov-type">{r.label}</span>
              <span className="mt-cov-bar">
                <span className={barTone} style={{ width: `${r.of ? Math.min(100, (r.n / r.of) * 100) : 0}%` }} />
              </span>
              <span className="mt-cov-n mono">
                {nf(r.n)} / {nf(r.of)}
              </span>
            </div>
          ))}
          {ws.excluded.length > 0 && phase !== "done" && (
            <span className="mt-excluded">Not included: {ws.excluded.map((s) => s.original_filename).join(", ")}</span>
          )}
          {(phase === "idle" || phase === "stale") && (
            <div className="mt-pt-4">
              <button type="button" className="btn btn-primary" onClick={ws.consolidate} disabled={!ws.docsReady}>
                <Combine /> {phase === "stale" ? "Consolidate again" : "Consolidate sources"}
              </button>
            </div>
          )}
          <ErrorLine message={ws.consError} />
        </div>
      </div>
    </Step>
  );
}
