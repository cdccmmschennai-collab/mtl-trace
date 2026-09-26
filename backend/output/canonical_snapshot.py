"""Canonical dataset snapshot: the long table (tag × attribute × source) as UTF-8 CSV, one file per run.

An archival, tool-independent copy of exactly what was stored — states, unmodified values and the
provenance of every cell — so a run's canonical layer can be inspected without the application.
"""

import csv
import io
from dataclasses import dataclass

COLUMNS = ("scope_order", "s_no", "milestone_tag", "attribute", "source_type", "state", "raw_value",
           "normalized_value", "source_record_ids", "document", "sheet", "row", "cell", "document_reference", "page")


@dataclass(frozen=True)
class SnapshotRow:
    scope_order: int
    s_no: str | None
    milestone_tag: str
    attribute: str
    source_type: str
    state: str
    raw_value: str | None
    normalized_value: str | None
    source_record_ids: tuple[int, ...]
    locations: tuple[dict, ...]


def build_snapshot(rows: list[SnapshotRow]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(COLUMNS)

    def join(locs, key):
        return " | ".join("" if loc.get(key) is None else str(loc.get(key)) for loc in locs)

    for r in rows:
        w.writerow([r.scope_order, r.s_no or "", r.milestone_tag, r.attribute, r.source_type, r.state,
                    "" if r.raw_value is None else r.raw_value,
                    "" if r.normalized_value is None else r.normalized_value,
                    " ".join(map(str, r.source_record_ids)),
                    join(r.locations, "document"), join(r.locations, "sheet"), join(r.locations, "row"),
                    join(r.locations, "cell"), join(r.locations, "document_reference"), join(r.locations, "page")])
    return buf.getvalue().encode("utf-8-sig")        # BOM so Excel opens it as UTF-8
