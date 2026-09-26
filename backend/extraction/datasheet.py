"""Data Sheet (MDS) adapter — identification only; fields are discovered by the shared keyword rules
(`backend.domain.fields`), never listed per source.

Verified against `input/sources/datasheet/0904_4391-DATA SHEET PRIORITY-2_COMPLETED.xlsx`
(sheet `DATASHEET`; `PRD COUNT` and `Sheet1` are a completion tracker and scratch, and are skipped).
There, `TAG NUMBER` is the join key and `TAG NUMBER AS PER DOC` the TAG attribute value printed on the
document — the shared rules keep them apart. Positions observed in that file are asserted only in tests.
"""

from backend.domain.sources import SOURCE_TYPES
from backend.extraction.tabular import TabularAdapter, TabularAdapterConfig

DATASHEET = TabularAdapter(TabularAdapterConfig(
    source_type="MDS",
    document_label="Data Sheet",
    sheet_names=("DATASHEET",),
    evidence_headers=("DATASHEET REFERENCE-ORIGINAL", "DATASHEET REFERENCE-DOC IDB"),
    keywords=SOURCE_TYPES["MDS"].keywords,
))
