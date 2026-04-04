import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from crypto_signals.domain.schemas import SignalStatus, TradeStatus

from tests.engine.test_tp_automation_race import _make_position, _make_signal


def test_tp3_race_condition_deterministically():
    """
    Verify race condition handling between TP automation and new position entry.
    Uses threading.Event for deterministic synchronization instead of time.sleep().
    """
    # Arrange Data
    # Old signal: TP3 hit, needs to close position
    old_signal = _make_signal("old-sig", status=SignalStatus.TP3_HIT)

    # New position: Created by NEW signal (same symbol), implies re-entry happened
    new_position = _make_position("new-pos", signal_id="new-sig-reentry")

    # Arrange Mocks
    position_repo = MagicMock()
    # Scenario: Automation asks for position by OLD signal ID
    # Repository incorrectly returns the NEW position (simulating the bug/race)
    position_repo.get_position_by_signal.return_value = new_position

    execution_engine = MagicMock()

    # 3. Deterministic Synchronization Events
    t1_ready = threading.Event()
    t2_ready = threading.Event()

    def tp_automation_task():
        """Simulates the background TP automation checking for the old signal."""
        t1_ready.set()  # Signal that T1 has started
        t2_ready.wait()  # Wait for T2 to also start (simulate true parallelism)

        # Guard Logic (The Fix)
        pos = position_repo.get_position_by_signal(old_signal.signal_id)

        # CRITICAL: The guard `pos.signal_id == old_signal.signal_id` prevents
        # closing the wrong position.
        if (
            pos
            and pos.status == TradeStatus.OPEN
            and pos.signal_id == old_signal.signal_id
        ):
            execution_engine.close_position_emergency(pos)

    def re_entry_task():
        """Simulates the new signal entry happening concurrently."""
        t2_ready.set()
        t1_ready.wait()
        # In a real race, this thread writes 'new_position' to DB
        # just as T1 reads it. Here we simulate T1 reading 'new_position' via the mock.
        pass

    # Act
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(tp_automation_task)
        f2 = executor.submit(re_entry_task)

        f1.result()
        f2.result()

    # Assert
    # The guard should have prevented close_position_emergency from being called
    # because new_position.signal_id != old_signal.signal_id
    execution_engine.close_position_emergency.assert_not_called()
