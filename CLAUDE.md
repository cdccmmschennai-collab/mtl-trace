# CDC MTL TOOL — Project Instructions

**Specification status:** validated 2026-09-24 against the actual repository files.
Read `docs/SPEC_VALIDATION_REPORT.md`, `docs/PRD.md` and `docs/TRD.md` before implementing anything.

## Purpose

CDC MTL Tool is a local engineering data consolidation and comparison application.

It processes a finalized MTL tag scope (milestone) against multiple engineering source documents,
creates a canonical dataset, compares defined attributes under the authoritative priority/lifecycle
rules, supports human review, produces the final comparison workbook, and preserves milestone history.

## Core Workflow

```
Finalized Tag Scope → Create Milestone → Import Finalized Tags → Lock Scope
→ Upload Sources → Identify / Validate → Extract → Normalize
→ CONSOLIDATE → Canonical Dataset → COMPARE → MATCH / MISMATCH / REVIEW REQUIRED
→ Human Review → Final Output → Save Run / History
```

Two pillars: **Consolidation** and **Comparison**. Review is part of the comparison workflow.

## Critical Business Rule

The finalized milestone tag scope is authoritative.

Source documents never define the final row universe. If the milestone contains 717 tags, the canonical
dataset contains 717 tags even when individual sources contain fewer. Tags found in a source but outside
the milestone never expand the scope; they are reported as unmatched/out-of-scope.

Enforce this structurally: the consolidation loop's outer iteration is always the milestone scope.

## Authoritative Files

| File | Authority for |
|---|---|
| `MTL Attribute Values Population.pdf` | source priority, lifecycle, final-value selection |
| `5.MTL-DATA MISMATCH COMPARISION - ORIGINAL BACKUP.xlsx` | output structure; human ground truth for all six sources |
| `5.MTL-DATA MISMATCH COMPARISION - AUTOMATED.xlsx` | **final output mental model — LAYOUT ONLY** |
| `input/references/5.MTL-DATA MISMATCH COMPARISION.xlsx` | the milestone tag scope (717 tags); the **working file** the system populates |
| `input/sources/datasheet/0904_4391-…_COMPLETED.xlsx` | representative source-document shape (all source types arrive like this) |

**Split authority on `AUTOMATED.xlsx`.** Its **layout** is the target mental model: five comparison
sheets, source columns, `REMARKS`, `FINAL <attribute>` and `STATUS` on every sheet. Its **data is not
authoritative** — it destroyed 123 real MOM values, bulk-generated remarks the human never wrote, and
uses banned states. Take structure from it; never take values, verdicts or rules from it.

`output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx` is defective in both respects — it emits verdicts for
rows with no source data. Ignore entirely. See `docs/SPEC_VALIDATION_REPORT.md` §18.4.

## Working File Model

The tag-scope workbook (`5.MTL-DATA MISMATCH COMPARISION.xlsx`) is the **working file**. It arrives
carrying only the finalized scope (`S.NO · TAG NUMBER · TAG DISCRIPTION · EQUIPMENT DESCRIPTION ·
SIZE & RATING`). The system **creates the comparison sheets and populates the source columns
automatically** from the uploaded source documents, producing a workbook shaped like `AUTOMATED.xlsx`.

## Source Priority (from the PDF — do not reorder)

1. Photography Name Plate (ASSET) · 2. Data Sheet (MDS) · 3. SPIR Sheet (SPIR/MIR) ·
4. **GA Document** · 5. Cross Section DWG (MXS) · 6. Test Certificate (MTC) · 7. O&M Manuals (MOM)

- **RULE-P1** — FINAL = value from the highest-ranked source holding a non-empty value.
- **RULE-P2** — among several candidate documents of ranks 2–7, use the latest-dated document.
- **RULE-P3** — where a source disagrees with the others, raise the disagreement.

The workbook's column order is **not** the priority order. Never infer priority from column position.

### GA Document — optional, dynamic

GA is a supported source type at priority 4, but **no real GA sample exists yet**. Do not invent a
GA-specific adapter or assume its layout.

- GA is **optional**. If no GA document is uploaded for a run, GA is simply not a source for that run —
  **do not emit an empty GA column**.
- If a GA document **is** uploaded, GA participates fully in consolidation and comparison at priority 4,
  and a GA column appears on every attribute sheet, positioned per the authoritative order.

## Source Types Are Dynamic

The comparison engine must **never hard-code a fixed set of source columns**. Source types are
determined per run by the documents actually uploaded. Adding a future source type must not require
changing the comparison engine.

## Comparison States — exactly three

**MATCH** · **MISMATCH** · **REVIEW REQUIRED**

| Situation | Result |
|---|---|
| Two or more applicable sources agree | **MATCH** |
| Two or more applicable sources conflict | **MISMATCH** |
| Exactly one applicable source has a value, nothing conflicting | **MATCH** |
| Ambiguous naming / interpretation / unresolved comparison | **REVIEW REQUIRED** |
| **No source has a value** | **leave FINAL and STATUS blank** |

**Blank is not a status.** It means no applicable source value exists, so no final value or comparison
result can be produced. `PENDING`, `NOT AVAILABLE` and `RESOLVED` are **not** comparison states.

Absence still lives in the canonical layer (`ABSENT_TAG` / `ABSENT_VALUE`) for coverage reporting — it
is simply never rendered as a verdict.

## Comparison Attributes

`TAG NUMBER` · `MAKE` · `MODEL` · `SERIAL NUMBER` · `PART NUMBER`

TAG NUMBER is special: it is compared against the milestone tag, and `FINAL TAG = the milestone tag`.
The other four are compared among sources only.

## Output

Six sheets: `SUMMERY`, `TAG NUMBER COMPARISION`, `MAKE COMPARISION`, `MODEL COMPARISION`,
`SERIAL NUMBER COMPARISION`, `PART NUMBER COMPARISION`.

**The workbook is generated, not cloned.** Sheets are created per attribute; source columns are created
**only for the source types actually uploaded for that run**, ordered by authoritative priority. A new
document type extends the workbook without a template edit and without an engine change.

Every comparison sheet carries `REMARKS`, `FINAL <attribute>` and `STATUS`, per the mental-model
reference. Header convention: `{ATTRIBUTE LABEL} IN {SOURCE LABEL}`.

Match the reference formatting: purple `#7030A0` A:E headers, yellow `#FFFF00` source headers,
`S.NO` written as text.

## Architecture

React + TypeScript + Vite → FastAPI (localhost) → processing engine → SQLite + local filesystem.
Packaged eventually as a local executable. No cloud, no authentication for V1.

Boundaries, enforced by imports:
- `comparison` never imports `extraction` — it reads canonical data only
- nothing below `api` imports FastAPI
- only `extraction/` and `output/` import openpyxl
- the processing engine runs headlessly, independent of the UI
- no Excel parsing or engineering logic in React

Canonical data is stored **long** (tag × attribute × source), pivoted to wide only by the output writer.
Comparison rules are **versioned data** (`rules/v1.yaml`), not code; `rules_version` is stamped on every run.

## Engineering Principles

- Investigate the supplied reference files before implementing. Never guess a source structure when the
  real document is available.
- **Never rely on fixed Excel column positions.** Source revisions move columns — `MAKE` may be column J
  in one file and column H in the next. Verified positions belong in tests as fixture assertions, never
  as constants in an adapter.
- **Discover fields semantically**, by normalized header meaning against a controlled alias table
  (`TAG NUMBER` / `TAG` / `TAG NO` / `TAG NUMBER AS PER DOCUMENT`; `MAKE` / `MANUFACTURER` / `MFR` /
  `OEM`; `MODEL` / `MODEL NO` / `MODEL NUMBER`; `SERIAL` / `SERIAL NUMBER` / `SERIAL NO`; `PART` /
  `PART NUMBER` / `PART NO`). Aliases are derived from real files and documented — never blind
  substring matching.
- Adapters must tolerate differing column order, extra columns, absent irrelevant columns, and minor
  header/case/spacing variation.
- **If a required field cannot be confidently identified, do not guess.** Flag the mapping as
  ambiguous/unknown, name the affected document, report every header found, and route to a review/error
  state. Never silently map a wrong column because it sits in a familiar position.
- Never invent engineering rules. Where the PDF is silent, route to REVIEW REQUIRED and ask.
- No last-write-wins on duplicate or conflicting source records — surface them for review.
- Preserve provenance: document, hash, sheet, row, column, and document/page reference where available.
- Source files and locked scope are immutable. A revised source creates a **new run**, never an overwrite.
- Missing values stay missing. Never fabricate.
- Deterministic rules first; AI makes no engineering decisions in V1.

## Phase Discipline

Implement only the currently requested phase. Do not add authentication, vendor punch lists, AI decision
making, cloud deployment, or unrelated features. Avoid over-engineering.

Phase 1 is the full end-to-end slice **through the UI** — create milestone → lock scope → upload →
extract → consolidate → compare → review → generate workbook → history. Do not push core functionality
into a later phase to make Phase 1 smaller.

## Existing Prototype

`mtl_phase1.py` has been retired and removed from the working tree (it remains in git history). It did not
run against the current inputs and cloned a template rather than generating one.

Ideas worth carrying forward: the TAG NUMBER vs TAG NUMBER AS PER DOC distinction, refusing to guess on
duplicates, validating output before saving, and never mutating inputs.

## Verification

Every phase requires unit tests, integration tests, representative real-file validation, output
validation and regression checks. Do not weaken tests to make an implementation pass.

Golden regression fixture (all figures verified):

```
scope 717 · DS rows 436 · DS keys in scope 436 · outside 0 · scope tags with no DS row 281
TAG from MDS 357 (343 equal key, 14 differ) · MAKE 124 · MODEL 98 · SERIAL 0 · PART 0
canonical cells 21,510 · MDS columns must equal ORIGINAL BACKUP exactly
```

Mandatory guard: **no comparison verdict for a row whose source values are all empty** — FINAL and
STATUS both stay blank. Both prior automation attempts in this repository violated exactly that.

Assert derived relationships, not hard-coded constants — 717 is a regression case, not a system limit.

## Open Blockers

**None.** Q1–Q4 were resolved on 2026-09-24; see `docs/SPEC_VALIDATION_REPORT.md` §21 for the decision
log and the minor confirmations still outstanding (none of which block implementation).
