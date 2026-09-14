"""Q1 acceptance regression: an interpreter outage must not invent a test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import RunState, UserState
from faker import Faker


@pytest.mark.parametrize("failure_kind", ["timeout", "contract_rejected"])
@pytest.mark.parametrize(
    ("language", "question", "followup", "understanding", "test_terms"),
    [
        (
            "en",
            "How can I save for an emergency fund?",
            "What if I set aside 2000 pesos each month?",
            "understand your question",
            ("test setup", "asset", "period"),
        ),
        (
            "es-419",
            "¿Cómo puedo ahorrar para un fondo de emergencia?",
            "¿Y si separo 2000 pesos cada mes?",
            "entender tu pregunta",
            ("configuración de prueba", "activo", "periodo"),
        ),
    ],
)
def test_savings_interpreter_failure_recovers_the_question_without_inventing_test(
    failure_kind: str,
    language: str,
    question: str,
    followup: str,
    understanding: str,
    test_terms: tuple[str, ...],
) -> None:
    class FailedInterpreter:
        last_failure_kind = failure_kind

        def __call__(self, request):
            return None

    result = interpret_stage(
        state=RunState.new(
            current_user_message=followup,
            recent_thread_history=[{"role": "user", "content": question}],
        ),
        user=UserState(user_id=Faker().uuid4(), language_preference=language),
        latest_task_snapshot=None,
        structured_interpreter=FailedInterpreter(),
    )

    retryable = failure_kind != "contract_rejected"
    code = (
        "interpreter_unavailable"
        if retryable
        else "interpreter_unavailable_not_retryable"
    )
    assert result.outcome == "ready_to_respond"
    assert result.decision.candidate_strategy_draft.asset_universe == []
    assert result.decision.missing_required_fields == []
    assert result.stage_patch["recovery"] == {"code": code, "retryable": retryable}
    if retryable:
        assert result.stage_patch["retry_last_turn"] == {"message": followup}
    else:
        assert "retry_last_turn" not in result.stage_patch

    locale_root = Path(__file__).resolve().parents[2] / "web/public/locales"
    catalog = json.loads((locale_root / language / "common.json").read_text())
    localized = catalog["chat"]["recovery"][code]
    fallback = result.stage_patch["assistant_response"]
    english_catalog = json.loads((locale_root / "en/common.json").read_text())
    assert fallback == english_catalog["chat"]["recovery"][code]
    assert understanding in localized
    assert "understand your question" in fallback
    assert all(term not in localized for term in test_terms)
    assert "—" not in localized + fallback
