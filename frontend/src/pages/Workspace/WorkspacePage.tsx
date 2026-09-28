import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Header, Toast, scrollToStep, useToast, type StepState } from "../../components/ui";
import { ComparisonStep } from "./ComparisonStep";
import { ConsolidationStep } from "./ConsolidationStep";
import { ExcelStep } from "./ExcelStep";
import { ScopeSelector } from "./ScopeSelector";
import { ScopeStep } from "./ScopeStep";
import { SourcesStep } from "./SourcesStep";
import { useWorkspace } from "./useWorkspace";
import { WorkflowNav, type WorkflowItem } from "./WorkflowNav";

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

  const workflow: WorkflowItem[] = [
    { id: "st-scope", label: "Scope", state: states[0], available: true },
    { id: "st-src", label: "Sources", state: states[1], available: show.src },
    { id: "st-cons", label: "Consolidate", state: states[2], available: show.cons },
    { id: "st-cmp", label: "Compare", state: states[3], available: show.cmp },
    { id: "st-out", label: "Excel", state: states[4], available: show.out && !!cmp },
  ];

  const page = useRef<HTMLDivElement>(null);
  const backdrop = usePageBackdrop(page);

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

  const scopeStatus = milestone?.scope_status ?? "NONE";

  return (
    <div className="mt-page" ref={page} style={backdrop.minHeight ? { minHeight: backdrop.minHeight } : undefined}>
      <div aria-hidden="true" className="mt-backdrop" style={{ background: backdrop.background }} />
      <Header
        center={<WorkflowNav items={workflow} />}
        right={<ScopeSelector currentRef={milestone?.milestone_code ?? null} tags={scopeStatus === "NONE" ? 0 : ws.tagCount} />}
      />
      <main className="mt-main" id="main">
        {/* The headline belongs to scope intake only; once the scope is locked the page starts with the steps. */}
        <div className="mt-intro">
          {milestone !== undefined && !locked && (
            <h1 className="mt-hero">
              <span className="mt-hero-lead">Trace your MTL data</span>
              <span className="mt-hero-sub">from source to final value</span>
            </h1>
          )}
        </div>

        {ws.loadError && milestone === undefined ? (
          <div className="mt-panel mt-pad mt-load-error">
            <span>{ws.loadError}</span>
            <Link to="/">Start a new tag scope</Link>
          </div>
        ) : milestone === undefined ? null : (
          <>
            {ws.loadError && <div className="mt-error mt-load-banner">{ws.loadError}</div>}
            <ScopeStep ws={ws} />
            {show.src && <SourcesStep ws={ws} />}
            {show.cons && <ConsolidationStep ws={ws} onDownloaded={(f) => showToast(`Downloaded · ${f}`)} />}
            {show.cmp && <ComparisonStep ws={ws} />}
            {show.out && cmp && <ExcelStep cmp={cmp} downloaded={ws.downloaded} onDownload={downloadExcel} />}
          </>
        )}
      </main>
      <Toast message={toast} />
    </div>
  );
}

/**
 * The page background: pure white at the top, then a static white → blue gradient that starts 70px inside the
 * Source documents step (or 100px above the end of the Scope step before it exists) and completes over 380px.
 */
function usePageBackdrop(page: RefObject<HTMLDivElement | null>) {
  const [y, setY] = useState<number | null>(null);
  useLayoutEffect(() => {
    const root = page.current;
    if (!root) return;
    const measure = () => {
      const top = root.getBoundingClientRect().top;
      const src = document.getElementById("st-src");
      const scope = document.getElementById("st-scope");
      const next = src
        ? Math.round(src.getBoundingClientRect().top - top + 70)
        : scope
          ? Math.round(scope.getBoundingClientRect().bottom - top - 100)
          : null;
      setY((prev) => (prev === next ? prev : next));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    const main = root.querySelector("main");
    if (main) ro.observe(main);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  });
  if (y === null) return { background: "transparent", minHeight: undefined };
  return {
    background: `linear-gradient(180deg, #FFFFFF 0, #FFFFFF ${y}px, #2640A6 ${y + 380}px, #2640A6 100%)`,
    minHeight: `${y + 640}px`,
  };
}
