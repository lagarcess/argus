"""The existing backtest worker preserves its declared result binding."""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from argus.agent_runtime.artifacts.drafts import draft_from_failed_launch_payload
from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.results import build_success_envelope
from argus.domain.tool_contracts import ToolCall, ToolResultCard
from argus.domain.tool_job_binding import bind_tool_job_call
from faker import Faker

from tests.public_excerpt_factories import (
    GENERATED_CARD_CONFIG_SNAPSHOT,
    build_chart,
    build_generated_artifact,
)
from tests.test_render_workflow_execution import (
    FakeBacktestJobGateway,
    FakeBacktestTool,
    _job_row,
)

fake = Faker()


def _request_payload(language: str = "en") -> dict:
    config = GENERATED_CARD_CONFIG_SNAPSHOT["engine_config"]
    return LaunchBacktestRequest.model_validate(
        {
            **config,
            "strategy_type": config["template"],
            "symbol": config["symbols"][0],
            "date_range": {"start": config["start_date"], "end": config["end_date"]},
            "sizing_mode": "capital_amount",
            "starting_capital": config["dca_capital"]["starting_capital"],
            "recurring_contribution": config["dca_capital"]["contribution"],
            "cadence": config["parameters"]["dca_cadence"],
            "language": language,
        }
    ).model_dump(mode="json", by_alias=True)


def _call(language: str = "en") -> ToolCall:
    declaration = get_backtest_declaration()
    arguments = declaration.validate_arguments(
        {
            "strategy": draft_from_failed_launch_payload(
                _request_payload(language)
            ).model_dump(mode="json")
        }
    )
    return ToolCall(
        tool_name=declaration.name,
        call_id=fake.uuid4(),
        arguments=arguments.model_dump(mode="json"),
    )


def test_backtest_admission_freezes_binding_before_dispatch(monkeypatch) -> None:
    from argus.agent_runtime.stages import tool_execution
    from argus.api.chat.backtest_jobs import (
        BacktestJobShadowContext,
        shadow_launch_payload,
    )

    call, artifact_id = _call(), fake.uuid4()
    context = SimpleNamespace(call=call, artifact_id=artifact_id)
    monkeypatch.setattr(tool_execution, "current_tool_execution_context", lambda: context)
    payload = shadow_launch_payload(
        payload=_request_payload(),
        context=BacktestJobShadowContext(
            user_id=fake.uuid4(), conversation_id=fake.uuid4(), account_kind="registered"
        ),
    )
    assert payload["tool_binding"]["call"] == call.model_dump(mode="json")
    assert payload["tool_binding"]["artifact_id"] == artifact_id
    assert "tool_binding" not in payload["request"]


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_async_backtest_persists_same_declared_card_and_replays_once(language) -> None:
    from workflows.backtest_job import run_backtest_job

    artifact = build_generated_artifact(language=language)
    config = deepcopy(GENERATED_CARD_CONFIG_SNAPSHOT)
    envelope = build_success_envelope(
        resolved_strategy={
            **config["resolved_strategy"],
            "asset_universe": config["symbols"],
        },
        resolved_parameters={
            **config["resolved_parameters"],
            "benchmark_symbol": config["benchmark_symbol"],
        },
        metrics=artifact.payload["metrics"],
        benchmark_metrics={},
        assumptions=[],
        caveats=[],
        provider_metadata={},
    ).model_dump(mode="json")

    call, artifact_id = _call(language), fake.uuid4()
    row = _job_row(
        launch_payload={
            "kind": "run_backtest_job",
            "request": _request_payload(language),
            "tool_binding": bind_tool_job_call(call=call, artifact_id=artifact_id),
        }
    )
    gateway = FakeBacktestJobGateway(row)
    tool = FakeBacktestTool(
        {
            "success": True,
            "payload": {
                "envelope": envelope,
                "result_card": {
                    **artifact.payload["result_card"],
                    "chart": build_chart(),
                },
                "explanation_context": {},
            },
        }
    )
    result = run_backtest_job(gateway, job_id=row["id"], backtest_tool=tool)
    assert result["status"] == "succeeded"
    run = gateway.finalization_store.backtest_runs[result["result_run_id"]]
    cards = run.conversation_result_card["tool_result_cards"]
    card = ToolResultCard.model_validate(cards[0])
    assert card.call_id == call.call_id and card.artifact_id == artifact_id
    assert card.presentation.answer is not None
    expected = next(
        row
        for row in artifact.payload["result_card"]["rows"]
        if row["key"] == card.presentation.answer.name
    )
    assert card.presentation.answer.value == expected["value"]
    assert ToolResultCard.model_validate(json.loads(json.dumps(cards[0]))) == card
    run_backtest_job(gateway, job_id=row["id"], backtest_tool=tool)
    assert len(tool.calls) == 1
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1
