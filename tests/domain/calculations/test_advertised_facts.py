"""Every advertised result name must resolve through an actual rendered card."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy

import pytest
from argus.agent_runtime.answer_calculation import render_answer_text
from argus.domain.calculations import get_calculation_declarations
from argus.domain.calculations.answer_request import calculation_kinds_clause
from argus.domain.tool_contracts import ToolCall, ToolOutcome, ToolResultCard
from argus.domain.tool_presentation_facts import presentation_reference_facts

from tests.domain.calculations import WORKED_ARGUMENTS
from tests.domain.calculations.support import run_calculation

DECLARATIONS = get_calculation_declarations()


def _local_variants(declaration) -> Iterator[ToolResultCard]:
    name = declaration.name
    seeds = [deepcopy(WORKED_ARGUMENTS[name])]
    if name == "time_value":
        seeds.append(
            {
                "currency": seeds[0]["currency"],
                "direction": "save",
                "present_value": 10000,
                "payment": 100,
                "future_value": None,
                "annual_rate_pct": 6,
                "periods": 120,
            }
        )
    elif name == "effective_rate":
        seeds.append({"currency": seeds[0]["currency"], "nominal_rate_pct": 10})
    elif name == "valuation_scenarios":
        seeds.append({**seeds[0], "amount": 10000})
    elif name == "ranked_comparison":
        maximum = next(
            m.max_length
            for m in declaration.arguments_type.model_fields["items"].metadata
            if hasattr(m, "max_length")
        )
        for count in (2, maximum):
            seeds.append(
                {
                    **seeds[0],
                    "items": [
                        {"label": f"Option {index}", "value": index // 2 + 1}
                        for index in range(count)
                    ],
                }
            )
    elif name == "scaled_amount":
        seeds.extend(
            {
                **seeds[0],
                "rate_unit": unit,
                "operation": operation,
                "output_currency": "DOP",
            }
            for unit in ("percent", "multiple")
            for operation in ("multiply", "divide")
        )
    for seed in seeds:
        card = run_calculation(name, seed)
        assert card.outcome.status == "succeeded", card.outcome
        yield card
        for rule in declaration.rules:
            solved = {field: card.outcome.result[field] for field in rule.fields}
            for unknown in rule.fields:
                variant = run_calculation(name, {**seed, **solved, unknown: None})
                assert variant.outcome.status == "succeeded", variant.outcome
                yield variant


def _historical_variants(declaration) -> Iterator[ToolResultCard]:
    # Typed offline observations exercise only presentation, never a provider.
    for decline in (True, False):
        outcome = ToolOutcome(
            status="succeeded",
            result={
                "symbol": "BTC",
                "asset_class": "crypto",
                "max_drawdown_pct": -50 if decline else 0,
                "requested_start_date": "2024-01-01",
                "requested_end_date": "2024-01-08",
                "observed_start_date": "2024-01-02",
                "observed_end_date": "2024-01-08",
                "peak_date": "2024-01-03" if decline else None,
                "trough_date": "2024-01-04" if decline else None,
                "observations": 5,
                "source": "argus_market_data",
                "price_basis": "close",
                "default_window": False,
            },
        )
        yield declaration.result_card(
            call=ToolCall(
                tool_name=declaration.name,
                call_id="offline-history",
                arguments={"symbol": "BTC"},
            ),
            outcome=outcome,
            artifact_id="offline-history",
        )


def _advertised_names(name: str) -> set[str]:
    line = next(
        line
        for line in calculation_kinds_clause().splitlines()
        if line.startswith(f"- {name}:")
    )
    results = line.split(" Results: ", 1)[-1] if " Results: " in line else ""
    return {part.split(" (", 1)[0] for part in results.rstrip(".").split(", ") if part}


@pytest.mark.parametrize("declaration", DECLARATIONS, ids=lambda item: item.name)
def test_every_advertised_name_has_a_rendered_witness(declaration):
    cards = list(
        _local_variants(declaration)
        if declaration.policy.external_calls == 0
        else _historical_variants(declaration)
    )
    advertised = _advertised_names(declaration.name)
    projection = declaration.card.result_projection
    assert projection is not None
    unconditional = {
        reference.name for reference in projection.references if not reference.conditional
    }
    witnessed = set()
    for card in cards:
        facts = presentation_reference_facts(card.presentation)
        result_names = {row.name for row in card.presentation.rows}
        if card.presentation.answer is not None:
            result_names.add(card.presentation.answer.name)
        assert unconditional <= result_names
        witnessed.update(result_names)
        available = advertised & facts.keys()
        template = " / ".join("{{" + name + "}}" for name in sorted(available))
        _, failure = render_answer_text(template, {"calculation": card})
        assert failure is None, (declaration.name, template, failure)
    assert advertised == witnessed, {
        "unrenderable": advertised - witnessed,
        "unadvertised": witnessed - advertised,
    }


def test_requested_window_metadata_is_not_advertised_as_a_rendered_fact():
    names = _advertised_names("historical_drawdown")
    assert {"observed_start_date", "observed_end_date"} <= names
    assert not {"requested_start_date", "requested_end_date"} & names
