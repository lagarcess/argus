"""A finance figure backs a calculation input only when it is the same kind of
figure about the same security, in the calculation's currency."""

from __future__ import annotations

from argus.agent_runtime.answer_calculation import _evidenced
from argus.domain.research.contracts import RetrievedRow

from tests.research.conftest import retrieved_row


def _row(**fields) -> RetrievedRow:
    return RetrievedRow.model_validate(retrieved_row(source_url=None, **fields))


def test_a_percent_row_never_backs_a_money_input_of_the_same_number() -> None:
    growth = _row(label="revenue growth", value=7.91, kind="percent", unit="%")
    assert (
        _evidenced(7.91, [growth], name="per_share", currency="USD", symbol="NVDA")
        is None
    )
    assert (
        _evidenced(7.91, [growth], name="growth_base_pct", currency="USD", symbol="NVDA")
        == growth
    )


def test_a_money_row_backs_an_input_only_in_its_currency_and_security() -> None:
    eps = _row(label="earnings per share", value=7.91, kind="currency", unit="USD")
    assert _evidenced(7.91, [eps], name="per_share", currency="USD", symbol="NVDA") == eps
    assert (
        _evidenced(7.91, [eps], name="per_share", currency="DOP", symbol="NVDA") is None
    )
    assert (
        _evidenced(7.91, [eps], name="per_share", currency="USD", symbol="AAPL") is None
    )
