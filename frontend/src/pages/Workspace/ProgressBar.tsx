import type { ReactNode } from "react";
import type { StepState } from "../../components/ui";

export interface NextAction {
  label: string;
  icon: ReactNode;
  onClick: () => void;
  busy?: boolean;
}

const LABELS = ["Scope", "Sources", "Consolidate", "Compare", "Excel"];

/** Workflow status (not tab navigation) and the single next action. */
export function ProgressBar({ states, next }: { states: StepState[]; next: NextAction }) {
  return (
    <div className="mt-progress">
      <div className="mt-progress-inner">
        <div role="list" aria-label="Workflow progress" className="mt-trace">
          {LABELS.map((label, i) => {
            const s = states[i];
            return (
              <div role="listitem" key={label} className={`mt-trace-item is-${s}`} aria-current={s === "active" ? "step" : undefined}>
                <span className="mt-trace-label">{label}</span>
                <span className="mt-trace-track">
                  <span className="mt-trace-dot" />
                  <span className="mt-trace-line" style={{ opacity: i === LABELS.length - 1 ? 0 : 1 }} />
                </span>
              </div>
            );
          })}
        </div>
        <button type="button" className="btn btn-primary btn-next" onClick={next.onClick} aria-busy={next.busy || undefined}>
          <span className="btn-next-lead">Next</span>
          <span>{next.label}</span>
          {next.icon}
        </button>
      </div>
    </div>
  );
}
