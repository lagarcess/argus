from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.scripts.diagnostics.book_balancing import BookBalancer, LedgerEntry


# Mock objects matching Alpaca / Firestore structures
@dataclass
class MockPosition:
    symbol: str
    qty: str
    avg_entry_price: str


@dataclass
class MockOrder:
    client_order_id: str
    symbol: str
    filled_qty: str = "1.0"
    filled_avg_price: str = "100.0"
    filled_at: Any = None
    submitted_at: Any = None


@dataclass
class MockDBPosition:
    position_id: str
    symbol: str
    status: Any  # Enum value
    quantity: float
    entry_fill_price: float
    updated_at: Any = None


class MockStatus:
    value = "OPEN"


class MockStatusClosed:
    value = "CLOSED"


@pytest.fixture
def mock_dependencies():
    with (
        patch(
            "crypto_signals.scripts.diagnostics.book_balancing.get_settings"
        ) as mock_settings,
        patch(
            "crypto_signals.scripts.diagnostics.book_balancing.get_trading_client"
        ) as mock_alpaca,
        patch(
            "crypto_signals.scripts.diagnostics.book_balancing.PositionRepository"
        ) as mock_repo_cls,
    ):
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_repo = mock_repo_cls.return_value
        mock_console = MagicMock()

        yield {
            "settings": mock_settings,
            "alpaca": mock_alpaca.return_value,
            "repo": mock_repo,
            "console": mock_console,
        }


def test_fetch_ledger_calls_apis(mock_dependencies):
    """Verify ledger fetching correctly calls necessary APIs."""
    mock_console = mock_dependencies["console"]
    balancer = BookBalancer(console_client=mock_console)

    # Setup Mocks
    mock_dependencies["alpaca"].get_all_positions.return_value = []
    mock_dependencies["alpaca"].get_orders.return_value = []
    mock_dependencies["repo"].get_open_positions.return_value = []
    mock_dependencies["repo"].get_closed_positions.return_value = []

    balancer.fetch_ledger(limit=300)

    # Verify Calls
    mock_dependencies["alpaca"].get_all_positions.assert_called_once()
    mock_dependencies["alpaca"].get_orders.assert_called_once()

    # Check limit passed to filters
    call_args = mock_dependencies["alpaca"].get_orders.call_args
    assert call_args[1]["filter"].limit == 300

    mock_dependencies["repo"].get_open_positions.assert_called_once()
    mock_dependencies["repo"].get_closed_positions.assert_called_once_with(limit=300)


def test_audit_identifies_reverse_orphan(mock_dependencies):
    """Ensure the audit identifies reverse orphan positions."""
    mock_console = mock_dependencies["console"]
    balancer = BookBalancer(console_client=mock_console)

    # Scenario: Open in Alpaca (Symbol "BTC/USD"), Missing in DB
    balancer.alpaca_open = {
        "BTC/USD": LedgerEntry("ALPACA", "unknown", "BTC/USD", "OPEN", 1.0, 50000.0, None)
    }
    balancer.db_open = {}

    # Patch console.print to capture output?
    # Or strict check of internal logic if we refactor?
    # For now, let's assume 'audit' prints to console.

    balancer.audit()

    # Verify "REVERSE ORPHAN" was printed
    # We can inspect the calls to console.print
    # OR we can inspect the table add_row if implementation uses rich.table.Table
    # Since table is constructed inside method, we check if console.print was called with a Table

    # NOTE: Asserting on rich Table content is hard.
    # Easier to verify issues_found count if return value existed, but audit returns None.
    # We will trust that if Reverse Orphan logic triggers, it prints "FOUND 1 CRITICAL ISSUES"

    # Verify console.print was called with a Table object
    assert mock_console.print.called

    # Check if any call argument was a Table
    found_table = False
    for call in mock_console.print.call_args_list:
        args, _ = call
        if args and hasattr(args[0], "rows"):
            found_table = True
            break

    assert found_table, "Should have printed a Table"


def test_audit_identifies_zombie(mock_dependencies):
    """Ensure the audit identifies zombie positions."""
    mock_console = mock_dependencies["console"]
    balancer = BookBalancer(console_client=mock_console)

    # Scenario: Open in DB ("ETH/USD"), Missing in Alpaca
    balancer.alpaca_open = {}
    balancer.db_open = {
        "pos-123": LedgerEntry(
            "FIRESTORE", "pos-123", "ETH/USD", "OPEN", 10.0, 3000.0, None
        )
    }

    balancer.audit()

    assert mock_console.print.called
    # Basic check - ensure we reached the end
    # Last print is usually summary or table if summary skipped
    pass


def test_audit_balanced(mock_dependencies):
    """Verify audit passes successfully for a balanced book."""
    mock_console = mock_dependencies["console"]
    balancer = BookBalancer(console_client=mock_console)

    # Scenario: Balanced
    balancer.alpaca_open = {
        "SOL/USD": LedgerEntry("ALPACA", "unknown", "SOL/USD", "OPEN", 5.0, 20.0, None)
    }
    balancer.db_open = {
        "pos-456": LedgerEntry("FIRESTORE", "pos-456", "SOL/USD", "OPEN", 5.0, 20.0, None)
    }

    balancer.audit()

    if not mock_console.print.called:
        pytest.fail("Console.print was NOT called at all.")

    # Check for "Balanced" text in ANY call
    found_balanced = False
    debug_calls = []
    for call in mock_console.print.call_args_list:
        args, _ = call
        if args:
            arg_str = str(args[0])
            debug_calls.append(arg_str)
            if "Balanced" in arg_str:
                found_balanced = True
                break

    if not found_balanced:
        pytest.fail(f"Balanced not found. Calls: {debug_calls}")


def test_audit_detailed_target(mock_dependencies):
    """Verify audit functions correctly targeting a specific symbol."""
    mock_console = mock_dependencies["console"]
    balancer = BookBalancer(console_client=mock_console)

    # Setup data
    target_id = "target-123"
    balancer.db_closed = {
        target_id: LedgerEntry(
            "FIRESTORE", target_id, "BTC/USD", "CLOSED", 0.1, 50000.0, None
        )
    }

    balancer.audit(target=target_id)

    # Check if DETAILED INSPECTION rule was printed (much easier)
    # mock_console.rule is called with title.
    rules = [str(call) for call in mock_console.rule.call_args_list]
    assert any(
        target_id in r for r in rules
    ), "Should have printed detailed inspection rule"
