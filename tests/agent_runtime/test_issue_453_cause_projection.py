from __future__ import annotations

import json

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.clarification_contract import (
    offline_clarification_fallback,
    typed_clarification_contract,
)
from argus.agent_runtime.llm_clarifier import OpenRouterClarificationGenerator
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.domain.backtesting.config import MAX_STARTING_CAPITAL, MIN_STARTING_CAPITAL


class RecordingClarifier:
    def __init__(self, question: str | None) -> None:
        self.question = question
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.question


def test_issue_453_starting_capital_bounds_recover_without_confirmation_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import confirm as confirm_module

    monkeypatch.setattr(
        confirm_module,
        "_strategy_with_latest_complete_data_adjustment",
        lambda strategy: strategy,
    )
    state = RunState.new(
        current_user_message="Buy and hold NFLX with $500 starting capital in 2024.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["NFLX"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=500,
    )

    confirmation = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert confirmation.outcome == "needs_clarification"
    assert "confirmation_payload" not in confirmation.patch
    constraint = confirmation.patch["optional_parameter_status"][
        "unsupported_constraints"
    ][0]
    assert constraint["category"] == "unsupported_starting_capital"
    assert constraint["minimum"] == MIN_STARTING_CAPITAL
    assert constraint["maximum"] == MAX_STARTING_CAPITAL

    state.requested_field = confirmation.patch["requested_field"]
    state.missing_required_fields = confirmation.patch["missing_required_fields"]
    state.optional_parameter_status = confirmation.patch["optional_parameter_status"]
    clarification = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )

    assert "$1,000" in clarification.patch["assistant_prompt"]
    assert "unsupported" not in clarification.patch["assistant_prompt"].lower()
    sidecar_payload = clarification.patch["clarification"]["payload"]
    assert sidecar_payload["minimum"] == MIN_STARTING_CAPITAL
    assert sidecar_payload["maximum"] == MAX_STARTING_CAPITAL


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_issue_453_starting_capital_bounds_use_canonical_backend_copy(
    language: str,
) -> None:
    response_intent = {
        "kind": "unsupported_recovery",
        "facts": {
            "unsupported_constraints": [
                {
                    "category": "unsupported_starting_capital",
                    "raw_value": "$500",
                    "minimum": MIN_STARTING_CAPITAL,
                    "maximum": MAX_STARTING_CAPITAL,
                }
            ]
        },
        "options": [
            {
                "label": "Choose a different amount",
                "replacement_values": {"requested_field": "capital_amount"},
            }
        ],
    }

    fallback = offline_clarification_fallback(
        language=language,
        response_intent=response_intent,
    )

    assert fallback == (
        "Starting capital must be between $1,000 and $100,000,000. "
        "What amount in that range should I use?"
    )
    assert "$500" not in fallback


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        (MAX_STARTING_CAPITAL, MIN_STARTING_CAPITAL),
        (float("nan"), MAX_STARTING_CAPITAL),
        (MIN_STARTING_CAPITAL, float("inf")),
    ],
)
def test_issue_453_invalid_starting_capital_bounds_fail_closed_in_backend_projection(
    minimum: float,
    maximum: float,
) -> None:
    response_intent = {
        "kind": "unsupported_recovery",
        "facts": {
            "unsupported_constraints": [
                {
                    "category": "unsupported_starting_capital",
                    "raw_value": "$500",
                    "minimum": minimum,
                    "maximum": maximum,
                }
            ]
        },
        "options": [
            {
                "label": "Choose a different amount",
                "replacement_values": {"requested_field": "capital_amount"},
            }
        ],
    }

    fallback = offline_clarification_fallback(
        language="en",
        response_intent=response_intent,
    )
    sidecar = typed_clarification_contract(response_intent=response_intent)

    assert fallback == "What starting capital amount should I use?"
    assert sidecar is not None
    assert "minimum" not in sidecar["payload"]
    assert "maximum" not in sidecar["payload"]


def test_issue_453_clarifier_routes_starting_capital_as_typed_range_rule() -> None:
    clarifier = OpenRouterClarificationGenerator()
    request = clarifier.request_model(
        current_user_message="Buy and hold NFLX with $500 starting capital.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["NFLX"],
            capital_amount=500,
        ),
        unsupported_constraints=[
            {
                "category": "unsupported_starting_capital",
                "raw_value": "$500",
                "minimum": MIN_STARTING_CAPITAL,
                "maximum": MAX_STARTING_CAPITAL,
                "explanation": "The requested capital is out of range.",
            }
        ],
        response_intent={
            "kind": "unsupported_recovery",
            "facts": {
                "unsupported_constraints": [
                    {
                        "category": "unsupported_starting_capital",
                        "raw_value": "$500",
                        "minimum": MIN_STARTING_CAPITAL,
                        "maximum": MAX_STARTING_CAPITAL,
                    }
                ]
            },
        },
    )

    messages = clarifier._messages(request)
    system_prompt = messages[0].content
    context = json.loads(messages[1].content)

    assert "validation range, not a strategy capability limit" in system_prompt
    constraint = context["unsupported_constraints"][0]
    assert constraint == {
        "category": "unsupported_starting_capital",
        "maximum": MAX_STARTING_CAPITAL,
        "minimum": MIN_STARTING_CAPITAL,
    }
    assert context["response_intent"]["facts"]["unsupported_constraints"] == [constraint]


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        (MAX_STARTING_CAPITAL, MIN_STARTING_CAPITAL),
        (float("nan"), MAX_STARTING_CAPITAL),
        (MIN_STARTING_CAPITAL, float("inf")),
    ],
)
def test_issue_453_clarifier_drops_invalid_starting_capital_bound_pairs(
    minimum: float,
    maximum: float,
) -> None:
    clarifier = OpenRouterClarificationGenerator()
    constraint = {
        "category": "unsupported_starting_capital",
        "raw_value": "$500",
        "minimum": minimum,
        "maximum": maximum,
        "explanation": "The requested capital is out of range.",
    }
    request = clarifier.request_model(
        current_user_message="Buy and hold NFLX with $500 starting capital.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["NFLX"],
            capital_amount=500,
        ),
        unsupported_constraints=[constraint],
        response_intent={
            "kind": "unsupported_recovery",
            "facts": {"unsupported_constraints": [constraint]},
        },
    )

    context = json.loads(clarifier._messages(request)[1].content)

    expected = [{"category": "unsupported_starting_capital"}]
    assert context["unsupported_constraints"] == expected
    assert context["response_intent"]["facts"]["unsupported_constraints"] == expected


def test_issue_453_clarifier_preserves_typed_time_granularity_value() -> None:
    clarifier = OpenRouterClarificationGenerator()
    constraint = {
        "category": "unsupported_time_granularity",
        "raw_value": "5m",
        "explanation": "Choose a supported timeframe.",
    }
    request = clarifier.request_model(
        current_user_message="Use five-minute bars.",
        candidate_strategy_draft=StrategySummary(timeframe="5m"),
        unsupported_constraints=[constraint],
        response_intent={
            "kind": "unsupported_recovery",
            "facts": {"unsupported_constraints": [constraint]},
        },
    )

    context = json.loads(clarifier._messages(request)[1].content)

    assert context["unsupported_constraints"] == [
        {"category": "unsupported_time_granularity", "raw_value": "5m"}
    ]
    assert context["response_intent"]["facts"]["unsupported_constraints"] == [
        {"category": "unsupported_time_granularity", "raw_value": "5m"}
    ]
