"""An input a calculation call left to its default is Argus's assumption."""

from __future__ import annotations

from tests.domain.calculations.support import declaration, run_calculation


def test_an_input_left_to_its_default_is_an_assumption_not_the_readers() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": None,
            "annual_rate_pct": 5,
            "periods": 12,
        },
    )
    sources = {fact.name: fact.source.kind for fact in card.presentation.inputs}
    assert sources["start_value"] == "user"
    assert sources["contribution"] == "assumption"
    assert sources["inflation_rate_pct"] == "assumption"
    assert card.arguments["sources"]["contribution"]["kind"] == "assumption"
    revised = declaration("growth_projection").recompute_arguments(
        card.arguments, {"annual_rate_pct": 6}
    )
    kept = revised.model_dump(mode="json")["sources"]
    assert kept["contribution"]["kind"] == "assumption"
    assert kept["annual_rate_pct"]["kind"] == "user"
