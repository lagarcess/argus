from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction.structured import extract_strategy_fields


def test_extractor_understands_sell_synonym_and_normalizes_exit_logic() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
        contract=build_default_capability_contract(),
    )

    assert result.exit_logic.raw_value == "sell when rsi is above 70"
    assert result.exit_logic.normalized_value == "exit when RSI rises above 70"
    assert result.exit_logic.status == "resolved"
    assert result.asset_universe.normalized_value == "TSLA"
    assert result.date_range.normalized_value == "last 2 years"


def test_extractor_marks_negation_flip_as_ambiguous() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell when RSI is not above 70",
        contract=build_default_capability_contract(),
    )

    assert result.exit_logic.status == "ambiguous"
    assert result.ambiguous_fields[0].field_name == "exit_logic"
    assert result.ambiguous_fields[0].reason_code == "negation_or_conditional_reversal"


def test_extractor_detects_unsupported_time_granularity() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell at market open when RSI is above 70",
        contract=build_default_capability_contract(),
    )

    assert result.unsupported_constraints[0].category == "unsupported_time_granularity"
    assert result.unsupported_constraints[0].simplification_options[0].label == (
        "Retry with daily bars"
    )
