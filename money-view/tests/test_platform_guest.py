"""Local guest ownership, fixed expiry, save flow and ledger currency provenance."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from server.platform import common as common_module
from server.platform import identity as identity_module
from server.platform import ledger
from server.platform.common import PlatformError, active_context, assert_active_context
from server.platform.identity import COOKIE
from server.platform.identity_contracts import GuestClaim
from test_platform_identity import BASE, app, login  # noqa: F401


@pytest.fixture
def guest_app(app):  # noqa: F811 - imported shared identity fixture
    with app.state.store.connection(write=True) as db:
        db.executescript(ledger.SCHEMA)
    app.include_router(ledger.router)
    app.state.identity.register_data_domain(
        "ledger",
        export=ledger.export_data,
        clear=ledger.clear_data,
        usage=ledger.usage_data,
    )
    return app


def start(client, *, locale="en", mode="empty"):
    return client.post(f"{BASE}/session/guest", json={"locale": locale, "mode": mode})


def add_account(client, currency, *, opening="0"):
    response = client.post(
        f"{BASE}/accounts",
        json={
            "name": f"{currency} account",
            "kind": "checking",
            "currency": currency,
            "opening_balance": opening,
            "idempotency_key": f"account-{currency}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_guests_are_isolated_without_invented_personal_or_money_facts(guest_app):
    with TestClient(guest_app) as first, TestClient(guest_app) as second:
        response = start(first, locale="es-419")
        a, b = response.json(), start(second).json()
        assert a["user"]["id"] != b["user"]["id"]
        assert a["household"]["id"] != b["household"]["id"]
        assert a["user"]["preferred_name"] is None
        assert a["household"]["country"] is None
        assert a["preferences"]["locale"] == "es-419"
        assert a["currency_context"] == {
            "currency": None,
            "source": "unknown",
            "account_id": None,
        }
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert first.get(f"{BASE}/accounts").json()["items"] == []
        account = add_account(first, "JPY", opening="123")
        assert second.get(f"{BASE}/accounts").json()["items"] == []
        assert (
            second.get(
                f"{BASE}/session", params={"account_id": account["id"]}
            ).status_code
            == 404
        )
        assert login(second, a["user"]["id"], password="anything").status_code == 401


def test_active_guest_entry_reuses_fixed_workspace_session_and_choices(guest_app):
    with TestClient(guest_app) as browser:
        before = start(browser).json()
        token = browser.cookies.get(COOKIE)
        after = start(browser, locale="es-419", mode="demo").json()
        assert after == before
        assert browser.cookies.get(COOKIE) == token
        assert (
            datetime.fromisoformat(before["guest"]["expires_at"])
            - datetime.fromisoformat(before["session"]["created_at"])
            == identity_module.GUEST_AGE
        )
        guest_app.state.identity.initialize()
        assert browser.get(f"{BASE}/session").json() == before


def test_expired_guest_cannot_read_claim_or_reuse_and_new_entry_is_isolated(
    guest_app, monkeypatch
):
    with TestClient(guest_app) as browser:
        before = start(browser).json()
        future = datetime.fromisoformat(before["guest"]["expires_at"]) + timedelta(
            seconds=1
        )
        monkeypatch.setattr(identity_module, "now", lambda: future)
        assert browser.get(f"{BASE}/session").status_code == 401
        assert (
            browser.post(
                f"{BASE}/session/claim",
                json={"display_name": "Saved", "password": "Saved-password-2026!"},
            ).status_code
            == 401
        )
        after = start(browser).json()
        assert after["user"]["id"] != before["user"]["id"]
        assert after["household"]["id"] != before["household"]["id"]


def test_claim_preserves_records_and_rotates_into_real_local_credentials(guest_app):
    with TestClient(guest_app) as browser:
        before = start(browser).json()
        account = add_account(browser, "KWD", opening="12.345")
        token = browser.cookies.get(COOKIE)
        response = browser.post(
            f"{BASE}/session/claim",
            json={"display_name": "My local profile", "password": "Saved-password-2026!"},
        )
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["user"]["id"] == before["user"]["id"]
        assert saved["household"]["id"] == before["household"]["id"]
        assert saved["guest"] == {
            "is_guest": False,
            "expires_at": None,
            "mode": None,
            "can_claim": False,
            "local_only": True,
        }
        assert browser.cookies.get(COOKIE) != token
        assert browser.get(f"{BASE}/accounts/{account['id']}").status_code == 200
        browser.post(f"{BASE}/session/logout")
        assert (
            login(browser, saved["user"]["id"], "Saved-password-2026!").status_code == 200
        )
        assert start(browser).status_code == 409
        with TestClient(guest_app) as old:
            old.cookies.set(COOKIE, token)
            assert old.get(f"{BASE}/session").status_code == 401


def test_display_currency_uses_stable_active_account_selection_and_never_converts(
    guest_app,
):
    with TestClient(guest_app) as browser:
        start(browser)
        jpy = add_account(browser, "JPY", opening="321")
        kwd = add_account(browser, "KWD", opening="4.567")
        assert browser.get(f"{BASE}/session").json()["currency_context"] == {
            "currency": "JPY",
            "source": "default_account",
            "account_id": jpy["id"],
        }
        assert browser.get(f"{BASE}/session", params={"account_id": kwd["id"]}).json()[
            "currency_context"
        ] == {"currency": "KWD", "source": "selected_account", "account_id": kwd["id"]}
        browser.patch(f"{BASE}/household", json={"currency_override": "EUR"})
        assert browser.get(f"{BASE}/session", params={"account_id": kwd["id"]}).json()[
            "currency_context"
        ] == {"currency": "EUR", "source": "explicit_override", "account_id": kwd["id"]}
        assert browser.get(f"{BASE}/accounts/{jpy['id']}").json()["currency"] == "JPY"
        assert browser.get(f"{BASE}/accounts/{kwd['id']}").json()["currency"] == "KWD"
        browser.patch(f"{BASE}/household", json={"currency_override": None})
        assert browser.delete(f"{BASE}/accounts/{jpy['id']}").status_code == 200
        assert (
            browser.get(f"{BASE}/session", params={"account_id": jpy["id"]}).status_code
            == 404
        )
        assert (
            browser.get(f"{BASE}/session").json()["currency_context"]["account_id"]
            == kwd["id"]
        )


def test_guest_admission_capacity_origin_and_seed_failure_are_atomic(
    guest_app, monkeypatch
):
    with TestClient(guest_app) as browser:
        assert (
            browser.post(
                f"{BASE}/session/guest",
                json={"locale": "en", "mode": "empty"},
                headers={"origin": "https://foreign.invalid"},
            ).status_code
            == 403
        )
        assert start(browser, mode="demo").status_code == 503

        def failed_seed(db, context):
            raise PlatformError("seed_failed", 503)

        guest_app.state.identity.register_guest_seed(failed_seed)
        assert start(browser, mode="demo").status_code == 503
        with guest_app.state.store.connection() as db:
            assert (
                db.execute("SELECT COUNT(*) FROM p_guest_workspaces").fetchone()[0] == 0
            )
            assert (
                db.execute("SELECT COUNT(*) FROM p_users WHERE fixture=0").fetchone()[0]
                == 0
            )
        monkeypatch.setattr(identity_module, "MAX_GUEST_WORKSPACES", 0)
        assert start(browser).status_code == 429


def test_guest_claim_obeys_captured_role_and_household_generation(guest_app):
    from starlette.requests import Request
    from starlette.responses import Response

    with TestClient(guest_app) as browser:
        initial = start(browser).json()
        with guest_app.state.store.connection() as db:
            captured = active_context(
                db,
                user_id=initial["user"]["id"],
                household_id=initial["household"]["id"],
                session_id=initial["session"]["id"],
            )
        assert (
            browser.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 200
        )
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "http",
                "path": "/",
                "headers": [],
            }
        )
        with pytest.raises(PlatformError, match="household_data_changed"):
            guest_app.state.identity.claim_guest(
                request,
                Response(),
                captured,
                GuestClaim(display_name="Saved", password="Saved-password-2026!"),
            )
        with guest_app.state.store.connection(write=True) as db:
            current = active_context(
                db,
                user_id=captured.user_id,
                household_id=captured.household_id,
                session_id=captured.session_id,
            )
            db.execute(
                "UPDATE p_memberships SET role='viewer' WHERE user_id=?",
                (captured.user_id,),
            )
            with pytest.raises(PlatformError, match="household_access_changed"):
                assert_active_context(db, current)
        assert (
            browser.post(
                f"{BASE}/session/claim",
                json={"display_name": "Saved", "password": "Saved-password-2026!"},
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"locale": "en"},
        {"locale": "fr", "mode": "empty"},
        {"locale": "en", "mode": "empty", "user_id": "user-demo"},
        {"locale": "en", "mode": "empty", "expires_at": "2099-01-01"},
    ],
)
def test_guest_creation_rejects_unowned_identity_or_expiry_input(guest_app, payload):
    with TestClient(guest_app) as browser:
        assert browser.post(f"{BASE}/session/guest", json=payload).status_code == 422
        with guest_app.state.store.connection() as db:
            assert (
                db.execute("SELECT COUNT(*) FROM p_guest_workspaces").fetchone()[0] == 0
            )


def test_claimed_account_outlives_original_guest_expiry(guest_app, monkeypatch):
    with TestClient(guest_app) as browser:
        guest = start(browser).json()
        assert (
            browser.post(
                f"{BASE}/session/claim",
                json={
                    "display_name": "Saved local workspace",
                    "password": "Saved-password-2026!",
                },
            ).status_code
            == 200
        )
        later = datetime.fromisoformat(guest["guest"]["expires_at"]) + timedelta(
            seconds=1
        )
        monkeypatch.setattr(identity_module, "now", lambda: later)
        monkeypatch.setattr(common_module, "now", lambda: later)
        response = browser.get(f"{BASE}/session")
        assert response.status_code == 200
        assert response.json()["guest"]["is_guest"] is False


def test_guest_expiry_fences_private_write_after_context_was_captured(
    guest_app, monkeypatch
):
    from server.platform.identity_contracts import FeedbackWrite
    from server.platform.settings import create_feedback

    with TestClient(guest_app) as browser:
        guest = start(browser).json()
        with guest_app.state.store.connection() as db:
            captured = active_context(
                db,
                user_id=guest["user"]["id"],
                household_id=guest["household"]["id"],
                session_id=guest["session"]["id"],
            )
        later = datetime.fromisoformat(guest["guest"]["expires_at"])
        monkeypatch.setattr(common_module, "now", lambda: later)
        with pytest.raises(PlatformError, match="authentication_required"):
            create_feedback(
                FeedbackWrite(kind="general", message="Expired private text"),
                captured,
                guest_app.state.identity,
            )
        with guest_app.state.store.connection() as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM p_local_feedback WHERE user_id=?",
                    (captured.user_id,),
                ).fetchone()[0]
                == 0
            )


def test_reset_clears_guest_currency_without_reseeding_or_extending_expiry(guest_app):
    with TestClient(guest_app) as browser:
        guest = start(browser).json()
        add_account(browser, "KWD", opening="4.567")
        browser.patch(
            f"{BASE}/household", json={"country": "JP", "currency_override": "EUR"}
        )
        assert (
            browser.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 200
        )
        after = browser.get(f"{BASE}/session").json()
        assert after["guest"] == guest["guest"]
        assert after["household"]["country"] is None
        assert after["currency_context"] == {
            "currency": None,
            "source": "unknown",
            "account_id": None,
        }
        assert browser.get(f"{BASE}/accounts").json()["items"] == []
        assert start(browser).json()["currency_context"]["source"] == "unknown"


def test_demo_entry_seeds_only_independent_owned_records_and_reset_stays_empty(guest_app):
    from server.platform.guest_demo import seed_guest_ledger

    guest_app.state.identity.register_guest_seed(seed_guest_ledger)
    with TestClient(guest_app) as first, TestClient(guest_app) as second:
        a, b = start(first, mode="demo").json(), start(second, mode="demo").json()
        a_accounts = first.get(f"{BASE}/accounts").json()["items"]
        b_accounts = second.get(f"{BASE}/accounts").json()["items"]
        assert 0 < len(a_accounts) <= 5
        assert len(a_accounts) == len(b_accounts)
        assert {item["id"] for item in a_accounts}.isdisjoint(
            item["id"] for item in b_accounts
        )
        source_account = next(
            item
            for item in a_accounts
            if item["id"] == a["currency_context"]["account_id"]
        )
        assert a["currency_context"]["currency"] == source_account["currency"]
        assert source_account["kind"] == "checking"
        assert a["currency_context"]["source"] == "default_account"
        with guest_app.state.store.connection() as db:
            for guest in (a, b):
                home_id = guest["household"]["id"]
                count = db.execute(
                    "SELECT COUNT(*) FROM p_transactions WHERE household_id=? AND source_kind='synthetic'",
                    (home_id,),
                ).fetchone()[0]
                assert 0 < count <= 200
                assert (
                    db.execute(
                        "SELECT COUNT(*) FROM p_accounts WHERE household_id=? AND owner_id<>?",
                        (home_id, guest["user"]["id"]),
                    ).fetchone()[0]
                    == 0
                )
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM p_transactions WHERE household_id='household-demo'"
                ).fetchone()[0]
                == 0
            )
        assert start(first, mode="demo").json() == a
        assert (
            first.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 200
        )
        guest_app.state.identity.initialize()
        assert start(first, mode="demo").json()["currency_context"]["source"] == "unknown"
        assert first.get(f"{BASE}/accounts").json()["items"] == []
        assert len(second.get(f"{BASE}/accounts").json()["items"]) == len(b_accounts)


@pytest.mark.parametrize("entry", ["registered", "guest"])
def test_explicit_country_clear_persists_unknown_and_settings_preserves_session_metadata(
    guest_app, entry
):
    with TestClient(guest_app) as browser:
        initial = (
            login(browser).json() if entry == "registered" else start(browser).json()
        )
        assert (
            browser.patch(f"{BASE}/household", json={"country": "JP"}).status_code == 200
        )
        assert (
            browser.patch(f"{BASE}/household", json={"name": "Kept country"}).json()[
                "country"
            ]
            == "JP"
        )
        cleared = browser.patch(f"{BASE}/household", json={"country": None})
        assert cleared.status_code == 200
        assert cleared.json()["country"] is None
        assert cleared.json()["effective_currency"] is None
        with guest_app.state.store.connection() as db:
            assert (
                db.execute(
                    "SELECT country FROM p_households WHERE id=?",
                    (initial["household"]["id"],),
                ).fetchone()[0]
                == ""
            )
        session = browser.get(f"{BASE}/session").json()
        settings = browser.get(f"{BASE}/settings").json()
        assert session["currency_context"] == {
            "currency": None,
            "source": "unknown",
            "account_id": None,
        }
        assert settings["guest"] == session["guest"]
        assert settings["currency_context"] == session["currency_context"]
        assert settings["household"]["country"] is None
        add_account(browser, "KWD")
        assert (
            browser.get(f"{BASE}/session").json()["currency_context"]["source"]
            == "default_account"
        )
        browser.patch(
            f"{BASE}/household", json={"country": "JP", "currency_override": "EUR"}
        )
        override = browser.patch(f"{BASE}/household", json={"country": None}).json()
        assert override["effective_currency"] == "EUR"
        assert (
            browser.get(f"{BASE}/session").json()["currency_context"]["source"]
            == "explicit_override"
        )
        assert browser.patch(f"{BASE}/household", json={"name": None}).status_code == 422


def test_session_generation_comes_from_lifecycle_reset_and_survives_claim(guest_app):
    with TestClient(guest_app) as browser:
        started = start(browser).json()
        assert started["data_generation"] == 0
        for expected in (1, 2):
            assert (
                browser.post(
                    f"{BASE}/settings/data/reset",
                    json={"confirmation": "RESET THIS HOUSEHOLD"},
                ).status_code
                == 200
            )
            session = browser.get(f"{BASE}/session").json()
            with guest_app.state.store.connection() as db:
                canonical = active_context(
                    db,
                    user_id=session["user"]["id"],
                    household_id=session["household"]["id"],
                    session_id=session["session"]["id"],
                )
            assert session["data_generation"] == canonical.data_generation == expected
        claimed = browser.post(
            f"{BASE}/session/claim",
            json={"display_name": "Saved workspace", "password": "Saved-password-2026!"},
        ).json()
        assert claimed["data_generation"] == session["data_generation"]
        switched = browser.post(
            f"{BASE}/households/switch", json={"household_id": claimed["household"]["id"]}
        ).json()
        assert switched["data_generation"] == claimed["data_generation"]
        browser.post(f"{BASE}/session/logout")
        assert (
            login(browser, claimed["user"]["id"], "Saved-password-2026!").json()[
                "data_generation"
            ]
            == claimed["data_generation"]
        )
