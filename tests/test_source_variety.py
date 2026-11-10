"""Many kinds of source document, one discovery: the five real source files (MDS, SPIR, MXS, MTC, MOM) and
the variations future revisions will bring — renamed sheets, moved / extra columns, title rows above the
header, qualified headers.

Column positions of the real files appear ONLY here, as fixture assertions — never in backend/.
"""

import io
from collections import Counter

import openpyxl
import pytest

from backend.domain.sources import ATTRIBUTE_INFO, ATTRIBUTES, SOURCE_TYPES, Attribute, ordered_source_types
from backend.extraction import registry
from backend.extraction.tabular import load_workbook
from tests.conftest import HEADERS, locked_milestone, make_workbook, new_run, upload
from tests.test_comparison_api import compare, workbook
from tests.test_consolidation_api import consolidate


def run(data: bytes, name: str, source_type: str | None = None):
    book = load_workbook(name, data)
    ident = registry.identify(book, source_type)
    return ident, (registry.extract(book, ident) if ident.source_type else None)


def values_in_order(ext) -> list[tuple]:
    return [(r.normalized_key, tuple(sorted((a.value, v.raw) for a, v in r.values.items()))) for r in ext.rows]


def codes(issues) -> list[str]:
    return [i.code for i in issues]


# The data sheet of each real file and the header carrying its join key / attributes (stripped text).
REAL_SHEETS = {"MDS": "DATASHEET", "SPIR": "SPIR DATA", "MXS": "MTL-DOC.DATA MXS", "MTC": "TEST CERTIFICATE", "MOM": "O&M"}
JOIN_HEADER = {"MDS": "TAG NUMBER", "SPIR": "TAG NUMBER", "MXS": "MXS TAG", "MTC": "TAG NUMBER", "MOM": "TAG NUMBER"}
ATTR_HEADERS = {
    "MDS": {Attribute.TAG_NUMBER: "TAG NUMBER AS PER DOC"},
    "SPIR": {Attribute.TAG_NUMBER: "SPIR TAG NUMBER"},
    "MXS": {Attribute.TAG_NUMBER: "TAG NUMBER AS PER DOC"},
    "MTC": {Attribute.TAG_NUMBER: "TEST CERTIFICATE TAG NUMBER"},
    "MOM": {},
}
for _t in ATTR_HEADERS:
    ATTR_HEADERS[_t].update({Attribute.MAKE: "MAKE", Attribute.MODEL: "MODEL",
                             Attribute.SERIAL_NUMBER: "SERIAL NUMBER", Attribute.PART_NUMBER: "PART NUMBER"})


def independent_rows(data: bytes, sheet: str) -> tuple[dict[str, int], list[tuple]]:
    """Header index by stripped text, and every non-empty data row — plain openpyxl, a separate code path."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    idx = {str(h).strip(): i for i, h in enumerate(rows[0]) if h is not None}
    body = [r for r in rows[1:] if any(v is not None and str(v).strip() for v in r)]
    return idx, body


def filled(v) -> bool:
    return v is not None and str(v).strip() != ""


# ---------------------------------------------------------------- every real file

def test_every_real_file_is_recognised_as_its_own_type(real_sources):
    for source_type, (name, data) in real_sources.items():
        ident, ext = run(data, name)
        assert (ident.source_type, ident.sheet_name) == (source_type, REAL_SHEETS[source_type]), name
        assert ext.ok, (name, ext.issues)
        assert len(ident.skipped_sheets) == len(load_workbook(name, data).sheets) - 1


def test_every_real_file_extracts_exactly_what_the_file_holds(real_sources):
    for source_type, (name, data) in real_sources.items():
        idx, body = independent_rows(data, REAL_SHEETS[source_type])
        _, ext = run(data, name)
        assert len(ext.rows) == len(body), name
        assert [r.raw_key.strip() if r.raw_key else None for r in ext.rows] == \
               [str(b[idx[JOIN_HEADER[source_type]]]).strip() if filled(b[idx[JOIN_HEADER[source_type]]]) else None
                for b in body], name
        assert set(ext.provided_attributes) == set(ATTR_HEADERS[source_type]), name
        counts = Counter(a for r in ext.rows for a, v in r.values.items() if v.normalized is not None)
        for attr, header in ATTR_HEADERS[source_type].items():
            assert counts.get(attr, 0) == sum(1 for b in body if filled(b[idx[header]])), (name, attr)


def test_real_mapping_fixture_positions(real_sources):
    """Positions verified in the real files. MAKE alone sits in J, N, I, M, I — bound by meaning every time."""
    expected = {
        "MDS": {"TAG_KEY": "B", "TAG_AS_PER_DOC": "G", "MAKE": "J", "MODEL": "K", "SERIAL_NUMBER": "L", "PART_NUMBER": "M"},
        "SPIR": {"TAG_KEY": "B", "TAG_AS_PER_DOC": "F", "MAKE": "N", "MODEL": "O", "SERIAL_NUMBER": "P", "PART_NUMBER": "Q"},
        "MXS": {"TAG_KEY": "B", "TAG_AS_PER_DOC": "F", "MAKE": "I", "MODEL": "J", "SERIAL_NUMBER": "K", "PART_NUMBER": "L"},
        "MTC": {"TAG_KEY": "B", "TAG_AS_PER_DOC": "F", "MAKE": "M", "MODEL": "O", "SERIAL_NUMBER": "J", "PART_NUMBER": "N"},
        "MOM": {"TAG_KEY": "B", "MAKE": "I", "MODEL": "J", "SERIAL_NUMBER": "K", "PART_NUMBER": "L"},
    }
    for source_type, (name, data) in real_sources.items():
        _, ext = run(data, name)
        bound = {b.key: b.column for b in ext.mapping if b.key not in ("DOCUMENT_REFERENCE", "DOCUMENT_IDB", "PAGE_NO")}
        assert bound == expected[source_type], name


def test_real_mxs_join_key_is_the_mxs_tag_column(real_sources):
    name, data = real_sources["MXS"]
    _, ext = run(data, name)
    assert [(b.key, b.header) for b in ext.mapping][:2] == [("TAG_KEY", "MXS TAG"), ("TAG_AS_PER_DOC", " TAG NUMBER AS PER DOC")]
    assert {"document_reference", "document_idb", "page"} <= set(ext.provenance_roles.values())
    assert ext.issues == []


def test_real_mtc_is_not_mistaken_for_an_asset_photo(real_sources):
    """`ASSET SERIAL NUMBER` mentions ASSET; the sheet is *titled* TEST CERTIFICATE — the title wins."""
    name, data = real_sources["MTC"]
    ident, ext = run(data, name)
    assert ident.source_type == "MTC"
    assert [(i.code, i.value) for i in ext.issues] == [("CROSS_REFERENCE_FIELD", "ASSET SERIAL NUMBER")]
    assert [b.header for b in ext.mapping if b.key == "SERIAL_NUMBER"] == ["SERIAL NUMBER"]
    refused, _ = run(data, name, source_type="ASSET")
    assert codes(refused.issues) == ["NOT_THIS_SOURCE_TYPE"] and refused.source_type is None


def test_real_mom_has_no_printed_tag_and_still_processes(real_sources):
    name, data = real_sources["MOM"]
    _, ext = run(data, name)
    assert ext.ok and [(i.code, i.value) for i in ext.issues] == [("FIELD_NOT_PROVIDED", "TAG NUMBER (as per document)")]


# ---------------------------------------------------------------- future revisions: nothing positional

KEYWORD_ONLY_SHEET_NAMES = {"MDS": "DATA SHEET REV-B", "SPIR": "MIR EXPORT", "MXS": "CROSS SECTION DATA",
                            "MTC": "MTC REV 2", "MOM": "O&M MANUAL EXTRACT"}


def revised(data: bytes, sheet: str, new_name: str) -> bytes:
    """The same document as a later revision might arrive: data sheet renamed, columns reversed, two
    unrelated columns inserted, and a title block above the header row."""
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb[sheet]
    grid = [[c.value for c in row] for row in ws.iter_rows()]
    position = wb.sheetnames.index(sheet)
    wb.remove(ws)
    new = wb.create_sheet(new_name, position)
    new.append(["MTL EXTRACT — REVISION B"])
    new.append([])
    for i, row in enumerate(grid):
        has_content = any(v is not None and str(v).strip() for v in row)
        extra = ["INSPECTOR", "QC FLAG"] if i == 0 else ([f"QC-{i}", None] if has_content else [None, None])
        new.append([extra[0], *reversed(row), extra[1]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize("source_type", list(REAL_SHEETS))
def test_a_revised_real_file_extracts_identically(real_sources, source_type):
    name, data = real_sources[source_type]
    _, original = run(data, name)
    ident, changed = run(revised(data, REAL_SHEETS[source_type], KEYWORD_ONLY_SHEET_NAMES[source_type]), "revised.xlsx")
    assert (ident.source_type, ident.sheet_name) == (source_type, KEYWORD_ONLY_SHEET_NAMES[source_type])
    assert changed.ok and changed.header_row == 3
    assert values_in_order(changed) == values_in_order(original)
    assert {b.key for b in changed.mapping} == {b.key for b in original.mapping}
    assert {b.key: b.column for b in changed.mapping}["MAKE"] != {b.key: b.column for b in original.mapping}["MAKE"]


# ---------------------------------------------------------------- join-key rule edges

def test_own_type_tag_is_an_attribute_when_a_bare_tag_column_exists():
    data = make_workbook({"MXS": [["MXS TAG", "TAG NUMBER", "MAKE"], ["T-1A", "T-1", "ACME"]]})
    _, ext = run(data, "mxs.xlsx")
    assert [(b.key, b.header) for b in ext.mapping][:2] == [("TAG_KEY", "TAG NUMBER"), ("TAG_AS_PER_DOC", "MXS TAG")]
    assert ext.rows[0].normalized_key == "T-1"


@pytest.mark.parametrize("headers", [
    ["MXS TAG", "MAKE"],                                              # which tag is it? no printed-tag column beside it
    ["MXS TAG", "MXS TAG NO", "TAG NUMBER AS PER DOC", "MAKE"],       # two own-type tag columns
    ["TAG NUMBER AS PER DOC", "MAKE"],                                # printed tag only
])
def test_join_key_is_never_guessed(headers):
    data = make_workbook({"MXS": [headers, ["T-1"] * len(headers)]})
    _, ext = run(data, "mxs.xlsx")
    assert not ext.ok and codes(ext.issues) == ["MISSING_FIELD"] and ext.rows == []
    assert all(h.strip() in ext.issues[0].message for h in headers)


def test_a_tag_column_naming_another_source_type_is_never_the_join_key():
    data = make_workbook({"MXS": [["SPIR TAG", "TAG NUMBER AS PER DOC", "MAKE"], ["T-1", "T-1", "A"]]})
    _, ext = run(data, "mxs.xlsx")
    assert codes(ext.issues) == ["MISSING_FIELD"]


# ---------------------------------------------------------------- cross-reference columns

def test_cross_reference_column_alone_is_not_this_documents_value():
    data = make_workbook({"TEST CERTIFICATE": [["TAG NUMBER", "MAKE", "ASSET SERIAL NUMBER"], ["T-1", "A", "SN-9"]]})
    _, ext = run(data, "mtc.xlsx")
    assert ext.ok and Attribute.SERIAL_NUMBER not in ext.provided_attributes
    assert codes(ext.issues) == ["CROSS_REFERENCE_FIELD", "FIELD_NOT_PROVIDED"]


def test_own_type_and_unqualified_columns_together_stay_ambiguous():
    data = make_workbook({"TEST CERTIFICATE": [["TAG NUMBER", "MAKE", "MTC MAKE"], ["T-1", "A", "B"]]})
    _, ext = run(data, "mtc.xlsx")
    assert not ext.ok and [(i.code, i.value) for i in ext.issues] == [("AMBIGUOUS_FIELD", "MAKE")]


# ---------------------------------------------------------------- identification ranking

def test_header_keywords_of_two_types_without_a_title_are_ambiguous():
    data = make_workbook({"Export": [["TAG NUMBER", "MTC TAG NO", "ASSET SERIAL NUMBER", "MAKE"],
                                     ["T-1", "T-1", "S", "A"]]})
    ident, _ = run(data, "x.xlsx")
    assert codes(ident.issues) == ["SOURCE_TYPE_AMBIGUOUS"]
    chosen, ext = run(data, "x.xlsx", source_type="MTC")
    assert chosen.source_type == "MTC" and ext.ok


def test_a_verified_evidence_header_outranks_a_keyword():
    data = make_workbook({"Export": [["TAG NUMBER", "TEST CERTIFICATE TAG NUMBER", "ASSET SERIAL NUMBER", "MAKE"],
                                     ["T-1", "T-1", "S", "A"]]})
    ident, _ = run(data, "x.xlsx")
    assert ident.source_type == "MTC"


def test_two_titled_types_in_one_workbook_are_ambiguous():
    data = make_workbook({"DATASHEET": [["TAG NUMBER", "MAKE"], ["T-1", "A"]],
                          "SPIR DATA": [["TAG NUMBER", "MAKE"], ["T-1", "B"]]})
    ident, _ = run(data, "both.xlsx")
    assert codes(ident.issues) == ["SOURCE_TYPE_AMBIGUOUS"]


# ---------------------------------------------------------------- end to end: all five, through the API

def test_all_five_real_sources_consolidate_and_compare(client, real_sources):
    """The scope is authoritative: it holds every tag any source keys on, plus tags no source has. Each source
    contributes; each sheet has one column per uploaded type in priority order (no ASSET / GA column); rows
    with no source value get no verdict."""
    keys = set()
    for source_type, (name, data) in real_sources.items():
        idx, body = independent_rows(data, REAL_SHEETS[source_type])
        keys |= {str(b[idx[JOIN_HEADER[source_type]]]).strip().upper() for b in body if filled(b[idx[JOIN_HEADER[source_type]]])}
    scope = sorted(keys) + ["NO-SOURCE-TAG-1", "NO-SOURCE-TAG-2"]
    scope_book = make_workbook({"SCOPE": [HEADERS] + [[f"{i:04d}", t, "DESC", "EQUIP", None] for i, t in enumerate(scope, 1)]})

    m = locked_milestone(client, scope_book)
    assert m["tag_count"] == len(scope)
    r = new_run(client, m["id"])
    for source_type, (name, data) in real_sources.items():
        s = upload(client, f"/api/runs/{r['id']}/sources", data, name=name).json()
        assert s["source_type"] == source_type and s["processing_status"] != "FAILED", (name, s)
    consolidate(client, r["id"])
    wb = workbook(client, r["id"], compare(client, r["id"]))

    order = ordered_source_types(real_sources)
    assert order == ["MDS", "SPIR", "MXS", "MTC", "MOM"]
    for attribute in ATTRIBUTES:
        info = ATTRIBUTE_INFO[attribute]
        rows = list(wb[info.sheet_name].iter_rows(values_only=True))
        header = list(rows[0])
        source_cols = [h for h in header if h and " IN " in str(h)]
        assert source_cols == [f"{info.column_label} IN {SOURCE_TYPES[t].label}" for t in order], attribute
        assert header[-3:] == ["REMARKS", info.final_label, "STATUS"]
        body = rows[1:]
        assert len(body) == len(scope)
        cols = [header.index(c) for c in source_cols]
        for row in body:
            has_value = any(filled(row[c]) for c in cols)
            assert has_value or (row[-2] in (None, "") and row[-1] in (None, "")), (attribute, row)
            assert row[-1] in (None, "", "MATCH", "MISMATCH", "REVIEW REQUIRED")
        tags = {row[header.index("TAG NUMBER")] for row in body}
        assert tags == set(scope)
    # Every source type contributes values somewhere.
    make = list(wb[ATTRIBUTE_INFO[Attribute.MAKE].sheet_name].iter_rows(values_only=True))
    for c in [h for h in make[0] if h and " IN " in str(h)]:
        assert any(filled(row[make[0].index(c)]) for row in make[1:]), c
