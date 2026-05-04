from unittest.mock import MagicMock, patch

import pytest
from argus.domain.orchestrator import (
    ChatTurnIntent,
    assistant_message_for_chat_turn,
    classify_chat_turn_intent,
)


@pytest.mark.asyncio
async def test_conversational_ux_restoration():
    # Mock LLM response with conversational message
    mock_response = ChatTurnIntent(
        intent="setup",
        confidence=0.9,
        assistant_response="I've set up your Buy and Hold strategy for AAPL. It's a classic long-term approach! Ready to run the simulation?"
    )

    with patch("os.getenv", return_value="fake_key"), \
         patch("argus.domain.orchestrator._build_model") as mock_build:
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_build.return_value = mock_model
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_response

        # Test intent classification
        intent = classify_chat_turn_intent(
            message="setup buy and hold for aapl",
            language="en"
        )

        assert intent.assistant_response == "I've set up your Buy and Hold strategy for AAPL. It's a classic long-term approach! Ready to run the simulation?"

        # Test message selection
        msg = assistant_message_for_chat_turn(intent, "setup buy and hold for aapl", "en")
        assert msg == intent.assistant_response
        assert "classic long-term approach" in msg

@pytest.mark.asyncio
async def test_conversational_ux_fallback():
    # Mock LLM response with low confidence but it MUST provide an assistant_response now
    mock_response = ChatTurnIntent(
        intent="guide",
        confidence=0.1,
        educational_need="strategy_help",
        assistant_response="I'm here to help you test strategies like Buy and Hold or DCA."
    )

    with patch("os.getenv", return_value="fake_key"), \
         patch("argus.domain.orchestrator._build_model") as mock_build:
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_build.return_value = mock_model
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_response

        intent = classify_chat_turn_intent(message="help", language="en")

        # Should prioritize LLM message
        msg = assistant_message_for_chat_turn(intent, "help", "en")
        assert "I'm here to help you test strategies" in msg

@pytest.mark.asyncio
async def test_conversational_ux_template_fallback():
    # Test the hardcoded templates when intent has no LLM response (simulating manual intent object)
    intent = ChatTurnIntent(
        intent="guide",
        confidence=0.0,
        educational_need="beginner_confused",
        assistant_response="" # Empty string to trigger template
    )

    msg = assistant_message_for_chat_turn(intent, "help", "en")
    assert "I'm here to help you validate" in msg
    assert "real historical data" in msg
