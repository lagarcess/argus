"""A request that starts before the data offers the first day every series the
coverage preflight needs has history, the benchmark included."""

from __future__ import annotations

from datetime import date

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, StrategySummary

STARTS = {
    "AAPL": date(2016, 1, 4),
    "SPY": date(2020, 7, 27),
    "QQQ": date(2021, 3, 1),
}
MESSAGES = [
    pytest.param("en", "Backtest Apple since 2015.", id="english"),
    pytest.param("es-419", "Prueba Apple desde 2015.", id="spanish"),
]


@pytest.mark.parametrize(("language", "message"), MESSAGES)
@pytest.mark.parametrize(
    ("benchmark_ticker", "available_from"),
    [(None, "2020-07-27"), ("QQQ", "2021-03-01")],
    ids=["default-benchmark", "named-benchmark"],
)
def test_the_offered_start_waits_for_the_benchmark_history(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    message: str,
    benchmark_ticker: str | None,
    available_from: str,
) -> None:
    monkeypatch.setattr(
        "argus.domain.market_data.tradability.asset_history_start",
        lambda symbol, asset_class: STARTS.get(symbol),
    )
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis=message,
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2015-01-01", "end": "2016-01-15"},
        comparison_baseline=benchmark_ticker,
    )

    result = confirm_stage(
        state=state, contract=build_default_capability_contract(), language=language
    )

    assert result.outcome == "needs_clarification"
    constraint = result.patch["optional_parameter_status"]["unsupported_constraints"][0]
    assert constraint["available_from"] == available_from
