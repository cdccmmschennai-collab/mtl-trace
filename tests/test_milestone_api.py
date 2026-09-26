"""Integration tests through the HTTP API: create â†’ import scope â†’ validate â†’ lock â†’ history."""

import hashlib
import sqlite3

import pytest

from backend.storage.files import MILESTONE_SUBDIRS
from tests.conftest import REAL_SCOPE_FILE, create, make_workbook, scope_rows, upload


# ---- milestone creation

def test_create_milestone_creates_record_and_folders(client, data_dir):
    m = create(client, "MTL-2026-001", project_name="CDC", package_name="PKG-A")
    assert m["milestone_code"] == "MTL-2026-001"
    assert (m["project_name"], m["package_name"]) == ("CDC", "PKG-A")
    assert (m["status"], m["scope_status"], m["tag_count"], m["run_count"]) == ("DRAFT", "NONE", 0, 0)
    assert (data_dir / "database" / "mtl.db").exists()
    assert (data_dir / "logs").is_dir()
    for sub in MILESTONE_SUBDIRS:
        assert (data_dir / "milestones" / "MTL-2026-001" / sub).is_dir()


def test_milestone_without_project_or_package(client):
    m = create(client, "M1")
    assert m["project_name"] is None and m["package_name"] is None


def test_project_and_package_are_reused(client):
    create(client, "M1", project_name="CDC", package_name="P")
    create(client, "M2", project_name="cdc", package_name="p")
    con = sqlite3.connect(client.app.state.db.path, isolation_level=None)  # autocommit: no lingering write lock
    assert con.execute("select count(*) from project").fetchone()[0] == 1
    assert con.execute("select count(*) from package").fetchone()[0] == 1


def test_duplicate_milestone_code_rejected_case_insensitively(client):
    create(client, "MTL-2026-001")
    r = client.post("/api/milestones", json={"milestone_code": "mtl-2026-001"})
    assert r.status_code == 409


@pytest.mark.parametrize("code", ["", "   ", "../evil", "a/b", "CON", "name.", "-lead"])
def test_invalid_milestone_codes_rejected(client, code):
    assert client.post("/api/milestones", json={"milestone_code": code}).status_code == 422


def test_package_requires_project(client):
    r = client.post("/api/milestones", json={"milestone_code": "M1", "package_name": "P"})
    assert r.status_code == 422


def test_unknown_milestone_404(client):
    assert client.get("/api/milestones/999").status_code == 404
    assert client.get("/api/milestones/999/scope").status_code == 404
    assert client.post("/api/milestones/999/scope/lock").status_code == 404


# ---- scope import & validation

def test_validate_is_a_dry_run(client):
    m = create(client)
    r = upload(client, f"/api/milestones/{m['id']}/scope/validate", make_workbook({"S": scope_rows(3)}))
    assert r.status_code == 200
    rep = r.json()
    assert rep["valid"] and rep["tag_count"] == 3 and rep["columns"]["TAG NUMBER"] == "B"
    assert client.get(f"/api/milestones/{m['id']}/scope").json()["tag_count"] == 0


def test_validate_reports_invalid_rows(client):
    m = create(client)
    rows = scope_rows(4)
    rows[2][1] = None
    rows[3][1] = "TAG-001"
    rep = upload(client, f"/api/milestones/{m['id']}/scope/validate", make_workbook({"S": rows})).json()
    assert not rep["valid"] and rep["tag_count"] == 0 and rep["data_row_count"] == 4
    by_code = {e["code"]: e for e in rep["errors"]}
    assert by_code["BLANK_TAG"]["rows"] == [3]
    assert by_code["DUPLICATE_TAG"]["rows"] == [2, 4]


def test_invalid_scope_import_is_rejected_and_nothing_persisted(client):
    m = create(client)
    rows = scope_rows(3)
    rows[3][1] = "TAG-001"
    r = upload(client, f"/api/milestones/{m['id']}/scope", make_workbook({"S": rows}))
    assert r.status_code == 422
    assert r.json()["detail"]["report"]["errors"][0]["code"] == "DUPLICATE_TAG"
    scope = client.get(f"/api/milestones/{m['id']}/scope").json()
    assert scope["tag_count"] == 0 and scope["scope_status"] == "NONE"


def test_import_stores_scope_and_original_file(client, data_dir):
    m = create(client)
    data = make_workbook({"S": scope_rows(5)})
    r = upload(client, f"/api/milestones/{m['id']}/scope", data, name="my scope.xlsx")
    assert r.status_code == 201
    body = r.json()
    digest = hashlib.sha256(data).hexdigest()
    assert body["report"]["file_sha256"] == digest
    assert body["milestone"]["scope_status"] == "DRAFT" and body["milestone"]["tag_count"] == 5
    assert body["milestone"]["scope_file_name"] == "my scope.xlsx"
    stored = data_dir / "milestones" / "MTL-2026-001" / "scope" / f"{digest}.xlsx"
    assert stored.read_bytes() == data

    scope = client.get(f"/api/milestones/{m['id']}/scope").json()
    assert [t["tag_number"] for t in scope["tags"]] == [f"TAG-{i:03d}" for i in range(1, 6)]
    assert scope["tags"][0]["s_no"] == "0001"


def test_draft_scope_can_be_replaced_before_lock(client):
    m = create(client)
    upload(client, f"/api/milestones/{m['id']}/scope", make_workbook({"S": scope_rows(5)}))
    r = upload(client, f"/api/milestones/{m['id']}/scope", make_workbook({"S": scope_rows(2)}))
    assert r.status_code == 201
    assert client.get(f"/api/milestones/{m['id']}/scope").json()["tag_count"] == 2


def test_real_717_tag_scope_import(client, real_scope_bytes):
    m = create(client)
    r = upload(client, f"/api/milestones/{m['id']}/scope", real_scope_bytes, name=REAL_SCOPE_FILE.name)
    assert r.status_code == 201, r.text
    rep = r.json()["report"]
    assert rep["valid"] and rep["sheet_name"] == "TAG NUMBER COMPARISION"
    assert rep["tag_count"] == 717 and rep["errors"] == [] and rep["warnings"] == []
    scope = client.get(f"/api/milestones/{m['id']}/scope").json()
    assert scope["tag_count"] == len(scope["tags"]) == 717
    assert scope["tags"][0]["s_no"] == "0001" and scope["tags"][-1]["s_no"] == "0717"
    # The input file on disk is never modified.
    assert REAL_SCOPE_FILE.read_bytes() == real_scope_bytes


# ---- locking

def _imported(client, n=3) -> dict:
    m = create(client)
    assert upload(client, f"/api/milestones/{m['id']}/scope", make_workbook({"S": scope_rows(n)})).status_code == 201
    return m


def test_lock_scope(client):
    m = _imported(client)
    r = client.post(f"/api/milestones/{m['id']}/scope/lock")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "SCOPE_LOCKED" and body["scope_status"] == "LOCKED"
    assert body["scope_locked_at"] and len(body["scope_fingerprint"]) == 64


def test_cannot_lock_without_scope(client):
    m = create(client)
    assert client.post(f"/api/milestones/{m['id']}/scope/lock").status_code == 409


def test_cannot_lock_twice(client):
    m = _imported(client)
    client.post(f"/api/milestones/{m['id']}/scope/lock")
    assert client.post(f"/api/milestones/{m['id']}/scope/lock").status_code == 409


def test_locked_scope_rejects_import_and_validate(client):
    m = _imported(client)
    before = client.get(f"/api/milestones/{m['id']}/scope").json()
    client.post(f"/api/milestones/{m['id']}/scope/lock")
    new = make_workbook({"S": scope_rows(9)})
    assert upload(client, f"/api/milestones/{m['id']}/scope", new).status_code == 409
    assert upload(client, f"/api/milestones/{m['id']}/scope/validate", new).status_code == 409
    after = client.get(f"/api/milestones/{m['id']}/scope").json()
    assert after["tags"] == before["tags"]


def test_database_itself_refuses_changes_to_a_locked_scope(client):
    """Protection holds even for writes that bypass the service layer."""
    m = _imported(client)
    client.post(f"/api/milestones/{m['id']}/scope/lock")
    con = sqlite3.connect(client.app.state.db.path, isolation_level=None)  # autocommit: no lingering write lock
    statements = [
        "UPDATE milestone_tag SET tag_number = 'X' WHERE milestone_id = ?",
        "DELETE FROM milestone_tag WHERE milestone_id = ?",
        "INSERT INTO milestone_tag (milestone_id, scope_order, source_row, tag_number, normalized_tag) "
        "VALUES (?, 99, 99, 'NEW', 'NEW')",
        "UPDATE milestone SET status = 'DRAFT' WHERE id = ?",
        "UPDATE milestone SET scope_locked_at = NULL WHERE id = ?",
        "UPDATE milestone SET scope_fingerprint = 'x' WHERE id = ?",
        "DELETE FROM milestone WHERE id = ?",
    ]
    for sql in statements:
        with pytest.raises(sqlite3.IntegrityError, match="locked"):
            con.execute(sql, (m["id"],))
    assert con.execute("select count(*) from milestone_tag").fetchone()[0] == 3


def test_processing_run_requires_locked_scope(client):
    m = _imported(client)
    con = sqlite3.connect(client.app.state.db.path, isolation_level=None)  # autocommit: no lingering write lock
    sql = ("INSERT INTO processing_run (milestone_id, run_number, status, rules_version, created_at) "
           "VALUES (?, 1, 'CREATED', 'v1', '2026-09-24')")
    with pytest.raises(sqlite3.IntegrityError, match="locked"):
        con.execute(sql, (m["id"],))
    client.post(f"/api/milestones/{m['id']}/scope/lock")
    con.execute(sql, (m["id"],))
    detail = client.get(f"/api/milestones/{m['id']}").json()
    assert detail["run_count"] == 1 and detail["latest_run"]["run_number"] == 1


# ---- history

def test_history_lists_milestones_newest_first_with_scope_state(client):
    create(client, "M-A", project_name="CDC", package_name="P1")
    b = create(client, "M-B")
    upload(client, f"/api/milestones/{b['id']}/scope", make_workbook({"S": scope_rows(4)}))
    c = create(client, "M-C")
    upload(client, f"/api/milestones/{c['id']}/scope", make_workbook({"S": scope_rows(2)}))
    client.post(f"/api/milestones/{c['id']}/scope/lock")

    history = client.get("/api/milestones").json()
    assert [h["milestone_code"] for h in history] == ["M-C", "M-B", "M-A"]
    by_code = {h["milestone_code"]: h for h in history}
    assert (by_code["M-A"]["scope_status"], by_code["M-A"]["tag_count"]) == ("NONE", 0)
    assert (by_code["M-A"]["project_name"], by_code["M-A"]["package_name"]) == ("CDC", "P1")
    assert (by_code["M-B"]["scope_status"], by_code["M-B"]["tag_count"]) == ("DRAFT", 4)
    assert (by_code["M-C"]["scope_status"], by_code["M-C"]["tag_count"]) == ("LOCKED", 2)
    assert all(h["created_at"] and h["run_count"] == 0 and h["latest_run"] is None for h in history)


def test_history_survives_restart(data_dir, real_scope_bytes):
    from fastapi.testclient import TestClient

    from backend.config import Settings
    from backend.main import create_app

    app1 = create_app(Settings(data_dir=data_dir))
    with TestClient(app1) as c1:
        m = create(c1)
        upload(c1, f"/api/milestones/{m['id']}/scope", real_scope_bytes, name=REAL_SCOPE_FILE.name)
        c1.post(f"/api/milestones/{m['id']}/scope/lock")
        fingerprint = c1.get(f"/api/milestones/{m['id']}").json()["scope_fingerprint"]
    app1.state.db.dispose()

    app2 = create_app(Settings(data_dir=data_dir))
    with TestClient(app2) as c2:
        [h] = c2.get("/api/milestones").json()
        assert (h["milestone_code"], h["scope_status"], h["tag_count"]) == ("MTL-2026-001", "LOCKED", 717)
        assert c2.get(f"/api/milestones/{h['id']}").json()["scope_fingerprint"] == fingerprint
    app2.state.db.dispose()
