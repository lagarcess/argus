from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.stages.recovery_composer import (
    compose_active_confirmation_interpreter_recovery,
)


@pytest.mark.asyncio
async def test_active_confirmation_recovery_composer_uses_user_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_openrouter_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "Claro, la confirmación sigue lista."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.recovery_composer.invoke_openrouter_chat_completion",
        fake_openrouter_chat_completion,
    )

    response = await compose_active_confirmation_interpreter_recovery(
        current_user_message="que significa esto?",
        setup_phrase="ETH buy and hold over the last 8 months.",
        assumptions_response="$100,000 starting capital",
        action_guidance="The visible confirmation is still ready.",
        language="es-419",
    )

    assert response == "Claro, la confirmación sigue lista."
    system_prompt = captured["messages"][0]["content"]
    assert "Spanish" in system_prompt
    assert "plain English" not in system_prompt
