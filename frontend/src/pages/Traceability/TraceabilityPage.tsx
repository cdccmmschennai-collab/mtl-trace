import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CircleCheck,
  Combine,
  Dot,
  Download,
  FileSpreadsheet,
  GitCompareArrows,
  LockKeyhole,
  Plus,
  Search,
  TriangleAlert,
  Upload,
  X,
} from "../../components/icons";
import { ErrorLine, Header, Toast, useToast } from "../../components/ui";
import { fmtDay, fmtTime, latest, nf } from "../../lib/format";
import { scopeState } from "../../lib/scopeState";
import type { Comparison, Consolidation, MilestoneDetail, MilestoneSummary, Run } from "../../types/api";

/**
 * Every tag scope with its state, latest activity and comparison workbook — read from the existing milestone,
 * run, consolidation and comparison endpoints. Nothing here is inferred beyond what those responses state.
 */
interface Entry {
  m: MilestoneSummary;
  detail: MilestoneDetail | null;
  run: Run | null; // the scope's current (latest) run
  cons: Consolidation | null;
  cmp: Comparison | null;
}

async function loadEntry(m: MilestoneSummary): Promise<Entry> {
  const [detail, runs] = await Promise.all([
    api.getMilestone(m.id),
    m.scope_status === "LOCKED" ? api.listRuns(m.id) : Promise.resolve([] as Run[]),
  ]);
  const run = runs[0] ?? null; // newest first
  let cons: Consolidation | null = null;
  let cmp: Comparison | null = null;
  if (run?.status === "CONSOLIDATED") [cons, cmp] = await Promise.all([api.getConsolidation(run.id), api.getComparison(run.id)]);
  return { m, detail, run, cons, cmp };
}

function lastActivity(e: Entry): string | null {
  const d = e.detail;
  return latest(
    e.m.created_at,
    d?.scope_imported_at,
    d?.scope_locked_at,
    ...(e.run?.sources.map((s) => s.processed_at) ?? []),
    e.cons?.consolidated_at,
    e.cmp?.compared_at,
    e.cmp?.output?.generated_at,
  );
}

export function TraceabilityPage() {
  const [params] = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [q, setQ] = useState(initialQ);
  const [open, setOpen] = useState<string | null>(initialQ ? initialQ.trim().toUpperCase() : null);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { toast, show } = useToast();

  useEffect(() => {
    let off = false;
    api
      .listMilestones()
      .then((list) =>
        Promise.all(list.map((m) => loadEntry(m).catch((): Entry => ({ m, detail: null, run: null, cons: null, cmp: null })))),
      )
      .then(
        (all) => {
          if (off) return;
          const at = (e: Entry) => new Date(lastActivity(e) ?? 0).getTime();
          setEntries(all.sort((a, b) => at(b) - at(a)));
        },
        (e: Error) => !off && setError(e.message),
      );
    return () => {
      off = true;
    };
  }, []);

  const rows = useMemo(() => {
    const Q = q.trim().toUpperCase();
    if (!entries) return [];
    if (!Q) return entries;
    return entries.filter((e) =>
      [e.m.milestone_code, e.detail?.scope_file_name, ...(e.run?.sources.map((s) => s.original_filename) ?? [])].some((v) =>
        v?.toUpperCase().includes(Q),
      ),
    );
  }, [entries, q]);

  return (
    <div className="mt-page">
      <div aria-hidden="true" className="mt-glow-top mt-glow-top-trace" />
      <Header
        brandLink="/"
        right={
          <Link to="/" className="btn btn-secondary btn-back">
            <ArrowLeft size={15} /> Back to workspace
          </Link>
        }
      />
      <main className="mt-main mt-main-trace" id="main">
        <div className="mt-trace-intro">
          <span className="mt-overline">HISTORY</span>
          <h1 className="mt-h2">Traceability</h1>
          <p className="mt-lede">Every workbook with its state, date and time.</p>
        </div>

        <label className="mt-search">
          <Search className="mt-faint" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search workbooks" aria-label="Search workbooks" />
          {q && (
            <button type="button" className="mt-search-clear" aria-label="Clear search" onClick={() => setQ("")}>
              <X size={14} />
            </button>
          )}
        </label>

        <ErrorLine message={error} />

        <div className="mt-panel mt-hist">
          <div className="mt-hist-grid mt-hist-head">
            <span>No.</span>
            <span>Workbook</span>
            <span>State</span>
            <span>Date &amp; time</span>
            <span />
          </div>
          {entries === null && !error && <div className="mt-hist-empty">Loading workbooks…</div>}
          {entries !== null && entries.length === 0 && <div className="mt-hist-empty">No tag scopes yet.</div>}
          {entries !== null && entries.length > 0 && rows.length === 0 && <div className="mt-hist-empty">No workbooks match “{q}”.</div>}
          {rows.map((e, i) => (
            <HistoryRow
              key={e.m.id}
              no={i + 1}
              entry={e}
              open={open === e.m.milestone_code.toUpperCase()}
              onToggle={() => setOpen((o) => (o === e.m.milestone_code.toUpperCase() ? null : e.m.milestone_code.toUpperCase()))}
              onDownloaded={(f) => show(`Downloaded · ${f}`)}
            />
          ))}
        </div>
      </main>
      <Toast message={toast} />
    </div>
  );
}

function HistoryRow({
  no,
  entry: e,
  open,
  onToggle,
  onDownloaded,
}: {
  no: number;
  entry: Entry;
  open: boolean;
  onToggle: () => void;
  onDownloaded: (file: string) => void;
}) {
  const { m, detail, run, cons, cmp } = e;
  const out = cmp?.output ?? null;
  const st = scopeState({
    scopeStatus: m.scope_status,
    hasSources: !!run && run.sources.length > 0,
    consolidated: !!cons,
    compared: !!cmp,
  });
  const last = lastActivity(e);
  const used = run ? run.sources.filter((s) => s.processing_status !== "FAILED").length : 0;
  const lastProcessed = latest(...(run?.sources.map((s) => s.processed_at) ?? []));

  const stages: { label: string; value: string; when: string | null; icon: ReactNode }[] = [
    { label: "Created", value: "Tag scope", when: m.created_at, icon: <Plus size={14} /> },
    {
      label: "Scope locked",
      value: m.scope_locked_at ? `${nf(m.tag_count)} tags` : "Not locked",
      when: m.scope_locked_at,
      icon: <LockKeyhole size={14} />,
    },
    {
      label: "Source documents",
      value: run && run.sources.length ? `${nf(used)} processed` : "None",
      when: run && run.sources.length ? lastProcessed : null,
      icon: <Upload size={14} />,
    },
    { label: "Consolidation", value: cons ? "Complete" : "Not run", when: cons?.consolidated_at ?? null, icon: <Combine size={14} /> },
    { label: "Comparison", value: cmp ? "Complete" : "Not run", when: cmp?.compared_at ?? null, icon: <GitCompareArrows size={14} /> },
    { label: "Excel output", value: out ? "Ready" : "Not generated", when: out?.generated_at ?? null, icon: <Download size={14} /> },
  ];

  const stateIcon = out ? <CircleCheck size={14} /> : st.label === "Draft scope" ? <TriangleAlert size={14} /> : <Dot size={14} />;

  return (
    <div className="mt-hist-item">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        className={`mt-hist-grid mt-hist-row${open ? " is-open" : ""}`}
        onClick={onToggle}
        onKeyDown={(ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            onToggle();
          }
        }}
      >
        <span className="mono mt-hist-no">{String(no).padStart(2, "0")}</span>
        <span className="mt-hist-ref">
          <FileSpreadsheet className="mt-ink-2" />
          <span className="mono mt-hist-ref-text">{m.milestone_code}</span>
          <span className="mt-faint mt-flex">{open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
        </span>
        <span className={`mt-hist-state tone-${st.tone}`}>
          {stateIcon}
          {st.label}
        </span>
        <span className="mt-hist-when">
          {last && (
            <>
              <span className="mt-hist-day">{fmtDay(last)}</span>
              <span className="mono mt-hist-time">{fmtTime(last)}</span>
            </>
          )}
        </span>
        <span className="mt-hist-dl">
          {out && (
            <a
              className="btn btn-primary btn-sm-32"
              href={api.downloadUrl(out.run_id, out.id)}
              download
              onClick={(ev) => {
                ev.stopPropagation();
                onDownloaded(out.file_name);
              }}
              onKeyDown={(ev) => ev.stopPropagation()}
            >
              <Download size={14} /> Download
            </a>
          )}
        </span>
      </div>
      {open && (
        <div className="mt-hist-detail mt-in-fast">
          <div className="mt-stage-grid">
            {stages.map((g) => (
                <div key={g.label} className="mt-stage">
                  <span className="mt-stage-label">
                    <span className={`mt-flex ${g.when ? "tone-match" : "mt-faint-2"}`}>{g.icon}</span>
                    {g.label}
                  </span>
                  <span className={`mt-stage-value${g.when ? "" : " is-empty"}`}>{g.value}</span>
                  <span className="mono mt-stage-when">
                    {g.when ? (
                      <>
                        {fmtDay(g.when)} · <span className="nowrap">{fmtTime(g.when)}</span>
                      </>
                    ) : (
                      "—"
                    )}
                  </span>
                </div>
            ))}
          </div>
          {out && <span className="mono mt-hist-file">{out.file_name}</span>}
          {detail === null && <span className="mt-ink-3">Details unavailable.</span>}
          <Link to={`/scopes/${m.id}`} className="mt-open-link">
            Open in workspace <ArrowRight size={14} />
          </Link>
        </div>
      )}
    </div>
  );
}
