"""Free replay of PR #626 f8d378c5's successful-card scenario framing failure."""

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.domain.calculations.answer_request import AnswerCalculation

from tests.agent_runtime.test_answer_calculation import _published_many


@pytest.fixture(
    params=[("Declining", "Unchanged", "Rising"), ("Baja", "Sin cambio", "Sube")]
)
def scenarios(request):
    return [
        AnswerCalculation.model_validate(
            {
                "name": label,
                "kind": "growth_projection",
                "solve_for": "end_value",
                "inputs": [
                    {
                        "name": "start_value",
                        "value": 10000,
                        "source": "user",
                        "currency": "USD",
                    },
                    {"name": "annual_rate_pct", "value": rate, "source": "assumption"},
                    {"name": "periods", "value": 10, "source": "user"},
                    {"name": "periods_per_year", "value": 1, "source": "user"},
                ],
            }
        )
        for label, rate in zip(request.param, (-10, 0, 10), strict=True)
    ]


@pytest.mark.parametrize(
    "reference", ["annual_rate_pct", "unknown_figure", "unknown.result"]
)
def test_shared_formula_does_not_erase_labeled_scenarios(scenarios, reference):
    # Reconstructed from the recorded inputs/reference failure, not raw model JSON.
    prose = "\n\n".join(
        f"**{request.name}**: {{{{{name}.end_value}}}} at {{{{{name}.annual_rate_pct}}}}."
        for request, name in zip(scenarios, ac.calculation_names(scenarios), strict=True)
    )
    template = (
        prose + "\n\n{{start_value}} * (1 + {{" + reference + "}} / 100) ^ {{periods}}."
    )
    notes = []
    published = _published_many(template, scenarios, notes=notes)
    cards = ac.cards_in(published.patch)
    assert all(card.outcome.status == "succeeded" for card in cards)
    for request, card in zip(scenarios, cards, strict=True):
        assert (
            f"**{request.name}**: {ac.figure_text(card.presentation.answer)}"
            in published.answer_text
        )
    assert "{{" not in published.answer_text
    assert ac.FIGURE_CHECK_REASON_CODE in notes
    # A stored recovery template must still re-render from changed card facts.
    assert published.template is not None
    mapping = dict(zip(ac.calculation_names(scenarios), cards, strict=True))
    first = cards[0].model_copy(
        update={
            "presentation": cards[0].presentation.model_copy(
                update={
                    "answer": cards[0].presentation.answer.model_copy(
                        update={"value": 4321}
                    )
                }
            )
        }
    )
    mapping[ac.calculation_names(scenarios)[0]] = first
    updated, failure = ac.render_answer_text(published.template["text"], mapping)
    assert failure is None and "USD 4,321" in updated


def test_unresolvable_scenario_row_recovers_under_its_original_label(scenarios):
    names = ac.calculation_names(scenarios)
    template = "\n\n".join(
        f"**{request.name}**: {{{{{name}.{'unknown' if index == 0 else 'end_value'}}}}}."
        for index, (request, name) in enumerate(zip(scenarios, names, strict=True))
    )
    notes = []
    published = _published_many(template, scenarios, notes=notes)
    for request, card in zip(scenarios, ac.cards_in(published.patch), strict=True):
        assert request.name in published.answer_text
        assert ac.figure_text(card.presentation.answer) in published.answer_text
    assert "{{" not in published.answer_text
    assert ac.FIGURE_CHECK_REASON_CODE in notes


@pytest.mark.parametrize(
    "language,label,explanation,scenarios",
    [
        (
            "es-419",
            "Escenarios NVDA",
            "No puedo predecir el futuro ni el resultado de un cruce dorado. "
            "Estos son escenarios ilustrativos, no pronósticos. "
            "Con {{amount}} durante {{horizon_years}} años, usamos un precio de "
            "{{price}} y ganancias por acción de {{per_share}}.",
            "Bajo: {{growth_low_pct}}. Base: {{growth_base_pct}}. Alto: {{growth_high_pct}}.",
        ),
        (
            "en",
            "NVDA scenarios",
            "I cannot predict the future or the outcome of a golden cross. "
            "These are illustrative scenarios, not forecasts. "
            "With {{amount}} over {{horizon_years}} years, we use a price of "
            "{{price}} and earnings per share of {{per_share}}.",
            "Low: {{growth_low_pct}}. Base: {{growth_base_pct}}. High: {{growth_high_pct}}.",
        ),
    ],
)
@pytest.mark.parametrize("invalid", [False, True])
@pytest.mark.parametrize("named", [False, True])
def test_successful_valuation_keeps_input_only_explanation(
    language, label, explanation, scenarios, invalid, named
):
    # PR #626 at 20984904: one successful valuation card, input references only.
    # Reconstruct the recorded shape without claiming verbatim model JSON.
    values = dict(
        amount=10000,
        horizon_years=10,
        price=213.94,
        per_share=7.91,
        growth_low_pct=0,
        growth_base_pct=10,
        growth_high_pct=20,
    )
    calculation = AnswerCalculation.model_validate(
        {
            "name": label if named else "",
            "kind": "valuation_scenarios",
            "inputs": [
                {
                    "name": name,
                    "value": value,
                    "source": "user"
                    if name in ("amount", "horizon_years")
                    else "assumption",
                    **({"currency": "USD"} if name == "amount" else {}),
                }
                for name, value in values.items()
            ],
        }
    )
    template = explanation + "\n\n" + scenarios
    if invalid:
        template += "\n\n{{unknown_result}}."
    notes = []
    published = _published_many(template, [calculation], language=language, notes=notes)
    card = ac.card_in(published.patch)
    assert card.outcome.status == "succeeded"
    owner = ac.calculation_names([calculation])[0]
    cards = {owner: card}
    expected, failure = ac.render_answer_text(explanation + "\n\n" + scenarios, cards)
    assert failure == "missing_computed_reference"
    assert expected in published.answer_text
    if named:
        assert (
            f"{label}: {ac.figure_text(card.presentation.answer)}"
            in published.answer_text
        )
    else:
        assert ac.figure_text(card.presentation.answer) in published.answer_text
        assert "calculation_1" not in published.answer_text
    assert "{{" not in published.answer_text
    assert ac.FIGURE_CHECK_REASON_CODE in notes
    assert published.template is not None
    assert ac.render_answer_text(published.template["text"], cards) == (
        published.answer_text,
        None,
    )
    # The attached card owns all three labeled, computed scenarios.
    rows = {row.name: row for row in card.presentation.rows}
    for scenario in ("low", "base", "high"):
        row = rows[f"value_at_horizon_{scenario}"]
        assert row.value is not None
        assert (
            row.label.locale_key
            == f"tools.calc.valuation_scenarios.value_at_horizon_{scenario}"
        )
