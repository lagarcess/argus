"""A balance is done at time zero only when it meets its target and cannot fall."""

from __future__ import annotations

from argus.domain.finance import tvm


def test_only_a_balance_that_does_not_fall_is_done_at_time_zero() -> None:
    assert tvm.target_already_met(1_200, 0, 1_000, 0.01)
    assert tvm.target_already_met(1_000, 0, 1_000, 0.0)
    assert tvm.target_already_met(1_000, 100, 900, -0.01)
    assert not tvm.target_already_met(1_000, 0, 500, -0.1)
    assert not tvm.target_already_met(900, 0, 1_000, 0.05)
