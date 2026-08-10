"""Shared builders for public evidence receipt tests.

Every case derives its expected values from these builders so a change to the
frozen payload shape shows up in one place instead of in a dozen literals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from argus.api.schemas import BacktestRun, Conversation, EvidenceArtifact

CONVERSATION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"
ARTIFACT_ID = "33333333-3333-4333-8333-333333333333"
IDEA_ID = "44444444-4444-4444-8444-444444444444"
IDEA_VERSION_ID = "55555555-5555-4555-8555-555555555555"
STRATEGY_ID = "66666666-6666-4666-8666-666666666666"

# A weekday window, because a fixture that puts bars on a weekend passes green
# and breaks on a real exchange calendar.
WINDOW_START = "2024-01-02"
WINDOW_END = "2024-03-01"


def utc(offset_minutes: int = 0) -> datetime:
    return datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc) + timedelta(
        minutes=offset_minutes
    )


def chart_series(points: int = 8, *, scale: float = 1.0) -> list[dict[str, Any]]:
    return [
        {"time": f"2024-01-{index + 2:02d}", "value": 10_000.0 + index * 120.0 * scale}
        for index in range(points)
    ]


def build_chart(points: int = 8, *, scale: float = 1.0) -> dict[str, Any]:
    return {
        "kind": "portfolio_equity",
        "currency": "USD",
        "base_value": 10_000.0,
        "series": chart_series(points, scale=scale),
        "markers": [{"time": WINDOW_START, "type": "entry", "label": "Entry"}],
        "attribution": "Argus",
    }


def build_result_card(
    *,
    title: str = "AAPL buy and hold",
    total_return: str = "+18.4%",
) -> dict[str, Any]:
    return {
        "title": title,
        "symbols": ["AAPL"],
        "strategy_label": "Buy and hold",
        "asset_class": "equity",
        "date_range": {
            "start": WINDOW_START,
            "end": WINDOW_END,
            "display": "Jan 2, 2024 to Mar 1, 2024",
        },
        "status_label": "Completed",
        "rows": [
            {"key": "total_return_pct", "label": "Total return", "value": total_return},
            {"key": "benchmark_return_pct", "label": "SPY", "value": "+9.1%"},
            {"key": "max_drawdown_pct", "label": "Max drawdown", "value": "-6.2%"},
        ],
        "benchmark_note": "Compared against SPY over the same window.",
        "assumptions": [
            "Long only, no leverage.",
            "Modeled commissions and slippage.",
        ],
        "quick_take": "AAPL beat SPY over this window.",
    }


def build_artifact_payload(
    *,
    result_card: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = result_card if result_card is not None else build_result_card()
    payload: dict[str, Any] = {
        "artifact_type": "backtest",
        "digest": "AAPL beat SPY over this window.",
        # Private plumbing the artifact legitimately carries. None of it may
        # reach a receipt.
        "source": {
            "run_id": RUN_ID,
            "conversation_id": CONVERSATION_ID,
            "strategy_id": STRATEGY_ID,
        },
        "assumptions": list(card["assumptions"]),
        "metrics": {"aggregate": {"performance": {"total_return_pct": 18.4}}},
        "quick_take": card.get("quick_take"),
        "breakdown": None,
        "result_card": card,
        "chart_summary": {"kind": "portfolio_equity", "points": 8, "currency": "USD"},
        "provenance": {
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "created_at": utc().isoformat(),
        },
    }
    if extra:
        payload.update(extra)
    return payload


def build_artifact(
    *,
    artifact_id: str = ARTIFACT_ID,
    payload: dict[str, Any] | None = None,
    title: str = "AAPL buy and hold",
    artifact_type: str = "backtest",
) -> EvidenceArtifact:
    return EvidenceArtifact(
        id=artifact_id,
        idea_id=IDEA_ID,
        idea_version_id=IDEA_VERSION_ID,
        source_conversation_id=CONVERSATION_ID,
        source_run_id=RUN_ID,
        artifact_type=artifact_type,
        lifecycle="captured",
        title=title,
        digest="AAPL beat SPY over this window.",
        payload=payload if payload is not None else build_artifact_payload(),
        created_at=utc(),
        updated_at=utc(),
    )


def build_run(
    *,
    run_id: str = RUN_ID,
    chart: dict[str, Any] | None = None,
    total_return: str = "+18.4%",
) -> BacktestRun:
    return BacktestRun(
        id=run_id,
        conversation_id=CONVERSATION_ID,
        strategy_id=STRATEGY_ID,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 18.4}}},
        config_snapshot={"template": "buy_and_hold"},
        conversation_result_card=build_result_card(total_return=total_return),
        created_at=utc(),
        chart=chart if chart is not None else build_chart(),
    )


def build_conversation(
    *, conversation_id: str = CONVERSATION_ID, language: str = "en"
) -> Conversation:
    return Conversation(
        id=conversation_id,
        title="AAPL idea",
        title_source="user_renamed",
        pinned=False,
        archived=False,
        deleted_at=None,
        created_at=utc(-60),
        updated_at=utc(),
        last_message_preview="AAPL",
        language=language,
    )


def new_uuid() -> str:
    return str(uuid4())


def stable_uuid(seed: int, *, prefix: int = 9) -> str:
    """A deterministic uuid for bulk fixtures.

    Ids reach a uuid column in production, so a fixture using a readable string
    would let the in-memory backend accept a shape the real one rejects.
    """
    return f"{prefix:08d}-0000-4000-8000-{seed:012d}"


# Non-buy-and-hold shapes. AGENTS.md requires acceptance evidence to span the
# strategy-shape space rather than standardising on the oldest, simplest shape,
# and buy and hold is the one shape whose label alone describes it.
INDICATOR_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "indicator_threshold",
    "resolved_strategy": {
        "strategy_type": "indicator_threshold",
        "entry_rule": {
            "indicator": "RSI",
            "period": 14,
            "threshold": 30,
            "direction": "below",
        },
        "exit_rule": {"indicator": "RSI", "period": 14, "threshold": 70},
    },
    "resolved_parameters": {
        "indicator": "RSI",
        "indicator_period": 14,
        "entry_threshold": 30,
        "exit_threshold": 70,
        "timeframe": "1D",
    },
}

DCA_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "dca_accumulation",
    "resolved_strategy": {
        "strategy_type": "dca_accumulation",
        "cadence": "monthly",
    },
    "resolved_parameters": {"cadence": "monthly", "recurring_contribution": 200},
}

BUY_AND_HOLD_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "buy_and_hold",
    "resolved_strategy": {"strategy_type": "buy_and_hold"},
    "resolved_parameters": {"capital_amount": 10_000, "timeframe": "1D"},
}

# The typed crossover rule as engine_launch/adapter.py freezes it: the parameters
# that decide the trades live in the rule, not in a generic indicator field.
CROSSOVER_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "moving_average_crossover",
    "resolved_strategy": {
        "strategy_type": "signal_strategy",
        "requested_strategy_template": "moving_average_crossover",
        "entry_rule": {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bullish",
        },
        "exit_rule": {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bearish",
        },
    },
    "resolved_parameters": {"timeframe": "1D"},
}

# The compiler builds entry and exit independently and never requires them to match,
# so a run can legitimately exit on windows it did not enter on.
CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT: dict[str, Any] = {
    **CROSSOVER_CONFIG_SNAPSHOT,
    "resolved_strategy": {
        **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
        "exit_rule": {
            "type": "moving_average_crossover",
            "fast_indicator": "ema",
            "fast_period": 9,
            "slow_indicator": "ema",
            "slow_period": 21,
            "direction": "bearish",
        },
    },
}

# A crossover entry paired with an exit of another kind: no faithful projection.
CROSSOVER_FOREIGN_EXIT_CONFIG_SNAPSHOT: dict[str, Any] = {
    **CROSSOVER_CONFIG_SNAPSHOT,
    "resolved_strategy": {
        **CROSSOVER_CONFIG_SNAPSHOT["resolved_strategy"],
        "exit_rule": {"type": "macd_crossover", "fast_period": 12, "slow_period": 26},
    },
}

MACD_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "signal_strategy",
    "resolved_strategy": {
        "strategy_type": "signal_strategy",
        "entry_rule": {
            "type": "macd_crossover",
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "direction": "bullish",
        },
    },
    "resolved_parameters": {"timeframe": "1D"},
}

BUY_THE_DIP_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "buy_the_dip",
    "resolved_strategy": {"strategy_type": "indicator_threshold"},
    "resolved_parameters": {"timeframe": "1D"},
}

# The direct engine path stores the engine config itself, so the executed
# parameters sit under `parameters` with no resolved_* nesting at all.
ENGINE_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "dca_accumulation",
    "symbols": ["AAPL"],
    "parameters": {"dca_cadence": "weekly"},
}

# A condition tree with no typed rule above it: nothing a flat fact list can
# round-trip.
GENERIC_RULE_SPEC_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "signal_strategy",
    "parameters": {
        "rule_spec": {
            "entry": {
                "conditions": [
                    {
                        "left": {"kind": "indicator", "key": "ema", "period": 9},
                        "operator": "cross_above",
                        "right": {"kind": "indicator", "key": "ema", "period": 21},
                    },
                    {
                        "left": {"kind": "indicator", "key": "rsi", "period": 14},
                        "operator": "lte",
                        "right": 40,
                    },
                ]
            },
            "exit": {
                "conditions": [
                    {
                        "left": {"kind": "indicator", "key": "rsi", "period": 14},
                        "operator": "gte",
                        "right": 65,
                    }
                ]
            },
        }
    },
}
