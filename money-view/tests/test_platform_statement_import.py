"""Statement intake preserves the reviewed intent at the ledger boundary."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
import test_platform_ledger as ledger_fixtures
from platform_identity_factory import identity_context
from server.platform import ledger
from server.platform.common import PlatformError, get_context
from server.platform.ledger_contracts import ImportCommit
from server.platform.statement_parser import DEFAULT_LIMITS, parse_delimited

client = ledger_fixtures.client
seeded = ledger_fixtures.seeded
store = ledger_fixtures.store


def statement(content=None, **changes):
    payload = {
        "account_id": "acct-demo-01",
        "mode": "statement",
        "csv": content
        or "Fecha;Comercio;Debe;Haber;Referencia\n20/09/2026;Statement market;12,50;;bank-1\n",
        "delimiter": ";",
        "date_format": "DMY",
        "decimal_separator": ",",
        "mapping": {
            "date": "Fecha",
            "merchant": "Comercio",
            "debit": "Debe",
            "credit": "Haber",
            "source_id": "Referencia",
        },
    }
    payload.update(changes)
    return payload


def test_statement_mapping_preview_is_inert_then_commits_once(client):
    before = Decimal(client.get("/api/platform/accounts/acct-demo-01").json()["balance"])
    response = client.post("/api/platform/imports/preview", json=statement())
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["rows"][0]["amount"] == "-12.50"
    assert preview["rows"][0]["date"] == "2026-09-20"
    assert preview["rows"][0]["currency"] == "USD"
    assert (
        Decimal(client.get("/api/platform/accounts/acct-demo-01").json()["balance"])
        == before
    )
    body = {
        "idempotency_key": "mapped-import",
        "preview_digest": preview["preview_digest"],
        "decisions": [],
    }
    path = f"/api/platform/imports/{preview['id']}/commit"
    receipt = client.post(path, json=body)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["imported"] == 1
    assert client.post(path, json=body).json() == receipt.json()
    assert Decimal(
        client.get("/api/platform/accounts/acct-demo-01").json()["balance"]
    ) == before - Decimal("12.50")


def test_identical_purchases_require_choice_and_can_both_be_imported(client):
    payload = statement(
        "Date,Merchant,Amount\n2026-09-20,Same purchase,-8.25\n2026-09-20,Same purchase,-8.25\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={"date": "Date", "merchant": "Merchant", "amount": "Amount"},
    )
    response = client.post("/api/platform/imports/preview", json=payload)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["review_count"] == 1
    body = {
        "idempotency_key": "two-purchases",
        "preview_digest": preview["preview_digest"],
    }
    path = f"/api/platform/imports/{preview['id']}/commit"
    assert client.post(path, json=body).json()["code"] == "import_review_required"
    body["decisions"] = [{"line": preview["rows"][1]["line"], "action": "import"}]
    result = client.post(path, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 2


def commit_body(preview, **extra):
    return {
        "idempotency_key": "statement-confirm",
        "preview_digest": preview["preview_digest"],
        **extra,
    }


def test_column_inspection_has_no_persisted_preview(client, store):
    with store.connection() as db:
        before = db.execute("SELECT COUNT(*) FROM p_imports").fetchone()[0]
    response = client.post("/api/platform/imports/preview", json=statement(mapping=None))
    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "mapping"
    assert response.json()["headers"] == [
        "Fecha",
        "Comercio",
        "Debe",
        "Haber",
        "Referencia",
    ]
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM p_imports").fetchone()[0] == before


@pytest.mark.parametrize(
    "content,code",
    [
        ('a,b\n"unfinished,b', "invalid_csv_quoting"),
        ('a,b\nplain"quote,b', "invalid_csv_quoting"),
        ('a,b\n"quoted"extra,b', "invalid_csv_quoting"),
        ("a,b\nzero\x00,b", "invalid_file_content"),
        ("a,b\n\ufffd,b", "invalid_file_content"),
        ("a,a\nx,y", "invalid_csv_headers"),
        (
            "a,b\n" + ("x" * (DEFAULT_LIMITS.max_cell_chars + 1)) + ",y",
            "import_cell_too_large",
        ),
        (
            ",".join(str(n) for n in range(DEFAULT_LIMITS.max_columns + 1)),
            "import_too_many_columns",
        ),
        ("a\n" + "é" * (DEFAULT_LIMITS.max_bytes // 2), "import_too_large"),
    ],
)
def test_parser_rejects_bounded_hostile_input(content, code):
    with pytest.raises(PlatformError) as caught:
        parse_delimited(content)
    assert caught.value.code == code


def test_invalid_and_blank_rows_count_toward_limit():
    limits = replace(DEFAULT_LIMITS, max_rows=3)
    for row in ["bad,bad,bad\n", "\n"]:
        with pytest.raises(PlatformError, match="import_too_many_rows"):
            parse_delimited("a,b\n" + row * (limits.max_rows + 1), limits=limits)


def test_quoted_multiline_and_tab_are_literal_data():
    table = parse_delimited(
        'a\tb\r\n"line one\nline two"\t"=HYPERLINK(https://example.invalid)"\r\n',
        delimiter="\t",
    )
    assert table.rows[0].cells == (
        "line one\nline two",
        "=HYPERLINK(https://example.invalid)",
    )


@pytest.mark.parametrize(
    "currency,amount,status",
    [
        ("JPY", "12", 200),
        ("JPY", "12.5", 422),
        ("KWD", "12.345", 200),
        ("KWD", "12.3456", 422),
    ],
)
def test_statement_currency_precision_is_owned_by_account(
    client, currency, amount, status
):
    account = client.post(
        "/api/platform/accounts",
        json={
            "name": "Statement precision",
            "kind": "cash",
            "currency": currency,
            "opening_balance": "0",
            "idempotency_key": "precision-account",
        },
    ).json()
    payload = statement(
        f"Date,Merchant,Amount\n2026-09-20,Precision,-{amount}\n",
        account_id=account["id"],
        delimiter=",",
        decimal_separator=".",
        date_format="YMD",
        mapping={"date": "Date", "merchant": "Merchant", "amount": "Amount"},
    )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    result = client.post(
        f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
    )
    assert result.status_code == status, result.text
    if status == 200:
        assert (
            client.get(f"/api/platform/accounts/{account['id']}").json()["balance"]
            == f"-{amount}"
        )
    else:
        assert preview["errors"][0]["code"] == "invalid_money_precision"


@pytest.mark.parametrize(
    "row,expected",
    [
        ("09/20/2026;Date mismatch;12,50;;bank-1", "invalid_statement_date"),
        ("20/09/2026;Both sides;12,50;3,00;bank-1", "invalid_debit_credit"),
        ("20/09/2026;Grouping;1.234,50;;bank-1", "invalid_statement_amount"),
        ("20/09/2026;Money in;;50,00;bank-1", "statement_positive_kind_required"),
    ],
)
def test_ambiguous_values_prevent_all_writes(client, row, expected):
    preview = client.post(
        "/api/platform/imports/preview",
        json=statement("Fecha;Comercio;Debe;Haber;Referencia\n" + row + "\n"),
    ).json()
    assert preview["errors"][0]["code"] == expected
    assert not preview["can_commit"]


def test_exact_source_id_reimport_skips_and_changed_source_flags_conflict(client):
    preview = client.post("/api/platform/imports/preview", json=statement()).json()
    assert (
        client.post(
            f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
        ).json()["imported"]
        == 1
    )
    again = client.post("/api/platform/imports/preview", json=statement()).json()
    assert again["duplicate_count"] == 1
    assert again["review_count"] == 0
    changed = client.post(
        "/api/platform/imports/preview",
        json=statement(statement()["csv"].replace("12,50", "15,00")),
    ).json()
    assert changed["errors"][0]["code"] == "source_transaction_changed"
    assert not changed["can_commit"]


def test_confirmed_duplicate_choice_is_immutable(client):
    payload = statement(
        "Date,Merchant,Amount\n2026-09-20,Purchase,-8.25\n2026-09-20,Purchase,-8.25\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={"date": "Date", "merchant": "Merchant", "amount": "Amount"},
    )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    path = f"/api/platform/imports/{preview['id']}/commit"
    body = commit_body(preview, decisions=[{"line": 3, "action": "skip"}])
    assert client.post(path, json=body).json()["imported"] == 1
    body["decisions"][0]["action"] = "import"
    assert client.post(path, json=body).status_code == 409
    body["idempotency_key"] = "different-key"
    assert client.post(path, json=body).json()["code"] == "import_decisions_changed"


def test_expiry_and_digest_prevent_stale_confirmation(client, monkeypatch):
    preview = client.post("/api/platform/imports/preview", json=statement()).json()
    path = f"/api/platform/imports/{preview['id']}/commit"
    assert (
        client.post(path, json=commit_body(preview, preview_digest="0" * 64)).json()[
            "code"
        ]
        == "import_preview_changed"
    )
    expired = ledger.now() + ledger.IMPORT_EXPIRY + timedelta(seconds=1)
    monkeypatch.setattr(ledger, "now", lambda: expired)
    assert (
        client.post(path, json=commit_body(preview)).json()["code"]
        == "import_preview_expired"
    )


def test_concurrent_confirmation_has_one_receipt_and_provenance(client, store):
    preview = client.post("/api/platform/imports/preview", json=statement()).json()
    context = identity_context(store)
    command = ImportCommit(**commit_body(preview))
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(
            pool.map(
                lambda _: ledger.commit_import(preview["id"], command, store, context),
                range(4),
            )
        )
    assert all(receipt == receipts[0] for receipt in receipts)
    with store.connection() as db:
        rows = db.execute(
            "SELECT * FROM p_import_rows WHERE import_id=?", (preview["id"],)
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["transaction_id"] == receipts[0]["transaction_ids"][0]


@pytest.mark.parametrize(
    "change,code",
    [
        ("role", "household_access_changed"),
        ("generation", "household_data_changed"),
        ("account", "account_not_found"),
    ],
)
def test_authority_and_account_changes_between_preview_and_commit(
    client, store, change, code
):
    preview = client.post("/api/platform/imports/preview", json=statement()).json()
    captured = identity_context(store)
    client.app.dependency_overrides[get_context] = lambda: captured
    with store.connection(write=True) as db:
        if change == "role":
            db.execute(
                "UPDATE p_memberships SET role='viewer' WHERE household_id=? AND user_id=?",
                (captured.household_id, captured.user_id),
            )
        elif change == "generation":
            db.execute(
                "INSERT INTO p_household_generations(household_id,generation) VALUES(?,1) ON CONFLICT(household_id) DO UPDATE SET generation=generation+1",
                (captured.household_id,),
            )
        else:
            db.execute(
                "UPDATE p_accounts SET deleted_at='2026-09-20' WHERE id=?",
                ("acct-demo-01",),
            )
    assert (
        client.post(
            f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
        ).json()["code"]
        == code
    )


def test_parsing_does_not_hold_the_writer_lock(client, store, monkeypatch):
    original = ledger.parse_delimited

    def observe(*args, **kwargs):
        with store.connection(write=True) as db:
            assert db.execute("SELECT 1").fetchone()[0] == 1
        return original(*args, **kwargs)

    monkeypatch.setattr(ledger, "parse_delimited", observe)
    assert (
        client.post("/api/platform/imports/preview", json=statement()).status_code == 200
    )


def test_distinct_bank_ids_preserve_identical_purchases(client):
    content = statement()["csv"]
    content += content.splitlines()[1].replace("bank-1", "bank-2") + "\n"
    preview = client.post("/api/platform/imports/preview", json=statement(content)).json()
    assert preview["review_count"] == 0
    assert preview["duplicate_count"] == 0
    receipt = client.post(
        f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
    ).json()
    assert receipt["imported"] == 2


def test_concurrent_new_content_match_requires_new_review(client):
    payload = statement(
        "Date,Merchant,Amount\n2026-09-20,Concurrent purchase,-7.50\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={"date": "Date", "merchant": "Merchant", "amount": "Amount"},
    )
    first = client.post("/api/platform/imports/preview", json=payload).json()
    second = client.post("/api/platform/imports/preview", json=payload).json()
    assert (
        client.post(
            f"/api/platform/imports/{first['id']}/commit", json=commit_body(first)
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/platform/imports/{second['id']}/commit",
        json=commit_body(second, idempotency_key="second-confirm"),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "import_preview_changed"


@pytest.mark.parametrize("filename", ["statement.pdf", "statement.xlsx", "photo.png"])
def test_unsupported_files_are_rejected_before_inspection(client, filename):
    response = client.post(
        "/api/platform/imports/preview", json=statement(file_name=filename, mapping=None)
    )
    assert response.json()["code"] == "unsupported_statement_file"


def test_tsv_header_mapping_and_explicit_money_in_kind(client):
    content = "Bank export\nDate\tPayee\tValue\n09/20/2026\tStatement salary\t1200.50\n"
    payload = statement(
        content,
        delimiter="\t",
        header_row=2,
        date_format="MDY",
        decimal_separator=".",
        positive_kind="income",
        mapping={"date": "Date", "merchant": "Payee", "amount": "Value"},
    )
    response = client.post("/api/platform/imports/preview", json=payload)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["rows"][0]["kind"] == "income"
    assert preview["rows"][0]["date"] == "2026-09-20"
    assert (
        client.post(
            f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
        ).json()["imported"]
        == 1
    )


@pytest.mark.parametrize("previous_source", ["statement", "manual", "legacy"])
@pytest.mark.parametrize("decision", ["import", "skip"])
def test_new_bank_reference_still_reviews_unknown_provenance(
    client, previous_source, decision
):
    content = (
        "Date,Merchant,Amount,Reference\n2026-09-20,Review duplicate,-8.25,bank-ref-1\n"
    )
    payload = statement(
        content,
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={
            "date": "Date",
            "merchant": "Merchant",
            "amount": "Amount",
            "source_id": "Reference",
        },
    )
    if previous_source == "manual":
        assert (
            client.post(
                "/api/platform/transactions",
                json={
                    "account_id": payload["account_id"],
                    "date": "2026-09-20",
                    "merchant": "Review duplicate",
                    "description": "",
                    "amount": "-8.25",
                    "category": "other",
                    "kind": "expense",
                    "idempotency_key": "previous",
                },
            ).status_code
            == 200
        )
    else:
        initial_payload = (
            {
                **payload,
                "mapping": {"date": "Date", "merchant": "Merchant", "amount": "Amount"},
            }
            if previous_source == "statement"
            else {
                "account_id": payload["account_id"],
                "csv": "date,merchant,description,amount,currency,category,kind\n2026-09-20,Review duplicate,,-8.25,USD,other,expense\n",
            }
        )
        first = client.post("/api/platform/imports/preview", json=initial_payload).json()
        assert (
            client.post(
                f"/api/platform/imports/{first['id']}/commit",
                json=commit_body(first, idempotency_key="previous"),
            ).status_code
            == 200
        )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    assert preview["rows"][0]["duplicate_status"] == "possible"
    assert preview["review_count"] == 1
    path = f"/api/platform/imports/{preview['id']}/commit"
    assert (
        client.post(path, json=commit_body(preview)).json()["code"]
        == "import_review_required"
    )
    assert client.post(
        path, json=commit_body(preview, decisions=[{"line": 2, "action": decision}])
    ).json()["imported"] == (1 if decision == "import" else 0)


@pytest.mark.parametrize("identified_first", [False, True])
def test_mixed_identified_and_unknown_rows_are_reviewed_in_either_order(
    client, identified_first
):
    rows = ["2026-09-20,Same row,-1.25,", "2026-09-20,Same row,-1.25,bank-reference"]
    if identified_first:
        rows.reverse()
    payload = statement(
        "Date,Merchant,Amount,Reference\n" + "\n".join(rows) + "\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={
            "date": "Date",
            "merchant": "Merchant",
            "amount": "Amount",
            "source_id": "Reference",
        },
    )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    assert preview["review_count"] == 1
    assert preview["rows"][1]["duplicate_status"] == "possible"


def test_new_reference_commit_detects_concurrent_unknown_provenance(client):
    payload = statement(
        "Date,Merchant,Amount,Reference\n2026-09-20,Before race,-2.00,unique-first\n2026-09-20,Raced purchase,-1.50,new-reference\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={
            "date": "Date",
            "merchant": "Merchant",
            "amount": "Amount",
            "source_id": "Reference",
        },
    )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    unknown = client.post(
        "/api/platform/imports/preview",
        json={
            **payload,
            "csv": "Date,Merchant,Amount,Reference\n2026-09-20,Raced purchase,-1.50,new-reference\n",
            "mapping": {"date": "Date", "merchant": "Merchant", "amount": "Amount"},
        },
    ).json()
    assert (
        client.post(
            f"/api/platform/imports/{unknown['id']}/commit",
            json=commit_body(unknown, idempotency_key="racer"),
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "import_preview_changed"

    assert client.get("/api/platform/transactions?q=Before%20race").json()["total"] == 0


@pytest.mark.parametrize("persisted_unknown", [False, True])
@pytest.mark.parametrize("decision", ["import", "skip"])
def test_repeated_source_group_keeps_preview_decision(
    client, store, persisted_unknown, decision
):
    payload = statement(
        "Date,Merchant,Amount,Reference\n2026-09-20,Repeated bank ref,-8.25,bank-ref-1\n2026-09-20,Repeated bank ref,-8.25,bank-ref-1\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={
            "date": "Date",
            "merchant": "Merchant",
            "amount": "Amount",
            "source_id": "Reference",
        },
    )
    unknown = "2026-09-20,Repeated bank ref,-8.25,\n"
    if persisted_unknown:
        initial = client.post(
            "/api/platform/imports/preview",
            json={**payload, "csv": "Date,Merchant,Amount,Reference\n" + unknown},
        ).json()
        assert (
            client.post(
                f"/api/platform/imports/{initial['id']}/commit",
                json=commit_body(initial, idempotency_key="initial"),
            ).status_code
            == 200
        )
    else:
        payload["csv"] = payload["csv"].replace("Reference\n", "Reference\n" + unknown)
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    assert [row["duplicate_status"] for row in preview["rows"]] == (
        ["possible", "exact"] if persisted_unknown else ["new", "possible", "exact"]
    )
    reviewed_line = next(
        row["line"] for row in preview["rows"] if row["duplicate_status"] == "possible"
    )
    body = commit_body(preview, decisions=[{"line": reviewed_line, "action": decision}])
    path = f"/api/platform/imports/{preview['id']}/commit"
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["imported"] == int(not persisted_unknown) + int(decision == "import")
    assert receipt["duplicates"] == len(preview["rows"]) - receipt["imported"]
    assert client.post(path, json=body).json() == receipt
    with store.connection() as connection:
        retained = connection.execute(
            "SELECT source_id FROM p_import_rows WHERE import_id=? AND source_id IS NOT NULL",
            (preview["id"],),
        ).fetchall()
    assert [row["source_id"] for row in retained] == (
        ["bank-ref-1"] if decision == "import" else []
    )
    next_preview = client.post("/api/platform/imports/preview", json=payload).json()
    source_row = next(row for row in next_preview["rows"] if row["source_id"])
    assert source_row["duplicate_status"] == (
        "exact" if decision == "import" else "possible"
    )


@pytest.mark.parametrize("persisted_source", ["absent", None, "A"])
def test_all_mixed_sequences_preserve_every_review_choice(persisted_source):
    from itertools import product

    from server.platform.statement_identity import Identity, resolve_sequence

    fingerprint = ("2026-09-20", "Sequence purchase", "", -825, "USD")
    existing = (
        []
        if persisted_source == "absent"
        else [Identity("record:old", fingerprint, persisted_source)]
    )
    for references in product([None, "A", "B"], repeat=4):
        candidates = [
            Identity(f"line:{index + 2}", fingerprint, source)
            for index, source in enumerate(references)
        ]
        preview = resolve_sequence(candidates, existing)
        first_reference = (
            {persisted_source: "record:old"}
            if persisted_source not in (None, "absent")
            else {}
        )
        for candidate, row in zip(candidates, preview, strict=True):
            if candidate.source_id in first_reference:
                assert row.duplicate_status == "exact"
                assert row.duplicate_of == first_reference[candidate.source_id]
            elif candidate.source_id:
                assert row.duplicate_status != "exact"
                first_reference[candidate.source_id] = candidate.key
        possible = [
            candidate.key
            for candidate, row in zip(candidates, preview, strict=True)
            if row.duplicate_status == "possible"
        ]
        for choices in product(["import", "skip"], repeat=len(possible)):
            decisions = dict(zip(possible, choices, strict=True))
            confirmed = resolve_sequence(
                candidates, existing, frozen=preview, decisions=decisions
            )
            approved = [
                candidate
                for candidate, row in zip(candidates, preview, strict=True)
                if row.duplicate_status == "new"
                or (
                    row.duplicate_status == "possible"
                    and decisions[candidate.key] == "import"
                )
            ]
            retained = [
                candidate
                for candidate, row in zip(candidates, confirmed, strict=True)
                if row.action == "import"
            ]
            assert all(row.error is None for row in confirmed)
            assert retained == approved
            references_retained = [item.source_id for item in retained if item.source_id]
            assert len(references_retained) == len(set(references_retained))


@pytest.mark.parametrize("decision", ["import", "skip"])
def test_another_unknown_match_after_review_requires_refresh_only_for_import(
    client, decision
):
    transaction = {
        "account_id": "acct-demo-01",
        "date": "2026-09-20",
        "merchant": "Reviewed race",
        "description": "",
        "amount": "-8.25",
        "category": "other",
        "kind": "expense",
    }
    assert (
        client.post(
            "/api/platform/transactions",
            json={**transaction, "idempotency_key": "first-unknown"},
        ).status_code
        == 200
    )
    payload = statement(
        "Date,Merchant,Amount,Reference\n2026-09-20,Reviewed race,-8.25,reference\n2026-09-20,Reviewed race,-8.25,reference\n",
        delimiter=",",
        date_format="YMD",
        decimal_separator=".",
        mapping={
            "date": "Date",
            "merchant": "Merchant",
            "amount": "Amount",
            "source_id": "Reference",
        },
    )
    preview = client.post("/api/platform/imports/preview", json=payload).json()
    assert [row["duplicate_status"] for row in preview["rows"]] == ["possible", "exact"]
    assert (
        client.post(
            "/api/platform/transactions",
            json={**transaction, "idempotency_key": "second-unknown"},
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/platform/imports/{preview['id']}/commit",
        json=commit_body(preview, decisions=[{"line": 2, "action": decision}]),
    )
    if decision == "import":
        assert response.status_code == 409
        assert response.json()["code"] == "import_preview_changed"
    else:
        assert response.status_code == 200, response.text
        assert response.json()["imported"] == 0
        assert response.json()["duplicates"] == 2
    assert client.get("/api/platform/transactions?q=Reviewed%20race").json()["total"] == 2


def test_statement_preview_from_previous_identity_policy_requires_refresh(client, store):
    import json

    preview = client.post("/api/platform/imports/preview", json=statement()).json()
    previous = {key: value for key, value in preview.items() if key != "identity_version"}
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_imports SET document=? WHERE id=?",
            (json.dumps(previous), preview["id"]),
        )
    response = client.post(
        f"/api/platform/imports/{preview['id']}/commit", json=commit_body(preview)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "import_preview_changed"
