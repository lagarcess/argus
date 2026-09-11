"""What the interpreter reads about the latest completed run.

A stored result reference carries the whole run: the card with its tool cards,
the chart series twice, markers and trades, about 170,000 characters for a
three-year daily run. Reading the user's turn needs the run's configuration and
its headline facts, so that is all an interpreter prompt receives.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifacts.drafts import draft_from_result_metadata
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.state.models import ArtifactReference

# Headline facts in the fact bank's reader words; none is a series or a list.
LATEST_RESULT_FACT_IDS = (
    "symbols",
    "strategy",
    "date_range",
    "benchmark_symbol",
    "starting_capital",
    "rule_summary",
    "execution_note",
    "assumptions",
    "total_return",
    "benchmark_return",
    "benchmark_delta",
    "annualized_return",
    "volatility",
    "sharpe_ratio",
    "max_drawdown",
    "drawdown_date",
    "drawdown_depth",
    "peak_date",
    "peak_value",
    "lowest_date",
    "lowest_value",
    "final_date",
    "final_value",
    "profit",
    "trade_count",
    "fee_bps",
    "slippage_bps",
    "gross_total_return",
    "net_total_return",
    "return_drag",
    "benchmark_cost_treatment",
    "runnable_next_tests",
)


def latest_result_facts(reference: ArtifactReference) -> dict[str, str]:
    fact_bank = result_followup_fact_bank(dict(reference.metadata))
    return {key: fact_bank[key] for key in LATEST_RESULT_FACT_IDS if key in fact_bank}


def latest_result_interpreter_context(reference: ArtifactReference) -> dict[str, Any]:
    """The run's typed configuration and headline facts, never its series or trades."""
    try:
        configuration = draft_from_result_metadata(dict(reference.metadata)).model_dump(
            mode="json", exclude_defaults=True
        )
    except Exception:  # noqa: BLE001
        # A malformed reference must not break reading the user's turn.
        configuration = {}
    return {"configuration": configuration, "facts": latest_result_facts(reference)}
