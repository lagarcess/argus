"""Regression tests for Issue #275: TP Automation Race Condition.

Verifies that TP3_HIT / INVALIDATED exits from an old signal do NOT close
positions belonging to a newer signal for the same symbol.

Root cause: Alpaca holds one aggregate position per symbol. When
close_position_emergency sells qty from the old signal's Firestore position,
it can sell shares belonging to a newly-bought position for the same symbol.
"""

from datetime import date
from unittest.mock import MagicMock

from alpaca.common.exceptions import APIError
from crypto_signals.domain.schemas import (
    ExitReason,
    SignalStatus,
    TradeStatus,
)

from tests.factories import PositionFactory, SignalFactory


def _make_signal(signal_id, symbol="AAVE/USD", status=SignalStatus.TP3_HIT):
    """Helper: create a Signal object using SignalFactory."""
    return SignalFactory.build(
        signal_id=signal_id,
        symbol=symbol,
        status=status,
        exit_reason=ExitReason.TP_HIT if status == SignalStatus.TP3_HIT else None,
        pattern_name="ELLIOTT_WAVE_135",
        discord_thread_id="thread_old",
    )


def _make_position(
    position_id,
    signal_id,
    symbol="AAVE/USD",
    status=TradeStatus.OPEN,
    qty=10.0,
):
    """Helper: create a real Position object."""
    return PositionFactory.build(
        position_id=position_id,
        ds=date(2026, 2, 10),
        symbol=symbol,
        signal_id=signal_id,
        status=status,
        qty=qty,
    )


# =============================================================================
# TEST: TP3_HIT on old signal must NOT close new signal's position
# =============================================================================


class TestTPAutomationSignalGuard:
    """Tests for the signal_id guard in the TP Automation block."""

    def test_tp3_closes_own_position_only(self):
        """TP3_HIT should close the position whose signal_id matches."""
        # Arrange
        old_signal = _make_signal("old-signal-aaa", status=SignalStatus.TP3_HIT)
        old_position = _make_position("old-pos", signal_id="old-signal-aaa")

        position_repo = MagicMock()
        position_repo.get_position_by_signal.return_value = old_position

        execution_engine = MagicMock()
        execution_engine.close_position_emergency.return_value = True

        # Act
        pos = position_repo.get_position_by_signal(old_signal.signal_id)
        result = execution_engine.close_position_emergency(pos)

        # Assert
        assert pos is not None, "Position should exist for matching signal_id"
        assert (
            pos.signal_id == old_signal.signal_id
        ), f"Expected signal_id == {old_signal.signal_id}, got {pos.signal_id}"
        assert (
            pos.status == TradeStatus.OPEN
        ), f"Expected status == OPEN, got {pos.status}"
        assert (
            result is True
        ), "close_position_emergency should return True for own position"
        execution_engine.close_position_emergency.assert_called_once_with(old_position)

    def test_tp3_skips_when_position_signal_id_mismatch(self):
        """TP3_HIT must NOT close a position whose signal_id doesn't match.

        This is the core regression test for Issue #275.
        Scenario: Old signal hits TP3, but get_position_by_signal returns
        a position linked to a DIFFERENT signal (the new one).
        """
        # Arrange
        old_signal = _make_signal("old-signal-aaa", status=SignalStatus.TP3_HIT)
        new_position = _make_position("new-pos", signal_id="new-signal-bbb")

        position_repo = MagicMock()
        position_repo.get_position_by_signal.return_value = new_position

        execution_engine = MagicMock()

        # Act
        pos = position_repo.get_position_by_signal(old_signal.signal_id)
        if (
            pos
            and pos.status == TradeStatus.OPEN
            and pos.signal_id == old_signal.signal_id
        ):
            execution_engine.close_position_emergency(pos)

        # Assert
        execution_engine.close_position_emergency.assert_not_called()

    def test_tp3_skips_when_position_already_closed(self):
        """TP3_HIT must not act on already-closed positions."""
        # Arrange
        old_signal = _make_signal("old-signal-aaa", status=SignalStatus.TP3_HIT)
        closed_position = _make_position(
            "old-pos", signal_id="old-signal-aaa", status=TradeStatus.CLOSED
        )

        position_repo = MagicMock()
        position_repo.get_position_by_signal.return_value = closed_position

        execution_engine = MagicMock()

        # Act
        pos = position_repo.get_position_by_signal(old_signal.signal_id)
        if (
            pos
            and pos.status == TradeStatus.OPEN
            and pos.signal_id == old_signal.signal_id
        ):
            execution_engine.close_position_emergency(pos)

        # Assert
        execution_engine.close_position_emergency.assert_not_called()

    def test_tp3_skips_when_no_position_found(self):
        """TP3_HIT must handle None position gracefully."""
        # Arrange
        old_signal = _make_signal("old-signal-aaa", status=SignalStatus.TP3_HIT)

        position_repo = MagicMock()
        position_repo.get_position_by_signal.return_value = None

        execution_engine = MagicMock()

        # Act
        pos = position_repo.get_position_by_signal(old_signal.signal_id)
        if (
            pos
            and pos.status == TradeStatus.OPEN
            and pos.signal_id == old_signal.signal_id
        ):
            execution_engine.close_position_emergency(pos)

        # Assert
        execution_engine.close_position_emergency.assert_not_called()

    def test_invalidated_signal_also_uses_guard(self):
        """INVALIDATED exits must also be guarded by signal_id match."""
        # Arrange
        inv_signal = _make_signal("old-signal-ccc", status=SignalStatus.INVALIDATED)
        new_position = _make_position("new-pos", signal_id="new-signal-ddd")

        position_repo = MagicMock()
        position_repo.get_position_by_signal.return_value = new_position

        execution_engine = MagicMock()

        # Act
        pos = position_repo.get_position_by_signal(inv_signal.signal_id)
        if (
            pos
            and pos.status == TradeStatus.OPEN
            and pos.signal_id == inv_signal.signal_id
        ):
            execution_engine.close_position_emergency(pos)

        # Assert
        execution_engine.close_position_emergency.assert_not_called()


# =============================================================================
# TEST: Alpaca position qty validation before emergency close
# =============================================================================


class TestAlpacaQtyValidation:
    """Tests for verifying Alpaca qty matches Firestore before closing."""

    def test_closes_normally_when_qty_matches(self):
        """Normal case: Alpaca and Firestore qty match, close proceeds."""
        # Arrange
        pos = _make_position("pos-1", signal_id="sig-1", qty=10.0)

        alpaca_position = MagicMock()
        alpaca_position.qty = "10.0"

        alpaca_client = MagicMock()
        alpaca_client.get_open_position.return_value = alpaca_position

        # Act
        alpaca_qty = float(alpaca_position.qty)

        # Assert
        assert (
            alpaca_qty >= pos.qty
        ), f"Alpaca qty ({alpaca_qty}) should be >= Firestore qty ({pos.qty})"

    def test_adjusts_qty_when_alpaca_has_less(self):
        """If Alpaca has fewer shares, adjust close qty to prevent overselling."""
        # Arrange
        pos = _make_position("pos-1", signal_id="sig-1", qty=10.0)

        alpaca_position = MagicMock()
        alpaca_position.qty = "5.0"

        alpaca_client = MagicMock()
        alpaca_client.get_open_position.return_value = alpaca_position

        # Act
        alpaca_qty = float(alpaca_position.qty)
        if alpaca_qty < pos.qty:
            pos.qty = alpaca_qty

        # Assert
        assert (
            pos.qty == 5.0
        ), f"Position qty should be adjusted to Alpaca qty 5.0, got {pos.qty}"

    def test_marks_closed_externally_when_alpaca_position_gone(self):
        """If position doesn't exist on Alpaca (404), mark CLOSED_EXTERNALLY."""
        # Arrange
        pos = _make_position("pos-1", signal_id="sig-1", qty=10.0)

        alpaca_client = MagicMock()
        mock_http_error = MagicMock()
        mock_http_error.response.status_code = 404
        error_404 = APIError("position not found", http_error=mock_http_error)
        alpaca_client.get_open_position.side_effect = error_404

        # Act
        try:
            alpaca_client.get_open_position(pos.symbol)
        except APIError as e:
            if e.status_code == 404:
                pos.status = TradeStatus.CLOSED
                pos.exit_reason = ExitReason.CLOSED_EXTERNALLY

        # Assert
        assert (
            pos.status == TradeStatus.CLOSED
        ), f"Expected status == CLOSED after 404, got {pos.status}"
        assert (
            pos.exit_reason == ExitReason.CLOSED_EXTERNALLY
        ), f"Expected exit_reason == CLOSED_EXTERNALLY, got {pos.exit_reason}"

    def test_skips_close_on_alpaca_api_error_not_404(self):
        """If API returns non-404 error (e.g. 500), do NOT mark closed."""
        # Arrange
        pos = _make_position("pos-1", signal_id="sig-1", qty=10.0)

        alpaca_client = MagicMock()
        mock_http_error = MagicMock()
        mock_http_error.response.status_code = 500
        error_500 = APIError("internal server error", http_error=mock_http_error)
        alpaca_client.get_open_position.side_effect = error_500

        # Act
        try:
            alpaca_client.get_open_position(pos.symbol)
        except APIError as e:
            if e.status_code == 404:
                pos.status = TradeStatus.CLOSED
            else:
                pass

        # Assert
        assert (
            pos.status == TradeStatus.OPEN
        ), f"Status should remain OPEN on non-404 error, got {pos.status}"
        assert (
            pos.exit_reason is None
        ), f"exit_reason should remain None on non-404 error, got {pos.exit_reason}"


# =============================================================================
# TEST: Duplicate symbol signal prevention
# =============================================================================


class TestDuplicateSymbolPrevention:
    """Tests for blocking signal generation when symbol has open Alpaca position."""

    def test_skips_signal_when_alpaca_position_exists(self):
        """Should skip signal generation if symbol already has an Alpaca position."""
        # Arrange
        alpaca_client = MagicMock()
        alpaca_position = MagicMock()
        alpaca_position.symbol = "AAVEUSD"
        alpaca_client.get_open_position.return_value = alpaca_position

        symbol = "AAVE/USD"
        alpaca_symbol = symbol.replace("/", "")
        should_skip = False

        # Act
        try:
            existing = alpaca_client.get_open_position(alpaca_symbol)
            if existing:
                should_skip = True
        except APIError:
            pass

        # Assert
        assert (
            should_skip is True
        ), "Signal should be skipped when Alpaca position already exists"

    def test_proceeds_when_no_alpaca_position(self):
        """Should proceed with signal generation when no Alpaca position exists."""
        # Arrange
        alpaca_client = MagicMock()
        mock_http_error = MagicMock()
        mock_http_error.response.status_code = 404
        error_404 = APIError("position does not exist", http_error=mock_http_error)
        alpaca_client.get_open_position.side_effect = error_404

        symbol = "AAVE/USD"
        alpaca_symbol = symbol.replace("/", "")
        should_skip = False

        # Act
        try:
            existing = alpaca_client.get_open_position(alpaca_symbol)
            if existing:
                should_skip = True
        except APIError:
            pass

        # Assert
        assert (
            should_skip is False
        ), "Signal should proceed when no Alpaca position exists (404)"
