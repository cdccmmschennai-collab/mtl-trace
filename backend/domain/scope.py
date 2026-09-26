"""Finalized tag scope: column definitions and validation rules.

The scope columns and their header text come from the working file
`input/references/5.MTL-DATA MISMATCH COMPARISION.xlsx` (sheet `TAG NUMBER COMPARISION`, A:E), including
the template's own spelling `TAG DISCRIPTION`. Headers are matched by normalized meaning, never by
column position.

Validation never silently discards a row. Every row that carries any data either becomes a scope tag
or produces an ERROR that blocks the import. Only fully empty rows are skipped, and embedded ones are
reported as WARNINGs.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from backend.domain.headers import normalize_header
from backend.domain.issues import Issue, Severity
from backend.domain.tags import normalize_tag
from backend.domain.values import cell_text


class ScopeField(StrEnum):
    S_NO = "s_no"
    TAG_NUMBER = "tag_number"
    TAG_DESCRIPTION = "tag_description"
    EQUIPMENT_DESCRIPTION = "equipment_description"
    SIZE_RATING = "size_rating"


# Template header text, in template order. All five are required columns.
SCOPE_HEADERS: dict[ScopeField, str] = {
    ScopeField.S_NO: "S.NO",
    ScopeField.TAG_NUMBER: "TAG NUMBER",
    ScopeField.TAG_DESCRIPTION: "TAG DISCRIPTION",
    ScopeField.EQUIPMENT_DESCRIPTION: "EQUIPMENT DESCRIPTION",
    ScopeField.SIZE_RATING: "SIZE & RATING",
}


NORMALIZED_SCOPE_HEADERS: dict[str, ScopeField] = {normalize_header(h): f for f, h in SCOPE_HEADERS.items()}


ScopeIssue = Issue


@dataclass(frozen=True)
class RawScopeRow:
    """One worksheet row below the header, as read from the file."""
    row_number: int
    values: dict[ScopeField, object]
    is_empty: bool                   # every cell in the row is blank, including non-scope columns


@dataclass(frozen=True)
class ScopeEntry:
    scope_order: int                 # 1-based position in the finalized scope
    source_row: int                  # worksheet row it came from (provenance)
    s_no: str | None                 # kept as text: '0001' must round-trip
    tag_number: str
    normalized_tag: str
    tag_description: str | None
    equipment_description: str | None
    size_rating: str | None


@dataclass
class ScopeValidation:
    entries: list[ScopeEntry] = field(default_factory=list)
    issues: list[ScopeIssue] = field(default_factory=list)
    data_row_count: int = 0

    @property
    def errors(self) -> list[ScopeIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ScopeIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def valid(self) -> bool:
        return not self.errors




def validate_scope_rows(rows: list[RawScopeRow], columns: dict[ScopeField, str]) -> ScopeValidation:
    """Validate the data rows of a scope sheet whose required columns have already been located."""
    result = ScopeValidation()
    tag_col = columns.get(ScopeField.TAG_NUMBER)
    sno_col = columns.get(ScopeField.S_NO)

    empty_rows: list[int] = []
    trimmed_rows: list[int] = []
    blank_sno_rows: list[int] = []
    numeric_sno_rows: list[int] = []
    rows_by_tag: dict[str, list[int]] = defaultdict(list)
    rows_by_sno: dict[str, list[int]] = defaultdict(list)
    blank_tag_rows: list[int] = []

    for row in rows:
        if row.is_empty:
            empty_rows.append(row.row_number)
            continue
        result.data_row_count += 1

        raw_tag = row.values.get(ScopeField.TAG_NUMBER)
        if cell_text(raw_tag) is None:
            blank_tag_rows.append(row.row_number)
            continue
        if not isinstance(raw_tag, str):
            result.issues.append(ScopeIssue(
                Severity.ERROR, "MALFORMED_TAG",
                f"TAG NUMBER holds a {type(raw_tag).__name__} value, not text. The value may have been "
                f"altered by Excel (e.g. lost leading zeros); format the cell as text and re-import.",
                rows=(row.row_number,), column=tag_col, value=str(raw_tag)))
            continue
        if any(ch in raw_tag for ch in "\r\n\t"):
            result.issues.append(ScopeIssue(
                Severity.ERROR, "MALFORMED_TAG",
                "TAG NUMBER contains a line break or tab, which suggests several tags in one cell.",
                rows=(row.row_number,), column=tag_col, value=raw_tag))
            continue

        tag = raw_tag.strip()
        if tag != raw_tag:
            trimmed_rows.append(row.row_number)
        normalized = normalize_tag(tag)
        rows_by_tag[normalized].append(row.row_number)

        raw_sno = row.values.get(ScopeField.S_NO)
        s_no = cell_text(raw_sno)
        if s_no is None:
            blank_sno_rows.append(row.row_number)
        else:
            if not isinstance(raw_sno, str):
                numeric_sno_rows.append(row.row_number)
            rows_by_sno[s_no].append(row.row_number)

        result.entries.append(ScopeEntry(
            scope_order=len(result.entries) + 1,
            source_row=row.row_number,
            s_no=s_no,
            tag_number=tag,
            normalized_tag=normalized,
            tag_description=cell_text(row.values.get(ScopeField.TAG_DESCRIPTION)),
            equipment_description=cell_text(row.values.get(ScopeField.EQUIPMENT_DESCRIPTION)),
            size_rating=cell_text(row.values.get(ScopeField.SIZE_RATING)),
        ))

    if blank_tag_rows:
        result.issues.append(ScopeIssue(
            Severity.ERROR, "BLANK_TAG",
            f"{len(blank_tag_rows)} row(s) contain data but have no TAG NUMBER.",
            rows=tuple(blank_tag_rows), column=tag_col))

    for normalized, row_numbers in rows_by_tag.items():
        if len(row_numbers) > 1:
            result.issues.append(ScopeIssue(
                Severity.ERROR, "DUPLICATE_TAG",
                f"TAG NUMBER '{normalized}' appears {len(row_numbers)} times "
                f"(compared ignoring case and surrounding spaces).",
                rows=tuple(row_numbers), column=tag_col, value=normalized))

    if result.data_row_count == 0:
        result.issues.append(ScopeIssue(
            Severity.ERROR, "EMPTY_SCOPE", "The scope sheet has a header row but no tag rows."))

    if empty_rows:
        result.issues.append(ScopeIssue(
            Severity.WARNING, "EMPTY_ROW",
            f"{len(empty_rows)} completely empty row(s) inside the tag list were skipped.",
            rows=tuple(empty_rows)))
    if trimmed_rows:
        result.issues.append(ScopeIssue(
            Severity.WARNING, "TAG_WHITESPACE_TRIMMED",
            f"{len(trimmed_rows)} TAG NUMBER value(s) had leading/trailing spaces, which were removed.",
            rows=tuple(trimmed_rows), column=tag_col))
    if blank_sno_rows:
        result.issues.append(ScopeIssue(
            Severity.WARNING, "BLANK_SNO", f"{len(blank_sno_rows)} row(s) have no S.NO.",
            rows=tuple(blank_sno_rows), column=sno_col))
    if numeric_sno_rows:
        result.issues.append(ScopeIssue(
            Severity.WARNING, "SNO_NOT_TEXT",
            f"{len(numeric_sno_rows)} S.NO value(s) are numbers rather than text; any leading zeros "
            f"were lost in the source file.",
            rows=tuple(numeric_sno_rows), column=sno_col))
    for s_no, row_numbers in rows_by_sno.items():
        if len(row_numbers) > 1:
            result.issues.append(ScopeIssue(
                Severity.WARNING, "DUPLICATE_SNO", f"S.NO '{s_no}' appears {len(row_numbers)} times.",
                rows=tuple(row_numbers), column=sno_col, value=s_no))

    return result
