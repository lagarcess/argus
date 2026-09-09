"""DCA readouts retain the executed money roles across stored run shapes."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from argus.api import backtest_service
from argus.api.artifact_presentation import reader_payload
from argus.api.schemas import BacktestRunResponse
from argus.domain.backtest_message_projection import result_fact_bank
from argus.domain.backtest_run_builder import build_backtest_run_from_result
from argus.domain.dca_capital import dca_capital_plan_from_config
from argus.domain.public_excerpt_turns import project_backtest_turn
from argus.domain.public_excerpts import PublicExcerptSourceError
from argus.domain.result_readout_facts import engine_config_from_snapshot
from argus.domain.run_dossiers import project_run_dossier
from fastapi import Request

from tests.public_excerpt_factories import (
    generated_card_config,
    generated_card_metrics,
)


def direct_run(config, monkeypatch, faker):
    """Use the current direct API's run/card builder with injected engine output."""
    monkeypatch.setattr(
        backtest_service,
        "compute_alpha_metrics",
        lambda *_args, **_kwargs: generated_card_metrics(),
    )
    monkeypatch.setattr(
        backtest_service, "build_result_chart", lambda *_args, **_kwargs: None
    )
    return backtest_service.create_run_from_payload(
        {},
        Request({"type": "http", "method": "POST", "path": "/api/v1/backtests/run"}),
        conversation_id=faker.uuid4(),
        run_id=faker.uuid4(),
        persist_in_memory=False,
        prepared_execution=backtest_service.PreparedBacktestExecution(config, None),
    )


@pytest.fixture(
    params=[
        ("direct", 0.0),
        ("direct", 500.0),
        ("agent", 0.0),
        ("agent", 500.0),
        ("agent_nested_only", 0.0),
        ("legacy_direct", 0.0),
        ("conflicting_agent", 0.0),
    ],
    ids=lambda item: f"{item[0]}-seed-{item[1]:g}",
)
def dca_run(request, monkeypatch, faker):
    shape, principal = request.param
    # The browser finding's exact money/cadence shape already belongs to this
    # shared production-card fixture: dca_capital + parameters.dca_cadence.
    engine = generated_card_config("dca_accumulation")
    engine["dca_capital"]["starting_capital"] = principal
    money = deepcopy(engine["dca_capital"])
    cadence = engine["parameters"]["dca_cadence"]
    if shape == "legacy_direct":
        del engine["dca_capital"]
        engine["starting_capital"] = money["contribution"]
        engine["starting_principal"] = 0.0
    run = direct_run(engine, monkeypatch, faker)
    if "agent" in shape:
        run = build_backtest_run_from_result(
            conversation_id=run.conversation_id,
            result_card=run.conversation_result_card,
            classify_symbol_func=lambda _symbol: SimpleNamespace(asset_class="equity"),
            envelope={
                "resolved_strategy": {
                    "strategy_type": engine["template"],
                    "asset_universe": engine["symbols"],
                },
                "resolved_parameters": {
                    "timeframe": engine["timeframe"],
                    "date_range": {
                        "start": engine["start_date"],
                        "end": engine["end_date"],
                    },
                    "benchmark_symbol": engine["benchmark_symbol"],
                    "starting_capital": money["starting_capital"],
                    "recurring_contribution": money["contribution"],
                    "cadence": cadence,
                    "engine_config": engine,
                },
                "metrics": run.metrics,
            },
        )
        assert run is not None
        if shape == "agent_nested_only":
            del run.config_snapshot["engine_config"]
        if shape == "conflicting_agent":
            run.config_snapshot["resolved_parameters"].update(
                starting_capital=9_000.0, recurring_contribution=7_000.0, cadence="weekly"
            )
            run.config_snapshot["resolved_strategy"].update(
                initial_capital=8_000.0,
                recurring_contribution=6_000.0,
                contribution_period="daily",
            )
    expected = {
        "starting_capital": money["starting_capital"],
        "recurring_contribution": money["contribution"],
        "cadence": cadence,
    }
    return run, expected


def reader_bank(boundary, run):
    # Emulate an already-stored bank. Calling the current producer here would
    # hide the historical-reader bug as soon as that producer is fixed.
    stored_bank = {**run.model_dump(), "result_card": run.conversation_result_card}
    stored_before = deepcopy(stored_bank)
    if boundary == "producer":
        result = result_fact_bank(run)
    elif boundary == "message":
        result = reader_payload({"result_fact_bank": stored_bank})["result_fact_bank"]
    elif boundary == "breakdown":
        result = reader_payload(
            {
                "response_intent": {
                    "kind": "result_breakdown",
                    "facts": {"result_fact_bank": stored_bank},
                }
            }
        )["response_intent"]["facts"]["result_fact_bank"]
    elif boundary == "direct_response":
        result = BacktestRunResponse(run=run).model_dump(mode="json")["run"]
    else:
        result = project_run_dossier(
            run=run.model_dump(),
            artifact={"id": "test-artifact", "source_run_id": run.id},
            decision=None,
            result_message_id=None,
            decision_action_availability=None,
        ).outcome.result_fact_bank
    assert stored_bank == stored_before
    return result


BOUNDARIES = ("producer", "message", "breakdown", "direct_response", "dossier")


def test_dossier_summary_uses_the_executed_cadence(dca_run):
    run, expected = dca_run
    dossier = project_run_dossier(
        run=run.model_dump(),
        artifact={"id": "test-artifact", "source_run_id": run.id},
        decision=None,
        result_message_id=None,
        decision_action_availability=None,
    )
    assert dossier.tested.cadence == expected["cadence"]


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_readers_and_receipt_keep_the_executed_dca_plan(dca_run, boundary):
    run, expected = dca_run
    original = deepcopy(run.model_dump())
    bank = reader_bank(boundary, run)
    parameters = bank["config_snapshot"].get("resolved_parameters", {})
    assert {key: parameters.get(key) for key in expected} == expected
    # Re-reading the projected config must still expose the executed plan. In
    # legacy configs the raw starting_capital slot was the contribution, so a
    # projected zero seed must never overwrite it during structural unwrapping.
    plan = dca_capital_plan_from_config(
        engine_config_from_snapshot(bank["config_snapshot"])
    )
    assert plan.contribution == expected["recurring_contribution"]
    assert plan.starting_capital == expected["starting_capital"]
    assert plan.period == expected["cadence"]

    leaf = project_backtest_turn(
        run=run, title="Recurring example", owner_note=None, language="en", private_ids=()
    )
    frozen = leaf.fact_bank.config_snapshot.resolved_parameters.model_dump()
    assert {key: frozen[key] for key in expected} == expected
    assert leaf.fact_bank.figures.total_return_pct is not None
    if expected["starting_capital"] == 0:
        assert "Starting capital: $0" in run.conversation_result_card["assumptions"]
    assert "Contribution: $200 monthly" in run.conversation_result_card["assumptions"]
    assert "dca_capital" not in leaf.fact_bank.config_snapshot.model_dump()
    assert "engine_config" not in leaf.model_dump_json()

    # A consumer editing its transport copy must not edit the stored run.
    parameters["starting_capital"] = -1
    assert run.model_dump() == original


@pytest.mark.parametrize("boundary", BOUNDARIES)
@pytest.mark.parametrize("invalid_field", ["contribution", "cadence"])
def test_unverifiable_historical_plan_keeps_reading_but_cannot_publish(
    monkeypatch, faker, boundary, invalid_field
):
    config = generated_card_config("dca_accumulation")
    run = direct_run(config, monkeypatch, faker)
    if invalid_field == "contribution":
        config["dca_capital"]["contribution"] = "unknown"
    else:
        config["parameters"]["dca_cadence"] = "unsupported"
    run.config_snapshot = config
    original = deepcopy(run.model_dump())
    assert reader_bank(boundary, run)["config_snapshot"] == config
    with pytest.raises(PublicExcerptSourceError):
        project_backtest_turn(
            run=run,
            title="Recurring example",
            owner_note=None,
            language="en",
            private_ids=(),
        )
    assert run.model_dump() == original


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_non_recurring_config_is_unchanged(monkeypatch, faker, boundary):
    config = generated_card_config("buy_and_hold")
    run = direct_run(config, monkeypatch, faker)
    assert reader_bank(boundary, run)["config_snapshot"] == config
