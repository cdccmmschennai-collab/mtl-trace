import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api/client";
import { prefersReducedMotion } from "../../components/ui";
import type { Comparison, Consolidation, MilestoneDetail, Run, RunSource, ScopeValidationReport, SourceType } from "../../types/api";

/**
 * Workspace state for the tool's one session: scope → documents → consolidate → compare → Excel. There is no
 * history: loading a new scope replaces everything. Everything shown is derived from what the backend reports;
 * the only local state is what the user has in hand (a picked file, an in-flight request).
 */

export type ScopePhase = "empty" | "selected" | "validating" | "validated" | "invalid" | "starting" | "loaded";
export type DocPhase = "processing" | "ok" | "warn" | "unknown" | "failed";
export type ConsPhase = "idle" | "running" | "done" | "stale";
export type CmpPhase = "idle" | "running" | "done";

export interface DocView {
  key: string;
  name: string;
  phase: DocPhase;
  source: RunSource | null; // null while the upload is in flight
}

export const CHECK_COUNT = 4;
let uploadSeq = 0;

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

function docPhase(s: RunSource): DocPhase {
  if (s.processing_status === "PROCESSED") return "ok";
  if (s.processing_status === "PROCESSED_WITH_WARNINGS") return "warn";
  return s.source_type ? "failed" : "unknown";
}

export function useWorkspace() {
  // ---------------------------------------------------------------- session (scope + its one run)
  const [milestone, setMilestone] = useState<MilestoneDetail | null | undefined>(undefined);
  const [run, setRun] = useState<Run | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const runRef = useRef<Run | null>(null);
  runRef.current = run;

  // Results belong to the current source set; any change to it discards them (backend and here).
  const [cons, setCons] = useState<Consolidation | null>(null);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [hadResults, setHadResults] = useState(false);
  const clearResults = () => {
    setCons(null);
    setCmp(null);
    setDownloaded(false);
  };

  const loadResults = useCallback(async (r: Run) => {
    if (r.status !== "CONSOLIDATED") return;
    const [c, m] = await Promise.all([api.getConsolidation(r.id), api.getComparison(r.id)]);
    setCons(c);
    setCmp(m);
    setHadResults(true);
  }, []);

  useEffect(() => {
    api.getSession().then(
      (s) => {
        setMilestone(s?.milestone ?? null);
        setRun(s?.run ?? null);
        if (s) loadResults(s.run).catch((e) => setLoadError(message(e)));
      },
      (e) => {
        setMilestone(null);
        setLoadError(message(e));
      },
    );
  }, [loadResults]);

  const hasSession = !!milestone && !!run;

  const [types, setTypes] = useState<SourceType[]>([]);
  useEffect(() => {
    if (hasSession && types.length === 0) api.sourceTypes().then(setTypes, (e) => setLoadError(message(e)));
  }, [hasSession, types.length]);

  // ---------------------------------------------------------------- scope
  const [scopeFile, setScopeFile] = useState<File | null>(null);
  const [report, setReport] = useState<ScopeValidationReport | null>(null);
  const [checksShown, setChecksShown] = useState(0);
  const [scopeBusy, setScopeBusy] = useState<null | "validate" | "start">(null);
  const [scopeError, setScopeError] = useState<string | null>(null);

  // The four checks come back in one response; reveal them one after another.
  useEffect(() => {
    if (!report || prefersReducedMotion()) {
      setChecksShown(report ? CHECK_COUNT : 0);
      return;
    }
    setChecksShown(0);
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      setChecksShown(n);
      if (n >= CHECK_COUNT) window.clearInterval(id);
    }, 180);
    return () => window.clearInterval(id);
  }, [report]);

  let scopePhase: ScopePhase;
  if (scopeBusy === "start") scopePhase = "starting";
  else if (scopeFile)
    scopePhase =
      scopeBusy === "validate" || (report && checksShown < CHECK_COUNT)
        ? "validating"
        : report
          ? report.valid
            ? "validated"
            : "invalid"
          : "selected";
  else scopePhase = hasSession ? "loaded" : "empty";

  const pickScopeFile = (file: File) => {
    setScopeFile(file);
    setReport(null);
    setScopeError(null);
  };

  const clearScopeFile = () => {
    setScopeFile(null);
    setReport(null);
    setScopeError(null);
  };

  const validateScope = async () => {
    if (!scopeFile || scopeBusy) return;
    setScopeBusy("validate");
    setScopeError(null);
    setReport(null);
    try {
      setReport(await api.validateScope(scopeFile));
    } catch (e) {
      setScopeError(message(e));
    } finally {
      setScopeBusy(null);
    }
  };

  /** Start the session on the validated scope. Replaces any current scope, documents and results. */
  const startSession = async () => {
    if (!scopeFile || scopeBusy || processing) return;
    setScopeBusy("start");
    setScopeError(null);
    try {
      const s = await api.startSession(scopeFile);
      setMilestone(s.milestone);
      setRun(s.run);
      setScopeFile(null);
      setReport(null);
      clearResults();
      setHadResults(false);
      setUploads([]);
      setSrcErrors([]);
      setOpenDocs(new Set());
      setConsError(null);
      setCmpError(null);
    } catch (e) {
      if (e instanceof ApiError && e.report) setReport(e.report);
      setScopeError(message(e));
    } finally {
      setScopeBusy(null);
    }
  };

  // ---------------------------------------------------------------- documents
  const [uploads, setUploads] = useState<{ key: string; name: string }[]>([]);
  const [busySource, setBusySource] = useState<number | null>(null);
  const [srcErrors, setSrcErrors] = useState<string[]>([]);
  const [openDocs, setOpenDocs] = useState<Set<string>>(new Set());

  // Document changes run one at a time, in order.
  const queue = useRef<Promise<void>>(Promise.resolve());
  const enqueue = (job: () => Promise<void>) => {
    queue.current = queue.current.then(job, job);
    return queue.current;
  };

  const openDoc = (key: string) => setOpenDocs((s) => new Set(s).add(key));
  const toggleDoc = (key: string) =>
    setOpenDocs((s) => {
      const n = new Set(s);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  const refreshRun = async () => {
    const current = runRef.current;
    if (!current) return null;
    const fresh = await api.getRun(current.id);
    runRef.current = fresh;
    setRun(fresh);
    return fresh;
  };

  /**
   * Run a change to the source set. The backend discards results built on the previous set; a refused change
   * (e.g. the same file twice) leaves them, so they are read back rather than assumed gone.
   */
  const changeSources = (label: string, job: (runId: number) => Promise<void>) =>
    enqueue(async () => {
      const current = runRef.current;
      if (!current) return;
      try {
        await job(current.id);
      } catch (e) {
        setSrcErrors((errs) => [...errs, `${label}: ${message(e)}`]);
      } finally {
        try {
          const fresh = await refreshRun();
          if (fresh?.status === "CONSOLIDATED") await loadResults(fresh);
          else clearResults();
        } catch (e) {
          setLoadError(message(e));
        }
      }
    });

  const addSources = (files: File[]) => {
    if (!run) return;
    const items = files.map((file) => ({ key: `u${++uploadSeq}`, name: file.name, file }));
    setUploads((u) => [...u, ...items.map(({ key, name }) => ({ key, name }))]);
    setSrcErrors([]);
    for (const it of items) {
      changeSources(it.name, async (runId) => {
        try {
          const rs = await api.uploadSource(runId, it.file);
          if (rs.processing_status === "FAILED") openDoc(`s${rs.id}`);
        } finally {
          setUploads((u) => u.filter((x) => x.key !== it.key));
        }
      });
    }
  };

  /** Process a document whose type was not detected again, as the type the user chose. */
  const retype = (rs: RunSource, type: string) => {
    setSrcErrors([]);
    setBusySource(rs.id);
    changeSources(rs.original_filename, async (runId) => {
      try {
        const next = await api.retypeSource(runId, rs.id, type);
        if (next.processing_status === "FAILED") openDoc(`s${next.id}`);
      } finally {
        setBusySource(null);
      }
    });
  };

  const removeSource = (rs: RunSource) => {
    setSrcErrors([]);
    setBusySource(rs.id);
    changeSources(rs.original_filename, async (runId) => {
      try {
        await api.removeSource(runId, rs.id);
      } finally {
        setBusySource(null);
      }
    });
  };

  const docs: DocView[] = [
    ...(run?.sources ?? []).map((s) => ({
      key: `s${s.id}`,
      name: s.original_filename,
      phase: busySource === s.id ? ("processing" as const) : docPhase(s),
      source: s,
    })),
    ...uploads.map((u) => ({ key: u.key, name: u.name, phase: "processing" as const, source: null })),
  ];
  const usable = (run?.sources ?? []).filter((s) => s.processing_status !== "FAILED" && s.source_type);
  const excluded = (run?.sources ?? []).filter((s) => !usable.includes(s));
  const processing = uploads.length > 0 || busySource !== null;
  const unknownCount = docs.filter((d) => d.phase === "unknown").length;
  const docsReady = hasSession && usable.length > 0 && !processing;

  // ---------------------------------------------------------------- consolidation & comparison
  const [consBusy, setConsBusy] = useState(false);
  const [cmpBusy, setCmpBusy] = useState(false);
  const [consError, setConsError] = useState<string | null>(null);
  const [cmpError, setCmpError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);

  const consolidate = async () => {
    if (!run || consBusy || processing) return;
    setConsBusy(true);
    setConsError(null);
    setCmpError(null);
    try {
      setCons(await api.consolidate(run.id));
      setHadResults(true);
      await refreshRun();
    } catch (e) {
      setConsError(message(e));
    } finally {
      setConsBusy(false);
    }
  };

  const compare = async () => {
    if (!run || cmpBusy) return;
    setCmpBusy(true);
    setCmpError(null);
    try {
      setCmp(await api.compare(run.id));
    } catch (e) {
      setCmpError(message(e));
    } finally {
      setCmpBusy(false);
    }
  };

  const consolidated = run?.status === "CONSOLIDATED";
  const consNow = consolidated && cons?.run_id === run?.id ? cons : null;
  const cmpNow = consNow && cmp?.run_id === run?.id ? cmp : null;
  const consPhase: ConsPhase = consNow ? "done" : consBusy ? "running" : hadResults ? "stale" : "idle";
  const cmpPhase: CmpPhase = cmpNow ? "done" : cmpBusy ? "running" : "idle";

  // ---------------------------------------------------------------- reveal
  const ready = milestone !== undefined && (!consolidated || !!consNow);

  const show = {
    src: hasSession,
    cons: hasSession && usable.length > 0 && (!processing || consPhase === "stale"),
    cmp: !!consNow,
    out: !!cmpNow,
  };

  const tagCount = hasSession ? milestone!.tag_count : report?.valid ? report.tag_count : 0;

  return {
    milestone,
    hasSession,
    loadError,
    ready,
    tagCount,
    // scope
    scopePhase,
    scopeFile,
    report,
    checksShown,
    scopeError,
    pickScopeFile,
    clearScopeFile,
    validateScope,
    startSession,
    // documents
    run,
    types,
    docs,
    usable,
    excluded,
    processing,
    unknownCount,
    docsReady,
    srcErrors,
    openDocs,
    toggleDoc,
    addSources,
    retype,
    removeSource,
    // consolidation / comparison / output
    cons: consNow,
    cmp: cmpNow,
    consPhase,
    cmpPhase,
    consError,
    cmpError,
    consolidate,
    compare,
    downloaded,
    markDownloaded: () => setDownloaded(true),
    show,
  };
}

export type Workspace = ReturnType<typeof useWorkspace>;
