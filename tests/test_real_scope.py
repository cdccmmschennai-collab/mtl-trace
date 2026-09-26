"""Real-file verification against the finalized milestone scope workbook.

Expected figures are derived from the file itself with an independent openpyxl read, so the test
holds for any scope size; 717 is the regression case, not a system limit.
"""

import io

import openpyxl

from backend.domain.scope import validate_scope_rows
from backend.extraction.scope import read_scope_workbook
from tests.conftest import REAL_SCOPE_FILE


def independent_read(data: bytes) -> list[tuple]:
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    rows = [r for r in wb["TAG NUMBER COMPARISION"].iter_rows(min_row=2, max_col=5, values_only=True)
            if any(v is not None for v in r)]
    wb.close()
    return rows


def test_real_scope_imports_every_tag_in_order(real_scope_bytes):
    expected = independent_read(real_scope_bytes)
    read = read_scope_workbook(REAL_SCOPE_FILE.name, real_scope_bytes)
    assert read.issues == []
    assert read.sheet_name == "TAG NUMBER COMPARISION"      # found by headers; SUMMERY is sheet 1
    assert read.header_row == 1

    v = validate_scope_rows(read.rows, read.columns)
    assert v.valid, v.errors
    assert v.warnings == []
    assert len(v.entries) == len(expected) == v.data_row_count
    assert len({e.normalized_tag for e in v.entries}) == len(expected)
    assert [e.tag_number for e in v.entries] == [r[1] for r in expected]
    assert [e.s_no for e in v.entries] == [r[0] for r in expected]
    assert [e.size_rating for e in v.entries] == [r[4] for r in expected]   # blanks stay blank


def test_real_scope_regression_case(real_scope_bytes):
    read = read_scope_workbook(REAL_SCOPE_FILE.name, real_scope_bytes)
    v = validate_scope_rows(read.rows, read.columns)
    assert len(v.entries) == 717
    first, last = v.entries[0], v.entries[-1]
    assert (first.s_no, first.tag_number) == ("0001", "66-45-SAC-001")
    assert (last.s_no, last.tag_number, last.source_row) == ("0717", "PMRCU8862B", 718)
    assert sum(1 for e in v.entries if e.size_rating is None) == 90
