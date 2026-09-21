"""The real composition must agree with the individually tested domain owners."""

import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.platform.identity import DEMO_PASSWORD


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "composed.sqlite3", FixtureInterpreter())


def login(client, user="user-demo"):
    response = client.post(
        "/api/platform/session/login",
        json={
            "user_id": user,
            "password": DEMO_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_all_domains_are_reachable_in_real_composition(app):
    with TestClient(app) as client:
        session = login(client)
        assert session["preferences"]["locale"] == "es-419"
        assert session["preferences"]["appearance"] == "light"
        assert session["household"]["effective_currency"] == "DOP"
        assert (
            session["household"]["effective_currency"] in session["supported_currencies"]
        )
        endpoints = [
            "/overview?currency=DOP",
            "/accounts",
            "/transactions?limit=25",
            "/spending?currency=DOP",
            "/budgets",
            "/bills",
            "/goals",
            "/scenarios",
            "/scenarios/templates",
            "/investing/portfolio",
            "/credit",
            "/tax",
            "/estate",
            "/appointments",
            "/membership",
            "/employer",
            "/settings",
            "/settings/usage",
            "/settings/data/export",
            "/assistant/actions",
            "/assistant/conversations",
            "/assistant/saved",
            "/runtime/usage",
        ]
        for endpoint in endpoints:
            response = client.get(f"/api/platform{endpoint}")
            assert response.status_code == 200, (endpoint, response.text)
        ledger = client.get("/api/platform/transactions?limit=25").json()
        assert ledger["total"] >= 12000
        assert len(ledger["items"]) == 25
        with app.state.store.connection() as db:
            membership_columns = {
                row[1] for row in db.execute("PRAGMA table_info(p_memberships)")
            }
        assert membership_columns == {"household_id", "user_id", "role"}


def test_household_reset_preserves_credentials_and_other_household(app):
    with TestClient(app) as client:
        login(client, "user-other")
        other_before = client.get("/api/platform/accounts").json()
        login(client)
        before_members = client.get("/api/platform/household/members").json()
        domains = set(app.state.identity.data_domains)
        assert domains == {
            "runtime",
            "assistant",
            "services",
            "planning",
            "investing",
            "ledger",
            "deposits",
        }
        exported = client.get("/api/platform/settings/data/export")
        assert exported.status_code == 200
        assert set(exported.json()["domains"]) == domains
        assert "password_hash" not in exported.text
        assert "token_hash" not in exported.text
        assert "household-other" not in exported.text
        reset = client.post(
            "/api/platform/settings/data/reset",
            json={"confirmation": "RESET THIS HOUSEHOLD"},
        )
        assert reset.status_code == 200, reset.text
        assert client.get("/api/platform/session").status_code == 200
        assert client.get("/api/platform/household/members").json() == before_members
        assert client.get("/api/platform/accounts").json()["total"] == 0
        assert client.get("/api/home").json()["saved"] == []
        login(client, "user-other")
        assert client.get("/api/platform/accounts").json() == other_before


def test_legacy_deposit_http_has_same_identity_and_write_boundary(app):
    with TestClient(app) as client:
        assert client.get("/api/home").status_code == 401
        login(client)
        inputs = client.get("/api/home").json()["examples"][0]["inputs"]
        proposal = client.post("/api/confirmations", json={"inputs": inputs})
        assert proposal.status_code == 200
        result = client.post(
            f"/api/confirmations/{proposal.json()['id']}/compute", json={"inputs": inputs}
        )
        assert result.status_code == 200
        decision = client.post(f"/api/comparisons/{result.json()['id']}/save").json()
        login(client, "user-other")
        assert client.get(f"/api/decisions/{decision['id']}").status_code == 404
        assert client.get("/api/home").json()["saved"] == []
        login(client, "user-viewer")
        assert client.get(f"/api/decisions/{decision['id']}").status_code == 200
        assert (
            client.post("/api/confirmations", json={"inputs": inputs}).status_code == 403
        )
        assert (
            client.post(
                "/api/demo/events", json={"scenario": "leader_changed"}
            ).status_code
            == 403
        )


def test_loopback_host_and_same_origin_are_enforced(app):
    with TestClient(app) as client:
        response = client.get(
            "/api/platform/demo/personas", headers={"Host": "untrusted.example"}
        )
        assert response.status_code == 400
        response = client.post(
            "/api/platform/session/login",
            json={
                "user_id": "user-demo",
                "password": DEMO_PASSWORD,
            },
            headers={"Origin": "https://untrusted.example"},
        )
        assert response.status_code == 403


def test_runtime_guards_cover_legacy_and_platform_routes(app):
    with TestClient(app) as client:
        login(client)
        for path in ("/api/interpret", "/api/platform/assistant/ask"):
            response = client.post(path, content=b"x" * 65_537)
            assert response.status_code == 413
            assert response.json()["code"] == "request_body_too_large"
            assert len(response.headers["x-request-id"]) == 32
        summary = client.get("/api/notices/summary?limit=20")
        assert summary.status_code == 200
        assert summary.json()["items"] == []
        assert summary.json()["unread_count"] == 0
        event = client.post(
            "/api/demo/events",
            json={
                "scenario": "same_winner",
                "idempotency_key": "composed-event",
            },
        )
        assert event.status_code == 202
        assert (
            client.post(
                "/api/demo/events",
                json={
                    "scenario": "same_winner",
                    "idempotency_key": "composed-event",
                },
            ).json()
            == event.json()
        )
        assert (
            client.post(
                "/api/demo/events",
                json={
                    "scenario": "failure",
                    "idempotency_key": "composed-event",
                },
            ).status_code
            == 409
        )
        endpoint = f"/api/platform/jobs/{event.json()['job_id']}"
        assert client.get(endpoint).status_code == 200
        login(client, "user-other")
        assert client.get(endpoint).status_code == 404
