"""
mtl_phase1.py

MTL Comparison Automation — Phase 1 Demo (Data Sheet population only).

Reads:
  - a reference/template comparison workbook (structure + formatting + the
    user-provided submission scope already in columns A-E)
  - a Data Sheet source workbook (raw worker export)

Writes a NEW workbook, structurally based on the reference, where:
  - every comparison sheet has the full 13-column A:M structure (FINAL
    column is added/configured wherever the reference doesn't already
    have it, using the existing FINAL column's formatting as the donor)
  - ONLY the DATA SHEET source column is populated
  - ASSET / SPIR / MXS / MOM / MTC / REMARKS / FINAL stay blank
  - no comparison logic (MATCH/MISMATCH/REVIEW/PRIORITY/FINAL selection)
    is computed -- that is a later phase

Never modifies either input file on disk.

Usage:
    python mtl_phase1.py \
        --reference "input/5.MTL-DATA MISMATCH COMPARISION.xlsx" \
        --datasheet "input/0904_4391-DATA SHEET PRIORITY-2_COMPLETED.xlsx" \
        --output "output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx"
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import copy
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook.workbook import Workbook


# ============================================================
# CONSTANTS -- sheet names, column positions, headers
# ============================================================

SHEET_SUMMARY = 'SUMMERY'
COMPARISON_SHEETS_IN_ORDER = [
    SHEET_SUMMARY,
    'TAG NUMBER COMPARISION',
    'MAKE COMPARISION',
    'MODEL COMPARISION',
    'SERIAL NUMBER COMPARISION',
    'PART NUMBER COMPARISION',
]
# The five sheets that carry the A:M source/comparison structure
# (SUMMERY is excluded -- it has its own, different layout).
FIELD_SHEETS_IN_ORDER = COMPARISON_SHEETS_IN_ORDER[1:]

# Data Sheet source workbook layout (verified against the real file).
DATASHEET_TAB_NAME = 'DATASHEET'
DS_COL_TAG_KEY = 2           # B: TAG NUMBER (submission cross-reference / join key)
DS_COL_TAG_AS_PER_DOC = 7    # G: " TAG NUMBER AS PER DOC" (the actual document value)
DS_COL_MAKE = 10             # J: MAKE
DS_COL_MODEL = 11            # K: MODEL
DS_COL_SERIAL = 12           # L: SERIAL NUMBER
DS_COL_PART = 13             # M: PART NUMBER

# Loose header-text checks used only to validate we were handed the right
# kind of file (not to re-derive column positions -- those are fixed above
# because they were verified against the real source file).
DS_EXPECTED_HEADERS = {
    DS_COL_TAG_KEY: 'TAG NUMBER',
    DS_COL_TAG_AS_PER_DOC: 'TAG NUMBER AS PER DOC',
    DS_COL_MAKE: 'MAKE',
    DS_COL_MODEL: 'MODEL',
    DS_COL_SERIAL: 'SERIAL NUMBER',
    DS_COL_PART: 'PART NUMBER',
}

# Which Data Sheet field feeds which comparison sheet's DATA SHEET column.
SHEET_FIELD_MAP = {
    'TAG NUMBER COMPARISION': 'tag_as_per_doc',
    'MAKE COMPARISION': 'make',
    'MODEL COMPARISION': 'model',
    'SERIAL NUMBER COMPARISION': 'serial',
    'PART NUMBER COMPARISION': 'part',
}

# Comparison-sheet A:M column layout (identical across all five field sheets).
COL_SNO = 1                  # A
COL_SUBMISSION_TAG = 2       # B  (submission TAG NUMBER -- user-owned, never written here)
COL_TAG_DESCRIPTION = 3      # C
COL_EQUIPMENT_DESCRIPTION = 4  # D
COL_SIZE_RATING = 5          # E
COL_ASSET = 6                # F
COL_DATASHEET_RESULT = 7     # G  <- this phase writes here
COL_SPIR = 8                 # H
COL_MXS = 9                  # I
COL_MOM = 10                 # J
COL_MTC = 11                 # K
COL_REMARKS = 12             # L
COL_FINAL = 13               # M  <- structural only in this phase; stays blank

SUBMISSION_COLUMNS = [COL_SNO, COL_SUBMISSION_TAG, COL_TAG_DESCRIPTION,
                      COL_EQUIPMENT_DESCRIPTION, COL_SIZE_RATING]
SOURCE_AND_DERIVED_COLUMNS = [COL_ASSET, COL_DATASHEET_RESULT, COL_SPIR, COL_MXS,
                              COL_MOM, COL_MTC, COL_REMARKS, COL_FINAL]

EXPECTED_HEADER_TEXT = {
    COL_SNO: 'S.NO',
    COL_SUBMISSION_TAG: 'TAG NUMBER',
    COL_ASSET: 'ASSET',
    # Header wording for this column varies per sheet ("...DATA SHEET (MDS)"
    # vs, on the MODEL sheet specifically, just "...IN (MDS)") -- 'MDS' is
    # the substring common to all five sheets' real headers.
    COL_DATASHEET_RESULT: 'MDS',
    COL_SPIR: 'SPIR',
    COL_MXS: 'MXS',
    COL_MOM: 'MOM',
    COL_MTC: 'MTC',
    COL_REMARKS: 'REMARKS',
}

# Header text required in the (possibly newly created) FINAL column, per sheet.
FINAL_HEADER_BY_SHEET = {
    'TAG NUMBER COMPARISION': 'FINAL TAG',
    'MAKE COMPARISION': 'FINAL MAKE',
    'MODEL COMPARISION': 'FINAL MODEL',
    'SERIAL NUMBER COMPARISION': 'FINAL SERIAL NUMBER',
    'PART NUMBER COMPARISION': 'FINAL PART NUMBER',
}

# A sheet in the reference workbook that is already known to have a
# correctly formatted FINAL column, used as the style donor for sheets
# that don't have one yet.
FINAL_STYLE_DONOR_SHEET = 'TAG NUMBER COMPARISION'


# ============================================================
# ERRORS
# ============================================================

class Phase1ValidationError(Exception):
    """Raised when input or output validation fails."""


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs(reference_path: Path, datasheet_path: Path) -> None:
    """Fail fast, with a clear message, before any processing happens."""
    if not reference_path.exists():
        raise Phase1ValidationError(f"Reference workbook not found: {reference_path}")
    if not datasheet_path.exists():
        raise Phase1ValidationError(f"Data Sheet workbook not found: {datasheet_path}")

    ref_wb = openpyxl.load_workbook(reference_path, read_only=True)
    missing_sheets = [s for s in COMPARISON_SHEETS_IN_ORDER if s not in ref_wb.sheetnames]
    if missing_sheets:
        raise Phase1ValidationError(
            f"Reference workbook is missing required sheet(s): {missing_sheets}. "
            f"Found: {ref_wb.sheetnames}"
        )
    ref_wb.close()

    ds_wb = openpyxl.load_workbook(datasheet_path, read_only=True)
    if DATASHEET_TAB_NAME not in ds_wb.sheetnames:
        raise Phase1ValidationError(
            f"Data Sheet workbook has no '{DATASHEET_TAB_NAME}' tab. "
            f"Found: {ds_wb.sheetnames}"
        )
    ds_ws = ds_wb[DATASHEET_TAB_NAME]
    header_row = next(ds_ws.iter_rows(min_row=1, max_row=1, values_only=True))
    problems = []
    for col_idx, expected_text in DS_EXPECTED_HEADERS.items():
        actual = header_row[col_idx - 1] if col_idx - 1 < len(header_row) else None
        actual_clean = (str(actual).strip().upper() if actual is not None else '')
        if expected_text.upper() not in actual_clean:
            problems.append(
                f"column {col_idx} expected header containing '{expected_text}', "
                f"found {actual!r}"
            )
    if problems:
        raise Phase1ValidationError(
            "Data Sheet workbook does not match the expected layout:\n  " +
            "\n  ".join(problems)
        )
    ds_wb.close()


# ============================================================
# DATA SHEET LOADING
# ============================================================

def normalize_key(value) -> Optional[str]:
    """Join-key normalization only -- never used for display."""
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if text else None


def load_datasheet_records(datasheet_path: Path) -> list[dict]:
    """Read every non-blank row of the DATASHEET tab into a plain list of
    dicts, in file order. No deduplication happens here."""
    wb = openpyxl.load_workbook(datasheet_path, data_only=True, read_only=True)
    ws = wb[DATASHEET_TAB_NAME]

    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None for v in row):
            continue
        raw_key = row[DS_COL_TAG_KEY - 1] if len(row) >= DS_COL_TAG_KEY else None
        records.append({
            'raw_key': raw_key,
            'normalized_key': normalize_key(raw_key),
            'tag_as_per_doc': row[DS_COL_TAG_AS_PER_DOC - 1] if len(row) >= DS_COL_TAG_AS_PER_DOC else None,
            'make': row[DS_COL_MAKE - 1] if len(row) >= DS_COL_MAKE else None,
            'model': row[DS_COL_MODEL - 1] if len(row) >= DS_COL_MODEL else None,
            'serial': row[DS_COL_SERIAL - 1] if len(row) >= DS_COL_SERIAL else None,
            'part': row[DS_COL_PART - 1] if len(row) >= DS_COL_PART else None,
        })
    wb.close()
    return records


def find_duplicate_keys(records: list[dict]) -> dict[str, int]:
    """Return {normalized_key: occurrence_count} for keys seen more than once."""
    counts: dict[str, int] = {}
    for rec in records:
        key = rec['normalized_key']
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return {k: v for k, v in counts.items() if v > 1}


def build_datasheet_lookup(records: list[dict], allow_duplicate_keys: bool = False) -> dict[str, dict]:
    """Build {normalized_tag: record}. Raises Phase1ValidationError if
    duplicate keys exist and allow_duplicate_keys is False (the default and
    recommended setting -- duplicates should be looked at, not silently
    resolved). If explicitly allowed, the LAST matching row wins, which is
    reported by the caller."""
    duplicates = find_duplicate_keys(records)
    if duplicates and not allow_duplicate_keys:
        raise Phase1ValidationError(
            "Duplicate TAG NUMBER keys found in the Data Sheet -- refusing to "
            "guess which row is correct. Re-run with allow_duplicate_keys=True "
            "(or --allow-duplicate-keys on the CLI) to proceed using the LAST "
            f"occurrence of each duplicate. Duplicate keys: {sorted(duplicates)}"
        )
    lookup: dict[str, dict] = {}
    for rec in records:
        key = rec['normalized_key']
        if key is None:
            continue
        lookup[key] = rec  # last occurrence wins when duplicates are allowed
    return lookup, duplicates


# ============================================================
# TEMPLATE PREPARATION -- ensure the full 13-column A:M structure
# ============================================================

def _copy_cell_style(src_cell, dst_cell) -> None:
    dst_cell.font = copy(src_cell.font)
    dst_cell.fill = copy(src_cell.fill)
    dst_cell.border = copy(src_cell.border)
    dst_cell.alignment = copy(src_cell.alignment)
    dst_cell.number_format = src_cell.number_format


def ensure_final_column(wb: Workbook, sheet_name: str) -> None:
    """Guarantee column M exists, is headered correctly, and is styled to
    match the workbook's existing FINAL column convention. If the sheet
    already has a correctly-headed FINAL column, this is a no-op on styling
    (we don't want to disturb an already-correct column) but the header
    text is still verified/corrected if it's missing or wrong."""
    ws = wb[sheet_name]
    header_cell = ws.cell(row=1, column=COL_FINAL)
    expected_header = FINAL_HEADER_BY_SHEET[sheet_name]

    already_present = header_cell.value == expected_header
    if already_present:
        return  # sheet already has the correct FINAL column (TAG / MAKE)

    donor_ws = wb[FINAL_STYLE_DONOR_SHEET]
    donor_header_cell = donor_ws.cell(row=1, column=COL_FINAL)

    header_cell.value = expected_header
    _copy_cell_style(donor_header_cell, header_cell)

    donor_width = donor_ws.column_dimensions['M'].width
    ws.column_dimensions['M'].width = donor_width

    # Match the donor's data-row style for column M so newly-created FINAL
    # cells look identical to the ones on sheets that already had them.
    donor_data_cell = donor_ws.cell(row=2, column=COL_FINAL)
    for row in range(2, ws.max_row + 1):
        cell = ws.cell(row=row, column=COL_FINAL)
        _copy_cell_style(donor_data_cell, cell)
        cell.value = None  # structural only -- must stay blank in this phase


def prepare_template(reference_path: Path) -> Workbook:
    """Load the reference workbook and make sure every field sheet has the
    full A:M structure, without disturbing anything else."""
    wb = openpyxl.load_workbook(reference_path, data_only=False)
    for sheet_name in FIELD_SHEETS_IN_ORDER:
        ensure_final_column(wb, sheet_name)
    return wb


# ============================================================
# ROW PROCESSING
# ============================================================

def clear_source_and_derived_cells(ws: Worksheet) -> None:
    """Blank ASSET/DATA SHEET/SPIR/MXS/MOM/MTC/REMARKS/FINAL for every data
    row, without touching cell styles (fills/borders/fonts/widths stay
    exactly as in the reference). Submission columns A-E are never touched."""
    for row in range(2, ws.max_row + 1):
        for col in SOURCE_AND_DERIVED_COLUMNS:
            cell = ws.cell(row=row, column=col)
            if cell.value is not None:
                cell.value = None


def populate_datasheet_column(ws: Worksheet, field_key: str, lookup: dict[str, dict]) -> dict:
    """Fill ONLY the DATA SHEET result column (G) for every submission row,
    by looking up the submission TAG NUMBER (column B) in the Data Sheet
    lookup table. No match, or a blank field on a match, both simply leave
    the cell blank -- nothing is invented or borrowed."""
    stats = {'submission_rows': 0, 'matched': 0, 'unmatched': 0,
             'matched_but_field_blank': 0, 'populated': 0}
    for row in range(2, ws.max_row + 1):
        stats['submission_rows'] += 1
        submission_tag = ws.cell(row=row, column=COL_SUBMISSION_TAG).value
        key = normalize_key(submission_tag)
        record = lookup.get(key) if key else None
        if record is None:
            stats['unmatched'] += 1
            continue
        stats['matched'] += 1
        value = record.get(field_key)
        if value in (None, ''):
            stats['matched_but_field_blank'] += 1
            continue
        ws.cell(row=row, column=COL_DATASHEET_RESULT).value = value
        stats['populated'] += 1
    return stats


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_output(wb: Workbook, reference_path: Path) -> list[str]:
    """Return a list of problems found (empty list = all checks passed)."""
    problems = []

    if wb.sheetnames != COMPARISON_SHEETS_IN_ORDER:
        problems.append(f"Sheet order mismatch: {wb.sheetnames} != {COMPARISON_SHEETS_IN_ORDER}")

    for sheet_name in FIELD_SHEETS_IN_ORDER:
        ws = wb[sheet_name]

        if ws.max_column < COL_FINAL:
            problems.append(f"{sheet_name}: has only {ws.max_column} columns, expected 13 (A:M)")
            continue

        for col, expected_text in EXPECTED_HEADER_TEXT.items():
            actual = ws.cell(row=1, column=col).value
            if actual is None or expected_text.upper() not in str(actual).upper():
                problems.append(f"{sheet_name}: column {col} header {actual!r} "
                                 f"does not contain expected '{expected_text}'")

        expected_final_header = FINAL_HEADER_BY_SHEET[sheet_name]
        actual_final_header = ws.cell(row=1, column=COL_FINAL).value
        if actual_final_header != expected_final_header:
            problems.append(f"{sheet_name}: FINAL header is {actual_final_header!r}, "
                             f"expected {expected_final_header!r}")

        for row in range(2, ws.max_row + 1):
            if ws.cell(row=row, column=COL_REMARKS).value not in (None, ''):
                problems.append(f"{sheet_name}: REMARKS not blank at row {row}")
                break
        for row in range(2, ws.max_row + 1):
            if ws.cell(row=row, column=COL_FINAL).value not in (None, ''):
                problems.append(f"{sheet_name}: FINAL not blank at row {row}")
                break
        for col in [COL_ASSET, COL_SPIR, COL_MXS, COL_MOM, COL_MTC]:
            for row in range(2, ws.max_row + 1):
                if ws.cell(row=row, column=col).value not in (None, ''):
                    problems.append(f"{sheet_name}: unexpected value in column {col} "
                                     f"(should be blank this phase) at row {row}")
                    break

    # submission row count preserved, vs the reference workbook
    ref_wb = openpyxl.load_workbook(reference_path, read_only=True)
    ref_rows = ref_wb['TAG NUMBER COMPARISION'].max_row
    ref_wb.close()
    out_rows = wb['TAG NUMBER COMPARISION'].max_row
    if ref_rows != out_rows:
        problems.append(f"Row count changed: reference had {ref_rows}, output has {out_rows}")

    return problems


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def build_phase1_datasheet_workbook(
    reference_path: str | Path,
    datasheet_path: str | Path,
    output_path: str | Path,
    allow_duplicate_keys: bool = False,
) -> dict:
    """Build the Phase 1 (Data Sheet only) comparison workbook.

    Returns a JSON-serializable processing report. Raises
    Phase1ValidationError on any input or output validation failure --
    never silently writes a partially-correct workbook.
    """
    reference_path = Path(reference_path)
    datasheet_path = Path(datasheet_path)
    output_path = Path(output_path)

    validate_inputs(reference_path, datasheet_path)

    records = load_datasheet_records(datasheet_path)
    lookup, duplicate_keys = build_datasheet_lookup(records, allow_duplicate_keys)

    report: dict = {
        'datasheet': {
            'rows_seen': len(records),
            'rows_with_key': sum(1 for r in records if r['normalized_key']),
            'unique_tags': len(lookup),
            'duplicate_keys': sorted(duplicate_keys.keys()),
            'duplicate_key_occurrences': duplicate_keys,
        },
    }

    wb = prepare_template(reference_path)

    for sheet_name, field_key in SHEET_FIELD_MAP.items():
        ws = wb[sheet_name]
        clear_source_and_derived_cells(ws)
        report[sheet_name] = populate_datasheet_column(ws, field_key, lookup)

    problems = validate_output(wb, reference_path)
    if problems:
        raise Phase1ValidationError(
            "Output validation failed -- refusing to save a partially-correct "
            "workbook:\n  " + "\n  ".join(problems)
        )
    report['output_validation'] = 'passed'

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    report['output_path'] = str(output_path)

    return report


# ============================================================
# CLI
# ============================================================

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='MTL Comparison Automation -- Phase 1 (Data Sheet population only).'
    )
    parser.add_argument('--reference', type=str,
                         default='input/5.MTL-DATA MISMATCH COMPARISION.xlsx',
                         help='Path to the reference/template comparison workbook.')
    parser.add_argument('--datasheet', type=str,
                         default='input/0904_4391-DATA SHEET PRIORITY-2_COMPLETED.xlsx',
                         help='Path to the Data Sheet source workbook.')
    parser.add_argument('--output', type=str,
                         default='output/MTL_DATA_COMPARISON_PHASE1_DATASHEET.xlsx',
                         help='Path to write the generated workbook to.')
    parser.add_argument('--allow-duplicate-keys', action='store_true',
                         help='If duplicate TAG NUMBER keys exist in the Data Sheet, '
                              'proceed using the LAST occurrence of each, instead of '
                              'failing validation.')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        report = build_phase1_datasheet_workbook(
            reference_path=args.reference,
            datasheet_path=args.datasheet,
            output_path=args.output,
            allow_duplicate_keys=args.allow_duplicate_keys,
        )
    except Phase1ValidationError as exc:
        print(f"VALIDATION ERROR:\n{exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, default=str))
    print(f"\nSaved: {report['output_path']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())