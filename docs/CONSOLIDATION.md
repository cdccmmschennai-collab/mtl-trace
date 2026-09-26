# Consolidation — implementation notes (Phase 1C)

Technical record of consolidation and the generated workbook structure as implemented. Business rules
remain in `PRD.md` / `TRD.md`. Last updated 2026-09-25.

## Flow

```
SOURCE_RECORD (Phase 1B, immutable)  +  locked MILESTONE_TAG scope
        → backend/consolidation/engine.py   (pure; never imports extraction, never opens a file)
        → CANONICAL_CELL  (long: tag × attribute × participating source type)
        → backend/output/comparison_workbook.py  (generated, validated on read-back)
        → backend/output/canonical_snapshot.py   (CSV of the canonical layer)
```

`POST /api/runs/{id}/consolidate` runs it once per run. Afterwards the run is `CONSOLIDATED` and frozen:
uploads are refused (service + trigger), and a revised or additional document goes into a new run.
`POST /api/milestones/{id}/runs` accepts `base_run_id` to start a new run from an earlier run's
processed documents (read back hash-verified from the vault and extracted afresh; the base run is only read).

## Canonical states

| State | Meaning |
|---|---|
| `PRESENT` | source row exists, value populated |
| `ABSENT_VALUE` | source row exists, value empty (incl. whitespace-only) |
| `ABSENT_TAG` | the source type has no row for this milestone tag |
| `CONFLICTING_DUPLICATE` | several rows for this tag in this source type (incl. across documents) — every candidate kept, none chosen |
| *(no cells)* | source type not in the run — reported as `not_in_run`, never a placeholder |
| *(no cells)* | attribute no document of that type has a column for — `attributes_provided` omits it (Phase 1D-1) |
| *(coverage list)* | source tag outside the milestone — counted and listed, never a canonical row |

A tag whose only row of a type comes from a document without that attribute's column is `ABSENT_VALUE`
(the row exists), never `ABSENT_TAG`. In the workbook, a participating source's column for an attribute it
does not provide is left empty.

Values are copied from the source record unmodified (`raw_value` exact, `normalized_value` trimmed only).
TAG NUMBER AS PER DOC is reported against the milestone tag using the central `normalize_tag`
(trim + case) only; the milestone tag is never replaced.

## Workbook structure

Six sheets per the documented structure. Source columns = participating source types only, in the PDF
step order (ASSET · MDS · SPIR · GA · MXS · MTC · MOM), header `{attribute label} IN {source label}`;
then `REMARKS · FINAL <attribute> · STATUS`. `SUMMERY`: `SL NO · DESCRIPTION · <code> QTY… · REMARKS ·
MATCH · MISMATCH · PENDING/NOT AVAILABLE · REVIEW REQUIRED`, QTY as static counts, plus
`TOTAL EQUIPMENT / TAG COUNT`. In Phase 1C, REMARKS / FINAL / STATUS and the SUMMERY result columns
are blank (Phase 1D fills them). A duplicate cell is left blank with an Excel comment listing the candidates.

Deliberate differences from the references, all documented:

- **MTC before MOM** — priority order (PRD §13.2); the template/AUTOMATED place MOM first.
- **Consistent header strings** — e.g. `MAKE IN SPIR (MIR)`, `MODEL IN DATA SHEET (MDS)`; AUTOMATED has
  `MAKE IN SPIR(MIR)`, `MAKE IN ASSET ` (trailing space), `MODEL NUMBER IN (MDS)`.
- **`PENDING/NOT AVAILABLE`** is kept as a template header only; PENDING is never written as a value.
- AUTOMATED's legend rows and scratch remark rows are not reproduced (they use banned states / invented rules).

## Storage

```
MTL_DATA/milestones/<code>/canonical/run-NNN/canonical.csv
MTL_DATA/milestones/<code>/outputs/run-NNN/consolidated.xlsx
```

Short on-disk names (Windows path limit); the descriptive name
`MTL-DATA MISMATCH COMPARISION - <code> - RUN-NNN - CONSOLIDATED.xlsx` is the download name. Files are
created exclusively (never overwritten) and hashed in `OUTPUT_ARTIFACT`; if the transaction fails the
files are removed so a retry is clean. `CANONICAL_CELL`, `RUN_CONSOLIDATION` and `OUTPUT_ARTIFACT` rows
are immutable (triggers).

## Controlled second-source fixture

The real SPIR adapter is enabled (Phase 1D-1); Data Sheet + SPIR consolidation is tested on the real files
(717 rows · 7,170 cells · both source columns equal ORIGINAL BACKUP except the two pinned deviations).
`tests/fixtures/second_source.py` is a **test-only** adapter (sheet `CONTROLLED FIXTURE SPIR`) that
replaces the SPIR adapter in a few tests, because the real SPIR has no duplicate or out-of-scope tag to
exercise those states. It is never imported by `backend/` (architecture test).
