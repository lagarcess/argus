"""Launch-validation envelope and refusal recovery for the confirm stage.

Behavior-preserving relocation from stages/confirm.py. The envelope check
mirrors the engine's accepted-value bounds so a ready card can never promise
a run the run-time validator refuses; the failure catalog turns each refusal
code into the clarification patch that recovers it, tagged with the code so
typed edit endpoints can answer with the exact reason.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.engine_launch.models import LaunchBacktestRequest


def _with_unsupported_constraint(
    optional_parameter_status: dict[str, Any],
    constraint: dict[str, Any],
) -> dict[str, Any]:
    unsupported_constraints = [
        item
        for item in optional_parameter_status.get("unsupported_constraints", [])
        if isinstance(item, dict)
    ]
    return {
        **optional_parameter_status,
        "unsupported_constraints": [*unsupported_constraints, constraint],
    }


def _validate_launch_envelope(request: LaunchBacktestRequest) -> None:
    """Enforce the engine's accepted-value envelope before a card can mint.

    The run-time validator owns these bounds; checking them here means a
    ready card can never promise a run the engine will refuse. Constants are
    imported, never restated, so the two layers cannot drift.
    """
    from argus.domain.backtesting.config import (
        MAX_STARTING_CAPITAL,
        MIN_STARTING_CAPITAL,
    )
    from argus.domain.backtesting.date_window import validate_backtest_date_window

    if request.capital_amount is not None:
        amount = float(request.capital_amount)
        # The launch adapter's rule: the band applies to a one-time bankroll;
        # a recurring contribution reuses the field but is exempt from the
        # floor and keeps the ceiling (_validate_launch_config in
        # engine_launch/adapter.py).
        recurring = request.strategy_type == "dca_accumulation"
        floor = 0.0 if recurring else MIN_STARTING_CAPITAL
        if amount > MAX_STARTING_CAPITAL or amount < floor or amount <= 0.0:
            raise ValueError("invalid_starting_capital")
    validate_backtest_date_window(
        start=date.fromisoformat(request.date_range.start),
        end=date.fromisoformat(request.date_range.end),
    )


def _tagged_launch_validation_failure(
    error_code: str,
    *,
    raw_value: Any | None = None,
    optional_parameter_status: dict[str, Any] | None = None,
    capital_role: str | None = None,
) -> dict[str, Any]:
    """Every launch validation failure names its code in the patch, so the
    typed edit endpoints can answer with the exact refusal instead of a
    generic conflict."""
    failure = _launch_validation_failure(
        error_code,
        raw_value=raw_value,
        optional_parameter_status=optional_parameter_status,
        capital_role=capital_role,
    )
    failure["launch_validation_code"] = error_code
    return failure


def _launch_validation_failure(
    error_code: str,
    *,
    raw_value: Any | None = None,
    optional_parameter_status: dict[str, Any] | None = None,
    capital_role: str | None = None,
) -> dict[str, Any]:
    if error_code == "unsupported_timeframe":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["timeframe"],
            "requested_field": "timeframe",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                dict(optional_parameter_status or {}),
                {
                    "category": "unsupported_time_granularity",
                    "raw_value": raw_value or error_code,
                    "explanation": (
                        "That bar size is not supported by the current backtest "
                        "engine. Choose a supported timeframe to keep the rest of "
                        "the strategy unchanged."
                    ),
                    "simplification_options": [
                        {
                            "label": "Retry with daily bars",
                            "replacement_values": {"timeframe": "1D"},
                        },
                        {
                            "label": "Retry with 1-hour bars",
                            "replacement_values": {"timeframe": "1h"},
                        },
                    ],
                },
            ),
        }
    if error_code == "invalid_starting_capital":
        from argus.domain.backtesting.config import (
            MAX_STARTING_CAPITAL,
            MIN_STARTING_CAPITAL,
        )

        if capital_role == "recurring_contribution":
            status = dict(optional_parameter_status or {})
            raw_constraints = status.get("unsupported_constraints", [])
            constraints = []
            if isinstance(raw_constraints, list):
                constraints = [
                    item
                    for item in raw_constraints
                    if isinstance(item, dict)
                    and item.get("category") != "unsupported_starting_capital"
                ]
            if constraints:
                status["unsupported_constraints"] = constraints
            else:
                status.pop("unsupported_constraints", None)
            return {
                "outcome": "needs_clarification",
                "missing_required_fields": ["capital_amount"],
                "requested_field": "capital_amount",
                "assistant_prompt": None,
                "optional_parameter_status": status,
            }

        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["capital_amount"],
            "requested_field": "capital_amount",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                dict(optional_parameter_status or {}),
                {
                    "category": "unsupported_starting_capital",
                    "raw_value": raw_value or error_code,
                    "minimum": MIN_STARTING_CAPITAL,
                    "maximum": MAX_STARTING_CAPITAL,
                    "explanation": (
                        "The backtest engine accepts starting capital between "
                        f"${MIN_STARTING_CAPITAL:,.0f} and "
                        f"${MAX_STARTING_CAPITAL:,.0f}. Choose an amount in "
                        "that range to keep the rest of the strategy unchanged."
                    ),
                    "simplification_options": [
                        {
                            "label": "Use $10,000",
                            "replacement_values": {"capital_amount": 10000},
                        },
                        {"label": "Choose a different amount"},
                    ],
                },
            ),
        }
    if error_code == "future_end_date":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "future_date_window",
                    "raw_value": error_code,
                    "explanation": (
                        "The requested end date is after the latest available "
                        "data Argus can test."
                    ),
                    "simplification_options": [
                        {"label": "Use the latest available date"},
                        {"label": "Choose an earlier end date"},
                        {"label": "Change the date range"},
                    ],
                },
            ),
        }
    if error_code == "invalid_chronological_date_range":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "invalid_date_window",
                    "raw_value": "selected date range",
                    "explanation": (
                        "The requested window is not usable because the start "
                        "date is not before the end date."
                    ),
                    "simplification_options": [
                        {"label": "Choose a new start date"},
                        {"label": "Choose a new end date"},
                        {"label": "Change the date range"},
                    ],
                },
            ),
        }
    if error_code == "indicator_data_insufficient":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "data_window_too_short_for_rule",
                    "raw_value": "selected date range",
                    "explanation": (
                        "The selected window does not provide enough bars for "
                        "the confirmed signal rule."
                    ),
                    "simplification_options": [
                        {"label": "Use a longer date range"},
                        {"label": "Use a shorter indicator period"},
                        {"label": "Choose a simpler supported rule"},
                    ],
                },
            ),
        }
    if error_code in {
        "missing_rule_group",
        "unsupported_rule_operator",
        "unsupported_indicator",
        "unsupported_indicator_threshold",
    }:
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["entry_logic"],
            "requested_field": "entry_logic",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "unsupported_indicator_rule",
                    "raw_value": error_code,
                    "explanation": (
                        "The strategy direction is understandable, but the "
                        "entry rule is not executable as structured."
                    ),
                    "simplification_options": [
                        {"label": "Use a supported RSI threshold rule"},
                        {"label": "Use a supported moving-average crossover"},
                        {"label": "Keep the full idea as a draft"},
                    ],
                },
            ),
        }
    return {
        "outcome": "needs_clarification",
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": None,
        "optional_parameter_status": _with_unsupported_constraint(
            {},
            {
                "category": "launch_payload_not_executable",
                "raw_value": error_code,
                "explanation": (
                    "One part of the draft is not executable in the current "
                    "backtest engine."
                ),
                "simplification_options": [
                    {"label": "Adjust the strategy rule"},
                    {"label": "Adjust the asset"},
                    {"label": "Adjust the date range"},
                ],
            },
        ),
    }
