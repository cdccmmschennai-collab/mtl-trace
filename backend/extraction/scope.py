"""Locate and read the finalized tag scope inside a workbook.

The scope sheet is found by its headers, not by sheet position or name: the real working file has
`SUMMERY` first and the scope on `TAG NUMBER COMPARISION`. A sheet qualifies when one of its first
rows carries all five template headers. If no sheet, or more than one sheet, qualifies, the reader
refuses to guess and reports every header it found.
"""

import io
import zipfile
from dataclasses import dataclass, field

import openpyxl
from openpyxl.utils import get_column_letter

from backend.domain.scope import (
    NORMALIZED_SCOPE_HEADERS,
    SCOPE_HEADERS,
    RawScopeRow,
    ScopeField,
    ScopeIssue,
    Severity,
    cell_text,
    normalize_header,
)

HEADER_SEARCH_ROWS = 20
SUPPORTED_EXTENSIONS = (".xlsx", ".xlsm")


@dataclass
class ScopeSheetRead:
    issues: list[ScopeIssue] = field(default_factory=list)
    sheet_name: str | None = None
    header_row: int | None = None
    columns: dict[ScopeField, str] = field(default_factory=dict)       # field -> column letter
    ignored_headers: list[str] = field(default_factory=list)
    rows: list[RawScopeRow] = field(default_factory=list)


@dataclass
class _HeaderCandidate:
    sheet_name: str
    header_row: int                                   # 1-based
    positions: dict[ScopeField, list[int]]            # field -> 0-based column indexes
    headers: list[str]                                # non-empty header texts, as found
    ignored: list[str]


def _error(code: str, message: str, **kw) -> ScopeIssue:
    return ScopeIssue(Severity.ERROR, code, message, **kw)


def _find_header(sheet_name: str, rows: list[tuple]) -> _HeaderCandidate | None:
    for idx, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        positions: dict[ScopeField, list[int]] = {}
        ignored: list[str] = []
        for col, value in enumerate(row):
            scope_field = NORMALIZED_SCOPE_HEADERS.get(normalize_header(value))
            if scope_field is not None:
                positions.setdefault(scope_field, []).append(col)
            elif cell_text(value) is not None:
                ignored.append(str(value).strip())
        if ScopeField.TAG_NUMBER in positions:
            headers = [str(v).strip() for v in row if cell_text(v) is not None]
            return _HeaderCandidate(sheet_name, idx + 1, positions, headers, ignored)
    return None


def _first_nonempty_row(rows: list[tuple]) -> list[str]:
    for row in rows[:HEADER_SEARCH_ROWS]:
        values = [str(v).strip() for v in row if cell_text(v) is not None]
        if values:
            return values
    return []


def read_scope_workbook(file_name: str, data: bytes) -> ScopeSheetRead:
    result = ScopeSheetRead()

    if not file_name.lower().endswith(SUPPORTED_EXTENSIONS):
        result.issues.append(_error(
            "UNSUPPORTED_FILE_TYPE",
            f"'{file_name}' is not an Excel workbook (.xlsx / .xlsm). Legacy .xls files must be saved "
            f"as .xlsx first."))
        return result

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        result.issues.append(_error("UNREADABLE_WORKBOOK", f"The file could not be opened as a workbook: {exc}"))
        return result

    try:
        sheets = {ws.title: [tuple(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    finally:
        wb.close()

    candidates = [c for name, rows in sheets.items() if (c := _find_header(name, rows)) is not None]
    complete = [c for c in candidates if len(c.positions) == len(SCOPE_HEADERS)]

    if len(complete) > 1:
        result.issues.append(_error(
            "SCOPE_SHEET_AMBIGUOUS",
            "More than one sheet carries the scope headers, so the scope sheet cannot be identified: "
            + ", ".join(f"'{c.sheet_name}'" for c in complete)
            + ". Upload a workbook containing a single scope sheet."))
        return result

    if not complete:
        required = ", ".join(SCOPE_HEADERS.values())
        if candidates:
            for c in candidates:
                missing = [SCOPE_HEADERS[f] for f in SCOPE_HEADERS if f not in c.positions]
                result.issues.append(_error(
                    "MISSING_REQUIRED_COLUMNS",
                    f"Sheet '{c.sheet_name}' (header row {c.header_row}) is missing required column(s): "
                    f"{', '.join(missing)}. Headers found: {', '.join(c.headers)}."))
        else:
            found = "; ".join(f"'{name}': {', '.join(_first_nonempty_row(rows)) or '(empty)'}"
                              for name, rows in sheets.items())
            result.issues.append(_error(
                "SCOPE_SHEET_NOT_FOUND",
                f"No sheet has the required scope headers ({required}). Headers found — {found}."))
        return result

    cand = complete[0]
    result.sheet_name = cand.sheet_name
    result.header_row = cand.header_row
    result.ignored_headers = cand.ignored

    duplicated = {f: cols for f, cols in cand.positions.items() if len(cols) > 1}
    for f, cols in duplicated.items():
        letters = ", ".join(get_column_letter(c + 1) for c in cols)
        result.issues.append(_error(
            "DUPLICATE_HEADER",
            f"Column header '{SCOPE_HEADERS[f]}' appears more than once (columns {letters}); "
            f"the correct column cannot be chosen.",
            value=SCOPE_HEADERS[f]))
    if duplicated:
        return result

    col_index = {f: cols[0] for f, cols in cand.positions.items()}
    result.columns = {f: get_column_letter(i + 1) for f, i in col_index.items()}

    data_rows = sheets[cand.sheet_name][cand.header_row:]
    # Trailing blank rows are worksheet formatting, not data; drop them before validation.
    while data_rows and all(cell_text(v) is None for v in data_rows[-1]):
        data_rows.pop()

    for offset, row in enumerate(data_rows):
        values = {f: (row[i] if i < len(row) else None) for f, i in col_index.items()}
        result.rows.append(RawScopeRow(
            row_number=cand.header_row + 1 + offset,
            values=values,
            is_empty=all(cell_text(v) is None for v in row),
        ))
    return result
