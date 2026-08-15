"""The focused discovery read: mode-A backstop for an omitted payload (#344)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime.interpreter import discovery_focused_read as dfr
from argus.agent_runtime.llm_interpreter import LLMInterpretationResponse
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretationRequest,
)
from argus.agent_runtime.state.models import UserState


def _educational_response(**overrides: Any) -> LLMInterpretationResponse:
    fields: dict[str, Any] = {
        "intent": "conversation_followup",
        "task_relation": "new_task",
        "user_goal_summary": "find trending cryptos",
        "semantic_turn_act": "educational_question",
    }
    fields.update(overrides)
    return LLMInterpretationResponse(**fields)


def _request(message: str = "find me cryptos that are trending") -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )


def _wire_read(monkeypatch: pytest.MonkeyPatch, read: dfr.FocusedAssetDiscoveryRead | Exception):
    calls: list[list[dict[str, str]]] = []

    async def _fake_invoke(**kwargs: Any):
        calls.append(kwargs["messages"])
        if isinstance(read, Exception):
            raise read
        return read

    monkeypatch.setattr(dfr, "invoke_openrouter_json_schema", _fake_invoke)
    return calls


class TestTrigger:
    def test_fires_on_payloadless_educational_shape(self) -> None:
        assert dfr.focused_discovery_read_applicable(_educational_response())

    def test_fires_on_missing_act_too(self) -> None:
        assert dfr.focused_discovery_read_applicable(
            _educational_response(semantic_turn_act=None)
        )

    def test_never_fires_when_a_payload_exists(self) -> None:
        response = _educational_response(
            asset_discovery=AssetDiscoveryRequest(
                relationship="category", category_description="tech"
            )
        )
        assert not dfr.focused_discovery_read_applicable(response)

    def test_never_fires_on_other_acts_or_claimed_shapes(self) -> None:
        assert not dfr.focused_discovery_read_applicable(
            _educational_response(semantic_turn_act="result_followup")
        )
        assert not dfr.focused_discovery_read_applicable(
            _educational_response(capability_question_focus="assets")
        )
        assert not dfr.focused_discovery_read_applicable(
            _educational_response(intent="beginner_guidance")
        )


class TestRecovery:
    def test_recovers_a_payload_and_records_the_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire_read(
            monkeypatch,
            dfr.FocusedAssetDiscoveryRead(
                asks_argus_to_find_assets=True,
                relationship="category",
                category_description="cryptos that are trending",
                asset_class_hint="crypto",
                needs_current_facts=True,
            ),
        )
        recovered = asyncio.run(
            dfr.focused_discovery_payload_response(
                response=_educational_response(), request=_request()
            )
        )
        assert recovered is not None
        assert recovered.asset_discovery is not None
        assert recovered.asset_discovery.needs_current_facts is True
        assert (
            "discovery_payload_recovered_by_focused_read" in recovered.reason_codes
        )

    def test_history_reaches_the_read_for_chip_followups(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _wire_read(
            monkeypatch,
            dfr.FocusedAssetDiscoveryRead(
                asks_argus_to_find_assets=True,
                relationship="category",
                category_description="pharmaceutical sector",
                needs_current_facts=True,
            ),
        )
        request = InterpretationRequest(
            current_user_message="Search current sources for: pharmaceutical sector",
            recent_thread_history=[
                {"role": "user", "content": "find me pharmaceutical stocks"},
                {"role": "assistant", "content": "Here are candidates from general knowledge."},
            ],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
        recovered = asyncio.run(
            dfr.focused_discovery_payload_response(
                response=_educational_response(), request=request
            )
        )
        assert recovered is not None
        history_blocks = [
            m["content"] for m in calls[0] if "Recent conversation" in m["content"]
        ]
        assert history_blocks and "general knowledge" in history_blocks[0]

    def test_a_no_answer_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire_read(
            monkeypatch,
            dfr.FocusedAssetDiscoveryRead(asks_argus_to_find_assets=False),
        )
        assert (
            asyncio.run(
                dfr.focused_discovery_payload_response(
                    response=_educational_response(), request=_request()
                )
            )
            is None
        )

    def test_a_yes_without_a_target_is_discarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire_read(
            monkeypatch,
            dfr.FocusedAssetDiscoveryRead(
                asks_argus_to_find_assets=True, relationship="category"
            ),
        )
        assert (
            asyncio.run(
                dfr.focused_discovery_payload_response(
                    response=_educational_response(), request=_request()
                )
            )
            is None
        )

    def test_provider_failure_is_silent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire_read(monkeypatch, RuntimeError("provider down"))
        assert (
            asyncio.run(
                dfr.focused_discovery_payload_response(
                    response=_educational_response(), request=_request()
                )
            )
            is None
        )


@pytest.mark.asyncio
async def test_recovered_payload_promotes_through_the_interpreter_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end at the interpreter: primary omits the payload, the focused
    read recovers it, and the guard promotes the act."""
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def _fake_recovered(**kwargs: Any):
        response = kwargs["response"]
        return response.model_copy(
            update={
                "asset_discovery": AssetDiscoveryRequest(
                    relationship="category",
                    category_description="cryptos that are trending",
                    asset_class_hint="crypto",
                    needs_current_facts=True,
                ),
                "reason_codes": [
                    *response.reason_codes,
                    "discovery_payload_recovered_by_focused_read",
                ],
            }
        )

    monkeypatch.setattr(
        interpreter_module, "focused_discovery_payload_response", _fake_recovered
    )

    async def audited_response(**_kwargs):
        raise AssertionError("a recovered discovery turn must bypass strategy audits")

    monkeypatch.setattr(
        interpreter_module, "_audited_response_ready_for_runtime", audited_response
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=_educational_response(),
        preferred_model="test-model",
        request=_request(),
    )
    assert repaired.semantic_turn_act == "asset_discovery"
    assert repaired.asset_discovery is not None
    assert "discovery_payload_recovered_by_focused_read" in repaired.reason_codes
    assert "discovery_payload_act_promoted" in repaired.reason_codes
