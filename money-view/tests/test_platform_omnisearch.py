"""Literal, bounded, household-owned recall over source records."""

import json
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.platform import assistant, investing, ledger, omnisearch, planning
from server.platform.common import Context, Evidence, get_context, get_store
from server.store import Store

STAMP = datetime(2026, 9, 21, 12, tzinfo=timezone.utc).isoformat()
AS_OF = date(2026, 9, 18).isoformat()


def source(record_id):
    return Evidence(
        id=record_id,
        kind="synthetic",
        title="Synthetic source",
        as_of=AS_OF,
        recorded_at=STAMP,
    ).model_dump(mode="json")


def add_account(db, record_id, household, name="Orchard cash"):
    db.execute(
        "INSERT INTO p_accounts(id,household_id,owner_id,name,institution,kind,currency,opening_minor,source_kind,recorded_at,as_of) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            record_id,
            household,
            "user-demo",
            name,
            "Orchard bank",
            "checking",
            "USD",
            10000,
            "synthetic",
            STAMP,
            AS_OF,
        ),
    )


def add_transaction(
    db, record_id, household, account_id, merchant="Orchard market", **changes
):
    data = {
        "id": record_id,
        "household_id": household,
        "account_id": account_id,
        "date": AS_OF,
        "merchant": merchant,
        "description": "Orchard supplies",
        "amount_minor": -12345,
        "currency": "USD",
        "category": "groceries",
        "kind": "expense",
        "status": "posted",
        "notes": "Orchard note",
        "source_kind": "synthetic",
        "recorded_at": STAMP,
    }
    data.update(changes)
    db.execute(
        f"INSERT INTO p_transactions({','.join(data)}) VALUES({','.join('?' for _ in data)})",
        tuple(data.values()),
    )


@pytest.fixture
def api(tmp_path):
    store = Store(tmp_path / "recall.sqlite")
    with store.connection(write=True) as db:
        db.executescript(
            ledger.SCHEMA
            + planning.SCHEMA
            + assistant.SCHEMA
            + investing.INVESTING_SCHEMA
        )
        for household in ("household-demo", "household-other"):
            suffix = household.removeprefix("household-")
            add_account(db, f"account-{suffix}", household)
            add_transaction(db, f"transaction-{suffix}", household, f"account-{suffix}")
            db.execute(
                "INSERT INTO p_assistant_conversations VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"conversation-{suffix}",
                    household,
                    "user-demo",
                    "Orchard conversation",
                    "active",
                    1,
                    STAMP,
                    STAMP,
                ),
            )
            db.execute(
                "INSERT INTO p_assistant_messages VALUES(?,?,?,?,?,?)",
                (
                    f"message-{suffix}",
                    household,
                    f"conversation-{suffix}",
                    "user",
                    json.dumps(
                        {
                            "text": "Orchard remembered question",
                            "private_secret": "never-display",
                        }
                    ),
                    STAMP,
                ),
            )
            for kind, document in [
                (
                    "budget",
                    {
                        "category": "Orchard budget",
                        "currency": "USD",
                        "limit": "400",
                        "month": "2026-09",
                    },
                ),
                (
                    "goal",
                    {
                        "name": "Orchard home",
                        "currency": "USD",
                        "target_amount": "12000",
                        "target_date": "2027-01-01",
                    },
                ),
            ]:
                document["evidence"] = source(f"{kind}-source-{suffix}")
                db.execute(
                    "INSERT INTO p_plans VALUES(?,?,?,?,?,?)",
                    (
                        f"{kind}-{suffix}",
                        household,
                        kind,
                        json.dumps(document),
                        "active",
                        STAMP,
                    ),
                )
            db.execute(
                "INSERT INTO p_scenarios VALUES(?,?,?)",
                (
                    f"scenario-{suffix}",
                    household,
                    json.dumps(
                        {
                            "name": "Orchard future",
                            "template": "home",
                            "inputs": {"currency": "USD", "initial_balance": "400"},
                            "evidence": source(f"scenario-source-{suffix}"),
                        }
                    ),
                ),
            )
            db.execute(
                "INSERT INTO p_investment_holdings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"holding-{suffix}",
                    household,
                    "user-demo",
                    "ORCH",
                    "Orchard holding",
                    "2",
                    "10000",
                    "USD",
                    AS_OF,
                    STAMP,
                    STAMP,
                    None,
                    json.dumps(source(f"holding-source-{suffix}")),
                ),
            )
    omnisearch.initialize(store)
    state = {"context": Context("user-demo", "household-demo", "owner", "session-demo")}
    app = FastAPI()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context] = lambda: state["context"]
    app.include_router(omnisearch.router)
    with TestClient(app) as client:
        yield client, store, state


def test_search_covers_domains_and_keeps_dated_source_previews(api):
    client, store, state = api
    response = client.get("/api/platform/search", params={"q": "Orchard"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert {item["kind"] for item in result["items"]} == {
        "conversation",
        "account",
        "transaction",
        "budget",
        "goal",
        "scenario",
        "holding",
    }
    assert len(result["items"]) == 7
    account = next(item for item in result["items"] if item["kind"] == "account")
    assert (
        account["target"]["account_id"]
        == account["target"]["record_id"]
        == "account-demo"
    )
    text = json.dumps(result)
    assert "household-other" not in text and "-other" not in text
    assert (
        "never-display" not in text
        and "user-demo" not in text
        and "household-demo" not in text
    )
    transaction = next(item for item in result["items"] if item["kind"] == "transaction")
    assert transaction["evidence"]["kind"] == "synthetic"
    assert transaction["evidence"]["as_of"] == AS_OF
    assert transaction["recorded_at"] == STAMP
    assert {"label": "amount", "value": "-123.45"} in transaction["fields"]
    conversation = next(
        item for item in result["items"] if item["kind"] == "conversation"
    )
    assert conversation["preview"] == "Orchard remembered question"
    assert conversation["target"]["page"] == "saved"


@pytest.mark.parametrize(
    "query",
    ["%", "_", "' OR 1=1 --", "transaction-other", "private_secret", "never-display"],
)
def test_query_is_literal_not_sql_or_internal_metadata(api, query):
    client, store, state = api
    assert client.get("/api/platform/search", params={"q": query}).json()["items"] == []


@pytest.mark.parametrize(
    "field,query",
    [
        ("merchant", "Orchard"),
        ("description", "Supplies"),
        ("category", "Dining"),
        ("notes", "Weekend"),
    ],
)
def test_declared_transaction_fields_are_searchable(api, field, query):
    client, store, state = api
    with store.connection(write=True) as db:
        add_transaction(
            db, "specific", "household-demo", "account-demo", **{field: f"{query} unique"}
        )
    result = client.get(
        "/api/platform/search", params={"q": query, "kind": "transaction"}
    ).json()
    assert any(item["target"]["record_id"] == "specific" for item in result["items"])


def test_literal_wildcard_characters_can_match_real_record_names(api):
    client, store, state = api
    with store.connection(write=True) as db:
        add_account(db, "percent", "household-demo", "% savings")
        add_account(db, "underscore", "household-demo", "_ reserved")
    for query, expected in [("%", "percent"), ("_", "underscore")]:
        assert [
            item["target"]["record_id"]
            for item in client.get("/api/platform/search", params={"q": query}).json()[
                "items"
            ]
        ] == [expected]


def test_pagination_dedupes_multifield_matches_in_stable_order(api):
    client, store, state = api
    whole = client.get(
        "/api/platform/search", params={"q": "Orchard", "limit": 40}
    ).json()["items"]
    collected = []
    offset = 0
    while True:
        page = client.get(
            "/api/platform/search", params={"q": "Orchard", "limit": 2, "offset": offset}
        ).json()
        collected.extend(page["items"])
        if not page["has_more"]:
            break
        offset = page["next_offset"]
    assert collected == whole
    assert len({item["id"] for item in collected}) == len(collected)
    browse = client.get("/api/platform/search", params={"limit": 40}).json()["items"]
    assert (
        client.get("/api/platform/search", params={"limit": 2, "offset": 2}).json()[
            "items"
        ]
        == browse[2:4]
    )


def test_scope_filters_and_deletion_hide_records(api):
    client, store, state = api
    assert [
        item["kind"]
        for item in client.get("/api/platform/search", params={"scope": "recent"}).json()[
            "items"
        ]
    ] == ["conversation"]
    with store.connection(write=True) as db:
        db.execute(
            "UPDATE p_assistant_conversations SET state='trashed' WHERE household_id='household-demo'"
        )
        db.execute(
            "UPDATE p_accounts SET deleted_at=? WHERE household_id='household-demo'",
            (STAMP,),
        )
        db.execute(
            "UPDATE p_transactions SET deleted_at=? WHERE household_id='household-demo'",
            (STAMP,),
        )
        db.execute(
            "UPDATE p_plans SET status='archived' WHERE household_id='household-demo'"
        )
        db.execute(
            "UPDATE p_investment_holdings SET deleted_at=? WHERE household_id='household-demo'",
            (STAMP,),
        )
    assert (
        client.get("/api/platform/search", params={"scope": "pinned"}).json()["items"]
        == []
    )
    assert {
        item["kind"] for item in client.get("/api/platform/search").json()["items"]
    } == {"scenario"}
    state["context"] = Context("user-other", "household-other", "viewer", "session-other")
    assert (
        len(client.get("/api/platform/search", params={"q": "Orchard"}).json()["items"])
        == 7
    )


@pytest.mark.parametrize(
    "params",
    [
        {"q": "x" * 121},
        {"limit": 41},
        {"limit": 0},
        {"offset": 1001},
        {"offset": -1},
        {"kind": "p_users"},
        {"scope": "deleted"},
    ],
)
def test_request_bounds(api, params):
    client, _, _ = api
    assert client.get("/api/platform/search", params=params).status_code == 422


def test_prefix_and_recent_queries_use_bounded_index_ranges(api):
    client, store, state = api
    with store.connection(write=True) as db:
        for index in range(10000):
            add_transaction(
                db,
                f"bulk-{index:05}",
                "household-demo",
                "account-demo",
                merchant=f"Bulk purchase {index}",
            )
        add_transaction(
            db, "needle", "household-demo", "account-demo", merchant="Needle purchase"
        )
    selected = next(item for item in omnisearch.SOURCES if item.kind == "transaction")
    with store.connection() as db:
        # Fail if the query walks thousands of nonmatching records before LIMIT.
        ticks = [0]

        def budget():
            ticks[0] += 1
            return int(ticks[0] > omnisearch.TRANSACTION_WINDOW * 2)

        db.set_progress_handler(budget, 100)
        assert (
            len(
                omnisearch._read_source(
                    db, selected, "household-demo", "Needle", 21, "all"
                ).rows
            )
            == 1
        )
        assert (
            len(
                omnisearch._read_source(
                    db, selected, "household-demo", "Bulk", 21, "all"
                ).rows
            )
            == 21
        )
        assert (
            len(
                omnisearch._read_source(
                    db, selected, "household-demo", "", 21, "all"
                ).rows
            )
            == 21
        )
        db.set_progress_handler(None, 0)
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM p_transactions INDEXED BY p_omni_transactions_transaction_field0 WHERE household_id=? AND deleted_at IS NULL AND substr(merchant,1,512) COLLATE NOCASE>=? AND substr(merchant,1,512) COLLATE NOCASE<? ORDER BY substr(merchant,1,512) COLLATE NOCASE,id LIMIT 20",
            ("household-demo", "Needle", "Needle\U0010ffff"),
        ).fetchall()
        assert any("SEARCH" in row[3] and "<expr>>?" in row[3] for row in plan)
        assert not any("TEMP B-TREE" in row[3] for row in plan)
    ceiling = client.get(
        "/api/platform/search",
        params={"q": "Bulk", "kind": "transaction", "offset": 1000, "limit": 40},
    ).json()
    assert len(ceiling["items"]) == 40
    assert ceiling["has_more"] and ceiling["window_limited"]
    assert ceiling["next_offset"] is None


def test_owned_saved_deposit_recall_without_cross_household_ids(api):
    client, store, state = api
    with store.connection(write=True) as db:
        for suffix in ["demo", "other"]:
            db.execute(
                "INSERT INTO comparisons VALUES(?,?)",
                (
                    f"comparison-{suffix}",
                    json.dumps(
                        {
                            "inputs": {
                                "country": "DO",
                                "currency": "DOP",
                                "amount": "25000",
                            }
                        }
                    ),
                ),
            )
            db.execute(
                "INSERT INTO p_placement_comparisons VALUES(?,?)",
                (f"comparison-{suffix}", f"household-{suffix}"),
            )
            db.execute(
                "INSERT INTO saved_decisions VALUES(?,?,?)",
                (f"decision-{suffix}", f"comparison-{suffix}", STAMP),
            )
    result = client.get(
        "/api/platform/search", params={"kind": "deposit", "q": "DO"}
    ).json()
    assert len(result["items"]) == 1
    assert result["items"][0]["target"]["decision"] == "decision-demo"
    assert "other" not in json.dumps(result)


def test_new_chat_contract_coexists_with_legacy_and_pins_are_owned(api):
    client, store, state = api
    with store.connection(write=True) as db:
        db.execute(
            "CREATE TABLE p_chat_conversations(id TEXT PRIMARY KEY,household_id TEXT,user_id TEXT,title TEXT,state TEXT,pinned INTEGER,created_at TEXT,updated_at TEXT)"
        )
        db.execute(
            "CREATE TABLE p_chat_messages(id TEXT PRIMARY KEY,household_id TEXT,conversation_id TEXT,turn_id TEXT,role TEXT,document TEXT,created_at TEXT)"
        )
        db.execute(
            "CREATE INDEX p_test_chat_message_window ON p_chat_messages(household_id,conversation_id,created_at,id)"
        )
        for suffix in ("demo", "other"):
            db.execute(
                "INSERT INTO p_chat_conversations VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"new-chat-{suffix}",
                    f"household-{suffix}",
                    "user-demo",
                    "Orchard new conversation",
                    "active",
                    1,
                    STAMP,
                    STAMP,
                ),
            )
            db.execute(
                "INSERT INTO p_chat_messages VALUES(?,?,?,?,?,?,?)",
                (
                    f"new-message-{suffix}",
                    f"household-{suffix}",
                    f"new-chat-{suffix}",
                    "turn",
                    "assistant",
                    json.dumps({"text": "Actual new conversation preview"}),
                    STAMP,
                ),
            )
    omnisearch.initialize(store)
    result = client.get(
        "/api/platform/search",
        params={"kind": "conversation", "q": "Orchard"},
    ).json()
    assert {item["target"]["page"] for item in result["items"]} == {"chat", "saved"}
    pinned = client.get(
        "/api/platform/search",
        params={"kind": "conversation", "scope": "pinned", "q": "Orchard"},
    ).json()["items"]
    assert len(pinned) == 1 and pinned[0]["target"]["page"] == "chat"
    assert pinned[0]["pinned"]
    chat = next(item for item in result["items"] if item["target"]["page"] == "chat")
    assert chat["preview"] == "Actual new conversation preview"
    assert chat["target"]["conversation_id"] == "new-chat-demo"
    assert "-other" not in json.dumps(result)


def test_long_source_fields_are_bounded_and_ties_paginate(api):
    client, store, state = api
    with store.connection(write=True) as db:
        for index in range(6):
            add_transaction(
                db,
                f"long-{index}",
                "household-demo",
                "account-demo",
                merchant="Long name " + ("x" * 1000) + str(index),
                description="y" * 10000,
                notes="z" * 10000,
            )
    whole = client.get(
        "/api/platform/search",
        params={"q": "Long name", "kind": "transaction", "limit": 40},
    ).json()["items"]
    first = client.get(
        "/api/platform/search",
        params={"q": "Long name", "kind": "transaction", "limit": 3},
    ).json()["items"]
    second = client.get(
        "/api/platform/search",
        params={"q": "Long name", "kind": "transaction", "limit": 3, "offset": 3},
    ).json()["items"]
    assert first + second == whole
    assert all(
        len(item["title"]) <= 160 and len(item["preview"]) <= 400 for item in whole
    )
    assert all(len(field["value"]) <= 240 for item in whole for field in item["fields"])


def test_transactions_follow_account_visibility_before_page_window(api):
    client, store, state = api
    with store.connection(write=True) as db:
        add_account(db, "visible-account", "household-demo", "Current account")
        add_transaction(
            db,
            "visible-transaction",
            "household-demo",
            "visible-account",
            merchant="Orchard visible",
            notes="Visible note",
        )
        # Archive only the account. Its child transaction stays otherwise active.
        db.execute("UPDATE p_accounts SET deleted_at=? WHERE id='account-demo'", (STAMP,))
    for query in ("", "Orchard"):
        result = client.get(
            "/api/platform/search", params={"kind": "transaction", "q": query, "limit": 1}
        ).json()
        assert [item["target"]["record_id"] for item in result["items"]] == [
            "visible-transaction"
        ]
        assert not result["has_more"] and result["next_offset"] is None
        assert "transaction-demo" not in json.dumps(result)
        assert "Orchard note" not in json.dumps(result)
    with store.connection(write=True) as db:
        db.execute("UPDATE p_accounts SET deleted_at=NULL WHERE id='account-demo'")
    restored = client.get(
        "/api/platform/search", params={"kind": "transaction", "q": "Orchard"}
    ).json()
    assert {item["target"]["record_id"] for item in restored["items"]} == {
        "visible-transaction",
        "transaction-demo",
    }


def test_historical_budget_target_keeps_record_identity_not_copied_filters(api):
    client, store, state = api
    previous = {
        "category": "Historical groceries",
        "currency": "JPY",
        "limit": "4000",
        "month": "2025-07",
        "evidence": source("old-budget-source"),
    }
    with store.connection(write=True) as db:
        db.execute(
            "INSERT INTO p_plans VALUES(?,?,?,?,?,?)",
            (
                "older-budget",
                "household-demo",
                "budget",
                json.dumps(previous),
                "active",
                STAMP,
            ),
        )
    result = client.get(
        "/api/platform/search", params={"kind": "budget", "q": "Historical"}
    ).json()["items"]
    assert len(result) == 1
    assert result[0]["target"]["page"] == "budgets"
    assert result[0]["target"]["record_id"] == "older-budget"
    assert {"label": "month", "value": previous["month"]} in result[0]["fields"]
    assert {"label": "currency", "value": previous["currency"]} in result[0]["fields"]
    assert "month" not in result[0]["target"] and "currency" not in result[0]["target"]


@pytest.mark.parametrize("query", ["", "Hidden"])
def test_archived_parent_candidate_work_stays_fixed_as_history_grows(api, query):
    client, store, _ = api
    selected = next(item for item in omnisearch.SOURCES if item.kind == "transaction")
    with store.connection(write=True) as db:
        db.execute("UPDATE p_accounts SET deleted_at=? WHERE id='account-demo'", (STAMP,))
    measurements = []
    previous = 0
    for size in (omnisearch.TRANSACTION_WINDOW * 2, omnisearch.TRANSACTION_WINDOW * 10):
        with store.connection(write=True) as db:
            for index in range(previous, size):
                add_transaction(
                    db,
                    f"hidden-{index:08}",
                    "household-demo",
                    "account-demo",
                    merchant="Hidden merchant",
                    description="Hidden description",
                    category="Hidden category",
                    notes="Hidden private note",
                )
        previous = size
        with store.connection() as db:
            ticks = [0]

            def budget(ticks=ticks):
                ticks[0] += 1
                return int(ticks[0] > omnisearch.TRANSACTION_WINDOW * 3)

            db.set_progress_handler(budget, 100)
            result = omnisearch._read_source(
                db, selected, "household-demo", query, 21, "all"
            )
            db.set_progress_handler(None, 0)
            assert not result.rows and result.limited
            measurements.append(ticks[0] * 100)
        payload = client.get(
            "/api/platform/search", params={"q": query, "kind": "transaction"}
        ).json()
        assert payload["items"] == [] and payload["window_limited"]
        assert not payload["has_more"] and payload["next_offset"] is None
        assert "hidden-" not in json.dumps(payload) and "private note" not in json.dumps(
            payload
        )
    # Tail size models the five-million-row shape: after the indexed window is
    # full, adding more archived children does not add parent probes or VM work.
    assert measurements[1] <= measurements[0] + 1000


def test_transaction_candidate_window_preserves_visible_pagination(api):
    client, store, _ = api
    with store.connection(write=True) as db:
        add_account(db, "archived-account", "household-demo")
        db.execute(
            "UPDATE p_accounts SET deleted_at=? WHERE id='archived-account'", (STAMP,)
        )
        for index in range(omnisearch.TRANSACTION_WINDOW + 5):
            add_transaction(
                db,
                f"window-{index:05}",
                "household-demo",
                "account-demo" if index % 2 else "archived-account",
                merchant="Window merchant",
                description="",
                category="",
                notes="",
            )

    def read(offset, limit):
        return client.get(
            "/api/platform/search",
            params={
                "q": "Window",
                "kind": "transaction",
                "offset": offset,
                "limit": limit,
            },
        ).json()

    first, second, combined = read(0, 10), read(10, 10), read(0, 20)
    assert first["items"] + second["items"] == combined["items"]
    assert first["next_offset"] == 10 and second["next_offset"] == 20
    assert all(value["window_limited"] for value in (first, second, combined))
    assert all(
        int(item["target"]["record_id"].split("-")[1]) % 2 for item in combined["items"]
    )
