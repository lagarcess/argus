"""The declared backtest binding preserves the canonical receipt's facts."""

from __future__ import annotations

import pytest
from argus.agent_runtime.tools.registered_backtest import (
    BacktestExecutionResult,
    backtest_execution_result,
    get_backtest_declaration,
)
from argus.domain.tool_contracts import ToolCall, ToolOutcome
from faker import Faker

from tests.public_excerpt_factories import (
    GENERATED_CARD_CONFIG_SNAPSHOT,
    build_chart,
    build_generated_artifact,
)

fake = Faker()


def _completed_final(language: str):
    artifact = build_generated_artifact(language=language)
    chart = build_chart()
    legacy_card = {**artifact.payload["result_card"], "chart": chart}
    envelope = {
        "execution_status": "succeeded",
        "resolved_strategy": GENERATED_CARD_CONFIG_SNAPSHOT["resolved_strategy"],
        "resolved_parameters": {
            **GENERATED_CARD_CONFIG_SNAPSHOT["resolved_parameters"],
            "benchmark_symbol": GENERATED_CARD_CONFIG_SNAPSHOT["benchmark_symbol"],
        },
        "metrics": artifact.payload["metrics"],
    }
    return {"result": envelope, "result_card": legacy_card}, artifact, chart


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_declared_card_retains_complete_canonical_dca_receipt_facts(language):
    from argus.domain.public_excerpts import backtest_receipt_facts

    final, artifact, chart = _completed_final(language)
    expected = backtest_receipt_facts(
        source=artifact.payload,
        title=artifact.title,
        run_chart=chart,
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
    )
    outcome = ToolOutcome(
        status="succeeded",
        result=backtest_execution_result(final).model_dump(mode="json"),
    )
    declaration = get_backtest_declaration()
    card = declaration.result_card(
        call=ToolCall(
            tool_name=declaration.name,
            call_id=fake.uuid4(),
            arguments={"strategy": {"asset_universe": expected.symbols}},
        ),
        outcome=outcome,
        artifact_id=fake.uuid4(),
    )
    presentation = card.presentation
    rows = {fact.name: fact for fact in [presentation.answer, *presentation.rows] if fact}
    assert {metric.key: rows[metric.key].value for metric in expected.metrics} == {
        metric.key: metric.value for metric in expected.metrics
    }
    assert {
        fact.key: rows[f"strategy.{fact.key}"].value for fact in expected.strategy_facts
    } == {fact.key: fact.value for fact in expected.strategy_facts}
    assert rows["start_date"].value == expected.date_range.start
    assert rows["end_date"].value == expected.date_range.end
    assert rows["benchmark_symbol"].value == expected.benchmark_symbol
    assert (
        rows["delta_vs_benchmark_pct"].unit.locale_key
        == "chat.tools.units.percentage_points"
    )
    assert presentation.visual == expected.visual

    notes = {note.locale_key.rsplit(".", 1)[-1]: note for note in presentation.notes}
    for assumption in expected.assumptions:
        if assumption.key == "contribution_cadence":
            assert assumption.value in notes
        else:
            assert notes[assumption.key].interpolation_args["value"] == assumption.value
    plan = GENERATED_CARD_CONFIG_SNAPSHOT["engine_config"]["dca_capital"]
    assert notes["starting_principal"].interpolation_args["amount"] == str(
        int(plan["starting_capital"])
    )
    assert notes["recurring_contribution"].interpolation_args["amount"] == str(
        plan["contribution"]
    )
    assert "modeled_fee_bps" in notes
    assert "modeled_slippage_bps" in notes


def test_pending_declared_backtest_has_no_answer_or_visual():
    declaration = get_backtest_declaration()
    call = ToolCall(
        tool_name=declaration.name, call_id=fake.uuid4(), arguments={"strategy": {}}
    )
    card = declaration.result_card(
        call=call,
        outcome=ToolOutcome(
            status="succeeded",
            result=BacktestExecutionResult(
                execution_status="pending", job_id=fake.uuid4()
            ).model_dump(mode="json"),
        ),
        artifact_id=fake.uuid4(),
    )
    assert card.presentation.answer is None
    assert card.presentation.visual is None


def test_unprojectable_result_never_becomes_a_partial_declared_answer():
    from argus.domain.tool_declaration import ToolInvocationError

    final, _, _ = _completed_final("en")
    final["result_card"]["rows"].append({"key": "unknown_metric", "value": "1"})
    with pytest.raises(ToolInvocationError) as error:
        backtest_execution_result(final)
    assert error.value.outcome.status == "unavailable"
    assert error.value.outcome.result is None
