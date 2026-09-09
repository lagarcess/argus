"""The Pydantic model is the owner of the frontend's nested final payload."""

from scripts.generate_chat_final_response_type import TARGET, render_final_response_type


def test_frontend_final_response_type_is_generated_from_graph_state() -> None:
    assert (
        TARGET.read_text(encoding="utf-8") == render_final_response_type()
    ), "Run poetry run python scripts/generate_chat_final_response_type.py"


def test_result_array_imports_the_shared_card_contract() -> None:
    generated = render_final_response_type()
    assert 'import type { ToolResultCard } from "./tool-result-card";' in generated
    assert "tool_result_cards?: Array<ToolResultCard>;" in generated
    assert "export type ToolResultCard" not in generated
