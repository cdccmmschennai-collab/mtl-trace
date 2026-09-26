// Mirrors backend/models/schemas.py. The frontend holds no engineering logic — it only displays these.

export type ScopeStatus = "NONE" | "DRAFT" | "LOCKED";

export interface RunSummary {
  id: number;
  run_number: number;
  status: string;
  rules_version: string;
  created_at: string;
  completed_at: string | null;
}

export interface MilestoneSummary {
  id: number;
  milestone_code: string;
  project_name: string | null;
  package_name: string | null;
  status: string;
  scope_status: ScopeStatus;
  tag_count: number;
  created_at: string;
  scope_locked_at: string | null;
  run_count: number;
  latest_run: RunSummary | null;
}

export interface MilestoneDetail extends MilestoneSummary {
  updated_at: string;
  scope_file_name: string | null;
  scope_file_sha256: string | null;
  scope_sheet_name: string | null;
  scope_imported_at: string | null;
  scope_fingerprint: string | null;
  runs: RunSummary[];
}

export interface ScopeIssue {
  severity: "ERROR" | "WARNING";
  code: string;
  message: string;
  rows: number[];
  column: string | null;
  value: string | null;
}

export interface ScopeValidationReport {
  valid: boolean;
  file_name: string;
  file_sha256: string;
  sheet_name: string | null;
  header_row: number | null;
  columns: Record<string, string>;
  ignored_headers: string[];
  data_row_count: number;
  tag_count: number;
  errors: ScopeIssue[];
  warnings: ScopeIssue[];
}

export interface ScopeTag {
  scope_order: number;
  source_row: number;
  s_no: string | null;
  tag_number: string;
  tag_description: string | null;
  equipment_description: string | null;
  size_rating: string | null;
}

export interface Scope {
  milestone_id: number;
  scope_status: ScopeStatus;
  tag_count: number;
  file_name: string | null;
  file_sha256: string | null;
  sheet_name: string | null;
  imported_at: string | null;
  locked_at: string | null;
  fingerprint: string | null;
  tags: ScopeTag[];
}

// ---------------------------------------------------------------- Phase 1B: runs & sources

export interface SourceType {
  code: string;
  label: string;
  adapter_available: boolean;
}

export interface Issue {
  severity: "ERROR" | "WARNING";
  code: string;
  message: string;
  rows: number[];
  column: string | null;
  value: string | null;
}

export interface FieldBinding {
  key: string;
  label: string;
  column: string;
  header: string;
}

export interface RunSource {
  id: number;
  run_id: number;
  document_id: number;
  original_filename: string;
  source_type: string | null;
  source_type_label: string | null;
  processing_status: "PROCESSED" | "PROCESSED_WITH_WARNINGS" | "FAILED";
  file_size: number;
  sha256: string;
  uploaded_at: string;
  processed_at: string;
  document_date: string | null;
  revision: string | null;
  sheet_name: string | null;
  header_row: number | null;
  row_count: number | null;
  recognized_tag_count: number | null;
  unique_tag_count: number | null;
  duplicate_tag_count: number | null;
  matched_tag_count: number | null;
  unmatched_tag_count: number | null;
  scope_tags_without_record: number | null;
  scope_tag_count: number;
  attributes_provided: string[];
  attribute_counts: Record<string, number>;
  mapping: FieldBinding[];
  headers_found: string[];
  skipped_sheets: { sheet: string; reason: string }[];
  duplicates: { tag: string; rows: number[]; in_scope: boolean }[];
  out_of_scope: { tag: string; rows: number[] }[];
  rows_without_tag_key: number[];
  errors: Issue[];
  warnings: Issue[];
}

export interface Run {
  id: number;
  milestone_id: number;
  milestone_code: string;
  run_number: number;
  status: string;
  rules_version: string;
  scope_fingerprint: string;
  scope_tag_count: number;
  created_at: string;
  notes: string | null;
  sources: RunSource[];
}

export interface SourceRow {
  row: number;
  source_tag: string | null;
  in_scope: boolean;
  values: Record<string, string | null>;
  location: Record<string, string | number | null>;
}

export interface SourceRowsPage {
  total: number;
  offset: number;
  rows: SourceRow[];
}

// ---------------------------------------------------------------- Phase 1C: consolidation

export type CellState = "PRESENT" | "ABSENT_VALUE" | "ABSENT_TAG" | "CONFLICTING_DUPLICATE";
export type SourceRowState = "ROW" | "NO_ROW" | "DUPLICATE_ROWS";

export interface TypeRef {
  code: string;
  label: string;
}

export interface AttributeStateCounts {
  present: number;
  absent_value: number;
  absent_tag: number;
  duplicate: number;
}

export interface SourceCoverage {
  source_type: string;
  label: string;
  documents: number;
  rows: number;
  rows_without_tag_key: number;
  unique_tags: number;
  duplicate_tag_count: number;
  duplicate_tags: { tag: string; rows: number }[];
  in_scope_tags: number;
  out_of_scope_tag_count: number;
  out_of_scope_tags: { tag: string; rows: number[] }[];
  scope_tags_without_row: number;
  attributes_provided: string[];
  attributes: Record<string, AttributeStateCounts>;
  tag_as_per_doc_equal: number;
  tag_as_per_doc_differs: number;
  tag_differences: { milestone_tag: string; tag_as_per_doc: string }[];
}

export interface OutputArtifact {
  id: number;
  run_id: number;
  kind: string;
  file_name: string;
  stored_path: string;
  sha256: string;
  file_size: number;
  generated_at: string;
}

export interface Consolidation {
  run_id: number;
  run_number: number;
  milestone_id: number;
  milestone_code: string;
  consolidated_at: string;
  scope_fingerprint: string;
  scope_tag_count: number;
  canonical_row_count: number;
  canonical_cell_count: number;
  attributes: TypeRef[];
  source_types: (TypeRef & { documents: number })[];
  not_in_run: TypeRef[];
  documents: {
    run_source_id: number;
    document_id: number;
    file_name: string;
    source_type: string | null;
    sha256: string;
    processing_status: string;
    included: boolean;
    excluded_reason: string | null;
  }[];
  coverage: SourceCoverage[];
  workbook: { summary_sheet: string; summary_headers: string[]; sheets: { name: string; headers: string[] }[] };
  outputs: OutputArtifact[];
}

export interface Provenance {
  record_id: number;
  source_tag: string | null;
  raw_value: string | null;
  document: string | null;
  sheet: string | null;
  row: number | null;
  cell: string | null;
  document_reference: string | null;
  page: string | null;
}

export interface CanonicalCell {
  state: CellState;
  value: string | null;
  provenance: Provenance[];
}

export interface CanonicalRow {
  milestone_tag_id: number;
  scope_order: number;
  s_no: string | null;
  tag_number: string;
  tag_description: string | null;
  equipment_description: string | null;
  size_rating: string | null;
  source_rows: Record<string, SourceRowState>;
  cells: Record<string, Record<string, CanonicalCell>>;
}

export interface CanonicalPage {
  run_id: number;
  total: number;
  filtered_total: number;
  offset: number;
  source_types: string[];
  attributes: string[];
  rows: CanonicalRow[];
}

export type ComparisonStatus = "MATCH" | "MISMATCH" | "REVIEW REQUIRED";

export interface AttributeComparison {
  code: string;
  label: string;
  sheet_name: string;
  provided_by: string[];
  counts: Record<ComparisonStatus, number>;
  no_source_value: number;
  reasons: Record<string, number>;
}

export interface Comparison {
  run_id: number;
  run_number: number;
  milestone_id: number;
  milestone_code: string;
  rules_version: string;
  compared_at: string;
  scope_tag_count: number;
  source_types: (TypeRef & { rank: number })[];
  totals: Record<ComparisonStatus, number>;
  /** tag × attribute rows left blank: no source holds a value, so no FINAL and no STATUS */
  no_source_value: number;
  attributes: AttributeComparison[];
  workbook: { summary_sheet: string; summary_headers: string[]; sheets: { name: string; headers: string[] }[] };
  output: OutputArtifact | null;
}
