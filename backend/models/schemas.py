"""Public API contract. Built from service views, never from ORM rows."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MilestoneCreate(BaseModel):
    milestone_code: str = Field(min_length=1, max_length=64)
    project_name: str | None = Field(default=None, max_length=200)
    package_name: str | None = Field(default=None, max_length=200)


class RunSummary(_Out):
    id: int
    run_number: int
    status: str
    rules_version: str
    created_at: datetime
    completed_at: datetime | None


class MilestoneSummary(_Out):
    id: int
    milestone_code: str
    project_name: str | None
    package_name: str | None
    status: str
    scope_status: str
    tag_count: int
    created_at: datetime
    scope_locked_at: datetime | None
    run_count: int
    latest_run: RunSummary | None


class MilestoneDetail(MilestoneSummary):
    updated_at: datetime
    scope_file_name: str | None
    scope_file_sha256: str | None
    scope_sheet_name: str | None
    scope_imported_at: datetime | None
    scope_fingerprint: str | None
    runs: list[RunSummary]


class ScopeIssueOut(_Out):
    severity: str
    code: str
    message: str
    rows: list[int]
    column: str | None
    value: str | None


class ScopeValidationReport(_Out):
    valid: bool
    file_name: str
    file_sha256: str
    sheet_name: str | None
    header_row: int | None
    columns: dict[str, str]
    ignored_headers: list[str]
    data_row_count: int
    tag_count: int
    errors: list[ScopeIssueOut]
    warnings: list[ScopeIssueOut]


class ScopeImportResult(BaseModel):
    report: ScopeValidationReport
    milestone: MilestoneDetail


class ScopeTag(_Out):
    scope_order: int
    source_row: int
    s_no: str | None
    tag_number: str
    tag_description: str | None
    equipment_description: str | None
    size_rating: str | None


class ScopeOut(_Out):
    milestone_id: int
    scope_status: str
    tag_count: int
    file_name: str | None
    file_sha256: str | None
    sheet_name: str | None
    imported_at: datetime | None
    locked_at: datetime | None
    fingerprint: str | None
    tags: list[ScopeTag]


# ---------------------------------------------------------------- Phase 1B: runs & sources

class RunCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    base_run_id: int | None = None          # start from this run's successfully processed documents


class SourceTypeOut(_Out):
    code: str
    label: str
    adapter_available: bool
    verified: bool


class IssueOut(ScopeIssueOut):
    pass


class FieldBinding(BaseModel):
    key: str
    label: str
    column: str
    header: str


class SkippedSheet(BaseModel):
    sheet: str
    reason: str


class DuplicateSourceTag(BaseModel):
    tag: str
    rows: list[int]
    in_scope: bool


class OutOfScopeTag(BaseModel):
    tag: str
    rows: list[int]


class RunSourceOut(_Out):
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
    mapping: list[FieldBinding]
    headers_found: list[str]
    skipped_sheets: list[SkippedSheet]
    duplicates: list[DuplicateSourceTag]
    out_of_scope: list[OutOfScopeTag]
    rows_without_tag_key: list[int]
    errors: list[IssueOut]
    warnings: list[IssueOut]


class RunOut(_Out):
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
    sources: list[RunSourceOut]


class SourceIdentificationOut(_Out):
    file_name: str
    sha256: str
    file_size: int
    source_type: str | None
    source_type_label: str | None
    sheet_name: str | None
    header_row: int | None
    row_count: int
    attributes_provided: list[str]
    mapping: list[FieldBinding]
    headers_found: list[str]
    skipped_sheets: list[SkippedSheet]
    errors: list[IssueOut]
    warnings: list[IssueOut]


class SourceRowOut(_Out):
    row: int
    source_tag: str | None
    in_scope: bool
    values: dict[str, str | None]
    location: dict


class SourceRowsOut(_Out):
    total: int
    offset: int
    rows: list[SourceRowOut]


# ---------------------------------------------------------------- Phase 1C: consolidation

class TypeRef(BaseModel):
    code: str
    label: str


class ParticipatingType(TypeRef):
    documents: int


class ConsolidationDocument(BaseModel):
    run_source_id: int
    document_id: int
    file_name: str
    source_type: str | None
    sha256: str
    processing_status: str
    included: bool
    excluded_reason: str | None


class AttributeStateCounts(BaseModel):
    present: int
    absent_value: int
    absent_tag: int
    duplicate: int


class TagCount(BaseModel):
    tag: str
    rows: int


class TagRows(BaseModel):
    tag: str
    rows: list[int]


class TagDifference(BaseModel):
    milestone_tag: str
    tag_as_per_doc: str


class SourceCoverageOut(BaseModel):
    source_type: str
    label: str
    documents: int
    rows: int
    rows_without_tag_key: int
    unique_tags: int
    duplicate_tag_count: int
    duplicate_tags: list[TagCount]
    in_scope_tags: int
    out_of_scope_tag_count: int
    out_of_scope_tags: list[TagRows]
    scope_tags_without_row: int
    attributes_provided: list[str]
    attributes: dict[str, AttributeStateCounts]
    tag_as_per_doc_equal: int
    tag_as_per_doc_differs: int
    tag_differences: list[TagDifference]


class WorkbookSheetOut(BaseModel):
    name: str
    headers: list[str]


class WorkbookStructureOut(BaseModel):
    summary_sheet: str
    summary_headers: list[str]
    sheets: list[WorkbookSheetOut]


class OutputOut(_Out):
    id: int
    run_id: int
    kind: str
    file_name: str
    stored_path: str
    sha256: str
    file_size: int
    generated_at: datetime


class ConsolidationOut(_Out):
    run_id: int
    run_number: int
    milestone_id: int
    milestone_code: str
    consolidated_at: datetime
    scope_fingerprint: str
    scope_tag_count: int
    canonical_row_count: int
    canonical_cell_count: int
    attributes: list[TypeRef]
    source_types: list[ParticipatingType]
    not_in_run: list[TypeRef]
    documents: list[ConsolidationDocument]
    coverage: list[SourceCoverageOut]
    workbook: WorkbookStructureOut
    outputs: list[OutputOut]


class ProvenanceOut(BaseModel):
    record_id: int
    source_tag: str | None
    raw_value: str | None
    document: str | None
    sheet: str | None
    row: int | None
    cell: str | None
    document_reference: str | None
    page: str | None


class CanonicalCellOut(BaseModel):
    state: str
    value: str | None
    provenance: list[ProvenanceOut]


class CanonicalRowOut(_Out):
    milestone_tag_id: int
    scope_order: int
    s_no: str | None
    tag_number: str
    tag_description: str | None
    equipment_description: str | None
    size_rating: str | None
    source_rows: dict[str, str]
    cells: dict[str, dict[str, CanonicalCellOut]]


class CanonicalPageOut(_Out):
    run_id: int
    total: int
    filtered_total: int
    offset: int
    source_types: list[str]
    attributes: list[str]
    rows: list[CanonicalRowOut]


# ---------------------------------------------------------------- Phase 1D: comparison

class RankedType(TypeRef):
    rank: int


class AttributeComparisonOut(BaseModel):
    code: str
    label: str
    sheet_name: str
    provided_by: list[str]
    counts: dict[str, int]
    no_source_value: int
    reasons: dict[str, int]


class ComparisonOut(_Out):
    run_id: int
    run_number: int
    milestone_id: int
    milestone_code: str
    rules_version: str
    compared_at: datetime
    scope_tag_count: int
    source_types: list[RankedType]
    totals: dict[str, int]
    no_source_value: int
    attributes: list[AttributeComparisonOut]
    workbook: WorkbookStructureOut
    output: OutputOut | None
