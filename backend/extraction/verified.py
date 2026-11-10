"""Cross Section (MXS), Test Certificate (MTC) and O&M Manual (MOM) adapters — identification only; fields
are discovered by the shared keyword rules (`backend.domain.fields`), never listed per source.

Verified on the real files in `SAMPLE FILES/`:

- MXS `0903_4391-MTL-MXS PRIORITY-2_COMPLETED.xlsx`, sheet `MTL-DOC.DATA MXS` (`PRD ASSIGNED & COUNT`
  skipped). There is no bare `TAG NUMBER`: the join key is `MXS TAG`, beside ` TAG NUMBER AS PER DOC`.
- MTC `0905_4391-TEST CERTIFICATE PRIORITY-2_COMPLETED.xlsx`, sheet `TEST CERTIFICATE` (`PRD-COUNT`
  skipped). `TEST CERTIFICATE TAG NUMBER` is the printed tag; `ASSET SERIAL NUMBER` is a cross-reference
  and is not this document's SERIAL NUMBER.
- MOM `0904_4391-MOM PRIORITY-2_COMPLETED.xlsx`, sheet `O&M` (`PRD-COUNT` skipped). No printed-tag column.

The exact sheet titles are extra evidence only — a renamed sheet is still recognised by its keywords
(`MXS`, `CROSS SECTION`, `TEST CERTIFICATE`, `O&M` …). Positions observed are asserted only in tests.
"""

from backend.domain.sources import SOURCE_TYPES
from backend.extraction.tabular import TabularAdapter, TabularAdapterConfig

MXS = TabularAdapter(TabularAdapterConfig(
    source_type="MXS",
    document_label="Cross Section",
    sheet_names=("MTL-DOC.DATA MXS",),
    keywords=SOURCE_TYPES["MXS"].keywords,
))

MTC = TabularAdapter(TabularAdapterConfig(
    source_type="MTC",
    document_label="Test Certificate",
    sheet_names=("TEST CERTIFICATE",),
    evidence_headers=("TEST CERTIFICATE TAG NUMBER", "TEST CERTIFICATE REFERENCE-ORIGINAL"),
    keywords=SOURCE_TYPES["MTC"].keywords,
))

MOM = TabularAdapter(TabularAdapterConfig(
    source_type="MOM",
    document_label="O&M Manual",
    sheet_names=("O&M",),
    evidence_headers=("O&M REFERENCE-ORIGINAL", "O&M REFERENCE-DOC IDB"),
    keywords=SOURCE_TYPES["MOM"].keywords,
))
