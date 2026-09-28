"""Processing runs and source documents: create run → upload → identify → map → extract → check
against the locked scope → persist evidence.

The milestone scope is read, never written: runs exist only on locked milestones (enforced here and by a
database trigger), and source tags outside the scope are reported, never added.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import PurePath

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from backend.config import RULES_VERSION
from backend.domain.issues import Issue, Severity
from backend.domain.milestone import MilestoneStatus
from backend.domain.sources import (
    ATTRIBUTES,
    SOURCE_TYPES,
    RunStatus,
    SourceProcessingStatus,
    compute_scope_coverage,
)
from backend.extraction import registry
from backend.extraction.tabular import Extraction, Identification, UnreadableWorkbook, load_workbook
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError
from backend.storage.database import Database
from backend.storage.files import FileStore, sha256_bytes
from backend.storage.models import (
    Milestone,
    MilestoneTag,
    ProcessingRun,
    RunSource,
    SourceDocument,
    SourceRecord,
    utcnow,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- views

@dataclass(frozen=True)
class SourceTypeView:
    code: str
    label: str
    adapter_available: bool
    verified: bool                           # adapter checked against a real file of the type


@dataclass(frozen=True)
class RunSourceView:
    id: int
    run_id: int
    document_id: int
    original_filename: str
    source_type: str | None
    source_type_label: str | None
    processing_status: str
    file_size: int
    sha256: str
    uploaded_at: datetime
    processed_at: datetime
    document_date: date | None
    revision: str | None
    sheet_name: str | None
    header_row: int | None
    row_count: int | None
    recognized_tag_count: int | None
    unique_tag_count: int | None
    duplicate_tag_count: int | None
    matched_tag_count: int | None
    unmatched_tag_count: int | None
    scope_tags_without_record: int | None
    scope_tag_count: int
    attributes_provided: list[str]
    attribute_counts: dict[str, int]
    mapping: list[dict]
    headers_found: list[str]
    skipped_sheets: list[dict]
    duplicates: list[dict]
    out_of_scope: list[dict]
    rows_without_tag_key: list[int]
    errors: list[Issue]
    warnings: list[Issue]


@dataclass(frozen=True)
class RunDetailView:
    id: int
    milestone_id: int
    milestone_code: str
    run_number: int
    status: str
    rules_version: str
    scope_fingerprint: str
    scope_tag_count: int
    created_at: datetime
    notes: str | None
    sources: list[RunSourceView] = field(default_factory=list)


@dataclass(frozen=True)
class IdentificationView:
    file_name: str
    sha256: str
    file_size: int
    source_type: str | None
    source_type_label: str | None
    sheet_name: str | None
    header_row: int | None
    row_count: int
    attributes_provided: list[str]
    mapping: list[dict]
    headers_found: list[str]
    skipped_sheets: list[dict]
    errors: list[Issue]
    warnings: list[Issue]


@dataclass(frozen=True)
class SourceRowView:
    row: int
    source_tag: str | None
    in_scope: bool
    values: dict[str, str | None]            # attribute -> raw value
    location: dict                           # provenance of the row


@dataclass(frozen=True)
class SourceRowsPage:
    total: int
    offset: int
    rows: list[SourceRowView]


# ---------------------------------------------------------------- helpers

def _utc(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None else None


def _issue_dict(i: Issue) -> dict:
    return {"severity": i.severity, "code": i.code, "message": i.message, "rows": list(i.rows),
            "column": i.column, "value": i.value}


def _issue(d: dict) -> Issue:
    return Issue(Severity(d["severity"]), d["code"], d["message"], tuple(d["rows"]), d["column"], d["value"])


def attributes_provided(report: dict) -> list[str]:
    """Attributes a processed document provides. Reports written before attribute columns became optional
    have no such entry; every attribute column was then required, so those documents provide all of them."""
    if "attributes_provided" in report:
        return list(report["attributes_provided"])
    return [a.value for a in ATTRIBUTES] if report.get("attribute_counts") else []


def _label(source_type: str | None) -> str | None:
    return SOURCE_TYPES[source_type].label if source_type in SOURCE_TYPES else None


@dataclass
class _Processed:
    ident: Identification
    extraction: Extraction | None


# ---------------------------------------------------------------- service

class RunService:
    def __init__(self, db: Database, files: FileStore):
        self.db = db
        self.files = files

    @staticmethod
    def source_types() -> list[SourceTypeView]:
        return [SourceTypeView(t.code, t.label, t.code in registry.ADAPTERS,
                               t.code in registry.ADAPTERS and registry.ADAPTERS[t.code].config.verified)
                for t in SOURCE_TYPES.values()]

    # ---- runs

    def create_run(self, milestone_id: int, notes: str | None, base_run_id: int | None = None,
                   exclude_source_ids: frozenset[int] = frozenset()) -> RunDetailView:
        """Create a run. With `base_run_id`, the new run starts with that run's successfully processed
        documents (except `exclude_source_ids`): each is read back from the vault (hash-verified) and
        extracted afresh for the new run. The base run is only read, never changed."""
        with self.db.session() as s:
            m = s.get(Milestone, milestone_id)
            if m is None:
                raise NotFoundError(f"Milestone {milestone_id} does not exist.")
            if m.status != MilestoneStatus.SCOPE_LOCKED:
                raise ConflictError("A processing run can only be created after the milestone scope is locked.")
            carried: list[tuple[str, str, str, str | None]] = []
            if base_run_id is not None:
                base = s.get(ProcessingRun, base_run_id)
                if base is None or base.milestone_id != m.id:
                    raise InvalidInputError(f"Run {base_run_id} is not a run of milestone '{m.milestone_code}'.")
                carried = [(rs.document.stored_path, rs.document.sha256, rs.document.original_filename, rs.source_type)
                           for rs in base.sources if rs.processing_status != SourceProcessingStatus.FAILED
                           and rs.id not in exclude_source_ids]
            number = (s.scalar(select(func.max(ProcessingRun.run_number))
                               .where(ProcessingRun.milestone_id == m.id)) or 0) + 1
            run = ProcessingRun(milestone_id=m.id, run_number=number, status=RunStatus.CREATED,
                                rules_version=RULES_VERSION, notes=(notes or "").strip() or None)
            s.add(run)
            s.flush()
            run_id = run.id
        log.info("Created run %s for milestone id=%s (run id=%s)", number, milestone_id, run_id)
        for path, digest, name, source_type in carried:
            self.upload_source(run_id, name, self.files.read_verified(path, digest), source_type)
        return self.get_run(run_id)

    def list_runs(self, milestone_id: int) -> list[RunDetailView]:
        with self.db.session() as s:
            if s.get(Milestone, milestone_id) is None:
                raise NotFoundError(f"Milestone {milestone_id} does not exist.")
            ids = s.scalars(select(ProcessingRun.id).where(ProcessingRun.milestone_id == milestone_id)
                            .order_by(ProcessingRun.run_number.desc())).all()
        return [self.get_run(i) for i in ids]

    def get_run(self, run_id: int) -> RunDetailView:
        with self.db.session() as s:
            run = self._run(s, run_id)
            m = s.get(Milestone, run.milestone_id)
            scope_count = self._scope_count(s, m.id)
            return RunDetailView(
                id=run.id, milestone_id=m.id, milestone_code=m.milestone_code, run_number=run.run_number,
                status=run.status, rules_version=run.rules_version, scope_fingerprint=m.scope_fingerprint,
                scope_tag_count=scope_count, created_at=_utc(run.created_at), notes=run.notes,
                sources=[self._source_view(rs, scope_count) for rs in run.sources])

    # ---- sources

    def identify_source(self, run_id: int, file_name: str, data: bytes, source_type: str | None) -> IdentificationView:
        """Dry run: detect type, sheet and field mapping without storing anything."""
        with self.db.session() as s:
            self._run(s, run_id)
        self._check_requested_type(source_type)
        book = self._load(file_name, data)
        p = self._process(book, source_type)
        issues = p.ident.issues + (p.extraction.issues if p.extraction else [])
        ext = p.extraction
        return IdentificationView(
            file_name=PurePath(file_name).name, sha256=sha256_bytes(data), file_size=len(data),
            source_type=p.ident.source_type, source_type_label=_label(p.ident.source_type),
            sheet_name=p.ident.sheet_name, header_row=ext.header_row if ext else None,
            row_count=len(ext.rows) if ext and ext.ok else 0,
            attributes_provided=[a.value for a in ext.provided_attributes] if ext and ext.ok else [],
            mapping=[vars(b) for b in ext.mapping] if ext else [],
            headers_found=ext.headers_found if ext else [], skipped_sheets=p.ident.skipped_sheets,
            errors=[i for i in issues if i.severity == Severity.ERROR],
            warnings=[i for i in issues if i.severity == Severity.WARNING])

    def upload_source(self, run_id: int, file_name: str, data: bytes, source_type: str | None,
                      document_date: str | None = None, revision: str | None = None) -> RunSourceView:
        self._check_requested_type(source_type)
        doc_date = self._parse_date(document_date)
        book = self._load(file_name, data)
        digest = sha256_bytes(data)
        name = PurePath(file_name).name

        with self.db.session() as s:
            run = self._run(s, run_id)
            if run.status == RunStatus.CONSOLIDATED:
                raise ConflictError(
                    f"Run {run.run_number} is consolidated, so its source set is frozen. Create a new run to add "
                    f"or revise documents — run {run.run_number} stays unchanged.")
            m = s.get(Milestone, run.milestone_id)
            existing = s.scalar(select(SourceDocument).where(SourceDocument.milestone_id == m.id,
                                                             SourceDocument.sha256 == digest))
            if existing is not None and s.scalar(select(RunSource.id).where(
                    RunSource.run_id == run.id, RunSource.source_document_id == existing.id)) is not None:
                raise ConflictError(f"This file (SHA-256 {digest[:12]}…) is already part of run {run.run_number}.")
            scope = dict(s.execute(select(MilestoneTag.normalized_tag, MilestoneTag.id)
                                   .where(MilestoneTag.milestone_id == m.id)).all())

            p = self._process(book, source_type)
            detected = p.ident.source_type
            ext = p.extraction
            issues: list[Issue] = list(p.ident.issues) + (list(ext.issues) if ext else [])
            report: dict = {"mapping": [vars(b) for b in ext.mapping] if ext else [],
                            "headers_found": ext.headers_found if ext else [],
                            "skipped_sheets": p.ident.skipped_sheets,
                            "attribute_counts": {}, "duplicates": [], "out_of_scope": [], "rows_without_tag_key": []}
            stats: dict = {}
            ok = ext is not None and ext.ok
            if ok:
                cov = compute_scope_coverage([(r.row_number, r.normalized_key) for r in ext.rows], set(scope))
                issues += self._coverage_issues(cov)
                stats = dict(row_count=cov.source_rows, recognized_tag_count=cov.rows_with_tag_key,
                             unique_tag_count=cov.unique_source_tags, duplicate_tag_count=len(cov.duplicates),
                             matched_tag_count=cov.matched_tags, unmatched_tag_count=len(cov.out_of_scope_tags),
                             scope_tags_without_record=cov.scope_tags_without_record)
                report["attributes_provided"] = [a.value for a in ext.provided_attributes]
                report["attribute_counts"] = {a.value: sum(1 for r in ext.rows if r.values[a].normalized is not None)
                                              for a in ext.provided_attributes}
                report["duplicates"] = [{"tag": d.normalized_tag, "rows": list(d.rows), "in_scope": d.in_scope}
                                        for d in cov.duplicates]
                report["out_of_scope"] = [{"tag": k, "rows": list(r)} for k, r in cov.out_of_scope_tags.items()]
                report["rows_without_tag_key"] = cov.rows_without_tag_key
            report["issues"] = [_issue_dict(i) for i in issues]

            if not ok:
                status = SourceProcessingStatus.FAILED
            elif any(i.severity == Severity.WARNING for i in issues):
                status = SourceProcessingStatus.PROCESSED_WITH_WARNINGS
            else:
                status = SourceProcessingStatus.PROCESSED

            rel_path, _ = self.files.store_immutable(m.milestone_code, "sources", data, PurePath(name).suffix or ".xlsx")
            if existing is None:
                existing = SourceDocument(milestone_id=m.id, source_type=detected, original_filename=name,
                                          stored_path=rel_path, file_size=len(data), sha256=digest,
                                          document_date=doc_date, revision=(revision or "").strip() or None)
                s.add(existing)
                s.flush()
            elif existing.source_type is None and detected is not None:
                existing.source_type = detected

            rs = RunSource(run_id=run.id, source_document_id=existing.id, source_type=detected,
                           processing_status=status, sheet_name=p.ident.sheet_name,
                           header_row=ext.header_row if ext else None, report=json.dumps(report), **stats)
            s.add(rs)
            s.flush()

            if ok:
                self._store_records(s, run.id, rs.id, existing.id, detected, ext, scope, book.file_name)
                if run.status == RunStatus.CREATED:
                    run.status = RunStatus.DOCUMENTS_UPLOADED
            rs_id = rs.id

        log.info("Run id=%s: %s processed as %s -> %s", run_id, name, detected, status)
        return self.get_run_source(run_id, rs_id)

    def remove_source(self, run_id: int, run_source_id: int) -> RunDetailView:
        """Remove a document from the milestone's working source set. Source records are immutable, so the
        run is not edited: a new run is created carrying every other processed document forward. The given
        run, its records and the stored file stay unchanged in history."""
        with self.db.session() as s:
            rs = s.get(RunSource, run_source_id)
            if rs is None or rs.run_id != run_id:
                raise NotFoundError(f"Source {run_source_id} is not part of run {run_id}.")
            milestone_id = s.get(ProcessingRun, run_id).milestone_id
            name = rs.document.original_filename
        log.info("Run id=%s: removing %s (run source id=%s) via a new run", run_id, name, run_source_id)
        return self.create_run(milestone_id, None, run_id, frozenset({run_source_id}))

    def get_run_source(self, run_id: int, run_source_id: int) -> RunSourceView:
        with self.db.session() as s:
            rs = s.get(RunSource, run_source_id)
            if rs is None or rs.run_id != run_id:
                raise NotFoundError(f"Source {run_source_id} is not part of run {run_id}.")
            run = s.get(ProcessingRun, run_id)
            return self._source_view(rs, self._scope_count(s, run.milestone_id))

    def list_source_rows(self, run_id: int, run_source_id: int, offset: int = 0, limit: int = 100) -> SourceRowsPage:
        """Extracted records regrouped per source row, for display. Values are the raw extracted text."""
        self.get_run_source(run_id, run_source_id)
        with self.db.session() as s:
            row_q = (select(SourceRecord.source_row_index).where(SourceRecord.run_source_id == run_source_id)
                     .distinct().order_by(SourceRecord.source_row_index))
            all_rows = s.scalars(row_q).all()
            page = all_rows[offset:offset + limit]
            if not page:
                return SourceRowsPage(len(all_rows), offset, [])
            recs = s.scalars(select(SourceRecord).where(SourceRecord.run_source_id == run_source_id,
                                                        SourceRecord.source_row_index.in_(page))
                             .order_by(SourceRecord.source_row_index, SourceRecord.id)).all()
        grouped: dict[int, list[SourceRecord]] = {}
        for r in recs:
            grouped.setdefault(r.source_row_index, []).append(r)
        rows = []
        for idx in page:
            rr = grouped[idx]
            loc = json.loads(rr[0].source_location)
            rows.append(SourceRowView(
                row=idx, source_tag=rr[0].source_tag, in_scope=rr[0].milestone_tag_id is not None,
                values={r.attribute: r.raw_value for r in rr},
                location={k: loc.get(k) for k in ("document", "sheet", "row", "document_reference", "page")}))
        return SourceRowsPage(len(all_rows), offset, rows)

    # ---- internals

    @staticmethod
    def _check_requested_type(source_type: str | None) -> None:
        if source_type is None:
            return
        if source_type not in SOURCE_TYPES:
            raise InvalidInputError(f"Unknown source type '{source_type}'.")
        if source_type not in registry.ADAPTERS:
            raise InvalidInputError(
                f"No adapter is available yet for {SOURCE_TYPES[source_type].label}. It will be enabled once a "
                f"real {source_type} file has been supplied and verified.")

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise InvalidInputError(f"Document date '{value}' is not a valid YYYY-MM-DD date.") from exc

    @staticmethod
    def _load(file_name: str, data: bytes):
        try:
            return load_workbook(file_name, data)
        except UnreadableWorkbook as exc:
            raise InvalidInputError(str(exc)) from exc

    @staticmethod
    def _process(book, source_type: str | None) -> _Processed:
        ident = registry.identify(book, source_type)
        if ident.source_type is None:
            return _Processed(ident, None)
        return _Processed(ident, registry.extract(book, ident))

    @staticmethod
    def _coverage_issues(cov) -> list[Issue]:
        out = []
        for d in cov.duplicates:
            out.append(Issue(Severity.WARNING, "DUPLICATE_SOURCE_TAG",
                             f"Tag '{d.normalized_tag}' has {len(d.rows)} rows in this document. All rows are kept; "
                             f"none is chosen automatically.", rows=d.rows, value=d.normalized_tag))
        if cov.out_of_scope_tags:
            rows = tuple(sorted(r for rs in cov.out_of_scope_tags.values() for r in rs))
            out.append(Issue(Severity.WARNING, "OUT_OF_SCOPE_TAG",
                             f"{len(cov.out_of_scope_tags)} tag(s) in this document are not in the milestone scope. "
                             f"They are recorded and reported but never added to the scope.", rows=rows))
        if cov.rows_without_tag_key:
            out.append(Issue(Severity.WARNING, "BLANK_TAG_KEY",
                             f"{len(cov.rows_without_tag_key)} row(s) have data but no TAG NUMBER key, so they cannot "
                             f"be linked to a milestone tag. They are recorded as unlinked evidence.",
                             rows=tuple(cov.rows_without_tag_key)))
        if cov.source_rows and cov.matched_tags == 0:
            out.append(Issue(Severity.WARNING, "NO_TAG_IN_SCOPE",
                             "None of this document's tags are in the milestone scope — check that it belongs to "
                             "this milestone."))
        return out

    @staticmethod
    def _store_records(s: Session, run_id: int, rs_id: int, doc_id: int, source_type: str,
                       ext: Extraction, scope: dict[str, int], file_name: str) -> None:
        payload = []
        for row in ext.rows:
            base_loc = {"document": file_name, "sheet": ext.sheet_name, "row": row.row_number, **ext.location_of(row)}
            tag_id = scope.get(row.normalized_key) if row.normalized_key else None
            for attr, v in row.values.items():
                loc = base_loc | {"column": v.column, "cell": f"{v.column}{row.row_number}", "raw_type": v.raw_type}
                payload.append({
                    "run_id": run_id, "run_source_id": rs_id, "source_document_id": doc_id,
                    "source_type": source_type, "source_row_index": row.row_number, "source_tag": row.raw_key,
                    "normalized_tag": row.normalized_key, "milestone_tag_id": tag_id, "attribute": attr.value,
                    "raw_value": v.raw, "normalized_value": v.normalized, "source_location": json.dumps(loc)})
        if payload:
            s.execute(insert(SourceRecord), payload)

    @staticmethod
    def _run(s: Session, run_id: int) -> ProcessingRun:
        run = s.get(ProcessingRun, run_id)
        if run is None:
            raise NotFoundError(f"Processing run {run_id} does not exist.")
        return run

    @staticmethod
    def _scope_count(s: Session, milestone_id: int) -> int:
        return s.scalar(select(func.count()).where(MilestoneTag.milestone_id == milestone_id)) or 0

    @staticmethod
    def _source_view(rs: RunSource, scope_count: int) -> RunSourceView:
        d = rs.document
        rep = json.loads(rs.report or "{}")
        issues = [_issue(i) for i in rep.get("issues", [])]
        return RunSourceView(
            id=rs.id, run_id=rs.run_id, document_id=d.id, original_filename=d.original_filename,
            source_type=rs.source_type, source_type_label=_label(rs.source_type),
            processing_status=rs.processing_status, file_size=d.file_size, sha256=d.sha256,
            uploaded_at=_utc(d.uploaded_at), processed_at=_utc(rs.processed_at), document_date=d.document_date,
            revision=d.revision, sheet_name=rs.sheet_name, header_row=rs.header_row, row_count=rs.row_count,
            recognized_tag_count=rs.recognized_tag_count, unique_tag_count=rs.unique_tag_count,
            duplicate_tag_count=rs.duplicate_tag_count, matched_tag_count=rs.matched_tag_count,
            unmatched_tag_count=rs.unmatched_tag_count, scope_tags_without_record=rs.scope_tags_without_record,
            scope_tag_count=scope_count, attributes_provided=attributes_provided(rep),
            attribute_counts=rep.get("attribute_counts", {}),
            mapping=rep.get("mapping", []), headers_found=rep.get("headers_found", []),
            skipped_sheets=rep.get("skipped_sheets", []), duplicates=rep.get("duplicates", []),
            out_of_scope=rep.get("out_of_scope", []), rows_without_tag_key=rep.get("rows_without_tag_key", []),
            errors=[i for i in issues if i.severity == Severity.ERROR],
            warnings=[i for i in issues if i.severity == Severity.WARNING])
