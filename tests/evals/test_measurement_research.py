"""Published research is observed through its bound call and rendered result."""

from __future__ import annotations

import pytest

from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_research import research_outcome
from tests.evals.test_measurement_selection import _selection_patch, _wire_delivery


@pytest.fixture
def price_case():
    return next(
        case
        for case in harness.load_eval_cases()
        if case.id == "ordinary_conversation_price_question_en"
    )


def test_zero_calls_cannot_publish_a_research_sidecar_from_another_turn():
    previous_turn = _selection_patch(action=False)

    assert research_outcome(previous_turn)["published"] is True
    assert research_outcome(previous_turn, calls=[], dispatch_patch={}) is None


@pytest.mark.parametrize("figures", [False, True])
@pytest.mark.parametrize("names", [("read",), ("read", "read"), ("read", "compare")])
def test_published_research_uses_completed_calls_without_requiring_a_tool_name(
    monkeypatch, price_case, figures, names
):
    _wire_delivery(
        monkeypatch,
        patches=[_selection_patch(figures=figures, action=False) for _ in names],
        names=names,
    )

    result = harness.run_eval_case(price_case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert result["typed_outcome"]["research"]["published"] is True
    assert result["typed_outcome"]["research"]["rows"] == int(figures) * len(names)


@pytest.mark.parametrize(
    "missing_binding", ["tool_effects", "tool_call_records", "final_response_payload"]
)
def test_unbound_research_is_not_published_evidence(
    monkeypatch, price_case, missing_binding
):
    _wire_delivery(monkeypatch, patches=[_selection_patch(action=False)], names=("read",))
    dispatch = harness.dispatch_requested_calls

    def incomplete_delivery(**kwargs):
        result = dispatch(**kwargs)
        result.stage_patch.pop(missing_binding, None)
        return result

    monkeypatch.setattr(harness, "dispatch_requested_calls", incomplete_delivery)

    result = harness.run_eval_case(price_case, run_prose_judge=False)

    assert result["typed_outcome"]["research"] is None
    assert any(failure.startswith("research:") for failure in result["failed_checks"])
