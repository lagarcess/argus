from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse


def test_asset_discovery_relationship_schema_explains_user_goal_precedence() -> None:
    schema = LLMInterpretationResponse.model_json_schema()
    description = schema["$defs"]["AssetDiscoveryRequest"]["properties"][
        "relationship"
    ]["description"]

    assert "comparison when the user's goal is choosing what to compare" in description
    assert "even when the comparison candidates share a category" in description
    assert "category only when the category itself is the discovery goal" in description
