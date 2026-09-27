import { useEffect, useRef } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ArrowDown, Download, Spinner } from "../../components/icons";
import { Header, Toast, scrollToStep, useToast, type StepState } from "../../components/ui";
import { nf } from "../../lib/format";
import { ComparisonStep } from "./ComparisonStep";
import { ConsolidationStep } from "./ConsolidationStep";
import { ExcelStep } from "./ExcelStep";
import { ProgressBar, type NextAction } from "./ProgressBar";
import { ScopeSelector } from "./ScopeSelector";
import { ScopeStep } from "./ScopeStep";
import { SourcesStep } from "./SourcesStep";
import { useWorkspace } from "./useWorkspace";

/** `/` is a new tag scope; `/scopes/:milestoneId` an existing one. Each scope gets a fresh workspace. */
export function WorkspaceRoute() {
  const { milestoneId } = useParams();
  if (milestoneId === undefined) return <Workspace key="new" milestoneId={null} />;
  const id = Number(milestoneId);
  if (!Number.isInteger(id) || id <= 0) return <Navigate to="/" replace />;
  return <Workspace key={id} milestoneId={id} />;
}

function Workspace({ milestoneId }: { milestoneId: number | null }) {
  const ws = useWorkspace(milestoneId);
  const { toast, show: showToast } = useToast();
  const { milestone, scopePhase, show, consPhase, cmpPhase, cmp } = ws;

  const locked = scopePhase === "locked";
  const consDone = consPhase === "done";
  const cmpDone = cmpPhase === "done";

  const states: StepState[] = [
    locked ? "done" : "active",
    !locked ? "waiting" : ws.docsReady ? "done" : "active",
    !ws.docsReady ? "waiting" : consDone ? "done" : "active",
    !consDone ? "waiting" : cmpDone ? "done" : "active",
    !cmpDone ? "waiting" : ws.downloaded ? "done" : "active",
  ];

  const downloadExcel = () => {
    if (!cmp?.output) return;
    ws.markDownloaded();
    showToast(`Downloaded · ${cmp.output.file_name}`);
  };

  const next = nextAction(ws, () => {
    if (!cmp?.output) return;
    const a = document.createElement("a");
    a.href = api.downloadUrl(cmp.run_id, cmp.output.id);
    a.download = cmp.output.file_name;
    a.click();
    downloadExcel();
  });

  // Each newly revealed step is scrolled into view — but not the ones already there when the page loads.
  const revealed = useRef<typeof show | null>(null);
  useEffect(() => {
    if (!ws.ready) return;
    const prev = revealed.current;
    revealed.current = show;
    if (!prev) return;
    const targets: [boolean, string, number][] = [
      [show.src && !prev.src, "st-src", 300],
      [show.cons && !prev.cons, "st-cons", 500],
      [show.cmp && !prev.cmp, "st-cmp", 350],
      [show.out && !prev.out, "st-out", 250],
    ];
    const hit = targets.filter(([t]) => t).pop();
    if (!hit) return;
    const id = window.setTimeout(() => scrollToStep(hit[1]), hit[2]);
    return () => window.clearTimeout(id);
  }, [ws.ready, show.src, show.cons, show.cmp, show.out]);

  const ref = milestone?.milestone_code ?? (ws.scopeRef || null);
  const scopeStatus = milestone?.scope_status ?? "NONE";
  const introMeta =
    scopeStatus === "LOCKED"
      ? `${nf(ws.tagCount)} tags · scope locked`
      : scopeStatus === "DRAFT"
        ? `${nf(ws.tagCount)} tags · draft`
        : "No scope imported";

  return (
    <div className="mt-page">
      <div aria-hidden="true" className="mt-glow-top" />
      <Header right={<ScopeSelector currentRef={milestone?.milestone_code ?? null} tags={scopeStatus === "NONE" ? 0 : ws.tagCount} />} />
      <ProgressBar states={states} next={next} />

      <main className="mt-main" id="main">
        <div className="mt-intro">
          <span className="mt-intro-ref mono">{ref ?? "NEW TAG SCOPE"}</span>
          <h1 className="mt-h1">Engineering data traceability</h1>
          <span className="mt-intro-meta mono">{milestone === undefined && !ws.loadError ? "Loading…" : introMeta}</span>
        </div>

        {ws.loadError && milestone === undefined ? (
          <div className="mt-panel mt-pad mt-load-error">
            <span>{ws.loadError}</span>
            <Link to="/">Start a new tag scope</Link>
          </div>
        ) : milestone === undefined ? null : (
          <>
            {ws.loadError && <div className="mt-error mt-load-banner">{ws.loadError}</div>}
            <ScopeStep ws={ws} state={states[0]} />
            {show.src && <SourcesStep ws={ws} state={states[1]} />}
            {show.cons && <ConsolidationStep ws={ws} state={states[2]} onDownloaded={(f) => showToast(`Downloaded · ${f}`)} />}
            {show.cmp && <ComparisonStep ws={ws} state={states[3]} />}
            {show.out && cmp && <ExcelStep cmp={cmp} state={states[4]} downloaded={ws.downloaded} onDownload={downloadExcel} />}
          </>
        )}
      </main>
      <Toast message={toast} />
    </div>
  );
}

function nextAction(ws: ReturnType<typeof useWorkspace>, download: () => void): NextAction {
  const go = (label: string, id: string, busy = false): NextAction => ({
    label,
    busy,
    icon: busy ? <Spinner size={14} /> : <ArrowDown size={14} />,
    onClick: () => scrollToStep(id),
  });
  if (!ws.ready) return go("Loading", "st-scope", true);
  switch (ws.scopePhase) {
    case "empty":
      return go("Upload tag scope", "st-scope");
    case "selected":
      return go("Validate scope", "st-scope");
    case "validating":
      return go("Validating", "st-scope", true);
    case "invalid":
      return go("Replace scope file", "st-scope");
    case "validated":
      return go(`Import ${nf(ws.report?.tag_count ?? 0)} tags`, "st-scope");
    case "importing":
      return go("Importing", "st-scope", true);
    case "imported":
      return go("Lock scope", "st-scope");
    case "locking":
      return go("Locking", "st-scope", true);
  }
  if (ws.docs.length === 0) return go("Add source files", "st-src");
  if (ws.processing) return go("Processing", "st-src", true);
  if (!ws.usable.length) return go("Set document type", "st-src");
  if (ws.consPhase === "running") return go("Consolidating", "st-cons", true);
  if (ws.consPhase !== "done") return go(ws.consPhase === "stale" ? "Consolidate again" : "Consolidate", "st-cons");
  if (ws.cmpPhase === "running") return go("Comparing", "st-cmp", true);
  if (ws.cmpPhase !== "done") return go("Compare", "st-cmp");
  return {
    label: ws.downloaded ? "Download again" : "Download Excel",
    icon: <Download size={14} />,
    onClick: () => {
      scrollToStep("st-out");
      download();
    },
  };
}
