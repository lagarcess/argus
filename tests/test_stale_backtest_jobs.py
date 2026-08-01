from __future__ import annotations

import os

from scripts.ops.stale_backtest_jobs import _prepare_supabase_env


def test_prepare_supabase_env_maps_workflow_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "ARGUS_WORKFLOW_DATABASE_URL",
        "postgresql://workflow-pooler.example/argus",
    )

    _prepare_supabase_env()

    assert os.environ["DATABASE_URL"] == "postgresql://workflow-pooler.example/argus"


def test_prepare_supabase_env_preserves_explicit_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://explicit-pooler.example/argus")
    monkeypatch.setenv(
        "ARGUS_WORKFLOW_DATABASE_URL",
        "postgresql://workflow-pooler.example/argus",
    )

    _prepare_supabase_env()

    assert os.environ["DATABASE_URL"] == "postgresql://explicit-pooler.example/argus"
