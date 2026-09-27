import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { ChevronDown, History, Plus, Search } from "../../components/icons";
import { nf } from "../../lib/format";
import { scopeState } from "../../lib/scopeState";
import type { MilestoneSummary } from "../../types/api";

/** Header control: the current scope reference and tag count; opens the list of scopes. */
export function ScopeSelector({ currentRef, tags }: { currentRef: string | null; tags: number }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [scopes, setScopes] = useState<MilestoneSummary[] | null>(null);
  const [compared, setCompared] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Load on open; for consolidated scopes, ask whether the comparison workbook exists ("Excel ready").
  useEffect(() => {
    if (!open) return;
    let off = false;
    api.listMilestones().then(
      (list) => {
        if (off) return;
        setScopes(list);
        setError(null);
        const consolidated = list.filter((m) => m.latest_run?.status === "CONSOLIDATED");
        Promise.all(consolidated.map((m) => api.getComparison(m.latest_run!.id).then((c) => (c ? m.id : null), () => null))).then(
          (ids) => !off && setCompared(new Set(ids.filter((x): x is number => x !== null))),
        );
      },
      (e: Error) => !off && setError(e.message),
    );
    return () => {
      off = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const Q = q.trim().toUpperCase();
  const rows = (scopes ?? [])
    .map((m) => ({
      m,
      state: scopeState({
        scopeStatus: m.scope_status,
        hasSources: !!m.latest_run && m.latest_run.status !== "CREATED",
        consolidated: m.latest_run?.status === "CONSOLIDATED",
        compared: compared.has(m.id),
      }).label,
    }))
    .filter((r) => !Q || r.m.milestone_code.toUpperCase().includes(Q) || r.state.toUpperCase().includes(Q));

  const go = (to: string) => {
    setOpen(false);
    navigate(to);
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="mt-selector" ref={root}>
      <button
        type="button"
        className="mt-selector-btn"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="mt-selector-ref">{currentRef ?? "NEW TAG SCOPE"}</span>
        <span className="mt-selector-tags">{tags ? `${nf(tags)} tags` : "—"}</span>
        <ChevronDown size={14} className="mt-faint" />
      </button>
      {open && (
        <div className="mt-menu mt-in-fast" role="menu">
          <label className="mt-menu-search">
            <Search className="mt-faint" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search scopes" aria-label="Search scopes" autoFocus />
          </label>
          {error && <div className="mt-menu-empty">{error}</div>}
          {scopes === null && !error && <div className="mt-menu-empty">Loading scopes…</div>}
          {scopes !== null && rows.length === 0 && <div className="mt-menu-empty">No scopes match.</div>}
          <div className="mt-menu-list">
            {rows.map(({ m, state }) => (
              <button key={m.id} type="button" role="menuitem" className="mt-menu-item" onClick={() => go(`/scopes/${m.id}`)}>
                <span className="mono mt-menu-ref">{m.milestone_code}</span>
                <span className="mt-menu-state">{state}</span>
              </button>
            ))}
          </div>
          <div className="mt-menu-divider" />
          <Link
            role="menuitem"
            className="mt-menu-item mt-menu-link"
            to={currentRef ? `/traceability?q=${encodeURIComponent(currentRef)}` : "/traceability"}
            onClick={() => setOpen(false)}
          >
            <History size={15} /> View traceability history
          </Link>
          <button type="button" role="menuitem" className="mt-menu-item mt-menu-new" onClick={() => go("/")}>
            <Plus /> New tag scope
          </button>
        </div>
      )}
    </div>
  );
}
