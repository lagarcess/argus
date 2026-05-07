from __future__ import annotations

from argus.domain.engine_launch.models import LaunchBacktestRequest


def resolve_starting_capital(
    request: LaunchBacktestRequest,
    *,
    initial_price: float | None = None,
) -> float:
    if request.sizing_mode == "capital_amount":
        assert request.capital_amount is not None
        return float(request.capital_amount)

    if initial_price is None or initial_price <= 0:
        raise ValueError("position_price_required")

    assert request.position_size is not None
    return float(request.position_size) * float(initial_price)
