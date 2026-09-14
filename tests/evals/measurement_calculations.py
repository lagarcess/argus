"""Calculation acceptance reads delivered cards and real persisted-history projection.

Authored history is input context, not evidence of a previous live turn. Its cards
are built by the declared calculator and loaded by the production history loader.
"""

from __future__ import annotations

import math
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from argus.api import state as api_state
from argus.api.message_store import load_runtime_thread_history
from argus.domain.market_data.historical_drawdown import HistoricalDrawdownObservation
from argus.domain.tool_contracts import ToolResultCard

from tests.domain.calculations.support import run_calculation
from tests.evals.measurement_assertions import _compare_subset


def stored_calculation_history(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not turns:
        return []
    messages = []
    for turn in turns:
        metadata = dict(turn.get("metadata") or {})
        if calculation := turn.get("calculation"):
            card = run_calculation(calculation["tool_name"], calculation["arguments"])
            if card.outcome.status != "succeeded":
                raise ValueError(f"invalid authored calculation: {card.outcome}")
            metadata["tool_result_cards"] = [card.model_dump(mode="json")]
        messages.append(
            SimpleNamespace(role=turn["role"], content=turn["content"], metadata=metadata)
        )
    gateway = SimpleNamespace(list_messages=lambda **_: messages)
    with patch.object(api_state, "supabase_gateway", gateway):
        return [
            turn.model_dump(mode="json")
            for turn in load_runtime_thread_history(
                user_id="argus-eval", conversation_id="authored-calculation-history"
            )
        ]


def delivered_calculations(patch: dict[str, Any]) -> list[dict[str, Any]]:
    final = patch.get("final_response_payload")
    if not isinstance(final, dict):
        return []
    cards = final.get("tool_result_cards")
    return cards if isinstance(cards, list) else []


def compare_calculations(
    expected: list[dict[str, Any]], actual: Any, failures: list[str]
) -> None:
    """A number in prose cannot replace an executed, successful, visible card."""
    if not isinstance(actual, list) or len(actual) != len(expected):
        failures.append(
            f"calculations.count: expected {len(expected)}, got {len(actual) if isinstance(actual, list) else None}"
        )
        return
    for index, (wanted, raw) in enumerate(zip(expected, actual, strict=True)):
        prefix = f"calculations.{index}"
        try:
            card = ToolResultCard.model_validate(raw)
        except ValueError:
            failures.append(f"{prefix}.card: invalid ToolResultCard")
            continue
        _compare_subset(prefix, wanted.get("card", {}), raw, failures)
        if card.outcome.status != "succeeded":
            failures.append(
                f"{prefix}.status: expected succeeded, got {card.outcome.status}"
            )
        answer = card.presentation.answer
        if answer is None:
            failures.append(f"{prefix}.answer: no displayed answer")
            continue
        reference = wanted.get("reference")
        if reference:
            computed = run_calculation(reference["tool_name"], reference["arguments"])
            assert computed.outcome.status == "succeeded", computed.outcome
            assert computed.presentation.answer is not None
            target = computed.presentation.answer.value
            if answer.unit != computed.presentation.answer.unit:
                failures.append(f"{prefix}.unit: displayed unit differs from calculation")
            if answer.name != computed.presentation.answer.name:
                failures.append(
                    f"{prefix}.field: displayed field differs from calculation"
                )
        else:
            target = wanted.get("answer_value")
        if target is not None:
            if not isinstance(answer.value, (int, float)) or not math.isclose(
                answer.value, target, rel_tol=1e-8, abs_tol=0.01
            ):
                failures.append(f"{prefix}.answer: expected {target}, got {answer.value}")
        if wanted.get("historical_drawdown"):
            _compare_historical_drawdown(prefix, card, failures)


def _compare_historical_drawdown(
    prefix: str, card: ToolResultCard, failures: list[str]
) -> None:
    result = card.outcome.result
    result = result if isinstance(result, dict) else {}
    answer = card.presentation.answer
    assert answer is not None
    if not isinstance(answer.value, (int, float)) or not -100 <= answer.value < 0:
        failures.append(f"{prefix}.drawdown: expected historical loss percentage")
    _compare_subset(
        f"{prefix}.provenance",
        {
            "source": "argus_market_data",
            "timeframe": "1D",
            "symbol": card.arguments.get("symbol"),
        },
        result,
        failures,
    )
    if answer.source is None or answer.source.kind != "market_data":
        failures.append(f"{prefix}.source: displayed drawdown is not market data")
    try:
        observation = HistoricalDrawdownObservation.model_validate(result)
    except ValueError:
        failures.append(f"{prefix}.history: invalid provider observation")
        return
    if observation.observations < 2:
        failures.append(f"{prefix}.observations: missing historical series")
    try:
        requested_start = date.fromisoformat(result["requested_start_date"])
        observed_start = date.fromisoformat(result["observed_start_date"])
        observed_end = date.fromisoformat(result["observed_end_date"])
        requested_end = date.fromisoformat(result["requested_end_date"])
        peak = date.fromisoformat(result["peak_date"])
        trough = date.fromisoformat(result["trough_date"])
        assert (
            requested_start
            <= observed_start
            <= peak
            < trough
            <= observed_end
            <= requested_end
        )
    except (KeyError, TypeError, ValueError, AssertionError):
        failures.append(f"{prefix}.window: invalid observed drawdown window")
    rows = {row.name: row.value for row in card.presentation.rows}
    for name in (
        "observed_start_date",
        "observed_end_date",
        "observations",
        "peak_date",
        "trough_date",
    ):
        if rows.get(name) != result.get(name) or rows.get(name) is None:
            failures.append(
                f"{prefix}.display.{name}: observed history did not reach card"
            )
    loss = result.get("max_drawdown_pct")
    if (
        not isinstance(loss, (int, float))
        or not isinstance(answer.value, (int, float))
        or not math.isclose(answer.value, loss, abs_tol=0.01)
    ):
        failures.append(f"{prefix}.display.loss: drawdown result and display differ")
