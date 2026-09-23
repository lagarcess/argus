"""Issue #644: composed discovery and capability prose never show U+2014.

The live measurement captured em dashes in discovery voicing and in an
educational capability reply. Those writers used to leave model punctuation
on `assistant_response`; evals and LangGraph read that patch before the API
SSE/persist door. This file drives the composition path through the existing
`rewrite_visible_reply` owner. It does not rewrite the #659 evidence fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from argus.agent_runtime.discovery import composer as composer_module
from argus.agent_runtime.discovery.contracts import ValidatedCandidate
from argus.agent_runtime.stages.interpret import StructuredInterpretation
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StageResult,
)
from argus.agent_runtime.state.models import ResponseProfile
from argus.domain.research.search import SearchResultPacket
from argus.domain.visible_reply import EM_DASH, rewrite_visible_reply

from tests.agent_runtime.test_interpret_stage import run_interpret_with_llm

try:
    from tests.evals.discovery_em_dash import assert_no_em_dash
except ImportError:  # #659 may still be landing alongside this PR
    def assert_no_em_dash(prose: str) -> None:
        if EM_DASH in prose:
            raise AssertionError(
                "user-facing prose contains U+2014 em dash "
                f"({prose.count(EM_DASH)} occurrence(s); "
                f"first at index {prose.index(EM_DASH)})"
            )


EN_DASH = "\u2013"

# Representative model output, including the two confirmed #644 shapes.
# These are inputs to the composer, not a rewrite of the evidence fixture.
DISCOVERY_EN = (
    "The search also returned some names that couldn't be fully verified in "
    f"the current data, so those aren't testable here{EM_DASH}but the two "
    "below are the confirmed options you can explore."
)
DISCOVERY_ES = (
    "La búsqueda también devolvió nombres que no se pudieron confirmar, "
    f"así que no son comprobables aquí{EM_DASH}pero las dos opciones "
    "de abajo sí lo son."
)
CAPABILITY_EN = (
    "It's built for experimenting with ideas you already have"
    f"{EM_DASH}like testing a strategy on a specific stock."
)
CAPABILITY_ES = (
    f"Argus no predice el futuro{EM_DASH}eso queda fuera de lo que hace."
)


def _decision() -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="discovery",
        confidence=0.9,
        effective_response_profile=ResponseProfile(
            effective_tone="friendly",
            effective_verbosity="medium",
            effective_expertise_mode="beginner",
        ),
        semantic_turn_act="asset_discovery",
        asset_discovery=AssetDiscoveryRequest(
            relationship="category",
            category_description="trending cryptos",
            anchor_symbols=[],
            asset_class_hint="crypto",
            needs_current_facts=True,
        ),
    )


def _packet() -> SearchResultPacket:
    return SearchResultPacket(
        results=(),
        retrieved_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        latency_ms=1,
        provider_id="test",
    )


def _candidate() -> ValidatedCandidate:
    return ValidatedCandidate(
        symbol="BTC",
        name="Bitcoin",
        asset_class="crypto",
        reason_text="confirmed",
    )


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("language", "voiced"),
    (("en", DISCOVERY_EN), ("es-419", DISCOVERY_ES)),
    ids=["en", "es-419"],
)
async def test_discovery_voicing_rewrites_em_dashes(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    voiced: str,
) -> None:
    async def _fake_complete(**_: Any) -> str:
        return voiced

    monkeypatch.setattr(
        composer_module, "invoke_openrouter_chat_completion", _fake_complete
    )

    reply = await composer_module._voiced_discovery_response(
        request=_decision().asset_discovery,
        candidates=[_candidate()],
        packet=_packet(),
        unverified_names=["Unconfirmed Coin"],
        uncorroborated_names=[],
        current_user_message="find me cryptos that are trending",
        language=language,
    )

    assert reply is not None
    assert_no_em_dash(reply)
    assert reply == rewrite_visible_reply(voiced, surface="discovery").text


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("language", "voiced"),
    (("en", DISCOVERY_EN), ("es-419", DISCOVERY_ES)),
    ids=["en", "es-419"],
)
async def test_discovery_recovery_voicing_rewrites_em_dashes(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    voiced: str,
) -> None:
    async def _fake_complete(**_: Any) -> str:
        return voiced

    monkeypatch.setattr(
        composer_module, "invoke_openrouter_chat_completion", _fake_complete
    )

    reply = await composer_module._voiced_discovery_recovery(
        code="discovery_search_failed",
        retryable=True,
        current_user_message="find me cryptos that are trending",
        language=language,
        unverified_names=[],
    )

    assert reply is not None
    assert_no_em_dash(reply)
    assert reply == rewrite_visible_reply(voiced, surface="discovery").text


@pytest.mark.parametrize(
    "voiced",
    (DISCOVERY_EN, DISCOVERY_ES),
    ids=["en", "es-419"],
)
def test_stage_result_patch_rewrites_composed_assistant_response(voiced: str) -> None:
    result = StageResult(
        outcome="ready_to_respond",
        stage_patch={"assistant_response": voiced},
    )

    reply = str(result.patch["assistant_response"])
    assert_no_em_dash(reply)
    assert reply == rewrite_visible_reply(voiced, surface="stage_result").text


@pytest.mark.parametrize(
    ("language", "prose"),
    (("en", CAPABILITY_EN), ("es-419", CAPABILITY_ES)),
    ids=["en", "es-419"],
)
def test_educational_capability_pass_through_rewrites_em_dashes(
    language: str,
    prose: str,
) -> None:
    from argus.agent_runtime.state.models import UserState

    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked whether Argus finds new stocks.",
        assistant_response=prose,
        semantic_turn_act="educational_question",
        capability_question_focus="general",
        detected_user_language=language,
    )

    result, _interpreter = run_interpret_with_llm(
        message="does argus support finding new stocks to invest in?",
        response=response,
        user=UserState(user_id="u1", language_preference=language),
    )

    reply = str(result.patch["assistant_response"])
    assert result.outcome == "ready_to_respond"
    assert_no_em_dash(reply)
    assert reply == rewrite_visible_reply(prose, surface="stage_result").text


def test_stage_result_patch_keeps_en_dash() -> None:
    text = f"Range 2020{EN_DASH}2024 is still an en dash."
    result = StageResult(
        outcome="ready_to_respond",
        stage_patch={"assistant_response": text},
    )

    reply = str(result.patch["assistant_response"])
    assert EN_DASH in reply
    assert_no_em_dash(reply)
