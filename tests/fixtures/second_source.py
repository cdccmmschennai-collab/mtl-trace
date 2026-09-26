"""CONTROLLED SECOND-SOURCE FIXTURE — test/verification only. NOT the production SPIR adapter.

The real SPIR (`backend/extraction/spir.py`, verified on the real file) has no duplicate and no
out-of-scope tag, so it cannot exercise those states in a second source. Tests that need them (and the
browser-verification launcher `serve_with_fixture.py`) temporarily replace the SPIR adapter with this one.
It is recognised only by a sheet named `CONTROLLED FIXTURE SPIR`; its fields are found by the shared
keyword discovery like any other source.

    python -m tests.fixtures.second_source <scope.xlsx> <out.xlsx>   # write a fixture file for the browser
"""

import io
import sys
from pathlib import Path

import openpyxl

from backend.extraction.tabular import TabularAdapter, TabularAdapterConfig

FIXTURE_SHEET = "CONTROLLED FIXTURE SPIR"
FIXTURE_REF_HEADER = "FIXTURE DOCUMENT REFERENCE"
FIXTURE_HEADERS = ["TAG NUMBER", "TAG NUMBER AS PER DOC", "MAKE", "MODEL", "SERIAL NUMBER", "PART NUMBER",
                   FIXTURE_REF_HEADER, "PAGE NO"]

FIXTURE_SPIR_ADAPTER = TabularAdapter(TabularAdapterConfig(
    source_type="SPIR",
    document_label="controlled SPIR fixture (test only — not a production SPIR adapter)",
    sheet_names=(FIXTURE_SHEET,),
    evidence_headers=(FIXTURE_REF_HEADER,),
))


def fixture_row(tag, as_per_doc=None, make=None, model=None, serial=None, part=None, ref="FIXTURE-SPIR-1", page=1):
    return [tag, as_per_doc, make, model, serial, part, ref, page]


def fixture_workbook(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = FIXTURE_SHEET
    ws.append(FIXTURE_HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def browser_fixture_rows(scope_tags: list[str]) -> list[list]:
    """A small, deterministic second source over real scope tags, exercising every canonical state:
    values equal to / different from the Data Sheet, empty values, one duplicate tag and one tag
    outside the scope. Values are invented test data and say so."""
    t = scope_tags
    return [
        fixture_row(t[0], as_per_doc=t[0], make="FIXTURE MAKE A", model="FX-100", serial="FX-SN-0001", part="FX-PN-1"),
        fixture_row(t[1], as_per_doc=t[1], make="FIXTURE MAKE A", model="FX-100"),
        fixture_row(t[2], as_per_doc="FIXTURE-DIFFERENT-TAG", make="FIXTURE MAKE B"),
        fixture_row(t[3]),                                                 # row exists, every value empty
        fixture_row(t[4], make="FIXTURE MAKE C", serial="FX-SN-0005"),
        fixture_row(t[4], make="FIXTURE MAKE D"),                          # duplicate tag — none chosen
        fixture_row("FIXTURE-OUT-OF-SCOPE-001", make="FIXTURE MAKE X"),    # outside the milestone
    ]


def main(scope_path: str, out_path: str) -> None:
    from backend.domain.scope import ScopeField
    from backend.extraction.scope import read_scope_workbook
    read = read_scope_workbook(Path(scope_path).name, Path(scope_path).read_bytes())
    tags = [str(r.values[ScopeField.TAG_NUMBER]).strip() for r in read.rows if not r.is_empty]
    Path(out_path).write_bytes(fixture_workbook(browser_fixture_rows(tags)))
    print(f"wrote {out_path} ({len(browser_fixture_rows(tags))} rows)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
