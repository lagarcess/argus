from unittest.mock import patch

import pytest
from argus.domain.orchestrator import (
    ExtractedSlot,
    StrategyIntentExtraction,
    orchestrate_chat_turn,
)


@pytest.mark.asyncio
async def test_screenshot_regression_state_persistence():
    """
    Reproduces the exact flow from the user screenshot to verify StrategyDraft persistence.
    1. "quiero probar un backtest"
    2. "quiero probar una reversion a la media con RSI"
    3. "Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy"
    """

    # We mock _extract_strategy_intent to simulate what the LLM would return
    with patch("argus.domain.orchestrator._extract_strategy_intent") as mock_extract:

        # --- Turn 1 ---
        # User: "quiero probar un backtest"
        # Extraction: wants_backtest=True
        mock_extract.return_value = StrategyIntentExtraction(wants_backtest=True)

        msg1 = "quiero probar un backtest"
        decision1 = orchestrate_chat_turn(message=msg1, language="es-419", history=[])

        assert decision1.intent == "clarify"
        draft1 = decision1.strategy_draft
        assert draft1.template.source == "missing"

        # --- Turn 2 ---
        # User: "quiero probar una reversion a la media con RSI"
        # Extraction: template="rsi_mean_reversion"
        mock_extract.return_value = StrategyIntentExtraction(
            template=ExtractedSlot(value="rsi_mean_reversion", confidence=1.0)
        )

        msg2 = "quiero probar una reversion a la media con RSI"
        history2 = [
            {"role": "user", "content": msg1},
            {"role": "assistant", "content": decision1.assistant_message, "metadata": {"strategy_draft": decision1.strategy_draft.model_dump()}}
        ]

        decision2 = orchestrate_chat_turn(message=msg2, language="es-419", history=history2)

        assert decision2.intent == "clarify"
        draft2 = decision2.strategy_draft
        assert draft2.template.value == "rsi_mean_reversion"

        # --- Turn 3 ---
        # User: "Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy"
        # Extraction: symbols=["GOOG"], starting_capital=10000
        mock_extract.return_value = StrategyIntentExtraction(
            symbols=ExtractedSlot(value=["GOOG"], confidence=1.0),
            starting_capital=ExtractedSlot(value=10000.0, confidence=1.0)
        )

        msg3 = "Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy"
        history3 = history2 + [
            {"role": "user", "content": msg2},
            {"role": "assistant", "content": decision2.assistant_message, "metadata": {"strategy_draft": decision2.strategy_draft.model_dump()}}
        ]

        decision3 = orchestrate_chat_turn(message=msg3, language="es-419", history=history3)

        # THE CRITICAL INVARIANTS
        final_draft = decision3.strategy_draft

        # 1. Template must NOT be lost (This was the bug!)
        assert final_draft.template.value == "rsi_mean_reversion", "Template was lost in Turn 3!"

        # 2. Symbol must be extracted/merged
        assert "GOOG" in (final_draft.symbols.value or []), f"Symbol GOOG was not extracted. Found: {final_draft.symbols.value}"

        # 3. Capital must be extracted/merged
        assert final_draft.starting_capital.value == 10000, f"Capital 10000 was not extracted. Found: {final_draft.starting_capital.value}"

        # 4. Logic should check if we are asking for strategy again
        assert "reversión a la media" not in decision3.assistant_message.lower(), "Assistant asked for strategy type again!"
