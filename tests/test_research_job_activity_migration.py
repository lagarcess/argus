"""Guard for the research-job activity migration.

The predicate "this succeeded job's result is readable in its conversation"
used to be stated inline four times. Every reader must now derive it from the
one owner so a research job (result = message, no run) cannot drift back to
"checking forever" on one path while another path settles it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260822000000_research_job_activity_settles.sql"
ORIGINAL = (
    ROOT / "supabase/migrations/20260801000000_add_conversation_activity_read_states.sql"
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def _function(sql: str, name: str) -> str:
    return sql.split(f"create or replace function public.{name}(", 1)[1].split("$$;", 1)[
        0
    ]


def test_one_owner_predicate_settles_research_jobs_and_reads_no_prose() -> None:
    sql = _normalized(MIGRATION)
    owner = _function(sql, "backtest_job_result_hydrateable")

    assert "j public.backtest_jobs" in owner
    # Only a succeeded row may settle: the research answer is persisted before
    # the row flips, so an early message must never read as finished work.
    assert "select j.status = 'succeeded' and (" in owner
    assert "j.operation_scope = 'chat.research'" in owner
    assert "->> 'research_result_message_id'" in owner
    assert "from public.messages as rm" in owner
    assert "rm.conversation_id = j.conversation_id" in owner
    assert "rm.user_id = j.user_id" in owner
    assert "evidence_artifacts" in owner
    assert "content" not in owner


def test_every_activity_reader_derives_from_the_owner() -> None:
    sql = _normalized(MIGRATION)

    for name, calls in (
        ("read_conversation_activity_sources", 2),
        ("mutate_conversation_activity_read_state", 1),
        ("baseline_conversation_activity_read_states", 1),
    ):
        function = _function(sql, name)
        assert function.count("public.backtest_job_result_hydrateable(j)") == calls
        assert "evidence_artifacts" not in function
        assert "content" not in function

    # Only the owner states the run/evidence chain.
    assert sql.count("join public.evidence_artifacts as e") == 1


def test_owner_predicate_is_service_role_only_like_its_callers() -> None:
    sql = _normalized(MIGRATION)

    for role in ("public", "anon", "authenticated"):
        assert (
            "revoke all on function public.backtest_job_result_hydrateable( "
            f"public.backtest_jobs ) from {role}"
        ) in sql
    assert (
        "grant execute on function public.backtest_job_result_hydrateable( "
        "public.backtest_jobs ) to service_role"
    ) in sql


def test_replaced_functions_keep_their_original_signatures() -> None:
    sql = _normalized(MIGRATION)
    original = _normalized(ORIGINAL)

    for name in (
        "read_conversation_activity_sources",
        "mutate_conversation_activity_read_state",
        "baseline_conversation_activity_read_states",
    ):
        replaced_head = _function(sql, name).split(" as $$", 1)[0]
        original_head = (
            original.split(f"create function public.{name}(", 1)[1]
            .split("$$;", 1)[0]
            .split(" as $$", 1)[0]
        )
        assert replaced_head == original_head
