"""Consolidation engine (TRD §15, SPEC_VALIDATION_REPORT §8).

    for tag in scope:                       # the outer loop is ALWAYS the locked milestone scope
        for attribute in attributes:
            for source_type in participating source types that PROVIDE this attribute:
                0 records  → ABSENT_TAG               (the source has no row for this tag)
                           → ABSENT_VALUE             (it has a row, from a document without this column)
                1 record   → PRESENT | ABSENT_VALUE   (row exists; value populated / empty)
                2+ records → CONFLICTING_DUPLICATE    (every candidate kept; none chosen)

Consequences that hold by construction, not by assertion:

- canonical rows == scope tags, in scope order, whatever the sources contain (CR-1);
- a source tag outside the scope never produces a row — it is counted and listed in the coverage (CR-2);
- a source type not participating in the run produces no cells at all, never an empty placeholder;
- likewise, a source type none of whose documents has a column for an attribute produces no cells for
  that attribute (available-data principle) — it is reported as not provided, never as ABSENT_TAG.

What this engine deliberately does NOT do: pick a FINAL value, apply source priority, compare values,
or decide MATCH / MISMATCH / REVIEW REQUIRED. That is the comparison engine (Phase 1D). Values are
carried exactly as stored on the source record — `raw_value` untouched, `normalized_value` trimmed only.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from backend.domain.sources import Attribute
from backend.domain.tags import normalize_tag


class CellState(StrEnum):
    PRESENT = "PRESENT"                                  # row exists, value populated
    ABSENT_VALUE = "ABSENT_VALUE"                        # row exists, value empty
    ABSENT_TAG = "ABSENT_TAG"                            # no row for this tag in this source
    CONFLICTING_DUPLICATE = "CONFLICTING_DUPLICATE"      # several rows for this tag; none chosen


# ---------------------------------------------------------------- inputs

@dataclass(frozen=True)
class ScopeTagIn:
    id: int
    scope_order: int
    tag_number: str
    normalized_tag: str


@dataclass(frozen=True)
class RecordIn:
    """One stored SOURCE_RECORD (source row × attribute)."""
    id: int
    run_source_id: int
    source_type: str
    row: int
    source_tag: str | None
    normalized_tag: str | None
    attribute: str
    raw_value: str | None
    normalized_value: str | None


# ---------------------------------------------------------------- outputs

@dataclass(frozen=True)
class Cell:
    milestone_tag_id: int
    attribute: Attribute
    source_type: str
    state: CellState
    raw_value: str | None               # set only for PRESENT / ABSENT_VALUE (the single record's value)
    normalized_value: str | None
    record_ids: tuple[int, ...]         # provenance anchors: 0 (ABSENT_TAG), 1, or every duplicate candidate


@dataclass
class AttributeCoverage:
    present: int = 0
    absent_value: int = 0
    absent_tag: int = 0
    duplicate: int = 0


@dataclass
class TagDifference:
    milestone_tag: str
    tag_as_per_doc: str


@dataclass
class SourceCoverage:
    """How one participating source type covers the locked scope. Counts are derived, never supplied."""
    source_type: str
    documents: int = 0
    rows: int = 0                                    # non-empty source rows across the type's documents
    rows_without_tag_key: int = 0
    unique_tags: int = 0
    duplicate_tags: dict[str, int] = field(default_factory=dict)       # tag -> row count (> 1)
    in_scope_tags: int = 0
    out_of_scope_tags: dict[str, list[int]] = field(default_factory=dict)   # tag -> source rows
    scope_tags_without_row: int = 0
    attributes_provided: list[str] = field(default_factory=list)
    attributes: dict[str, AttributeCoverage] = field(default_factory=dict)
    # TAG NUMBER AS PER DOC vs the milestone tag (central tag normalization only: trim + case).
    tag_as_per_doc_equal: int = 0
    tag_as_per_doc_differs: list[TagDifference] = field(default_factory=list)


@dataclass
class Consolidation:
    source_types: tuple[str, ...]
    attributes: tuple[Attribute, ...]
    tag_ids: tuple[int, ...]                         # canonical rows, in scope order
    cells: list[Cell]
    coverage: dict[str, SourceCoverage]
    provided: dict[str, tuple[Attribute, ...]]       # source type -> attributes it provides

    def provides(self, source_type: str, attribute: Attribute) -> bool:
        return attribute in self.provided[source_type]

    @property
    def expected_cell_count(self) -> int:
        return len(self.tag_ids) * sum(len(p) for p in self.provided.values())


class ConsolidationError(ValueError):
    pass


# ---------------------------------------------------------------- engine

def consolidate(tags: list[ScopeTagIn], records: list[RecordIn], source_types: list[str],
                attributes: tuple[Attribute, ...], documents_per_type: dict[str, int] | None = None,
                provided: dict[str, set[str]] | None = None) -> Consolidation:
    """`provided`: source type -> attribute codes its documents have a column for (None → every attribute)."""
    tags = sorted(tags, key=lambda t: t.scope_order)
    if len({t.normalized_tag for t in tags}) != len(tags):
        raise ConsolidationError("The milestone scope contains duplicate tags; it cannot anchor a canonical dataset.")
    if len(set(source_types)) != len(source_types):
        raise ConsolidationError("A source type is listed twice.")
    stray = {r.source_type for r in records} - set(source_types)
    if stray:
        raise ConsolidationError(f"Records belong to non-participating source type(s): {', '.join(sorted(stray))}.")
    attr_values = {a.value for a in attributes}
    if provided is None:
        provided = {st: attr_values for st in source_types}
    by_type = {st: tuple(a for a in attributes if a.value in provided.get(st, ())) for st in source_types}
    missing = {(r.source_type, r.attribute) for r in records if r.attribute in attr_values
               and r.attribute not in provided.get(r.source_type, ())}
    if missing:
        raise ConsolidationError(f"Records exist for attributes declared not provided: {sorted(missing)}.")

    scope_keys = {t.normalized_tag for t in tags}
    index: dict[tuple[str, str, str], list[RecordIn]] = defaultdict(list)
    has_row: set[tuple[str, str]] = set()                     # (tag, source type) with at least one source row
    for r in records:
        if r.normalized_tag is not None and r.normalized_tag in scope_keys:
            has_row.add((r.normalized_tag, r.source_type))
            if r.attribute in attr_values:
                index[(r.normalized_tag, r.attribute, r.source_type)].append(r)

    coverage = {st: _coverage(st, [r for r in records if r.source_type == st], scope_keys,
                              (documents_per_type or {}).get(st, 0)) for st in source_types}
    for st in source_types:
        coverage[st].attributes_provided = [a.value for a in by_type[st]]

    cells: list[Cell] = []
    for tag in tags:                                          # CR-1: the scope drives the loop
        for attribute in attributes:
            for st in source_types:
                if attribute not in by_type[st]:              # not provided: no cell, never a placeholder
                    continue
                found = sorted(index.get((tag.normalized_tag, attribute.value, st), ()), key=lambda r: (r.run_source_id, r.row))
                cells.append(_cell(tag.id, attribute, st, found, (tag.normalized_tag, st) in has_row))

    for cell in cells:
        cov = coverage[cell.source_type].attributes.setdefault(cell.attribute.value, AttributeCoverage())
        if cell.state == CellState.PRESENT:
            cov.present += 1
        elif cell.state == CellState.ABSENT_VALUE:
            cov.absent_value += 1
        elif cell.state == CellState.ABSENT_TAG:
            cov.absent_tag += 1
        else:
            cov.duplicate += 1

    if Attribute.TAG_NUMBER in attributes:
        tag_by_id = {t.id: t for t in tags}
        for cell in cells:
            if cell.attribute == Attribute.TAG_NUMBER and cell.state == CellState.PRESENT:
                milestone = tag_by_id[cell.milestone_tag_id]
                cov = coverage[cell.source_type]
                if normalize_tag(cell.normalized_value) == milestone.normalized_tag:
                    cov.tag_as_per_doc_equal += 1
                else:
                    cov.tag_as_per_doc_differs.append(TagDifference(milestone.tag_number, cell.raw_value))

    result = Consolidation(tuple(source_types), tuple(attributes), tuple(t.id for t in tags), cells, coverage, by_type)
    if len(cells) != result.expected_cell_count:          # structural self-check; cannot fail silently
        raise ConsolidationError(f"Canonical dataset has {len(cells)} cells, expected {result.expected_cell_count}.")
    return result


def _cell(tag_id: int, attribute: Attribute, source_type: str, found: list[RecordIn], has_row: bool) -> Cell:
    ids = tuple(r.id for r in found)
    if not found:
        # A row exists but came only from a document of this type without this column: the source row is
        # there, the value is not — ABSENT_VALUE, not ABSENT_TAG.
        state = CellState.ABSENT_VALUE if has_row else CellState.ABSENT_TAG
        return Cell(tag_id, attribute, source_type, state, None, None, ())
    if len(found) > 1:                                    # never last-write-wins
        return Cell(tag_id, attribute, source_type, CellState.CONFLICTING_DUPLICATE, None, None, ids)
    r = found[0]
    state = CellState.PRESENT if r.normalized_value is not None else CellState.ABSENT_VALUE
    return Cell(tag_id, attribute, source_type, state, r.raw_value, r.normalized_value, ids)


def _coverage(source_type: str, records: list[RecordIn], scope_keys: set[str], documents: int) -> SourceCoverage:
    cov = SourceCoverage(source_type, documents=documents)
    rows: dict[tuple[int, int], str | None] = {}
    for r in records:
        rows[(r.run_source_id, r.row)] = r.normalized_tag
    cov.rows = len(rows)
    cov.rows_without_tag_key = sum(1 for k in rows.values() if k is None)
    per_tag = Counter(k for k in rows.values() if k is not None)
    cov.unique_tags = len(per_tag)
    cov.duplicate_tags = {k: n for k, n in per_tag.items() if n > 1}
    cov.in_scope_tags = sum(1 for k in per_tag if k in scope_keys)
    out: dict[str, list[int]] = defaultdict(list)
    for (_, row), k in sorted(rows.items()):
        if k is not None and k not in scope_keys:
            out[k].append(row)
    cov.out_of_scope_tags = dict(out)
    cov.scope_tags_without_row = len(scope_keys) - cov.in_scope_tags
    return cov
