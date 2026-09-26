"""Unit tests: scope sheet discovery (extraction) and scope validation rules (domain)."""

from datetime import datetime

from backend.domain.scope import ScopeField, normalize_header, validate_scope_rows
from backend.domain.tags import normalize_tag
from backend.extraction.scope import read_scope_workbook
from tests.conftest import HEADERS, make_workbook, scope_rows


def check(sheets: dict[str, list[list]]):
    read = read_scope_workbook("scope.xlsx", make_workbook(sheets))
    if read.issues:
        return read, None
    return read, validate_scope_rows(read.rows, read.columns)


def codes(issues) -> list[str]:
    return [i.code for i in issues]


# ---- header / sheet discovery

def test_header_normalization_is_exact_not_substring():
    assert normalize_header(" s. no ") == normalize_header("S.NO") == "S NO"
    assert normalize_header("SIZE&RATING") == "SIZE & RATING"
    assert normalize_header("TAG NUMBER AS PER DOC") != normalize_header("TAG NUMBER")


def test_tag_normalization_trims_and_uppercases_only():
    assert normalize_tag("  66-45-sac-001 ") == "66-45-SAC-001"
    assert normalize_tag("88-LT-802") != normalize_tag("88-LIT-802")


def test_valid_scope_is_accepted():
    read, v = check({"Scope": scope_rows(3)})
    assert v.valid and len(v.entries) == 3
    assert [e.scope_order for e in v.entries] == [1, 2, 3]
    assert v.entries[0].s_no == "0001"
    assert read.columns[ScopeField.TAG_NUMBER] == "B"


def test_scope_sheet_found_by_headers_not_position():
    sheets = {"SUMMERY": [["SL NO", "DESCRIPTION"], [1, "TAG MISMATCH"]], "TAGS": scope_rows(2)}
    read, v = check(sheets)
    assert read.sheet_name == "TAGS" and v.valid


def test_columns_found_by_header_in_any_order_with_extra_columns():
    rows = [["NOTES", "SIZE & RATING", "TAG NUMBER", "S.NO", "EQUIPMENT DESCRIPTION", "TAG DISCRIPTION"],
            ["x", "2IN", "T-1", "0001", "PUMP", "Pump A"]]
    read, v = check({"S": rows})
    assert v.valid
    e = v.entries[0]
    assert (e.tag_number, e.s_no, e.size_rating, e.tag_description) == ("T-1", "0001", "2IN", "Pump A")
    assert read.ignored_headers == ["NOTES"]


def test_header_row_need_not_be_row_one():
    read, v = check({"S": [["MILESTONE SCOPE"], []] + scope_rows(2)})
    assert read.header_row == 3 and v.valid
    assert v.entries[0].source_row == 4


def test_missing_required_column_is_reported_with_headers_found():
    rows = [["S.NO", "TAG NUMBER", "TAG DISCRIPTION", "SIZE & RATING"], ["0001", "T-1", "d", None]]
    read, _ = check({"S": rows})
    assert codes(read.issues) == ["MISSING_REQUIRED_COLUMNS"]
    assert "EQUIPMENT DESCRIPTION" in read.issues[0].message
    assert "Headers found" in read.issues[0].message


def test_no_scope_sheet_lists_headers_found():
    read, _ = check({"Other": [["A", "B"], [1, 2]]})
    assert codes(read.issues) == ["SCOPE_SHEET_NOT_FOUND"]
    assert "'Other': A, B" in read.issues[0].message


def test_two_scope_sheets_are_ambiguous_not_guessed():
    read, _ = check({"One": scope_rows(2), "Two": scope_rows(2)})
    assert codes(read.issues) == ["SCOPE_SHEET_AMBIGUOUS"]


def test_duplicate_required_header_is_not_guessed():
    rows = [HEADERS + ["TAG NUMBER"], ["0001", "T-1", "d", "e", None, "T-9"]]
    read, _ = check({"S": rows})
    assert codes(read.issues) == ["DUPLICATE_HEADER"]
    assert "B, F" in read.issues[0].message


def test_unsupported_and_unreadable_files():
    assert codes(read_scope_workbook("scope.xls", b"x").issues) == ["UNSUPPORTED_FILE_TYPE"]
    assert codes(read_scope_workbook("scope.xlsx", b"not a zip").issues) == ["UNREADABLE_WORKBOOK"]


# ---- row validation

def test_blank_tag_is_an_error_not_a_skip():
    rows = scope_rows(3)
    rows[2][1] = None      # worksheet row 3
    rows[3][1] = "   "     # worksheet row 4 — whitespace only
    _, v = check({"S": rows})
    assert not v.valid
    blank = [i for i in v.errors if i.code == "BLANK_TAG"]
    assert len(blank) == 1 and blank[0].rows == (3, 4)


def test_duplicate_tags_detected_after_normalization():
    rows = scope_rows(3)
    rows[3][1] = " tag-001"   # same as row 2 ignoring case/space
    _, v = check({"S": rows})
    dup = [i for i in v.errors if i.code == "DUPLICATE_TAG"]
    assert len(dup) == 1 and dup[0].rows == (2, 4) and dup[0].value == "TAG-001"


def test_non_text_tag_is_malformed():
    rows = scope_rows(2)
    rows[1][1] = 12345
    rows[2][1] = datetime(2026, 1, 1)
    _, v = check({"S": rows})
    assert codes(v.errors) == ["MALFORMED_TAG", "MALFORMED_TAG"]


def test_multi_line_tag_is_malformed():
    rows = scope_rows(1)
    rows[1][1] = "T-1\nT-2"
    _, v = check({"S": rows})
    assert codes(v.errors) == ["MALFORMED_TAG"]


def test_empty_scope_is_an_error():
    _, v = check({"S": [HEADERS]})
    assert codes(v.errors) == ["EMPTY_SCOPE"]


def test_embedded_empty_rows_warn_and_trailing_empty_rows_are_ignored():
    rows = scope_rows(2)
    rows.insert(2, [None] * 5)          # worksheet row 3
    rows += [[None] * 5, [None] * 5]    # trailing
    _, v = check({"S": rows})
    assert v.valid and len(v.entries) == 2
    assert [(i.code, i.rows) for i in v.warnings] == [("EMPTY_ROW", (3,))]


def test_row_with_data_only_in_ignored_column_is_blank_tag():
    rows = [HEADERS + ["NOTES"], ["0001", "T-1", "d", "e", None, None], [None, None, None, None, None, "orphan"]]
    _, v = check({"S": rows})
    assert [(i.code, i.rows) for i in v.errors] == [("BLANK_TAG", (3,))]


def test_warnings_do_not_block_and_values_are_preserved():
    rows = scope_rows(3)
    rows[1][1] = "  TAG-001  "
    rows[2][0] = None
    rows[3][0] = 3
    _, v = check({"S": rows})
    assert v.valid
    assert sorted(codes(v.warnings)) == ["BLANK_SNO", "SNO_NOT_TEXT", "TAG_WHITESPACE_TRIMMED"]
    assert v.entries[0].tag_number == "TAG-001"
    assert v.entries[1].s_no is None
    assert v.entries[2].s_no == "3"


def test_duplicate_sno_is_a_warning():
    rows = scope_rows(2)
    rows[2][0] = "0001"
    _, v = check({"S": rows})
    assert v.valid and codes(v.warnings) == ["DUPLICATE_SNO"]


def test_all_rows_counted_even_when_invalid():
    rows = scope_rows(4)
    rows[2][1] = None
    _, v = check({"S": rows})
    assert v.data_row_count == 4 and len(v.entries) == 3
