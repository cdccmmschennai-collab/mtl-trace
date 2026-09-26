# Source Adapters — implementation notes

Technical record of source discovery and extraction as implemented. Business rules remain in `PRD.md` /
`TRD.md`; this file records only implementation detail and verified facts. Last updated 2026-09-25 (Phase 1D-1).

## Model: shared discovery, identification-only adapters

Every supplied source is a worker-export workbook: a join-key column holding the milestone tag, "value as per
document" columns, and document/page provenance. Which columns a document has, and how they are worded,
varies by document type. So:

- **Field discovery is shared** (`backend/domain/fields.py`) — one keyword rule set for every source type.
  There are no per-source field lists.
- **An adapter only identifies its document type** (`TabularAdapterConfig`: source type, label, sheet titles,
  evidence headers). Registering one in `backend/extraction/registry.py` is the only step to enable a type.
- **Available-data principle**: a document contributes the attributes it has. Only the join key is required.

| Source type | Adapter | Status |
|---|---|---|
| MDS — Data Sheet | `backend/extraction/datasheet.py` | **enabled**, verified on the real file |
| SPIR (MIR) | `backend/extraction/spir.py` | **enabled**, verified on the real file |
| ASSET, GA, MXS, MTC, MOM | — | awaiting real files |

## Keyword discovery

Headers are normalized (`backend/domain/headers.py`: upper-case, punctuation other than `&` is a separator,
whitespace collapsed). Then document qualifiers are stripped and the **whole remaining phrase** must equal a
core phrase — no substring or fuzzy matching (`PART NUMBER REMARKS` never binds).

Document qualifiers (they say where a value was read, not what it is):
- suffix `AS PER DOC` / `AS PER DOCUMENT` (Data Sheet)
- one leading or trailing source-type word — the registered codes/summary codes: ASSET, MDS, SPIR, MIR, GA,
  MXS, MTC, MOM (SPIR: `SPIR TAG NUMBER`)

| Concept | Core phrases | Notes |
|---|---|---|
| join key | `TAG` · `TAG NUMBER` · `TAG NO` — **bare** | the milestone tag the worker searched for |
| TAG NUMBER (attribute) | the same phrases **with a qualifier** | tag printed on the document |
| MAKE | `MAKE` · `MANUFACTURER` · `MFR` · `OEM` | |
| MODEL | `MODEL` · `MODEL NO` · `MODEL NUMBER` | |
| SERIAL NUMBER | `SERIAL` · `SERIAL NUMBER` · `SERIAL NO` | |
| PART NUMBER | `PART` · `PART NUMBER` · `PART NO` | |

Only these five attributes are discovered. Every other header is reported in `headers_found` and left alone.

Provenance, by whole-word keyword; several columns may bind, all are kept:
`IDB` / `DOKNR` → document_idb · `REF` / `REFERENCE` → document_reference · `PAGE` / `PAGE NO` → page.
Where one role has several columns (SPIR stages), the role value joins the populated ones in column order
(`; `), and every cell is also kept under its own header in `source_location.source_fields`.

Binding outcomes:

| Situation | Result |
|---|---|
| join key: none / several | `MISSING_FIELD` / `AMBIGUOUS_FIELD` — error, document `FAILED` |
| attribute: none | `FIELD_NOT_PROVIDED` — warning; attribute not provided, nothing filled in |
| attribute: several | `AMBIGUOUS_FIELD` — error (never choose a column) |
| no attribute column at all | `NO_ATTRIBUTE_FIELD` — error |

## Value normalization

Stored per record: `raw_value` (exact cell text, surrounding spaces kept) and `normalized_value` (trimmed;
whitespace-only → empty; numbers rendered without a trailing `.0`). No case folding, no punctuation handling,
no synonym handling — equivalence belongs to comparison/review.

## Verified on `0904_4391-DATA SHEET PRIORITY-2_COMPLETED.xlsx` (sheet `DATASHEET`)

Join key `TAG NUMBER`; TAG attribute ` TAG NUMBER AS PER DOC`; provenance `DATASHEET REFERENCE-ORIGINAL`,
`DATASHEET REFERENCE-DOC IDB`, `PAGE NO`. Sheets `PRD COUNT` and `Sheet1` are skipped.
436 rows · 436 unique keys · 0 duplicates · 436 in scope · 0 outside · 281 scope tags without a row ·
TAG/MAKE/MODEL/SERIAL/PART populated 357/124/98/0/0 · TAG as-per-doc equals key 343, differs 14.

## Verified on `4391-SPIR DATA PRIORITY-2_COMPLETED.xlsx` (sheet `SPIR DATA`)

Join key `TAG NUMBER`; TAG attribute `SPIR TAG NUMBER`; MAKE/MODEL/SERIAL NUMBER/PART NUMBER under those
headers; provenance `SPIR REF-INITIAL/NORMAL/LCS`, `DOKNR INITIAL/NORMAL/LCS`, `PAGE NO`. Sheet `PRD-COUNT`
is skipped. Not extracted (reported only): equipment description, size & rating, valve schedule, acquisition,
weight, country, manufacture month/year, vendor details, remarks, name, date.
464 rows · 464 unique keys · 0 duplicates · 464 in scope · 0 outside · 253 scope tags without a row ·
TAG/MAKE/MODEL/SERIAL/PART populated 377/458/355/331/370 · SPIR TAG equals key 357, differs 20.

## Oracle deviations (ORIGINAL BACKUP)

Every source cell of `ORIGINAL BACKUP` equals the extracted raw value exactly, except one per source, where
the human copy dropped punctuation the source file carries. The adapter keeps the source value (stripping
punctuation would be an equivalence rule the specification forbids); the tests pin exactly these.

| Source | Sheet | Tag | Source file | ORIGINAL BACKUP |
|---|---|---|---|---|
| MDS (3,584 / 3,585 equal) | MAKE COMPARISION | 68-SP-015 | `TOPSAFE CO., LTD` | `TOPSAFE CO LTD` |
| SPIR (1,890 / 1,891 values equal) | MAKE COMPARISION | 88-GV-1601 | `JIANGSU YDF VALVE CO.,LTD` | `JIANGSU YDF VALVE CO,LTD` |
