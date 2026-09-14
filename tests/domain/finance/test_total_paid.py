"""Level payments that clear a loan early pay only what the balance needs."""

from __future__ import annotations

import pytest
from argus.domain.finance import tvm


def test_payments_stop_once_the_balance_is_cleared() -> None:
    assert tvm.total_paid(1_000, 0.0, 200, 12) == pytest.approx(1_000.0)
    assert tvm.total_paid(1_000, 0.01, 300, 12) == pytest.approx(1_022.48371)


def test_payments_due_at_the_start_clear_before_the_period_accrues() -> None:
    assert tvm.total_paid(1_000, 0.01, 600, 12, timing=1) == pytest.approx(1_004.0)
