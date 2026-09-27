import { CircleCheck, Dot, GitCompareArrows, Spinner } from "../../components/icons";
import { ErrorLine, Status, Step, type StepState } from "../../components/ui";
import { fmtWhen, nf, plural } from "../../lib/format";
import type { Workspace } from "./useWorkspace";

export function ComparisonStep({ ws, state }: { ws: Workspace; state: StepState }) {
  const { cmpPhase: phase, cons, cmp } = ws;
  if (!cons) return null;

  const status =
    phase === "done" ? (
      <Status tone="match" kind="done">Complete</Status>
    ) : phase === "running" ? (
      <Status tone="accent" kind="busy">Comparing</Status>
    ) : (
      <Status tone="accent">Ready</Status>
    );

  // Priority order is the backend's: the comparison's ranks once compared, the consolidation's order before.
  const priority = cmp
    ? [...cmp.source_types].sort((a, b) => a.rank - b.rank)
    : cons.source_types.map((t, i) => ({ ...t, rank: i + 1 }));
  const included = cons.documents.filter((d) => d.included).length;
  const running = phase === "running";

  return (
    <Step id="st-cmp" title="Compare source values" state={state} status={status}>
      {phase !== "done" && (
        <div className="mt-panel mt-step-content mt-in-mid">
          <div className="mt-split">
            <div className="mt-split-main">
              <span className="mt-panel-label">Attributes</span>
              {cons.attributes.map((a) => (
                <div key={a.code} className="mt-attr-row">
                  <span className={`mt-flex ${running ? "tone-accent" : "mt-faint-2"}`}>
                    {running ? <Spinner size={14} /> : <Dot size={14} />}
                  </span>
                  <span className="mono mt-attr-label">{a.label}</span>
                  <span className={`mt-attr-track${running ? " is-running" : ""}`} />
                </div>
              ))}
            </div>
            <div className="mt-split-side">
              <span className="mt-panel-label">Source priority</span>
              {priority.map((p) => (
                <div key={p.code} className="mt-priority-row">
                  <span className="mono mt-priority-rank">{p.rank}</span>
                  <span>{p.label}</span>
                </div>
              ))}
            </div>
          </div>
          {phase === "idle" && (
            <div className="mt-panel-section mt-pad-14">
              <button type="button" className="btn btn-primary" onClick={ws.compare}>
                <GitCompareArrows /> Compare sources
              </button>
            </div>
          )}
          {ws.cmpError && (
            <div className="mt-panel-section mt-pad-14">
              <ErrorLine message={ws.cmpError} />
            </div>
          )}
        </div>
      )}
      {phase === "done" && cmp && (
        <div className="mt-panel mt-summary mt-step-content mt-in-mid">
          <CircleCheck size={20} className="tone-match pop mt-summary-icon" />
          <div className="mt-col">
            <span className="mt-done-label">Comparison complete</span>
            <span className="mt-done-sub">
              {plural(cmp.attributes.length, "attribute")} × <span className="tnum">{nf(cmp.scope_tag_count)}</span> tags across{" "}
              {plural(included, "source document")} <span className="mono mt-when">· {fmtWhen(cmp.compared_at)}</span>
            </span>
          </div>
        </div>
      )}
    </Step>
  );
}
