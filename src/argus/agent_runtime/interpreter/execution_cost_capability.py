from __future__ import annotations

from argus.domain.backtesting.config import _execution_realism_feature_enabled


def execution_cost_capability_clause() -> str:
    """Capability truth for the interpreter system prompt.

    With the engine flag off this must stay byte-identical to the legacy
    sentence so flag-off interpretation cannot drift.
    """
    if not _execution_realism_feature_enabled():
        return (
            "No brokerage trading, shorting, mixed asset-class runs, "
            "custom scripting, or real slippage/fee realism.\n\n"
        )
    return (
        "No brokerage trading, shorting, mixed asset-class runs, or "
        "custom scripting. Per-trade fee and slippage assumptions are "
        "supported: when the user states them explicitly in any language, "
        "record decimal fractions in extra_parameters.fee_rate and "
        "extra_parameters.slippage (0.1% fees means 0.001; one basis point "
        "is 0.0001, so 10 bps fees means 0.001 and 5 bps slippage means "
        "0.0005). Copy the exact bounded current-user phrase supporting each "
        "populated value into evidence_spans.fee_rate and "
        "evidence_spans.slippage. Canonical explicit-user provenance is derived "
        "from those spans; never invent costs or evidence. Both costs default "
        "to zero when the user does not state them.\n\n"
    )
