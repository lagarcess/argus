"""Real local identity/session and household privacy boundary checks."""

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from server.platform import identity as identity_module
from server.platform.common import (
    CURRENCY_DIGITS,
    Context,
    PlatformError,
    active_context,
    assert_active_context,
    now,
)
from server.platform.identity import COOKIE, DEMO_PASSWORD, Identity, router, token_hash
from server.platform.identity_contracts import FeedbackWrite
from server.platform.settings import create_feedback
from server.store import Store

BASE = "/api/platform"


@pytest.fixture
def app(tmp_path):
    application = FastAPI()
    application.state.store = Store(tmp_path / "identity.sqlite3")
    application.state.identity = Identity(application.state.store)
    application.state.identity.initialize()
    application.include_router(router)

    @application.exception_handler(PlatformError)
    async def platform_error(_, exc):
        return JSONResponse({"code": exc.code}, status_code=exc.status)

    return application


def login(client, user_id="user-demo", password=DEMO_PASSWORD, **extra):
    return client.post(
        f"{BASE}/session/login", json={"user_id": user_id, "password": password, **extra}
    )


@pytest.fixture
def client(app):
    with TestClient(app) as value:
        assert login(value).status_code == 200
        yield value


def test_no_implicit_auth_hashed_credentials_and_logout_stays_out(app):
    with TestClient(app) as browser:
        assert browser.get(f"{BASE}/session").status_code == 401
        assert (
            browser.get(
                f"{BASE}/settings", headers={"X-User-Id": "user-demo"}
            ).status_code
            == 401
        )
        public = browser.get(f"{BASE}/demo/personas").json()
        assert {item["user_id"] for item in public["items"]} == {
            "user-demo",
            "user-partner",
            "user-viewer",
            "user-other",
        }
        assert public["default_password"] == DEMO_PASSWORD
        response = login(browser)
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        raw_token = browser.cookies.get(COOKIE)
        with app.state.store.connection() as db:
            user = db.execute(
                "SELECT password_hash FROM p_users WHERE id='user-demo'"
            ).fetchone()[0]
            saved = db.execute("SELECT token_hash FROM p_sessions").fetchone()[0]
            assert DEMO_PASSWORD not in user
            assert user.startswith("scrypt$")
            assert saved == token_hash(raw_token) and saved != raw_token
        assert browser.post(f"{BASE}/session/logout").json() == {"logged_out": True}
        assert browser.post(f"{BASE}/session/logout").status_code == 200
        browser.cookies.set(COOKIE, raw_token)
        assert browser.get(f"{BASE}/session").status_code == 401
        app.state.identity.initialize()
        assert browser.get(f"{BASE}/session").status_code == 401


@pytest.mark.parametrize("change", ["expired", "revoked", "removed_membership"])
def test_session_authority_is_rechecked_on_every_request(app, client, change):
    snapshot = client.get(f"{BASE}/session").json()
    with app.state.store.connection(write=True) as db:
        if change == "expired":
            db.execute(
                "UPDATE p_sessions SET expires_at=? WHERE id=?",
                ((now() - timedelta(seconds=1)).isoformat(), snapshot["session"]["id"]),
            )
        elif change == "revoked":
            db.execute(
                "UPDATE p_sessions SET revoked_at=? WHERE id=?",
                (now().isoformat(), snapshot["session"]["id"]),
            )
        else:
            db.execute("DELETE FROM p_memberships WHERE user_id='user-demo'")
    assert client.get(f"{BASE}/settings").status_code == 401


def test_session_reads_throttle_activity_writes_without_caching_authority(
    app, client, monkeypatch
):
    snapshot = client.get(f"{BASE}/session").json()
    created = datetime.fromisoformat(snapshot["session"]["created_at"])
    current_time = created
    monkeypatch.setattr(identity_module, "now", lambda: current_time)
    connection = app.state.store.connection
    writes = []

    @contextmanager
    def observed_connection(*, write=False):
        writes.append(write)
        with connection(write=write) as db:
            yield db

    monkeypatch.setattr(app.state.store, "connection", observed_connection)

    def last_seen():
        with connection() as db:
            return db.execute(
                "SELECT last_seen_at FROM p_sessions WHERE id=?",
                (snapshot["session"]["id"],),
            ).fetchone()[0]

    for delta in (timedelta(), timedelta(minutes=1), timedelta(minutes=4, seconds=59)):
        current_time = created + delta
        assert client.get(f"{BASE}/session").status_code == 200
        assert client.get(f"{BASE}/settings").status_code == 200
    assert not any(writes)
    assert last_seen() == created.isoformat()

    current_time = created + identity_module.SESSION_ACTIVITY_INTERVAL
    writes.clear()
    assert client.get(f"{BASE}/session").status_code == 200
    assert sum(writes) == 1
    assert last_seen() == current_time.isoformat()
    writes.clear()
    for _ in range(3):
        assert client.get(f"{BASE}/session").status_code == 200
    assert not any(writes)

    # A persisted role change takes effect inside the activity-throttle window.
    with connection(write=True) as db:
        db.execute("UPDATE p_memberships SET role='viewer' WHERE user_id='user-demo'")
    changed = client.get(f"{BASE}/session")
    assert changed.json()["household"]["role"] == "viewer"
    assert not any(writes)

    with connection(write=True) as db:
        db.execute(
            "UPDATE p_sessions SET revoked_at=? WHERE id=?",
            (current_time.isoformat(), snapshot["session"]["id"]),
        )
    writes.clear()
    current_time += identity_module.SESSION_ACTIVITY_INTERVAL
    assert client.get(f"{BASE}/session").status_code == 401
    assert not any(writes)


def test_overdue_activity_touch_preserves_a_concurrent_newer_timestamp(
    app, client, monkeypatch
):
    timestamp = now()
    monkeypatch.setattr(identity_module, "now", lambda: timestamp)
    connection = app.state.store.connection
    with connection(write=True) as db:
        db.execute(
            "UPDATE p_sessions SET last_seen_at=?",
            ((timestamp - identity_module.SESSION_ACTIVITY_INTERVAL).isoformat(),),
        )
    newer_timestamp = (timestamp + timedelta(seconds=1)).isoformat()
    touched = False

    @contextmanager
    def concurrent_touch(*, write=False):
        nonlocal touched
        if write and not touched:
            touched = True
            with connection(write=True) as db:
                db.execute("UPDATE p_sessions SET last_seen_at=?", (newer_timestamp,))
        with connection(write=write) as db:
            yield db

    monkeypatch.setattr(app.state.store, "connection", concurrent_touch)
    assert client.get(f"{BASE}/session").status_code == 200
    assert touched
    with connection() as db:
        assert (
            db.execute("SELECT last_seen_at FROM p_sessions").fetchone()[0]
            == newer_timestamp
        )


def test_bad_credentials_cross_origin_and_household_scope(app, client):
    assert login(client, password="wrong").status_code == 401
    assert login(client, household_id="household-other").status_code == 403
    assert (
        client.post(
            f"{BASE}/households/switch", json={"household_id": "household-other"}
        ).status_code
        == 403
    )
    assert client.get(f"{BASE}/households").json()["items"][0]["id"] == "household-demo"
    response = client.patch(
        f"{BASE}/settings/profile",
        json={"display_name": "Injected"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert client.get(f"{BASE}/session").json()["user"]["display_name"] == "Alex Rivera"
    with TestClient(app) as foreign:
        assert login(foreign, "user-other").status_code == 200
        other_id = foreign.get(f"{BASE}/session").json()["session"]["id"]
        assert client.delete(f"{BASE}/settings/sessions/{other_id}").status_code == 404


def test_authorized_household_switch_is_persisted(app, client):
    with app.state.store.connection(write=True) as db:
        db.execute(
            "INSERT INTO p_memberships VALUES ('household-other','user-demo','viewer')"
        )
    switched = client.post(
        f"{BASE}/households/switch", json={"household_id": "household-other"}
    )
    assert switched.status_code == 200
    assert switched.json()["household"]["role"] == "viewer"
    assert client.get(f"{BASE}/session").json()["household"]["id"] == "household-other"
    assert client.patch(f"{BASE}/household", json={"name": "No"}).status_code == 403


def test_profile_preferences_and_currency_have_one_owner(app, client):
    changed = client.patch(
        f"{BASE}/settings/profile",
        json={
            "display_name": "  Maria Finance  ",
            "preferred_name": "  Mari  ",
            "avatar_color": "plum",
        },
    )
    assert changed.json()["display_name"] == "Maria Finance"
    assert changed.json()["preferred_name"] == "Mari"
    prefs = {
        "locale": "en",
        "timezone": "Pacific/Auckland",
        "appearance": "dark",
        "sidebar_compact": True,
        "notifications": {"bills": False},
    }
    result = client.patch(f"{BASE}/settings/preferences", json=prefs).json()
    assert result["locale"] == "en"
    assert result["notifications"] == {
        "bills": False,
        "account_changes": True,
        "product_updates": False,
    }
    home = client.patch(f"{BASE}/household", json={"country": "NZ"}).json()
    assert home["effective_currency"] == "NZD"
    assert (
        client.patch(f"{BASE}/household", json={"currency_override": "USD"}).json()[
            "effective_currency"
        ]
        == "USD"
    )
    assert (
        client.patch(f"{BASE}/household", json={"currency_override": None}).json()[
            "effective_currency"
        ]
        == "NZD"
    )
    assert (
        client.patch(f"{BASE}/settings/profile", json={"preferred_name": "   "}).json()[
            "preferred_name"
        ]
        is None
    )
    app.state.identity = Identity(app.state.store)
    app.state.identity.initialize()
    snapshot = client.get(f"{BASE}/settings").json()
    assert snapshot["preferences"] == result
    assert snapshot["profile"]["display_name"] == "Maria Finance"
    assert snapshot["household"]["effective_currency"] == "NZD"
    with TestClient(app) as partner:
        login(partner, "user-partner")
        snapshot = partner.get(f"{BASE}/session").json()
        assert snapshot["household"]["effective_currency"] == "NZD"
        assert snapshot["preferences"]["locale"] == "es-419"


@pytest.mark.parametrize(
    "path,body",
    [
        ("profile", {"display_name": " "}),
        ("profile", {"display_name": "x" * 81}),
        ("profile", {"preferred_name": "x" * 41}),
        ("profile", {"avatar_color": "fake"}),
        ("profile", {"user_id": "user-other"}),
        ("preferences", {"locale": "fr"}),
        ("preferences", {"timezone": "Mars/Olympus"}),
        ("preferences", {"notifications": {"email": True}}),
    ],
)
def test_settings_validate_boundary(client, path, body):
    assert client.patch(f"{BASE}/settings/{path}", json=body).status_code == 422


def test_viewer_personal_settings_work_shared_writes_fail(app):
    with TestClient(app) as viewer:
        assert login(viewer, "user-viewer").status_code == 200
        assert (
            viewer.patch(
                f"{BASE}/settings/profile", json={"preferred_name": "T"}
            ).status_code
            == 200
        )
        assert (
            viewer.patch(
                f"{BASE}/settings/preferences", json={"locale": "en"}
            ).status_code
            == 200
        )
        assert (
            viewer.patch(f"{BASE}/household", json={"country": "US"}).status_code == 403
        )
        assert (
            viewer.post(
                f"{BASE}/household/members",
                json={"display_name": "New", "password": DEMO_PASSWORD},
            ).status_code
            == 403
        )
        assert (
            viewer.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 403
        )
        assert (
            viewer.post(
                f"{BASE}/settings/memories",
                json={"content": "My confirmed preference", "confirmed": True},
            ).status_code
            == 201
        )


def test_membership_roles_local_credentials_and_last_owner(app, client):
    assert (
        client.patch(
            f"{BASE}/household/members/user-demo", json={"role": "editor"}
        ).status_code
        == 409
    )
    assert client.delete(f"{BASE}/household/members/user-demo").status_code == 409
    added = client.post(
        f"{BASE}/household/members",
        json={
            "display_name": "Local member",
            "password": DEMO_PASSWORD,
            "role": "viewer",
        },
    )
    assert added.status_code == 201
    new_id = added.json()["user_id"]
    with TestClient(app) as member:
        assert login(member, new_id).status_code == 200
        assert (
            member.patch(f"{BASE}/household", json={"name": "Denied"}).status_code == 403
        )
        assert (
            client.patch(
                f"{BASE}/household/members/{new_id}", json={"role": "owner"}
            ).status_code
            == 200
        )
        assert (
            member.patch(f"{BASE}/household", json={"name": "Co-owned"}).status_code
            == 200
        )
        assert client.delete(f"{BASE}/household/members/{new_id}").status_code == 200
        assert member.get(f"{BASE}/session").status_code == 401


def test_password_change_revokes_all_sessions_and_persists(app, client):
    with TestClient(app) as second:
        login(second)
        assert len(client.get(f"{BASE}/settings/sessions").json()["items"]) == 2
        assert (
            client.post(
                f"{BASE}/settings/password",
                json={"current_password": "wrong", "new_password": "A-new-password!"},
            ).status_code
            == 401
        )
        assert second.get(f"{BASE}/session").status_code == 200
        changed = client.post(
            f"{BASE}/settings/password",
            json={"current_password": DEMO_PASSWORD, "new_password": "A-new-password!"},
        )
        assert changed.json() == {"changed": True, "logged_out": True}
        assert client.get(f"{BASE}/session").status_code == 401
        assert second.get(f"{BASE}/session").status_code == 401
        app.state.identity.initialize()
        assert login(client).status_code == 401
        assert login(client, password="A-new-password!").status_code == 200


def test_revoke_others_is_idempotent_and_preserves_current(app, client):
    with TestClient(app) as second:
        login(second)
        result = client.post(f"{BASE}/settings/sessions/revoke", json={"scope": "others"})
        assert result.json() == {"revoked": 1, "logged_out": False}
        assert second.get(f"{BASE}/session").status_code == 401
        assert client.get(f"{BASE}/session").status_code == 200
        assert (
            client.post(
                f"{BASE}/settings/sessions/revoke", json={"scope": "others"}
            ).json()["revoked"]
            == 0
        )
        assert (
            client.post(f"{BASE}/settings/sessions/revoke", json={"scope": "all"}).json()[
                "logged_out"
            ]
            is True
        )
        assert client.get(f"{BASE}/session").status_code == 401


def test_confirmed_memories_private_persisted_enabled_and_reset(app, client):
    command = {"content": "Use monthly numbers", "confirmed": True}
    assert (
        client.post(
            f"{BASE}/settings/memories", json={"content": command["content"]}
        ).status_code
        == 422
    )
    memory = client.post(f"{BASE}/settings/memories", json=command).json()
    context = Context("user-demo", "household-demo", "owner", "unused")
    assert app.state.identity.active_memories(context) == []
    client.patch(f"{BASE}/settings/memories", json={"enabled": True})
    assert app.state.identity.active_memories(context)[0]["content"] == command["content"]
    with TestClient(app) as partner:
        login(partner, "user-partner")
        assert partner.get(f"{BASE}/settings/memories").json()["items"] == []
        assert (
            partner.patch(
                f"{BASE}/settings/memories/{memory['id']}", json=command
            ).status_code
            == 404
        )
        assert (
            partner.delete(f"{BASE}/settings/memories/{memory['id']}").status_code == 404
        )
    updated = client.patch(
        f"{BASE}/settings/memories/{memory['id']}",
        json={"content": "Use weekly numbers", "confirmed": True},
    ).json()
    assert updated["content"] == "Use weekly numbers"
    assert client.get(f"{BASE}/settings/memories/export").json()["items"] == [updated]
    client.patch(f"{BASE}/settings/memories", json={"enabled": False})
    assert app.state.identity.active_memories(context) == []
    app.state.identity.initialize()
    assert len(client.get(f"{BASE}/settings/memories").json()["items"]) == 1
    assert (
        client.post(
            f"{BASE}/settings/memories/reset", json={"confirmation": "no"}
        ).status_code
        == 422
    )
    for expected in (1, 0):
        assert (
            client.post(
                f"{BASE}/settings/memories/reset",
                json={"confirmation": "DELETE MY MEMORIES"},
            ).json()["deleted"]
            == expected
        )


def register_test_domain(app, *, fail_clear=False):
    with app.state.store.connection(write=True) as db:
        db.execute(
            "CREATE TABLE domain_fixture (household_id TEXT PRIMARY KEY,value TEXT)"
        )
        db.executemany(
            "INSERT INTO domain_fixture VALUES (?,?)",
            [
                ("household-demo", "our-record"),
                ("household-other", "private-other-record"),
            ],
        )

    def export(db, context):
        return [
            dict(row)
            for row in db.execute(
                "SELECT value FROM domain_fixture WHERE household_id=?",
                (context.household_id,),
            )
        ]

    def clear(db, context):
        db.execute(
            "DELETE FROM domain_fixture WHERE household_id=?", (context.household_id,)
        )
        if fail_clear:
            raise PlatformError("failed_domain", 409)

    def usage(db, context):
        return {
            "records": db.execute(
                "SELECT COUNT(*) FROM domain_fixture WHERE household_id=?",
                (context.household_id,),
            ).fetchone()[0]
        }

    app.state.identity.register_data_domain(
        "fixture", export=export, clear=clear, usage=usage
    )


def test_real_usage_export_and_reset_scoped_and_idempotent(app, client):
    register_test_domain(app)
    client.post(
        f"{BASE}/settings/memories",
        json={"content": "Local preference", "confirmed": True},
    )
    receipt = client.post(
        f"{BASE}/settings/feedback", json={"kind": "bug", "message": "A local report"}
    )
    assert receipt.status_code == 201 and receipt.json()["status"] == "saved_locally"
    usage = client.get(f"{BASE}/settings/usage").json()
    assert usage["metrics"] == {
        "active_sessions": 1,
        "confirmed_memories": 1,
        "local_feedback": 1,
    }
    assert usage["domains"] == {"fixture": {"records": 1}}
    exported = client.get(f"{BASE}/settings/data/export")
    assert exported.headers["content-disposition"].startswith("attachment")
    text = json.dumps(exported.json())
    assert "our-record" in text and "private-other-record" not in text
    assert (
        "password_hash" not in text
        and "token_hash" not in text
        and DEMO_PASSWORD not in text
    )
    assert (
        client.post(
            f"{BASE}/settings/data/reset", json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    for _ in range(2):
        assert (
            client.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 200
        )
    app.state.identity.initialize()
    assert client.get(f"{BASE}/settings/data/export").json()["domains"]["fixture"] == []
    assert client.get(f"{BASE}/settings/memories").json()["items"] == []
    assert client.get(f"{BASE}/settings/feedback").json()["items"] == []
    with app.state.store.connection() as db:
        assert (
            db.execute("SELECT value FROM domain_fixture").fetchone()[0]
            == "private-other-record"
        )


def test_reset_domain_failure_rolls_back_entire_transaction(app, client):
    register_test_domain(app, fail_clear=True)
    assert (
        client.post(
            f"{BASE}/settings/data/reset", json={"confirmation": "RESET THIS HOUSEHOLD"}
        ).status_code
        == 409
    )
    assert (
        client.get(f"{BASE}/settings/usage").json()["domains"]["fixture"]["records"] == 1
    )


def test_deletion_shared_owner_guard_and_user_tombstone_never_reseed(app, client):
    register_test_domain(app)
    body = {"confirmation": "DELETE MY LOCAL ACCOUNT", "current_password": DEMO_PASSWORD}
    assert (
        client.request("DELETE", f"{BASE}/settings/account", json=body).status_code == 409
    )
    assert (
        client.patch(
            f"{BASE}/household/members/user-partner", json={"role": "owner"}
        ).status_code
        == 200
    )
    deleted = client.request("DELETE", f"{BASE}/settings/account", json=body)
    assert deleted.status_code == 200
    assert deleted.json()["private_households_cleared"] == []
    assert client.get(f"{BASE}/session").status_code == 401
    app.state.identity.initialize()
    assert login(client).status_code == 401
    ids = {
        item["user_id"] for item in client.get(f"{BASE}/demo/personas").json()["items"]
    }
    assert "user-demo" not in ids
    with app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM domain_fixture").fetchone()[0] == 2
        user = db.execute(
            "SELECT password_hash,preferred_name,deleted_at FROM p_users WHERE id='user-demo'"
        ).fetchone()
        assert user[0] == "" and user[1] is None and user[2] is not None


def test_single_member_account_deletion_erases_private_domain_only(app):
    register_test_domain(app)
    with TestClient(app) as single:
        login(single, "user-other")
        result = single.request(
            "DELETE",
            f"{BASE}/settings/account",
            json={
                "confirmation": "DELETE MY LOCAL ACCOUNT",
                "current_password": DEMO_PASSWORD,
            },
        )
        assert result.json()["private_households_cleared"] == ["household-other"]
        with app.state.store.connection() as db:
            assert [
                row[0] for row in db.execute("SELECT household_id FROM domain_fixture")
            ] == ["household-demo"]
        app.state.identity.initialize()
        assert login(single, "user-other").status_code == 401


@pytest.mark.parametrize("has_other_membership", [False, True])
def test_member_removal_disposes_personal_data_without_stranding_account(
    app, client, has_other_membership
):
    register_test_domain(app)
    created = client.post(
        f"{BASE}/household/members",
        json={
            "display_name": "Local member",
            "password": DEMO_PASSWORD,
            "role": "editor",
        },
    ).json()
    user_id = created["user_id"]
    with TestClient(app) as member, TestClient(app) as other_session:
        assert login(member, user_id).status_code == 200
        member.patch(f"{BASE}/settings/profile", json={"preferred_name": "Personal name"})
        member.patch(f"{BASE}/settings/preferences", json={"locale": "en"})
        member.patch(f"{BASE}/settings/memories", json={"enabled": True})
        member.post(
            f"{BASE}/settings/memories",
            json={"content": "Private household memory", "confirmed": True},
        )
        member.post(
            f"{BASE}/settings/feedback",
            json={"kind": "general", "message": "Private household feedback"},
        )
        if has_other_membership:
            with app.state.store.connection(write=True) as db:
                db.execute(
                    "INSERT INTO p_memberships VALUES ('household-other',?,'editor')",
                    (user_id,),
                )
            assert (
                login(other_session, user_id, household_id="household-other").status_code
                == 200
            )
            other_session.post(
                f"{BASE}/settings/memories",
                json={"content": "Retained other memory", "confirmed": True},
            )
            other_session.post(
                f"{BASE}/settings/feedback",
                json={"kind": "general", "message": "Retained other feedback"},
            )

        removed = client.delete(f"{BASE}/household/members/{user_id}")
        assert removed.json() == {
            "removed": True,
            "local_account_deleted": not has_other_membership,
            "personal_household_data_deleted": True,
            "shared_household_data_preserved": True,
        }
        assert member.get(f"{BASE}/session").status_code == 401
        with app.state.store.connection() as db:
            for table in (
                "p_memories",
                "p_memory_settings",
                "p_local_feedback",
                "p_sessions",
            ):
                assert (
                    db.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE user_id=? AND household_id='household-demo'",
                        (user_id,),
                    ).fetchone()[0]
                    == 0
                )
            assert db.execute("SELECT COUNT(*) FROM domain_fixture").fetchone()[0] == 2
            user = db.execute("SELECT * FROM p_users WHERE id=?", (user_id,)).fetchone()
            preferences_count = db.execute(
                "SELECT COUNT(*) FROM p_preferences WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            if has_other_membership:
                assert user["deleted_at"] is None and user["password_hash"]
                assert preferences_count == 1
            else:
                assert user["deleted_at"] is not None and user["password_hash"] == ""
                assert (
                    user["preferred_name"] is None
                    and user["display_name"] == "Deleted local user"
                )
                assert preferences_count == 0

        app.state.identity.initialize()
        if has_other_membership:
            assert other_session.get(f"{BASE}/session").status_code == 200
            assert (
                other_session.get(f"{BASE}/settings/memories").json()["items"][0][
                    "content"
                ]
                == "Retained other memory"
            )
            assert (
                other_session.get(f"{BASE}/settings/feedback").json()["items"][0][
                    "message"
                ]
                == "Retained other feedback"
            )
            assert login(member, user_id).status_code == 200
            assert (
                member.get(f"{BASE}/session").json()["household"]["id"]
                == "household-other"
            )
        else:
            assert login(member, user_id).status_code == 401


def test_new_preferences_start_light_saved_choice_and_currency_owner_persist(
    app, client, monkeypatch
):
    assert client.get(f"{BASE}/session").json()["preferences"]["appearance"] == "light"
    client.patch(f"{BASE}/settings/preferences", json={"appearance": "dark"})
    app.state.identity.initialize()
    assert client.get(f"{BASE}/session").json()["preferences"]["appearance"] == "dark"
    monkeypatch.setitem(CURRENCY_DIGITS, "AUD", 2)
    for endpoint in ("session", "settings"):
        assert client.get(f"{BASE}/{endpoint}").json()["supported_currencies"] == list(
            CURRENCY_DIGITS
        )


@pytest.mark.parametrize("overflow", ["rows", "bytes"])
def test_memory_context_is_bounded_without_silently_omitting_confirmed_records(
    app, client, overflow
):
    stamp = now().isoformat()
    count = identity_module.MAX_MEMORY_CONTEXT_ROWS + 1 if overflow == "rows" else 10
    content = "monthly" if overflow == "rows" else "é" * 2000
    with app.state.store.connection(write=True) as db:
        db.executemany(
            "INSERT INTO p_memories VALUES (?,?,?,?,?,?)",
            [
                (
                    f"memory-cap-{index}",
                    "user-demo",
                    "household-demo",
                    content,
                    stamp,
                    stamp,
                )
                for index in range(count)
            ],
        )
    context = Context("user-demo", "household-demo", "owner", "unused")
    assert app.state.identity.active_memories(context) == []
    client.patch(f"{BASE}/settings/memories", json={"enabled": True})
    with pytest.raises(PlatformError, match="memory_context_too_large") as failure:
        app.state.identity.active_memories(context)
    assert failure.value.status == 413
    assert (
        app.state.identity.active_memories(
            Context("user-partner", "household-demo", "editor", "unused")
        )
        == []
    )
    # Oversized context never removes the user's consented source records.
    with app.state.store.connection() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM p_memories WHERE user_id='user-demo'"
            ).fetchone()[0]
            == count
        )
    if overflow == "rows":
        with app.state.store.connection(write=True) as db:
            db.execute("DELETE FROM p_memories WHERE id=?", (f"memory-cap-{count - 1}",))
        assert (
            len(app.state.identity.active_memories(context))
            == identity_module.MAX_MEMORY_CONTEXT_ROWS
        )


@pytest.mark.parametrize("overflow", ["rows", "bytes"])
def test_household_export_budget_is_shared_across_callbacks_and_never_partial(
    app, client, monkeypatch, overflow
):
    completed = []
    with app.state.store.connection(write=True) as db:
        db.execute(
            "CREATE TABLE export_fixture (id TEXT PRIMARY KEY,household_id TEXT,document TEXT)"
        )
        db.executemany(
            "INSERT INTO export_fixture VALUES (?,?,?)",
            [
                (f"{domain}-{index}", "household-demo", "x" * 2000)
                for domain in ("first", "second")
                for index in range(3)
            ],
        )

    def export_first(db, context):
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT document FROM export_fixture WHERE household_id=? AND id LIKE 'first-%'",
                (context.household_id,),
            )
        ]
        completed.append("first")
        return rows

    def export_second(db, context):
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT document FROM export_fixture WHERE household_id=? AND id LIKE 'second-%'",
                (context.household_id,),
            ).fetchall()
        ]
        completed.append("second")
        return rows

    for name, callback in (("first", export_first), ("second", export_second)):
        app.state.identity.register_data_domain(
            name,
            export=callback,
            clear=lambda _db, _ctx: None,
            usage=lambda _db, _ctx: {},
        )
    if overflow == "rows":
        monkeypatch.setattr(identity_module, "MAX_HOUSEHOLD_EXPORT_ROWS", 10)
    else:
        monkeypatch.setattr(identity_module, "MAX_HOUSEHOLD_EXPORT_BYTES", 10_000)
    response = client.get(f"{BASE}/settings/data/export")
    assert response.status_code == 413
    assert response.json() == {"code": "household_export_too_large"}
    assert completed == ["first"]
    assert "content-disposition" not in response.headers


def test_full_seeded_household_export_fits_budget_and_excludes_credentials(tmp_path):
    from server.app import create_app
    from server.interpreter import FixtureInterpreter

    with TestClient(
        create_app(tmp_path / "full-export.sqlite3", FixtureInterpreter())
    ) as browser:
        assert login(browser).status_code == 200
        response = browser.get(f"{BASE}/settings/data/export")
        assert response.status_code == 200, response.text
        document = response.json()
        assert len(document["domains"]["ledger"]["p_transactions"]) >= 12_000
        assert set(document["domains"]) == set(browser.app.state.identity.data_domains)
        assert document["household_id"] == "household-demo"
        serialized = response.text
        assert "password_hash" not in serialized and "token_hash" not in serialized
        assert DEMO_PASSWORD not in serialized


def captured_context(app, user_id, household_id):
    with app.state.store.connection() as db:
        return active_context(
            db, user_id=user_id, household_id=household_id, session_id="accepted-request"
        )


@pytest.mark.parametrize(
    "change,user_id,household_id,error_code,status",
    [
        ("reset", "user-demo", "household-demo", "household_data_changed", 409),
        ("delete", "user-other", "household-other", "authentication_required", 401),
        ("remove", "user-partner", "household-demo", "authentication_required", 401),
        ("promote", "user-partner", "household-demo", "household_access_changed", 409),
        ("demote", "user-partner", "household-demo", "household_access_changed", 409),
    ],
)
def test_paused_private_write_cannot_survive_lifecycle_change(
    app, client, change, user_id, household_id, error_code, status
):
    captured = captured_context(app, user_id, household_id)
    ready, resume = Event(), Event()
    private_message = f"Private text accepted before {change}"

    def accepted_request():
        ready.set()
        assert resume.wait(5), "lifecycle change did not release paused request"
        return create_feedback(
            FeedbackWrite(kind="general", message=private_message),
            captured,
            app.state.identity,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(accepted_request)
        try:
            assert ready.wait(5)
            if change == "reset":
                response = client.post(
                    f"{BASE}/settings/data/reset",
                    json={"confirmation": "RESET THIS HOUSEHOLD"},
                )
            elif change == "delete":
                with TestClient(app) as other:
                    assert login(other, user_id).status_code == 200
                    response = other.request(
                        "DELETE",
                        f"{BASE}/settings/account",
                        json={
                            "confirmation": "DELETE MY LOCAL ACCOUNT",
                            "current_password": DEMO_PASSWORD,
                        },
                    )
            elif change == "remove":
                response = client.delete(f"{BASE}/household/members/{user_id}")
            else:
                response = client.patch(
                    f"{BASE}/household/members/{user_id}",
                    json={"role": "owner" if change == "promote" else "viewer"},
                )
            assert response.status_code == 200, response.text
        finally:
            resume.set()
        with pytest.raises(PlatformError, match=error_code) as failure:
            future.result(timeout=5)
        assert failure.value.status == status
    with app.state.store.connection() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM p_local_feedback WHERE message=?",
                (private_message,),
            ).fetchone()[0]
            == 0
        )


def test_generation_is_monotonic_scoped_and_survives_reinitialization(app, client):
    original = captured_context(app, "user-demo", "household-demo")
    assert original.data_generation == 0
    for generation in (1, 2):
        assert (
            client.post(
                f"{BASE}/settings/data/reset",
                json={"confirmation": "RESET THIS HOUSEHOLD"},
            ).status_code
            == 200
        )
        app.state.identity.initialize()
        fresh = captured_context(app, "user-demo", "household-demo")
        assert fresh.data_generation == generation
        assert captured_context(app, "user-other", "household-other").data_generation == 0
        # Authentication also captures the new generation for ordinary HTTP writes.
        assert (
            client.post(
                f"{BASE}/settings/feedback",
                json={"kind": "general", "message": "Fresh generation"},
            ).status_code
            == 201
        )
        with app.state.store.connection(write=True) as db:
            assert_active_context(db, fresh)
            with pytest.raises(PlatformError, match="household_data_changed"):
                assert_active_context(db, original)


def test_failed_reset_rolls_back_generation_and_allows_previously_accepted_write(
    app, client
):
    register_test_domain(app, fail_clear=True)
    captured = captured_context(app, "user-demo", "household-demo")
    assert (
        client.post(
            f"{BASE}/settings/data/reset", json={"confirmation": "RESET THIS HOUSEHOLD"}
        ).status_code
        == 409
    )
    assert (
        captured_context(app, "user-demo", "household-demo").data_generation
        == captured.data_generation
    )
    receipt = create_feedback(
        FeedbackWrite(kind="general", message="Retained after rollback"),
        captured,
        app.state.identity,
    )
    assert receipt["status"] == "saved_locally"


def test_logout_does_not_cancel_accepted_private_write(app, client):
    captured = captured_context(app, "user-demo", "household-demo")
    assert client.post(f"{BASE}/session/logout").status_code == 200
    receipt = create_feedback(
        FeedbackWrite(kind="general", message="Accepted before logout"),
        captured,
        app.state.identity,
    )
    assert receipt["status"] == "saved_locally"


@pytest.mark.parametrize(
    "role,minimum_role,expected",
    [
        ("viewer", "viewer", None),
        ("viewer", "editor", "read_only_household"),
        ("editor", "owner", "owner_required"),
    ],
)
def test_current_context_minimum_role_is_enforced_in_write_transaction(
    app, role, minimum_role, expected
):
    user_id = "user-viewer" if role == "viewer" else "user-partner"
    context = captured_context(app, user_id, "household-demo")
    with app.state.store.connection(write=True) as db:
        if expected:
            with pytest.raises(PlatformError, match=expected) as failure:
                assert_active_context(db, context, minimum_role=minimum_role)
            assert failure.value.status == 403
        else:
            assert_active_context(db, context, minimum_role=minimum_role)
