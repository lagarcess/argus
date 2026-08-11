"""The frozen payload must not carry the author's language.

A receipt is opened by strangers whose language has nothing to do with whoever ran
the backtest, so every field it freezes is a key and a scalar, and the sentences are
composed at view time. These are the proofs for that rule: the invariant over the
whole payload first, then the cases for each field that used to break it.
"""

from __future__ import annotations

from typing import Any, get_args

import pytest
from argus.api.public_excerpt_schemas import PublicExcerptPayload, PublicExcerptSnapshot
from argus.domain.public_excerpts import (
    PublicExcerptSourceError,
    build_public_excerpt_payload,
    new_public_excerpt_id,
)
from pydantic import ValidationError

from tests.public_excerpt_factories import (
    BUY_AND_HOLD_CONFIG_SNAPSHOT,
    DCA_CONFIG_SNAPSHOT,
    ENGINE_CONFIG_SNAPSHOT,
    ENGINE_MODELED_COSTS_CONFIG_SNAPSHOT,
    GENERATED_CARD_CONFIG_SNAPSHOT,
    WINDOW_END,
    WINDOW_START,
    build_artifact,
    build_artifact_payload,
    build_chart,
    build_generated_artifact,
    build_result_card,
    utc,
)

OWNER_ID = "99999999-9999-4999-8999-999999999999"


def _payload(**overrides: Any) -> PublicExcerptPayload:
    kwargs: dict[str, Any] = {
        "artifact": build_artifact(),
        "run_chart": build_chart(),
        "run_config_snapshot": BUY_AND_HOLD_CONFIG_SNAPSHOT,
        "owner_note": None,
        "content_language": "en",
    }
    kwargs.update(overrides)
    return build_public_excerpt_payload(**kwargs)


def _assumption_pairs(payload: PublicExcerptPayload) -> list[tuple[str, str | None]]:
    return [(fact.key, fact.value) for fact in payload.assumptions]


def test_the_frozen_payload_does_not_depend_on_the_author_s_language() -> None:
    """The invariant this whole lane exists for, stated at the altitude of the class.

    The same run, written up by the production generator in each supported language,
    has to freeze the same payload. Only ``content_language`` may differ, because it
    is the one field whose job is to name the language.

    Written against the real generator rather than a fixture on purpose. A literal
    card cannot show a language difference, which is how prose reached a public page
    that strangers open: the frozen sentences were correct for the author and
    unreadable for everyone else. Any field added later that freezes a rendered
    string fails here, whichever field it is.
    """
    english = _payload(
        artifact=build_generated_artifact(language="en"),
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
        content_language="en",
    ).model_dump(mode="json")
    spanish = _payload(
        artifact=build_generated_artifact(language="es-419"),
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
        content_language="es-419",
    ).model_dump(mode="json")

    assert english.pop("content_language") == "en"
    assert spanish.pop("content_language") == "es-419"
    assert english == spanish


def test_the_generator_s_prose_is_not_read_at_all() -> None:
    """Not merely translated elsewhere: never consulted.

    Rewriting every assumption sentence the run froze, into text no projection
    would ever produce, must leave the receipt byte identical. If it does not, some
    field is still passing the author's prose through.
    """
    artifact = build_generated_artifact(language="en")
    card = dict(artifact.payload["result_card"])
    card["assumptions"] = ["nonsense the projection must never repeat"]
    card["date_range"] = {**card["date_range"], "display": "whenever to whenever"}
    rewritten = build_artifact(
        title=artifact.title,
        payload=build_artifact_payload(
            result_card=card,
            extra={"assumptions": list(card["assumptions"])},
        ),
    )
    baseline = _payload(
        artifact=artifact,
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
    )
    assert (
        _payload(artifact=rewritten, run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT)
        == baseline
    )


def test_every_assumption_the_generator_can_write_has_a_typed_fact() -> None:
    """One run that produces every assumption class the card builder emits.

    The generator writes six sentences for this config: the contribution pair, long
    only, equal weight, the modeled costs, and the benchmark that carried them. Each
    one has to survive the projection as a key, or the receipt is quieter about the
    run than the app was.
    """
    card = build_generated_artifact(language="en").payload["result_card"]
    assert len(card["assumptions"]) == 6
    payload = _payload(
        artifact=build_generated_artifact(language="en"),
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
    )
    assert _assumption_pairs(payload) == [
        ("recurring_contribution", "200"),
        ("contribution_cadence", "monthly"),
        ("starting_principal", "0"),
        ("long_only", None),
        ("equal_weight", None),
        ("modeled_fee_bps", "10"),
        ("modeled_slippage_bps", "5"),
        ("benchmark_same_modeled_costs", "SPY"),
    ]


def test_a_costless_run_says_so_rather_than_saying_nothing() -> None:
    payload = _payload(run_config_snapshot=BUY_AND_HOLD_CONFIG_SNAPSHOT)
    assert _assumption_pairs(payload) == [
        ("long_only", None),
        ("equal_weight", None),
        ("no_costs", None),
        ("benchmark", "SPY"),
    ]


def test_the_direct_engine_snapshot_projects_the_same_facts() -> None:
    """Both config snapshot shapes reach the same assumptions, as they must.

    The agent path nests the engine config; the direct engine path is the config.
    Reading only one of them is how the strategy facts once went missing for every
    run made through the other.
    """
    agent_path = _assumption_pairs(_payload(run_config_snapshot=DCA_CONFIG_SNAPSHOT))
    engine_path = _assumption_pairs(_payload(run_config_snapshot=ENGINE_CONFIG_SNAPSHOT))
    assert [key for key, _ in agent_path] == [key for key, _ in engine_path]
    assert dict(agent_path)["contribution_cadence"] == "monthly"
    assert dict(engine_path)["contribution_cadence"] == "weekly"


def test_assumption_values_carry_no_locale_formatting() -> None:
    """Bare scalars, so the viewer's locale supplies its own separators.

    A frozen "$1,000" reads as one thousand to one reader and as one to another.
    """
    large = {
        **ENGINE_CONFIG_SNAPSHOT,
        "starting_capital": 25_000,
        "recurring_contribution": 25_000,
    }
    values = dict(_assumption_pairs(_payload(run_config_snapshot=large)))
    assert values["recurring_contribution"] == "25000"


def test_the_assumption_key_set_is_closed() -> None:
    from argus.api.public_excerpt_schemas import AssumptionKey, PublicExcerptAssumption

    assert set(get_args(AssumptionKey)) == {
        "long_only",
        "equal_weight",
        "no_costs",
        "modeled_fee_bps",
        "modeled_slippage_bps",
        "benchmark",
        "benchmark_same_modeled_costs",
        "recurring_contribution",
        "contribution_cadence",
        "starting_principal",
    }
    with pytest.raises(ValidationError):
        PublicExcerptAssumption(key="whatever_the_run_wrote", value="anything")


def test_a_run_whose_stated_costs_will_not_project_refuses() -> None:
    """Understating a modeled cost misdescribes every number beside it."""
    unreadable = {
        **ENGINE_CONFIG_SNAPSHOT,
        "_execution_realism": {"enabled": True, "fee_bps": "n/a", "slippage_bps": 5.0},
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=unreadable)


def test_a_recurring_run_with_no_contribution_amount_refuses() -> None:
    without_amount = {
        key: value
        for key, value in ENGINE_CONFIG_SNAPSHOT.items()
        if key not in {"starting_capital", "recurring_contribution"}
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(run_config_snapshot=without_amount)


def test_the_flag_state_at_share_time_cannot_rewrite_what_the_run_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The costs are read from the frozen run, not through the live feature flag.

    A receipt created after the kill switch was thrown still describes a run that
    was charged, because the run was charged.
    """
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    values = dict(
        _assumption_pairs(
            _payload(run_config_snapshot=ENGINE_MODELED_COSTS_CONFIG_SNAPSHOT)
        )
    )
    assert values["modeled_fee_bps"] == "10"
    assert values["modeled_slippage_bps"] == "5"


# ── The tested window ─────────────────────────────────────────────────────────


def test_the_window_freezes_two_dates_and_no_rendered_string() -> None:
    date_range = _payload().date_range
    assert date_range.start == WINDOW_START
    assert date_range.end == WINDOW_END
    assert "display" not in date_range.model_dump(mode="json")


@pytest.mark.parametrize(
    "window",
    [
        {"start": "January 2, 2024", "end": "March 1, 2024"},
        {"start": "2 de enero de 2024", "end": "1 de marzo de 2024"},
        {"start": "2024-02-30", "end": WINDOW_END},
        {"start": WINDOW_START, "end": ""},
    ],
)
def test_a_window_the_page_cannot_parse_is_refused(window: dict[str, str]) -> None:
    """A rendered window is not a window. The page has to be able to speak it."""
    poisoned = build_artifact_payload(
        result_card={**build_result_card(), "date_range": window}
    )
    with pytest.raises(PublicExcerptSourceError):
        _payload(artifact=build_artifact(payload=poisoned))


def test_the_owner_list_row_carries_the_window_as_dates() -> None:
    """The owner reads this row in the app's current language, not the run's."""
    from argus.domain.public_excerpts import snapshot_list_item

    snapshot = PublicExcerptSnapshot(
        id="0",
        public_id=new_public_excerpt_id(),
        owner_id=OWNER_ID,
        title="AAPL",
        payload=_payload(),
        payload_digest="0" * 64,
        created_at=utc(),
    )
    row = snapshot_list_item(snapshot)
    assert row.date_range.start == WINDOW_START
    assert row.date_range.end == WINDOW_END


def test_a_metric_key_outside_the_closed_set_is_left_out() -> None:
    """Its label would have to be frozen to be readable, so it is not published."""
    card = {
        **build_result_card(),
        "rows": [
            {"key": "total_return_pct", "label": "Total return", "value": "+18.4%"},
            {
                "key": "benchmark_delta",
                "label": "Compared with SPY",
                "value": "Beat by 9.3 percentage points",
            },
        ],
    }
    payload = _payload(
        artifact=build_artifact(payload=build_artifact_payload(result_card=card))
    )
    assert [metric.key for metric in payload.metrics] == ["total_return_pct"]


def test_a_metric_freezes_its_number_and_no_label() -> None:
    metric = _payload().metrics[0]
    assert "label" not in metric.model_dump(mode="json")
