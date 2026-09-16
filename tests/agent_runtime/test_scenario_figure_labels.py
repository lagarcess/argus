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
