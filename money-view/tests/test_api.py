import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.service import PlacementService
from server.store import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "api.sqlite3", FixtureInterpreter())) as value:
        yield value


def confirmation(client):
    example = client.get("/api/home").json()["examples"][0]
    response = client.post(
        "/api/interpret",
        json={
            "message": example["messages"]["es-419"],
            "locale": "es-419",
            "demo_example_id": example["id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmation"
    return response.json()["confirmation"]


def test_http_complete_saved_notice_flow(client):
    home = client.get("/api/home").json()
    assert home["demo"] is True
    assert home["source_status"]["state"] == "ready"
    assert home["saved"] == []
    proposal = confirmation(client)
    assert "rows" not in proposal
    computed = client.post(
        f"/api/confirmations/{proposal['id']}/compute",
        json={"inputs": proposal["inputs"]},
    )
    assert computed.status_code == 200
    result = computed.json()
    assert result["inputs"]["amount"] == "250000.00"
    source_id = next(
        row["source"]["id"] for row in result["rows"] if not row["is_baseline"]
    )
    source = client.get(f"/api/sources/{source_id}").json()
    assert source["synthetic"] is True
    assert source["kind"] == "synthetic"
    assert source["published_on"]
    decision = client.post(f"/api/comparisons/{result['id']}/save").json()
    assert client.get(f"/api/decisions/{decision['id']}").json() == decision
    event = client.post("/api/demo/events", json={"scenario": "leader_changed"})
    assert event.status_code == 202
    home = client.get("/api/home").json()
    assert home["source_status"]["load_id"] == event.json()["load_id"]
    assert home["source_status"]["state"] == "ready"
    notice = client.get("/api/notices").json()["items"][0]
    assert notice["reasons"] == ["winner_changed"]
    assert notice["before"] == result
    assert notice["after"] == home["saved"][0]["latest"]
    assert client.post(f"/api/notices/{notice['id']}/read").json()["read_at"] is not None
    assert client.get("/api/home").json()["notices"][0]["read_at"] is not None


def test_api_retries_edits_and_validation(client):
    proposal = confirmation(client)
    inputs = dict(proposal["inputs"], amount="10000", current_annual_rate_pct=None)
    endpoint = f"/api/confirmations/{proposal['id']}/compute"
    first = client.post(endpoint, json={"inputs": inputs})
    assert first.status_code == 200
    assert first.json()["inputs"]["amount"] == "10000.00"
    assert client.post(endpoint, json={"inputs": inputs}).json() == first.json()
    conflict = client.post(endpoint, json={"inputs": proposal["inputs"]})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "confirmation_consumed"
    invalid = client.post(endpoint, json={"inputs": dict(inputs, amount="NaN")})
    assert invalid.status_code == 422
    assert invalid.json() == {"code": "invalid_request"}
    invalid = client.post(
        "/api/interpret", json={"message": "anything", "surprise": True}
    )
    assert invalid.status_code == 422


@pytest.mark.parametrize("endpoint", ["/api/decisions/missing", "/api/sources/missing"])
def test_unknown_resources_are_json_not_found(client, endpoint):
    response = client.get(endpoint)
    assert response.status_code == 404
    assert response.json()["code"].endswith("not_found")


def test_unavailable_free_text_and_edited_demo_do_not_compute(client):
    response = client.post(
        "/api/interpret",
        json={"message": "Anything outside an explicit replay", "locale": "en"},
    )
    assert response.json()["status"] == "model_unavailable"
    example = client.get("/api/home").json()["examples"][0]
    response = client.post(
        "/api/interpret",
        json={
            "message": "Changed example",
            "locale": "en",
            "demo_example_id": example["id"],
        },
    )
    assert response.json()["status"] == "model_unavailable"
    with client.app.state.service.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] == 0


def test_failed_background_load_is_reported_without_erasing_saved_result(client):
    proposal = confirmation(client)
    result = client.post(
        f"/api/confirmations/{proposal['id']}/compute",
        json={"inputs": proposal["inputs"]},
    ).json()
    decision = client.post(f"/api/comparisons/{result['id']}/save").json()
    assert (
        client.post("/api/demo/events", json={"scenario": "failure"}).status_code == 202
    )
    home = client.get("/api/home").json()
    assert home["source_status"]["state"] == "stale"
    assert home["saved"][0]["latest"] == decision["baseline"]
    assert home["saved"][0]["checks"][0]["status"] == "failed"


def test_scheduled_cli_writes_same_sqlite_state_without_model_configuration(tmp_path):
    database = tmp_path / "scheduled.sqlite3"
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "server.jobs",
        "--database",
        str(database),
        "--provider",
        "fixture",
        "load",
        "--load-id",
        "scheduled-1",
    ]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CLARA_LLM_")
    }
    completed = subprocess.run(
        command, cwd=root, env=environment, capture_output=True, text=True, check=True
    )
    assert json.loads(completed.stdout)["source_status"]["state"] == "ready"
    with TestClient(create_app(database, FixtureInterpreter())) as client:
        assert client.get("/api/home").json()["source_status"]["load_id"] == "scheduled-1"
        repeated = subprocess.run(
            command, cwd=root, env=environment, capture_output=True, text=True, check=True
        )
        assert json.loads(repeated.stdout)["load_id"] == "scheduled-1"


def test_app_restart_recovers_interrupted_load_without_changing_saved_result(tmp_path):
    database = tmp_path / "restart.sqlite3"
    with TestClient(create_app(database, FixtureInterpreter())) as client:
        proposal = confirmation(client)
        result = client.post(
            f"/api/confirmations/{proposal['id']}/compute",
            json={"inputs": proposal["inputs"]},
        ).json()
        decision = client.post(f"/api/comparisons/{result['id']}/save").json()
        load_id = client.app.state.service.begin_load("leader_changed")
        # Opening a connection or service for a concurrent job is not recovery.
        concurrent = PlacementService(Store(database))
        assert concurrent.home("fixture")["source_status"]["state"] == "loading"

    for _ in range(2):
        with TestClient(create_app(database, FixtureInterpreter())) as restarted:
            home = restarted.get("/api/home").json()
            assert home["source_status"]["state"] == "stale"
            assert home["source_status"]["error_code"] == "load_interrupted"
            assert home["source_status"]["load_id"] == load_id
            assert home["saved"][0]["latest"] == decision["baseline"]
            checks = home["saved"][0]["checks"]
            assert len(checks) == 1
            assert checks[0]["status"] == "failed"
            assert checks[0]["error_code"] == "load_interrupted"
            assert home["notices"] == []
    with TestClient(create_app(database, FixtureInterpreter())) as restarted:
        assert (
            restarted.post(
                "/api/demo/events", json={"scenario": "leader_changed"}
            ).status_code
            == 202
        )
        assert restarted.get("/api/home").json()["source_status"]["state"] == "ready"


def test_cli_retry_reports_requested_failure_even_after_newer_success(tmp_path, capsys):
    from server.jobs import main

    database = tmp_path / "cli-retry.sqlite3"
    arguments = ["--database", str(database), "--provider", "fixture", "load"]
    failed = arguments + ["--scenario", "failure", "--load-id", "failed-old"]
    assert main(failed) == 1
    capsys.readouterr()
    assert main(arguments + ["--load-id", "success-new"]) == 0
    capsys.readouterr()
    assert main(failed) == 1
    response = json.loads(capsys.readouterr().out)
    assert response["load_id"] == "failed-old"
    assert response["load_status"]["status"] == "failed"
    assert response["load_status"]["error_code"] == "synthetic_load_failure"
    assert response["source_status"]["state"] == "ready"


def test_startup_recovers_interrupted_first_seed_and_publishes_fresh_attempt(tmp_path):
    database = tmp_path / "interrupted-seed.sqlite3"
    service = PlacementService(Store(database))
    interrupted_id = service.begin_load("baseline", load_id="fixture-bootstrap-v1")
    with TestClient(create_app(database, FixtureInterpreter())) as restarted:
        home = restarted.get("/api/home").json()
        assert home["source_status"]["state"] == "ready"
        assert home["source_status"]["load_id"] != interrupted_id
        receipt = service.load_status(interrupted_id)
        assert receipt["status"] == "failed"
        assert receipt["error_code"] == "load_interrupted"
        assert receipt["completed_at"] is not None


def test_cli_success_retry_is_success_even_when_latest_attempt_failed(tmp_path, capsys):
    from server.jobs import main

    arguments = ["--database", str(tmp_path / "success-retry.sqlite3"), "load"]
    successful = arguments + ["--load-id", "success-old"]
    assert main(successful) == 0
    capsys.readouterr()
    assert main(arguments + ["--scenario", "failure", "--load-id", "failure-new"]) == 1
    capsys.readouterr()
    assert main(successful) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["load_status"]["status"] == "succeeded"
    assert response["load_id"] == "success-old"
    assert response["source_status"]["state"] == "stale"
