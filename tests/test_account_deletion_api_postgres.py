"""Marcus #801 S1 / Priya 1 on real PostgreSQL: a person whose deletion run is
in flight is locked out of every route but POST /account/delete, and a retry
there resumes and finishes their own run."""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import psycopg
import pytest
from argus.api import dependencies
from argus.api import state as api_state
from argus.api.auth_sessions import auth_session_is_active
from argus.api.main import app
from argus.api.routers import account as account_route
from argus.api.schemas import User
from fastapi.testclient import TestClient

from tests.household.financial_fixtures import DSN, NOW
from tests.household.financial_fixtures import lane as lane  # noqa: F401 - fixture
from tests.test_account_deletion_fk_census_postgres import (
    _invite_code_secret,  # noqa: F401 - autouse fixture (#794 invite codes)
)
from tests.test_account_deletion_postgres import (  # noqa: F401 - fixtures
    BANNED,
    SqlAuthAdmin,
    _service,
    world,
)

pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL required")

SECRET = "test-only-jwt-secret-0123456789abcdef"
URL = "/api/v1/account/delete"


def test_a_locked_person_retries_and_the_run_finishes(lane, world, monkeypatch):  # noqa: ANN001, F811
    a = world["a"]
    session = str(uuid.uuid4())
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("insert into auth.sessions(id, user_id) values (%s, %s)", (session, a))
    token = jwt.encode(
        {
            "sub": a,
            "session_id": session,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int(time.time()) + 600,
        },
        SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}

    def gotrue_user(raw):  # noqa: ANN001, ANN202
        # GoTrue's /user refuses a banned account's token (user_banned).
        if a in BANNED:
            raise RuntimeError("User is banned")
        return {"id": a, "email": "a@example.test"}

    gateway = MagicMock()
    gateway.get_auth_user_from_token.side_effect = gotrue_user
    gateway.get_or_create_profile_for_auth_user.return_value = User(
        id=a, email="a@example.test", created_at=NOW, updated_at=NOW
    )
    monkeypatch.setenv(account_route.FLAG, "true")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.delenv("ARGUS_MOCK_AUTH", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_MOCK_AUTH", raising=False)
    monkeypatch.setattr(api_state, "DATABASE_URL", DSN)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(dependencies, "permanent_account_access_allowed", lambda *_: True)
    account_route._per_account.reset()

    # The first pass opens the run, locks the account and moves the data,
    # then the Admin API delete fails.
    admins = [SqlAuthAdmin(crash_on_delete=1), SqlAuthAdmin()]
    services = iter([_service(lane, admins[0]), _service(lane, admins[1])])
    client = TestClient(app)
    try:
        with patch.object(
            account_route, "account_deletion_service", side_effect=lambda: next(services)
        ):
            first = client.post(URL, json={"confirm": True}, headers=headers)
            assert first.status_code == 503, first.text
            assert first.json()["code"] == "account_deletion_incomplete"
            # Locked: every other route refuses this session now.
            assert not auth_session_is_active(database_url=DSN, token=token, user_id=a)
            second = client.post(URL, json={"confirm": True}, headers=headers)
        assert second.status_code == 200, second.text
        assert second.json() == {"status": "done", "pending": []}
        # The retry was verified locally, never through GoTrue's /user.
        assert gateway.get_auth_user_from_token.call_count == 1
        with psycopg.connect(DSN) as c:
            assert not c.execute("select 1 from auth.users where id=%s", (a,)).fetchone()
            assert not c.execute(
                "select 1 from auth.sessions where id=%s", (session,)
            ).fetchone()
    finally:
        world["placeholders"] += admins[0].created + admins[1].created
        account_route._per_account.reset()
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("delete from auth.sessions where id=%s", (session,))
