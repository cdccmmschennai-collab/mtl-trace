"""Milestone and finalized-scope workflow: create → import scope → validate → lock → history."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePath

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.milestone import MilestoneStatus, ScopeStatus, scope_status, validate_milestone_code
from backend.domain.scope import SCOPE_HEADERS, ScopeEntry, ScopeIssue, validate_scope_rows
from backend.extraction.scope import read_scope_workbook
from backend.storage.database import Database
from backend.storage.files import FileStore, sha256_bytes
from backend.storage.models import Milestone, MilestoneTag, Package, ProcessingRun, Project, utcnow

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- errors

class ServiceError(Exception):
    pass


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InvalidInputError(ServiceError):
    pass


class ScopeRejectedError(ServiceError):
    def __init__(self, report: "ScopeReport"):
        super().__init__("The scope file failed validation; nothing was imported.")
        self.report = report


# ---------------------------------------------------------------- views

@dataclass(frozen=True)
class RunView:
    id: int
    run_number: int
    status: str
    rules_version: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class MilestoneView:
    id: int
    milestone_code: str
    project_name: str | None
    package_name: str | None
    status: str
    scope_status: ScopeStatus
    tag_count: int
    created_at: datetime
    updated_at: datetime
    scope_file_name: str | None
    scope_file_sha256: str | None
    scope_sheet_name: str | None
    scope_imported_at: datetime | None
    scope_locked_at: datetime | None
    scope_fingerprint: str | None
    run_count: int
    latest_run: RunView | None
    runs: list[RunView] = field(default_factory=list)


@dataclass(frozen=True)
class ScopeReport:
    valid: bool
    file_name: str
    file_sha256: str
    sheet_name: str | None
    header_row: int | None
    columns: dict[str, str]           # template header -> column letter
    ignored_headers: list[str]
    data_row_count: int
    tag_count: int
    errors: list[ScopeIssue]
    warnings: list[ScopeIssue]


@dataclass(frozen=True)
class ScopeView:
    milestone_id: int
    scope_status: ScopeStatus
    tag_count: int
    file_name: str | None
    file_sha256: str | None
    sheet_name: str | None
    imported_at: datetime | None
    locked_at: datetime | None
    fingerprint: str | None
    tags: list[ScopeEntry]


# ---------------------------------------------------------------- service

def _utc(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None else None


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


def scope_fingerprint(entries: list[ScopeEntry]) -> str:
    """Content hash of the ordered scope. Later runs record it to prove which scope they used."""
    payload = [[e.scope_order, e.s_no, e.tag_number, e.tag_description, e.equipment_description, e.size_rating]
               for e in entries]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


class MilestoneService:
    def __init__(self, db: Database, files: FileStore):
        self.db = db
        self.files = files

    # ---- milestones

    def create_milestone(self, code: str, project_name: str | None, package_name: str | None) -> MilestoneView:
        code = (code or "").strip()
        project_name, package_name = _clean(project_name), _clean(package_name)
        if (problem := validate_milestone_code(code)) is not None:
            raise InvalidInputError(problem)
        if package_name and not project_name:
            raise InvalidInputError("A package requires a project.")

        try:
            with self.db.session() as s:
                if s.scalar(select(Milestone.id).where(Milestone.milestone_code == code)) is not None:
                    raise ConflictError(f"Milestone '{code}' already exists.")
                project = self._get_or_create_project(s, project_name) if project_name else None
                package = self._get_or_create_package(s, project, package_name) if package_name else None
                milestone = Milestone(milestone_code=code, project=project, package=package,
                                      status=MilestoneStatus.DRAFT)
                s.add(milestone)
                s.flush()
                milestone_id = milestone.id
        except IntegrityError as exc:
            raise ConflictError(f"Milestone '{code}' already exists.") from exc

        self.files.ensure_milestone_dirs(code)
        log.info("Created milestone %s (id=%s)", code, milestone_id)
        return self.get_milestone(milestone_id)

    def list_milestones(self) -> list[MilestoneView]:
        with self.db.session() as s:
            milestones = s.scalars(select(Milestone).order_by(Milestone.created_at.desc(), Milestone.id.desc())).all()
            counts = self._tag_counts(s)
            return [self._view(m, counts.get(m.id, 0), include_runs=False) for m in milestones]

    def get_milestone(self, milestone_id: int) -> MilestoneView:
        with self.db.session() as s:
            m = self._load(s, milestone_id)
            return self._view(m, self._tag_counts(s, milestone_id).get(m.id, 0), include_runs=True)

    # ---- scope

    def validate_scope(self, milestone_id: int, file_name: str, data: bytes) -> ScopeReport:
        with self.db.session() as s:
            self._require_unlocked(self._load(s, milestone_id))
        report, _ = self._check_scope_file(file_name, data)
        return report

    def import_scope(self, milestone_id: int, file_name: str, data: bytes) -> ScopeReport:
        """Validate and, only if there are no errors, replace the milestone's draft scope."""
        report, entries = self._check_scope_file(file_name, data)
        if not report.valid:
            raise ScopeRejectedError(report)

        with self.db.session() as s:
            m = self._load(s, milestone_id)
            self._require_unlocked(m)
            rel_path, digest = self.files.store_immutable(
                m.milestone_code, "scope", data, PurePath(file_name).suffix or ".xlsx")
            s.execute(delete(MilestoneTag).where(MilestoneTag.milestone_id == m.id))
            s.execute(insert(MilestoneTag), [
                {"milestone_id": m.id, "scope_order": e.scope_order, "source_row": e.source_row,
                 "s_no": e.s_no, "tag_number": e.tag_number, "normalized_tag": e.normalized_tag,
                 "tag_description": e.tag_description, "equipment_description": e.equipment_description,
                 "size_rating": e.size_rating}
                for e in entries])
            m.scope_file_name = PurePath(file_name).name
            m.scope_file_path = rel_path
            m.scope_file_sha256 = digest
            m.scope_sheet_name = report.sheet_name
            m.scope_imported_at = utcnow()
        log.info("Imported scope for milestone id=%s: %s tags from %s (%s)",
                 milestone_id, len(entries), file_name, digest)
        return report

    def get_scope(self, milestone_id: int) -> ScopeView:
        with self.db.session() as s:
            m = self._load(s, milestone_id)
            entries = self._entries(s, m.id)
            return ScopeView(
                milestone_id=m.id, scope_status=scope_status(m.status, len(entries)), tag_count=len(entries),
                file_name=m.scope_file_name, file_sha256=m.scope_file_sha256, sheet_name=m.scope_sheet_name,
                imported_at=_utc(m.scope_imported_at), locked_at=_utc(m.scope_locked_at),
                fingerprint=m.scope_fingerprint, tags=entries)

    def lock_scope(self, milestone_id: int) -> MilestoneView:
        with self.db.session() as s:
            m = self._load(s, milestone_id)
            if m.status == MilestoneStatus.SCOPE_LOCKED:
                raise ConflictError("The scope is already locked.")
            entries = self._entries(s, m.id)
            if not entries:
                raise ConflictError("Import a finalized tag scope before locking.")
            m.scope_fingerprint = scope_fingerprint(entries)
            m.scope_locked_at = utcnow()
            m.status = MilestoneStatus.SCOPE_LOCKED
        log.info("Locked scope for milestone id=%s (%s tags)", milestone_id, len(entries))
        return self.get_milestone(milestone_id)

    # ---- internals

    def _check_scope_file(self, file_name: str, data: bytes) -> tuple[ScopeReport, list[ScopeEntry]]:
        read = read_scope_workbook(file_name, data)
        issues = list(read.issues)
        entries: list[ScopeEntry] = []
        data_rows = 0
        if not issues:
            validation = validate_scope_rows(read.rows, read.columns)
            issues.extend(validation.issues)
            entries = validation.entries
            data_rows = validation.data_row_count
        errors = [i for i in issues if i.severity == "ERROR"]
        report = ScopeReport(
            valid=not errors,
            file_name=PurePath(file_name).name,
            file_sha256=sha256_bytes(data),
            sheet_name=read.sheet_name,
            header_row=read.header_row,
            columns={SCOPE_HEADERS[f]: letter for f, letter in read.columns.items()},
            ignored_headers=read.ignored_headers,
            data_row_count=data_rows,
            tag_count=len(entries) if not errors else 0,
            errors=errors,
            warnings=[i for i in issues if i.severity == "WARNING"],
        )
        return report, entries

    @staticmethod
    def _load(s: Session, milestone_id: int) -> Milestone:
        m = s.get(Milestone, milestone_id)
        if m is None:
            raise NotFoundError(f"Milestone {milestone_id} does not exist.")
        return m

    @staticmethod
    def _require_unlocked(m: Milestone) -> None:
        if m.status == MilestoneStatus.SCOPE_LOCKED:
            raise ConflictError(
                f"The scope of milestone '{m.milestone_code}' is locked and cannot be changed. "
                f"A corrected scope must be created as a new milestone.")

    @staticmethod
    def _entries(s: Session, milestone_id: int) -> list[ScopeEntry]:
        tags = s.scalars(select(MilestoneTag).where(MilestoneTag.milestone_id == milestone_id)
                         .order_by(MilestoneTag.scope_order)).all()
        return [ScopeEntry(t.scope_order, t.source_row, t.s_no, t.tag_number, t.normalized_tag,
                           t.tag_description, t.equipment_description, t.size_rating) for t in tags]

    @staticmethod
    def _tag_counts(s: Session, milestone_id: int | None = None) -> dict[int, int]:
        q = select(MilestoneTag.milestone_id, func.count()).group_by(MilestoneTag.milestone_id)
        if milestone_id is not None:
            q = q.where(MilestoneTag.milestone_id == milestone_id)
        return dict(s.execute(q).all())

    @staticmethod
    def _get_or_create_project(s: Session, name: str) -> Project:
        project = s.scalar(select(Project).where(Project.name == name))
        if project is None:
            project = Project(name=name)
            s.add(project)
        return project

    @staticmethod
    def _get_or_create_package(s: Session, project: Project, name: str) -> Package:
        s.flush()
        package = s.scalar(select(Package).where(Package.project_id == project.id, Package.name == name))
        if package is None:
            package = Package(project=project, name=name)
            s.add(package)
        return package

    @staticmethod
    def _view(m: Milestone, tag_count: int, include_runs: bool) -> MilestoneView:
        runs = [RunView(r.id, r.run_number, r.status, r.rules_version, _utc(r.created_at), _utc(r.completed_at))
                for r in m.runs]
        return MilestoneView(
            id=m.id, milestone_code=m.milestone_code,
            project_name=m.project.name if m.project else None,
            package_name=m.package.name if m.package else None,
            status=m.status, scope_status=scope_status(m.status, tag_count), tag_count=tag_count,
            created_at=_utc(m.created_at), updated_at=_utc(m.updated_at),
            scope_file_name=m.scope_file_name, scope_file_sha256=m.scope_file_sha256,
            scope_sheet_name=m.scope_sheet_name, scope_imported_at=_utc(m.scope_imported_at),
            scope_locked_at=_utc(m.scope_locked_at), scope_fingerprint=m.scope_fingerprint,
            run_count=len(runs), latest_run=runs[-1] if runs else None,
            runs=runs if include_runs else [],
        )
