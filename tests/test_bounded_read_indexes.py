from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260727000001_add_bounded_read_indexes.sql"
)
SEARCH_MIGRATION_GLOB = "*_add_search_trigram_indexes.sql"


def _migration_sql() -> str:
    assert MIGRATION.exists(), "bounded-read index migration is missing"
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_bounded_read_migration_adds_only_the_three_proven_indexes() -> None:
    migration = _migration_sql()

    assert (
        "create index if not exists idx_conversations_active_page "
        "on public.conversations "
        "(user_id, pinned desc, updated_at desc, id desc) "
        "where deleted_at is null"
    ) in migration
    assert (
        "create index if not exists idx_messages_reload_artifact_page "
        "on public.messages "
        "(user_id, conversation_id, created_at, id)"
    ) in migration
    assert (
        "create index if not exists idx_decision_notes_idea_latest "
        "on public.decision_notes "
        "(user_id, idea_id, updated_at desc, id desc)"
    ) in migration

    assert migration.count("create index if not exists") == 3
    assert "create unique index" not in migration
    assert "create function" not in migration
    assert "create view" not in migration
    assert "create materialized view" not in migration
    assert "generated always as" not in migration
    assert "grant " not in migration


def test_message_artifact_index_is_a_reload_superset_without_content() -> None:
    migration = _migration_sql()

    assert "where role = 'assistant'" in migration
    for field in (
        "active_confirmation_reference",
        "backtest_job",
        "backtest_job_id",
        "confirmation_card",
        "confirmation_payload",
        "latest_run_id",
        "result_card",
        "result_run_id",
    ):
        assert f"metadata->>'{field}'" in migration
    for artifact_kind in (
        "confirmation",
        "result",
        "backtest_result",
        "backtest_job",
    ):
        assert f'"artifact_kind": "{artifact_kind}"' in migration

    assert "content" not in migration
    assert "user_id, conversation_id, created_at, id" in migration


def test_bounded_read_migration_records_exact_index_rollback() -> None:
    migration = _migration_sql()

    for index_name in (
        "idx_conversations_active_page",
        "idx_messages_reload_artifact_page",
        "idx_decision_notes_idea_latest",
    ):
        assert f"drop index if exists public.{index_name}" in migration


def test_search_trigram_migration_is_private_and_index_only() -> None:
    migrations = sorted((ROOT / "supabase" / "migrations").glob(SEARCH_MIGRATION_GLOB))
    assert len(migrations) == 1, "Search trigram migration is missing or ambiguous"
    migration = " ".join(migrations[0].read_text(encoding="utf-8").lower().split())

    assert "create extension if not exists pg_trgm with schema extensions" in migration
    for index_name in (
        "idx_conversations_search_norm_trgm",
        "idx_strategies_search_norm_trgm",
        "idx_collections_search_norm_trgm",
        "idx_backtest_runs_search_norm_trgm",
        "idx_ideas_search_norm_trgm",
        "idx_evidence_search_norm_trgm",
    ):
        assert f"create index if not exists {index_name}" in migration
        assert f"drop index if exists public.{index_name}" in migration

    assert migration.count("create index if not exists") == 6
    assert " extensions.gin_trgm_ops" in migration
    assert "create function" not in migration
    assert "create view" not in migration
    assert "create materialized view" not in migration
    assert "generated always as" not in migration
    assert "grant " not in migration
