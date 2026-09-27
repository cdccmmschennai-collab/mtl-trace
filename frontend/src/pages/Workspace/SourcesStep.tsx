import { useRef, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  Spinner,
  SourceTypeIcon,
  TriangleAlert,
  Upload,
} from "../../components/icons";
import { ErrorLine, FileDrop, Status, Step, type StepState } from "../../components/ui";
import { nf, plural } from "../../lib/format";
import type { RunSource, SourceType } from "../../types/api";
import type { DocView, Workspace } from "./useWorkspace";

const ATTRS = [
  { code: "TAG_NUMBER", short: "TAG" },
  { code: "MAKE", short: "MAKE" },
  { code: "MODEL", short: "MODEL" },
  { code: "SERIAL_NUMBER", short: "SERIAL" },
  { code: "PART_NUMBER", short: "PART" },
];
const ACCEPT = ".xlsx,.xlsm";

export function SourcesStep({ ws, state }: { ws: Workspace; state: StepState }) {
  const usable = ws.usable.length;
  const status = ws.processing ? (
    <Status tone="accent" kind="busy">Processing</Status>
  ) : ws.docs.length === 0 ? (
    <Status tone="muted">No documents</Status>
  ) : usable ? (
    ws.unknownCount ? (
      <Status tone="review" kind="warn">{`${usable} ready · ${ws.unknownCount} needs type`}</Status>
    ) : (
      <Status tone="match" kind="done">{`${usable} ready`}</Status>
    )
  ) : ws.unknownCount ? (
    <Status tone="review" kind="warn">{`${ws.unknownCount} needs type`}</Status>
  ) : (
    <Status tone="mismatch" kind="error">Not processed</Status>
  );

  const scopeTags = ws.tagCount;
  const intakeLocked = ws.run === undefined || ws.consPhase === "running" || ws.cmpPhase === "running";

  return (
    <Step id="st-src" title="Source documents" state={state} status={status} glowHeight={380}>
      <div className="mt-step-content mt-stack">
        {ws.docs.length === 0 ? (
          <FileDrop
            className="mt-dropzone"
            accept={ACCEPT}
            multiple
            disabled={intakeLocked}
            label="Drop source files or browse files"
            onFiles={ws.addSources}
          >
            <span className="mt-dropzone-icon">
              <Upload size={20} />
            </span>
            <span className="mt-dropzone-title">Drop source files</span>
            <span className="mt-dropzone-sub">Excel documents · multiple files</span>
            <span className="mt-dropzone-types">
              {ws.types.length ? ws.types.filter((t) => t.adapter_available).map((t) => t.label).join(" · ") : " "}
            </span>
            <span className="mt-pill">Browse files</span>
          </FileDrop>
        ) : (
          <div className="mt-panel mt-doclist">
            {ws.docs.map((d) => (
              <DocRow
                key={d.key}
                doc={d}
                scopeTags={scopeTags}
                open={ws.openDocs.has(d.key)}
                onToggle={() => ws.toggleDoc(d.key)}
                types={ws.types}
                canRetype={!ws.processing && ws.consPhase !== "running" && ws.cmpPhase !== "running"}
                hasFile={d.source ? ws.hasFileFor(d.source) : false}
                onRetype={ws.retype}
              />
            ))}
            <FileDrop
              className="mt-drop-row"
              accept={ACCEPT}
              multiple
              disabled={intakeLocked}
              label="Drop or browse to add files"
              onFiles={ws.addSources}
            >
              <span className="mt-drop-row-label">
                <Upload size={15} /> Drop or browse to add files
              </span>
              <span className="mono mt-drop-row-count">{plural(ws.docs.length, "file")}</span>
            </FileDrop>
          </div>
        )}
        {ws.srcErrors.map((e, i) => (
          <ErrorLine key={i} message={e} />
        ))}
      </div>
    </Step>
  );
}

function DocRow({
  doc,
  scopeTags,
  open,
  onToggle,
  types,
  canRetype,
  hasFile,
  onRetype,
}: {
  doc: DocView;
  scopeTags: number;
  open: boolean;
  onToggle: () => void;
  types: SourceType[];
  canRetype: boolean;
  hasFile: boolean;
  onRetype: (rs: RunSource, type: string, picked?: File) => void;
}) {
  const s = doc.source;
  const proc = doc.phase === "processing";
  const ready = !!s && !proc && (doc.phase === "ok" || doc.phase === "warn");
  const matched = s?.matched_tag_count ?? 0;
  const pct = ready && scopeTags ? Math.min(100, (matched / scopeTags) * 100) : 0;

  const statusEl = proc ? (
    <span className="mt-doc-status tone-accent">
      <Spinner size={14} /> Processing
    </span>
  ) : doc.phase === "ok" ? (
    <span className="mt-doc-status tone-match">
      <CircleCheck size={15} className="pop" /> Ready
    </span>
  ) : doc.phase === "warn" ? (
    <span className="mt-doc-status tone-review">
      <TriangleAlert size={15} /> {plural(s!.warnings.length, "warning")}
    </span>
  ) : doc.phase === "unknown" ? (
    <span className="mt-doc-status tone-review">
      <TriangleAlert size={15} /> Needs type
    </span>
  ) : (
    <span className="mt-doc-status tone-mismatch">
      <CircleAlert size={15} /> Not processed
    </span>
  );

  const typeLabel = proc
    ? s?.source_type_label ?? "Detecting type…"
    : s?.source_type_label ?? "Type not detected";

  return (
    <div className="mt-doc mt-in">
      <div className="mt-doc-grid">
        <span className="mt-doc-icon">
          <SourceTypeIcon code={s?.source_type ?? null} />
        </span>
        <span className="mt-doc-name mono">{doc.name}</span>
        {statusEl}
        <span />
        <span className={`mt-doc-type${!proc && !s?.source_type ? " is-missing" : ""}`}>{typeLabel}</span>
        <span className="mt-doc-cov mono">
          {ready ? `${nf(matched)} / ${nf(scopeTags)} in scope` : proc ? "reading…" : `— / ${nf(scopeTags)}`}
        </span>
        <span />
        <span className="mt-doc-bar">
          <span style={{ width: `${pct}%` }} />
        </span>
        <span />
        <span className="mt-doc-attrs">
          {ATTRS.map((a) => (
            <span key={a.code} className={`mono${ready && s!.attributes_provided.includes(a.code) ? "" : " is-missing"}`}>
              {a.short}
            </span>
          ))}
        </span>
        {s && !proc ? (
          <button type="button" className="mt-doc-details" onClick={onToggle} aria-expanded={open}>
            Details {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        ) : (
          <span />
        )}
      </div>
      {open && s && !proc && (
        <DocDetails source={s} unknown={doc.phase === "unknown"} types={types} canRetype={canRetype} hasFile={hasFile} onRetype={onRetype} />
      )}
    </div>
  );
}

function DocDetails({
  source: s,
  unknown,
  types,
  canRetype,
  hasFile,
  onRetype,
}: {
  source: RunSource;
  unknown: boolean;
  types: SourceType[];
  canRetype: boolean;
  hasFile: boolean;
  onRetype: (rs: RunSource, type: string, picked?: File) => void;
}) {
  const [choice, setChoice] = useState("");
  const picker = useRef<HTMLInputElement>(null);
  const facts: [string, string][] = [
    ["Sheet", s.sheet_name ?? "—"],
    ["Header row", s.header_row != null ? String(s.header_row) : "—"],
    ["Rows read", s.row_count != null ? nf(s.row_count) : "—"],
    ["Tags found", s.unique_tag_count != null ? nf(s.unique_tag_count) : "—"],
    ["Outside scope, not added", s.unmatched_tag_count != null ? nf(s.unmatched_tag_count) : "—"],
    ["Duplicate tags", s.duplicate_tag_count != null ? nf(s.duplicate_tag_count) : "—"],
  ];

  const choose = (type: string) => {
    setChoice(type);
    if (!type) return;
    if (hasFile) onRetype(s, type);
    else picker.current?.click(); // the file is not held in this session: ask for it again (verified by SHA-256)
  };

  return (
    <div className="mt-doc-details-body mt-in-fast">
      {unknown && (
        <div className="mt-type-pick">
          <span className="mt-type-pick-label">Type not detected</span>
          <select
            className="mt-select"
            aria-label="Document type"
            value={choice}
            disabled={!canRetype}
            onChange={(e) => choose(e.target.value)}
          >
            <option value="">Choose type…</option>
            {types
              .filter((t) => t.adapter_available)
              .map((t) => (
                <option key={t.code} value={t.code}>
                  {t.label}
                </option>
              ))}
          </select>
          {!hasFile && <span className="mt-type-pick-hint">You will be asked to choose the file again.</span>}
          <input
            ref={picker}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f && choice) onRetype(s, choice, f);
            }}
          />
        </div>
      )}
      <div className="mt-facts">
        {facts.map(([k, v]) => (
          <div key={k} className="mt-fact">
            <span className="mt-fact-k">{k}</span>
            <span className="mt-fact-v mono">{v}</span>
          </div>
        ))}
      </div>
      {s.errors.map((e, i) => (
        <div key={`e${i}`} className="mt-issue is-error">
          <CircleAlert size={14} />
          <span>{e.message}</span>
        </div>
      ))}
      {s.warnings.map((w, i) => (
        <div key={`w${i}`} className="mt-issue is-warn">
          <TriangleAlert size={14} />
          <span>{w.message}</span>
        </div>
      ))}
    </div>
  );
}
