"""One scenario table for the job-settlement rule, drawn by both twins.

`backtest_job_result_hydrateable` (SQL) and `_memory_result_hydrateable`
(memory store) are two implementations of one rule: a succeeded job is
settled when its result is readable in its conversation. Nothing structural
makes them agree, so the memory test (`tests/test_conversation_activity.py`)
and the Postgres test (`tests/test_conversation_activity_postgres.py`, a
required CI gate on the disposable database) both parametrize over this
table. A scenario added here runs against both; a change to only one
implementation fails on that side.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobSettlementScenario:
    id: str
    operation_scope: str
    status: str
    # The research answer message named by execution_metadata exists.
    answer_present: bool
    expected_hydrateable: bool
    expected_operation: str
    expected_attention: str


JOB_SETTLEMENT_SCENARIOS: tuple[JobSettlementScenario, ...] = (
    JobSettlementScenario(
        id="research_succeeded_with_answer_settles",
        operation_scope="chat.research",
        status="succeeded",
        answer_present=True,
        expected_hydrateable=True,
        expected_operation="idle",
        expected_attention="new_activity",
    ),
    JobSettlementScenario(
        id="research_succeeded_without_answer_keeps_checking",
        operation_scope="chat.research",
        status="succeeded",
        answer_present=False,
        expected_hydrateable=False,
        expected_operation="checking",
        expected_attention="none",
    ),
    # The answer is persisted before the row flips to succeeded; an early
    # message must never read as finished work.
    JobSettlementScenario(
        id="research_running_with_early_answer_stays_running",
        operation_scope="chat.research",
        status="running",
        answer_present=True,
        expected_hydrateable=False,
        expected_operation="running",
        expected_attention="none",
    ),
    # A backtest never settles through the message branch, even when a
    # message with that id happens to exist.
    JobSettlementScenario(
        id="backtest_succeeded_without_run_keeps_checking",
        operation_scope="chat.run_backtest",
        status="succeeded",
        answer_present=True,
        expected_hydrateable=False,
        expected_operation="checking",
        expected_attention="none",
    ),
)
