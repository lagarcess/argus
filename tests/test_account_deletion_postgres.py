"""Lane 6: the account deletion command end to end on real PostgreSQL.

Reuses the census world (A shares plans, groups, records and households with
B; C contributed to A's plan and left) and adds a departed binding A owns, a
plan nobody else is in, a note on a shared record, and Plaid and Gmail
credentials. The Admin API is a fake that runs SQL on auth.users, here only.
"""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest
from argus.domain.account_deletion.auth_admin import PLACEHOLDER_DOMAIN
from argus.domain.account_deletion.service import (
    AccountDeletionRejected,
    AccountDeletionService,
    subject_hash,
)
from argus.domain.household.planning import SharedPlanningService
from argus.domain.household.schemas import CreateHouseholdRequest
from argus.domain.ingestion.connections_postgres import PostgresConnectionRepository
from argus.observability.analytics_deletion import RecordingAnalyticsDeletion
from argus.observability.product_events import actor_hash_for_user
from psycopg_pool import ConnectionPool

from tests.account_deletion_census import sweep
from tests.household.financial_fixtures import DSN, NOW, account, key
from tests.household.financial_fixtures import command as household_command
from tests.household.financial_fixtures import lane as lane  # noqa: F401 - fixture
from tests.household.shared_cleanup import cleanup
from tests.household.shared_plan_fixtures import money, request
from tests.household.test_shared_planning_departure import accept, invitation, leave
from tests.test_account_deletion_fk_census_postgres import (
    HANDOFF_BLOCKERS,
    _bill,
    _occurrence,
    _plan_as,
    build_world,
    probe,
)

pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL required")


class Crash(Exception):
    pass


class SqlAuthAdmin:
    """Test-only stand-in for the Supabase Admin API."""

    def __init__(self, *, providers=(), crash_on_delete=0, after_create=None):  # noqa: ANN001
        self.providers = set(providers)
        self.crash_on_delete = crash_on_delete
        self.after_create = after_create
        self.created: list[str] = []
        self.creates = 0
        self.deleted: list[str] = []

    def create_placeholder(self, *, user_id: str, email: str) -> None:
        assert email.startswith("exmiembro+") and email.endswith("@" + PLACEHOLDER_DOMAIN)
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute(
                "insert into auth.users(id,email,is_anonymous,raw_app_meta_data,email_confirmed_at)"
                " values (%s,%s,false,%s,now())",
                (user_id, email, json.dumps({"placeholder": True})),
            )
        self.creates += 1
        self.created.append(user_id)
        if self.after_create:
            self.after_create(user_id, email)

    def user_exists(self, user_id: str) -> bool:
        with psycopg.connect(DSN) as c:
            return bool(
                c.execute("select 1 from auth.users where id=%s", (user_id,)).fetchone()
            )

    def identity_providers(self, user_id: str) -> set[str]:
        return set(self.providers)

    def delete_user(self, user_id: str) -> None:
        if self.crash_on_delete:
            self.crash_on_delete -= 1
            raise Crash("admin api down")
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("delete from auth.users where id=%s", (user_id,))
        self.deleted.append(user_id)


class FakeRevoker:
    def __init__(self, fail=()):  # noqa: ANN001
        self.fail = set(fail)
        self.calls: list[tuple[str, str, bytes | None]] = []

    def revoke_for_deletion(self, *, source, connection_id, external_ref, envelope):  # noqa: ANN001
        self.calls.append((source, connection_id, envelope))
        return "failed" if source in self.fail else "revoked"


def _service(lane, admin, revoker=None, analytics=None):  # noqa: ANN001, F811
    return AccountDeletionService(
        households=lane[0]._repository,
        auth_admin=admin,
        revoker=revoker or FakeRevoker(),
        analytics=analytics or RecordingAnalyticsDeletion(),
        clock=lambda: NOW,
    )


def _extras(lane, world):  # noqa: ANN001, F811
    """A departed binding A owns, a plan only A is in, a noted record, sources."""
    households, records, _ = lane
    a, b = world["a"], world["b"]
    plans = SharedPlanningService(households)
    h1 = world["households"][0]
    amid = households.get(user_id=a, household_id=h1).membership_id
    aa = world["aa"]
    s1 = dict(households=households, records=records, plans=plans, hid=h1, a=a, b=b)
    solo = _plan_as(s1, a, amid, "bill", [], [(amid, "100")], _bill(aa))

    # C comes back to H1; B's plan has both A and C paying, so once both are
    # deleted it shows "Exmiembro 1" and "Exmiembro 2".
    c = world["c"]
    cmid = accept(s1, c, invitation(s1, a))
    with psycopg.connect(DSN) as conn:
        ba = str(
            conn.execute(
                "select id from public.financial_accounts where user_id=%s and type <> 'other_debt' order by created_at limit 1",
                (b,),
            ).fetchone()[0]
        )
    bmid = households.get(user_id=b, household_id=h1).membership_id
    pair = _plan_as(
        s1,
        b,
        bmid,
        "bill",
        [amid, cmid],
        [(bmid, "40"), (amid, "30"), (cmid, "30")],
        _bill(ba),
    )
    money(s1, a, pair, request("expense", aa, "3"), "bill_payment", _occurrence(pair))
    money(
        dict(s1, c=c),
        c,
        pair,
        request("expense", account(records, c), "4"),
        "bill_payment",
        _occurrence(pair),
    )

    h3 = household_command(
        households,
        a,
        "create",
        lambda: households.create(
            user_id=a, request=CreateHouseholdRequest(name="Third", display_name="Alice")
        ),
    ).household_id
    s3 = dict(s1, hid=h3)
    s3["amid"] = households.get(user_id=a, household_id=h3).membership_id
    s3["bmid"] = accept(s3, b, invitation(s3, a))
    departed = _plan_as(
        s3,
        a,
        s3["amid"],
        "bill",
        [s3["bmid"]],
        [(s3["amid"], "50"), (s3["bmid"], "50")],
        _bill(aa),
    )
    money(
        s3,
        a,
        departed,
        request("expense", aa, "7", note="regalo secreto"),
        "bill_payment",
        _occurrence(departed),
    )
    household_command(
        households,
        a,
        "transfer_admin",
        lambda: households.transfer_admin(
            user_id=a, household_id=h3, new_admin_user_id=b
        ),
        h3,
    )
    leave(s3, a)

    pool_conn = PostgresConnectionRepository(lane[0]._repository._pool)
    gmail = pool_conn.create(
        user_id=a,
        source="gmail",
        external_ref="mbx-" + key(),
        label="Gmail",
        now=NOW,
        secret=b"g",
    )
    return dict(solo=solo, pair=pair, departed=departed, h3=h3, gmail=gmail.id)


def _rows_holding(conn, needle):  # noqa: ANN001
    """Every table in public or argus_private with a row whose text holds needle."""
    found = []
    for schema, table in conn.execute(
        "select table_schema, table_name from information_schema.tables"
        " where table_schema in ('public','argus_private') and table_type='BASE TABLE'"
    ).fetchall():
        if conn.execute(
            f'select 1 from "{schema}"."{table}" t where t::text like %s limit 1',
            (f"%{needle}%",),
        ).fetchone():
            found.append(f"{schema}.{table}")
    return found


def _members_of(user_ids):  # noqa: ANN001
    with psycopg.connect(DSN) as c:
        return {
            str(r[0])
            for r in c.execute(
                "select id from public.household_members where user_id=any(%s::uuid[])",
                (list(user_ids),),
            ).fetchall()
        }


def _totals(snapshot, gone):  # noqa: ANN001
    """The money B sees per plan. Two things change exactly as on an ordinary
    leave (#773), not because of the deletion: the shared debt plan becomes a
    read-only archive, which stops its future schedule, and a departed
    member's goal savings stop counting as applied (the archive keeps
    last_applied_minor, which reads do not use yet). So A's applied amounts and
    schedule-derived remainders are not compared; every amount, date and
    purpose is, and so is everyone else's applied money, except goal savings:
    a goal's backing is the destination account's balance, and A's accounts
    and balances go with A, so savings into A's accounts can no longer show as
    backed (a known gap reported with Lane 6)."""
    keep = {}
    for plan in snapshot["plans"]:
        keep[(plan["ref"]["kind"], plan["ref"]["id"])] = dict(
            actual=plan["progress"]["actual_minor"],
            contributions=sorted(
                (
                    c["amount_minor"],
                    None
                    if (c.get("person") or {}).get("membership_id") in gone
                    or c["purpose"] == "goal_saving"
                    else c["applied_minor"],
                    c["date"],
                    c["purpose"],
                )
                for c in plan["contributions"]
            ),
        )
    return keep


def _names(value):  # noqa: ANN001
    if isinstance(value, dict):
        out = {value["display_name"]} if "display_name" in value else set()
        for v in value.values():
            out |= _names(v)
        return out
    if isinstance(value, list):
        return set().union(*(_names(v) for v in value)) if value else set()
    return set()


def _side_effect_free(placeholder, email):  # noqa: ANN001
    """Marcus: a placeholder create sends no email, records no signup or
    analytics event, and makes no profile and no beta admission."""
    with psycopg.connect(DSN) as c:
        assert set(_rows_holding(c, placeholder)) == {
            "argus_private.account_placeholders",
            "argus_private.account_deletion_placeholders",
        }, placeholder
        assert _rows_holding(c, email) == []


def _cleanup(world, placeholders, hids):  # noqa: ANN001
    ids = [world["a"], world["b"], world["c"], *placeholders]
    with psycopg.connect(DSN) as c, c.transaction():
        c.execute(
            "delete from public.household_deletion_events where household_id=any(%s::uuid[])",
            (hids,),
        )
        cleanup(c, ids, hids)
        c.execute(
            "delete from public.household_account_grants where household_id=any(%s::uuid[])",
            (hids,),
        )
        c.execute(
            "delete from public.household_invitations where household_id=any(%s::uuid[])",
            (hids,),
        )
        c.execute(
            "delete from public.household_command_receipts where household_id=any(%s::uuid[])",
            (hids,),
        )
        c.execute(
            "delete from public.household_members where household_id=any(%s::uuid[])",
            (hids,),
        )
        c.execute("delete from public.households where id=any(%s::uuid[])", (hids,))
        c.execute(
            "delete from public.feedback where user_id=any(%s::uuid[]) or context->>'account_email' like %s",
            (ids, f"%{world['a']}%"),
        )
        c.execute("delete from auth.users where id=any(%s::uuid[])", (placeholders,))
        c.execute(
            "delete from argus_private.account_placeholders where id=any(%s::uuid[])",
            (placeholders,),
        )
        for uid in (world["a"], world["c"]):
            c.execute(
                "delete from argus_private.account_deletion_runs where subject_hash=%s",
                (subject_hash(uid),),
            )


@pytest.fixture
def world(lane):  # noqa: F811
    with ConnectionPool(DSN, min_size=1, max_size=4, open=True) as pool:
        built = build_world(lane, pool)
    with psycopg.connect(DSN) as c:
        built["aa"] = str(
            c.execute(
                "select id from public.financial_accounts where user_id=%s and type <> 'other_debt' order by created_at limit 1",
                (built["a"],),
            ).fetchone()[0]
        )
    built.update(_extras(lane, built))
    built["placeholders"] = []
    try:
        yield built
    finally:
        _cleanup(built, built["placeholders"], built["households"] + [built["h3"]])


def test_deleting_a_sharing_person_keeps_everyone_elses_history(lane, world):  # noqa: F811
    a, b = world["a"], world["b"]
    plans = SharedPlanningService(lane[0])
    hids = world["households"] + [world["h3"]]
    with psycopg.connect(DSN) as conn:
        plain_error, blockers, _, _ = probe(conn, a, sweep(conn))
    assert plain_error is not None
    assert HANDOFF_BLOCKERS <= {(i.table, i.columns) for k, i in blockers if k == "fk"}
    gone = _members_of([a])
    before = {h: _totals(plans.snapshot(b, h), gone) for h in hids}
    with psycopg.connect(DSN) as conn:
        email = conn.execute("select email from auth.users where id=%s", (a,)).fetchone()[
            0
        ]

    admin = SqlAuthAdmin(after_create=_side_effect_free)
    revoker = FakeRevoker()
    analytics = RecordingAnalyticsDeletion()
    outcome = _service(lane, admin, revoker, analytics).delete_account(user_id=a)
    world["placeholders"] += admin.created

    assert outcome.status == "done", outcome
    # Marcus (3): one create per placeholder, each side-effect free (checked in
    # the hook), and at least two of them: H1, H2, H3 and A's shared groups.
    assert admin.creates == len(set(admin.created)) >= 3
    # One placeholder per sharing scope: every plan of A's in one household
    # shares that household's placeholder.
    with psycopg.connect(DSN) as conn:
        per_household = conn.execute(
            """select b.household_id, count(distinct b.owner_user_id) filter (where b.owner_user_id = any(%s::uuid[])),
                      count(distinct m.user_id)
                 from public.household_members m
                 join public.household_plan_bindings b on b.household_id = m.household_id
                where m.user_id = any(%s::uuid[]) group by b.household_id""",
            (admin.created, admin.created),
        ).fetchall()
        assert per_household and all(row[2] == 1 for row in per_household), per_household
    assert sorted(admin.deleted) == sorted(
        [a, *[p for p in admin.created if p in admin.deleted[1:]]]
    )
    assert {c[0] for c in revoker.calls} == {"plaid", "gmail"}
    assert analytics.calls == [
        {"distinct_id": actor_hash_for_user(a), "delete_events": True}
    ]

    gone = _members_of(admin.created)
    after = {h: _totals(plans.snapshot(b, h), gone) for h in hids}
    for h in hids:
        for ref, totals in before[h].items():
            if ref in after[h]:
                assert after[h][ref] == totals, (h, ref)
    h1 = world["households"][0]
    # The plan only A was in is gone; every other plan of A's in H1 is B's now.
    with psycopg.connect(DSN) as conn:
        assert not conn.execute(
            "select 1 from public.household_plan_bindings where definition_id=%s",
            (world["solo"]["ref"]["id"],),
        ).fetchone()
        live = conn.execute(
            "select kind, owner_user_id, departed_at from public.household_plan_bindings"
            " where household_id=%s and revoked_at is null and departed_at is null",
            (h1,),
        ).fetchall()
        assert live and all(str(row[1]) == b for row in live if row[0] != "debt")
        debt = conn.execute(
            """select b.owner_user_id, d.user_id, a.user_id
                 from public.household_plan_bindings b
                 join public.financial_debt_plans d on d.id = b.definition_id and d.user_id = b.owner_user_id
                 join public.financial_accounts a on a.id = d.debt_account_id
                where b.household_id=%s and b.kind='debt'""",
            (h1,),
        ).fetchone()
        # Lucas: the shared debt plan is a read-only archive; the plan and its
        # debt account both move to H1's placeholder.
        assert debt and len({str(x) for x in debt}) == 1 and str(debt[0]) in admin.created
        # Notes are gone from every kept copy.
        assert not conn.execute(
            "select 1 from public.financial_record_revisions where user_id=any(%s::uuid[]) and details ? 'note'",
            (admin.created,),
        ).fetchone()
        assert not conn.execute(
            "select 1 from public.financial_record_revisions where details::text like '%%regalo secreto%%'"
        ).fetchone()
        # Nothing anywhere still holds A's id or email.
        assert _rows_holding(conn, a) == []
        assert _rows_holding(conn, email) == []
        assert not conn.execute("select 1 from auth.users where id=%s", (a,)).fetchone()
        run = conn.execute(
            "select user_id, status, steps from argus_private.account_deletion_runs where subject_hash=%s",
            (subject_hash(a),),
        ).fetchone()
        assert run[0] is None and run[1] == "done"
        assert not conn.execute(
            "select 1 from argus_private.account_deletion_placeholders where subject_hash=%s",
            (subject_hash(a),),
        ).fetchone()
        assert not conn.execute(
            "select 1 from argus_private.account_deletion_revocations where subject_hash=%s and (secret_ciphertext is not null or status <> 'revoked')",
            (subject_hash(a),),
        ).fetchone()
        events = {
            row[0]
            for row in conn.execute(
                "select kind from public.household_deletion_events where household_id=any(%s::uuid[])",
                (hids,),
            ).fetchall()
        }
        assert {"member_deleted", "plan_handed_over"} <= events
    # The handed-over plans are B's to edit, and A shows as Exmiembro.
    snapshot = plans.snapshot(b, h1)
    owned = [p for p in snapshot["plans"] if p["is_owner"] and not p["read_only"]]
    assert len(owned) >= 4
    names = _names(snapshot)
    assert "Alice" not in names and any(n.startswith("Exmiembro") for n in names), names

    # C is deleted too: in the plan both of them were in, they are numbered.
    c_admin = SqlAuthAdmin(after_create=_side_effect_free)
    assert _service(lane, c_admin).delete_account(user_id=world["c"]).status == "done"
    world["placeholders"] += c_admin.created
    pair = [
        p
        for p in plans.snapshot(b, h1)["plans"]
        if p["ref"]["id"] == world["pair"]["ref"]["id"]
    ][0]
    assert {c["person"]["display_name"] for c in pair["contributions"]} == {
        "Exmiembro 1",
        "Exmiembro 2",
    }

    # Rerunning is a no-op, and placeholders are refused.
    assert _service(lane, SqlAuthAdmin()).delete_account(user_id=a).status == "done"
    with pytest.raises(AccountDeletionRejected):
        _service(lane, SqlAuthAdmin()).delete_account(user_id=admin.created[0])


def test_a_crash_between_placeholders_and_the_auth_delete_resumes(lane, world):  # noqa: F811
    a = world["a"]
    admin = SqlAuthAdmin(crash_on_delete=1)
    with pytest.raises(Crash):
        _service(lane, admin).delete_account(user_id=a)
    world["placeholders"] += admin.created
    with psycopg.connect(DSN) as conn:
        run = conn.execute(
            "select user_id, status from argus_private.account_deletion_runs where subject_hash=%s",
            (subject_hash(a),),
        ).fetchone()
        assert str(run[0]) == a and run[1] == "data_deleted"
        assert conn.execute("select 1 from auth.users where id=%s", (a,)).fetchone()
    resumed = SqlAuthAdmin()
    assert _service(lane, resumed).delete_account(user_id=a).status == "done"
    # No new placeholder on resume; the same ones are kept or cleared.
    assert resumed.creates == 0
    with psycopg.connect(DSN) as conn:
        assert not conn.execute("select 1 from auth.users where id=%s", (a,)).fetchone()
        assert _rows_holding(conn, a) == []


def test_failed_provider_revokes_stay_pending_until_a_retry(lane, world):  # noqa: F811
    a = world["a"]
    admin = SqlAuthAdmin(providers={"apple"})
    outcome = _service(lane, admin, FakeRevoker(fail={"gmail"})).delete_account(user_id=a)
    world["placeholders"] += admin.created
    assert outcome.status == "auth_deleted"
    assert sorted(outcome.pending) == ["apple", "gmail"]
    with psycopg.connect(DSN) as conn:
        pending = conn.execute(
            "select provider, secret_ciphertext is not null from argus_private.account_deletion_revocations"
            " where subject_hash=%s and status='pending' order by provider",
            (subject_hash(a),),
        ).fetchall()
        assert pending == [("apple", False), ("gmail", True)]
    retry = FakeRevoker()
    outcome = _service(lane, SqlAuthAdmin(), retry).delete_account(user_id=a)
    assert [c[0] for c in retry.calls] == ["gmail"]
    # Apple has no revoke path yet: it fails safe and stays owed.
    assert outcome.status == "auth_deleted" and outcome.pending == ["apple"]


def test_definers_need_the_deletion_writer_and_copies_keep_history(lane, world):  # noqa: F811
    a = world["a"]
    with psycopg.connect(DSN) as conn:
        for sql in (
            "select argus_private.deletion_finish(%s, null)",
            "select argus_private.deletion_pass_on_archives(%s)",
        ):
            with pytest.raises(psycopg.Error, match="deletion"):
                conn.execute(sql, (a,))
            conn.rollback()
        before = conn.execute(
            """select r.revision, r.amount_minor, r.as_of, r.recorded_at, rec.created_at, rec.current_revision
                 from public.financial_record_revisions r
                 join public.financial_records rec on rec.id = r.record_id
                 join public.financial_activity_memberships m on m.record_id = rec.id
                 join public.financial_plan_links l on l.activity_id = m.activity_id
                where rec.user_id=%s and l.activity_owner_id=%s and l.binding_id is not null
                order by 1,2,3,4""",
            (a, a),
        ).fetchall()
    admin = SqlAuthAdmin()
    _service(lane, admin).delete_account(user_id=a)
    world["placeholders"] += admin.created
    with psycopg.connect(DSN) as conn:
        after = conn.execute(
            """select r.revision, r.amount_minor, r.as_of, r.recorded_at, rec.created_at, rec.current_revision
                 from public.financial_record_revisions r
                 join public.financial_records rec on rec.id = r.record_id
                 join public.financial_activity_memberships m on m.record_id = rec.id
                 join public.financial_plan_links l on l.activity_id = m.activity_id
                where rec.user_id=any(%s::uuid[]) and l.activity_owner_id=rec.user_id
                order by 1,2,3,4""",
            (admin.created,),
        ).fetchall()
    # The kept copies carry the original revision numbers and timestamps.
    assert before and set(before) <= set(after)


def test_rejects_bad_ids_unknown_people_and_guests(lane):  # noqa: F811
    service = _service(lane, SqlAuthAdmin())
    for bad in ("", "not-a-uuid", str(uuid.uuid4())):
        with pytest.raises(AccountDeletionRejected):
            service.delete_account(user_id=bad)
    guest = str(uuid.uuid4())
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("insert into auth.users(id,is_anonymous) values (%s,true)", (guest,))
    try:
        with pytest.raises(AccountDeletionRejected, match="guest"):
            service.delete_account(user_id=guest)
    finally:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("delete from auth.users where id=%s", (guest,))
