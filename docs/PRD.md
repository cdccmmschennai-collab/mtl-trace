# CDC MTL Tool — Product Requirements Document (PRD)

**Version:** 1.2
**Status:** Validated against the actual repository files (2026-09-24). See `docs/SPEC_VALIDATION_REPORT.md`.

> **Changes in 1.1** — driven by the authoritative `MTL Attribute Values Population.pdf` and the real
> `5.MTL-DATA MISMATCH COMPARISION - ORIGINAL BACKUP.xlsx`:
> §12 comparison states reduced to exactly three (PENDING / NOT AVAILABLE / RESOLVED removed);
> §13 source priority replaced with the authoritative seven-source order;
> §11 output structure corrected against the real template.
>
> **Changes in 1.2** — final specification decisions: §12 case D (no source value → FINAL and STATUS
> left blank, not a fourth state); §13.2 GA as an optional dynamically included source; §13.3 dynamic
> source types; §8.2 semantic header discovery and the no-guessing rule; AC-16/AC-17; §19 all blockers
> closed.

## 1. Product Overview

CDC MTL Tool is an engineering data consolidation and comparison tool that processes a finalized set of allocated MTL tags against multiple source documents, creates a canonical dataset, compares defined attributes across those sources, enables human review of comparison results, and preserves each comparison milestone as historical evidence.

The primary workflow is:

**Finalized Tag Scope → Milestone → Source Upload → Extraction → Consolidation → Canonical Dataset → Comparison → Review → Final Output → History**

The two primary product pillars are **Consolidation** and **Comparison**.

## 2. Product Objective

Allow an engineering user who already has finalized MTL tags and source documents to consolidate the source information into the required format, compare defined attributes according to approved rules, review exceptions, generate the comparison output, and reopen the milestone later with its evidence.

## 3. Key Terminology

### Milestone
A finalized engineering business scope. Example: `MTL-2026-001` containing 717 finalized tags. A milestone is not a software-development phase.

### Run
One processing attempt/version against a milestone using a particular set of source documents and rules. Revised source documents create a new run rather than overwriting historical evidence.

### Finalized Tag Scope
The authoritative list of tags allocated to the milestone. It defines the canonical row universe.

### Source Document
Engineering input such as Data Sheet/MDS, Asset, SPIR/MIR, MXS, MOM/O&M, or MTC.

### Canonical Dataset
The normalized representation of every milestone tag and all available source information.

### Comparison Result
The result of evaluating source values for a defined attribute according to the approved comparison rules.

### Review
Human inspection and resolution of comparison results requiring confirmation.

## 4. Core Business Rules

### BR-01 — Finalized Scope Is Authoritative
If the milestone contains 717 tags, the canonical dataset contains 717 rows even if a source contains fewer records.

Example:

- Milestone: 717 tags
- Data Sheet: 436 tags
- Asset: 700 tags
- SPIR: 500 tags

The canonical dataset remains 717 rows.

Missing source records remain missing/blank. They must not cause milestone tags to be deleted.

### BR-02 — Source Documents Do Not Define Scope
Never infer the final tag universe from source documents.

### BR-03 — Consolidation and Comparison Are Separate
Consolidation answers: "What information does each source provide for each finalized tag?"

Comparison answers: "How do those values compare and what result follows from the approved rules?"

### BR-04 — Comparison Uses Canonical Data
The comparison engine operates on canonical structured data, not directly on arbitrary raw source files.

### BR-05 — Original Sources Are Immutable
Uploaded source documents must not be modified.

### BR-06 — Revised Sources Create New Runs
A revised/corrected source document creates a new run and does not overwrite earlier evidence.

### BR-07 — Traceability
Source-derived values must be traceable to their source document and, where practical, sheet/page/row/column or equivalent source location.

### BR-08 — Engineering Rules Are Authoritative
Detailed priority, lifecycle, attribute, exception, and final-value rules must come from the supplied authoritative priority/lifecycle document. Do not invent engineering rules.

### BR-09 — Deterministic First
The first release uses deterministic rules plus human review. AI may be considered later but must not make engineering-value decisions in V1.

## 5. Primary User

The primary user is an engineering team member who has finalized MTL scope and source documents and needs to consolidate and compare them.

Authentication is not required for V1.

## 6. End-to-End Workflow

```text
Finalized Tag Scope
        ↓
Create Milestone
        ↓
Upload Source Documents
        ↓
Extract / Normalize
        ↓
Consolidate
        ↓
Canonical Dataset
        ↓
Compare
        ↓
Review
        ↓
Final Comparison Output
        ↓
Milestone History
```

## 7. First Release Scope

The first usable product must support:

- Create a milestone.
- Define/import the finalized tag scope.
- Validate the finalized tag count.
- Upload multiple source documents.
- Identify/select source-document types.
- Extract source information.
- Normalize source information.
- Consolidate against the finalized tag scope.
- Generate a canonical dataset containing every milestone tag.
- Run comparison.
- Display comparison results.
- Enable human review.
- Generate/download the comparison workbook.
- Preserve milestone history.
- Reopen a milestone later.

## 8. Initial Source Types

- Data Sheet / MDS
- Asset
- SPIR / MIR
- MXS
- MOM / O&M
- MTC

Actual layouts must be learned from real supplied examples; the system must not assume identical structures.

## 8.1 Verified Source Inventory

Native source files currently supplied: **Data Sheet only**. The other six types are expected to carry
the same kind of values in the same worker-export shape and will be implemented on a shared tabular
adapter base, each verified against a real file before being enabled.

The `ORIGINAL BACKUP` workbook contains human-extracted values for all six workbook sources across all
five attributes, and therefore serves as the **validation oracle** for each adapter as its real file
arrives.

## 8.2 Field Discovery Requirements

Source layouts are similar but **not guaranteed identical**. The system must not depend on fixed column
positions — `MAKE` may be column J in one revision and column H in the next.

Extraction identifies fields by **header meaning**, using normalized comparison against a controlled,
documented alias table derived from the real files:

| Field | Accepted aliases (extended only from real files) |
|---|---|
| TAG NUMBER | `TAG NUMBER`, `TAG`, `TAG NO`, `TAG NUMBER AS PER DOC(UMENT)` |
| MAKE | `MAKE`, `MANUFACTURER`, `MFR`, `OEM` |
| MODEL | `MODEL`, `MODEL NO`, `MODEL NUMBER` |
| SERIAL NUMBER | `SERIAL`, `SERIAL NUMBER`, `SERIAL NO` |
| PART NUMBER | `PART`, `PART NUMBER`, `PART NO` |

Adapters must tolerate differing column order, additional columns, absent irrelevant columns, and minor
header/capitalization/spacing variation. Blind substring matching is not acceptable.

**Ambiguous or unidentifiable fields are never guessed.** The system flags the mapping as
ambiguous/unknown, names the affected source document, reports the headers it did find, and routes the
condition to a review/error state.

## 9. Current Data Sheet Reference

The existing Data Sheet prototype establishes:

```text
Sheet: DATASHEET
B: TAG NUMBER
G: TAG NUMBER AS PER DOC
J: MAKE
K: MODEL
L: SERIAL NUMBER
M: PART NUMBER
```

TAG NUMBER and TAG NUMBER AS PER DOC are distinct concepts. The milestone/finalized tag is the join key.

The current prototype demonstrated:

- Milestone scope: 717
- Data Sheet rows: 436
- Matched tags: 436
- Unmatched milestone tags: 281

Observed populated fields:

- MAKE: 124
- MODEL: 98
- SERIAL NUMBER: 0
- PART NUMBER: 0

These are fixture observations, not hard-coded constants.

## 10. Canonical Dataset

The canonical dataset must retain every finalized milestone tag and relevant common context.

The current comparison format establishes:

- TAG NUMBER
- TAG DISCRIPTION
- EQUIPMENT DESCRIPTION
- SIZE & RATING
- ASSET
- DATA SHEET
- SPIR
- MXS
- MOM
- MTC

Internal provenance must accompany source-derived values.

Missing source information remains missing. The system must not fabricate values.

## 11. Comparison Output

**Authoritative source: `5.MTL-DATA MISMATCH COMPARISION - ORIGINAL BACKUP.xlsx` (inspected).**

Six sheets: `SUMMERY`, `TAG NUMBER COMPARISION`, `MAKE COMPARISION`, `MODEL COMPARISION`,
`SERIAL NUMBER COMPARISION`, `PART NUMBER COMPARISION`.

Comparison-sheet layout:

```
A S.NO · B TAG NUMBER · C TAG DISCRIPTION · D EQUIPMENT DESCRIPTION · E SIZE & RATING
F..K  six source columns   (ASSET PHOTO, DATA SHEET (MDS), SPIR (MIR),
                            CROSS SECTION (MXS), O&M MANUAL (MOM), TEST CERTIFICATE (MTC))
L REMARKS · [M FINAL <attribute>] · [N STATUS]
```

The human original is not uniform (TAG and MAKE have a FINAL column; MODEL, SERIAL and PART do not).
**The target follows the mental-model reference `…- AUTOMATED.xlsx` instead: every comparison sheet
carries `REMARKS`, `FINAL <attribute>` and `STATUS`.** Only the *layout* of that file is authoritative —
its values, verdicts and remarks are not (see `docs/SPEC_VALIDATION_REPORT.md` §18.4).

Source columns F.. are generated **only for the source types uploaded for that run** (§13.2/§13.3),
ordered by authoritative priority, so the column count varies per run.

`SUMMERY` is A1:I14 — `SL NO · DESCRIPTION · ASSET QTY · MDS QTY · MIR QTY · MXS QTY · MOM QTY ·
MTC QTY · REMARKS`, rows 2–6 being the five attributes.

Formatting: scope headers A:E filled `#7030A0` bold; source/remarks/final headers `#FFFF00`;
`S.NO` is text (`'0001'`, zero-padded); data rows 2–718.

A 14th `STATUS` column carrying the comparison result is an approved addition.

**The workbook is generated, not cloned.** Sheets and source columns are created from the registered
attributes and the source types actually present, so a new source type or attribute extends the
workbook without a template edit.

Preserve the supplied business-facing terminology unless the specification documents a justified change.

## 12. Comparison States

Exactly three states. No others.

| # | Situation | Result |
|---|---|---|
| A | Two or more applicable sources agree | **MATCH** |
| B | Two or more applicable sources conflict | **MISMATCH** |
| C | Exactly one applicable source has a non-empty value, no other conflicts | **MATCH** |
| D | **No source has a value** | **FINAL and STATUS left blank** |
| E | Ambiguous naming / interpretation / unresolved comparison | **REVIEW REQUIRED** |

- **MATCH** — the applicable source values agree under the authoritative comparison rules; or exactly
  one applicable source holds a non-empty value and no other applicable source conflicts with it.
- **MISMATCH** — two or more applicable sources hold non-empty values that conflict.
- **REVIEW REQUIRED** — the result cannot be safely finalized by deterministic rules and needs human
  judgement (ambiguous values, conflicting duplicate source records, unresolved source interpretation,
  a lifecycle/priority exception, or any condition the authoritative rules flag for judgement).

**Blank is not a status.** Where no applicable source holds a value, there is no final value and no
comparison result to produce — both cells stay empty. This is case D, not a fourth state.

`PENDING`, `NOT AVAILABLE` and `RESOLVED` are **not** comparison states. Absence of source data is
represented in the canonical layer (§10) for coverage reporting, never as a comparison verdict.

Authoritative PDF exceptions take precedence wherever explicitly defined.

### 11.1 / 12.1 Single-source rule

If exactly one source holds a non-empty value for an attribute and no other applicable source holds a
conflicting value, the result is **MATCH**. Exceptions defined by the authoritative PDF take precedence.

## 13. Source Priority and Lifecycle

**Authoritative source: `MTL Attribute Values Population.pdf` (read).**

Seven sources, consulted in strict priority order. Step 1 populates attribute values; steps 2–7
populate only values still *missing*:

| Rank | Source | Code |
|---|---|---|
| 1 | Photography Name Plate | ASSET |
| 2 | Data Sheet | MDS |
| 3 | SPIR Sheet | SPIR / MIR |
| 4 | **GA Document** | **GA** |
| 5 | Cross Section DWG | MXS |
| 6 | Test Certificate | MTC |
| 7 | O&M Manuals | MOM |

- **RULE-P1 (population)** — FINAL = the value from the highest-ranked source holding a non-empty value.
- **RULE-P2 (lifecycle)** — where several candidate documents exist among ranks 2–7, use the
  **latest-dated document**.
- **RULE-P3 (mismatch)** — where a source's value disagrees with the other sources' values, the
  disagreement is raised.

Note: the workbook's column order is **not** the priority order (MOM precedes MTC in the columns but
ranks below it). Priority must never be inferred from column position.

### 13.2 GA Document — optional, dynamically included

GA is a supported source type at priority 4. No real GA sample exists yet, so **no GA-specific adapter
or layout may be assumed or invented**. The architecture supports GA from the outset:

- GA is **optional**. If no GA document is uploaded for a run, GA is not a source for that run and
  **no empty GA column is produced**.
- If a GA document **is** uploaded, GA is treated as a real source, participates in consolidation and
  comparison at priority 4, and a GA column appears on every attribute sheet in priority position.

Example — without GA:

```
MAKE:  ASSET · DATA SHEET · SPIR · MXS · MTC · MOM · FINAL
```

with GA uploaded:

```
MAKE:  ASSET · DATA SHEET · SPIR · GA · MXS · MTC · MOM · FINAL
```

The same applies to TAG NUMBER, MODEL, SERIAL NUMBER, PART NUMBER and any future attribute.

### 13.3 Source types are dynamic

The comparison engine must not hard-code a fixed set of source columns. Source types are determined per
run by the documents actually uploaded, and future source types must be addable without rewriting the
comparison engine. No run requires every possible source to exist.

Documented divergences from the PDF, all deliberate: `Create Punch List` is not implemented as a punch
list (out of scope) and is mapped to comparison state + remarks + review queue; `Raise Request to
CDC-ONSITE` is an operational action outside the tool; `Data Quality Check` is realised as the review
stage plus output validation.

## 14. Human Review

The reviewer should see:

- tag;
- attribute;
- all available source values;
- comparison state;
- remarks;
- final value;
- source traceability.

Review decisions must be persisted and must not modify original source records.

## 15. Historical Evidence

A milestone must preserve:

- milestone metadata;
- finalized tag scope;
- source documents;
- source metadata;
- source hashes;
- processing runs;
- canonical dataset;
- comparison results;
- review decisions;
- generated outputs.

Source metadata should include original filename, source type, file size, upload timestamp, SHA-256 hash, processing status, row count where applicable, recognized tag count, and matched/unmatched tag information where applicable.

## 16. UI

The product should prioritize workflow efficiency over dashboard complexity.

Minimum screens:

- Home / History
- Create Milestone
- Milestone Workspace
- Sources
- Consolidation
- Comparison
- Review
- Results

Suggested milestone workspace navigation:

```text
SCOPE | SOURCES | CONSOLIDATION | COMPARISON | REVIEW | RESULTS
```

## 17. Explicit V1 Out of Scope

- Vendor Punch List
- Authentication
- Cloud hosting
- Complex RBAC
- Multi-user cloud collaboration
- External database infrastructure
- ERP integration
- Email workflow
- Mobile application
- AI-based engineering decisions
- Automatic engineering-value guessing
- Unrelated analytics/dashboard features

## 18. Acceptance Criteria

### AC-01 — Milestone Scope
A milestone can be created with a finalized tag scope.

### AC-02 — Scope Authority
A 717-tag milestone produces exactly 717 canonical tag rows regardless of source coverage.

### AC-03 — Data Sheet Case
The representative case retains:

- 717 milestone tags
- 436 Data Sheet rows
- 436 matched tags
- 281 milestone tags without Data Sheet records

### AC-04 — Missing Values
Missing source values remain missing.

### AC-05 — Multi-Source Consolidation
Multiple sources can contribute to the same canonical tag.

### AC-06 — Comparison
Comparison operates on canonical data.

### AC-07 — Rules
Comparison/final-value selection follows the authoritative priority/lifecycle document.

### AC-08 — Review
Review-required results can be inspected and resolved.

### AC-09 — Output
The required comparison workbook can be generated.

### AC-10 — History
A milestone can be reopened with its source, run, comparison, review, and output history intact.

### AC-11 — Source Integrity
Original source files are not modified.

### AC-12 — Reproducibility
A run is identifiable by its scope, source files, rule/version information, and processing metadata.

### AC-13 — Three-State Results
Every comparison result is exactly one of MATCH, MISMATCH, REVIEW REQUIRED — or blank where no
applicable source holds a value. No other state string is ever written.

### AC-16 — Dynamic Source Columns
A run produces source columns only for the source types actually uploaded. Uploading a GA document adds
a GA column at priority position 4 on every attribute sheet; not uploading one produces no GA column
anywhere.

### AC-17 — No Positional Column Assumptions
Extraction resolves fields by header meaning. A source file carrying the same fields in a different
column order extracts identically. A field that cannot be confidently identified is reported with the
affected document and the headers found — never guessed.

### AC-14 — No Verdict Without Evidence
No comparison verdict is emitted that contradicts the underlying canonical data. Specifically, a row
whose source values are all empty must never be reported as agreeing or disagreeing sources.

### AC-15 — Priority Compliance
Auto-elected FINAL values follow the authoritative priority order (§13, RULE-P1). Validated against the
human ground truth in `ORIGINAL BACKUP`: the rule reproduces 29 of the 34 human FINAL MAKE values;
the 5 exceptions are manufacturer naming-variant judgements and must route to REVIEW REQUIRED.

## 19. Open Blockers

**None.** Q1–Q4 were resolved on 2026-09-24:

- **Q1 — resolved.** No source value → FINAL and STATUS left blank (§12 case D). Not a fourth state.
- **Q2 — resolved.** Ambiguous naming/interpretation → **REVIEW REQUIRED** (§12 case E). No equality
  rule is invented for manufacturer naming variants.
- **Q3 — resolved.** GA is an optional, dynamically included source at priority 4 (§13.2).
- **Q4 — resolved in approach.** All source documents arrive in the same worker-export shape as the
  supplied Data Sheet. Adapters are built on a shared tabular base with semantic header discovery
  (§8.2) and each is verified against its real file before being enabled.

Minor confirmations still outstanding are listed in `docs/SPEC_VALIDATION_REPORT.md` §21; none block
implementation.

