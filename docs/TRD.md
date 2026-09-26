# CDC MTL Tool — Technical Requirements Document (TRD)

**Version:** 1.2
**Status:** Validated against the actual repository files (2026-09-24). See `docs/SPEC_VALIDATION_REPORT.md`.

> **Changes in 1.1** — §9 canonical storage changed from wide to long (provenance + the seventh source
> type make a wide table untenable); §10 source vault is content-addressed; §17 comparison reduced to
> three states; §18 rules externalized as versioned data; §20 output workbook is generated dynamically,
> not cloned; new §12.1 shared tabular adapter base and verified regression fixture.
>
> **Changes in 1.2** — final specification decisions: semantic header discovery with a controlled
> alias table and AmbiguousFieldMapping (§12.1); dynamic per-run source types, GA optional at rank 4
> (§17/§18/§20); blank FINAL+STATUS where no source holds a value (§17); four mandatory output guards (§20).

## 1. Technical Objective

Build a local engineering application implementing:

```text
Finalized Tag Scope
→ Milestone
→ Source Upload
→ Extraction
→ Normalization
→ Consolidation
→ Canonical Dataset
→ Comparison
→ Review
→ Output
→ History
```

The architecture must separate extraction, normalization, consolidation, comparison, review, output generation, and historical storage.

## 2. Technology Stack

### Frontend
- React
- TypeScript
- Vite

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy

### Processing
- openpyxl
- pandas where appropriate
- source-specific document libraries only where real formats require them

### Database
- SQLite

### Packaging
A local executable should eventually launch the application and expose a localhost browser UI. PyInstaller or an equivalent packaging approach may be used.

## 3. Deployment Model

V1 is local-first.

```text
MTL Comparison Tool.exe
        ↓
Local API
        ↓
Local Browser UI
        ↓
SQLite + Local File Storage
```

No Hostinger, cloud database, external storage, or authentication is required for V1.

## 4. High-Level Architecture

```text
+------------------------------------------------------+
|                 LOCAL BROWSER UI                     |
|                 React + TypeScript                   |
+--------------------------+---------------------------+
                           |
                           | HTTP
                           v
+------------------------------------------------------+
|                    FASTAPI API                       |
|                                                      |
| Milestone API | Source API | Processing API          |
| Comparison API | Review API | Output/History API     |
+--------------------------+---------------------------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
+--------------------------+   +-----------------------+
|     PROCESSING ENGINE    |   |       STORAGE         |
|                          |   |                       |
| Identification           |   | SQLite                |
| Extraction               |   | Local files           |
| Normalization            |   | Hashes                |
| Consolidation            |   | Metadata              |
| Comparison               |   | Results               |
+------------+-------------+   +-----------------------+
             |
             v
+------------------------------------------------------+
|                CANONICAL DATA MODEL                  |
+------------------------------------------------------+
```

## 5. Architectural Principles

- Finalized milestone scope is authoritative.
- Each source type has an isolated adapter.
- Comparison consumes canonical data, not raw files.
- Business comparison rules are deterministic and versionable.
- Source-derived values retain provenance.
- Original evidence is immutable.
- Revised source documents create new runs.
- Processing modules remain independently testable.
- The frontend does not parse engineering documents.
- Do not build a generic framework before understanding the real files.

## 6. Proposed Backend Structure

```text
backend/
├── api/
│   ├── milestones.py
│   ├── sources.py
│   ├── consolidation.py
│   ├── comparison.py
│   ├── review.py
│   └── outputs.py
├── domain/
│   ├── milestone.py
│   ├── run.py
│   ├── source.py
│   ├── canonical.py
│   ├── comparison.py
│   └── review.py
├── extraction/
│   ├── base.py
│   ├── datasheet.py
│   ├── asset.py
│   ├── spir.py
│   ├── mxs.py
│   ├── mom.py
│   └── mtc.py
├── normalization/
│   └── engine.py
├── consolidation/
│   └── engine.py
├── comparison/
│   ├── engine.py
│   ├── rules.py
│   ├── priority.py
│   └── lifecycle.py
├── review/
│   └── service.py
├── storage/
│   ├── database.py
│   ├── repositories.py
│   └── files.py
├── output/
│   └── comparison_workbook.py
├── models/
│   └── schemas.py
└── main.py
```

This is an architectural target. Do not create every module prematurely.

## 7. Frontend Structure

```text
frontend/
└── src/
    ├── pages/
    │   ├── Home/
    │   ├── CreateMilestone/
    │   ├── MilestoneWorkspace/
    │   ├── Consolidation/
    │   ├── Comparison/
    │   ├── Review/
    │   └── Results/
    ├── components/
    ├── api/
    ├── hooks/
    ├── types/
    └── app/
```

No Excel/document parsing or engineering comparison logic belongs in the frontend.

## 8. Domain Model

Core entities:

- PROJECT
- PACKAGE
- MILESTONE
- MILESTONE_TAG
- SOURCE_DOCUMENT
- SOURCE_RECORD
- PROCESSING_RUN
- CANONICAL_RECORD
- COMPARISON_RESULT
- REVIEW_DECISION
- OUTPUT

Relationship:

```text
PROJECT
  └── PACKAGE
       └── MILESTONE
            ├── MILESTONE_TAG
            ├── SOURCE_DOCUMENT
            └── PROCESSING_RUN
                 ├── SOURCE_RECORD
                 ├── CANONICAL_RECORD
                 ├── COMPARISON_RESULT
                 ├── REVIEW_DECISION
                 └── OUTPUT
```

## 9. Database Requirements

SQLite stores structured metadata and results. Binary source/output files remain in local filesystem storage.

### Milestone
- id
- milestone_code
- project_id
- package_id
- status
- created_at
- updated_at

### Milestone Tag
- id
- milestone_id
- tag_number
- tag_description
- equipment_description
- size_rating
- scope_order

### Source Document
- id
- milestone_id
- source_type
- original_filename
- stored_path — content-addressed, `sources/<sha256>.<ext>`
- file_size
- sha256
- **document_date** — required by RULE-P2 (latest-dated document wins)
- **revision** — where known
- uploaded_at

No `run_id` here: a document may participate in several runs. Run membership and per-run processing
statistics live on `RUN_SOURCE`.

### Processing Run
- id
- milestone_id
- run_number
- status
- started_at
- completed_at
- rules_version
- notes

### Source Record
- id
- run_id
- source_document_id
- source_type
- source_tag
- normalized_tag
- attribute
- raw_value
- normalized_value
- source_location

### Canonical Cell  *(replaces the wide "Canonical Record" of v1.0)*
- id
- run_id
- milestone_tag_id
- attribute
- source_type
- raw_value
- normalized_value
- state — `PRESENT` | `ABSENT_TAG` | `ABSENT_VALUE` | `CONFLICTING_DUPLICATE`
- source_record_id — provenance anchor

**Stored long (one row per tag × attribute × source), pivoted to wide only by the output writer.**
A wide table cannot carry per-cell provenance and would require a schema migration for every new source
type — and the authoritative PDF has already introduced a seventh (GA Document).

**Three-way absence is deliberate.** Excel renders all three as blank, but they mean different things:
`ABSENT_TAG` = the source has no row for this tag; `ABSENT_VALUE` = the source has the tag but the
field is empty; `PRESENT` = a value exists. Verified on the real Data Sheet: 281 `ABSENT_TAG` and
79 `ABSENT_VALUE` for the TAG NUMBER attribute.

### Comparison Result
- id, run_id, milestone_tag_id, attribute
- state — `MATCH` | `MISMATCH` | `REVIEW REQUIRED`
- final_value, final_source_type
- remarks, rule_id, is_auto, computed_at

### Run Source  *(join; per-run stats live here, not on the document)*
- run_id, source_document_id, processing_status
- row_count, recognized_tag_count, matched_tag_count, unmatched_tag_count

The same file processed under a newer `rules_version` is a different result, so these counts belong to
the run, not to the document.

## 10. File Storage

```text
MTL_DATA/
├── database/
│   └── mtl.db
├── milestones/
│   └── MTL-2026-001/
│       ├── scope/
│       ├── sources/
│       ├── extracted/
│       ├── canonical/
│       ├── comparison/
│       ├── review/
│       └── outputs/
└── logs/
```

Original inputs are immutable. Generated outputs are stored separately.

## 11. Source File Integrity

Every uploaded source should receive a SHA-256 hash.

Retain:

- filename
- source type
- size
- hash
- upload time
- run
- processing status

## 12. Extraction Architecture

Each source type should have an adapter contract conceptually supporting:

- `identify()`
- `validate()`
- `extract()`
- `normalize()`

Adapters: `AssetAdapter`, `DataSheetAdapter`, `SpirAdapter`, `GaAdapter`, `MxsAdapter`, `MtcAdapter`,
`MomAdapter`. They convert real source layouts into normalized source records.

### 12.1 Shared tabular adapter base

The supplied source documents are worker-export workbooks sharing a common shape: a join key column
holding the milestone tag, a "value as per document" column per attribute, and document/page provenance
columns. Adapters are therefore built on a shared tabular base and differ only in their header mapping
and sheet selection.

**Layout is discovered semantically, never by fixed column index.** Source revisions move columns —
`MAKE` may be column J in one file and column H in the next — so no adapter may encode a position.
Verified positions belong in the adapter's *tests* as fixture assertions.

Field resolution pipeline:

```text
header cell → normalize (trim, collapse whitespace, upper-case, strip punctuation noise)
            → match against the controlled alias table for the field
            → exactly one confident match  → bind field to that column
            → zero or multiple matches     → AmbiguousFieldMapping
```

Controlled alias table (extended only from real files, never invented):

| Field | Aliases |
|---|---|
| TAG NUMBER (join key) | `TAG NUMBER`, `TAG`, `TAG NO` |
| TAG NUMBER (attribute) | `TAG NUMBER AS PER DOC`, `TAG NUMBER AS PER DOCUMENT` |
| MAKE | `MAKE`, `MANUFACTURER`, `MFR`, `OEM` |
| MODEL | `MODEL`, `MODEL NO`, `MODEL NUMBER` |
| SERIAL NUMBER | `SERIAL`, `SERIAL NUMBER`, `SERIAL NO` |
| PART NUMBER | `PART`, `PART NUMBER`, `PART NO` |

Adapters must tolerate differing column order, additional columns, absent irrelevant columns, and minor
header / capitalization / spacing variation. Blind substring matching is prohibited — `PART NUMBER`
must not be matched by a header merely containing `PART`, and the join-key `TAG NUMBER` must never be
confused with the attribute `TAG NUMBER AS PER DOC`.

**`AmbiguousFieldMapping` is never resolved by guessing.** The adapter raises it carrying the source
document, the field it could not bind, the candidate columns, and every header it found. The run
surfaces this as a review/error condition. A wrong column must never be silently bound because it sits
in a familiar position.

Adapters must report the sheets they skipped rather than silently ignoring them. Verified example: the
Data Sheet workbook carries `DATASHEET` (extract), `PRD COUNT` (a per-document completion tracker) and
`Sheet1` (scratch).

No adapter is written speculatively. Each is implemented only once a real file of that type is
supplied, and is validated against the corresponding column of `ORIGINAL BACKUP`, which holds
human-extracted values for all six workbook sources.

## 13. Normalized Source Record

Conceptual fields:

- source_type
- source_document_id
- source_tag
- normalized_tag
- attribute
- raw_value
- normalized_value
- source_location

For Excel, source location may include sheet/row/column. For PDF, page/table/field may be appropriate.

## 14. Tag Matching

Centralize tag normalization.

```text
Raw Source Tag
      ↓
Tag Normalization
      ↓
Normalized Tag Key
      ↓
Milestone Tag Lookup
```

Duplicate source keys must be detected and must not silently discard conflicting engineering records.

## 15. Consolidation Engine

Input:

```text
Finalized Milestone Tags
+
Normalized Source Records
```

Output:

```text
Canonical Dataset
```

Conceptually:

```text
for each milestone tag:
    create canonical row

    for each source:
        locate source records for tag

        if found:
            attach normalized source value
            attach provenance

        if not found:
            preserve missing state
```

Every milestone tag must remain.

## 16. Current Data Sheet Validation Case

Golden regression fixture, every figure verified by inspection:

```text
Milestone scope .............................. 717 tags (717 unique, 0 duplicates)
Data Sheet rows .............................. 436  (436 unique keys, 0 duplicates)
DS keys within scope ......................... 436     outside scope: 0
Scope tags with no DS row .................... 281     → ABSENT_TAG
TAG NUMBER present from MDS .................. 357     (79 ABSENT_VALUE)
   ...of which equal the join key ............ 343
   ...of which differ from the join key ...... 14      e.g. 68-SP-051→SP-123, 88-LT-802→88-LIT-802
MAKE / MODEL / SERIAL / PART from MDS ........ 124 / 98 / 0 / 0
Canonical cells (717 × 5 attributes × 6 sources)  21,510
```

Cross-validation: these MDS counts match the MDS columns of `ORIGINAL BACKUP` exactly, so the Data
Sheet adapter has an independent oracle.

Agreement distribution across all 717 × 5 = 3,585 comparisons in `ORIGINAL BACKUP`:

| Situation | Count |
|---|---|
| No source holds a value | 1,430 |
| Exactly one source holds a value | 1,162 |
| Two or more, all agree | 403 |
| Two or more, disagree | 590 |

These are test observations, not constants. The fixture asserts *derived relationships* — the test
computes 717 from the scope file and 436 from the Data Sheet — so a 900-tag milestone passes the same
test. 717 is a regression case, not a system limit.

## 17. Comparison Engine

```text
Canonical Cells for (tag, attribute)
      ↓
Applicable-value vector, ordered by source priority rank
      ↓
Comparison Logic
      ├── MATCH             ≥2 values all equal, OR exactly 1 value and nothing conflicting
      ├── MISMATCH          ≥2 values, not all equal
      ├── REVIEW REQUIRED   conflicting duplicates, priority/lifecycle exception, naming ambiguity
      └── (no values)       → FINAL and STATUS both left BLANK — not a state
      ↓
FINAL selection — RULE-P1: highest-ranked source holding a non-empty value
      ↓
Comparison Result
```

Exactly three states. `PENDING` / `NOT AVAILABLE` / `RESOLVED` are not comparison states, and **blank
is not a status** — it is the absence of any result, produced only when no applicable source holds a
value.

The comparison package **never imports the extraction package** — it reads canonical data only, and has
no knowledge of sheets, rows or column letters. It receives `milestone_tag · attribute · source_type ·
raw_value · normalized_value · provenance`.

**Source types are dynamic.** The engine iterates whatever source types the run actually has, ordered
by priority rank from the rules file. No fixed source list may be compiled into the engine; adding a
source type must require no engine change.

## 18. Comparison Rules

**Rules are data, not code.** Priority order, lifecycle conditions, equality semantics, missing-value
handling, conflict handling and final-value permissions live in a versioned `rules/v1.yaml`, loaded at
run time, with `rules_version` stamped on every `PROCESSING_RUN`. This is what makes a run reproducible
and makes a future rules revision a data change plus tests rather than an engine rewrite.

Authoritative rules taken from `MTL Attribute Values Population.pdf`:

- **RULE-P1 (priority / population)** — seven sources in rank order: 1 Photography Name Plate (ASSET),
  2 Data Sheet (MDS), 3 SPIR Sheet, 4 GA Document, 5 Cross Section DWG (MXS), 6 Test Certificate (MTC),
  7 O&M Manuals (MOM). Step 1 populates values; steps 2–7 populate only values still missing. Therefore
  FINAL = the value from the highest-ranked source holding a non-empty value.
- **RULE-P2 (lifecycle)** — among several candidate documents of ranks 2–7, use the latest-dated document.
- **RULE-P3 (mismatch)** — where a source's value disagrees with the other sources', raise the disagreement.

GA (rank 4) is **optional**: present in a run only if a GA document was uploaded. The rules file lists
all seven ranks; the engine applies the ranks that the run actually has. No GA-specific extraction
behaviour may be assumed until a real GA sample is supplied.

Attribute-specific behaviour:

- **TAG NUMBER** is compared against the milestone tag (an always-present master value) and
  `FINAL TAG = the milestone TAG NUMBER`. Verified: 667 of 668 human-filled rows in `ORIGINAL BACKUP`.
- **MAKE / MODEL / SERIAL NUMBER / PART NUMBER** are compared among sources only; FINAL follows RULE-P1.

Normalization before comparison — evidence-backed only: trim whitespace; a whitespace-only cell is
empty; case-insensitive equality. **No** punctuation stripping, abbreviation expansion, or
prefix/substring matching — those are judgement calls the PDF does not define.

## 19. Review

Review operates on persisted comparison results.

A review decision should retain:

- comparison_result_id
- decision
- final_value
- remarks
- reviewed_at

Review does not modify original source records.

## 20. Output Generation

Output generation consumes:

```text
Canonical Dataset
+
Comparison Results
+
Review Decisions
```

and produces the business-facing comparison workbook.

**The workbook is generated, not cloned from a template file.** Sheets are created per comparison
attribute; source columns are created **only for the source types actually participating in the run**,
ordered by authoritative priority rank. Adding a source type (e.g. GA Document) or an attribute extends
the workbook without editing a template and without changing the comparison engine.

Consequently the column count varies per run. A source type that was not uploaded produces **no
column** — never an empty placeholder. The layout target is the mental-model reference
`…- AUTOMATED.xlsx`: every comparison sheet carries `REMARKS`, `FINAL <attribute>` and `STATUS`.

Required sheets: `SUMMERY`, `TAG NUMBER COMPARISION`, `MAKE COMPARISION`, `MODEL COMPARISION`,
`SERIAL NUMBER COMPARISION`, `PART NUMBER COMPARISION`.

Comparison-sheet layout:

```text
A S.NO · B TAG NUMBER · C TAG DISCRIPTION · D EQUIPMENT DESCRIPTION · E SIZE & RATING
F..K  one column per source type
L REMARKS · [M FINAL <attribute>] · [N STATUS]
```

Header naming convention, from the real workbook: `{ATTRIBUTE LABEL} IN {SOURCE LABEL}` —
e.g. `MAKE IN DATA SHEET (MDS)`, `SL/NO IN SPIR (MIR)`, `P/N IN CROSS SECTION (MXS)`.

Formatting fidelity required: scope headers A:E `#7030A0` bold; source/remarks/final headers `#FFFF00`;
`S.NO` written as text (`'0001'`); freeze panes at A2; data rows 2..(1 + tag count).

`SUMMERY` — A1:I14: `SL NO · DESCRIPTION · ASSET QTY · MDS QTY · MIR QTY · MXS QTY · MOM QTY ·
MTC QTY · REMARKS`, rows 2–6 = the five attributes. QTY columns are per-source non-empty counts,
written as static computed values rather than live formulas (a formula silently recalculates if a cell
is later edited, invalidating an archived result).

**Output validation is mandatory before saving.** Required guards:

1. No comparison verdict for a row whose source values are all empty — `FINAL` and `STATUS` must both
   be blank. Both prior automation attempts in this repository violated exactly that
   (see `docs/SPEC_VALIDATION_REPORT.md` §18.4).
2. No source column present for a source type that did not participate in the run.
3. Row count equals the milestone tag count; tag order matches scope order.
4. No value written into a source column that the canonical layer does not hold — the MOM data-loss
   defect in `AUTOMATED.xlsx` is the regression this prevents.

## 21. Initial API Requirements

### Milestones
```text
POST /api/milestones
GET  /api/milestones
GET  /api/milestones/{id}
```

### Scope
```text
POST /api/milestones/{id}/scope
GET  /api/milestones/{id}/scope
```

### Sources
```text
POST /api/milestones/{id}/sources
GET  /api/milestones/{id}/sources
```

### Runs / Processing
```text
POST /api/runs
GET  /api/runs/{id}
POST /api/runs/{id}/extract
POST /api/runs/{id}/consolidate
POST /api/runs/{id}/compare
```

### Results
```text
GET /api/runs/{id}/canonical
GET /api/runs/{id}/comparison
```

### Review
```text
GET  /api/runs/{id}/review
POST /api/comparison/{id}/review
```

### Outputs
```text
POST /api/runs/{id}/outputs/comparison
GET  /api/runs/{id}/outputs
```

Exact API schemas should be finalized during implementation after validating the domain model.

## 22. Processing State Machine

```text
DRAFT
  ↓
SCOPE_LOCKED
  ↓
DOCUMENTS_UPLOADED
  ↓
EXTRACTING
  ↓
CONSOLIDATED
  ↓
COMPARING
  ↓
REVIEW_REQUIRED
  ↓
COMPLETED
```

## 23. Error Handling

Distinguish:

### Validation
- missing scope
- duplicate milestone tags
- unsupported source type
- invalid workbook structure

### Extraction
- missing sheet
- missing headers
- unreadable file
- ambiguous layout

### Business Data
- source tag not in milestone
- duplicate source tag
- missing source value
- conflicting source records

### System
- filesystem failure
- database failure
- unexpected exception

Errors should identify milestone, run, source, and stage where possible.

## 24. Testing

### Unit
- tag normalization
- duplicate detection
- source adapters
- field mapping
- consolidation
- comparison rules
- lifecycle rules
- review transitions

### Integration
```text
Milestone
→ Upload
→ Extract
→ Consolidate
→ Compare
→ Review
→ Output
```

### Real-file
Use supplied engineering documents.

### Regression
Keep the 717-tag Data Sheet case as a regression fixture.

## 25. Performance

The application must comfortably support the current 717-tag workflow without hard-coding a 717-tag limit.

Measure performance using real engineering files.

## 26. Security / Privacy

No authentication is required for V1.

Keep source documents, outputs, and application data local by default.

## 27. Packaging

Target user experience:

```text
MTL Comparison Tool.exe
        ↓
Local services start
        ↓
Browser opens localhost UI
        ↓
User works locally
```

Packaging should follow stabilization of the processing workflow.

## 28. Future Extensibility

The architecture should permit:

- more source types;
- additional comparison attributes;
- PDF extraction;
- OCR;
- optional AI-assisted explanations;
- richer review;
- audit reporting.

These must not weaken the deterministic comparison foundation.

## 29. Technical Non-Goals

Do not introduce in the first implementation:

- distributed microservices;
- Kubernetes;
- cloud orchestration;
- external message brokers unless genuinely required;
- authentication systems;
- unnecessary frontend frameworks;
- unnecessary analytics platforms;
- AI agents making engineering decisions.

## 30. Definition of Done

A phase is complete only when:

- implementation matches PRD/TRD;
- supplied business rules are respected;
- representative real files have been processed;
- tests pass;
- canonical scope is correct;
- comparison results are validated;
- output is validated;
- source files remain intact;
- historical run behavior is verified;
- no unrelated scope was introduced.
