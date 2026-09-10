from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


class _Interpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response
        self.last_status = "unused"

    def __call__(self, request: Any) -> StructuredInterpretation:
        self.last_status = "used"
        return self.response


def _run(
    *,
    message: str,
    response: StructuredInterpretation,
    snapshot: TaskSnapshot | None = None,
):
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    return interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="beginner"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={},
        structured_interpreter=_Interpreter(response),
    )


def _discovery_interpretation(
    *,
    relationship: str = "category",
    category_description: str | None = "cybersecurity stocks",
    anchor_symbols: list[str] | None = None,
    language: str = "en",
    result_followup_focus: str | None = None,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="find candidate assets to test",
        detected_user_language=language,
        semantic_turn_act="asset_discovery",
        asset_discovery=AssetDiscoveryRequest(
            relationship=relationship,
            category_description=category_description,
            anchor_symbols=anchor_symbols or [],
            asset_class_hint="equity",
        ),
        result_followup_focus=result_followup_focus,
        confidence=0.9,
    )


def _result_snapshot() -> TaskSnapshot:
    return TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
        )
    )


class TestDiscoveryRouteFlagOff:
    @pytest.fixture(autouse=True)
    def _disable_discovery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", "false")

    def test_asset_discovery_act_routes_to_discovery_recovery(self) -> None:
        result = _run(
            message="What cybersecurity stocks could I test?",
            response=_discovery_interpretation(),
        )
        assert result.outcome == "ready_to_respond"
        patch = result.patch
        assert patch["recovery"]["code"] == "discovery_unavailable"
        assert patch["recovery"]["retryable"] is False
        assert str(patch["assistant_response"]).strip()
        assert patch["semantic_turn_act"] == "asset_discovery"

    @pytest.mark.parametrize("rail_enabled", ["false", "true"])
    def test_discovery_wins_over_generic_result_followup_composition(
        self, monkeypatch: pytest.MonkeyPatch, rail_enabled: str
    ) -> None:
        monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", rail_enabled)
        result = _run(
            message="Find companies similar to Nvidia",
            response=_discovery_interpretation(
                relationship="peer",
                category_description=None,
                anchor_symbols=["NVDA"],
                result_followup_focus="general",
            ),
            snapshot=_result_snapshot(),
        )
        assert result.outcome == "ready_to_respond"
        assert result.patch["recovery"]["code"] == "discovery_unavailable"

    def test_spanish_discovery_ask_flows_identically(self) -> None:
        result = _run(
            message="¿Qué acciones de ciberseguridad podría probar?",
            response=_discovery_interpretation(language="es-419"),
        )
        assert result.outcome == "ready_to_respond"
        assert result.patch["recovery"]["code"] == "discovery_unavailable"

    def test_detected_turn_language_reaches_discovery_composer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from argus.agent_runtime.discovery import composer as composer_module

        captured: dict[str, Any] = {}
        original = composer_module.discovery_stage_result_if_applicable

        async def _spy(**kwargs: Any):
            captured["language"] = kwargs.get("language")
            return await original(**kwargs)

        monkeypatch.setattr(composer_module, "discovery_stage_result_if_applicable", _spy)
        _run(
            message="¿Qué acciones de ciberseguridad podría probar?",
            response=_discovery_interpretation(language="es-419"),
        )
        assert captured["language"] == "es-419"

    def test_discovery_patch_never_touches_pending_or_result_state(self) -> None:
        snapshot = TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
            ),
            latest_backtest_result_reference=ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="run-9",
            ),
        )
        result = _run(
            message="what similar companies could I try?",
            response=_discovery_interpretation(
                relationship="peer",
                category_description=None,
                anchor_symbols=["AAPL"],
            ),
            snapshot=snapshot,
        )
        patch = result.patch
        assert "pending_strategy_summary" not in patch
        assert "latest_backtest_result_reference" not in patch
        assert "confirmation_payload" not in patch
        assert patch.get("candidate_strategy_draft", {}).get("asset_universe") in (
            None,
            [],
        )


class TestPayloadGatedStageRouting:
    """Issue #344: a filled payload owns the turn even when the scripted
    interpretation carries a non-discovery act, proving the stage gate does
    not depend on the interpreter-level act normalization."""

    @pytest.fixture(autouse=True)
    def _disable_discovery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", "false")

    def test_filled_payload_routes_despite_educational_act(self) -> None:
        response = _discovery_interpretation().model_copy(
            update={"semantic_turn_act": "educational_question"}
        )
        result = _run(
            message="find me cryptos that are trending",
            response=response,
        )
        assert result.outcome == "ready_to_respond"
        patch = result.patch
        assert patch["recovery"]["code"] == "discovery_unavailable"
        assert patch["asset_discovery"] is not None


class TestNonDiscoveryTurnsStayOut:
    def test_generic_try_next_does_not_enter_discovery(self) -> None:
        response = StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="what to try next",
            semantic_turn_act="result_followup",
            result_followup_focus="general",
            assistant_response="You could vary the period next.",
            confidence=0.9,
        )
        result = _run(
            message="what should I try next?",
            response=response,
            snapshot=_result_snapshot(),
        )
        patch = result.patch
        assert patch.get("recovery", {}).get("code") != "discovery_unavailable"
        assert patch.get("asset_discovery") is None

    def test_direct_backtest_never_constructs_search_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from argus.domain.research.search import selection as selection_module

        constructed: list[str] = []

        def _spy(**kwargs: Any) -> Any:
            constructed.append(str(kwargs))
            raise AssertionError("provider must not be constructed")

        monkeypatch.setattr(
            selection_module, "search_provider_for_config", _spy, raising=True
        )
        monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", "true")
        response = StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="backtest AAPL",
            semantic_turn_act="new_idea",
            candidate_strategy_draft=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
            ),
            confidence=0.9,
        )
        result = _run(message="Backtest AAPL for last year", response=response)
        assert constructed == []
        assert result.outcome != "end_run"


class TestDiscoveryDuringPendingConfirmation:
    """Issue #292: carried confirmation state never rides a discovery turn."""

    def test_public_payload_of_a_discovery_turn_carries_no_confirmation(self) -> None:
        from argus.agent_runtime.runtime import _public_result
        from argus.agent_runtime.state.models import ConfirmationPayload

        run_state = RunState.new(
            current_user_message="what companies similar to Apple could I try?",
            recent_thread_history=[],
        )
        run_state.confirmation_payload = ConfirmationPayload(
            strategy=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
            ),
        )
        result = {
            "run_state": run_state,
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Here are candidates.",
            "discovery": {"kind": "asset_discovery", "candidates": []},
        }

        serialized = _public_result(result)

        assert "discovery" in serialized
        assert "confirmation_payload" not in serialized

    def test_discovery_recovery_turn_carries_no_confirmation_either(self) -> None:
        from argus.agent_runtime.runtime import _public_result
        from argus.agent_runtime.state.models import ConfirmationPayload

        run_state = RunState.new(
            current_user_message="what companies similar to Apple could I try?",
            recent_thread_history=[],
        )
        run_state.confirmation_payload = ConfirmationPayload(
            strategy=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
            ),
        )
        # Recovery paths emit no discovery sidecar; the typed act on the
        # run state is what marks the turn.
        run_state.semantic_turn_act = "asset_discovery"
        result = {
            "run_state": run_state,
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Discovery is unavailable right now.",
        }

        serialized = _public_result(result)

        assert "confirmation_payload" not in serialized

    def test_non_discovery_turn_keeps_the_confirmation_backfill(self) -> None:
        from argus.agent_runtime.runtime import _public_result
        from argus.agent_runtime.state.models import ConfirmationPayload

        run_state = RunState.new(
            current_user_message="what assumptions are you using?",
            recent_thread_history=[],
        )
        run_state.confirmation_payload = ConfirmationPayload(
            strategy=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
            ),
        )
        result = {
            "run_state": run_state,
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Standard assumptions.",
        }

        serialized = _public_result(result)

        assert "confirmation_payload" in serialized


def test_strategy_repair_never_runs_on_a_typed_discovery_act() -> None:
    """Issue #292: the focused strategy repair rebuilt a draft for a
    discovery ask (whose draft is empty by contract) and demoted the act,
    capturing the turn into the confirmation corridor."""
    from argus.agent_runtime.llm_interpreter import (
        LLMInterpretationResponse,
        _strategy_extraction_repair_is_allowed,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="find similar companies",
        semantic_turn_act="asset_discovery",
        asset_discovery=AssetDiscoveryRequest(
            relationship="peer",
            category_description=None,
            anchor_symbols=["AAPL"],
            asset_class_hint="equity",
        ),
    )
    request = InterpretationRequest(
        current_user_message="¿Qué empresas parecidas a Apple podría probar?",
        user=UserState(user_id="u1"),
    )

    assert _strategy_extraction_repair_is_allowed(response, request=request) is False

    payloadless = response.model_copy(update={"asset_discovery": None})
    assert (
        _strategy_extraction_repair_is_allowed(payloadless, request=request) is False
    )
