import { useCallback, useEffect, useState } from "react";
import type { Run } from "../types/api";
import { api } from "./client";

/**
 * The milestone's current source set. Processing runs remain in the backend (source immutability, a frozen
 * consolidated dataset) but are not a user concept: the UI always works on the latest run.
 * `run` is undefined while loading and null when no document has been uploaded yet.
 */
export function useWorkingRun(milestoneId: number, enabled: boolean) {
  const [run, setRun] = useState<Run | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(
    () =>
      api.listRuns(milestoneId).then(
        (rs) => setRun(rs[0] ?? null),           // newest first
        (e: Error) => setError(e.message),
      ),
    [milestoneId],
  );

  useEffect(() => {
    if (enabled) reload();
  }, [enabled, reload]);

  return { run, setRun, reload, error, setError };
}

/**
 * A run that can accept a new document. A consolidated run is frozen, so adding a document afterwards starts a
 * new run carrying the current documents forward; the user then consolidates again.
 */
export async function openRunForUpload(milestoneId: number, current: Run | null): Promise<Run> {
  if (current && current.status !== "CONSOLIDATED") return current;
  return api.createRun(milestoneId, undefined, current?.id ?? null);
}
