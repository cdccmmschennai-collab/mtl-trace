"""Comparison engine (TRD §17, PRD §12, SPEC_VALIDATION_REPORT §9).

Consumes canonical cells only — never a source file, never the extraction package. For each
milestone tag × attribute it receives the cells of the participating source types that provide that
attribute and decides, under the loaded rules:

    applicable values  = PRESENT cells (value non-empty after normalization), in priority order
    duplicates         = CONFLICTING_DUPLICATE cells with at least one non-empty candidate

    no applicable value and no duplicate          → FINAL blank, STATUS blank   (not a state)
    a duplicate                                   → REVIEW REQUIRED   (never last-write-wins)
    manufacturer-name attribute (MAKE): the differing values are only naming variants of each other
        (backend/comparison/names.py)             → REVIEW REQUIRED, FINAL blank (not resolved automatically)
    ≥2 applicable values that differ              → MISMATCH          (RULE-P3)
    milestone-anchored attribute (TAG NUMBER):
        the sources agree, but not with the milestone tag → REVIEW REQUIRED
    otherwise                                     → MATCH  (≥2 agree, or exactly one value)

    FINAL — milestone-anchored attribute: the milestone tag.
          — otherwise: the highest-ranked source holding a value (RULE-P1); blank when that source's
            rows are conflicting duplicates, because no candidate may be chosen automatically.

Missing source values never count as disagreement. Raw values are never modified; equality uses the
rules' normalization (trim + case-insensitive) only.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from backend.comparison.names import is_name_variant
from backend.comparison.rules import Rules


class Status(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    REVIEW_REQUIRED = "REVIEW REQUIRED"


class Reason(StrEnum):
    SINGLE_SOURCE = "SINGLE_SOURCE"                            # MATCH: exactly one applicable value
    SOURCES_AGREE = "SOURCES_AGREE"                            # MATCH: ≥2 values, all equal
    SOURCES_DISAGREE = "SOURCES_DISAGREE"                      # MISMATCH
    DIFFERS_FROM_MILESTONE = "DIFFERS_FROM_MILESTONE"          # REVIEW REQUIRED: sources agree, milestone differs
    DUPLICATE_SOURCE_RECORDS = "DUPLICATE_SOURCE_RECORDS"      # REVIEW REQUIRED
    NAME_VARIANT = "NAME_VARIANT"                              # REVIEW REQUIRED: manufacturer names may be the same
    NO_SOURCE_VALUE = "NO_SOURCE_VALUE"                        # blank FINAL and STATUS


PRESENT = "PRESENT"
DUPLICATE = "CONFLICTING_DUPLICATE"


@dataclass(frozen=True)
class SourceValue:
    source_type: str
    state: str                                 # canonical cell state
    value: str | None                          # canonical normalized value (trimmed source text)
    candidates: tuple[str | None, ...] = ()    # duplicate candidates' values (CONFLICTING_DUPLICATE only)


@dataclass(frozen=True)
class ComparisonInput:
    milestone_tag_id: int
    milestone_tag: str
    attribute: str
    values: tuple[SourceValue, ...]            # participating source types that provide this attribute


@dataclass(frozen=True)
class ComparisonResult:
    milestone_tag_id: int
    attribute: str
    status: Status | None
    final_value: str | None
    final_source: str | None                   # source type FINAL came from; "MILESTONE" for anchored attributes
    reason: Reason
    remarks: str | None
    compared_sources: tuple[str, ...]          # source types holding an applicable value, priority order


MILESTONE = "MILESTONE"


def _names(sources, labels: Mapping[str, str]) -> str:
    """"A", "A and B", "A, B and C" — business labels in the given (priority) order."""
    names = [labels.get(v.source_type, v.source_type) for v in sources]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def compare(item: ComparisonInput, rules: Rules, labels: Mapping[str, str] | None = None) -> ComparisonResult:
    labels = labels or {}
    ranked = sorted(item.values, key=lambda v: rules.rank(v.source_type))
    applicable = [v for v in ranked if v.state == PRESENT and rules.key(v.value) is not None]
    duplicates = [v for v in ranked if v.state == DUPLICATE and any(rules.key(c) for c in v.candidates)]
    compared = tuple(v.source_type for v in applicable)
    anchored = item.attribute in rules.milestone_anchored

    def result(status, reason, final, final_source, remarks=None):
        return ComparisonResult(item.milestone_tag_id, item.attribute, status, final, final_source, reason, remarks,
                                compared)

    if not applicable and not duplicates:
        return result(None, Reason.NO_SOURCE_VALUE, None, None)

    if anchored:
        final, final_source = item.milestone_tag, MILESTONE
    else:
        first = next(v for v in ranked if v in applicable or v in duplicates)
        final, final_source = (first.value, first.source_type) if first in applicable else (None, None)

    if duplicates:
        notes = "; ".join(f"{labels.get(d.source_type, d.source_type)}: "
                          + " | ".join(repr(c) for c in d.candidates if rules.key(c)) for d in duplicates)
        return result(Status.REVIEW_REQUIRED, Reason.DUPLICATE_SOURCE_RECORDS, final, final_source,
                      f"Several source rows for this tag; no value chosen automatically ({notes}).")

    # Remarks explain non-MATCH rows only, in business wording; the source values sit in the row's own columns.
    distinct = {rules.key(v.value) for v in applicable}
    if len(distinct) > 1 and item.attribute in rules.manufacturer_names:
        label = item.attribute.replace("_", " ")
        if all(is_name_variant(a.value, b.value) for a, b in combinations(applicable, 2)
               if rules.key(a.value) != rules.key(b.value)):
            return result(Status.REVIEW_REQUIRED, Reason.NAME_VARIANT, None, None,
                          f"{label} values may represent the same manufacturer; human review required.")
        return result(Status.MISMATCH, Reason.SOURCES_DISAGREE, final, final_source,
                      f"{_names(applicable, labels)} {label} values differ; human review required.")

    if len(distinct) > 1:
        chosen = "milestone TAG retained" if anchored else f"{labels.get(final_source, final_source)} selected by source priority"
        return result(Status.MISMATCH, Reason.SOURCES_DISAGREE, final, final_source,
                      f"{_names(applicable, labels)} values differ; {chosen}.")

    if anchored and distinct != {rules.key(item.milestone_tag)}:
        return result(Status.REVIEW_REQUIRED, Reason.DIFFERS_FROM_MILESTONE, final, final_source,
                      f"{_names(applicable, labels)} TAG differs from milestone TAG; milestone TAG retained.")

    reason = Reason.SINGLE_SOURCE if len(applicable) == 1 else Reason.SOURCES_AGREE
    return result(Status.MATCH, reason, final, final_source)


def compare_all(items: list[ComparisonInput], rules: Rules,
                labels: Mapping[str, str] | None = None) -> list[ComparisonResult]:
    """`labels` maps source-type codes to the business labels used in remarks (codes when absent)."""
    return [compare(i, rules, labels) for i in items]
