"""Source documents, comparison attributes and source-vs-scope coverage.

Source types are registered data, not a fixed column list. The seven types are those of
`MTL Attribute Values Population.pdf`; their *priority ranks* are comparison rules and will live in
`rules/v1.yaml` (Phase 1C), so they are deliberately not encoded here. Whether a type can actually be
processed depends only on whether an adapter is registered for it (`backend/extraction/registry.py`).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum


class Attribute(StrEnum):
    TAG_NUMBER = "TAG_NUMBER"
    MAKE = "MAKE"
    MODEL = "MODEL"
    SERIAL_NUMBER = "SERIAL_NUMBER"
    PART_NUMBER = "PART_NUMBER"


ATTRIBUTES: tuple[Attribute, ...] = tuple(Attribute)


@dataclass(frozen=True)
class AttributeInfo:
    """Business-facing wording of one comparison attribute, from the comparison workbook."""
    attribute: Attribute
    label: str                  # "SERIAL NUMBER"
    sheet_name: str             # "SERIAL NUMBER COMPARISION" (template spelling)
    column_label: str           # source-column prefix: "{column_label} IN {source label}"
    final_label: str            # "FINAL SERIAL NUMBER"
    summary_description: str    # SUMMERY row text: "SERIAL NUMBER MISMATCH"


# Sheet names, FINAL headers and SUMMERY descriptions are verbatim from the working file and the
# mental-model reference `…- AUTOMATED.xlsx`. Column prefixes use each sheet's own wording
# (`SL/NO`, `P/N`); MODEL uses `MODEL`, matching its FINAL header (the reference mixes MODEL and
# MODEL NUMBER on one sheet).
ATTRIBUTE_INFO: dict[Attribute, AttributeInfo] = {a.attribute: a for a in (
    AttributeInfo(Attribute.TAG_NUMBER, "TAG NUMBER", "TAG NUMBER COMPARISION", "TAG NUMBER", "FINAL TAG", "TAG MISMATCH"),
    AttributeInfo(Attribute.MAKE, "MAKE", "MAKE COMPARISION", "MAKE", "FINAL MAKE", "MAKE MISMATCH"),
    AttributeInfo(Attribute.MODEL, "MODEL", "MODEL COMPARISION", "MODEL", "FINAL MODEL", "MODEL MISMATCH"),
    AttributeInfo(Attribute.SERIAL_NUMBER, "SERIAL NUMBER", "SERIAL NUMBER COMPARISION", "SL/NO",
                  "FINAL SERIAL NUMBER", "SERIAL NUMBER MISMATCH"),
    AttributeInfo(Attribute.PART_NUMBER, "PART NUMBER", "PART NUMBER COMPARISION", "P/N",
                  "FINAL PART NUMBER", "PART NUMBER MISMATCH"),
)}


@dataclass(frozen=True)
class SourceTypeInfo:
    code: str
    label: str
    summary_code: str           # SUMMERY "<code> QTY" header; the template uses MIR for SPIR
    # Whole-word phrases that name this document type in a sheet title or header (after normalize_header).
    # They identify an uploaded document and qualify headers such as `SPIR TAG NUMBER`.
    keywords: tuple[str, ...] = ()


# Labels follow the business-facing workbook wording. Declaration order is the sequence of
# `MTL Attribute Values Population.pdf` (steps 1–7) and is the *display* order of source columns.
# It is never used to select a value — priority as a rule belongs to `rules/v1.yaml`.
# Keywords come from the codes, the workbook labels and the PDF's document names only.
SOURCE_TYPES: dict[str, SourceTypeInfo] = {t.code: t for t in (
    SourceTypeInfo("ASSET", "ASSET PHOTO", "ASSET", ("ASSET", "ASSET PHOTO", "PHOTOGRAPHY", "NAME PLATE", "NAMEPLATE")),
    SourceTypeInfo("MDS", "DATA SHEET (MDS)", "MDS", ("MDS", "DATASHEET", "DATA SHEET")),
    SourceTypeInfo("SPIR", "SPIR (MIR)", "MIR", ("SPIR", "MIR")),
    SourceTypeInfo("GA", "GA DOCUMENT", "GA", ("GA", "GA DOCUMENT", "GENERAL ARRANGEMENT")),
    SourceTypeInfo("MXS", "CROSS SECTION (MXS)", "MXS", ("MXS", "CROSS SECTION")),
    SourceTypeInfo("MTC", "TEST CERTIFICATE (MTC)", "MTC", ("MTC", "TEST CERTIFICATE")),
    SourceTypeInfo("MOM", "O&M MANUAL (MOM)", "MOM", ("MOM", "O&M", "O&M MANUAL")),
)}


def ordered_source_types(codes) -> list[str]:
    """The given source-type codes in display order. Unknown codes are refused, never appended."""
    codes = set(codes)
    unknown = codes - SOURCE_TYPES.keys()
    if unknown:
        raise ValueError(f"Unknown source type(s): {', '.join(sorted(unknown))}")
    return [c for c in SOURCE_TYPES if c in codes]


class RunStatus(StrEnum):
    CREATED = "CREATED"                          # no successfully processed source yet
    DOCUMENTS_UPLOADED = "DOCUMENTS_UPLOADED"    # at least one source processed (TRD §22)
    CONSOLIDATED = "CONSOLIDATED"                # canonical dataset built; the run's sources are frozen


class SourceProcessingStatus(StrEnum):
    PROCESSED = "PROCESSED"
    PROCESSED_WITH_WARNINGS = "PROCESSED_WITH_WARNINGS"
    FAILED = "FAILED"                            # nothing extracted; see issues


@dataclass(frozen=True)
class DuplicateKey:
    normalized_tag: str
    rows: tuple[int, ...]
    in_scope: bool


@dataclass
class ScopeCoverage:
    """How a source's tag keys relate to the locked milestone scope. Never alters the scope."""
    source_rows: int = 0                         # non-empty data rows seen
    rows_with_tag_key: int = 0
    rows_without_tag_key: list[int] = field(default_factory=list)
    unique_source_tags: int = 0
    duplicates: list[DuplicateKey] = field(default_factory=list)
    matched_tags: int = 0                        # unique source keys inside the scope
    out_of_scope_tags: dict[str, tuple[int, ...]] = field(default_factory=dict)   # key -> rows
    scope_tags_without_record: int = 0


def compute_scope_coverage(row_keys: list[tuple[int, str | None]], scope_tags: set[str]) -> ScopeCoverage:
    """`row_keys` is (worksheet row, normalized tag key or None) for every non-empty source row."""
    cov = ScopeCoverage(source_rows=len(row_keys))
    rows_by_key: dict[str, list[int]] = defaultdict(list)
    for row, key in row_keys:
        if key is None:
            cov.rows_without_tag_key.append(row)
        else:
            rows_by_key[key].append(row)
    cov.rows_with_tag_key = sum(len(r) for r in rows_by_key.values())
    cov.unique_source_tags = len(rows_by_key)
    cov.duplicates = [DuplicateKey(k, tuple(r), k in scope_tags) for k, r in rows_by_key.items() if len(r) > 1]
    cov.matched_tags = sum(1 for k in rows_by_key if k in scope_tags)
    cov.out_of_scope_tags = {k: tuple(r) for k, r in rows_by_key.items() if k not in scope_tags}
    cov.scope_tags_without_record = len(scope_tags) - cov.matched_tags
    return cov
