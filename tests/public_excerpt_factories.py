"""Shared builders for public evidence receipt tests.

Every case derives its expected values from these builders so a change to the
frozen payload shape shows up in one place instead of in a dozen literals.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from argus.api.schemas import BacktestRun, Conversation, EvidenceArtifact
from argus.domain.backtesting.cards import (
    build_result_card as generate_result_card,
)

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
    """Weekday bars walked with a real calendar, not by counting up a day number.

    Formatting the index into a fixed month produced 2024-01-32 past thirty bars,
    which no exchange ever traded and which crashed the chart on the rendered page.
    A series long enough to look like a real run has to leave the month.
    """
    series: list[dict[str, Any]] = []
    day = date.fromisoformat(WINDOW_START)
    while len(series) < points:
        if day.weekday() < 5:
            series.append(
                {
                    "time": day.isoformat(),
                    "value": 10_000.0 + len(series) * 120.0 * scale,
                }
            )
        day += timedelta(days=1)
    return series


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
        "benchmark_note": None,
        # What build_result_card actually writes: prose, in the language the author
        # was working in. The receipt must not read any of it, so the fixture keeps
        # it rather than tidying it away.
        "assumptions": [
            "Long-only",
            "Equal weight",
            "No fees/slippage",
            "Benchmark: SPY",
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
        # The engine always computes a benchmark, so a fixture without one describes
        # a run that cannot exist and would let the projection pass on a payload
        # that names SPY and carries no number for it.
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 18.4,
                    "benchmark_return_pct": 9.1,
                    "delta_vs_benchmark_pct": 9.3,
                }
            }
        },
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
    # The agent path nests the engine config the run was handed, exactly as
    # engine_launch/adapter.py builds it, so the receipt reads the same numbers the
    # engine did rather than a paraphrase of them.
    "resolved_parameters": {
        "cadence": "monthly",
        "recurring_contribution": 200,
        "starting_principal": 0.0,
        "engine_config": {
            "template": "dca_accumulation",
            "starting_capital": 200,
            "recurring_contribution": 200,
            "starting_principal": 0.0,
            "parameters": {"dca_cadence": "monthly"},
            "allocation_method": "equal_weight",
            "side": "long",
        },
    },
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
# parameters sit under `parameters` with no resolved_* nesting at all. Normalization
# always fills starting_capital, and the DCA builder always sets the contribution
# pair, so a fixture without them would let the projection pass on a config the
# engine never produces.
ENGINE_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "dca_accumulation",
    "symbols": ["AAPL"],
    "parameters": {"dca_cadence": "weekly"},
    "starting_capital": 500,
    "recurring_contribution": 500,
    "starting_principal": 0.0,
    "allocation_method": "equal_weight",
    "side": "long",
}

# The same direct engine config with costs modeled. `_execution_realism` is written
# into the config only when the feature was on for the run, which is what makes it
# the frozen record of what the engine was told to charge.
ENGINE_MODELED_COSTS_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "buy_and_hold",
    "symbols": ["AAPL"],
    "parameters": {},
    "starting_capital": 10_000,
    "allocation_method": "equal_weight",
    "side": "long",
    "_execution_realism": {"enabled": True, "fee_bps": 10.0, "slippage_bps": 5.0},
}

# The engine config a real recurring-contribution run with modeled costs executes.
# Every assumption the result card can produce is reachable from it: the pair of
# contribution facts, the pair of cost facts, and the benchmark that carried them.
GENERATED_CARD_CONFIG: dict[str, Any] = {
    "template": "dca_accumulation",
    "asset_class": "equity",
    "symbols": ["AAPL"],
    "timeframe": "1D",
    "start_date": WINDOW_START,
    "end_date": WINDOW_END,
    "side": "long",
    "starting_capital": 200,
    "allocation_method": "equal_weight",
    "benchmark_symbol": "SPY",
    "parameters": {"dca_cadence": "monthly"},
    "recurring_contribution": 200,
    "starting_principal": 0.0,
    "_execution_realism": {"enabled": True, "fee_bps": 10.0, "slippage_bps": 5.0},
}

GENERATED_CARD_METRICS: dict[str, Any] = {
    "aggregate": {
        "performance": {
            "profit": 120.0,
            "total_return_pct": 18.4,
            # The engine computes both halves of the comparison, so a fixture with
            # only the delta describes a run it does not produce.
            "benchmark_return_pct": 9.1,
            "delta_vs_benchmark_pct": 9.3,
            "execution_realism": {
                "enabled": True,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
                "gross_total_return_pct": 19.0,
                "net_total_return_pct": 18.4,
                "return_drag_pct": 0.6,
            },
        },
        "risk": {"max_drawdown_pct": -6.2},
        "efficiency": {"total_trades": 3, "win_rate": 0.66},
    }
}


def build_generated_artifact(
    *,
    language: str,
    title: str = "AAPL every month",
) -> EvidenceArtifact:
    """An artifact whose card came from the production generator, not from a literal.

    The generator writes its assumptions and its tested window as prose, in the
    language the author was working in. A hand-written fixture cannot show that,
    which is exactly how a receipt froze one language and rendered it to everyone.
    """
    card = generate_result_card(
        GENERATED_CARD_CONFIG,
        GENERATED_CARD_METRICS,
        language=language,
    )
    return build_artifact(
        title=title,
        payload=build_artifact_payload(
            result_card=card,
            extra={
                "assumptions": list(card["assumptions"]),
                "metrics": GENERATED_CARD_METRICS,
            },
        ),
    )


# The agent path's snapshot for that same run, as backtest_run_builder writes it:
# the engine config is lifted to the top level and repeated inside the resolved
# parameters it came from.
GENERATED_CARD_CONFIG_SNAPSHOT: dict[str, Any] = {
    "template": "dca_accumulation",
    "symbols": ["AAPL"],
    "benchmark_symbol": "SPY",
    "resolved_strategy": {"strategy_type": "dca_accumulation", "cadence": "monthly"},
    "resolved_parameters": {
        "cadence": "monthly",
        "recurring_contribution": 200,
        "starting_principal": 0.0,
        "engine_config": GENERATED_CARD_CONFIG,
    },
    "engine_config": GENERATED_CARD_CONFIG,
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


# One engine config per executable template, so a projection can be driven with the
# production generator across the whole shape space rather than one canonical run.
# Derived from ALLOWED_TEMPLATES by test, so a template added later has nowhere to
# hide.
def generated_card_config(
    template: str, *, modeled_costs: bool = False
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "template": template,
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": WINDOW_START,
        "end_date": WINDOW_END,
        "side": "long",
        "starting_capital": 10_000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }
    if template == "dca_accumulation":
        config["starting_capital"] = 200
        config["recurring_contribution"] = 200
        config["starting_principal"] = 0.0
        config["parameters"] = {"dca_cadence": "monthly"}
    if modeled_costs:
        config["_execution_realism"] = {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
        }
    return config


def generated_card_metrics(*, modeled_costs: bool = False) -> dict[str, Any]:
    performance: dict[str, Any] = {
        "profit": 120.0,
        "total_return_pct": 18.4,
        "benchmark_return_pct": 9.1,
        "delta_vs_benchmark_pct": 9.3,
        "annualized_return_pct": 24.0,
    }
    if modeled_costs:
        performance["execution_realism"] = {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
            "gross_total_return_pct": 19.0,
            "net_total_return_pct": 18.4,
            "return_drag_pct": 0.6,
        }
    return {
        "aggregate": {
            "performance": performance,
            "risk": {"max_drawdown_pct": -6.2, "volatility_pct": 12.0},
            # More than one trade, so the win-rate row is actually emitted for the
            # templates that show it. A fixture that never triggers a row cannot
            # prove the projection handles it.
            "efficiency": {"total_trades": 3, "win_rate": 0.66},
        }
    }


def build_template_artifact(
    template: str,
    *,
    language: str = "en",
    modeled_costs: bool = False,
    title: str = "AAPL idea",
) -> tuple[EvidenceArtifact, dict[str, Any]]:
    """An artifact whose card came from the production generator, plus that card."""
    card = generate_result_card(
        generated_card_config(template, modeled_costs=modeled_costs),
        generated_card_metrics(modeled_costs=modeled_costs),
        language=language,
    )
    artifact = build_artifact(
        title=title,
        payload=build_artifact_payload(
            result_card=card,
            extra={
                "assumptions": list(card["assumptions"]),
                "metrics": generated_card_metrics(modeled_costs=modeled_costs),
            },
        ),
    )
    return artifact, card


# The config snapshot the agent path stores for each of those runs.
def generated_card_snapshot(
    template: str, *, modeled_costs: bool = False
) -> dict[str, Any]:
    engine_config = generated_card_config(template, modeled_costs=modeled_costs)
    resolved_strategy: dict[str, Any] = {"strategy_type": template}
    if template == "moving_average_crossover":
        resolved_strategy["entry_rule"] = {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bullish",
        }
    if template == "rsi_mean_reversion":
        resolved_strategy["entry_rule"] = {
            "indicator": "RSI",
            "period": 14,
            "threshold": 30,
            "direction": "below",
        }
        resolved_strategy["exit_rule"] = {
            "indicator": "RSI",
            "period": 14,
            "threshold": 70,
        }
    if template == "signal_strategy":
        resolved_strategy["entry_rule"] = {
            "type": "macd_crossover",
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "direction": "bullish",
        }
    if template == "dca_accumulation":
        resolved_strategy["cadence"] = "monthly"
    return {
        "template": template,
        "symbols": ["AAPL"],
        "benchmark_symbol": "SPY",
        "resolved_strategy": resolved_strategy,
        "resolved_parameters": {
            "timeframe": "1D",
            "indicator": "RSI",
            "indicator_period": 14,
            "entry_threshold": 30,
            "exit_threshold": 70,
            "engine_config": engine_config,
        },
        "engine_config": engine_config,
    }
