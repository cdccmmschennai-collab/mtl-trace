"""Integration tests: processing runs, source upload/identification/extraction, scope validation, provenance."""

import hashlib
import json
import sqlite3

import pytest

from tests.conftest import (
    DS_HEADERS,
    REAL_DATASHEET_FILE,
    create,
    ds_row,
    locked_milestone,
    make_workbook,
    new_run,
    scope_rows,
    upload,
)


def small_scope() -> bytes:
    return make_workbook({"S": scope_rows(5)})          # TAG-001 .. TAG-005


def ds_file(rows: list[list], headers=DS_HEADERS) -> bytes:
    return make_workbook({"DATASHEET": [headers] + rows, "PRD COUNT": [["SL.NO"], [1]]})


def db(client) -> sqlite3.Connection:
    return sqlite3.connect(client.app.state.db.path, isolation_level=None)


# ---------------------------------------------------------------- runs

def test_run_requires_locked_milestone(client):
    m = create(client)
    upload(client, f"/api/milestones/{m['id']}/scope", small_scope())
    r = client.post(f"/api/milestones/{m['id']}/runs", json={})
    assert r.status_code == 409 and "locked" in r.json()["detail"]
    assert client.post("/api/milestones/999/runs", json={}).status_code == 404


def test_create_and_list_runs(client):
    m = locked_milestone(client, small_scope())
    r1 = new_run(client, m["id"])
    r2 = client.post(f"/api/milestones/{m['id']}/runs", json={"notes": "revised MDS"}).json()
    assert (r1["run_number"], r2["run_number"]) == (1, 2)
    assert r1["status"] == "CREATED" and r1["rules_version"] == "v1" and r1["sources"] == []
    assert r1["scope_fingerprint"] == m["scope_fingerprint"] and r1["scope_tag_count"] == 5
    assert r2["notes"] == "revised MDS"
    runs = client.get(f"/api/milestones/{m['id']}/runs").json()
    assert [r["run_number"] for r in runs] == [2, 1]
    detail = client.get(f"/api/milestones/{m['id']}").json()
    assert detail["run_count"] == 2 and detail["latest_run"]["run_number"] == 2
    assert client.get("/api/runs/999").status_code == 404


def test_source_types_all_available_and_mds_spir_verified(client):
    types = {t["code"]: (t["adapter_available"], t["verified"]) for t in client.get("/api/source-types").json()}
    assert types == {"ASSET": (True, False), "MDS": (True, True), "SPIR": (True, True), "GA": (True, False),
                     "MXS": (True, False), "MTC": (True, False), "MOM": (True, False)}


# ---------------------------------------------------------------- real Data Sheet

def test_real_datasheet_end_to_end(client, data_dir, real_scope_bytes, real_datasheet_bytes):
    m = locked_milestone(client, real_scope_bytes)
    run = new_run(client, m["id"])
    r = upload(client, f"/api/runs/{run['id']}/sources", real_datasheet_bytes, name=REAL_DATASHEET_FILE.name)
    assert r.status_code == 201, r.text
    s = r.json()

    digest = hashlib.sha256(real_datasheet_bytes).hexdigest()
    assert (s["source_type"], s["source_type_label"], s["processing_status"]) == ("MDS", "DATA SHEET (MDS)", "PROCESSED")
    assert s["sha256"] == digest and s["file_size"] == len(real_datasheet_bytes)
    assert s["original_filename"] == REAL_DATASHEET_FILE.name and s["sheet_name"] == "DATASHEET"
    assert {x["sheet"] for x in s["skipped_sheets"]} == {"PRD COUNT", "Sheet1"}
    assert (s["row_count"], s["recognized_tag_count"], s["unique_tag_count"], s["duplicate_tag_count"]) == (436, 436, 436, 0)
    assert (s["matched_tag_count"], s["unmatched_tag_count"], s["scope_tags_without_record"]) == (436, 0, 281)
    assert s["scope_tag_count"] == 717
    assert s["attribute_counts"] == {"TAG_NUMBER": 357, "MAKE": 124, "MODEL": 98, "SERIAL_NUMBER": 0, "PART_NUMBER": 0}
    assert s["errors"] == [] and s["warnings"] == []

    # Stored immutably, content-addressed; the original input is untouched.
    stored = data_dir / "milestones" / "MTL-2026-001" / "sources" / f"{digest}.xlsx"
    assert stored.read_bytes() == real_datasheet_bytes
    assert REAL_DATASHEET_FILE.read_bytes() == real_datasheet_bytes

    # Run advanced; scope untouched.
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "DOCUMENTS_UPLOADED"
    scope = client.get(f"/api/milestones/{m['id']}/scope").json()
    assert scope["tag_count"] == 717 and scope["fingerprint"] == m["scope_fingerprint"]

    # One record per source row × attribute, empty values included.
    con = db(client)
    assert con.execute("select count(*) from source_record").fetchone()[0] == 436 * 5
    assert con.execute("select count(*) from source_record where milestone_tag_id is null").fetchone()[0] == 0
    assert con.execute("select count(*) from source_record where normalized_value is not null").fetchone()[0] == 357 + 124 + 98


def test_real_datasheet_provenance(client, real_scope_bytes, real_datasheet_bytes):
    m = locked_milestone(client, real_scope_bytes)
    run = new_run(client, m["id"])
    upload(client, f"/api/runs/{run['id']}/sources", real_datasheet_bytes, name=REAL_DATASHEET_FILE.name)
    con = db(client)
    raw, norm, loc, tag, mt = con.execute(
        "select r.raw_value, r.normalized_value, r.source_location, r.source_tag, t.tag_number "
        "from source_record r join milestone_tag t on t.id = r.milestone_tag_id "
        "where r.attribute = 'MAKE' and r.source_row_index = 256").fetchone()
    assert (raw, norm) == (" Honeywell", "Honeywell")          # raw kept exactly, normalized trimmed only
    assert tag == mt                                            # linked to the right milestone tag
    loc = json.loads(loc)
    assert loc["document"] == REAL_DATASHEET_FILE.name and loc["sheet"] == "DATASHEET"
    assert (loc["row"], loc["column"], loc["cell"]) == (256, "J", "J256")
    assert loc["document_reference"] and "page" in loc

    # The TAG attribute comes from TAG NUMBER AS PER DOC, not from the join key.
    val, key = con.execute("select normalized_value, normalized_tag from source_record "
                           "where attribute = 'TAG_NUMBER' and normalized_tag = '68-SP-051'").fetchone()
    assert (val, key) == ("SP-123", "68-SP-051")


def test_source_rows_endpoint_pages_extracted_rows(client, real_scope_bytes, real_datasheet_bytes):
    m = locked_milestone(client, real_scope_bytes)
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", real_datasheet_bytes, name=REAL_DATASHEET_FILE.name).json()
    page = client.get(f"/api/runs/{run['id']}/sources/{s['id']}/rows?offset=0&limit=10").json()
    assert page["total"] == 436 and len(page["rows"]) == 10
    first = page["rows"][0]
    assert first["row"] == 2 and first["source_tag"] == "61-BFV-1302" and first["in_scope"]
    assert set(first["values"]) == {"TAG_NUMBER", "MAKE", "MODEL", "SERIAL_NUMBER", "PART_NUMBER"}
    assert first["location"]["sheet"] == "DATASHEET"
    assert client.get(f"/api/runs/{run['id']}/sources/{s['id']}/rows?offset=430&limit=10").json()["rows"][-1]["row"] == 437


# ---------------------------------------------------------------- identification

def test_identify_is_a_dry_run(client, data_dir):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    r = upload(client, f"/api/runs/{run['id']}/sources/identify", ds_file([ds_row("TAG-001")]))
    assert r.status_code == 200
    body = r.json()
    assert (body["source_type"], body["sheet_name"], body["row_count"]) == ("MDS", "DATASHEET", 1)
    assert {b["key"] for b in body["mapping"]} >= {"TAG_KEY", "TAG_AS_PER_DOC", "MAKE", "MODEL"}
    assert client.get(f"/api/runs/{run['id']}").json()["sources"] == []
    assert list((data_dir / "milestones" / "MTL-2026-001" / "sources").iterdir()) == []


def test_unknown_requested_type_is_rejected_and_not_stored(client, data_dir):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    assert upload(client, f"/api/runs/{run['id']}/sources", b"x", source_type="BOGUS").status_code == 422
    assert list((data_dir / "milestones" / "MTL-2026-001" / "sources").iterdir()) == []


def test_requested_type_contradicted_by_the_file_fails(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001")]), source_type="GA").json()
    assert s["processing_status"] == "FAILED" and s["errors"][0]["code"] == "NOT_THIS_SOURCE_TYPE"
    assert "MDS" in s["errors"][0]["message"]


@pytest.mark.parametrize("sheet, headers, expected", [
    ("MXS DATA", ["TAG NUMBER", "MXS TAG NUMBER", "MAKE", "MODEL"], "MXS"),
    ("Sheet1", ["TAG NUMBER", "TAG NUMBER AS PER DOC", "MAKE", "MTC REFERENCE"], "MTC"),       # header keyword
    ("O&M MANUAL", ["TAG NO", "MANUFACTURER", "MODEL NO", "SERIAL NO"], "MOM"),
    ("NAME PLATE", ["TAG NUMBER", "MAKE", "SERIAL NUMBER"], "ASSET"),
    ("GA", ["TAG NUMBER", "GA TAG NUMBER", "MAKE"], "GA"),
])
def test_other_source_types_are_identified_by_keywords(client, sheet, headers, expected):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    row = ["TAG-001", *["X"] * (len(headers) - 1)]
    s = upload(client, f"/api/runs/{run['id']}/sources", make_workbook({sheet: [headers, row]})).json()
    assert (s["source_type"], s["errors"]) == (expected, [])
    assert s["matched_tag_count"] == 1


def test_unnamed_file_is_accepted_for_an_explicitly_chosen_unverified_type(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    data = make_workbook({"Export": [["TAG NUMBER", "MAKE", "MODEL"], ["TAG-001", "ACME", "M1"]]})
    auto = upload(client, f"/api/runs/{run['id']}/sources", data, name="a.xlsx").json()
    assert auto["processing_status"] == "FAILED" and auto["errors"][0]["code"] == "SOURCE_TYPE_UNKNOWN"
    run2 = new_run(client, m["id"])
    chosen = upload(client, f"/api/runs/{run2['id']}/sources", data, name="a.xlsx", source_type="MTC").json()
    assert chosen["source_type"] == "MTC" and chosen["attributes_provided"] == ["MAKE", "MODEL"]


def test_non_workbook_is_rejected(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    assert upload(client, f"/api/runs/{run['id']}/sources", b"hello", name="notes.txt").status_code == 422
    assert upload(client, f"/api/runs/{run['id']}/sources", b"not a zip", name="x.xlsx").status_code == 422


def test_explicit_datasheet_type_is_cross_checked(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    other = make_workbook({"Tags": [["TAG NUMBER", "MAKE"], ["TAG-001", "A"]]})
    s = upload(client, f"/api/runs/{run['id']}/sources", other, source_type="MDS").json()
    assert s["processing_status"] == "FAILED" and s["errors"][0]["code"] == "NOT_THIS_SOURCE_TYPE"


# ---------------------------------------------------------------- failures are recorded, never guessed

def test_ambiguous_mapping_fails_visibly_and_extracts_nothing(client, data_dir):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    headers = DS_HEADERS + ["MANUFACTURER"]
    data = ds_file([ds_row("TAG-001", make="A") + ["B"]], headers=headers)
    r = upload(client, f"/api/runs/{run['id']}/sources", data, name="bad.xlsx")
    assert r.status_code == 201
    s = r.json()
    assert s["processing_status"] == "FAILED" and s["source_type"] == "MDS"
    [err] = s["errors"]
    assert err["code"] == "AMBIGUOUS_FIELD" and "bad.xlsx" in err["message"] and "DATASHEET" in err["message"]
    assert "MANUFACTURER" in err["message"] and s["row_count"] is None
    assert db(client).execute("select count(*) from source_record").fetchone()[0] == 0
    assert (data_dir / "milestones" / "MTL-2026-001" / "sources" / f"{s['sha256']}.xlsx").exists()
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "CREATED"


def test_missing_attribute_column_is_reported_with_headers_found_and_processes(client):
    """Available-data principle (Phase 1D-1): a missing MODEL column is reported, never guessed, and the
    document still processes with the attributes it has."""
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    headers = [h for h in DS_HEADERS if h != "MODEL"]
    row = ds_row("TAG-001", make="ACME")
    del row[DS_HEADERS.index("MODEL")]
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([row], headers=headers)).json()
    assert s["processing_status"] == "PROCESSED_WITH_WARNINGS" and s["errors"] == []
    [w] = s["warnings"]
    assert w["code"] == "FIELD_NOT_PROVIDED" and w["value"] == "MODEL" and "Headers found" in w["message"]
    assert "MODEL" not in s["attributes_provided"] and s["attribute_counts"]["MAKE"] == 1


def test_missing_join_key_still_fails_with_headers_found(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources",
               make_workbook({"DATASHEET": [["S.NO", "MAKE", "MODEL"], [1, "A", "M"]]})).json()
    assert s["processing_status"] == "FAILED"
    assert s["errors"][0]["code"] == "MISSING_FIELD" and "Headers found" in s["errors"][0]["message"]


def test_unknown_document_fails_as_unknown_type(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", make_workbook({"X": [["A"], [1]]})).json()
    assert s["processing_status"] == "FAILED" and s["source_type"] is None
    assert s["errors"][0]["code"] == "SOURCE_TYPE_UNKNOWN"


# ---------------------------------------------------------------- scope checks

def test_duplicate_source_tags_are_kept_and_reported(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    rows = [ds_row("TAG-001", make="ACME"), ds_row("TAG-002"), ds_row("tag-001 ", make="OTHER")]
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file(rows)).json()
    assert s["processing_status"] == "PROCESSED_WITH_WARNINGS"
    assert (s["row_count"], s["unique_tag_count"], s["duplicate_tag_count"], s["matched_tag_count"]) == (3, 2, 1, 2)
    assert s["duplicates"] == [{"tag": "TAG-001", "rows": [2, 4], "in_scope": True}]
    assert [w["code"] for w in s["warnings"]] == ["DUPLICATE_SOURCE_TAG"]
    makes = db(client).execute("select raw_value from source_record where attribute='MAKE' "
                               "and normalized_tag='TAG-001' order by source_row_index").fetchall()
    assert [x[0] for x in makes] == ["ACME", "OTHER"]            # both kept, none chosen


def test_out_of_scope_tags_are_reported_not_added(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    rows = [ds_row("TAG-001"), ds_row("NOT-IN-SCOPE", make="X"), ds_row("TAG-003")]
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file(rows)).json()
    assert (s["matched_tag_count"], s["unmatched_tag_count"], s["scope_tags_without_record"]) == (2, 1, 3)
    assert s["out_of_scope"] == [{"tag": "NOT-IN-SCOPE", "rows": [3]}]
    assert [w["code"] for w in s["warnings"]] == ["OUT_OF_SCOPE_TAG"]
    con = db(client)
    assert con.execute("select count(*) from source_record where normalized_tag='NOT-IN-SCOPE' "
                       "and milestone_tag_id is null").fetchone()[0] == 5
    assert client.get(f"/api/milestones/{m['id']}/scope").json()["tag_count"] == 5


def test_rows_without_tag_key_are_recorded_as_unlinked(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001"), ds_row(None, make="ORPHAN")])).json()
    assert s["rows_without_tag_key"] == [3] and s["recognized_tag_count"] == 1
    assert "BLANK_TAG_KEY" in [w["code"] for w in s["warnings"]]


def test_document_from_another_milestone_warns(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("ZZZ-1")])).json()
    assert "NO_TAG_IN_SCOPE" in [w["code"] for w in s["warnings"]]


# ---------------------------------------------------------------- document identity & immutability

def test_same_file_twice_in_one_run_is_refused_but_reused_across_runs(client):
    m = locked_milestone(client, small_scope())
    run1, run2 = new_run(client, m["id"]), new_run(client, m["id"])
    data = ds_file([ds_row("TAG-001")])
    a = upload(client, f"/api/runs/{run1['id']}/sources", data).json()
    assert upload(client, f"/api/runs/{run1['id']}/sources", data).status_code == 409
    b = upload(client, f"/api/runs/{run2['id']}/sources", data, name="renamed.xlsx").json()
    assert a["document_id"] == b["document_id"] and a["id"] != b["id"]
    assert b["original_filename"] == a["original_filename"]        # the document keeps its first identity
    assert db(client).execute("select count(*) from source_document").fetchone()[0] == 1


def test_document_date_and_revision_captured(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001")]),
               document_date="2026-09-04", revision="C").json()
    assert (s["document_date"], s["revision"]) == ("2026-09-04", "C")
    bad = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-002")]), document_date="04/09/2026")
    assert bad.status_code == 422


def test_source_evidence_is_immutable_in_the_database(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001", make="A")]))
    con = db(client)
    for sql in ("UPDATE source_record SET raw_value = 'B'", "DELETE FROM source_record",
                "UPDATE source_document SET sha256 = 'x'"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute(sql)


def test_run_source_detail_and_404s(client):
    m = locked_milestone(client, small_scope())
    run = new_run(client, m["id"])
    s = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001")])).json()
    assert client.get(f"/api/runs/{run['id']}/sources/{s['id']}").json()["id"] == s["id"]
    assert client.get(f"/api/runs/{run['id']}/sources/999").status_code == 404
    other = new_run(client, m["id"])
    assert client.get(f"/api/runs/{other['id']}/sources/{s['id']}").status_code == 404
    assert client.get(f"/api/runs/{run['id']}").json()["sources"][0]["id"] == s["id"]
