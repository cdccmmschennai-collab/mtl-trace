# MTL Trace

Local engineering data consolidation and comparison for a finalized MTL milestone.

Engineering finalizes a milestone tag scope (for example 717 plant tags). Engineers then spend a lot of time
searching those tags across the project's source documents: Asset Photo, Data Sheet (MDS), SPIR/MIR, GA,
Cross Section (MXS), Test Certificate (MTC), O&M Manual (MOM). MTL Trace does that work instead:

```
Load finalized tag scope (validated, then locked for the session)
→ Upload source documents → Identify / validate / extract
→ CONSOLIDATE → canonical dataset
→ COMPARE → FINAL value + MATCH / MISMATCH / REVIEW REQUIRED
→ Comparison workbook (Excel) for engineering review
```

It runs entirely on the local machine: no cloud and no authentication. It is delivered as a standalone
Windows desktop tool (`CDC MTL Tool.exe`): double-click it and the tool opens in its own window.

**One session, no history.** The tool works on one scope and one set of documents at a time. Adding or
removing a document clears the consolidation and comparison, so you run them again on the new set. Loading a
new scope replaces everything, and every launch starts empty. Save the comparison workbook you need before you
close the tool.

## Core rules

- **The milestone scope is authoritative.** The comparison has exactly one row per scope tag. Source documents
  never add rows; tags found only in a source are reported as out of scope.
- **Source priority** (from `MTL Attribute Values Population.pdf`):
  1 Asset Photo · 2 Data Sheet (MDS) · 3 SPIR/MIR · 4 GA · 5 Cross Section (MXS) · 6 Test Certificate (MTC) ·
  7 O&M Manual (MOM). FINAL is taken from the highest-priority source holding a value.
- **Exactly three statuses:** `MATCH`, `MISMATCH`, `REVIEW REQUIRED`. When no source holds a value, FINAL and
  STATUS stay **blank**; blank is not a status.
- **TAG NUMBER** is compared against the milestone tag, and FINAL TAG is always the milestone tag. Sources that
  disagree with each other give `MISMATCH`. Sources that agree with each other but differ from the milestone tag
  give `REVIEW REQUIRED`.
- **MAKE** naming variants (short/full/legal form, punctuation, a truncated word) are `REVIEW REQUIRED` with a
  blank FINAL. Genuine conflicts stay `MISMATCH`. The rule is deterministic and whole-word, with no fuzzy
  matching (`backend/comparison/names.py`).
- **Source types are dynamic.** Only the document types uploaded for a run appear as source columns. Fields are
  discovered by header meaning, never by fixed Excel column position.
- Comparison rules are versioned data in `rules/v1.yaml`, and the rules version is stamped on every run.

Full specification: `docs/PRD.md`, `docs/TRD.md`, `docs/SPEC_VALIDATION_REPORT.md`; project instructions in
`CLAUDE.md`.

## Architecture

```
React + TypeScript + Vite (frontend/)  →  FastAPI on localhost (backend/api)
    →  services  →  extraction · consolidation · comparison · output
    →  SQLite + local file store (MTL_DATA/)
```

| Path | Contents |
|---|---|
| `backend/api/` | HTTP routes (the only layer that imports FastAPI) |
| `backend/services/` | Session (one scope + one run), milestone, run, consolidation and comparison workflows |
| `backend/extraction/` | Source-document adapters (scope, Data Sheet, SPIR) and semantic header discovery |
| `backend/consolidation/` | Canonical dataset: milestone tag × attribute × source, stored long |
| `backend/comparison/` | Comparison engine; reads canonical data only, never source files |
| `backend/output/` | Comparison / consolidated workbook generation |
| `backend/storage/` | SQLite models and the local file store |
| `rules/` | Versioned comparison rules |
| `frontend/src/` | UI, one page: Scope → Sources → Consolidate → Compare → Excel |
| `desktop.py`, `packaging/`, `build_exe.ps1` | Desktop launcher (pywebview window) and the PyInstaller build |
| `tests/` | Unit, integration, real-data regression and architecture-boundary tests |
| `docs/` | PRD, TRD, specification validation, consolidation and adapter notes |

## Setup

Developed and tested with Python 3.14 and Node.js 24.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip install -r requirements.txt

cd frontend && npm install
```

## Desktop tool

Build the standalone executable (needs the venv and Node.js, see Setup):

```powershell
.\build_exe.ps1                 # → dist\CDC MTL Tool.exe
```

Copy `dist\CDC MTL Tool.exe` to any Windows 10/11 PC and double-click it. Python and Node are not needed there.
The window uses Microsoft Edge WebView2, which is part of Windows 10/11. The tool starts its engine on a free
local port (127.0.0.1 only), and closing the window stops it. Working data lives in
`%LOCALAPPDATA%\CDC MTL Tool\` and is cleared at every launch. "Download" opens a Windows *Save as* dialog.

From a checkout you can also run the same window without building: `npm --prefix frontend run build`, then
`.venv\Scripts\python desktop.py`.

## Running (development)

Backend (port 8300):

```bash
.venv/bin/python -m uvicorn backend.main:create_app --factory --port 8300
```

Frontend (port 3300; proxies `/api` to 8300):

```bash
cd frontend && npm run dev
```

Open http://localhost:3300.

Runtime data (SQLite database, uploaded documents, generated workbooks, logs) is written to `MTL_DATA/` in the
repository root, or to the directory named by the `MTL_DATA_DIR` environment variable. It is never committed.

## Tests

```bash
.venv/bin/python -m pytest                 # backend
cd frontend && npm run typecheck           # frontend
```

The real-data regression tests use the project's Data Sheet and SPIR documents. Those are company working files
and are **not** in this repository. Place them locally at:

```
input/sources/datasheet/0904_4391-DATA SHEET PRIORITY-2_COMPLETED.xlsx
input/sources/spir/4391-SPIR DATA PRIORITY-2_COMPLETED.xlsx
```

When they are absent, those tests are skipped rather than failed.

## Repository contents and data policy

Reference material required to understand and verify the application. Only the PDF is committed; the Excel
workbooks are kept local (see `.gitignore`) and must be placed in the paths below:

| File | Role |
|---|---|
| `MTL Attribute Values Population.pdf` | Authority for source priority and final-value selection |
| `input/references/5.MTL-DATA MISMATCH COMPARISION.xlsx` | The milestone tag scope and working file |
| `5.MTL-DATA MISMATCH COMPARISION - ORIGINAL BACKUP.xlsx` | Human ground truth and output structure |
| `5.MTL-DATA MISMATCH COMPARISION - AUTOMATED.xlsx` | Output **layout** reference only; its data is not authoritative |

Kept local only, see `.gitignore`: every Excel workbook, the `input/` folder, generated output (`output/`),
runtime data (`MTL_DATA/`), virtual environments, `node_modules`, build output, caches, logs and `.env` files.

The earlier prototype `mtl_phase1.py` has been retired; it remains in git history.
