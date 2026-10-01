"""Reconciliation behavior shared by the in-memory and real-Postgres stores.

The central case: one card purchase arrives as a Wallet tap, a bank email, a
Plaid pending row that later posts, and a statement line. It must stay one
financial event with every source's evidence, and record one activity.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argus.domain.ingestion.contract import ImportCandidate
from argus.domain.ingestion.reconcile.model import ReconcileError, StaleEvent
from argus.domain.recording.errors import IdempotencyConflict
from argus.domain.recording.money_schemas import MoneyRequest
from argus.domain.recording.money_service import MoneyService
from argus.domain.recording.schemas import CreateFinancialAccountRequest

NOW = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)
DAY = date(2026, 9, 18)


def new_account(world, kind="credit_card", currency="USD"):
    return world.accounts.create(
        user_id=world.user,
        idempotency_key=str(uuid4()),
        request=CreateFinancialAccountRequest(type=kind, currency=currency),
    ).stored.account.id


def cand(connection, external_id, **values):
    source = values.pop("source")
    body = {
        "source": {
            "source": source,
            "connection_id": connection,
            "external_id": external_id,
            "observed_at": NOW,
            "replaces_external_id": values.pop("replaces", None),
        },
        "evidence": values.pop("evidence", "transaction"),
    }
    body.update(values)
    return ImportCandidate(**body)


def tap(conn, eid="tap-1", amount="12.50", **extra):
    return cand(
        conn,
        eid,
        source="shortcuts",
        amount=amount,
        currency="USD",
        occurred_on=DAY,
        account={"name": "Sapphire"},
        merchant="Café Uno",
        **extra,
    )


def plaid(
    conn,
    eid,
    amount="12.50",
    status="pending",
    currency="USD",
    kind_hint="expense",
    direction="outflow",
    **extra,
):
    return cand(
        conn,
        eid,
        source="plaid",
        status=status,
        amount=amount,
        currency=currency,
        direction=direction,
        occurred_on=DAY,
        account={"external_account_id": "acc-1", "mask": "4321"},
        merchant="CAFE UNO",
        kind_hint=kind_hint,
        **extra,
    )


def submit(world, conn, *candidates):
    return world.recon.submit(
        user_id=world.user, connection_id=conn, candidates=candidates
    )


def only(world, state="open"):
    items = world.recon.list(user_id=world.user, states=(state,))
    assert len(items) == 1, items
    return items[0]


def accept(world, event, key="accept-1", **overrides):
    preview = world.recon.preview(
        user_id=world.user, event_id=event["id"], overrides=overrides
    )
    reviewed = MoneyRequest.model_validate(preview["preview"]["reviewed_request"])
    reviewed = reviewed.model_copy(
        update={"preview_token": preview["preview"]["preview_token"]}
    )
    current = world.recon.detail(user_id=world.user, event_id=event["id"])
    return world.recon.accept(
        user_id=world.user,
        event_id=event["id"],
        idempotency_key=key,
        version=current["version"],
        request=reviewed,
    )


def link_accounts(world, account, *pairs):
    """Prior confirmed imports taught reconciliation these mappings."""

    for conn, candidate in pairs:
        submit(world, conn, candidate)
    for event in world.recon.list(user_id=world.user, states=("open",)):
        world.recon.resolve(
            user_id=world.user,
            event_id=event["id"],
            version=event["version"],
            changes={"account_id": account},
        )
        current = world.recon.detail(user_id=world.user, event_id=event["id"])
        world.recon.dismiss(
            user_id=world.user, event_id=event["id"], version=current["version"]
        )


def activities(world):
    from argus.domain.recording.money_reads import current_activities

    return current_activities(world.accounts.list_accounts(user_id=world.user))


def test_same_purchase_from_four_sources_is_one_event_and_one_record(world):
    card = new_account(world)
    shortcuts, gmail, bank, statement = (
        world.connect(s) for s in ("shortcuts", "gmail", "plaid", "statement")
    )
    link_accounts(
        world,
        card,
        (shortcuts, tap(shortcuts, "setup-tap", amount="1.00")),
        (bank, plaid(bank, "setup-txn", amount="1.00")),
        (
            statement,
            cand(
                statement,
                "setup-line",
                source="statement",
                amount="1",
                currency="USD",
                occurred_on=DAY - timedelta(days=30),
                account={"mask": "4321"},
            ),
        ),
    )

    submit(world, shortcuts, tap(shortcuts))
    submit(world, bank, plaid(bank, "txn-p"))
    event = only(world)
    assert sorted(o["source"] for o in event["observations"]) == ["plaid", "shortcuts"]

    submit(
        world,
        gmail,
        cand(
            gmail,
            "msg-1",
            source="gmail",
            evidence="unclassified",
            excerpt="Compra aprobada en CAFE UNO",
        ),
    )
    email = next(
        e
        for e in world.recon.list(user_id=world.user, states=("open",))
        if e["evidence"] == "unclassified"
    )
    assert "kind" in email["unresolved"] and "amount" in email["unresolved"]
    email = world.recon.resolve(
        user_id=world.user,
        event_id=email["id"],
        version=email["version"],
        changes={
            "amount": "12.5",
            "currency": "USD",
            "occurred_on": DAY.isoformat(),
            "account_id": card,
            "kind": "expense",
        },
    )
    assert email["possible_duplicates"] == [event["id"]]
    merged = world.recon.merge(
        user_id=world.user,
        event_id=email["id"],
        into_event_id=event["id"],
        version=email["version"],
        into_version=world.recon.detail(user_id=world.user, event_id=event["id"])[
            "version"
        ],
    )
    assert merged["id"] == event["id"]
    assert sorted(o["source"] for o in merged["observations"]) == [
        "gmail",
        "plaid",
        "shortcuts",
    ]

    result = accept(world, merged, category_id=None)
    activity_id = result["activity"]["activity_id"]
    assert result["activity"]["amount"] == "12.50"

    # The pending row posts, then the statement arrives.
    submit(
        world,
        bank,
        plaid(
            bank,
            "txn-posted",
            status="posted",
            replaces="txn-p",
            posted_on=DAY + timedelta(days=1),
        ),
    )
    submit(
        world,
        statement,
        cand(
            statement,
            "line-7",
            source="statement",
            status="posted",
            amount="12.50",
            currency="USD",
            direction="outflow",
            occurred_on=DAY,
            account={"mask": "4321"},
        ),
    )
    final = only(world, "accepted")
    assert final["id"] == event["id"] and final["activity_id"] == activity_id
    assert final["attention"] is None
    live = sorted((o["source"], o["status"]) for o in final["observations"] if o["live"])
    assert live == [
        ("gmail", "unknown"),
        ("plaid", "posted"),
        ("shortcuts", "unknown"),
        ("statement", "posted"),
    ]
    superseded = [o for o in final["observations"] if not o["live"]]
    assert [(o["source"], o["status"]) for o in superseded] == [("plaid", "pending")]
    assert world.recon.list(user_id=world.user, states=("open",)) == []
    recorded = [a for a in activities(world) if a["amount"] == "12.50"]
    assert [a["activity_id"] for a in recorded] == [activity_id]


def test_equal_amount_and_date_never_merge_distinct_purchases(world):
    card = new_account(world)
    shortcuts, bank = world.connect("shortcuts"), world.connect("plaid")
    link_accounts(
        world,
        card,
        (shortcuts, tap(shortcuts, "s0", amount="1")),
        (bank, plaid(bank, "p0", amount="1")),
    )
    submit(world, shortcuts, tap(shortcuts, "tap-a"), tap(shortcuts, "tap-b"))
    submit(world, bank, plaid(bank, "txn-a"), plaid(bank, "txn-b"))
    open_events = world.recon.list(user_id=world.user, states=("open",))
    assert len(open_events) == 4
    plaid_events = [e for e in open_events if e["observations"][0]["source"] == "plaid"]
    for e in plaid_events:
        assert e["attention"] == "ambiguous_match"
        assert len(e["possible_duplicates"]) == 2
    # Two observations from one source are never merged by a person either.
    a, b = (e for e in open_events if e["observations"][0]["source"] == "shortcuts")
    with pytest.raises(ReconcileError) as caught:
        world.recon.merge(
            user_id=world.user,
            event_id=a["id"],
            into_event_id=b["id"],
            version=a["version"],
            into_version=b["version"],
        )
    assert caught.value.code == "import_merge_same_source"


def test_unconfirmed_account_is_only_a_possible_duplicate(world):
    shortcuts, bank = world.connect("shortcuts"), world.connect("plaid")
    submit(world, shortcuts, tap(shortcuts))
    submit(world, bank, plaid(bank, "txn-1"))
    events = world.recon.list(user_id=world.user, states=("open",))
    assert len(events) == 2
    later = next(e for e in events if e["observations"][0]["source"] == "plaid")
    assert later["attention"] == "possible_duplicate"


def test_redelivery_is_unchanged_and_concurrent_retries_record_once(world):
    bank = world.connect("plaid")
    first = submit(world, bank, plaid(bank, "txn-1"))
    assert (first.recorded, first.unchanged) == (1, 0)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(lambda _: submit(world, bank, plaid(bank, "txn-1")), range(6))
        )
    assert all(r.unchanged == 1 for r in results)
    event = only(world)
    assert len(event["observations"]) == 1 and event["observations"][0]["revisions"] == 1


def test_source_removal_before_review_withdraws_the_draft(world):
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1"))
    result = submit(world, bank, cand(bank, "txn-1", source="plaid", status="removed"))
    assert result.withdrawn == 1
    assert world.recon.list(user_id=world.user, states=("open",)) == []
    gone = only(world, "dismissed")
    with pytest.raises(ReconcileError):
        world.recon.reopen(
            user_id=world.user, event_id=gone["id"], version=gone["version"]
        )


def test_source_change_after_acceptance_flags_but_never_edits_the_record(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-p"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    activity_id = accept(world, event)["activity"]["activity_id"]
    submit(
        world,
        bank,
        plaid(bank, "txn-x", status="posted", amount="15.00", replaces="txn-p"),
    )
    flagged = only(world, "accepted")
    assert flagged["attention"] == "source_changed"
    assert flagged["attention_detail"]["amount"] == {"before": "12.5", "after": "15"}
    detail = MoneyService(world.accounts).detail(
        user_id=world.user, activity_id=activity_id
    )
    assert detail["amount"] == "12.50"
    cleared = world.recon.acknowledge(
        user_id=world.user, event_id=flagged["id"], version=flagged["version"]
    )
    assert cleared["attention"] is None
    submit(world, bank, cand(bank, "txn-x", source="plaid", status="removed"))
    assert only(world, "accepted")["attention"] == "source_removed"
    assert [a["activity_id"] for a in activities(world)] == [activity_id]


def test_acceptance_is_idempotent_and_single_under_concurrency(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    preview = world.recon.preview(user_id=world.user, event_id=event["id"])
    reviewed = MoneyRequest.model_validate(
        preview["preview"]["reviewed_request"]
    ).model_copy(update={"preview_token": preview["preview"]["preview_token"]})

    def attempt(key):
        try:
            return world.recon.accept(
                user_id=world.user,
                event_id=event["id"],
                idempotency_key=key,
                version=event["version"],
                request=reviewed,
            )["activity"]["activity_id"]
        except (ReconcileError, StaleEvent):
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(attempt, [f"k{i}" for i in range(6)]))
    assert len({i for i in ids if i}) == 1
    assert len(activities(world)) == 1
    winner = only(world, "accepted")
    again = world.recon.accept(
        user_id=world.user,
        event_id=event["id"],
        idempotency_key=winner_key(winner, ids),
        version=1,
        request=reviewed,
    )
    assert again["replayed"] is True
    other = reviewed.model_copy(update={"amount": "13"})
    with pytest.raises((IdempotencyConflict, ReconcileError)):
        world.recon.accept(
            user_id=world.user,
            event_id=event["id"],
            idempotency_key=winner_key(winner, ids),
            version=1,
            request=other,
        )
    assert len(activities(world)) == 1


def winner_key(event, ids):
    assert event["activity_id"] in ids
    return next(f"k{i}" for i, value in enumerate(ids) if value)


def test_currency_is_never_guessed_or_converted(world):
    peso = new_account(world, kind="cash", currency="DOP")
    shortcuts = world.connect("shortcuts")
    submit(
        world,
        shortcuts,
        cand(
            shortcuts,
            "t1",
            source="shortcuts",
            amount="500",
            occurred_on=DAY,
            uncertain=frozenset({"currency"}),
        ),
    )
    event = only(world)
    assert "currency" in event["unresolved"]
    with pytest.raises(ReconcileError) as caught:
        world.recon.preview(user_id=world.user, event_id=event["id"])
    assert caught.value.code == "import_unresolved"
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"currency": "USD", "account_id": peso, "kind": "expense"},
    )
    with pytest.raises(ReconcileError) as caught:
        world.recon.preview(user_id=world.user, event_id=event["id"])
    assert caught.value.code == "import_currency_mismatch"


def test_already_recorded_purchase_links_instead_of_recording_twice(world):
    card = new_account(world)
    money = MoneyService(world.accounts)
    request = MoneyRequest(
        kind="expense",
        account_id=card,
        amount="12.50",
        occurred_at=datetime(2026, 9, 18, 15, tzinfo=timezone.utc),
    )
    preview = money.preview(user_id=world.user, request=request)
    manual = money.write(
        user_id=world.user,
        request=MoneyRequest.model_validate(preview["reviewed_request"]).model_copy(
            update={"preview_token": preview["preview_token"]}
        ),
        idempotency_key="manual-1",
    )["activity"]["activity_id"]
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    assert event["existing_activity_matches"] == [manual]
    linked = world.recon.link_activity(
        user_id=world.user,
        event_id=event["id"],
        activity_id=manual,
        version=event["version"],
    )
    assert linked["state"] == "accepted" and linked["activity_id"] == manual
    submit(world, bank, plaid(bank, "txn-2", amount="40"))
    second = only(world)
    with pytest.raises(ReconcileError) as caught:
        world.recon.link_activity(
            user_id=world.user,
            event_id=second["id"],
            activity_id=manual,
            version=second["version"],
        )
    assert caught.value.code == "activity_already_linked"
    assert len(activities(world)) == 1


def test_notices_and_balances_are_evidence_not_activity(world):
    gmail, bank = world.connect("gmail"), world.connect("plaid")
    submit(
        world,
        gmail,
        cand(
            gmail,
            "due-1",
            source="gmail",
            evidence="due_notice",
            due_on=date(2026, 10, 15),
            amount="5000",
            currency="DOP",
        ),
    )
    submit(
        world,
        bank,
        cand(
            bank,
            "bal-1",
            source="plaid",
            evidence="balance",
            balance_scope="available",
            amount="900",
            currency="USD",
        ),
    )
    for event in world.recon.list(user_id=world.user, states=("open",)):
        assert event["unresolved"] == []
        with pytest.raises(ReconcileError) as caught:
            world.recon.preview(user_id=world.user, event_id=event["id"])
        assert caught.value.code == "import_not_activity"
    assert activities(world) == []


def test_disconnect_drops_drafts_and_keeps_recorded_provenance(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1"), plaid(bank, "txn-2", amount="40"))
    first = next(
        e
        for e in world.recon.list(user_id=world.user, states=("open",))
        if e["facts"]["amount"] == "12.5"
    )
    first = world.recon.resolve(
        user_id=world.user,
        event_id=first["id"],
        version=first["version"],
        changes={"account_id": card},
    )
    accept(world, first)
    removed = world.recon.forget_connection(user_id=world.user, connection_id=bank)
    assert removed == 1
    assert world.recon.list(user_id=world.user, states=("open",)) == []
    kept = only(world, "accepted")
    [observation] = kept["observations"]
    assert observation["redacted"] and observation["merchant"] is None
    assert observation["external_id"] == "txn-1"


def test_people_are_isolated(world, other_world):
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1"))
    event = only(world)
    assert other_world.recon.list(user_id=other_world.user, states=("open",)) == []
    from argus.domain.ingestion.reconcile.model import EventNotFound

    with pytest.raises(EventNotFound):
        other_world.recon.detail(user_id=other_world.user, event_id=event["id"])
    with pytest.raises(ValueError):
        world.recon.submit(
            user_id=world.user,
            connection_id=str(uuid4()),
            candidates=[plaid(bank, "txn-2")],
        )


def test_reviewed_batch_records_clear_items_and_returns_exceptions(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "seed", amount="1"))
    [seed] = world.recon.list(user_id=world.user, states=("open",))
    world.recon.resolve(
        user_id=world.user,
        event_id=seed["id"],
        version=seed["version"],
        changes={"account_id": card},
    )
    seed = world.recon.detail(user_id=world.user, event_id=seed["id"])
    world.recon.dismiss(user_id=world.user, event_id=seed["id"], version=seed["version"])
    submit(
        world,
        bank,
        plaid(bank, "a", amount="10"),
        plaid(bank, "b", amount="20"),
        plaid(bank, "c", amount="30", currency=None),
        plaid(bank, "d", amount="40"),
    )
    shortcuts = world.connect("shortcuts")
    submit(
        world, shortcuts, tap(shortcuts, "t", amount="10")
    )  # possible duplicate of "a"
    listed = world.recon.list(user_id=world.user, states=("open",))
    by_amount = {
        e["facts"]["amount"]: e
        for e in listed
        if e["observations"][0]["source"] == "plaid"
    }
    stale_id = by_amount["20"]["id"]
    items = [(e["id"], e["version"] + (9 if e["id"] == stale_id else 0)) for e in listed]
    results = world.recon.accept_batch(
        user_id=world.user, items=items, idempotency_key="batch-1"
    )
    outcome = {r["event_id"]: r for r in results}
    assert outcome[by_amount["40"]["id"]]["outcome"] == "accepted"
    assert outcome[stale_id]["code"] == "stale_version"
    assert outcome[by_amount["30"]["id"]]["code"] == "import_unresolved"
    assert outcome[by_amount["10"]["id"]]["code"] == "import_possible_duplicate"
    assert [r["outcome"] for r in results].count("accepted") == 1
    again = world.recon.accept_batch(
        user_id=world.user, items=items, idempotency_key="batch-1"
    )
    [replayed] = [r for r in again if r["outcome"] == "accepted"]
    assert replayed["replayed"] is True
    assert replayed["activity_id"] == outcome[by_amount["40"]["id"]]["activity_id"]
    assert len(activities(world)) == 1


# --- Review regressions (#772 review) ------------------------------------


def _open(world, source=None, external_id=None):
    events = world.recon.list(user_id=world.user, states=("open",))
    return [
        e
        for e in events
        if (source is None or e["observations"][0]["source"] == source)
        and (external_id is None or e["observations"][0]["external_id"] == external_id)
    ]


def test_reconnected_source_cannot_record_an_accepted_purchase_again(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "txn-1", status="posted"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    accepted = accept(world, event)["activity"]["activity_id"]
    world.disconnect(bank)
    world.recon.forget_connection(user_id=world.user, connection_id=bank)
    again = world.connect("plaid")
    submit(world, again, plaid(again, "txn-1", status="posted"))
    [draft] = _open(world)
    assert draft["possible_duplicates"] == [event["id"]]
    flagged = world.recon.detail(user_id=world.user, event_id=event["id"])
    assert flagged["possible_duplicates"] == [draft["id"]]
    result = world.recon.accept_batch(
        user_id=world.user, items=[(draft["id"], draft["version"])], idempotency_key="b1"
    )
    assert result[0]["outcome"] == "needs_review"
    assert [a["activity_id"] for a in activities(world)] == [accepted]
    merged = world.recon.merge(
        user_id=world.user,
        event_id=draft["id"],
        into_event_id=event["id"],
        version=draft["version"],
        into_version=world.recon.detail(user_id=world.user, event_id=event["id"])[
            "version"
        ],
    )
    assert merged["id"] == event["id"] and merged["state"] == "accepted"


def test_possible_duplicates_are_flagged_on_both_events(world):
    card = new_account(world)
    gmail, bank = world.connect("gmail"), world.connect("plaid")
    link_accounts(world, card, (bank, plaid(bank, "seed", amount="1")))
    submit(
        world,
        gmail,
        cand(
            gmail,
            "m1",
            source="gmail",
            amount="12.50",
            currency="USD",
            occurred_on=DAY,
            account={"mask": "4321"},
        ),
    )
    [first] = _open(world, "gmail")
    submit(world, bank, plaid(bank, "t1", status="posted"))
    [second] = _open(world, "plaid", "t1")
    first = world.recon.detail(user_id=world.user, event_id=first["id"])
    assert second["possible_duplicates"] == [first["id"]]
    assert first["possible_duplicates"] == [second["id"]]
    assert first["attention"] == second["attention"] == "possible_duplicate"
    accept(world, second, key="k-b")
    first = world.recon.detail(user_id=world.user, event_id=first["id"])
    result = world.recon.accept_batch(
        user_id=world.user, items=[(first["id"], first["version"])], idempotency_key="b2"
    )
    assert result[0]["outcome"] == "needs_review"
    # The person says they are different purchases: both sides clear.
    cleared = world.recon.acknowledge(
        user_id=world.user, event_id=first["id"], version=first["version"]
    )
    assert cleared["possible_duplicates"] == [] and cleared["attention"] is None
    second = world.recon.detail(user_id=world.user, event_id=second["id"])
    assert second["possible_duplicates"] == []


def test_match_window_follows_the_date_a_person_supplies(world):
    card = new_account(world)
    gmail, bank = world.connect("gmail"), world.connect("plaid")
    link_accounts(world, card, (bank, plaid(bank, "seed", amount="1")))
    submit(
        world,
        gmail,
        cand(
            gmail,
            "m1",
            source="gmail",
            amount="12.50",
            currency="USD",
            direction="outflow",
            account={"mask": "4321"},
        ),
    )
    [email] = _open(world, "gmail")
    world.recon.resolve(
        user_id=world.user,
        event_id=email["id"],
        version=email["version"],
        changes={"occurred_on": DAY.isoformat(), "account_id": card},
    )
    submit(world, bank, plaid(bank, "t1", status="posted"))
    [posted] = [
        e
        for e in world.recon.list(user_id=world.user, states=("open",))
        if e["observations"][0]["external_id"] in ("t1", "m1")
        and len(e["observations"]) == 2
    ] or [None]
    if posted is None:  # not auto-linked: it must at least be flagged both ways
        [bank_event] = _open(world, "plaid", "t1")
        assert bank_event["possible_duplicates"] == [email["id"]]


def test_removed_then_replaced_evidence_comes_back(world):
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "pend"))
    submit(world, bank, cand(bank, "pend", source="plaid", status="removed"))
    assert _open(world) == []
    submit(world, bank, plaid(bank, "post", status="posted", replaces="pend"))
    [back] = _open(world)
    states = {o["external_id"]: o["live"] for o in back["observations"]}
    assert states == {"pend": False, "post": True}


def test_source_removed_warning_clears_when_evidence_returns(world):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "pend"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    accept(world, event)
    submit(world, bank, cand(bank, "pend", source="plaid", status="removed"))
    assert only(world, "accepted")["attention"] == "source_removed"
    submit(world, bank, plaid(bank, "post", status="posted", replaces="pend"))
    assert only(world, "accepted")["attention"] is None


def test_batch_returns_money_refusals_per_item(world):
    card = new_account(world)
    bank = world.connect("plaid")
    link_accounts(world, card, (bank, plaid(bank, "seed", amount="1")))
    submit(
        world,
        bank,
        plaid(bank, "pay", kind_hint="card_payment", direction="inflow"),
        plaid(bank, "ok", amount="40"),
    )
    payment = next(e for e in _open(world) if e["facts"]["kind"] == "card_payment")
    assert "destination_account_id" in payment["unresolved"]
    items = [(e["id"], e["version"]) for e in _open(world)]
    results = world.recon.accept_batch(
        user_id=world.user, items=items, idempotency_key="b1"
    )
    assert sorted(r["outcome"] for r in results) == ["accepted", "needs_review"]


def test_invalid_resolution_is_refused_before_it_is_stored(world):
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "t1"))
    event = only(world)
    for changes, code in (
        ({"kind": "bogus"}, "kind_invalid"),
        ({"category_id": "nope"}, "category_unknown"),
        ({"time_zone": "Mars/Base"}, "time_zone_unknown"),
    ):
        with pytest.raises(ReconcileError) as caught:
            world.recon.resolve(
                user_id=world.user,
                event_id=event["id"],
                version=event["version"],
                changes=changes,
            )
        assert caught.value.code == code


def test_evidence_arriving_after_disconnect_is_ignored(world):
    shortcuts = world.connect("shortcuts")
    submit(world, shortcuts, tap(shortcuts))
    world.disconnect(shortcuts)
    world.recon.forget_connection(user_id=world.user, connection_id=shortcuts)
    late = submit(world, shortcuts, tap(shortcuts, "tap-late"))
    assert late.recorded == 0 and late.ignored == 1
    assert _open(world) == []


def test_merge_refuses_dismissed_events_and_checks_both_versions(world):
    shortcuts, bank = world.connect("shortcuts"), world.connect("plaid")
    submit(world, shortcuts, tap(shortcuts))
    submit(world, bank, plaid(bank, "t1"))
    tap_event, bank_event = _open(world, "shortcuts")[0], _open(world, "plaid")[0]
    with pytest.raises(StaleEvent):
        world.recon.merge(
            user_id=world.user,
            event_id=tap_event["id"],
            into_event_id=bank_event["id"],
            version=tap_event["version"],
            into_version=bank_event["version"] + 3,
        )
    dismissed = world.recon.dismiss(
        user_id=world.user,
        event_id=bank_event["id"],
        version=world.recon.detail(user_id=world.user, event_id=bank_event["id"])[
            "version"
        ],
    )
    tap_event = world.recon.detail(user_id=world.user, event_id=tap_event["id"])
    with pytest.raises(ReconcileError) as caught:
        world.recon.merge(
            user_id=world.user,
            event_id=tap_event["id"],
            into_event_id=bank_event["id"],
            version=tap_event["version"],
            into_version=dismissed["version"],
        )
    assert caught.value.code == "import_dismissed"


def test_interrupted_acceptance_resumes_without_a_second_record(world, monkeypatch):
    card = new_account(world)
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "t1"))
    event = only(world)
    event = world.recon.resolve(
        user_id=world.user,
        event_id=event["id"],
        version=event["version"],
        changes={"account_id": card},
    )
    preview = world.recon.preview(user_id=world.user, event_id=event["id"])["preview"]
    request = MoneyRequest.model_validate(preview["reviewed_request"]).model_copy(
        update={"preview_token": preview["preview_token"]}
    )
    real_write = world.recon.money.write

    def committed_then_lost(**kwargs):
        real_write(**kwargs)
        raise ConnectionError("response lost after commit")

    monkeypatch.setattr(world.recon.money, "write", committed_then_lost)
    with pytest.raises(ConnectionError):
        world.recon.accept(
            user_id=world.user,
            event_id=event["id"],
            idempotency_key="k1",
            version=event["version"],
            request=request,
        )
    monkeypatch.setattr(world.recon.money, "write", real_write)
    assert (
        world.recon.detail(user_id=world.user, event_id=event["id"])["state"]
        == "accepting"
    )
    # A different key cannot record again; it completes the original instead.
    with pytest.raises(ReconcileError) as caught:
        world.recon.accept(
            user_id=world.user,
            event_id=event["id"],
            idempotency_key="k2",
            version=event["version"],
            request=request,
        )
    assert caught.value.code == "import_already_accepted"
    assert only(world, "accepted")["activity_id"]
    assert len(activities(world)) == 1


def test_linking_waits_while_an_import_is_being_recorded(world):
    card = new_account(world)
    money = MoneyService(world.accounts)
    request = MoneyRequest(
        kind="expense",
        account_id=card,
        amount="40",
        occurred_at=datetime(2026, 9, 18, 15, tzinfo=timezone.utc),
    )
    preview = money.preview(user_id=world.user, request=request)
    manual = money.write(
        user_id=world.user,
        request=MoneyRequest.model_validate(preview["reviewed_request"]).model_copy(
            update={"preview_token": preview["preview_token"]}
        ),
        idempotency_key="manual-40",
    )["activity"]["activity_id"]
    bank = world.connect("plaid")
    submit(world, bank, plaid(bank, "t1"), plaid(bank, "t2", amount="40"))
    first, second = sorted(_open(world), key=lambda e: e["facts"]["amount"])
    from dataclasses import replace

    with world.recon.store.transaction(world.user) as tx:
        tx.put_event(replace(tx.event(first["id"]), state="accepting", accept_key="k"))
    with pytest.raises(ReconcileError) as caught:
        world.recon.link_activity(
            user_id=world.user,
            event_id=second["id"],
            activity_id=manual,
            version=second["version"],
        )
    assert caught.value.code == "import_accept_in_progress"


def test_deleted_events_leave_no_dangling_duplicate_references(world):
    shortcuts, bank = world.connect("shortcuts"), world.connect("plaid")
    submit(world, shortcuts, tap(shortcuts))
    submit(world, bank, plaid(bank, "t1"))
    tap_event = _open(world, "shortcuts")[0]
    bank_event = _open(world, "plaid")[0]
    assert bank_event["possible_duplicates"] == [tap_event["id"]]
    world.disconnect(shortcuts)
    world.recon.forget_connection(user_id=world.user, connection_id=shortcuts)
    bank_event = world.recon.detail(user_id=world.user, event_id=bank_event["id"])
    assert bank_event["possible_duplicates"] == [] and bank_event["attention"] is None
