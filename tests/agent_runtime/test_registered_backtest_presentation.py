"""The declared backtest binding preserves executed facts without sharing."""

from __future__ import annotations

from copy import deepcopy

import pytest
from argus.agent_runtime.tools.registered_backtest import (
    BacktestExecutionResult,
    backtest_execution_result,
    get_backtest_declaration,
)
from argus.domain.tool_contracts import ToolCall, ToolOutcome
from faker import Faker

from tests.public_excerpt_factories import (
    CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT,
    GENERATED_CARD_CONFIG_SNAPSHOT,
    build_chart,
    build_generated_artifact,
    generated_card_snapshot,
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
def test_declared_card_retains_complete_canonical_dca_facts(language):
    final, artifact, chart = _completed_final(language)
    outcome = ToolOutcome(
        status="succeeded",
        result=backtest_execution_result(final).model_dump(mode="json"),
    )
    declaration = get_backtest_declaration()
    card = declaration.result_card(
        call=ToolCall(
            tool_name=declaration.name,
            call_id=fake.uuid4(),
            arguments={"strategy": {"asset_universe": final["result_card"]["symbols"]}},
        ),
        outcome=outcome,
        artifact_id=fake.uuid4(),
    )
    presentation = card.presentation
    rows = {fact.name: fact for fact in [presentation.answer, *presentation.rows] if fact}
    expected = {
        row["key"]: row["value"]
        for row in final["result_card"]["rows"]
        if row["key"] != "benchmark_delta"
    }
    assert {key: rows[key].value for key in expected} == expected
    assert presentation.answer.name == "contribution_return_pct"
    assert rows["strategy.cadence"].value == "monthly"
    assert rows["start_date"].value == final["result_card"]["date_range"]["start"]
    assert rows["end_date"].value == final["result_card"]["date_range"]["end"]
    assert (
        rows["benchmark_symbol"].value
        == GENERATED_CARD_CONFIG_SNAPSHOT["benchmark_symbol"]
    )
    assert (
        rows["delta_vs_benchmark_pct"].unit.locale_key
        == "chat.tools.units.percentage_points"
    )
    assert presentation.visual.model_dump(mode="json") == {
        key: chart[key] for key in ("kind", "currency", "base_value", "series")
    }

    notes = {note.locale_key.rsplit(".", 1)[-1]: note for note in presentation.notes}
    plan = GENERATED_CARD_CONFIG_SNAPSHOT["engine_config"]["dca_capital"]
    assert (
        float(notes["starting_principal"].interpolation_args["amount"])
        == plan["starting_capital"]
    )
    assert (
        float(notes["recurring_contribution"].interpolation_args["amount"])
        == plan["contribution"]
    )
    assert "monthly" in notes
    assert "modeled_fee_bps" in notes
    assert "modeled_slippage_bps" in notes
    assert "receipt" not in outcome.result
    assert "facts" in outcome.result


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


@pytest.mark.parametrize("template", ["buy_and_hold", "rsi_mean_reversion"])
def test_projection_preserves_non_dca_strategy_facts(template):
    from argus.domain.backtesting.cards import build_result_card

    final, _, _ = _completed_final("en")
    final = deepcopy(final)
    config = final["result"]["resolved_parameters"]["engine_config"]
    config.update(template=template, starting_capital=10_000, parameters={})
    config.pop("dca_capital")
    final["result"]["resolved_strategy"] = {"strategy_type": template}
    if template == "rsi_mean_reversion":
        config["parameters"] = {
            "indicator": "rsi",
            "indicator_period": 14,
            "entry_threshold": 30.0,
            "exit_threshold": 55.0,
        }
        final["result"]["resolved_strategy"]["strategy_type"] = "indicator_threshold"
    final["result_card"] = build_result_card(config, final["result"]["metrics"])
    facts = backtest_execution_result(final).facts
    assert "total_return_pct" in {metric.key for metric in facts.metrics}
    values = {fact.key: fact.value for fact in facts.strategy_facts}
    assert "cadence" not in values
    if template == "rsi_mean_reversion":
        assert values["indicator"] == "rsi"
        assert float(values["indicator_period"]) == 14
        assert float(values["entry_threshold"]) == 30.0
        assert float(values["exit_threshold"]) == 55.0


@pytest.mark.parametrize("missing", ["benchmark_return_pct", "delta_vs_benchmark_pct"])
def test_missing_benchmark_number_withholds_the_whole_result(missing):
    from argus.domain.tool_declaration import ToolInvocationError

    final, _, _ = _completed_final("en")
    final = deepcopy(final)
    del final["result"]["metrics"]["aggregate"]["performance"][missing]
    with pytest.raises(ToolInvocationError):
        backtest_execution_result(final)


@pytest.mark.parametrize("seed", [0, 1000])
def test_projection_preserves_seed_and_zero_benchmark_without_fallback(seed, monkeypatch):
    final, _, _ = _completed_final("en")
    final = deepcopy(final)
    engine = final["result"]["resolved_parameters"]["engine_config"]
    engine["dca_capital"]["starting_capital"] = seed
    final["result"]["metrics"]["aggregate"]["performance"].update(
        benchmark_return_pct=0, delta_vs_benchmark_pct=0
    )
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    facts = backtest_execution_result(final).facts
    assumptions = {fact.key: fact.value for fact in facts.assumptions}
    metrics = {fact.key: fact.value for fact in facts.metrics}
    assert assumptions["starting_principal"] == seed
    assert assumptions["recurring_contribution"] == engine["dca_capital"]["contribution"]
    assert assumptions["modeled_fee_bps"] == engine["_execution_realism"]["fee_bps"]
    assert metrics["benchmark_return_pct"] == "+0.0%"
    # A zero benchmark leaves the whole shown return as the gap.
    assert metrics["delta_vs_benchmark_pct"] == "18.4"


def test_crossover_preserves_independent_exit_windows():
    from argus.domain.backtesting.cards import build_result_card

    final, _, _ = _completed_final("en")
    snapshot = deepcopy(generated_card_snapshot("moving_average_crossover"))
    strategy = deepcopy(CROSSOVER_DIFFERING_EXIT_CONFIG_SNAPSHOT["resolved_strategy"])
    snapshot["resolved_strategy"] = strategy
    final["result"] = {**final["result"], **snapshot}
    final["result_card"] = build_result_card(
        snapshot["engine_config"], final["result"]["metrics"]
    )
    facts = backtest_execution_result(final).facts
    values = {fact.key: fact.value for fact in facts.strategy_facts}
    for key in ("fast_indicator", "fast_period", "slow_indicator", "slow_period"):
        assert values[key] == strategy["entry_rule"][key]
        assert values[f"exit_{key}"] == strategy["exit_rule"][key]


def test_missing_modeled_cost_cannot_turn_into_zero():
    from argus.domain.tool_declaration import ToolInvocationError

    final, _, _ = _completed_final("en")
    final = deepcopy(final)
    raw = final["result"]["resolved_parameters"]["engine_config"]["_execution_realism"]
    raw["enabled"] = "true"
    del raw["fee_bps"]
    with pytest.raises(ToolInvocationError):
        backtest_execution_result(final)


@pytest.mark.parametrize(
    "path,value",
    [
        (("result_card", "date_range", "start"), "2024-02-30"),
        (
            (
                "result",
                "resolved_parameters",
                "engine_config",
                "_execution_realism",
                "fee_bps",
            ),
            None,
        ),
        (
            (
                "result",
                "resolved_parameters",
                "engine_config",
                "dca_capital",
                "contribution",
            ),
            0,
        ),
        (("result_card", "chart", "series", 0, "value"), float("nan")),
        (("result", "metrics", "aggregate", "risk", "max_drawdown_pct"), float("nan")),
    ],
)
def test_invalid_required_facts_never_become_a_partial_answer(path, value):
    from argus.domain.tool_declaration import ToolInvocationError

    final, _, _ = _completed_final("en")
    final = deepcopy(final)
    cursor = final
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(ToolInvocationError) as error:
        backtest_execution_result(final)
    assert error.value.outcome.status == "unavailable"
    assert error.value.outcome.result is None
