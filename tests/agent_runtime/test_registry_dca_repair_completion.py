"""Retained budget-ceiling rescue plus explicitly authored completion controls.

Only message.content is retained. No candidate completion-audit reply existed;
those provider outputs are labeled counterfactual in the fixture. All sockets
are disabled and the real schemas validate every replayed response.
"""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter as li
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.semantic_integrity import conserve_semantic_constraints
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState

FIXTURE = Path(__file__).parent / "fixtures" / "registry_dca_repair_completion.json"


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Provider sockets are forbidden in completion replay")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")


@pytest.fixture
def replies() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def _candidate_reply(replies: dict[str, Any], schema: str | None) -> dict[str, Any]:
    return next(
        row["message_content"]
        for row in replies["historical"]["18-candidate-r1"]["replies"]
        if row["schema_name"] == schema
    )


def _request(replies: dict[str, Any]) -> InterpretationRequest:
    focused = _candidate_reply(replies, "FocusedStrategyExtraction")
    return InterpretationRequest(
        current_user_message=focused["raw_user_phrasing"],
        user=UserState(user_id="registry-completion-replay"),
    )


def _projected_response(replies: dict[str, Any]) -> LLMInterpretationResponse:
    request = _request(replies)
    return li._response_from_focused_strategy_extraction(
        extraction=FocusedStrategyExtraction.model_validate(
            _candidate_reply(replies, "FocusedStrategyExtraction")
        ),
        request=request,
        base_response=LLMInterpretationResponse(
            intent="calculate",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary=request.current_user_message,
            candidate_strategy_draft=LLMStrategyDraft(),
            semantic_turn_act="new_idea",
        ),
    )


def _assert_ceiling_only(response: Any, message: str) -> None:
    draft = response.candidate_strategy_draft
    strategy = (
        _strategy_from_llm(draft, message)
        if isinstance(draft, LLMStrategyDraft)
        else draft
    )
    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})
    assert report.evidence.contribution_ceiling == 5000
    assert report.evidence.recurring_contribution is None
    assert report.strategy.capital_amount is None
    assert report.blocking_missing_fields == ["capital_amount"]
    assert "capital_amount" in response.missing_required_fields


class _ReplyReplay:
    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.calls: list[str] = []
        self.unexpected: list[str] = []

    def assert_money_completion(self) -> None:
        field_reads = [
            i
            for i, name in enumerate(self.calls)
            if name == "StatedRunFieldFidelityAudit"
        ]
        retained_field_reads = sum(
            row["schema_name"] == "StatedRunFieldFidelityAudit"
            for row in self.replies["historical"]["18-candidate-r1"]["replies"]
        )
        # An independently accepted role may eliminate the duplicate read.
        assert field_reads
        assert len(field_reads) <= retained_field_reads
        assert max(field_reads) < self.calls.index("DcaContractAudit")
        assert self.calls.count("DcaContributionRoleAudit") == 1
        assert self.calls[-2:] == ["DcaContractAudit", "DcaContributionRoleAudit"]
        assert self.unexpected == []

    async def __call__(self, **kwargs: Any) -> Any:
        schema = kwargs["schema_name"]
        self.calls.append(schema)
        if schema == "LLMInterpretationResponse":
            # Replay the retained invalid last primary response. In the chat
            # control both model candidates deliberately receive this same
            # captured body; that route combination is authored, not history.
            value = _candidate_reply(self.replies, None)
        elif schema in self.replies["authored_completion"]:
            value = self.replies["authored_completion"][schema]
        else:
            matches = [
                row["message_content"]
                for row in self.replies["historical"]["18-candidate-r1"]["replies"]
                if row["schema_name"] == schema
            ]
            if not matches:
                self.unexpected.append(schema)
                pytest.fail(f"Unexpected completion replay schema: {schema}")
            # The two retained stated-field audit bodies are identical.
            value = matches[0]
        return kwargs["schema_model"].model_validate(copy.deepcopy(value))


def _install_replay(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any]
) -> _ReplyReplay:
    replay = _ReplyReplay(replies)
    monkeypatch.setattr(li, "invoke_openrouter_json_schema", replay)
    monkeypatch.setattr(
        li, "_unique_repair_models", lambda *_args, **_kwargs: ["offline"]
    )
    return replay


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["structured_candidates", "chat_candidates"])
async def test_retained_failed_primary_rescue_completes_money_roles(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any], mode: str
) -> None:
    replay = _install_replay(monkeypatch, replies)

    async def no_context(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(li, "provider_asset_resolution_context_for_request", no_context)
    monkeypatch.setattr(li, "openrouter_structured_model_candidates", lambda: ["offline"])
    if mode == "chat_candidates":

        class CapturedInvalidModel:
            def with_structured_output(self, schema_model: Any) -> Any:
                self.schema_model = schema_model
                return self

            async def ainvoke(self, _messages: Any) -> Any:
                return await replay(
                    schema_name="LLMInterpretationResponse",
                    schema_model=self.schema_model,
                )

        monkeypatch.setattr(
            li, "build_openrouter_model", lambda *_args, **_kwargs: CapturedInvalidModel()
        )
        from argus.llm import openrouter

        monkeypatch.setattr(
            openrouter,
            "resolve_openrouter_model",
            lambda model_name=None, **kwargs: "offline-fallback"
            if kwargs.get("fallback")
            else model_name or "offline-primary",
        )
    interpreter = li.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name="offline-primary" if mode == "chat_candidates" else None,
    )
    request = _request(replies)
    response = await interpreter.ainvoke(request)
    assert response is not None
    _assert_ceiling_only(response, request.current_user_message)
    replay.assert_money_completion()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repair_gate",
    [
        "_response_needs_material_evidence_strategy_repair",
        "_response_needs_pre_guidance_focused_strategy_extraction",
    ],
)
async def test_early_focused_exit_uses_same_completion(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any], repair_gate: str
) -> None:
    replay = _install_replay(monkeypatch, replies)
    request = _request(replies)
    response = _projected_response(replies)

    async def no_change(*, response: Any, **_kwargs: Any) -> Any:
        return response

    async def no_repair(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(li, "_ready_active_artifact_edit_planned_response", no_repair)
    monkeypatch.setattr(li, "_early_starting_capital_rechecked_response", no_repair)
    monkeypatch.setattr(li, "_early_focused_strategy_repaired_response", no_repair)
    monkeypatch.setattr(li, "_asset_grounding_audited_response", no_change)
    monkeypatch.setattr(
        li,
        "_response_needs_material_evidence_strategy_repair",
        lambda **_kwargs: repair_gate.endswith("material_evidence_strategy_repair"),
    )
    monkeypatch.setattr(
        li,
        "_response_needs_pre_guidance_focused_strategy_extraction",
        lambda **_kwargs: repair_gate.endswith(
            "pre_guidance_focused_strategy_extraction"
        ),
    )
    ready = await li._audited_response_ready_for_runtime(
        response=response, preferred_model="offline", request=request
    )
    _assert_ceiling_only(ready, request.current_user_message)
    replay.assert_money_completion()


@pytest.mark.asyncio
async def test_ordinary_completion_retains_existing_sequence_location(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any]
) -> None:
    response = _projected_response(replies)
    order: list[str] = []

    async def no_repair(**_kwargs: Any) -> None:
        return None

    for name in (
        "_ready_active_artifact_edit_planned_response",
        "_early_starting_capital_rechecked_response",
        "_early_focused_strategy_repaired_response",
    ):
        monkeypatch.setattr(li, name, no_repair)
    for name in (
        "_response_needs_material_evidence_strategy_repair",
        "_response_needs_pre_guidance_focused_strategy_extraction",
    ):
        monkeypatch.setattr(li, name, lambda **_kwargs: False)
    for name in (
        "_asset_grounding_audited_response",
        "_context_question_audited_response",
        "_dca_contract_audited_response",
        "_strategy_family_continuity_audited_response",
        "_dca_contribution_role_audited_response",
    ):

        def spy(owner: str):
            async def call(*, response: Any, **_kwargs: Any) -> Any:
                order.append(owner)
                return response

            return call

        monkeypatch.setattr(li, name, spy(name))
    # End at the existing post-sequence readiness check; this control proves
    # position/order and does not author a financial interpretation.
    monkeypatch.setattr(
        li,
        "_response_can_skip_optional_runtime_readiness_audits",
        lambda **_kwargs: "_dca_contribution_role_audited_response" in order,
    )
    ready = await li._audited_response_ready_for_runtime(
        response=response, preferred_model="offline", request=_request(replies)
    )
    assert (
        ready.candidate_strategy_draft.capital_amount
        == response.candidate_strategy_draft.capital_amount
    )
    assert order[-4:] == [
        "_context_question_audited_response",
        "_dca_contract_audited_response",
        "_strategy_family_continuity_audited_response",
        "_dca_contribution_role_audited_response",
    ]


@pytest.mark.asyncio
async def test_retained_valid_primary45_completes_later_focused_repair(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any]
) -> None:
    # The second measured candidate accepted its primary, passed the original
    # DCA block as follow_up, then became calculate in a later focused repair.
    # Replay its actual bodies, not the candidate18 fallback route.
    replies = copy.deepcopy(replies)
    replies["historical"]["18-candidate-r1"] = replies["historical"]["45-candidate-r2"]
    replay = _install_replay(monkeypatch, replies)
    response = LLMInterpretationResponse.model_validate(
        _candidate_reply(replies, "LLMInterpretationResponse")
    )
    assert response.intent == "follow_up"
    request = _request(replies)
    ready = await li._response_ready_for_runtime(
        response=response, preferred_model="offline", request=request
    )
    _assert_ceiling_only(ready, request.current_user_message)
    assert ready.intent == "calculate"
    assert replay.calls.count("FocusedStrategyExtraction") == 1
    replay.assert_money_completion()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "turn_act,task_relation",
    [
        ("new_idea", "new_task"),
        ("answer_pending_need", "continue"),
        ("refine_current_idea", "refine"),
    ],
)
@pytest.mark.parametrize("ceiling", [None, 5000])
async def test_authored_supported_plan_preserves_turn_and_independent_money_roles(
    monkeypatch: pytest.MonkeyPatch,
    turn_act: str,
    task_relation: str,
    ceiling: float | None,
) -> None:
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot

    request = InterpretationRequest(
        current_user_message="Use $200 every month.",
        user=UserState(user_id="authored-completion-control"),
        selected_thread_metadata={"requested_field": "capital_amount"}
        if task_relation != "new_task"
        else {},
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="dca_accumulation",
                asset_universe=["SPY"],
                asset_class="equity",
                cadence="monthly",
            )
        )
        if task_relation != "new_task"
        else None,
    )
    response = LLMInterpretationResponse(
        intent="calculate",
        task_relation=task_relation,
        semantic_turn_act=turn_act,
        user_goal_summary="Authored independent contribution and ceiling control",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            asset_class="equity",
            cadence="monthly",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            capital_amount=200,
            recurring_contribution=200,
            total_capital=ceiling,
            field_provenance={
                "capital_amount": "recurring_contribution",
                "recurring_contribution": "explicit_user",
                "total_capital": "total_capital",
            },
        ),
    )

    async def authored_audit(**kwargs: Any) -> Any:
        schema = kwargs["schema_name"]
        values = {
            "StatedRunFieldFidelityAudit": {
                "recurring_contribution_amount": 200,
                "confidence": 1,
            },
            "DcaContractAudit": {
                "is_recurring_buy_request": True,
                "recurring_contribution_amount": 200,
                "cadence": "monthly",
                "total_budget_amount": ceiling,
                "total_budget_source": "total_budget",
                "confidence": 1,
            },
            "DcaContributionRoleAudit": {
                "recurring_contribution_explicit": True,
                "total_budget_not_recurring": ceiling is not None,
                "confidence": 1,
            },
        }
        assert schema in values, schema
        return kwargs["schema_model"].model_validate(values[schema])

    monkeypatch.setattr(li, "invoke_openrouter_json_schema", authored_audit)
    monkeypatch.setattr(
        li, "_unique_repair_models", lambda *_args, **_kwargs: ["authored"]
    )
    ready = await li._focused_repair_completed_response(response, "authored", request)
    assert ready.intent == "calculate"
    assert ready.task_relation == task_relation
    assert ready.semantic_turn_act == turn_act
    report = conserve_semantic_constraints(
        strategy=_strategy_from_llm(ready.candidate_strategy_draft),
        selected_thread_metadata=request.selected_thread_metadata,
    )
    assert report.evidence.recurring_contribution == 200
    assert report.evidence.contribution_ceiling == ceiling
    assert report.strategy.capital_amount == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent,turn_act",
    [("cannot", "unsupported_request"), ("explain", "educational_question")],
)
async def test_authored_non_strategy_completion_retains_answer_without_audits(
    monkeypatch: pytest.MonkeyPatch, intent: str, turn_act: str
) -> None:
    response = LLMInterpretationResponse(
        intent=intent,
        task_relation="new_task",
        semantic_turn_act=turn_act,
        user_goal_summary="Authored no-strategy control",
        assistant_response="A grounded non-strategy answer.",
        candidate_strategy_draft=LLMStrategyDraft(),
    )
    request = InterpretationRequest(
        current_user_message="A request without any execution facts.",
        user=UserState(user_id="authored-no-strategy"),
    )
    calls: list[str] = []

    async def forbidden(**kwargs: Any) -> None:
        calls.append(kwargs["schema_name"])
        pytest.fail("A non-strategy answer must not spend strategy audit calls")

    monkeypatch.setattr(li, "invoke_openrouter_json_schema", forbidden)
    ready = await li._focused_repair_completed_response(response, "authored", request)
    assert ready.model_dump() == response.model_dump()
    assert calls == []


@pytest.mark.asyncio
async def test_retained_baseline17_replies_keep_ceiling_refusal_and_missing_amount(
    monkeypatch: pytest.MonkeyPatch, replies: dict[str, Any]
) -> None:
    from argus.domain.market_data.assets import ResolvedAsset

    original_resolver = li.resolve_asset

    def resolved_voo(symbol: str, **kwargs: Any) -> Any:
        # Typed asset fixture isolates the money boundary; no historical
        # asset-provider response is invented or replayed here.
        if symbol.upper() == "VOO":
            return ResolvedAsset("VOO", "equity", "Vanguard S&P 500 ETF", "VOO")
        return original_resolver(symbol, **kwargs)

    monkeypatch.setattr(li, "resolve_asset", resolved_voo)
    retained = replies["historical"]["17-baseline-r1"]["replies"]
    response = LLMInterpretationResponse.model_validate(retained[0]["message_content"])
    # The schema-less second contract reply is identified by its matching
    # DcaContractAudit receipt in the retained baseline log, not invented.
    queue = [
        (row["schema_name"] or "DcaContractAudit", row["message_content"])
        for row in retained[1:]
    ]
    calls: list[str] = []

    async def invoke(**kwargs: Any) -> Any:
        name = kwargs["schema_name"]
        calls.append(name)
        assert queue and queue[0][0] == name, (name, [item[0] for item in queue])
        _name, content = queue.pop(0)
        return kwargs["schema_model"].model_validate(copy.deepcopy(content))

    monkeypatch.setattr(li, "invoke_openrouter_json_schema", invoke)
    monkeypatch.setattr(
        li,
        "_unique_repair_models",
        lambda *_args, **_kwargs: ["offline-primary", "offline-fallback"],
    )
    request = _request(replies)
    ready = await li._response_ready_for_runtime(
        response=response, preferred_model="offline", request=request
    )
    _assert_ceiling_only(ready, request.current_user_message)
    assert queue == []
    assert calls.count("DcaContractAudit") == 2
    assert calls.count("DcaContributionRoleAudit") == 1
