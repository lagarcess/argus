"""Generic edit accounting works without knowing backtest fields."""

from argus.domain.edit_contract import complete_edit_disclosure


def test_second_artifact_uses_the_same_applied_or_disclosed_contract():
    requested = [("set", "savings_goal"), ("set", "monthly_deposit")]
    assert (
        complete_edit_disclosure(
            requested=requested,
            materialized_targets={"savings_goal", "monthly_deposit"},
            has_changes=True,
        )
        is None
    )
    assert complete_edit_disclosure(
        requested=requested,
        materialized_targets={"savings_goal"},
        has_changes=True,
    ) == {
        "unapplied": [
            {"op": "set", "target": "monthly_deposit", "reason": "not_materialized"}
        ]
    }


def test_empty_application_cannot_be_hidden_by_an_optimistic_note():
    disclosure = complete_edit_disclosure(
        requested=[],
        materialized_targets=set(),
        has_changes=False,
        note="Done.",
    )
    assert disclosure["unapplied"][0]["reason"] == "no_change_applied"


def test_existing_refusal_keeps_its_specific_reason_without_duplicate_entries():
    refusal = {"op": "set", "target": "monthly_deposit", "reason": "outside_range"}
    disclosure = complete_edit_disclosure(
        requested=[("set", "monthly_deposit")],
        materialized_targets=set(),
        has_changes=False,
        unapplied=[refusal],
        note="Choose a supported value.",
    )
    assert disclosure == {"unapplied": [refusal], "note": "Choose a supported value."}
