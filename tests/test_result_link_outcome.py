"""The link outcome the publisher obeys.

``link_shadow_backtest_job_result`` reports what the gated write actually
did; these tests pin the outcome semantics: a standing row without the
requested result is a refusal the publisher must withhold, and the
tolerant paths stay publishable only where nothing durable was guarded.
"""

from __future__ import annotations

import pytest
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    backtest_job_shadow_context,
)
from argus.api.chat.result_link import link_shadow_backtest_job_result


class _LinkGateway:
    def __init__(
        self,
        *,
        link_result: dict[str, object] | None = None,
        should_raise: bool = False,
    ) -> None:
        self.link_result = link_result
        self.should_raise = should_raise
        self.result_links: list[dict[str, object]] = []

    def link_backtest_job_result(self, **payload: object) -> dict[str, object]:
        if self.should_raise:
            raise RuntimeError("link failed")
        self.result_links.append(payload)
        if self.link_result is not None:
            return dict(self.link_result)
        return {"id": payload["job_id"], **payload}


def _context() -> BacktestJobShadowContext:
    return BacktestJobShadowContext(
        user_id="user-1",
        conversation_id="conversation-1",
        account_kind="registered",
    )


def test_link_outcome_refused_when_the_lifecycle_statement_won() -> None:
    """A standing row without the requested result means the attach was
    refused; the publisher must withhold the result so a restored card can
    never sit beside one."""
    gateway = _LinkGateway(
        link_result={"id": "job-1", "status": "canceled", "result_run_id": None},
    )
    context = _context()
    context.created_job_id = "job-1"
    context.workflow_dispatch_started = True

    with backtest_job_shadow_context(context):
        outcome = link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=gateway,
            dev_memory_fallback_enabled=True,
        )

    assert len(gateway.result_links) == 1
    assert outcome.publishable is False
    assert outcome.reason == "refused"
    assert outcome.job == {"id": "job-1", "status": "canceled", "result_run_id": None}


def test_link_outcome_refused_when_the_job_owns_a_different_result() -> None:
    """A job already linked to another run must not publish this one; the
    first link owns the card's consequence."""
    gateway = _LinkGateway(
        link_result={"id": "job-1", "status": "succeeded", "result_run_id": "run-0"},
    )
    context = _context()
    context.created_job_id = "job-1"
    context.workflow_dispatch_started = True

    with backtest_job_shadow_context(context):
        outcome = link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=gateway,
            dev_memory_fallback_enabled=True,
        )

    assert outcome.publishable is False
    assert outcome.reason == "refused"


def test_link_outcome_publishable_without_a_job_context() -> None:
    with backtest_job_shadow_context(None):
        outcome = link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=None,
            dev_memory_fallback_enabled=False,
        )
    assert outcome.publishable is True
    assert outcome.reason == "no_job"


def test_link_outcome_tolerates_gateway_errors_only_in_dev_fallback() -> None:
    context = _context()
    context.created_job_id = "job-1"

    with backtest_job_shadow_context(context):
        outcome = link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=_LinkGateway(should_raise=True),
            dev_memory_fallback_enabled=True,
        )
    assert outcome.publishable is True
    assert outcome.reason == "link_error"

    with backtest_job_shadow_context(context):
        with pytest.raises(RuntimeError):
            link_shadow_backtest_job_result(
                user_id="user-1",
                run_id="run-1",
                gateway=_LinkGateway(should_raise=True),
                dev_memory_fallback_enabled=False,
            )
