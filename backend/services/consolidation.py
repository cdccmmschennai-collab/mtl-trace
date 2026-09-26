"""Consolidation workflow (Phase 1C): a run's stored SOURCE_RECORDs + the locked scope → canonical dataset
→ generated consolidated workbook and canonical snapshot.

Reads source *records* only — never reopens a source file. Consolidates each run exactly once; the run's
sources are then frozen (service check + database triggers), so a revised or additional document goes
into a new run and earlier runs stay exactly as they were.

No FINAL value, priority, or MATCH / MISMATCH / REVIEW REQUIRED is produced here (Phase 1D).
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from backend.consolidation.engine import CellState, Consolidation, RecordIn, ScopeTagIn, consolidate
from backend.domain.sources import (
    ATTRIBUTE_INFO,
    ATTRIBUTES,
    SOURCE_TYPES,
    RunStatus,
    SourceProcessingStatus,
    ordered_source_types,
)
from backend.domain.tags import normalize_tag
from backend.output.canonical_snapshot import SnapshotRow, build_snapshot
from backend.output.comparison_workbook import (
    AttributeSheet,
    ScopeRow,
    SourceCell,
    SourceColumn,
    WorkbookModel,
    build_workbook,
)
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError
from backend.services.runs import attributes_provided
from backend.storage.database import Database
from backend.storage.files import FileStore
from backend.storage.models import (
    CanonicalCell,
    Milestone,
    MilestoneTag,
    OutputArtifact,
    ProcessingRun,
    RunConsolidation,
    RunSource,
    SourceRecord,
)

log = logging.getLogger(__name__)

WORKBOOK_KIND = "CONSOLIDATED_WORKBOOK"
SNAPSHOT_KIND = "CANONICAL_SNAPSHOT"
LOCATION_KEYS = ("document", "sheet", "row", "cell", "document_reference", "page")

# Row filters for the CONSOLIDATION grid. Presentation only — they select rows, they decide nothing.
ROW_FILTERS = ("all", "with_values", "no_source_row", "missing_in_some_source", "empty_values", "duplicates",
               "tag_differs")


# ---------------------------------------------------------------- views

@dataclass(frozen=True)
class OutputView:
    id: int
    run_id: int
    kind: str
    file_name: str
    stored_path: str
    sha256: str
    file_size: int
    generated_at: datetime


@dataclass(frozen=True)
class ConsolidationView:
    run_id: int
    run_number: int
    milestone_id: int
    milestone_code: str
    consolidated_at: datetime
    scope_fingerprint: str
    scope_tag_count: int
    canonical_row_count: int
    canonical_cell_count: int
    attributes: list[dict]
    source_types: list[dict]
    not_in_run: list[dict]
    documents: list[dict]
    coverage: list[dict]
    workbook: dict
    outputs: list[OutputView]


@dataclass(frozen=True)
class CanonicalRowView:
    milestone_tag_id: int
    scope_order: int
    s_no: str | None
    tag_number: str
    tag_description: str | None
    equipment_description: str | None
    size_rating: str | None
    source_rows: dict[str, str]                      # source type -> ROW | NO_ROW | DUPLICATE_ROWS
    cells: dict[str, dict[str, dict]]                # attribute -> source type -> {state, value, provenance}


@dataclass(frozen=True)
class CanonicalPageView:
    run_id: int
    total: int
    filtered_total: int
    offset: int
    source_types: list[str]
    attributes: list[str]
    rows: list[CanonicalRowView] = field(default_factory=list)


def _utc(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None else None


def source_columns(source_types: list[str]) -> list[SourceColumn]:
    return [SourceColumn(st, SOURCE_TYPES[st].label, SOURCE_TYPES[st].summary_code) for st in source_types]


def sheet_shells() -> list[AttributeSheet]:
    return [AttributeSheet(a.value, i.sheet_name, i.column_label, i.final_label, i.summary_description, [])
            for a, i in ((a, ATTRIBUTE_INFO[a]) for a in ATTRIBUTES)]


CellSnapshot = tuple[str, str | None, list[tuple[str | None, dict]]]   # state, raw value, [(candidate raw, location)]


def source_workbook_model(tags, source_types: list[str], cells: dict[tuple[int, str, str], CellSnapshot],
                          title: str) -> WorkbookModel:
    """Workbook layout with the source columns filled from canonical cells, keyed (tag id, attribute, source type).
    A missing key means the source does not provide that attribute: the cell stays empty. Shared by the
    consolidated and the comparison workbook."""
    sheets = sheet_shells()
    for sheet in sheets:
        for t in tags:
            row = {}
            for st in source_types:
                c = cells.get((t.id, sheet.attribute, st))
                if c is not None and c[0] == CellState.PRESENT:
                    row[st] = SourceCell(c[1])
                elif c is not None and c[0] == CellState.CONFLICTING_DUPLICATE:
                    cands = "; ".join(f"{raw!r} ({loc.get('document')} row {loc.get('row')})" for raw, loc in c[2])
                    row[st] = SourceCell(None, f"Duplicate source rows for this tag — none chosen: {cands}")
                else:
                    row[st] = SourceCell(None)
            sheet.cells.append(row)
    return WorkbookModel(
        scope=[ScopeRow(t.s_no, t.tag_number, t.tag_description, t.equipment_description, t.size_rating) for t in tags],
        sources=source_columns(source_types), sheets=sheets, title=title)


def _type_ref(code: str) -> dict:
    return {"code": code, "label": SOURCE_TYPES[code].label}


# ---------------------------------------------------------------- service

class ConsolidationService:
    def __init__(self, db: Database, files: FileStore):
        self.db = db
        self.files = files

    # ---- consolidate

    def consolidate(self, run_id: int) -> ConsolidationView:
        written: list[str] = []
        try:
            tags, source_types, cell_count = self._consolidate(run_id, written)
        except BaseException:
            for path in written:                       # transaction rolled back: leave no orphaned artifact
                self.files.resolve(path).unlink(missing_ok=True)
            raise
        log.info("Consolidated run id=%s: %s tags, source type(s) %s, %s cells",
                 run_id, tags, ", ".join(source_types), cell_count)
        return self.get_consolidation(run_id)

    def _consolidate(self, run_id: int, written: list[str]) -> tuple[int, list[str], int]:
        with self.db.session() as s:
            run = self._run(s, run_id)
            if run.status == RunStatus.CONSOLIDATED or self._record(s, run_id) is not None:
                raise ConflictError(
                    f"Run {run.run_number} is already consolidated. Its canonical dataset and outputs are "
                    f"preserved unchanged; to add or revise documents, create a new run.")
            m = s.get(Milestone, run.milestone_id)
            included = [rs for rs in run.sources
                        if rs.processing_status != SourceProcessingStatus.FAILED and rs.source_type is not None]
            if not included:
                raise ConflictError(
                    f"Run {run.run_number} has no successfully processed source document to consolidate.")
            source_types = ordered_source_types({rs.source_type for rs in included})
            docs_per_type = {st: sum(1 for rs in included if rs.source_type == st) for st in source_types}
            provided: dict[str, set[str]] = {st: set() for st in source_types}
            for rs in included:
                provided[rs.source_type] |= set(attributes_provided(json.loads(rs.report or "{}")))

            tags = s.scalars(select(MilestoneTag).where(MilestoneTag.milestone_id == m.id)
                             .order_by(MilestoneTag.scope_order)).all()
            rec_rows = s.execute(
                select(SourceRecord.id, SourceRecord.run_source_id, SourceRecord.source_type,
                       SourceRecord.source_row_index, SourceRecord.source_tag, SourceRecord.normalized_tag,
                       SourceRecord.attribute, SourceRecord.raw_value, SourceRecord.normalized_value,
                       SourceRecord.source_location)
                .where(SourceRecord.run_id == run.id,
                       SourceRecord.run_source_id.in_([rs.id for rs in included]))).all()
            records = [RecordIn(*r[:9]) for r in rec_rows]
            locations = {r[0]: json.loads(r[9]) for r in rec_rows}

            result = consolidate([ScopeTagIn(t.id, t.scope_order, t.tag_number, t.normalized_tag) for t in tags],
                                 records, source_types, ATTRIBUTES, docs_per_type, provided)

            summary = {"coverage": [self._coverage_dict(c) for c in result.coverage.values()],
                       "documents": [self._document_dict(rs, rs in included) for rs in run.sources]}
            s.add(RunConsolidation(
                run_id=run.id, scope_fingerprint=m.scope_fingerprint, tag_count=len(tags),
                cell_count=len(result.cells), source_types=json.dumps(source_types),
                run_source_ids=json.dumps([rs.id for rs in included]), summary=json.dumps(summary)))
            s.execute(insert(CanonicalCell), [
                {"run_id": run.id, "milestone_tag_id": c.milestone_tag_id, "attribute": c.attribute.value,
                 "source_type": c.source_type, "state": c.state.value, "raw_value": c.raw_value,
                 "normalized_value": c.normalized_value,
                 "source_record_id": c.record_ids[0] if len(c.record_ids) == 1 else None,
                 "source_record_ids": json.dumps(list(c.record_ids))}
                for c in result.cells])

            record_by_id = {r.id: r for r in records}
            workbook = build_workbook(self._workbook_model(m.milestone_code, run.run_number, tags, result,
                                                           record_by_id, locations))
            snapshot = build_snapshot(self._snapshot_rows(tags, result, locations))
            # Short names on disk (Windows path-length limit); the descriptive name is the download name.
            base = f"MTL-DATA MISMATCH COMPARISION - {m.milestone_code} - RUN-{run.run_number:03d}"
            for kind, area, disk_name, name, data in (
                    (SNAPSHOT_KIND, "canonical", "canonical.csv", f"{base} - CANONICAL.csv", snapshot),
                    (WORKBOOK_KIND, "outputs", "consolidated.xlsx", f"{base} - CONSOLIDATED.xlsx", workbook)):
                path, digest = self.files.store_generated(m.milestone_code, area, run.run_number, disk_name, data)
                written.append(path)
                s.add(OutputArtifact(run_id=run.id, kind=kind, file_name=name, stored_path=path,
                                     sha256=digest, file_size=len(data)))
            run.status = RunStatus.CONSOLIDATED
            return len(tags), source_types, len(result.cells)

    # ---- read

    def get_consolidation(self, run_id: int) -> ConsolidationView:
        with self.db.session() as s:
            run = self._run(s, run_id)
            rec = self._record(s, run_id)
            if rec is None:
                raise NotFoundError(f"Run {run.run_number} has not been consolidated yet.")
            m = s.get(Milestone, run.milestone_id)
            source_types = json.loads(rec.source_types)
            summary = json.loads(rec.summary)
            model = WorkbookModel(scope=[], sources=source_columns(source_types), sheets=sheet_shells())
            return ConsolidationView(
                run_id=run.id, run_number=run.run_number, milestone_id=m.id, milestone_code=m.milestone_code,
                consolidated_at=_utc(rec.created_at), scope_fingerprint=rec.scope_fingerprint,
                scope_tag_count=rec.tag_count, canonical_row_count=rec.tag_count, canonical_cell_count=rec.cell_count,
                attributes=[{"code": a.value, "label": ATTRIBUTE_INFO[a].label} for a in ATTRIBUTES],
                source_types=[_type_ref(st) | {"documents": sum(1 for d in summary["documents"]
                                                                 if d["included"] and d["source_type"] == st)}
                              for st in source_types],
                not_in_run=[_type_ref(st) for st in SOURCE_TYPES if st not in source_types],
                documents=summary["documents"],
                # Consolidations recorded before attribute columns became optional covered every attribute.
                coverage=[{"attributes_provided": list(c["attributes"])} | c | {"label": SOURCE_TYPES[c["source_type"]].label}
                          for c in summary["coverage"]],
                workbook={"summary_sheet": "SUMMERY", "summary_headers": model.summary_headers(),
                          "sheets": [{"name": sh.sheet_name, "headers": model.sheet_headers(sh)}
                                     for sh in model.sheets]},
                outputs=self._outputs(s, run.id))

    def list_outputs(self, run_id: int) -> list[OutputView]:
        with self.db.session() as s:
            self._run(s, run_id)
            return self._outputs(s, run_id)

    def output_file(self, run_id: int, output_id: int) -> tuple[Path, str]:
        with self.db.session() as s:
            art = s.get(OutputArtifact, output_id)
            if art is None or art.run_id != run_id:
                raise NotFoundError(f"Output {output_id} is not part of run {run_id}.")
            self.files.read_verified(art.stored_path, art.sha256)        # refuse to serve altered evidence
            return self.files.resolve(art.stored_path), art.file_name

    def canonical_rows(self, run_id: int, offset: int = 0, limit: int = 100, row_filter: str = "all",
                       search: str | None = None) -> CanonicalPageView:
        if row_filter not in ROW_FILTERS:
            raise InvalidInputError(f"Unknown filter '{row_filter}'. Use one of: {', '.join(ROW_FILTERS)}.")
        with self.db.session() as s:
            run = self._run(s, run_id)
            rec = self._record(s, run_id)
            if rec is None:
                raise NotFoundError(f"Run {run.run_number} has not been consolidated yet.")
            source_types = json.loads(rec.source_types)
            tags = s.scalars(select(MilestoneTag).where(MilestoneTag.milestone_id == run.milestone_id)
                             .order_by(MilestoneTag.scope_order)).all()
            cells = s.execute(select(CanonicalCell.milestone_tag_id, CanonicalCell.attribute,
                                     CanonicalCell.source_type, CanonicalCell.state, CanonicalCell.raw_value,
                                     CanonicalCell.normalized_value, CanonicalCell.source_record_ids)
                              .where(CanonicalCell.run_id == run_id)).all()
            by_tag: dict[int, dict[str, dict[str, tuple]]] = {}
            for c in cells:
                by_tag.setdefault(c[0], {}).setdefault(c[1], {})[c[2]] = c

            needle = (search or "").strip().upper()
            matching = [t for t in tags
                        if (not needle or needle in t.tag_number.upper()
                            or needle in (t.tag_description or "").upper()
                            or needle in (t.equipment_description or "").upper())
                        and self._matches(row_filter, t, by_tag.get(t.id, {}))]
            page = matching[offset:offset + limit]

            wanted = {rid for t in page for per_attr in by_tag.get(t.id, {}).values()
                      for c in per_attr.values() for rid in json.loads(c[6])}
            recs = {r.id: r for r in s.scalars(select(SourceRecord).where(SourceRecord.id.in_(wanted)))} if wanted else {}

            rows = []
            for t in page:
                per_attr = by_tag.get(t.id, {})
                rows.append(CanonicalRowView(
                    milestone_tag_id=t.id, scope_order=t.scope_order, s_no=t.s_no, tag_number=t.tag_number,
                    tag_description=t.tag_description, equipment_description=t.equipment_description,
                    size_rating=t.size_rating,
                    source_rows={st: self._row_state([per_src[st][3] for per_src in per_attr.values() if st in per_src])
                                 for st in source_types
                                 if any(st in per_src for per_src in per_attr.values())},
                    cells={a: {st: self._cell_view(c, recs) for st, c in per_src.items()}
                           for a, per_src in per_attr.items()}))
            return CanonicalPageView(run_id, len(tags), len(matching), offset, source_types,
                                     [a.value for a in ATTRIBUTES], rows)

    # ---- internals

    @staticmethod
    def _matches(row_filter: str, tag: MilestoneTag, per_attr: dict[str, dict[str, tuple]]) -> bool:
        states = [c[3] for per_src in per_attr.values() for c in per_src.values()]
        if row_filter == "all":
            return True
        if row_filter == "with_values":
            return CellState.PRESENT in states
        if row_filter == "no_source_row":
            return bool(states) and all(st == CellState.ABSENT_TAG for st in states)
        if row_filter == "missing_in_some_source":
            return CellState.ABSENT_TAG in states and any(st != CellState.ABSENT_TAG for st in states)
        if row_filter == "empty_values":
            return CellState.ABSENT_VALUE in states
        if row_filter == "duplicates":
            return CellState.CONFLICTING_DUPLICATE in states
        # tag_differs: a source's TAG NUMBER AS PER DOC differs from the milestone tag
        return any(c[3] == CellState.PRESENT and normalize_tag(c[5]) != tag.normalized_tag
                   for c in per_attr.get("TAG_NUMBER", {}).values())

    @staticmethod
    def _row_state(states: list[str]) -> str:
        """Whether a source type has a row for the tag, read across every attribute it provides."""
        if CellState.CONFLICTING_DUPLICATE in states:
            return "DUPLICATE_ROWS"
        return "NO_ROW" if all(s == CellState.ABSENT_TAG for s in states) else "ROW"

    @staticmethod
    def _cell_view(c: tuple, recs: dict[int, SourceRecord]) -> dict:
        provenance = []
        for rid in json.loads(c[6]):
            r = recs[rid]
            loc = json.loads(r.source_location)
            provenance.append({"record_id": rid, "source_tag": r.source_tag, "raw_value": r.raw_value,
                               **{k: loc.get(k) for k in LOCATION_KEYS}})
        return {"state": c[3], "value": c[4], "provenance": provenance}

    def _workbook_model(self, code: str, run_number: int, tags, result: Consolidation,
                        records: dict[int, RecordIn], locations: dict[int, dict]) -> WorkbookModel:
        index = {(c.milestone_tag_id, c.attribute.value, c.source_type): c for c in result.cells}
        cells = {k: (c.state, c.raw_value, [(records[i].raw_value, locations[i]) for i in c.record_ids])
                 for k, c in index.items()}
        return source_workbook_model(tags, list(result.source_types), cells,
                                     f"{code} run {run_number} — consolidated (pre-comparison)")

    @staticmethod
    def _snapshot_rows(tags, result: Consolidation, locations: dict[int, dict]) -> list[SnapshotRow]:
        tag_by_id = {t.id: t for t in tags}
        return [SnapshotRow(tag_by_id[c.milestone_tag_id].scope_order, tag_by_id[c.milestone_tag_id].s_no,
                            tag_by_id[c.milestone_tag_id].tag_number, c.attribute.value, c.source_type, c.state.value,
                            c.raw_value, c.normalized_value, c.record_ids,
                            tuple(locations[i] for i in c.record_ids))
                for c in result.cells]

    @staticmethod
    def _coverage_dict(c) -> dict:
        return {
            "source_type": c.source_type, "documents": c.documents, "rows": c.rows,
            "rows_without_tag_key": c.rows_without_tag_key, "unique_tags": c.unique_tags,
            "duplicate_tag_count": len(c.duplicate_tags),
            "duplicate_tags": [{"tag": k, "rows": n} for k, n in c.duplicate_tags.items()],
            "in_scope_tags": c.in_scope_tags, "out_of_scope_tag_count": len(c.out_of_scope_tags),
            "out_of_scope_tags": [{"tag": k, "rows": v} for k, v in c.out_of_scope_tags.items()],
            "scope_tags_without_row": c.scope_tags_without_row,
            "attributes_provided": c.attributes_provided,
            "attributes": {a: asdict(v) for a, v in c.attributes.items()},
            "tag_as_per_doc_equal": c.tag_as_per_doc_equal,
            "tag_as_per_doc_differs": len(c.tag_as_per_doc_differs),
            "tag_differences": [asdict(d) for d in c.tag_as_per_doc_differs],
        }

    @staticmethod
    def _document_dict(rs: RunSource, included: bool) -> dict:
        d = rs.document
        reason = None if included else (
            "processing failed" if rs.processing_status == SourceProcessingStatus.FAILED else "type not identified")
        return {"run_source_id": rs.id, "document_id": d.id, "file_name": d.original_filename,
                "source_type": rs.source_type, "sha256": d.sha256, "processing_status": rs.processing_status,
                "included": included, "excluded_reason": reason}

    @staticmethod
    def _outputs(s: Session, run_id: int) -> list[OutputView]:
        arts = s.scalars(select(OutputArtifact).where(OutputArtifact.run_id == run_id).order_by(OutputArtifact.id)).all()
        return [OutputView(a.id, a.run_id, a.kind, a.file_name, a.stored_path, a.sha256, a.file_size,
                           _utc(a.generated_at)) for a in arts]

    @staticmethod
    def _record(s: Session, run_id: int) -> RunConsolidation | None:
        return s.scalar(select(RunConsolidation).where(RunConsolidation.run_id == run_id))

    @staticmethod
    def _run(s: Session, run_id: int) -> ProcessingRun:
        run = s.get(ProcessingRun, run_id)
        if run is None:
            raise NotFoundError(f"Processing run {run_id} does not exist.")
        return run
