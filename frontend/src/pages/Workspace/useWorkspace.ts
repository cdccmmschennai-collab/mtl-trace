import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../../api/client";
import { openRunForUpload, useWorkingRun } from "../../api/useWorkingRun";
import { prefersReducedMotion } from "../../components/ui";
import { refFromFileName, sha256Hex } from "../../lib/format";
import type {
  Comparison,
  Consolidation,
  MilestoneDetail,
  RunSource,
  ScopeValidationReport,
  SourceType,
} from "../../types/api";

/**
 * Workspace state. Everything shown is derived from what the backend reports for the milestone and its current
 * (latest) run; the only local state is what the user has in hand (a picked file, an in-flight request).
 */

export type ScopePhase =
  | "empty"
  | "selected"
  | "validating"
  | "validated"
  | "invalid"
  | "importing"
  | "imported"
  | "locking"
  | "locked";
export type DocPhase = "processing" | "ok" | "warn" | "unknown" | "failed";
export type ConsPhase = "idle" | "running" | "done" | "stale";
export type CmpPhase = "idle" | "running" | "done";

export interface DocView {
  key: string;
  name: string;
  phase: DocPhase;
  source: RunSource | null; // null while the upload is in flight
}

/** A scope file validated on the "new tag scope" page, handed to the new scope's workspace. */
const pendingScopes = new Map<number, { file: File; ref: string; report: ScopeValidationReport | null; error: string | null }>();
/** Files uploaded in this session, by milestone and SHA-256 — needed to re-submit a document with a chosen type. */
const uploadedFiles = new Map<string, File>();

export const CHECK_COUNT = 4;
let uploadSeq = 0;

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

async function validateOrReport(milestoneId: number, file: File): Promise<ScopeValidationReport> {
  try {
    return await api.validateScope(milestoneId, file);
  } catch (e) {
    if (e instanceof ApiError && e.report) return e.report;
    throw e;
  }
}

function docPhase(s: RunSource): DocPhase {
  if (s.processing_status === "PROCESSED") return "ok";
  if (s.processing_status === "PROCESSED_WITH_WARNINGS") return "warn";
  return s.source_type ? "failed" : "unknown";
}

export function useWorkspace(milestoneId: number | null) {
  const navigate = useNavigate();

  // ---------------------------------------------------------------- milestone
  const [milestone, setMilestone] = useState<MilestoneDetail | null | undefined>(milestoneId ? undefined : null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reloadMilestone = useCallback(async () => {
    if (!milestoneId) return;
    try {
      setMilestone(await api.getMilestone(milestoneId));
    } catch (e) {
      setLoadError(message(e));
    }
  }, [milestoneId]);

  useEffect(() => {
    reloadMilestone();
  }, [reloadMilestone]);

  const scopeStatus = milestone?.scope_status ?? "NONE";
  const locked = scopeStatus === "LOCKED";

  // ---------------------------------------------------------------- scope
  const handoff = milestoneId ? pendingScopes.get(milestoneId) : undefined;
  const [scopeFile, setScopeFile] = useState<File | null>(handoff?.file ?? null);
  const [scopeRef, setScopeRef] = useState(handoff?.ref ?? "");
  const [report, setReport] = useState<ScopeValidationReport | null>(handoff?.report ?? null);
  const [checksShown, setChecksShown] = useState(0);
  const [scopeBusy, setScopeBusy] = useState<null | "validate" | "import" | "lock">(null);
  const [scopeError, setScopeError] = useState<string | null>(handoff?.error ?? null);
  const [confirmLock, setConfirmLock] = useState(false);

  useEffect(() => {
    if (milestoneId) pendingScopes.delete(milestoneId);
  }, [milestoneId]);

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
  if (locked) scopePhase = "locked";
  else if (scopeBusy === "lock") scopePhase = "locking";
  else if (scopeBusy === "import") scopePhase = "importing";
  else if (scopeFile)
    scopePhase =
      scopeBusy === "validate" || (report && checksShown < CHECK_COUNT)
        ? "validating"
        : report
          ? report.valid
            ? "validated"
            : "invalid"
          : "selected";
  else if (scopeStatus === "DRAFT") scopePhase = "imported";
  else scopePhase = "empty";

  const pickScopeFile = (file: File) => {
    setScopeFile(file);
    setReport(null);
    setScopeError(null);
    if (!milestone) setScopeRef(refFromFileName(file.name));
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
      if (milestone) {
        setReport(await validateOrReport(milestone.id, scopeFile));
        return;
      }
      // New tag scope: the scope reference becomes the milestone, then the file is validated against it.
      const ref = scopeRef.trim();
      if (!ref) throw new Error("Enter a scope reference.");
      let created: MilestoneDetail;
      try {
        created = await api.createMilestone({ milestone_code: ref });
      } catch (e) {
        if (e instanceof ApiError && e.status === 409)
          throw new Error(`Scope reference ${ref} already exists. Choose another reference, or open it from the scope menu.`);
        throw e;
      }
      let rep: ScopeValidationReport | null = null;
      let err: string | null = null;
      try {
        rep = await validateOrReport(created.id, scopeFile);
      } catch (e) {
        err = message(e);
      }
      pendingScopes.set(created.id, { file: scopeFile, ref, report: rep, error: err });
      navigate(`/scopes/${created.id}`);
    } catch (e) {
      setScopeError(message(e));
    } finally {
      setScopeBusy(null);
    }
  };

  const importScope = async () => {
    if (!milestone || !scopeFile || scopeBusy) return;
    setScopeBusy("import");
    setScopeError(null);
    try {
      const res = await api.importScope(milestone.id, scopeFile);
      setMilestone(res.milestone);
      setScopeFile(null);
      setReport(null);
    } catch (e) {
      if (e instanceof ApiError && e.report) setReport(e.report);
      setScopeError(message(e));
    } finally {
      setScopeBusy(null);
    }
  };

  const lockScope = async () => {
    if (!milestone || scopeBusy) return;
    setScopeBusy("lock");
    setScopeError(null);
    try {
      setMilestone(await api.lockScope(milestone.id));
      setConfirmLock(false);
    } catch (e) {
      setScopeError(message(e));
    } finally {
      setScopeBusy(null);
    }
  };

  // ---------------------------------------------------------------- sources (current run)
  const { run, setRun, error: runError } = useWorkingRun(milestoneId ?? 0, !!milestoneId && locked);
  const runRef = useRef(run);
  useEffect(() => {
    runRef.current = run;
  }, [run]);

  const [types, setTypes] = useState<SourceType[]>([]);
  useEffect(() => {
    if (locked) api.sourceTypes().then(setTypes, (e) => setLoadError(message(e)));
  }, [locked]);

  const [uploads, setUploads] = useState<{ key: string; name: string }[]>([]);
  const [retyping, setRetyping] = useState<number | null>(null);
  const [srcErrors, setSrcErrors] = useState<string[]>([]);
  const [openDocs, setOpenDocs] = useState<Set<string>>(new Set());

  // Uploads and re-typing run strictly one at a time so that at most one new run is ever opened.
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

  const refreshRun = async (runId: number) => {
    const fresh = await api.getRun(runId);
    runRef.current = fresh;
    setRun(fresh);
    return fresh;
  };

  /** After a failed request, show whatever run the backend now holds as current. */
  const resync = () => {
    const current = runRef.current;
    if (current) refreshRun(current.id).catch(() => undefined);
  };

  const addSources = (files: File[]) => {
    // Never before the working run is known: uploading then could open a run without the current documents.
    if (!milestone || !locked || run === undefined) return;
    const mId = milestone.id;
    const items = files.map((file) => ({ key: `u${++uploadSeq}`, name: file.name, file }));
    setUploads((u) => [...u, ...items.map(({ key, name }) => ({ key, name }))]);
    setSrcErrors([]);
    for (const it of items) {
      enqueue(async () => {
        try {
          // A consolidated run is frozen: openRunForUpload starts a new run carrying its documents forward.
          const target = await openRunForUpload(mId, runRef.current ?? null);
          if (target.id !== runRef.current?.id) runRef.current = target;
          const rs = await api.uploadSource(target.id, it.file, {});
          uploadedFiles.set(`${mId}:${rs.sha256}`, it.file);
          await refreshRun(target.id);
          if (rs.processing_status === "FAILED") openDoc(`s${rs.id}`);
        } catch (e) {
          setSrcErrors((errs) => [...errs, `${it.name}: ${message(e)}`]);
          resync();
        } finally {
          setUploads((u) => u.filter((x) => x.key !== it.key));
        }
      }).then(() => reloadMilestone());
    }
  };

  const hasFileFor = (rs: RunSource) => !!milestone && uploadedFiles.has(`${milestone.id}:${rs.sha256}`);

  /**
   * Submit an unrecognised document again with the type the user chose. The backend refuses the same file twice
   * in one run, so a new run is opened from the current one (base_run_id carries every processed document
   * forward); the current run is left unchanged. Documents still awaiting a type are re-submitted as they were
   * when their files are at hand, so they stay visible.
   */
  const retype = (rs: RunSource, type: string, picked?: File) => {
    if (!milestone || run === undefined) return;
    const mId = milestone.id;
    const key = `${mId}:${rs.sha256}`;
    setSrcErrors([]);
    enqueue(async () => {
      const file = picked ?? uploadedFiles.get(key);
      if (!file) return;
      if (picked) {
        const digest = await sha256Hex(picked);
        const same = digest ? digest === rs.sha256 : picked.name === rs.original_filename && picked.size === rs.file_size;
        if (!same) {
          setSrcErrors([`${picked.name} is not the same file as ${rs.original_filename}. Choose the original file.`]);
          return;
        }
      }
      const current = runRef.current;
      if (!current) return;
      setRetyping(rs.id);
      try {
        const next = await api.createRun(mId, undefined, current.id);
        runRef.current = next;
        const up = await api.uploadSource(next.id, file, { source_type: type });
        uploadedFiles.set(key, file);
        for (const other of current.sources) {
          if (other.id === rs.id || other.processing_status !== "FAILED") continue;
          const f = uploadedFiles.get(`${mId}:${other.sha256}`);
          if (f) {
            const again = await api.uploadSource(next.id, f, other.source_type ? { source_type: other.source_type } : {}).catch(() => null);
            if (again?.processing_status === "FAILED") openDoc(`s${again.id}`);
          }
        }
        await refreshRun(next.id);
        if (up.processing_status === "FAILED") openDoc(`s${up.id}`);
      } catch (e) {
        setSrcErrors([`${rs.original_filename}: ${message(e)}`]);
        resync();
      } finally {
        setRetyping(null);
      }
    }).then(() => reloadMilestone());
  };

  const docs: DocView[] = [
    ...(run?.sources ?? []).map((s) => ({
      key: `s${s.id}`,
      name: s.original_filename,
      phase: retyping === s.id ? ("processing" as const) : docPhase(s),
      source: s,
    })),
    ...uploads.map((u) => ({ key: u.key, name: u.name, phase: "processing" as const, source: null })),
  ];
  const usable = (run?.sources ?? []).filter((s) => s.processing_status !== "FAILED" && s.source_type);
  const excluded = (run?.sources ?? []).filter((s) => !usable.includes(s));
  const processing = uploads.length > 0 || retyping !== null;
  const unknownCount = docs.filter((d) => d.phase === "unknown").length;
  const docsReady = locked && usable.length > 0 && !processing;

  // ---------------------------------------------------------------- consolidation & comparison (current run only)
  const [cons, setCons] = useState<Consolidation | null>(null);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [resultsFor, setResultsFor] = useState<number | null>(null);
  const [consBusy, setConsBusy] = useState(false);
  const [cmpBusy, setCmpBusy] = useState(false);
  const [consError, setConsError] = useState<string | null>(null);
  const [cmpError, setCmpError] = useState<string | null>(null);
  const [downloadedFor, setDownloadedFor] = useState<number | null>(null);

  const runId = run?.id;
  const isConsolidated = run?.status === "CONSOLIDATED";
  useEffect(() => {
    if (!runId || !isConsolidated) return;
    let off = false;
    Promise.all([api.getConsolidation(runId), api.getComparison(runId)]).then(
      ([c, r]) => {
        if (off) return;
        setCons(c);
        setCmp(r);
        setResultsFor(runId);
      },
      (e) => !off && setLoadError(message(e)),
    );
    return () => {
      off = true;
    };
  }, [runId, isConsolidated]);

  // Results are only ever shown for the run they belong to — never a previous run's.
  const consNow = isConsolidated && cons?.run_id === runId ? cons : null;
  const cmpNow = isConsolidated && cmp?.run_id === runId ? cmp : null;
  const stale = !isConsolidated && !!milestone?.runs.some((r) => r.status === "CONSOLIDATED");

  const consolidate = async () => {
    if (!run || consBusy || processing) return;
    setConsBusy(true);
    setConsError(null);
    try {
      setCons(await api.consolidate(run.id));
      await refreshRun(run.id);
      reloadMilestone();
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
      reloadMilestone();
    } catch (e) {
      setCmpError(message(e));
    } finally {
      setCmpBusy(false);
    }
  };

  const consPhase: ConsPhase = consNow ? "done" : consBusy ? "running" : stale ? "stale" : "idle";
  const cmpPhase: CmpPhase = cmpNow ? "done" : cmpBusy ? "running" : "idle";
  const downloaded = !!cmpNow && downloadedFor === cmpNow.run_id;
  const markDownloaded = () => cmpNow && setDownloadedFor(cmpNow.run_id);

  // ---------------------------------------------------------------- readiness & reveal
  const ready =
    milestone !== undefined && (!locked || run !== undefined) && (!isConsolidated || resultsFor === runId || !!consNow);

  const show = {
    src: locked,
    cons: locked && usable.length > 0 && (!processing || isConsolidated || stale),
    cmp: !!consNow,
    out: !!cmpNow,
  };

  const tagCount =
    scopeStatus !== "NONE" ? milestone?.tag_count ?? 0 : report?.valid ? report.tag_count : 0;

  return {
    milestone,
    loadError: loadError ?? runError,
    ready,
    locked,
    tagCount,
    // scope
    scopePhase,
    scopeFile,
    scopeRef,
    setScopeRef,
    report,
    checksShown,
    scopeError,
    confirmLock,
    setConfirmLock,
    pickScopeFile,
    clearScopeFile,
    validateScope,
    importScope,
    lockScope,
    // sources
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
    hasFileFor,
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
    markDownloaded,
    show,
  };
}

export type Workspace = ReturnType<typeof useWorkspace>;
