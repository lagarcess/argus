"""Guard for the workflow-proof scope migration.

A proof job is not conversation work. The seeder owns the proof's scope and
its created_by signature (``workflows.proof``); the migration's scope check
and its reclassification statement are pinned to those values, so the seeder
and the schema cannot name the proof differently. The settle rule itself is
untouched: this migration must not restate or replace the owner function.
"""

from __future__ import annotations

import re
from pathlib import Path

from argus.domain.backtest_admission import CHAT_RUN_SCOPE, DIRECT_RUN_SCOPE
from argus.domain.job_settlement import RESEARCH_OPERATION_SCOPE, SQL_FUNCTION_NAME

from workflows.proof import PROOF_OPERATION_SCOPE, PROOF_SEED_CREATED_BY

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/20260905000000_workflow_proof_jobs_leave_conversations.sql"
)


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _statements(text: str) -> str:
    """The migration without its comment lines: what the database executes."""
    return _normalized(
        "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("--")
        )
    )


def test_scope_check_admits_every_scope_including_the_proof() -> None:
    sql = _normalized(MIGRATION.read_text(encoding="utf-8"))
    check = re.search(
        r"add constraint backtest_jobs_operation_scope_check check \( "
        r"operation_scope in \( (.*?) \) \)",
        sql,
    )
    assert check is not None
    scopes = [scope.strip().strip("'") for scope in check.group(1).split(",")]
    assert scopes == [
        CHAT_RUN_SCOPE,
        DIRECT_RUN_SCOPE,
        RESEARCH_OPERATION_SCOPE,
        PROOF_OPERATION_SCOPE,
    ]
    assert "drop constraint if exists backtest_jobs_operation_scope_check" in sql


def test_reclassification_is_keyed_on_the_seeder_signature() -> None:
    sql = _normalized(MIGRATION.read_text(encoding="utf-8"))

    assert (
        "update public.backtest_jobs set "
        f"operation_scope = '{PROOF_OPERATION_SCOPE}', "
        "conversation_id = null, updated_at = now() "
        f"where launch_payload ->> 'created_by' = '{PROOF_SEED_CREATED_BY}'"
    ) in sql
    # Idempotent: a replay finds nothing left to move.
    assert (
        f"and ( operation_scope <> '{PROOF_OPERATION_SCOPE}' "
        "or conversation_id is not null )"
    ) in sql
    # Only the seeder's rows move. Chat jobs a proof-shadow deployment sent to
    # the proof task keep their scope; their settlement is owed to their run.
    assert "launch_payload ->> 'kind'" not in sql


def test_settle_rule_owner_is_not_restated_here() -> None:
    sql = _statements(MIGRATION.read_text(encoding="utf-8"))

    assert SQL_FUNCTION_NAME not in sql
    assert "create or replace function" not in sql
    assert "evidence_artifacts" not in sql
