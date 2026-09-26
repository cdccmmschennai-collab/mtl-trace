"""Comparison workflow (Phase 1D): a consolidated run's canonical dataset → comparison results → the
comparison workbook.

Reads canonical cells only (plus the candidate values of duplicate cells, from the source records they
anchor) — never a source file. Compares each run once, under the rules version stamped on the run; the
results and the workbook are then immutable. A revised source set is a new run.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert, select

from backend.comparison.engine import ComparisonInput, Reason, SourceValue, Status, compare_all
from backend.comparison.rules import Rules, RulesError, load_rules
from backend.config import REPO_ROOT
from backend.domain.sources import ATTRIBUTE_INFO, ATTRIBUTES, SOURCE_TYPES
from backend.output.comparison_workbook import WorkbookModel, build_workbook
from backend.services.consolidation import OutputView, sheet_shells, source_columns, source_workbook_model
from backend.services.milestones import ConflictError, NotFoundError
from backend.storage.database import Database
from backend.storage.files import FileStore
from backend.storage.models import (
    CanonicalCell,
    ComparisonResult,
    Milestone,
    MilestoneTag,
    OutputArtifact,
    ProcessingRun,
    RunComparison,
    RunConsolidation,
    SourceRecord,
)

log = logging.getLogger(__name__)

COMPARISON_KIND = "COMPARISON_WORKBOOK"
STATES = [s.value for s in Status]
RULES_DIR = REPO_ROOT / "rules"


@dataclass(frozen=True)
class ComparisonView:
    run_id: int
    run_number: int
    milestone_id: int
    milestone_code: str
    rules_version: str
    compared_at: datetime
    scope_tag_count: int
    source_types: list[dict]                 # priority order: {code, label, rank}
    totals: dict[str, int]                   # MATCH / MISMATCH / REVIEW REQUIRED
    no_source_value: int                     # tag × attribute rows left blank (no verdict)
    attributes: list[dict]                   # per attribute: counts, reasons, providing sources
    workbook: dict
    output: OutputView | None


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


class ComparisonService:
    def __init__(self, db: Database, files: FileStore, rules_dir: Path = RULES_DIR):
        self.db = db
        self.files = files
        self.rules_dir = rules_dir

    def rules(self, version: str) -> Rules:
        path = self.rules_dir / f"{version}.yaml"
        if not path.exists():
            raise ConflictError(f"Comparison rules '{version}' ({path.name}) are not available.")
        return load_rules(path)

    # ---- compare

    def compare(self, run_id: int) -> ComparisonView:
        written: list[str] = []
        try:
            counts = self._compare(run_id, written)
        except BaseException:
            for path in written:                       # transaction rolled back: leave no orphaned artifact
                self.files.resolve(path).unlink(missing_ok=True)
            raise
        log.info("Compared run id=%s: %s", run_id, counts)
        return self.get_comparison(run_id)

    def _compare(self, run_id: int, written: list[str]) -> dict:
        with self.db.session() as s:
            run = self._run(s, run_id)
            cons = s.scalar(select(RunConsolidation).where(RunConsolidation.run_id == run.id))
            if cons is None:
                raise ConflictError(f"Run {run.run_number} has not been consolidated yet. Consolidate it first; "
                                    f"comparison always runs on the consolidated dataset.")
            if s.scalar(select(RunComparison.id).where(RunComparison.run_id == run.id)) is not None:
                raise ConflictError(f"Run {run.run_number} has already been compared. Its results and workbook are "
                                    f"preserved unchanged; to compare a revised source set, create a new run.")
            rules = self.rules(run.rules_version)
            try:
                source_types = sorted(json.loads(cons.source_types), key=rules.rank)
            except RulesError as exc:
                raise ConflictError(str(exc)) from exc
            m = s.get(Milestone, run.milestone_id)
            tags = s.scalars(select(MilestoneTag).where(MilestoneTag.milestone_id == m.id)
                             .order_by(MilestoneTag.scope_order)).all()

            cells = s.execute(select(CanonicalCell.milestone_tag_id, CanonicalCell.attribute, CanonicalCell.source_type,
                                     CanonicalCell.state, CanonicalCell.raw_value, CanonicalCell.normalized_value,
                                     CanonicalCell.source_record_ids)
                              .where(CanonicalCell.run_id == run.id)).all()
            dup_ids = {rid for c in cells if c.state == "CONFLICTING_DUPLICATE" for rid in json.loads(c.source_record_ids)}
            recs = {r.id: r for r in s.scalars(select(SourceRecord).where(SourceRecord.id.in_(dup_ids)))} if dup_ids else {}

            by_key: dict[tuple[int, str], list[SourceValue]] = {}
            snapshot: dict[tuple[int, str, str], tuple] = {}
            for c in cells:
                ids = json.loads(c.source_record_ids) if c.state == "CONFLICTING_DUPLICATE" else []
                by_key.setdefault((c.milestone_tag_id, c.attribute), []).append(SourceValue(
                    c.source_type, c.state, c.normalized_value, tuple(recs[i].normalized_value for i in ids)))
                snapshot[(c.milestone_tag_id, c.attribute, c.source_type)] = (
                    c.state, c.raw_value, [(recs[i].raw_value, json.loads(recs[i].source_location)) for i in ids])

            items = [ComparisonInput(t.id, t.tag_number, a.value, tuple(by_key.get((t.id, a.value), ())))
                     for a in ATTRIBUTES for t in tags]
            results = compare_all(items, rules, {st: SOURCE_TYPES[st].label for st in source_types})

            s.execute(insert(ComparisonResult), [
                {"run_id": run.id, "milestone_tag_id": r.milestone_tag_id, "attribute": r.attribute,
                 "status": r.status.value if r.status else None, "final_value": r.final_value,
                 "final_source_type": r.final_source, "reason": r.reason.value, "remarks": r.remarks,
                 "compared_sources": json.dumps(list(r.compared_sources))} for r in results])
            summary = self._summary(results, cells, source_types)
            s.add(RunComparison(run_id=run.id, rules_version=rules.version, source_types=json.dumps(source_types),
                                summary=json.dumps(summary)))

            model = source_workbook_model(tags, source_types, snapshot,
                                          f"{m.milestone_code} run {run.run_number} — comparison (rules {rules.version})")
            by_attr: dict[str, list] = {a.value: [] for a in ATTRIBUTES}
            for r in results:                           # results are attribute-major, scope order within
                by_attr[r.attribute].append(r)
            model.statuses = {a: [r.status.value if r.status else None for r in rs] for a, rs in by_attr.items()}
            model.finals = {a: [r.final_value for r in rs] for a, rs in by_attr.items()}
            model.remarks = {a: [r.remarks for r in rs] for a, rs in by_attr.items()}
            data = build_workbook(model)

            name = f"MTL-DATA MISMATCH COMPARISION - {m.milestone_code} - RUN-{run.run_number:03d}.xlsx"
            path, digest = self.files.store_generated(m.milestone_code, "comparison", run.run_number,
                                                      "comparison.xlsx", data)
            written.append(path)
            s.add(OutputArtifact(run_id=run.id, kind=COMPARISON_KIND, file_name=name, stored_path=path,
                                 sha256=digest, file_size=len(data)))
            return summary["totals"]

    # ---- read

    def get_comparison(self, run_id: int) -> ComparisonView:
        with self.db.session() as s:
            run = self._run(s, run_id)
            rec = s.scalar(select(RunComparison).where(RunComparison.run_id == run.id))
            if rec is None:
                raise NotFoundError(f"Run {run.run_number} has not been compared yet.")
            m = s.get(Milestone, run.milestone_id)
            summary = json.loads(rec.summary)
            source_types = json.loads(rec.source_types)
            rules = self.rules(rec.rules_version)
            art = s.scalar(select(OutputArtifact).where(OutputArtifact.run_id == run.id,
                                                        OutputArtifact.kind == COMPARISON_KIND))
            output = (OutputView(art.id, art.run_id, art.kind, art.file_name, art.stored_path, art.sha256,
                                 art.file_size, _utc(art.generated_at)) if art else None)
            shell =WorkbookModel(scope=[], sources=source_columns(source_types), sheets=sheet_shells())
            return ComparisonView(
                run_id=run.id, run_number=run.run_number, milestone_id=m.id, milestone_code=m.milestone_code,
                rules_version=rec.rules_version, compared_at=_utc(rec.created_at),
                scope_tag_count=summary["scope_tag_count"],
                source_types=[{"code": st, "label": SOURCE_TYPES[st].label, "rank": rules.rank(st) + 1}
                              for st in source_types],
                totals=summary["totals"], no_source_value=summary["no_source_value"],
                attributes=summary["attributes"],
                workbook={"summary_sheet": "SUMMERY", "summary_headers": shell.summary_headers(),
                          "sheets": [{"name": sh.sheet_name, "headers": shell.sheet_headers(sh)} for sh in shell.sheets]},
                output=output)

    # ---- internals

    @staticmethod
    def _summary(results, cells, source_types: list[str]) -> dict:
        provided: dict[str, set[str]] = {}
        for c in cells:
            provided.setdefault(c.attribute, set()).add(c.source_type)
        attributes = []
        for a in ATTRIBUTES:
            rs = [r for r in results if r.attribute == a.value]
            counts = Counter(r.status.value for r in rs if r.status)
            attributes.append({
                "code": a.value, "label": ATTRIBUTE_INFO[a].label, "sheet_name": ATTRIBUTE_INFO[a].sheet_name,
                "provided_by": [st for st in source_types if st in provided.get(a.value, set())],
                "counts": {h: counts.get(h, 0) for h in STATES},
                "no_source_value": sum(1 for r in rs if r.status is None),
                "reasons": {reason.value: sum(1 for r in rs if r.reason == reason) for reason in Reason},
            })
        totals = {h: sum(x["counts"][h] for x in attributes) for h in STATES}
        return {"scope_tag_count": len(results) // len(ATTRIBUTES), "totals": totals,
                "no_source_value": sum(x["no_source_value"] for x in attributes), "attributes": attributes}

    @staticmethod
    def _run(s, run_id: int) -> ProcessingRun:
        run = s.get(ProcessingRun, run_id)
        if run is None:
            raise NotFoundError(f"Processing run {run_id} does not exist.")
        return run
