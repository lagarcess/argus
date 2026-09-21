"""Concurrent snapshot and local recovery behavior at the storage boundary."""

import json
import sqlite3
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.platform import investing
from server.platform.identity import DEMO_PASSWORD
from server.platform.storage_ops import backup_database, restore_database
from server.store import Store

fake = Faker()


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "clara.sqlite3", busy_timeout_ms=100)
    with value.connection(write=True) as db:
        db.execute("CREATE TABLE counter (value INTEGER NOT NULL)")
        db.execute("INSERT INTO counter VALUES(0)")
    return value


def read_counter(store):
    with store.connection() as db:
        return db.execute("SELECT value FROM counter").fetchone()[0]


def increment(store):
    with store.connection(write=True) as db:
        db.execute("UPDATE counter SET value=value+1")


def test_wal_readers_keep_snapshot_while_writer_commits(store):
    readers_ready = Barrier(4)
    writer_done = Barrier(4)

    def reader():
        with store.read_snapshot():
            before = read_counter(store)
            readers_ready.wait(timeout=5)
            writer_done.wait(timeout=5)
            return before, read_counter(store)

    with ThreadPoolExecutor(max_workers=3) as pool:
        readers = [pool.submit(reader) for _ in range(3)]
        readers_ready.wait(timeout=5)
        increment(store)
        writer_done.wait(timeout=5)
        assert [future.result(timeout=5) for future in readers] == [(0, 0)] * 3
    assert read_counter(store) == 1
    with store.connection() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == store.busy_timeout_ms


def test_writer_wait_is_bounded_and_failed_write_rolls_back(store):
    with store.connection(write=True):
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(increment, store)
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                future.result(timeout=2)
        assert 0.05 <= time.monotonic() - started < 2
    with pytest.raises(ValueError, match="abort"):
        with store.connection(write=True) as db:
            db.execute("UPDATE counter SET value=7")
            raise ValueError("abort")
    assert read_counter(store) == 0
    increment(store)
    assert read_counter(store) == 1


def test_snapshot_is_nested_read_only_path_scoped_and_cleared(store, tmp_path):
    same_path = Store(store.path)
    other = Store(tmp_path / "other.sqlite3")
    with store.read_snapshot() as snapshot:
        with same_path.connection() as nested:
            assert nested is snapshot
        with store.read_snapshot() as nested:
            assert nested is snapshot
        with pytest.raises(RuntimeError, match="Cannot write"):
            increment(store)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            snapshot.execute("UPDATE counter SET value=5")
        with other.connection(write=True) as db:
            db.execute("INSERT INTO datasets VALUES(?,?,?)", (fake.uuid4(), "US", "{}"))
    with pytest.raises(ValueError):
        with store.read_snapshot():
            raise ValueError("abort read")
    increment(store)
    assert read_counter(store) == 1


def test_portfolio_composition_keeps_cash_and_order_in_one_snapshot(store, monkeypatch):
    context = identity_context(store)
    investing.initialize(store)
    monkeypatch.setattr(investing, "_linked_investment_accounts", lambda *_: [])
    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd", side="buy", symbol="AAPL", quantity="1"
        ),
    )
    before = investing.portfolio_summary(store, context)
    original_list_books = investing.list_books

    def read_books_then_trade(value, owner):
        books = original_list_books(value, owner)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(
                investing.confirm_order, store, context, preview["id"], fake.uuid4()
            ).result(timeout=5)
        return books

    with monkeypatch.context() as patch:
        patch.setattr(investing, "list_books", read_books_then_trade)
        during = investing.portfolio_summary(store, context)
    after = investing.portfolio_summary(store, context)
    assert during["simulation"] == before["simulation"]
    assert after["simulation"]["books"] != before["simulation"]["books"]
    assert len(after["simulation"]["recent_orders"]) == 1


def test_online_backup_copies_committed_wal_and_restores_new_private_file(
    store, tmp_path
):
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "recovered.sqlite3"
    with store.connection(write=True) as db:
        db.execute("UPDATE counter SET value=9")
        # The backup must see committed data while a writer has uncommitted data.
        manifest = backup_database(store.path, backup)
    restored_manifest = restore_database(backup, restored)
    assert read_counter(Store(restored)) == 0
    assert read_counter(store) == 9
    assert restored_manifest["row_counts"] == manifest["row_counts"]
    for path in (backup, restored, tmp_path / "backup.sqlite3.manifest.json"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_backup_restore_preserves_credentials_sessions_and_household_ownership(tmp_path):
    source = tmp_path / "source.sqlite3"
    app = create_app(source, interpreter=FixtureInterpreter())
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/platform/session/login",
                json={"user_id": "user-demo", "password": DEMO_PASSWORD},
            ).status_code
            == 200
        )
        session = client.get("/api/platform/session").json()
        preview = client.post(
            "/api/platform/investing/orders/preview",
            json={
                "book_id": "book-demo-usd",
                "side": "buy",
                "symbol": "AAPL",
                "quantity": "1",
            },
        )
        assert preview.status_code == 200
        receipt = client.post(
            f"/api/platform/investing/orders/{preview.json()['id']}/confirm",
            json={"idempotency_key": fake.uuid4()},
        )
        assert receipt.status_code == 200
        portfolio = client.get("/api/platform/investing/portfolio").json()
        assert portfolio["simulation"]["recent_orders"][0]["id"] == receipt.json()["id"]
        backup = tmp_path / "backup.sqlite3"
        manifest = backup_database(source, backup)
        restored = tmp_path / "restored.sqlite3"
        restore_database(backup, restored)
        with sqlite3.connect(source) as original, sqlite3.connect(restored) as recovered:
            for table in manifest["row_counts"]:
                quoted = '"' + table.replace('"', '""') + '"'
                assert (
                    original.execute(f"SELECT * FROM {quoted}").fetchall()
                    == recovered.execute(f"SELECT * FROM {quoted}").fetchall()
                )
        restored_app = create_app(restored, interpreter=FixtureInterpreter())
        with TestClient(restored_app) as recovered:
            recovered.cookies.update(client.cookies)
            assert recovered.get("/api/platform/session").json() == session
            recovered_portfolio = recovered.get(
                "/api/platform/investing/portfolio"
            ).json()
            for key in ("linked_accounts", "alternative_holdings", "simulation"):
                assert recovered_portfolio[key] == portfolio[key]
            # Calculated evidence receives a fresh id and timestamp per request.
            for key in ("totals", "net_worth_additions"):

                def values(items):
                    return [
                        {k: v for k, v in item.items() if k != "source"} for item in items
                    ]

                assert values(recovered_portfolio[key]) == values(portfolio[key])
            assert (
                recovered.post(
                    "/api/platform/session/login",
                    json={"user_id": "user-other", "password": DEMO_PASSWORD},
                ).status_code
                == 200
            )
            other = recovered.get("/api/platform/investing/portfolio").json()
            assert {item["id"] for item in other["alternative_holdings"]}.isdisjoint(
                {item["id"] for item in portfolio["alternative_holdings"]}
            )


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_storage_ops_never_overwrite_or_follow_symlinks(store, tmp_path, operation):
    backup = tmp_path / "backup.sqlite3"
    backup_database(store.path, backup)
    source = store.path if operation is backup_database else backup
    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"keep this file")
    with pytest.raises(FileExistsError):
        operation(source, existing)
    assert existing.read_bytes() == b"keep this file"
    with pytest.raises(FileExistsError):
        operation(source, source)
    alias = tmp_path / "alias.sqlite3"
    alias.symlink_to(source)
    with pytest.raises(ValueError, match="Symlink"):
        operation(alias, tmp_path / "new.sqlite3")
    with pytest.raises(ValueError, match="Symlink"):
        operation(source, alias)


def test_restore_refuses_tampered_manifest_before_creating_destination(store, tmp_path):
    backup = tmp_path / "backup.sqlite3"
    backup_database(store.path, backup)
    manifest_path = tmp_path / "backup.sqlite3.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sha256"] = "invalid"
    manifest_path.write_text(json.dumps(manifest))
    destination = tmp_path / "restored.sqlite3"
    with pytest.raises(ValueError, match="SHA-256"):
        restore_database(backup, destination)
    assert not destination.exists()


def test_snapshot_pins_at_entry_and_copied_context_does_not_cross_threads(store):
    from contextvars import copy_context

    with store.read_snapshot():
        inherited = copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(inherited.run, increment, store).result(timeout=5)
        assert read_counter(store) == 0
    assert read_counter(store) == 1


def test_backup_rejects_foreign_key_damage_and_cleans_partial_files(store, tmp_path):
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO deposit_rates VALUES(?,?,?)", (fake.uuid4(), fake.uuid4(), "{}")
        )
    backup = tmp_path / "invalid.sqlite3"
    with pytest.raises(ValueError, match="foreign key"):
        backup_database(store.path, backup)
    assert not backup.exists()
    assert not Path(str(backup) + ".manifest.json").exists()


def test_existing_manifest_is_preserved_without_creating_backup(store, tmp_path):
    backup = tmp_path / "backup.sqlite3"
    manifest = Path(str(backup) + ".manifest.json")
    manifest.write_text("preserve existing manifest")
    with pytest.raises(FileExistsError):
        backup_database(store.path, backup)
    assert not backup.exists()
    assert manifest.read_text() == "preserve existing manifest"
