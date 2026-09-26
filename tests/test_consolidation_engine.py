"""Unit tests: the pure consolidation engine (scope × attributes × participating sources)."""

import dataclasses

import pytest

from backend.consolidation.engine import (
    Cell,
    CellState,
    ConsolidationError,
    RecordIn,
    ScopeTagIn,
    consolidate,
)
from backend.domain.sources import ATTRIBUTES, Attribute

_ids = iter(range(1, 10**6))


def scope(n: int) -> list[ScopeTagIn]:
    return [ScopeTagIn(i, i, f"TAG-{i:03d}", f"TAG-{i:03d}") for i in range(1, n + 1)]


def row(source_type: str, row_no: int, tag: str | None, rs: int = 1, **values) -> list[RecordIn]:
    """All five attribute records of one source row, like Phase 1B stores them (empty values included)."""
    key = tag.strip().upper() if tag else None
    out = []
    for a in ATTRIBUTES:
        raw = values.get(a.value)
        norm = raw.strip() or None if raw is not None else None
        out.append(RecordIn(next(_ids), rs, source_type, row_no, tag, key, a.value, raw, norm))
    return out


def cell(result, tag_id: int, attribute: Attribute, source_type: str) -> Cell:
    [c] = [c for c in result.cells if (c.milestone_tag_id, c.attribute, c.source_type) == (tag_id, attribute, source_type)]
    return c


def test_canonical_rows_are_the_scope_whatever_the_source_contains():
    tags = scope(7)
    records = row("MDS", 2, "TAG-001", MAKE="ACME") + row("MDS", 3, "OUTSIDE-1", MAKE="X")
    result = consolidate(tags, records, ["MDS"], ATTRIBUTES)
    assert result.tag_ids == tuple(t.id for t in tags)                     # every scope tag, scope order
    assert len(result.cells) == len(tags) * len(ATTRIBUTES) * 1 == result.expected_cell_count
    assert {c.milestone_tag_id for c in result.cells} == {t.id for t in tags}   # never expanded by OUTSIDE-1


def test_scope_order_drives_the_rows_even_if_tags_arrive_unordered():
    tags = scope(4)
    result = consolidate(list(reversed(tags)), [], ["MDS"], ATTRIBUTES)
    assert result.tag_ids == (1, 2, 3, 4)


def test_every_canonical_state_is_distinguished():
    records = (row("MDS", 2, "TAG-001", MAKE="ACME")                     # present
               + row("MDS", 3, "TAG-002")                                 # row exists, values empty
               + row("MDS", 4, "TAG-003", MAKE="A") + row("MDS", 5, " tag-003", MAKE="B"))   # duplicate
    result = consolidate(scope(4), records, ["MDS"], ATTRIBUTES)
    assert cell(result, 1, Attribute.MAKE, "MDS").state == CellState.PRESENT
    assert cell(result, 1, Attribute.MODEL, "MDS").state == CellState.ABSENT_VALUE
    assert cell(result, 2, Attribute.MAKE, "MDS").state == CellState.ABSENT_VALUE
    dup = cell(result, 3, Attribute.MAKE, "MDS")
    assert dup.state == CellState.CONFLICTING_DUPLICATE and len(dup.record_ids) == 2
    assert dup.raw_value is None                                          # none chosen — never last-write-wins
    absent = cell(result, 4, Attribute.MAKE, "MDS")
    assert (absent.state, absent.record_ids) == (CellState.ABSENT_TAG, ())


def test_whitespace_only_value_is_an_empty_value_not_a_present_one():
    result = consolidate(scope(1), row("MDS", 2, "TAG-001", MODEL="   "), ["MDS"], ATTRIBUTES)
    assert cell(result, 1, Attribute.MODEL, "MDS").state == CellState.ABSENT_VALUE


def test_source_values_are_carried_unmodified():
    result = consolidate(scope(1), row("MDS", 2, "TAG-001", MAKE=" TOPSAFE CO., LTD"), ["MDS"], ATTRIBUTES)
    c = cell(result, 1, Attribute.MAKE, "MDS")
    assert (c.raw_value, c.normalized_value) == (" TOPSAFE CO., LTD", "TOPSAFE CO., LTD")


def test_two_sources_keep_their_own_values_side_by_side():
    records = row("MDS", 2, "TAG-001", MAKE="ACME", rs=1) + row("SPIR", 9, "TAG-001", MAKE="ACME LTD", rs=2)
    result = consolidate(scope(2), records, ["MDS", "SPIR"], ATTRIBUTES)
    assert cell(result, 1, Attribute.MAKE, "MDS").raw_value == "ACME"
    assert cell(result, 1, Attribute.MAKE, "SPIR").raw_value == "ACME LTD"
    assert len(result.cells) == 2 * len(ATTRIBUTES) * 2
    assert cell(result, 2, Attribute.MAKE, "SPIR").state == CellState.ABSENT_TAG


def test_one_source_run_has_no_cells_for_other_types():
    result = consolidate(scope(3), row("MDS", 2, "TAG-001"), ["MDS"], ATTRIBUTES)
    assert {c.source_type for c in result.cells} == {"MDS"}
    assert set(result.coverage) == {"MDS"}


def test_rows_from_two_documents_of_one_type_are_duplicates_not_merged():
    records = row("MDS", 2, "TAG-001", MAKE="A", rs=1) + row("MDS", 2, "TAG-001", MAKE="B", rs=2)
    result = consolidate(scope(1), records, ["MDS"], ATTRIBUTES, {"MDS": 2})
    assert cell(result, 1, Attribute.MAKE, "MDS").state == CellState.CONFLICTING_DUPLICATE
    cov = result.coverage["MDS"]
    assert (cov.documents, cov.rows, cov.duplicate_tags) == (2, 2, {"TAG-001": 2})


def test_coverage_counts_are_derived():
    records = (row("MDS", 2, "TAG-001", MAKE="A") + row("MDS", 3, "TAG-002")
               + row("MDS", 4, "TAG-002") + row("MDS", 5, "NOPE-1") + row("MDS", 6, None, MAKE="orphan"))
    cov = consolidate(scope(5), records, ["MDS"], ATTRIBUTES).coverage["MDS"]
    assert (cov.rows, cov.rows_without_tag_key, cov.unique_tags) == (5, 1, 3)
    assert cov.duplicate_tags == {"TAG-002": 2}
    assert (cov.in_scope_tags, cov.out_of_scope_tags, cov.scope_tags_without_row) == (2, {"NOPE-1": [5]}, 3)
    make = cov.attributes["MAKE"]
    assert (make.present, make.absent_value, make.absent_tag, make.duplicate) == (1, 0, 3, 1)
    assert make.present + make.absent_value + make.absent_tag + make.duplicate == 5


def test_tag_as_per_doc_difference_is_reported_milestone_tag_kept():
    records = row("MDS", 2, "TAG-001", TAG_NUMBER="tag-001 ") + row("MDS", 3, "TAG-002", TAG_NUMBER="T-2")
    result = consolidate(scope(2), records, ["MDS"], ATTRIBUTES)
    cov = result.coverage["MDS"]
    assert cov.tag_as_per_doc_equal == 1
    assert [(d.milestone_tag, d.tag_as_per_doc) for d in cov.tag_as_per_doc_differs] == [("TAG-002", "T-2")]
    assert cell(result, 2, Attribute.TAG_NUMBER, "MDS").raw_value == "T-2"      # source value preserved


def test_engine_produces_no_comparison_outcome():
    fields = {f.name for f in dataclasses.fields(Cell)}
    assert fields == {"milestone_tag_id", "attribute", "source_type", "state", "raw_value", "normalized_value",
                      "record_ids"}
    assert {s.value for s in CellState} == {"PRESENT", "ABSENT_VALUE", "ABSENT_TAG", "CONFLICTING_DUPLICATE"}


def test_records_of_a_non_participating_type_are_refused():
    with pytest.raises(ConsolidationError, match="non-participating"):
        consolidate(scope(1), row("SPIR", 2, "TAG-001"), ["MDS"], ATTRIBUTES)


def test_duplicate_scope_is_refused():
    tags = scope(2) + [ScopeTagIn(99, 3, "tag-001", "TAG-001")]
    with pytest.raises(ConsolidationError, match="duplicate"):
        consolidate(tags, [], ["MDS"], ATTRIBUTES)


# ---------------------------------------------------------------- available-data principle (Phase 1D-1)

def _only(records: list[RecordIn], *attrs: str) -> list[RecordIn]:
    return [r for r in records if r.attribute in attrs]


def test_attribute_not_provided_by_a_source_type_gets_no_cells():
    tags = scope(3)
    spir = _only(row("SPIR", 2, "TAG-001", MAKE="ACME", MODEL="M1"), "TAG_NUMBER", "MAKE", "MODEL")
    records = row("MDS", 2, "TAG-001", MAKE="ACME") + spir
    provided = {"MDS": {a.value for a in ATTRIBUTES}, "SPIR": {"TAG_NUMBER", "MAKE", "MODEL"}}
    result = consolidate(tags, records, ["MDS", "SPIR"], ATTRIBUTES, provided=provided)
    assert len(result.cells) == result.expected_cell_count == 3 * (5 + 3)
    assert not [c for c in result.cells if c.source_type == "SPIR" and c.attribute == Attribute.PART_NUMBER]
    assert cell(result, 1, Attribute.MAKE, "SPIR").state == CellState.PRESENT
    assert cell(result, 2, Attribute.MAKE, "SPIR").state == CellState.ABSENT_TAG
    assert result.coverage["SPIR"].attributes_provided == ["TAG_NUMBER", "MAKE", "MODEL"]
    assert set(result.coverage["SPIR"].attributes) == {"TAG_NUMBER", "MAKE", "MODEL"}


def test_row_from_a_document_without_the_column_is_absent_value_not_absent_tag():
    """Two SPIR documents: one has a SERIAL column, the other not. A tag whose only row is in the second
    document has a SPIR row — its SERIAL is ABSENT_VALUE, never ABSENT_TAG."""
    doc1 = row("SPIR", 2, "TAG-001", rs=1, SERIAL_NUMBER="S1")
    doc2 = _only(row("SPIR", 2, "TAG-002", rs=2, MAKE="ACME"), "TAG_NUMBER", "MAKE", "MODEL", "PART_NUMBER")
    result = consolidate(scope(3), doc1 + doc2, ["SPIR"], ATTRIBUTES)
    assert cell(result, 1, Attribute.SERIAL_NUMBER, "SPIR").state == CellState.PRESENT
    c = cell(result, 2, Attribute.SERIAL_NUMBER, "SPIR")
    assert (c.state, c.raw_value, c.record_ids) == (CellState.ABSENT_VALUE, None, ())
    assert cell(result, 3, Attribute.SERIAL_NUMBER, "SPIR").state == CellState.ABSENT_TAG


def test_records_for_an_attribute_declared_not_provided_are_refused():
    with pytest.raises(ConsolidationError, match="declared not provided"):
        consolidate(scope(1), row("MDS", 2, "TAG-001"), ["MDS"], ATTRIBUTES, provided={"MDS": {"MAKE"}})
