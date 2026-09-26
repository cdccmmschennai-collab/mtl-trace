"""SPIR (MIR) adapter — identification only; fields are discovered by the shared keyword rules
(`backend.domain.fields`), never listed per source.

Verified against `input/sources/spir/4391-SPIR DATA PRIORITY-2_COMPLETED.xlsx` (sheet `SPIR DATA`;
`PRD-COUNT` is a completion tracker and is skipped). There, `TAG NUMBER` is the join key and
`SPIR TAG NUMBER` the TAG attribute value printed on the SPIR — the shared rules read the leading source
word as a document qualifier, exactly as `AS PER DOC` on the Data Sheet. References come per SPIR stage
(`SPIR REF-INITIAL/NORMAL/LCS`, `DOKNR INITIAL/NORMAL/LCS`); every one is kept as provenance.
Positions observed in that file are asserted only in tests.
"""

from backend.domain.sources import SOURCE_TYPES
from backend.extraction.tabular import TabularAdapter, TabularAdapterConfig

SPIR = TabularAdapter(TabularAdapterConfig(
    source_type="SPIR",
    document_label="SPIR",
    sheet_names=("SPIR DATA",),
    evidence_headers=("SPIR TAG NUMBER", "SPIR REF-INITIAL", "SPIR REF-NORMAL", "SPIR REF-LCS"),
    keywords=SOURCE_TYPES["SPIR"].keywords,
))
