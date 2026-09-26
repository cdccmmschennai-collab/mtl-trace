"""Schema: PROJECT, PACKAGE, MILESTONE, MILESTONE_TAG, PROCESSING_RUN (Phase 1A);
SOURCE_DOCUMENT, RUN_SOURCE, SOURCE_RECORD (Phase 1B); RUN_CONSOLIDATION, CANONICAL_CELL,
OUTPUT_ARTIFACT (Phase 1C); RUN_COMPARISON, COMPARISON_RESULT (Phase 1D).

A later phase may add REVIEW_DECISION, hanging off PROCESSING_RUN by foreign key. Nothing here is specific to one source type: source_type is a value,
never a column, so a new source type extends the data without a schema change.
"""

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC; SQLite has no timezone type. Views re-attach UTC on the way out."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200, collation="NOCASE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Package(Base):
    __tablename__ = "package"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(200, collation="NOCASE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    project: Mapped[Project] = relationship()


class Milestone(Base):
    __tablename__ = "milestone"
    __table_args__ = (CheckConstraint("status IN ('DRAFT', 'SCOPE_LOCKED')", name="ck_milestone_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_code: Mapped[str] = mapped_column(String(64, collation="NOCASE"), unique=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("package.id"))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")

    # Provenance of the imported scope workbook (stored content-addressed under scope/).
    scope_file_name: Mapped[str | None] = mapped_column(Text)
    scope_file_path: Mapped[str | None] = mapped_column(Text)
    scope_file_sha256: Mapped[str | None] = mapped_column(String(64))
    scope_sheet_name: Mapped[str | None] = mapped_column(Text)
    scope_imported_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Set once, at lock; the triggers below make them irreversible.
    scope_locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    scope_fingerprint: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    project: Mapped[Project | None] = relationship()
    package: Mapped[Package | None] = relationship()
    runs: Mapped[list["ProcessingRun"]] = relationship(order_by="ProcessingRun.run_number")


class MilestoneTag(Base):
    __tablename__ = "milestone_tag"
    __table_args__ = (
        UniqueConstraint("milestone_id", "normalized_tag"),   # the scope-authority rule, structurally
        UniqueConstraint("milestone_id", "scope_order"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestone.id"), index=True)
    scope_order: Mapped[int] = mapped_column(Integer)
    source_row: Mapped[int] = mapped_column(Integer)          # worksheet row in the scope file
    s_no: Mapped[str | None] = mapped_column(Text)            # text: '0001' must round-trip
    tag_number: Mapped[str] = mapped_column(Text)
    normalized_tag: Mapped[str] = mapped_column(Text)
    tag_description: Mapped[str | None] = mapped_column(Text)
    equipment_description: Mapped[str | None] = mapped_column(Text)
    size_rating: Mapped[str | None] = mapped_column(Text)


class ProcessingRun(Base):
    """One processing attempt against a milestone's locked scope. Created from Phase 1B onward."""
    __tablename__ = "processing_run"
    __table_args__ = (UniqueConstraint("milestone_id", "run_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestone.id"), index=True)
    run_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    rules_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list["RunSource"]] = relationship(order_by="RunSource.id")


class SourceDocument(Base):
    """A physical uploaded file, identified by content hash. May participate in several runs."""
    __tablename__ = "source_document"
    __table_args__ = (UniqueConstraint("milestone_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestone.id"), index=True)
    source_type: Mapped[str | None] = mapped_column(String(20))    # None until identified
    original_filename: Mapped[str] = mapped_column(Text)
    stored_path: Mapped[str] = mapped_column(Text)                  # sources/<sha256>.<ext>, relative to MTL_DATA
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    document_date: Mapped[date | None] = mapped_column(Date)        # RULE-P2 input; user-supplied
    revision: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RunSource(Base):
    """One document's participation in one run, with that run's processing outcome and statistics."""
    __tablename__ = "run_source"
    __table_args__ = (UniqueConstraint("run_id", "source_document_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_document.id"))
    source_type: Mapped[str | None] = mapped_column(String(20))
    processing_status: Mapped[str] = mapped_column(String(30))
    sheet_name: Mapped[str | None] = mapped_column(Text)
    header_row: Mapped[int | None] = mapped_column(Integer)
    row_count: Mapped[int | None] = mapped_column(Integer)
    recognized_tag_count: Mapped[int | None] = mapped_column(Integer)    # rows with a usable tag key
    unique_tag_count: Mapped[int | None] = mapped_column(Integer)
    duplicate_tag_count: Mapped[int | None] = mapped_column(Integer)
    matched_tag_count: Mapped[int | None] = mapped_column(Integer)
    unmatched_tag_count: Mapped[int | None] = mapped_column(Integer)     # source keys outside the scope
    scope_tags_without_record: Mapped[int | None] = mapped_column(Integer)
    report: Mapped[str] = mapped_column(Text, default="{}")               # JSON: mapping, issues, details
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    document: Mapped[SourceDocument] = relationship()


class SourceRecord(Base):
    """One extracted value: (source row × attribute), stored even when empty so later phases can tell
    ABSENT_VALUE (row present, cell empty) from ABSENT_TAG (no row). Immutable once written."""
    __tablename__ = "source_record"
    __table_args__ = (Index("ix_source_record_run_attr", "run_id", "attribute"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"))
    run_source_id: Mapped[int] = mapped_column(ForeignKey("run_source.id"), index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_document.id"))
    source_type: Mapped[str] = mapped_column(String(20))
    source_row_index: Mapped[int] = mapped_column(Integer)
    source_tag: Mapped[str | None] = mapped_column(Text)          # join key exactly as in the file
    normalized_tag: Mapped[str | None] = mapped_column(Text)
    milestone_tag_id: Mapped[int | None] = mapped_column(ForeignKey("milestone_tag.id"))   # None = outside scope
    attribute: Mapped[str] = mapped_column(String(20))
    raw_value: Mapped[str | None] = mapped_column(Text)            # exact cell text, spaces kept
    normalized_value: Mapped[str | None] = mapped_column(Text)     # trimmed; no equivalence rules
    source_location: Mapped[str] = mapped_column(Text)             # JSON provenance


class RunConsolidation(Base):
    """The one consolidation of a run (Phase 1C). Written once; the run's sources are then frozen."""
    __tablename__ = "run_consolidation"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), unique=True)
    scope_fingerprint: Mapped[str] = mapped_column(String(64))     # the locked scope it was built on
    tag_count: Mapped[int] = mapped_column(Integer)
    cell_count: Mapped[int] = mapped_column(Integer)
    source_types: Mapped[str] = mapped_column(Text)                # JSON list, display order
    run_source_ids: Mapped[str] = mapped_column(Text)              # JSON list of participating RUN_SOURCE ids
    summary: Mapped[str] = mapped_column(Text)                     # JSON coverage report
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CanonicalCell(Base):
    """Canonical dataset, stored long: milestone tag × attribute × participating source type (TRD §9).

    `state` distinguishes PRESENT / ABSENT_VALUE / ABSENT_TAG / CONFLICTING_DUPLICATE. A source type not
    in the run has no cells at all. `source_record_ids` (JSON) anchors provenance — one id, or every
    duplicate candidate. Values are copied from the source record, unmodified.
    """
    __tablename__ = "canonical_cell"
    __table_args__ = (
        UniqueConstraint("run_id", "milestone_tag_id", "attribute", "source_type"),
        CheckConstraint("state IN ('PRESENT', 'ABSENT_VALUE', 'ABSENT_TAG', 'CONFLICTING_DUPLICATE')",
                        name="ck_canonical_cell_state"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), index=True)
    milestone_tag_id: Mapped[int] = mapped_column(ForeignKey("milestone_tag.id"))
    attribute: Mapped[str] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(30))
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))   # single-record cells
    source_record_ids: Mapped[str] = mapped_column(Text, default="[]")


class RunComparison(Base):
    """The one comparison of a consolidated run (Phase 1D). Written once, under a stamped rules version."""
    __tablename__ = "run_comparison"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), unique=True)
    rules_version: Mapped[str] = mapped_column(String(30))
    source_types: Mapped[str] = mapped_column(Text)                # JSON list, priority order
    summary: Mapped[str] = mapped_column(Text)                     # JSON counts per attribute
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ComparisonResult(Base):
    """One comparison verdict: milestone tag × attribute. `status` is NULL (and `final_value` NULL) when no
    applicable source holds a value — blank is not a status."""
    __tablename__ = "comparison_result"
    __table_args__ = (
        UniqueConstraint("run_id", "milestone_tag_id", "attribute"),
        CheckConstraint("status IS NULL OR status IN ('MATCH', 'MISMATCH', 'REVIEW REQUIRED')",
                        name="ck_comparison_result_status"),
        CheckConstraint("status IS NOT NULL OR final_value IS NULL", name="ck_comparison_result_blank"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), index=True)
    milestone_tag_id: Mapped[int] = mapped_column(ForeignKey("milestone_tag.id"))
    attribute: Mapped[str] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    final_value: Mapped[str | None] = mapped_column(Text)
    final_source_type: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(40))
    remarks: Mapped[str | None] = mapped_column(Text)
    compared_sources: Mapped[str] = mapped_column(Text, default="[]")   # JSON list of source types with a value


class OutputArtifact(Base):
    """A generated file (canonical snapshot, consolidated workbook, …). Hashed at generation; never rewritten."""
    __tablename__ = "output_artifact"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_run.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    file_name: Mapped[str] = mapped_column(Text)
    stored_path: Mapped[str] = mapped_column(Text)                 # relative to MTL_DATA
    sha256: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# Scope immutability is enforced by the database itself, not only by the service layer, so no code
# path — including a future bug or a manual SQL session — can silently change a locked tag universe.
_LOCKED = "(SELECT scope_locked_at FROM milestone WHERE id = {ref}.milestone_id) IS NOT NULL"
TRIGGERS = [
    f"""CREATE TRIGGER IF NOT EXISTS trg_milestone_tag_insert_locked BEFORE INSERT ON milestone_tag
        WHEN {_LOCKED.format(ref='NEW')}
        BEGIN SELECT RAISE(ABORT, 'milestone scope is locked'); END""",
    f"""CREATE TRIGGER IF NOT EXISTS trg_milestone_tag_update_locked BEFORE UPDATE ON milestone_tag
        WHEN {_LOCKED.format(ref='OLD')}
        BEGIN SELECT RAISE(ABORT, 'milestone scope is locked'); END""",
    f"""CREATE TRIGGER IF NOT EXISTS trg_milestone_tag_delete_locked BEFORE DELETE ON milestone_tag
        WHEN {_LOCKED.format(ref='OLD')}
        BEGIN SELECT RAISE(ABORT, 'milestone scope is locked'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_milestone_lock_irreversible BEFORE UPDATE ON milestone
        WHEN OLD.scope_locked_at IS NOT NULL AND (
             NEW.scope_locked_at IS NOT OLD.scope_locked_at
          OR NEW.scope_fingerprint IS NOT OLD.scope_fingerprint
          OR NEW.scope_file_sha256 IS NOT OLD.scope_file_sha256
          OR NEW.scope_file_path IS NOT OLD.scope_file_path
          OR NEW.status = 'DRAFT')
        BEGIN SELECT RAISE(ABORT, 'milestone scope is locked'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_milestone_delete_locked BEFORE DELETE ON milestone
        WHEN OLD.scope_locked_at IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'milestone scope is locked'); END""",
    # Runs always operate on a locked scope.
    f"""CREATE TRIGGER IF NOT EXISTS trg_run_requires_locked_scope BEFORE INSERT ON processing_run
        WHEN NOT {_LOCKED.format(ref='NEW')}
        BEGIN SELECT RAISE(ABORT, 'processing run requires a locked milestone scope'); END""",
    # Source evidence is immutable: a revised file is a new document, a revised result is a new run.
    """CREATE TRIGGER IF NOT EXISTS trg_source_document_immutable BEFORE UPDATE ON source_document
        WHEN NEW.sha256 IS NOT OLD.sha256 OR NEW.stored_path IS NOT OLD.stored_path
          OR NEW.file_size IS NOT OLD.file_size OR NEW.milestone_id IS NOT OLD.milestone_id
        BEGIN SELECT RAISE(ABORT, 'source documents are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_source_record_no_update BEFORE UPDATE ON source_record
        BEGIN SELECT RAISE(ABORT, 'source records are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_source_record_no_delete BEFORE DELETE ON source_record
        BEGIN SELECT RAISE(ABORT, 'source records are immutable'); END""",
    # Phase 1C — a consolidated run is frozen: no new documents or records, no way back to an earlier state.
    """CREATE TRIGGER IF NOT EXISTS trg_run_source_frozen BEFORE INSERT ON run_source
        WHEN (SELECT status FROM processing_run WHERE id = NEW.run_id) = 'CONSOLIDATED'
        BEGIN SELECT RAISE(ABORT, 'run is consolidated; its sources are frozen'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_source_record_frozen BEFORE INSERT ON source_record
        WHEN (SELECT status FROM processing_run WHERE id = NEW.run_id) = 'CONSOLIDATED'
        BEGIN SELECT RAISE(ABORT, 'run is consolidated; its sources are frozen'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_run_consolidated_forward_only BEFORE UPDATE ON processing_run
        WHEN OLD.status = 'CONSOLIDATED' AND NEW.status IN ('CREATED', 'DOCUMENTS_UPLOADED')
        BEGIN SELECT RAISE(ABORT, 'a consolidated run cannot return to an earlier state'); END""",
    *[f"""CREATE TRIGGER IF NOT EXISTS trg_{t}_no_{op.lower()} BEFORE {op} ON {t}
        BEGIN SELECT RAISE(ABORT, '{t} rows are immutable'); END"""
      for t in ("canonical_cell", "run_consolidation", "output_artifact", "run_comparison", "comparison_result")
      for op in ("UPDATE", "DELETE")],
    # Phase 1D — comparison only on a consolidated run.
    """CREATE TRIGGER IF NOT EXISTS trg_comparison_requires_consolidation BEFORE INSERT ON run_comparison
        WHEN (SELECT status FROM processing_run WHERE id = NEW.run_id) IS NOT 'CONSOLIDATED'
        BEGIN SELECT RAISE(ABORT, 'comparison requires a consolidated run'); END""",
]
