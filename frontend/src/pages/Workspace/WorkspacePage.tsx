import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { Header, Toast, scrollToStep, useToast, type StepState } from "../../components/ui";
import { nf } from "../../lib/format";
import { ComparisonStep } from "./ComparisonStep";
import { ConsolidationStep } from "./ConsolidationStep";
import { ExcelStep } from "./ExcelStep";
import { ScopeStep } from "./ScopeStep";
import { SourcesStep } from "./SourcesStep";
import { useWorkspace } from "./useWorkspace";
import { WorkflowNav, type WorkflowItem } from "./WorkflowNav";

/** The tool's single page: scope → source documents → consolidate → compare → Excel. */
export function Workspace() {
  const ws = useWorkspace();
  const { toast, show: showToast } = useToast();
  const { milestone, hasSession, show, consPhase, cmpPhase, cmp } = ws;

  const consDone = consPhase === "done";
  const cmpDone = cmpPhase === "done";

  const states: StepState[] = [
    hasSession ? "done" : "active",
    !hasSession ? "waiting" : ws.docsReady ? "done" : "active",
    !ws.docsReady ? "waiting" : consDone ? "done" : "active",
    !consDone ? "waiting" : cmpDone ? "done" : "active",
    !cmpDone ? "waiting" : ws.downloaded ? "done" : "active",
  ];

  const onExcelSaved = (msg: string) => {
    ws.markDownloaded();
    showToast(msg);
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

  return (
    <div className="mt-page" ref={page} style={backdrop.minHeight ? { minHeight: backdrop.minHeight } : undefined}>
      <div aria-hidden="true" className="mt-backdrop" style={{ background: backdrop.background }} />
      <Header
        center={<WorkflowNav items={workflow} />}
        right={
          hasSession && milestone ? (
            <span className="mt-scope-chip" title={milestone.scope_file_name ?? undefined}>
              <span className="mt-scope-chip-name">{milestone.scope_file_name}</span>
              <span className="mt-scope-chip-tags">{nf(milestone.tag_count)} tags</span>
            </span>
          ) : null
        }
      />
      <main className="mt-main" id="main">
        {/* The headline belongs to scope intake only; once a scope is loaded the page starts with the steps. */}
        <div className="mt-intro">
          {milestone !== undefined && !hasSession && (
            <h1 className="mt-hero">
              <span className="mt-hero-lead">Trace your MTL data</span>
              <span className="mt-hero-sub">from source to final value</span>
            </h1>
          )}
        </div>

        {ws.loadError && <div className="mt-error mt-load-banner">{ws.loadError}</div>}
        {milestone !== undefined && (
          <>
            <ScopeStep ws={ws} />
            {show.src && <SourcesStep ws={ws} />}
            {show.cons && <ConsolidationStep ws={ws} onSaved={showToast} />}
            {show.cmp && <ComparisonStep ws={ws} />}
            {show.out && cmp && <ExcelStep cmp={cmp} downloaded={ws.downloaded} onSaved={onExcelSaved} />}
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
