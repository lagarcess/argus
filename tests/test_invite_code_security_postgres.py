"""#789 on real Postgres: keyed digests off client tables, rotation, guards.

Runs in CI's real-PostgreSQL matrix (top-level ``tests/test_*_postgres.py``).
"""

from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("psycopg_pool")

from argus.domain.household.errors import (  # noqa: E402
    InvitationConsumed,
    InvitationNotFound,
    InviteCodesUnavailable,
)
from argus.domain.household.invite_codes import CodeHasher, normalize_code  # noqa: E402
from argus.domain.household.invites import PostgresInviteStore  # noqa: E402
from argus.domain.household.postgres import PostgresHouseholdRepository  # noqa: E402
from argus.domain.household.repository import FinancialAccountLookup  # noqa: E402
from argus.domain.household.service import HouseholdService  # noqa: E402
from argus.domain.recording.postgres_repository import (  # noqa: E402
    PostgresFinancialAccountRepository,
)

from tests.test_household_invites_postgres import (  # noqa: E402
    TEST_CODE_SECRET,
    _cleanup,
    _make_lane,
    _users,
)

OTHER_SECRET = "a-different-invite-code-secret-9876543210"
DIGEST = re.compile(r"^v2\.[0-9a-f]{8}\.[0-9a-f]{64}$")


@pytest.fixture
def lane():
    value = _make_lane()
    try:
        yield value
    finally:
        _cleanup(value)


def _store(lane, hasher):  # noqa: ANN001, ANN202
    return PostgresInviteStore(
        lane.pool, settings=lane.settings, clock=lane.clock, code_hasher=hasher
    )


def _households(lane, hasher):  # noqa: ANN001, ANN202
    return HouseholdService(
        PostgresHouseholdRepository(
            lane.pool,
            FinancialAccountLookup(PostgresFinancialAccountRepository(lane.pool)),
            clock=lane.clock,
            code_hasher=hasher,
        ),
        invite_settings=lane.settings,
    )


def _digest_of(lane, column: str, invitation_id: str):  # noqa: ANN202
    return lane.row(
        f"select digest,rehashed_at from argus_private.invite_code_digests"  # noqa: S608
        f" where {column}=%s",
        invitation_id,
    )


def test_codes_are_keyed_and_unknown_under_another_secret(lane):
    admin, member = lane.users[1:3]
    hid = lane.household(admin)
    household = lane.households.invite(user_id=admin, household_id=hid)
    beta = lane.beta(admin).invitation
    for column, iid in (
        ("household_invitation_id", household.id),
        ("beta_invitation_id", beta.id),
    ):
        digest = _digest_of(lane, column, iid)[0]
        assert DIGEST.match(digest)
        assert digest.split(".")[1] == lane.hasher.current.key_id
    stranger = CodeHasher.from_secrets(OTHER_SECRET)
    other_store = _store(lane, stranger)
    other_households = _households(lane, stranger)
    with pytest.raises(InvitationNotFound):
        other_households.preview_invitation(user_id=member, code=household.code)
    with pytest.raises(InvitationNotFound):
        other_households.accept(user_id=member, code=household.code)
    with pytest.raises(InvitationNotFound):
        other_store.preview(token=None, code=beta.code)
    with pytest.raises(InvitationNotFound):
        other_store.redeem(user_id=member, token=None, code=beta.code)
    # Link tokens do not depend on the code secret.
    assert other_store.preview(token=beta.token, code=None).kind == "beta"
    assert other_households.preview_invitation(user_id=member, token=household.token)


def test_rotation_finds_old_codes_and_rehashes_them_on_use(lane):
    link = lane.group_link(5, label="Rotation")
    old_kid = lane.hasher.current.key_id
    rotated = CodeHasher.from_secrets(OTHER_SECRET, TEST_CODE_SECRET)
    assert _digest_of(lane, "beta_invitation_id", link.id)[0].split(".")[1] == old_kid
    # During the window the previous secret still finds the code ...
    assert _store(lane, rotated).preview(token=None, code=link.code).kind == "group_link"
    digest, rehashed_at = _digest_of(lane, "beta_invitation_id", link.id)
    # ... and using it moved the digest to the current secret.
    assert digest.split(".")[1] == rotated.current.key_id and rehashed_at is not None
    assert digest == rotated.digest(normalize_code(link.code))
    # After the window, only the new secret is configured; the code still works.
    new_only = CodeHasher.from_secrets(OTHER_SECRET)
    assert (
        _store(lane, new_only)
        .redeem(user_id=lane.users[1], token=None, code=link.code)
        .admitted
    )
    with pytest.raises(InvitationNotFound):
        _store(lane, CodeHasher.from_secrets(TEST_CODE_SECRET)).preview(
            token=None, code=link.code
        )
    # A code minted during the window is made with the current secret only.
    fresh = _store(lane, rotated).create_beta(
        user_id=lane.users[2], key="rotation-fresh", request_hash="{}"
    )
    lane.invitation_ids.add(fresh.invitation.id)
    fresh_digest = _digest_of(lane, "beta_invitation_id", fresh.invitation.id)
    assert fresh_digest[0].split(".")[1] == rotated.current.key_id
    assert fresh_digest[1] is None


def test_without_a_secret_nothing_is_written_and_codes_are_refused(lane, monkeypatch):
    monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET", raising=False)
    monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET_PREVIOUS", raising=False)
    sender = lane.users[1]
    existing = lane.beta(sender).invitation
    unkeyed = PostgresInviteStore(lane.pool, settings=lane.settings, clock=lane.clock)
    before = lane.row(
        "select count(*) from public.beta_invitations where created_by=%s", sender
    )
    with pytest.raises(InviteCodesUnavailable):
        unkeyed.create_beta(user_id=sender, key="no-secret", request_hash="{}")
    assert (
        lane.row(
            "select count(*) from public.beta_invitations where created_by=%s", sender
        )
        == before
    )
    with pytest.raises(InviteCodesUnavailable):
        unkeyed.preview(token=None, code=existing.code)
    with pytest.raises(InviteCodesUnavailable):
        unkeyed.redeem(user_id=lane.users[2], token=None, code=existing.code)
    assert unkeyed.preview(token=existing.token, code=None).kind == "beta"
    admin = lane.users[3]
    hid = lane.household(admin)
    with pytest.raises(InviteCodesUnavailable):
        _households(lane, None).invite(user_id=admin, household_id=hid)


def test_no_client_role_can_ever_read_a_code_digest(lane):
    owner = lane.users[1]
    lane.beta(owner)
    hid = lane.household(owner)
    lane.households.invite(user_id=owner, household_id=hid)
    with lane.pool.connection() as conn:
        # No client-reachable table has a code digest column any more.
        columns = conn.execute(
            "select table_schema||'.'||table_name||'.'||column_name"
            " from information_schema.columns where column_name like '%%code_hash%%'"
            " or (column_name='digest' and table_schema<>'argus_private'"
            " and table_name like '%%invit%%')"
        ).fetchall()
        assert columns == []
        assert (
            conn.execute(
                "select count(*) from pg_policies where schemaname='argus_private'"
                " and tablename='invite_code_digests'"
            ).fetchone()[0]
            == 0
        )
        assert conn.execute(
            "select relrowsecurity from pg_class where oid="
            "'argus_private.invite_code_digests'::regclass"
        ).fetchone() == (True,)
        grants = conn.execute(
            "select grantee,privilege_type from information_schema.role_table_grants"
            " where table_schema='argus_private' and table_name='invite_code_digests'"
            " and grantee in ('anon','authenticated','service_role','PUBLIC')"
        ).fetchall()
        assert grants == []
        for role in ("anon", "authenticated"):
            assert not conn.execute(
                "select has_schema_privilege(%s,'argus_private','usage')", (role,)
            ).fetchone()[0]
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(f"set local role {role}")
                    conn.execute("select * from argus_private.invite_code_digests")
        # service_role reaches the schema (earlier migrations grant usage for
        # other tables) but holds no privilege on this table.
        assert conn.execute(
            "select has_schema_privilege('service_role','argus_private','usage')"
        ).fetchone() == (True,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("set local role service_role")
                conn.execute("select * from argus_private.invite_code_digests")
        # Even if someone later granted schema usage and SELECT, RLS with no
        # policy returns nothing to the invite's own sender.
        try:
            with conn.transaction():
                conn.execute("grant usage on schema argus_private to authenticated")
                conn.execute(
                    "grant select on argus_private.invite_code_digests to authenticated"
                )
                conn.execute("set local role authenticated")
                conn.execute(
                    "select set_config('request.jwt.claims', %s, true)",
                    (f'{{"sub":"{owner}","role":"authenticated"}}',),
                )
                seen = conn.execute(
                    "select count(*) from argus_private.invite_code_digests"
                ).fetchone()[0]
                assert seen == 0
                raise psycopg.Rollback()
        finally:
            conn.execute("reset role")
        # An unkeyed (v1-style) digest can never be written back.
        import hashlib

        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute(
                    "insert into argus_private.invite_code_digests"
                    "(digest,household_invitation_id) select %s,id"
                    " from public.household_invitations limit 1",
                    (hashlib.sha256(b"argus-invite-code:v1:ABCDEFGH").hexdigest(),),
                )


def test_single_use_claim_checks_its_row_count_even_without_the_lock(lane, monkeypatch):
    """Priya: invites.py checked no row count on the use_count=0 update.

    With the row lock removed, the guarded update's row count alone must still
    admit exactly one person; without the check, every racer was admitted.
    """
    monkeypatch.setattr(PostgresInviteStore, "_single_use_lock", "")
    sender = lane.users[1]
    invitees = _users(lane.pool, 8)
    lane.users.extend(invitees)
    code = lane.beta(sender).invitation.code
    barrier = threading.Barrier(len(invitees))

    def redeem(user):  # noqa: ANN001, ANN202
        barrier.wait()
        try:
            return lane.store.redeem(user_id=user, token=None, code=code).outcome
        except InvitationConsumed:
            return "consumed"

    with ThreadPoolExecutor(max_workers=len(invitees)) as pool:
        outcomes = list(pool.map(redeem, invitees))
    assert outcomes.count("admitted") == 1, outcomes
    assert outcomes.count("consumed") == len(invitees) - 1
    assert lane.row(
        "select count(*) from public.beta_admissions where user_id=any(%s::uuid[])",
        invitees,
    ) == (1,)


def test_revoke_in_flight_on_a_full_link_is_not_counted_as_overflow(lane):
    """Priya: removing FOR UPDATE on the group-link re-read broke no test.

    The link is at its cap and a revoke is in flight (row locked, not yet
    committed). The guarded update misses at once on the committed, full row
    without waiting. Only a locking re-read waits for the revoke and answers
    revoked with overflow untouched; a plain re-read sees the old row, counts
    an overflow and answers full.
    """
    import time

    from argus.domain.household.errors import GroupLinkFull, InvitationRevoked

    link = lane.group_link(1, label="Revoke in flight")
    first, second = lane.users[1:3]
    assert lane.store.redeem(user_id=first, token=None, code=link.code).admitted
    outcome: dict[str, object] = {}

    def tap() -> None:
        try:
            outcome["result"] = lane.store.redeem(
                user_id=second, token=None, code=link.code
            )
        except (InvitationRevoked, GroupLinkFull) as error:
            outcome["result"] = type(error).__name__

    with psycopg.connect(DSN, autocommit=False) as revoker:
        revoker.execute(
            "update public.beta_invitations set revoked_at=now() where id=%s",
            (link.id,),
        )
        worker = threading.Thread(target=tap)
        worker.start()
        with psycopg.connect(DSN, autocommit=True) as probe:
            deadline = time.monotonic() + 10
            waiting = 0
            while time.monotonic() < deadline and not waiting:
                waiting = probe.execute(
                    "select count(*) from pg_stat_activity"
                    " where wait_event_type='Lock' and pid<>%s",
                    (revoker.info.backend_pid,),
                ).fetchone()[0]
                time.sleep(0.02)
        assert waiting, "the redeem never waited on the in-flight revoke"
        revoker.commit()
    worker.join(timeout=10)
    assert outcome.get("result") == "InvitationRevoked", outcome
    assert lane.row(
        "select use_count,overflow_count from public.beta_invitations where id=%s",
        link.id,
    ) == (1, 0)


@pytest.mark.parametrize("locked", [True, False], ids=["row_lock", "guard_only"])
def test_household_accept_refuses_an_invitation_revoked_under_it(
    lane, monkeypatch, locked
):
    """Priya: the household accept row-count guard had no test.

    A revoke of the invitation is in flight (row locked, not yet committed).
    With the row lock, accept waits and answers revoked. With the lock cleared
    (``_household_accept_lock``), accept reads the old row, adds the member and
    then its guarded update waits and misses: the row-count check must refuse
    and roll the membership back. Without that check the revoked invitation
    was accepted.
    """
    import time

    from argus.domain.household.errors import InvitationRevoked

    if not locked:
        monkeypatch.setattr(PostgresHouseholdRepository, "_household_accept_lock", "")
    admin, joiner = lane.users[1:3]
    hid = lane.household(admin)
    invite = lane.households.invite(user_id=admin, household_id=hid)
    outcome: dict[str, object] = {}

    def accept() -> None:
        try:
            outcome["result"] = lane.households.accept(user_id=joiner, code=invite.code)
        except (InvitationRevoked, InvitationConsumed) as error:
            outcome["result"] = type(error).__name__

    with psycopg.connect(DSN, autocommit=False) as revoker:
        revoker.execute(
            "update public.household_invitations set revoked_at=now() where id=%s",
            (invite.id,),
        )
        worker = threading.Thread(target=accept)
        worker.start()
        with psycopg.connect(DSN, autocommit=True) as probe:
            deadline = time.monotonic() + 10
            waiting = 0
            while time.monotonic() < deadline and not waiting:
                waiting = probe.execute(
                    "select count(*) from pg_stat_activity"
                    " where wait_event_type='Lock' and pid<>%s",
                    (revoker.info.backend_pid,),
                ).fetchone()[0]
                time.sleep(0.02)
        assert waiting, "the accept never waited on the in-flight revoke"
        revoker.commit()
    worker.join(timeout=10)
    expected = "InvitationRevoked" if locked else "InvitationConsumed"
    assert outcome.get("result") == expected, outcome
    assert lane.row(
        "select count(*) from public.household_members"
        " where household_id=%s and user_id=%s",
        hid,
        joiner,
    ) == (0,)
    assert lane.row(
        "select accepted_at from public.household_invitations where id=%s", invite.id
    ) == (None,)
