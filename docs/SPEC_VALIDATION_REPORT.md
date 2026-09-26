# CDC MTL Tool — Specification Validation Report

**Date:** 2026-09-24
**Status:** **SPECIFICATION READY FOR IMPLEMENTATION.** All blocking questions resolved (§21).
**Nothing has been implemented.** No reference or source file has been modified.

---

## Evidence base

Every statement below is derived from files actually inspected in this repository.

| File | Role | Verdict |
|---|---|---|
| `MTL Attribute Values Population.pdf` | **Authoritative priority / lifecycle rules** | Read (1-page flowchart, rendered and transcribed) |
| `5.MTL-DATA MISMATCH COMPARISION - ORIGINAL BACKUP.xlsx` | **Authoritative output structure + human ground truth** | Fully inspected, 6 sheets |
| `input/references/5.MTL-DATA MISMATCH COMPARISION.xlsx` | **Milestone tag scope** (confirmed by user) | 717 tags, A:E |
| `input/sources/datasheet/0904_4391-…_COMPLETED.xlsx` | Real Data Sheet source | 436 rows, fully mapped |
| `5.MTL-DATA MISMATCH COMPARISION - AUTOMATED.xlsx` | **Final output mental model — LAYOUT ONLY** | Layout adopted; **data defective — see §18.4** |
| `output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx` | Older automation output | **Defective — see §18.4** |
| `mtl_phase1.py` | Existing prototype | Does not run against current inputs — see §20.5 |

---

## 1. Product definition

CDC MTL Tool is a **local desktop-style application** (launched by an executable, serving a local browser UI, no cloud, no authentication) that takes a finalized milestone tag scope, consolidates engineering attribute values from multiple source documents against that scope, compares them under the authoritative priority/lifecycle rules, routes the undecidable cases to human review, and produces the final comparison workbook — preserving every run as historical evidence.

Two pillars: **Consolidation** and **Comparison**. Review is part of the comparison/result workflow. Vendor Punch List is **out of scope** (see §7.4 — the authoritative PDF does reference punch lists, and this is a deliberate, documented divergence).

---

## 2. Confirmed business workflow

```
Create Milestone → Import Finalized Tags → Lock Scope → Upload Source Documents
→ Identify / Validate → Extract → Normalize → CONSOLIDATE → Canonical Dataset
→ COMPARE → MATCH / MISMATCH / REVIEW REQUIRED → Human Review
→ Download Final Comparison Excel → Save Run / History
```

This is the Phase 1 slice and it must be usable end-to-end **through the UI**, not only as backend libraries.

---

## 3. Confirmed milestone / run model

- **MILESTONE** = fixed business scope (e.g. `MTL-2026-001`, 717 tags). Immutable once locked.
- **RUN** = one processing attempt against that milestone with a particular set of source documents and a particular `rules_version`.
- A revised source document **creates a new run**; it never overwrites a historical run.
- **Verified:** the tag scope file contains 717 rows, 717 distinct tags, zero duplicates, zero blanks. All five sheets of the ORIGINAL BACKUP carry exactly those 717 tags **in identical order** — confirming the scope file is the row universe and the output preserves its ordering.

---

## 4. Confirmed source-document types

The authoritative PDF defines **seven** sources in strict priority order. The existing workbook has columns for only **six**.

| Priority | PDF name | Code | Workbook column label | Present in workbook |
|---|---|---|---|---|
| **1** | Photography Name Plate | ASSET | `… IN ASSET PHOTO` (F) | Yes |
| **2** | Data Sheet | MDS | `… IN DATA SHEET (MDS)` (G) | Yes |
| **3** | SPIR Sheet | SPIR / MIR | `… IN SPIR (MIR)` (H) | Yes |
| **4** | **GA Document** | **GA** | *(created on upload)* | **Optional — dynamic** |
| **5** | Cross Section DWG | MXS | `… IN CROSS SECTION (MXS)` (I) | Yes |
| **6** | Test Certificate | MTC | `… IN TEST CERTIFICATE (MTC)` (K) | Yes |
| **7** | O&M Manuals | MOM | `… IN O&M MANUAL (MOM)` (J) | Yes |

Two findings:

1. **GA Document (priority 4) has no column in the existing workbook — resolved as an optional, dynamic source.** GA is supported from the outset but no GA-specific adapter or layout may be invented until a real sample exists. If a GA document is uploaded for a run, GA participates fully at priority 4 and a GA column is created on every attribute sheet in priority position; if it is not uploaded, **no empty GA column is produced**. The same applies to any future source type.
2. **Workbook column order ≠ priority order.** The workbook places MOM (priority 7) at column J, before MTC (priority 6) at column K. Column order is a display choice and priority is a rule; they are independent, but the implementation must never infer priority from column position.

### 4.1 Source columns are dynamic

The set of source columns is determined **per run** by the documents actually uploaded. The comparison
engine must not compile in a fixed source list. Example — without GA:

```
MAKE:  ASSET · DATA SHEET · SPIR · MXS · MTC · MOM · FINAL
```

with GA uploaded:

```
MAKE:  ASSET · DATA SHEET · SPIR · GA · MXS · MTC · MOM · FINAL
```

The same applies to TAG NUMBER, MODEL, SERIAL NUMBER, PART NUMBER and any future attribute. No run
requires every possible source to exist, and a future source type must be addable without rewriting the
comparison engine.

---

## 5. Actual source-document structures

### 5.1 Data Sheet (verified in full)

Workbook tabs: `DATASHEET` (extract), `PRD COUNT` (ignore — per-document completion tracker, 52 documents), `Sheet1` (ignore — scratch).

`DATASHEET`: 22 columns, header row 1, **436 data rows**, 436 unique tag keys, **zero duplicates**.

| Purpose | Col | Header | Non-empty |
|---|---|---|---|
| **Join key** (milestone tag) | B | `TAG NUMBER` | 436 |
| **TAG NUMBER** attribute | G | `" TAG NUMBER AS PER DOC"` *(leading space)* | **357** |
| MAKE | J | `MAKE` | 124 |
| MODEL | K | `MODEL` | 98 |
| SERIAL NUMBER | L | `SERIAL NUMBER` | 0 |
| PART NUMBER | M | `PART NUMBER` | 0 |
| Provenance — document | F | `DATASHEET REFERENCE-ORIGINAL` | 436 |
| Provenance — page | H | `PAGE NO` | 402 |

Other columns present and out of scope for now: `E DOC IDB`, `I SIZE & RATING`, `N/O WEIGHT+UNIT`, `P COUNTRY`, `Q MESC NUMBER`, `R EQPT HAZARDOUS CLASSIFICATION`, `S ADDITIONAL INFORMATION`, `T REMARKS`, `U NAME`, `V DATE`.

**Column B vs column G is the critical distinction.** B is the milestone tag the worker was searching for (the join key). G is the tag actually printed on the document (the compared value). Conflating them makes every tag trivially MATCH and destroys the purpose of the TAG NUMBER sheet. Verified: of the 357 rows with a G value, **343 equal the join key and 14 differ** — e.g. `68-SP-051 → SP-123`, `88-LT-802 → 88-LIT-802`, `68-TIT-1987 → TIT-1987`.

**Cross-validation:** the Data Sheet's own fill counts (TAG 357, MAKE 124, MODEL 98, SERIAL 0, PART 0) match the MDS column of the human ORIGINAL BACKUP **exactly**. The Data Sheet adapter therefore has a verified oracle.

### 5.3 Field discovery — semantic, never positional

Source layouts are similar but **not guaranteed identical**. A later revision of the same source may
place `MAKE` in column H rather than column J. No adapter may encode a column position.

```text
header cell → normalize (trim, collapse whitespace, upper-case, strip punctuation noise)
            → match against the controlled alias table
            → exactly one confident match → bind field to that column
            → zero or multiple matches    → AmbiguousFieldMapping (never guess)
```

| Field | Accepted aliases (extended only from real files) |
|---|---|
| TAG NUMBER (join key) | `TAG NUMBER`, `TAG`, `TAG NO` |
| TAG NUMBER (attribute) | `TAG NUMBER AS PER DOC`, `TAG NUMBER AS PER DOCUMENT` |
| MAKE | `MAKE`, `MANUFACTURER`, `MFR`, `OEM` |
| MODEL | `MODEL`, `MODEL NO`, `MODEL NUMBER` |
| SERIAL NUMBER | `SERIAL`, `SERIAL NUMBER`, `SERIAL NO` |
| PART NUMBER | `PART`, `PART NUMBER`, `PART NO` |

Adapters tolerate differing column order, extra columns, absent irrelevant columns, and minor
header / capitalization / spacing variation. **Blind substring matching is prohibited** — a header
merely containing `PART` must not bind `PART NUMBER`, and the join-key `TAG NUMBER` must never be
confused with the attribute `TAG NUMBER AS PER DOC`. The real Data Sheet has both, three columns apart.

On `AmbiguousFieldMapping` the system flags the mapping, names the source document, lists the candidate
columns and every header found, and routes the run to a review/error state. A wrong column is never
silently bound because it sits in a familiar position.

### 5.2 Other six sources

Per user direction, the other documents carry the same kind of values in the same worker-export shape as the Data Sheet. Adapters will be built on a shared tabular base (join key + tag-as-per-doc + attribute columns + document/page provenance), with the exact header mapping **verified per type against a real file before that adapter is enabled**. Native files for ASSET, SPIR, GA, MXS, MOM, MTC are not yet in the repository → **Blocker Q4**.

**Important asset already available:** the ORIGINAL BACKUP contains human-extracted values for all six workbook sources across all five attributes. That is a ready-made **validation oracle** — when a real source file arrives, its adapter output can be diffed against the corresponding column of the backup.

Per-source non-empty counts in the ORIGINAL BACKUP:

| Attribute | ASSET | MDS | SPIR | MXS | MOM | MTC |
|---|---|---|---|---|---|---|
| TAG NUMBER | 82 | 357 | 377 | 161 | 123 | 0 |
| MAKE | 98 | 124 | 458 | 228 | 132 | 25 |
| MODEL | 85 | 98 | 355 | 10 | 5 | 25 |
| SERIAL NUMBER | 90 | 0 | 331 | 24 | 0 | 12 |
| PART NUMBER | 28 | 0 | 370 | 65 | 0 | 0 |

---

## 6. Confirmed comparison attributes

Five, confirmed by the ORIGINAL BACKUP sheet set:

`TAG NUMBER` · `MAKE` · `MODEL` · `SERIAL NUMBER` · `PART NUMBER`

**TAG NUMBER is structurally different from the other four.** It is compared against the milestone tag (an always-present master value); the other four are compared among sources only, with no master. This is confirmed by the human FINAL behaviour in §9.3.

---

## 7. Authoritative priority / lifecycle rules (from the PDF)

The PDF `MTL Attribute Values Population.pdf` is a single-page flowchart. Transcribed:

```
Start → Data Collection / Segregate Tag wise documents
         (fed by: Photography Data / DOC Master Data)
   ↓
1  Identify MTL Attribute Values from Photography Name Plate
        Yes → Populate MTL Attribute Values
        No  → Raise Request to CDC-ONSITE
   ↓
2  Identify MTL *Missing* Attribute Values from Data Sheet       No → Create Punch List   [2 ≠ 1 3 4 5 6 7]
   ↓
3  Identify MTL *Missing* Attribute Values from SPIR Sheet       No → Create Punch List   [3 ≠ 1 2 4 5 6 7]
   ↓
4  Identify MTL *Missing* Attribute Values from GA Document      No → Create Punch List   [4 ≠ 1 2 3 5 6 7]
   ↓
5  Identify MTL *Missing* Attribute Values from Cross Section DWG No → Create Punch List  [5 ≠ 1 2 3 4 6 7]
   ↓
6  Identify MTL *Missing* Attribute Values from Test Certificate No → Create Punch List   [6 ≠ 1 2 3 4 5 7]
   ↓
7  Identify MTL *Missing* Attribute Values from O&M Manuals      No → Create Punch List   [7 ≠ 1 2 3 4 5 6]
   ↓
Data Quality Check → End

Note: "Consider Latest date Document from Following Documents for MTL Data Population"  [2 3 4 5 6 7]
```

Four rules follow directly:

- **RULE-P1 (Priority / population).** Sources are consulted in rank order 1→7. Step 1 populates attribute values; steps 2–7 populate only *missing* attribute values. Therefore **FINAL = the value from the highest-ranked source that has a non-empty value.**
- **RULE-P2 (Lifecycle).** Where several candidate documents exist among ranks 2–7, use the **latest-dated document**.
- **RULE-P3 (Mismatch detection).** The `N ≠ 1 2 3 …` badges beside each "Create Punch List" branch mean: where source N's value disagrees with the other sources' values, the disagreement is raised. This is the MISMATCH condition.
- **RULE-P4 (Escalation).** If the Photography Name Plate yields nothing, `Raise Request to CDC-ONSITE`. For ranks 2–7, a failure yields `Create Punch List`.

### 7.4 Documented divergences from the PDF

| PDF element | Decision | Reason |
|---|---|---|
| `Create Punch List` | **Not implemented as a punch list.** Mapped to comparison state + REMARKS + review queue. | Vendor Punch List is explicitly out of scope for this version. |
| `Raise Request to CDC-ONSITE` | Not implemented. | Operational action outside the tool. |
| `Data Quality Check` | Realised as the review stage + output validation. | No further definition given in the PDF. |
| GA Document (rank 4) | No workbook column exists. | → Blocker Q3. |

### 7.5 Validation of RULE-P1 against human ground truth

I applied "first non-empty value by PDF priority" to the ORIGINAL BACKUP and compared it to the FINAL values a human actually wrote:

| Sheet | Human FINAL filled | Rule reproduces human | Disagrees |
|---|---|---|---|
| MAKE COMPARISION | 34 rows | **29 (85.3%)** | 5 (14.7%) |
| TAG NUMBER COMPARISION | 668 rows | 411 (61.5%) | 257 (38.5%) |

**MAKE:** the rule is correct. All 5 disagreements are manufacturer *naming-variant* judgements, not priority errors:

| Row | Sources | Priority picks | Human picked |
|---|---|---|---|
| 72–74 | MDS `TELEDYNE`, SPIR `SIMTRONICS TELEDYNE` | `TELEDYNE` (rank 2) | `SIMTRONICS TELEDYNE` |
| 91 | ASSET `E2S WARNING SIGNAL`, SPIR `E2S` | `E2S WARNING SIGNAL` (rank 1) | `E2S` |
| 99 | ASSET `E2S WARNING SIGNALS`, SPIR `E2S` | `E2S WARNING SIGNALS` (rank 1) | `E2S` |

Note the human chose the *longer* string in rows 72–74 and the *shorter* string in rows 91/99. **The naming-variant rule is not derivable and must not be invented** → Blocker Q2.

**TAG:** all 257 "disagreements" are rows where *no source has any value*, yet the human still wrote the milestone tag. This is not a failure of RULE-P1 — it confirms the TAG attribute is special-cased (§9.3).

---

## 8. Consolidation rules

Consolidation is milestone-scope-anchored, pure and deterministic: `(MilestoneTag[], SourceRecord[]) → CanonicalCell[]`.

```
for tag in milestone.tags:              # ← the outer loop is ALWAYS the scope
    for attribute in ATTRIBUTES:
        for source in SOURCE_TYPES:
            records = index[(tag.normalized_tag, attribute, source)]
            0 records  → ABSENT_TAG or ABSENT_VALUE
            1 record   → PRESENT
            2+ records → CONFLICTING_DUPLICATE  (never last-write-wins)
```

- **CR-1.** The outer loop is the milestone scope. 717 tags in → 717 rows out, always. This makes the scope-authority rule true *by construction*, not by assertion.
- **CR-2.** Source rows whose tag is outside the milestone are never merged and never extend scope; they are counted and reported as `unmatched_tag_count` on the run. *(Verified: for the current Data Sheet this count is 0 — all 436 keys are inside the 717.)*
- **CR-3.** Three-way absence, because Excel renders all three as blank but they mean different things:
  - `ABSENT_TAG` — the source has no row for this tag (281 tags for the Data Sheet)
  - `ABSENT_VALUE` — the source has the tag but the field is empty (79 Data Sheet rows)
  - `PRESENT` — a value exists
- **CR-4.** Every `PRESENT` cell carries provenance: source document, SHA-256, sheet, row, column, and — where the source offers it — the engineering document reference and page number.
- **CR-5.** Normalization applied before comparison, evidence-backed only:
  - trim leading/trailing whitespace
  - a whitespace-only cell is empty *(1 real occurrence found: MXS MODEL, row 3)*
  - case-insensitive equality
  - **no** punctuation stripping, abbreviation expansion, or prefix/substring matching — §7.5 proves those are judgement calls.

**Canonical output shape for the current fixture:** 717 tags × 5 attributes × 6 sources = **21,510 cells**.

---

## 9. Comparison rules

Comparison consumes canonical cells only. It never opens a source file.

### 9.1 Applicable-value vector

For each `(tag, attribute)`, collect the non-empty normalized values across sources, in priority order.

### 9.2 State assignment

| Condition | State |
|---|---|
| ≥2 applicable values, all equal | **MATCH** |
| Exactly 1 applicable value, none conflicting | **MATCH** (agreed single-source rule) |
| ≥2 applicable values, not all equal | **MISMATCH** |
| Conflicting duplicate source records for the same tag+attribute+source | **REVIEW REQUIRED** |
| Priority/lifecycle exception, or naming/interpretation ambiguity | **REVIEW REQUIRED** |
| **0 applicable values** | **FINAL and STATUS both left BLANK** |

**Blank is not a status.** Where no applicable source holds a value there is no final value and no
comparison result to produce, so both cells stay empty. This resolves Q1 and introduces no fourth state.

### 9.3 FINAL value

- **TAG NUMBER:** `FINAL TAG = the milestone TAG NUMBER`. Verified: 667 of 668 human-filled rows equal the milestone tag (99.9%); the single exception (row 114: master `68-C-JB-7460`, final `6130-IRC-006`) is an evident data-entry error in the source workbook.
- **MAKE / MODEL / SERIAL NUMBER / PART NUMBER:** `FINAL = first non-empty value by priority rank` (RULE-P1), auto-elected on MATCH. On MISMATCH or REVIEW REQUIRED the proposed value is shown but FINAL is **not** auto-committed until reviewed.

### 9.4 Observed distribution over the real data

Applying §9.1 to the ORIGINAL BACKUP, across all 717 × 5 = 3,585 comparisons:

| Situation | Count | % |
|---|---|---|
| No source has a value | **1,430** | 39.9% |
| Exactly one source has a value | 1,162 | 32.4% |
| Two or more, all agree | 403 | 11.2% |
| Two or more, disagree | 590 | 16.5% |

Per sheet:

| Sheet | Zero | One | Agree | Conflict |
|---|---|---|---|---|
| TAG NUMBER | 243 | 148 | 191 | 135 |
| MAKE | 223 | 113 | 79 | 302 |
| MODEL | 294 | 288 | 36 | 99 |
| SERIAL NUMBER | 330 | 322 | 49 | 16 |
| PART NUMBER | 340 | 291 | 48 | 38 |

**The 1,430 zero-source cells (40% of the workbook) are written blank** — no FINAL value and no STATUS
(Q1, resolved). The remaining 2,155 cells carry a verdict: 1,565 resolve to MATCH by the single-source
and full-agreement rules, and the 590 conflicting cells resolve to MISMATCH or REVIEW REQUIRED
according to the rules file.

---

## 10. Exact definitions

**MATCH** — The applicable source values agree under the authoritative comparison rules. Also: exactly one applicable source has a non-empty value and no other applicable source holds a conflicting value. Any exception defined by the authoritative PDF takes precedence.

**MISMATCH** — Two or more applicable sources hold non-empty values that conflict under the authoritative comparison rules (PDF RULE-P3).

**REVIEW REQUIRED** — The result cannot be safely finalized deterministically. Includes: conflicting duplicate source records for the same tag/attribute/source; a priority or lifecycle exception the rules flag for judgement; naming-variant ambiguity of the kind evidenced in §7.5; and any condition the authoritative rules identify as requiring human judgement.

**BLANK (not a state)** — No applicable source holds a value, therefore no final value and no comparison result can be produced. `FINAL` and `STATUS` are both left empty.

`PENDING`, `NOT AVAILABLE` and `RESOLVED` are **not** comparison states. Absence is represented in the canonical layer (`ABSENT_TAG` / `ABSENT_VALUE`) for coverage reporting, never as a comparison verdict.

---

## 11. Handling of missing source values

- Missing values are recorded in the canonical layer with the three-way distinction in CR-3 and are **never fabricated**.
- A missing value does not remove the tag, the row, or the source column.
- Missing values are excluded from the applicable-value vector, so they cannot by themselves create a MISMATCH.
- Coverage (per-source non-empty counts) is reported on the SUMMERY sheet `… QTY` columns and on the run record.
- **Resolved (Q1):** where *every* applicable source is missing a value, `FINAL` and `STATUS` are both left blank. No status is invented for this case.

---

## 12. Handling of duplicate / conflicting source records

- Duplicate detection is per `(normalized_tag, attribute, source_type)` within a run.
- **No last-write-wins.** All conflicting records are retained as distinct `SOURCE_RECORD` rows with full provenance.
- The affected canonical cell is marked `CONFLICTING_DUPLICATE`; the comparison result becomes **REVIEW REQUIRED**; the reviewer sees every candidate value with its document, page and row.
- A duplicate in one source never blocks processing of other tags or other sources.
- Where duplicates arise from several documents of the same type, **RULE-P2 applies first**: prefer the latest-dated document. Only genuinely undatable or same-date conflicts reach review.
- *Verified:* the current Data Sheet has **zero** duplicate keys, so this path requires a synthetic fixture.

---

## 13. Canonical data model

Stored **long** (one row per tag × attribute × source), pivoted to wide only by the output writer. A wide table cannot carry per-cell provenance and would need a schema migration for every new source type — and the PDF has just added a seventh (GA).

```
CANONICAL_CELL
  id, run_id, milestone_tag_id, attribute, source_type,
  raw_value, normalized_value, state,            -- PRESENT | ABSENT_TAG | ABSENT_VALUE | CONFLICTING_DUPLICATE
  source_record_id                                -- provenance anchor
```

---

## 14. Database model (SQLite)

```
PROJECT ──< PACKAGE ──< MILESTONE ──┬──< MILESTONE_TAG
                                    ├──< SOURCE_DOCUMENT
                                    └──< PROCESSING_RUN ──┬──< RUN_SOURCE
                                                          ├──< SOURCE_RECORD
                                                          ├──< CANONICAL_CELL
                                                          ├──< COMPARISON_RESULT ──< REVIEW_DECISION
                                                          └──< OUTPUT_ARTIFACT
```

- **MILESTONE** — `id, milestone_code UNIQUE, project_id, package_id, status, scope_locked_at, created_at, updated_at`
- **MILESTONE_TAG** — `id, milestone_id, scope_order, s_no, tag_number, normalized_tag, tag_description, equipment_description, size_rating` · `UNIQUE(milestone_id, normalized_tag)` — this constraint *is* the scope-authority rule. `s_no` stored as **text** (`'0001'`, zero-padded, must round-trip).
- **SOURCE_DOCUMENT** — `id, milestone_id, source_type, original_filename, stored_path, file_size, sha256, document_date, revision, uploaded_at`. `document_date` exists to serve RULE-P2.
- **PROCESSING_RUN** — `id, milestone_id, run_number, status, rules_version, started_at, completed_at, notes`
- **RUN_SOURCE** — `run_id, source_document_id, processing_status, row_count, recognized_tag_count, matched_tag_count, unmatched_tag_count`. Per-run stats live on the join, not the document: the same file under a newer `rules_version` is a different result.
- **SOURCE_RECORD** — `id, run_id, source_document_id, source_type, source_row_index, source_tag, normalized_tag, attribute, raw_value, normalized_value, source_location JSON`
- **CANONICAL_CELL** — as §13
- **COMPARISON_RESULT** — `id, run_id, milestone_tag_id, attribute, state, final_value, final_source_type, remarks, rule_id, is_auto, computed_at`
- **REVIEW_DECISION** — `id, comparison_result_id, decision, final_value, remarks, reviewed_at, reviewed_by` — **append-only**
- **OUTPUT_ARTIFACT** — `id, run_id, kind, stored_path, sha256, generated_at`

---

## 15. File-storage model

```
MTL_DATA/
├── database/mtl.db
├── milestones/MTL-2026-001/
│   ├── scope/         original scope workbook (immutable)
│   ├── sources/       <sha256>.<ext>  (content-addressed, immutable)
│   ├── extracted/     per-run extraction dumps
│   ├── canonical/     per-run canonical snapshots
│   ├── comparison/    per-run comparison snapshots
│   ├── review/        review exports
│   └── outputs/       generated workbooks
└── logs/
```

**Refinement adopted:** source files are stored **content-addressed** by SHA-256, with the original filename kept as metadata. This makes immutability and the new-run-on-revision rule structural rather than a matter of discipline: an identical re-upload is detected and reuses evidence; a genuinely revised file gets a different hash and cannot collide with the old one.

---

## 16. API / backend architecture

```
React + TS + Vite  →  FastAPI (localhost)  →  Processing engine  →  SQLite + filesystem
```

Layer rules, enforced by import boundaries:
- `api` imports services and domain only — no engineering logic in route handlers
- `comparison` **never** imports `extraction` (it reads canonical data only)
- nothing below `api` imports FastAPI
- nothing except `extraction/` and `output/` imports openpyxl
- the processing engine is runnable headlessly, independent of the UI

Endpoints (per TRD §21): milestones, scope, sources, runs (`extract` / `consolidate` / `compare`), canonical, comparison, review, outputs.

**Rules are data, not code.** Priority order, lifecycle, equality semantics and final-value permissions live in a versioned `rules/v1.yaml`, loaded at run time, with `rules_version` stamped on every run. This is what makes runs reproducible and makes a future rules revision a data change plus tests rather than an engine rewrite.

---

## 17. UI workflow

No KPI dashboard. Workflow-first.

1. **Home / History** — milestones, runs, dates, status; reopen any historical run
2. **Create Milestone** — code, project, package
3. **Milestone Workspace** — `SCOPE | SOURCES | CONSOLIDATION | COMPARISON | REVIEW | RESULTS`
   - **SCOPE** — import finalized tags, validate count, lock
   - **SOURCES** — upload, auto-identify type, validation report, per-source coverage stats
   - **CONSOLIDATION** — canonical grid, coverage per source, unmatched/out-of-scope report
   - **COMPARISON** — per-attribute result grid, filterable by state
   - **REVIEW** — queue of REVIEW REQUIRED (and MISMATCH) rows showing every source value with provenance; reviewer sets FINAL + remarks
   - **RESULTS** — generate and download the workbook; list prior outputs
4. **Review** and **Results** also reachable directly.

---

## 18. Actual comparison output / template structure

### 18.1 The authoritative structure (ORIGINAL BACKUP)

Six sheets: `SUMMERY`, `TAG NUMBER COMPARISION`, `MAKE COMPARISION`, `MODEL COMPARISION`, `SERIAL NUMBER COMPARISION`, `PART NUMBER COMPARISION`.

**The sheets are not uniform.** Verified:

| Sheet | Cols | Has FINAL? |
|---|---|---|
| TAG NUMBER COMPARISION | 13 (A:M) | `FINAL TAG` |
| MAKE COMPARISION | 13 (A:M) | `FINAL MAKE` |
| MODEL COMPARISION | **12 (A:L)** | **none** |
| SERIAL NUMBER COMPARISION | **12 (A:L)** | **none** |
| PART NUMBER COMPARISION | **12 (A:L)** | **none** |

Common layout: `A S.NO · B TAG NUMBER · C TAG DISCRIPTION · D EQUIPMENT DESCRIPTION · E SIZE & RATING · F–K six source columns · L REMARKS · [M FINAL …]`

`SUMMERY` is **A1:I14** — `SL NO · DESCRIPTION · ASSET QTY · MDS QTY · MIR QTY · MXS QTY · MOM QTY · MTC QTY · REMARKS`, rows 2–6 = the five attributes, rows 12–14 a human scratch list of remark phrases. All QTY cells are **empty** in the human original.

Formatting: scope headers A:E filled `#7030A0` bold; source/remarks/final headers `#FFFF00`; no data-cell colour coding; `S.NO` is text `'0001'`; rows 2–718.

### 18.2 Dynamic generation (per your latest direction)

The workbook is **generated**, not cloned. Sheets and source columns are created from the registered attributes × the source types actually present, so adding GA (or a new attribute) adds a column (or a sheet) without a template edit.

Header naming follows the observed convention `{ATTRIBUTE LABEL} IN {SOURCE LABEL}` — e.g. `MAKE IN DATA SHEET (MDS)`, `SL/NO IN SPIR (MIR)`, `P/N IN CROSS SECTION (MXS)`.

**Documented divergence:** the human headers are internally inconsistent — `MAKE IN ASSET ` (trailing space), `MODEL NUMBER IN (MDS)` (source name omitted), `SPIR(MIR)` vs `SPIR (MIR)`. The generator will emit the **consistent** form. This is a deliberate normalization; flagged as Q5 in case the exact legacy strings are contractually required.

### 18.3 Confirmed target structure

The **working file** is the tag-scope workbook `5.MTL-DATA MISMATCH COMPARISION.xlsx`, which arrives
carrying only `S.NO · TAG NUMBER · TAG DISCRIPTION · EQUIPMENT DESCRIPTION · SIZE & RATING`. The system
**creates the comparison sheets and populates the source columns automatically**, producing a workbook
shaped like the mental-model reference `…- AUTOMATED.xlsx`.

Confirmed:

- **`STATUS`** on every comparison sheet, carrying MATCH / MISMATCH / REVIEW REQUIRED — or blank where
  no applicable source holds a value.
- **`FINAL <attribute>`** on **all five** sheets (Q6 resolved — the human original has it on only two).
- Source columns created **only for the source types participating in the run**, ordered by
  authoritative priority rank. A source type not uploaded produces **no column**, never an empty
  placeholder.
- SUMMERY `… QTY` columns populated with per-source non-empty counts as **static computed values**
  (Q7 — a live formula silently recalculates if a cell is later edited, invalidating an archived result).

### 18.4 `AUTOMATED.xlsx` — layout authoritative, data defective

Its **layout** is the approved mental model (five comparison sheets, source columns, REMARKS, FINAL,
STATUS). Its **contents are not authoritative**, and the defects below must not be reproduced.

**`… - AUTOMATED.xlsx`:** a cell-by-cell diff against ORIGINAL BACKUP shows it **destroyed 123 real MOM tag values** (`TAG NUMBER IN O&M MANUAL(MOM)`: 123 changed, 123 lost, 0 gained), and its SUMMERY consequently reports `MOM QTY = 0`. It also bulk-generated REMARKS the human never wrote (MAKE +232, MODEL +393, SERIAL +346, PART +378) and auto-filled FINAL on 448/332/374/339 rows, and it uses the now-banned `PENDING` state (223–340 rows per sheet).

**`output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx`:** internally inconsistent — rows with no source value in any column carry MATCH/MISMATCH verdicts (SERIAL: all six source columns empty across all 717 rows, yet 371 MATCH + 16 MISMATCH).

Both embed invented equality rules in SUMMERY remarks ("contained manufacturer abbreviations", "unambiguous prefix", "clear majority"). **None of that is authoritative.** §7.5 shows why: the human's own naming-variant choices go in opposite directions.

**Recommendation:** keep `AUTOMATED.xlsx` in place as the layout reference, with a README recording
that only its structure is authoritative. Move `output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx` to
`reference/untrusted/` — it is defective in both structure and data.

These two defects are exactly what output-validation guards 1 and 4 (TRD §20) exist to prevent.

### 18.5 Human REMARKS are sparse and unreliable — not an oracle

On the TAG sheet, **169 rows** have a source value differing from the master tag, but only **35** carry a human remark — and of those, at least 2 name the wrong source (rows 95 and 99: derived `ASSET PHOTO,SPIR`, human wrote `TAG MISMATCH WITH DATA SHEET,SPIR`). Two further remarks (`NOT IN SAP`) encode external knowledge not present in the workbook. The MAKE sheet has 11 remarks including a typo (`MALE NOT AVL`). MODEL, SERIAL and PART sheets have **zero** remarks.

REMARKS will therefore be **generated deterministically** by the engine, following the observed vocabulary (`{ATTRIBUTE} MISMATCH WITH {SOURCE LIST}`, `{ATTRIBUTE} NOT AVL`), with reviewer remarks stored separately and never overwritten.

---

## 19. History / audit model

Reopening a milestone must surface: milestone metadata and date; the finalized tag scope as imported; every source document with `original_filename, source_type, revision, document_date, upload timestamp, SHA-256, file_size, processing_status, row_count, recognized_tag_count, matched_tag_count, unmatched_tag_count`; every processing run with its `rules_version`; the canonical dataset; comparison results; review decisions; and generated outputs.

Guarantees: source files and scope are immutable; runs are additive; review decisions are append-only; outputs are hashed at generation. A run is fully reproducible from `(scope, source hashes, rules_version)`.

---

## 20. Phase 1 exact scope

A complete, usable end-to-end slice through the UI. Nothing core is deferred to make it smaller.

**In scope**

1. Create milestone; import finalized tags from the scope workbook; validate; **lock scope**
2. Upload source documents; identify/validate type; hash and store immutably; report coverage
3. Extract + normalize — **Data Sheet adapter fully functional**; other adapters built on the shared tabular base with semantic header discovery (§5.3) and enabled as each real file is supplied and verified. GA included on the same terms if a GA document is uploaded.
4. Consolidate into the canonical dataset — `tags × attributes × participating sources` (21,510 cells for the current fixture's six sources)
5. Compare under `rules/v1.yaml` implementing RULE-P1, P2, P3 → MATCH / MISMATCH / REVIEW REQUIRED, or blank where no source holds a value
6. Review UI for REVIEW REQUIRED and MISMATCH rows, with full provenance; decisions persisted
7. Generate the comparison workbook — dynamically built from the participating sources, with REMARKS, FINAL and STATUS on every sheet
8. Save run; browse history; reopen a historical milestone and run
9. FastAPI backend + React/TS/Vite UI, SQLite, local filesystem

**Out of scope for Phase 1:** packaging to `.exe` (after the workflow stabilises); Vendor Punch List; authentication; cloud; AI; OCR/PDF extraction of native source documents.

**Regression fixture (golden, verified):**

```
Milestone scope .............................. 717 tags (717 unique, 0 duplicates)
Data Sheet rows .............................. 436  (436 unique keys, 0 duplicates)
DS keys within scope ......................... 436   outside scope: 0
Scope tags with no DS row .................... 281   → ABSENT_TAG
TAG NUMBER present from MDS .................. 357   (79 ABSENT_VALUE; 343 equal key, 14 differ)
MAKE / MODEL / SERIAL / PART from MDS ........ 124 / 98 / 0 / 0
Canonical cells .............................. 21,510
MDS columns must equal ORIGINAL BACKUP exactly
```

### 20.5 Disposition of `mtl_phase1.py`

It **does not run** against the current inputs — verified:

```
VALIDATION ERROR: Reference workbook is missing required sheet(s):
['MAKE COMPARISION','MODEL COMPARISION','SERIAL NUMBER COMPARISION','PART NUMBER COMPARISION'].
Found: ['SUMMERY','TAG NUMBER COMPARISION']
```

It was written against a template that is not in the repository, and it clones a template rather than generating one. Its valuable ideas migrate into the architecture: the B-vs-G tag distinction, refusing to guess on duplicates, validating output before saving, and never mutating inputs. **Keep it in place, untouched, until Phase 1 passes its regression fixture; then retire it.**

---

## 21. Decision log and remaining confirmations

### 21.1 Decision log — all blocking questions resolved (2026-09-24)

| # | Question | **Decision** |
|---|---|---|
| **Q1** | State when no source holds a value (1,430 cells, 40%) | **Leave `FINAL` and `STATUS` blank.** Blank is not a status; it means no applicable source value exists, so no result can be produced. No fourth state is introduced. |
| **Q2** | Naming-variant equality (`TELEDYNE` vs `SIMTRONICS TELEDYNE`; `E2S` vs `E2S WARNING SIGNAL`) | **REVIEW REQUIRED.** No equality rule is invented. Ambiguous naming/interpretation routes to human judgement. |
| **Q3** | GA Document has no workbook column | **GA is an optional, dynamically included source at priority 4.** Uploaded → participates fully and a GA column is created on every attribute sheet in priority position. Not uploaded → no GA column at all. No GA adapter or layout may be assumed until a real sample exists. |
| **Q4** | No native source files for the other six types | **Resolved in approach.** All source documents arrive in the same worker-export shape as the supplied Data Sheet. Adapters are built on a shared tabular base using semantic header discovery against a controlled alias table (§5.3), each verified against its real file before being enabled. |
| **Q6** | FINAL columns on MODEL / SERIAL / PART | **Yes — every comparison sheet carries `REMARKS`, `FINAL <attribute>` and `STATUS`**, per the mental-model reference `…- AUTOMATED.xlsx`. |

### 21.2 Minor confirmations outstanding — none blocking

These are routine calls I have made so that implementation is not held up. Each is a one-line change if
you prefer otherwise.

- **Q5 — Header strings.** *Decision:* reproduce the real workbook's per-attribute/per-source labels verbatim for the six known sources, and apply the `{ATTRIBUTE} IN {SOURCE}` convention to any new source type (including GA). This keeps existing business-facing wording intact while making new columns well-formed.
- **Q7 — SUMMERY QTY columns.** *Decision:* **static computed values.** The mental-model reference uses live `COUNTIF`/`SUMPRODUCT` formulas, but an archived evidence workbook must not silently recalculate if a cell is later edited.
- **Q8 — Lifecycle document dates.** RULE-P2 needs a date per source document. *Decision:* capture `document_date` at upload — pre-filled from a date found in the file where one exists, user-editable. RULE-P2 is only ever invoked when two documents of the same source type both supply a value for the same tag + attribute, so this does not gate Phase 1.
- **Q9 — `NOT IN SAP` remarks.** *Decision:* external knowledge, not derivable from any source document. Available only as a reviewer-entered remark; never generated.
- **Q10 — Row 114 anomaly** in `ORIGINAL BACKUP` (`FINAL TAG = 6130-IRC-006` against master `68-C-JB-7460`). *Decision:* treated as a data-entry error in that reference file, not a rule. It does not affect implementation.

**Housekeeping**

- Root `claude.md` is an older, shorter variant of the full project instructions; the two should not compete. Proposal: replace it with the updated full version (see §22).
- Repository has **zero git commits**. An initial commit before implementation would protect the supplied reference files.
- The two defective workbooks currently sit at the repo root — proposal in §18.4.

---

## 22. Recommended implementation sequence after approval

| Step | Deliverable | Gate |
|---|---|---|
| **0** | Initial git commit; move defective workbooks to `reference/untrusted/`; add `pytest`, `fastapi`, `pydantic`, `sqlalchemy`, `pypdf` to `requirements.txt` | — |
| **1** | `domain/` — types, tag normalization, scope model + scope importer. Unit tests. | Scope import yields exactly 717 tags, `'0001'` preserved as text |
| **2** | `extraction/` — adapter protocol, registry, **DataSheetAdapter** (header-driven, not position-hardcoded). Unit tests + real-file test. | 436 records; MDS values match ORIGINAL BACKUP exactly |
| **3** | `consolidation/engine.py` + three-way absence + provenance. Unit + property tests. | 21,510 cells; 281 ABSENT_TAG, 79 ABSENT_VALUE |
| **4** | `comparison/` + `rules/v1.yaml` implementing RULE-P1/P2/P3, dynamic source set. | MAKE FINAL reproduces the human's 29/34 priority-consistent rows; the 5 naming-variant rows route to REVIEW REQUIRED; zero-source rows produce blank FINAL + blank STATUS |
| **5** | `output/comparison_workbook.py` — dynamic sheet/column generation, formatting fidelity. | Structure matches the mental-model reference; guards: no verdict on an all-empty row, no column for a non-participating source, no value absent from the canonical layer |
| **6** | `storage/` — SQLite schema, repositories, content-addressed file vault, runs & history. | Reopen a historical run intact; input hashes unchanged |
| **7** | `api/` — FastAPI endpoints over the engine. | Full pipeline drivable over HTTP |
| **8** | `frontend/` — the six workspace tabs + Home/History. | End-to-end Phase 1 slice usable through the UI |
| **9** | Remaining source adapters (incl. GA), one per real file supplied. | Each adapter's output diffed against its ORIGINAL BACKUP column |
| **10** | Packaging to a local executable. | After the workflow stabilises |

**All steps are unblocked.** Step 9 proceeds per source type as each real file arrives; the absence of a
GA sample does not hold up steps 1–8, because GA participates through the same dynamic source mechanism
as every other type.
