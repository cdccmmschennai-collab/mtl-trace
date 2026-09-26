import { AlertCircle, AlertTriangle } from "lucide-react";
import type { Issue } from "../types/api";

export function IssueList({ title, issues }: { title: string; issues: Issue[] }) {
  if (issues.length === 0) return null;
  return (
    <>
      <h4>{title}</h4>
      <ul className="issues">
        {issues.map((i, n) => {
          const isErr = i.severity.toLowerCase() === "error";
          return (
            <li key={n} className={`issue issue-${i.severity.toLowerCase()}`}>
              {isErr ? (
                <AlertCircle size={16} style={{ color: "var(--err)", marginTop: 2, flexShrink: 0 }} />
              ) : (
                <AlertTriangle size={16} style={{ color: "var(--warn)", marginTop: 2, flexShrink: 0 }} />
              )}
              <div>
                <span className="issue-code">{i.code}</span>
                <span>{i.message}</span>
                {i.rows.length > 0 && (
                  <span className="muted">
                    {" "}
                    Row{i.rows.length > 1 ? "s" : ""} {formatRows(i.rows)}
                    {i.column ? ` (column ${i.column})` : ""}.
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function formatRows(rows: number[], max = 15): string {
  const shown = rows.slice(0, max).join(", ");
  return rows.length > max ? `${shown} … +${rows.length - max} more` : shown;
}
