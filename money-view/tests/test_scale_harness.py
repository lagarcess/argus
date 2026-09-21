"""Fixture safety and repeatability, separate from the measured HTTP run."""

import json
import sqlite3

import pytest
from scripts.scale_check import (
    Profile,
    clean_environment,
    main,
    percentile,
    seed_database,
    stable,
)


def test_bounded_acceptance_distribution():
    profile = Profile()
    counts = profile.distribution()
    assert sum(counts) == profile.transactions
    assert len(counts) == profile.households
    assert counts.count(profile.heavy_transactions) == profile.heavy_households
    assert counts[profile.heavy_households] == profile.stress_transactions
    assert min(counts) > 0


def test_seed_restart_preserves_financial_shapes_and_counts(tmp_path):
    profile = Profile(
        identities=10,
        households=8,
        transactions=10_000,
        heavy_households=2,
        heavy_transactions=1_000,
        stress_transactions=3_000,
        batch_size=113,
    )
    path = tmp_path / "fixture.sqlite3"
    before = seed_database(path, profile)
    after = seed_database(path, profile)
    assert before["counts"] == after["counts"]
    assert after["fixture_ledger_count"] == profile.transactions
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert not db.execute(
            "SELECT t.id FROM p_transactions t JOIN p_accounts a ON a.id=t.account_id WHERE t.household_id<>a.household_id OR t.currency<>a.currency"
        ).fetchall()
        assert not db.execute(
            "SELECT t.id FROM p_transactions t JOIN p_transaction_splits s ON s.transaction_id=t.id GROUP BY t.id HAVING SUM(s.amount_minor)<>t.amount_minor"
        ).fetchall()
        assert not db.execute(
            "SELECT transfer_id FROM p_transactions WHERE description='Synthetic capacity fixture' AND transfer_id IS NOT NULL GROUP BY transfer_id HAVING COUNT(*)<>2 OR SUM(amount_minor)<>0"
        ).fetchall()
        assert (
            db.execute(
                "SELECT COUNT(*) FROM p_memberships WHERE household_id=?",
                (stable("household", 0),),
            ).fetchone()[0]
            == 2
        )
    with pytest.raises(ValueError, match="existing fixture profile"):
        seed_database(
            path,
            Profile(
                identities=11,
                households=8,
                transactions=10_000,
                heavy_households=2,
                heavy_transactions=1_000,
                stress_transactions=3_000,
            ),
        )


def test_server_environment_does_not_inherit_provider_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "never-forward-this")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "never-forward-this")
    monkeypatch.setenv("CLARA_LLM_API_KEY", "never-forward-this")
    env = clean_environment(tmp_path / "fixture.sqlite3")
    assert "OPENAI_API_KEY" not in env and "ANTHROPIC_API_KEY" not in env
    assert env["CLARA_LLM_API_KEY"] == ""
    assert "never-forward-this" not in env.values()


def test_nearest_rank_percentile_and_invalid_distribution():
    assert percentile(list(range(1, 101)), 0.95) == 95
    with pytest.raises(ValueError):
        Profile(households=50).distribution()


def test_seed_only_failure_exits_nonzero_and_preserves_unowned_database(
    tmp_path, monkeypatch
):
    path = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unrelated (id INTEGER)")
        db.execute("INSERT INTO unrelated VALUES (1)")
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(
        "sys.argv",
        ["scale_check", "--database", str(path), "--output", str(output), "--seed-only"],
    )
    assert main() == 1
    assert "not owned" in json.loads(output.read_text())["stopped"]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT id FROM unrelated").fetchall() == [(1,)]
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='capacity_fixture'"
        ).fetchall()
