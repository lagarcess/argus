"""A capacity refusal is a request to wait, not a failure (#482).

Argus runs five concurrent backtests product-wide. At the ceiling the run is
refused before a job exists, so nothing broke and nothing was lost. The runtime
used to say "The run hit a temporary data or service issue", which is the copy
for something going wrong, in English regardless of the workspace language.
"""

from __future__ import annotations

from typing import Any

import pytest

from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import RunState
from argus.agent_runtime.tools.backtest_stub import StubBacktestTool
from argus.api.chat.backtest_job_envelopes import admission_rejection_envelope


def _capacity_state() -> RunState:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}
    return state


@pytest.mark.parametrize("decision", ["per_user_capacity", "global_capacity"])
def test_capacity_refusal_is_recoverable_and_typed(decision: str) -> None:
    """Both ceilings, per-user and global, produce the same typed condition."""

    envelope = admission_rejection_envelope(decision)
    result = execute_stage(
        state=_capacity_state(),
        tool=StubBacktestTool(responses=[envelope]),
        max_retries=2,
    )

    assert result.outcome == "execution_failed_recoverably"
    recovery: dict[str, Any] = result.patch["recovery"]
    assert recovery["code"] == "backtest_capacity_exceeded"
    assert recovery["retryable"] is True


@pytest.mark.parametrize("decision", ["per_user_capacity", "global_capacity"])
def test_capacity_refusal_does_not_read_as_a_failure(decision: str) -> None:
    """The copy bar from #482: name the condition, say nothing was lost, say
    what happens next, and do not promise an ETA we cannot honor."""

    result = execute_stage(
        state=_capacity_state(),
        tool=StubBacktestTool(responses=[admission_rejection_envelope(decision)]),
        max_retries=2,
    )

    prompt = result.patch["assistant_prompt"]
    assert "nothing was lost" in prompt.lower()
    # The generic failure copy is what this condition used to borrow.
    assert "temporary data or service issue" not in prompt
    assert "could not complete" not in prompt


def test_capacity_refusal_offers_a_retry() -> None:
    """A wait the user can act on: the refused run keeps a retry affordance,
    unlike a terminal failure."""

    result = execute_stage(
        state=_capacity_state(),
        tool=StubBacktestTool(
            responses=[admission_rejection_envelope("global_capacity")]
        ),
        max_retries=2,
    )

    references = result.patch.get("artifact_references") or []
    assert references, "a refused run must still expose its failed-action reference"
    assert any(
        (reference.get("metadata") or {}).get("retryable") is True
        for reference in references
    )


def test_other_admission_rejections_keep_their_own_copy() -> None:
    """Scoped to capacity: an allowance refusal is a different fact and must not
    inherit the wait copy."""

    result = execute_stage(
        state=_capacity_state(),
        tool=StubBacktestTool(
            responses=[admission_rejection_envelope("allowance_exhausted")]
        ),
        max_retries=2,
    )

    assert result.patch.get("recovery", {}).get("code") != "backtest_capacity_exceeded"
