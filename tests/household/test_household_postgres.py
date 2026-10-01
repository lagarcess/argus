"""Canonical Household authorization and retries on disposable PostgreSQL."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argus.domain.household.errors import (
    HouseholdNotFound,
    InvitationConsumed,
    MustTransferOrClose,
)
from argus.domain.household.financial import HouseholdFinancialService
from argus.domain.household.postgres import PostgresHouseholdRepository
from argus.domain.household.repository import FinancialAccountLookup
from argus.domain.household.schemas import CreateHouseholdRequest, Recipient
from argus.domain.household.service import HouseholdService
from argus.domain.recording.errors import IdempotencyConflict, StaleVersion
from argus.domain.recording.money_schemas import MoneyRequest
from argus.domain.recording.postgres_repository import PostgresFinancialAccountRepository
from argus.domain.recording.records import OpeningWrite
from argus.domain.recording.repository import NewAccount
from psycopg_pool import ConnectionPool

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL required")
NOW = datetime.now(timezone.utc)


def key():
    return str(uuid4())


@pytest.fixture
def lane():
    users = [key() for _ in range(3)]
    pool = ConnectionPool(DSN, min_size=1, max_size=5)
    records = PostgresFinancialAccountRepository(pool)
    service = HouseholdService(
        PostgresHouseholdRepository(
            pool, FinancialAccountLookup(records), clock=lambda: NOW
        )
    )
    with pool.connection() as c:
        for uid in users:
            c.execute(
                "insert into auth.users(id,email,is_anonymous) values(%s,%s,false)",
                (uid, f"household-{uid}@example.test"),
            )
    try:
        yield service, records, users
    finally:
        with pool.connection() as c, c.transaction():
            hids = [
                r[0]
                for r in c.execute(
                    "select id from households where created_by=any(%s::uuid[])", (users,)
                ).fetchall()
            ]
            c.execute(
                "delete from household_command_receipts where actor_id=any(%s::uuid[])",
                (users,),
            )
            c.execute(
                "delete from household_account_grants where household_id=any(%s::uuid[])",
                (hids,),
            )
            c.execute(
                "delete from household_invitations where household_id=any(%s::uuid[])",
                (hids,),
            )
            c.execute(
                "delete from household_members where household_id=any(%s::uuid[])",
                (hids,),
            )
            c.execute("delete from households where id=any(%s::uuid[])", (hids,))
            c.execute("delete from auth.users where id=any(%s::uuid[])", (users,))
        pool.close()


def command(s, actor, operation, action, hid=None, body=None, k=None):
    if body is None:
        body = (
            {"expected_version": s.get(user_id=actor, household_id=hid).version}
            if hid
            else {}
        )
    return s.execute(
        actor=actor,
        operation=operation,
        key=k or key(),
        body=body,
        household_id=hid,
        action=action,
    )


def setup(lane):
    s, records, (a, b, other) = lane
    h = command(
        s,
        a,
        "create",
        lambda: s.create(
            user_id=a,
            request=CreateHouseholdRequest(name="Fixture", display_name="Alice"),
        ),
    )
    hid = h.household_id
    invitation = command(
        s, a, "invite", lambda: s.invite(user_id=a, household_id=hid), hid
    ).invitation
    accepted = command(
        s,
        b,
        "accept",
        lambda: s.accept(user_id=b, token=invitation.token, display_name="Bob"),
    )
    return hid, accepted.membership_id, invitation.token


def account(records, owner, amount=1000, currency="DOP", share=10000, kind="checking"):
    return records.create(
        user_id=owner,
        idempotency_key=key(),
        identity_hash=key(),
        account=NewAccount(
            type=kind, currency=currency, nickname=key(), ownership_share_bps=share
        ),
        opening=OpeningWrite(
            amount_minor=amount * 100,
            as_of=NOW - timedelta(days=3),
            time_zone="UTC",
            reason=None,
        )
        if amount is not None
        else None,
    ).stored.account.id


def share(s, actor, hid, aid, mid, permission="view"):
    return command(
        s,
        actor,
        "share:" + aid,
        lambda: s.replace_grants(
            user_id=actor,
            household_id=hid,
            account_id=aid,
            recipients=[Recipient(membership_id=mid, permission=permission)],
        ),
        hid,
    )


def money(s, actor, hid, body, *, aid=None, k=None, member=None, version=None):
    h = s.get(user_id=actor, household_id=hid)
    return HouseholdFinancialService(s).money(
        actor,
        hid,
        body,
        aid,
        k,
        membership_id=member or h.membership_id,
        expected_household_version=version or h.version,
    )


def reviewed(s, actor, hid, body, aid=None):
    preview = money(s, actor, hid, body, aid=aid)
    assert preview["ready"]
    return MoneyRequest.model_validate(
        preview["reviewed_request"] | {"preview_token": preview["preview_token"]}
    )


def expense(aid, amount="25", revision=None):
    return MoneyRequest(
        kind="expense",
        account_id=aid,
        amount=amount,
        occurred_at=NOW - timedelta(days=1),
        time_zone="UTC",
        expected_revision=revision,
        reason="Receipt correction" if revision else None,
    )


def test_create_and_invitation_retry_are_durable_and_do_not_repeat_capabilities(lane):
    s, _, (a, b, other) = lane
    k = key()
    body = {"name": "One"}

    def action():
        return s.create(user_id=a, request=CreateHouseholdRequest(name="One"))

    first = command(s, a, "create", action, body=body, k=k)
    assert (
        command(s, a, "create", action, body=body, k=k).household_id == first.household_id
    )
    with pytest.raises(IdempotencyConflict):
        command(s, a, "create", action, body={"name": "Different"}, k=k)
    hid = first.household_id
    version = s.get(user_id=a, household_id=hid).version
    k = key()

    def action():
        return s.invite(user_id=a, household_id=hid)

    invite = command(
        s, a, "invite", action, hid, {"expected_version": version}, k
    ).invitation
    retry = command(s, a, "invite", action, hid, {"expected_version": version}, k)
    assert retry.invitation.token is None and retry.invitation.id == invite.id
    assert invite.expires_at == NOW + timedelta(days=7)
    assert s.preview_invitation(user_id=b, token=invite.token).available
    accepted = s.accept(user_id=b, token=invite.token, display_name="Bob")
    assert s.accept(user_id=b, token=invite.token) == accepted
    with pytest.raises(InvitationConsumed):
        s.accept(user_id=other, token=invite.token)
    assert HouseholdFinancialService(s).snapshot(b, hid)["accounts"] == []


@pytest.mark.parametrize("ending", ["leave", "remove", "close"])
def test_departure_replay_and_rejoin_require_fresh_consent(lane, ending):
    s, records, (a, b, _) = lane
    hid, mid, token = setup(lane)
    aid = account(records, a)
    bid = account(records, b)
    amid = s.get(user_id=a, household_id=hid).membership_id
    share(s, a, hid, aid, mid)
    share(s, b, hid, bid, amid)
    actor = b if ending == "leave" else a
    action = (
        (lambda: s.leave(user_id=b, household_id=hid))
        if ending == "leave"
        else (lambda: s.remove_member(user_id=a, household_id=hid, member_user_id=b))
        if ending == "remove"
        else (lambda: s.close(user_id=a, household_id=hid))
    )
    version = s.get(user_id=actor, household_id=hid).version
    k = key()
    command(s, actor, ending, action, hid, {"expected_version": version}, k)
    assert command(
        s, actor, ending, action, hid, {"expected_version": version}, k
    ).replayed
    original = s.accept(user_id=b, token=token)
    assert original.membership_id == mid and original.state == "departed"
    assert records.get_account(user_id=a, account_id=aid) and records.get_account(
        user_id=b, account_id=bid
    )
    if ending != "close":
        inv = command(
            s, a, "invite", lambda: s.invite(user_id=a, household_id=hid), hid
        ).invitation
        rejoined = s.accept(user_id=b, token=inv.token)
        assert rejoined.membership_id != mid
        assert HouseholdFinancialService(s).snapshot(b, hid)["accounts"] == []
        assert s.accept(user_id=b, token=token).state == "departed"


def test_shared_edit_owner_actor_correction_and_revoked_replay(lane):
    s, records, (a, b, _) = lane
    hid, mid, _ = setup(lane)
    aid = account(records, a)
    share(s, a, hid, aid, mid)
    with pytest.raises(HouseholdNotFound):
        money(s, b, hid, expense(aid))
    share(s, a, hid, aid, mid, "edit")
    body = reviewed(s, b, hid, expense(aid))
    k = key()
    first = money(s, b, hid, body, k=k)
    activity_id = first["activity"]["activity"]["activity_id"]
    assert money(s, b, hid, body, k=k)["replayed"]
    assert (
        records.get_account(user_id=a, account_id=aid).expenses[0].current.recorded_by
        == b
    )
    corrected = reviewed(s, b, hid, expense(aid, "20", 1), activity_id)
    result = money(s, b, hid, corrected, aid=activity_id, k=key())
    assert result["accounts"][0]["account"]["balance"]["amount"] == "980.00"
    version = s.get(user_id=a, household_id=hid).version
    command(
        s,
        a,
        "withdraw",
        lambda: s.replace_grants(
            user_id=a, household_id=hid, account_id=aid, recipients=[]
        ),
        hid,
    )
    with pytest.raises(HouseholdNotFound):
        money(s, b, hid, body, k=k)
    with pytest.raises(StaleVersion):
        command(s, a, "stale", lambda: None, hid, {"expected_version": version})


def test_projection_deduplicates_named_grants_and_keeps_currency_unknowns(lane):
    s, records, (a, b, c) = lane
    hid, mid, _ = setup(lane)
    inv = command(
        s, a, "invite", lambda: s.invite(user_id=a, household_id=hid), hid
    ).invitation
    third = s.accept(user_id=c, token=inv.token).membership_id
    cash = account(records, a)
    asset = account(records, a, 8000, share=5000, kind="property")
    unknown = account(records, a, None, currency="USD")
    account(records, a, 9000)
    for aid in [cash, asset, unknown]:
        command(
            s,
            a,
            "share:" + aid,
            lambda aid=aid: s.replace_grants(
                user_id=a,
                household_id=hid,
                account_id=aid,
                recipients=[Recipient(membership_id=mid), Recipient(membership_id=third)],
            ),
            hid,
        )
    for actor in [a, b, c]:
        snap = HouseholdFinancialService(s).snapshot(actor, hid)
        assert len(snap["accounts"]) == 3
        totals = {p["currency"]: p for p in snap["positions"]}
        assert totals["DOP"]["amount_minor"] == 500000
        assert totals["USD"]["unknown_count"] == 1 and totals["USD"]["amount_minor"] == 0


def test_single_admin_must_explicitly_close(lane):
    s, _, (a, _, _) = lane
    h = s.create(user_id=a, request=CreateHouseholdRequest())
    with pytest.raises(MustTransferOrClose):
        s.leave(user_id=a, household_id=h.id)
