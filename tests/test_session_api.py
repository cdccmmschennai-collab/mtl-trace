"""The single working session: one scope, one run, no history."""

import sqlite3

from backend.config import Settings
from backend.main import create_app
from backend.services.session import DEFAULT_CODE, code_from_file_name
from tests.conftest import DS_HEADERS, ds_row, make_workbook, scope_rows, upload


def ds_file(rows: list[list]) -> bytes:
    return make_workbook({"DATASHEET": [DS_HEADERS] + rows})


def start(client, n: int = 5, name: str = "My Scope.xlsx") -> dict:
    r = upload(client, "/api/session/scope", make_workbook({"S": scope_rows(n)}), name=name)
    assert r.status_code == 201, r.text
    return r.json()


def counts(client) -> tuple:
    con = sqlite3.connect(client.app.state.db.path, isolation_level=None)
    return tuple(con.execute(f"select count(*) from {t}").fetchone()[0]
                 for t in ("milestone", "processing_run", "source_document", "canonical_cell"))


def test_no_session_before_a_scope_is_loaded(client):
    r = client.get("/api/session")
    assert r.status_code == 200 and r.json() is None


def test_scope_starts_a_locked_session_with_one_run(client):
    s = start(client, 5)
    m, run = s["milestone"], s["run"]
    assert m["scope_status"] == "LOCKED" and m["tag_count"] == 5 and m["scope_file_name"] == "My Scope.xlsx"
    assert m["milestone_code"] == "MY-SCOPE" and m["run_count"] == 1
    assert run["milestone_id"] == m["id"] and run["status"] == "CREATED" and run["scope_tag_count"] == 5
    assert client.get("/api/session").json() == s


def test_full_flow_through_the_session(client):
    run = start(client, 3)["run"]
    src = upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001", make="ACME")]), name="ds.xlsx")
    assert src.status_code == 201, src.text
    assert client.post(f"/api/runs/{run['id']}/consolidate").status_code == 201
    cmp = client.post(f"/api/runs/{run['id']}/compare").json()
    assert cmp["output"]["file_name"] == "MTL-DATA MISMATCH COMPARISION.xlsx"
    assert client.get(f"/api/runs/{run['id']}/outputs/{cmp['output']['id']}/download").status_code == 200


def test_validate_is_a_dry_run(client):
    first = start(client, 3)
    r = upload(client, "/api/session/scope/validate", make_workbook({"S": scope_rows(7)}))
    assert r.status_code == 200 and r.json()["valid"] and r.json()["tag_count"] == 7
    assert client.get("/api/session").json() == first


def test_invalid_scope_is_rejected_and_keeps_the_current_session(client):
    first = start(client, 3)
    bad = make_workbook({"S": scope_rows(2) + [["0003", "TAG-001", "DUP", "EQUIP", None]]})
    r = upload(client, "/api/session/scope", bad)
    assert r.status_code == 422 and r.json()["detail"]["report"]["valid"] is False
    assert client.get("/api/session").json() == first


def test_new_scope_replaces_everything(client, data_dir):
    run = start(client, 3)["run"]
    upload(client, f"/api/runs/{run['id']}/sources", ds_file([ds_row("TAG-001", make="ACME")]))
    client.post(f"/api/runs/{run['id']}/consolidate")
    assert counts(client) == (1, 1, 1, 15)

    s = start(client, 4, name="second.xlsx")
    assert s["milestone"]["tag_count"] == 4 and s["run"]["sources"] == []
    assert counts(client) == (1, 1, 0, 0)
    assert [p.name for p in (data_dir / "milestones").iterdir()] == ["SECOND"]


def test_reset_discards_the_session(client, data_dir):
    start(client, 3)
    assert client.delete("/api/session").status_code == 204
    assert client.get("/api/session").json() is None
    assert counts(client) == (0, 0, 0, 0)
    assert list((data_dir / "milestones").iterdir()) == []


def test_fresh_start_discards_the_previous_session(data_dir):
    from fastapi.testclient import TestClient

    first = create_app(Settings(data_dir=data_dir))
    with TestClient(first) as c:
        start(c, 3)
    first.state.db.dispose()
    again = create_app(Settings(data_dir=data_dir, fresh_start=True))
    with TestClient(again) as c:
        assert c.get("/api/session").json() is None
    again.state.db.dispose()


def test_code_from_file_name():
    assert code_from_file_name("5.MTL-DATA MISMATCH COMPARISION.xlsx") == "5.MTL-DATA-MISMATCH-COMPARISION"
    assert code_from_file_name("  my   scope (rev 2).xlsx") == "MY-SCOPE-REV-2"
    assert code_from_file_name("CON.xlsx") == DEFAULT_CODE
    assert code_from_file_name("___.xlsx") == DEFAULT_CODE
