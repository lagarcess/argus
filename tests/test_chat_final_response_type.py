"""The Pydantic model is the owner of the frontend's nested final payload."""

from scripts.generate_chat_final_response_type import TARGET, render_final_response_type


def test_frontend_final_response_type_is_generated_from_graph_state() -> None:
    assert (
        TARGET.read_text(encoding="utf-8") == render_final_response_type()
    ), "Run poetry run python scripts/generate_chat_final_response_type.py"
