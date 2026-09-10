"""Bind executed backtest facts to the declared result card."""

from __future__ import annotations

from typing import Any, Literal

from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.tools.backtest_result_facts import (
    BacktestCardFacts,
    backtest_card_facts,
)
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCardPresentation,
    ToolFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import ToolInvocationError
from pydantic import BaseModel, ConfigDict, model_validator


class BacktestArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: BacktestStrategyInput


class BacktestExecutionResult(BaseModel):
    """Safe result facts; trusted context retains launch and provider records."""

    model_config = ConfigDict(extra="forbid")
    execution_status: Literal["succeeded", "pending"]
    facts: BacktestCardFacts | None = None
    job_id: str | None = None

    @model_validator(mode="after")
    def completed_results_have_complete_facts(self) -> BacktestExecutionResult:
        if self.execution_status == "succeeded" and self.facts is None:
            raise ValueError("A completed backtest needs its complete executed facts")
        if self.execution_status == "pending" and self.facts is not None:
            raise ValueError("A pending backtest cannot carry completed result facts")
        return self


def backtest_execution_result(final: dict[str, Any]) -> BacktestExecutionResult:
    """Use one fact owner for in-process and background tool results."""
    result = final.get("result")
    card = final.get("result_card")
    if not isinstance(result, dict) or not isinstance(card, dict):
        raise ToolInvocationError("unavailable", code="invalid_backtest_result")
    parameters = result.get("resolved_parameters")
    if not isinstance(parameters, dict):
        raise ToolInvocationError("unavailable", code="invalid_backtest_result")
    try:
        facts = backtest_card_facts(result=result, card=card)
    except (ValueError, TypeError, KeyError) as exc:
        raise ToolInvocationError(
            "unavailable", code="unprojectable_backtest_result"
        ) from exc
    return BacktestExecutionResult(execution_status="succeeded", facts=facts)


def backtest_presentation(
    arguments: BacktestArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    title = LocalizedText(
        locale_key="chat.tools.backtest.title",
        interpolation_args={
            "asset_universe": ", ".join(arguments.strategy.asset_universe)
        },
    )
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title)
    facts = BacktestExecutionResult.model_validate(outcome.result).facts
    if facts is None:
        return ToolCardPresentation(title=title)
    metrics = [
        ToolFact(
            name=metric.key,
            label=LocalizedText(locale_key=f"receipt.metric_labels.{metric.key}"),
            value=metric.value,
            unit=(
                LocalizedText(locale_key="chat.tools.units.percentage_points")
                if metric.key == "delta_vs_benchmark_pct"
                else None
            ),
        )
        for metric in facts.metrics
    ]
    headline = next(
        (
            row
            for row in metrics
            if row.name in {"total_return_pct", "contribution_return_pct"}
        ),
        metrics[0] if metrics else None,
    )
    rows = [metric for metric in metrics if metric is not headline]
    rows.extend(
        ToolFact(
            name=f"strategy.{fact.key}",
            label=LocalizedText(locale_key=f"receipt.strategy_facts.{fact.key}"),
            value=fact.value,
            value_text=(
                LocalizedText(locale_key=f"receipt.{fact.key}_values.{fact.value}")
                if fact.key in {"strategy_type", "cadence"}
                else None
            ),
        )
        for fact in facts.strategy_facts
    )
    rows.extend(
        [
            ToolFact(
                name="symbols",
                label=LocalizedText(locale_key="receipt.fields.asset"),
                value=", ".join(facts.symbols),
            ),
            ToolFact(
                name="start_date",
                label=LocalizedText(locale_key="chat.tools.backtest.start_date"),
                value=facts.date_range.start,
            ),
            ToolFact(
                name="end_date",
                label=LocalizedText(locale_key="chat.tools.backtest.end_date"),
                value=facts.date_range.end,
            ),
        ]
    )
    if facts.asset_class is not None:
        rows.append(
            ToolFact(
                name="asset_class",
                label=LocalizedText(locale_key="receipt.fields.asset_class"),
                value=facts.asset_class,
                value_text=LocalizedText(
                    locale_key=f"receipt.asset_class_values.{facts.asset_class}"
                ),
            )
        )
    if facts.benchmark_symbol is not None:
        rows.append(
            ToolFact(
                name="benchmark_symbol",
                label=LocalizedText(locale_key="receipt.fields.benchmark"),
                value=facts.benchmark_symbol,
            )
        )
    # Every assumption comes from the canonical projector. Templates select the
    # argument they need; all interpolation aliases derive from that same fact.
    notes = [
        LocalizedText(
            locale_key=(
                f"receipt.cadence_values.{fact.value}"
                if fact.key == "contribution_cadence"
                else f"receipt.assumptions.{fact.key}"
            ),
            interpolation_args={
                name: fact.value for name in ("value", "amount", "bps", "symbol")
            },
        )
        for fact in facts.assumptions
    ]
    return ToolCardPresentation(
        title=title,
        answer=headline,
        rows=rows,
        notes=notes,
        visual=facts.visual,
    )
