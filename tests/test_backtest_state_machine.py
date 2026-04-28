from __future__ import annotations

from argus.domain.backtest_state_machine import (
    BacktestConversationState,
    BacktestParamsUpdate,
    apply_backtest_turn,
)


def test_partial_updates_merge_and_wait_for_missing_fields() -> None:
    state = BacktestConversationState()

    first = apply_backtest_turn(
        state=state,
        update=BacktestParamsUpdate(template="rsi_mean_reversion"),
        message="run RSI",
        language="en",
    )
    assert first.action == "ask_missing"
    assert first.state.params.template == "rsi_mean_reversion"
    assert first.state.missing_fields == ["symbols"]

    second = apply_backtest_turn(
        state=first.state,
        update=BacktestParamsUpdate(symbols=["AAPL"]),
        message="use AAPL",
        language="en",
    )
    assert second.action == "await_confirmation"
    assert second.state.params.template == "rsi_mean_reversion"
    assert second.state.params.symbols == ["AAPL"]
    assert second.state.awaiting_confirmation is True
    assert "AAPL" in second.message
    assert "Run this" in second.message
    assert "Change something" in second.message
    assert "Cancel" in second.message


def test_change_during_confirmation_overwrites_field_and_requires_new_yes() -> None:
    ready = apply_backtest_turn(
        state=BacktestConversationState(),
        update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
        message="buy dips on AAPL",
        language="en",
    ).state

    changed = apply_backtest_turn(
        state=ready,
        update=BacktestParamsUpdate(symbols=["MSFT"]),
        message="use MSFT instead",
        language="en",
    )

    assert changed.action == "await_confirmation"
    assert changed.state.params.symbols == ["MSFT"]
    assert changed.state.awaiting_confirmation is True
    assert "MSFT" in changed.message
    assert "AAPL" not in changed.message


def test_explicit_confirmation_is_required_before_run() -> None:
    ready = apply_backtest_turn(
        state=BacktestConversationState(),
        update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
        message="buy dips on AAPL",
        language="en",
    ).state

    not_yes = apply_backtest_turn(
        state=ready,
        update=BacktestParamsUpdate(),
        message="looks good",
        language="en",
    )
    assert not_yes.action == "await_confirmation"

    confirmed = apply_backtest_turn(
        state=ready,
        update=BacktestParamsUpdate(),
        message="yes",
        language="en",
        confirmation_action="accept_and_run",
    )
    assert confirmed.action == "run_backtest"
    assert confirmed.config is not None
    assert confirmed.config["symbols"] == ["AAPL"]
    assert confirmed.config["benchmark_symbol"] == "SPY"


def test_confirmation_edit_and_cancel_actions_do_not_run() -> None:
    ready = apply_backtest_turn(
        state=BacktestConversationState(),
        update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
        message="buy dips on AAPL",
        language="en",
    ).state

    edit = apply_backtest_turn(
        state=ready,
        update=BacktestParamsUpdate(),
        message="change something",
        language="en",
        confirmation_action="edit_parameters",
    )
    assert edit.action == "edit_backtest"
    assert edit.state.awaiting_confirmation is False
    assert edit.config is None

    cancel = apply_backtest_turn(
        state=ready,
        update=BacktestParamsUpdate(),
        message="cancel",
        language="en",
        confirmation_action="cancel_backtest",
    )
    assert cancel.action == "cancel_backtest"
    assert cancel.state == BacktestConversationState()
    assert cancel.config is None


def test_dca_requires_cadence_before_confirmation() -> None:
    result = apply_backtest_turn(
        state=BacktestConversationState(),
        update=BacktestParamsUpdate(
            template="dca_accumulation",
            symbols=["BTC"],
            asset_class="crypto",
        ),
        message="DCA into BTC",
        language="en",
    )

    assert result.action == "ask_missing"
    assert result.state.missing_fields == ["dca_cadence"]
    assert "How often" in result.message
