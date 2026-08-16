"""The frozen payload must not carry the author's language.

A receipt is opened by strangers whose language has nothing to do with whoever ran
the backtest, so every field it freezes is a key and a scalar, and the sentences are
composed at view time. These are the proofs for that rule: the invariant over the
whole payload first, then the cases for each field that used to break it.
"""

from __future__ import annotations

from typing import Any, get_args

import pytest
from argus.api.public_excerpt_schemas import (
    MetricKey,
    PublicExcerptPayload,
    PublicExcerptSnapshot,
)
from argus.domain.capability_registry import ALLOWED_TEMPLATES
from argus.domain.public_excerpts import (
    BENCHMARK_METRIC_KEYS,
    PROSE_METRIC_KEYS,
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
    build_template_artifact,
    generated_card_snapshot,
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
    # Everything except the prose is carried over untouched, so the only difference
    # between the two artifacts is the sentences the projection must not read.
    rewritten = build_artifact(
        title=artifact.title,
        payload={
            **artifact.payload,
            "result_card": card,
            "assumptions": list(card["assumptions"]),
        },
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
    assert len(card["assumptions"]) == 7
    payload = _payload(
        artifact=build_generated_artifact(language="en"),
        run_config_snapshot=GENERATED_CARD_CONFIG_SNAPSHOT,
    )
    assert _assumption_pairs(payload) == [
        ("recurring_contribution", "200"),
        ("contribution_cadence", "monthly"),
        ("starting_principal", "0"),
        ("fractional_shares", None),
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
        "dca_capital": {
            **ENGINE_CONFIG_SNAPSHOT["dca_capital"],
            "contribution": 25_000,
        },
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
        "fractional_shares",
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
        if key != "dca_capital"
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


def test_a_metric_freezes_its_number_and_no_label() -> None:
    metric = _payload().metrics[0]
    assert "label" not in metric.model_dump(mode="json")


# ── Nothing vanishes: the other half of the invariant ─────────────────────────
#
# Cross-language equality alone could not see a field disappearing, because zero
# metrics is byte-identical to zero metrics. That blindness let the benchmark
# comparison drop out of every real receipt while the page went on naming a
# benchmark. These drive the production generator across every executable template
# and assert on presence and count, not only on sameness.

TEMPLATE_CASES = [
    (template, modeled_costs)
    for template in sorted(ALLOWED_TEMPLATES)
    for modeled_costs in (False, True)
]


def _template_payload(
    template: str, *, modeled_costs: bool, language: str = "en"
) -> tuple[PublicExcerptPayload, dict[str, Any]]:
    artifact, card = build_template_artifact(
        template, language=language, modeled_costs=modeled_costs
    )
    payload = build_public_excerpt_payload(
        artifact=artifact,
        run_chart=build_chart(),
        run_config_snapshot=generated_card_snapshot(
            template, modeled_costs=modeled_costs
        ),
        owner_note=None,
        content_language=language,
    )
    return payload, card


def test_every_executable_template_is_covered_by_these_cases() -> None:
    """Derived from the registry, so a template added later has nowhere to hide."""
    assert {template for template, _ in TEMPLATE_CASES} == set(ALLOWED_TEMPLATES)


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_the_metric_key_set_covers_everything_the_generator_emits(
    template: str, modeled_costs: bool
) -> None:
    """The enum is checked against the generator instead of being remembered.

    The previous set carried three keys nothing emits and omitted the only benchmark
    number a real card contains, which is exactly the kind of drift a hand-kept list
    accumulates.
    """
    _, card = _template_payload(template, modeled_costs=modeled_costs)
    known = set(get_args(MetricKey)) | PROSE_METRIC_KEYS
    emitted = {row["key"] for row in card["rows"]}
    assert emitted <= known, f"unprojectable metric keys: {sorted(emitted - known)}"


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_no_result_card_number_is_lost_on_the_way_into_a_receipt(
    template: str, modeled_costs: bool
) -> None:
    """Every row the card carried is accounted for, by name.

    The one row that is not carried under its own key is the prose comparison, and
    it is only allowed to be missing because the numbers behind it are present.
    """
    payload, card = _template_payload(template, modeled_costs=modeled_costs)
    projected = {metric.key for metric in payload.metrics}
    for row in card["rows"]:
        if row["key"] in PROSE_METRIC_KEYS:
            assert projected & BENCHMARK_METRIC_KEYS, (
                f"{row['key']} was dropped and nothing typed replaced it, so the "
                "receipt names a benchmark it cannot show"
            )
            continue
        assert row["key"] in projected, f"{row['key']} vanished from the receipt"


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_a_receipt_never_names_a_benchmark_it_cannot_show(
    template: str, modeled_costs: bool
) -> None:
    payload, _ = _template_payload(template, modeled_costs=modeled_costs)
    assert payload.benchmark_symbol == "SPY"
    assert {metric.key for metric in payload.metrics} >= BENCHMARK_METRIC_KEYS


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_no_assumption_the_card_stated_is_lost(
    template: str, modeled_costs: bool
) -> None:
    """The card's sentences and the payload's facts, counted.

    The projection derives its facts from the run rather than reading the card, so
    the check that matters is that it never says less than the card did. It says
    more for a recurring run, where one sentence carries both an amount and a
    cadence.
    """
    payload, card = _template_payload(template, modeled_costs=modeled_costs)
    assert len(payload.assumptions) >= len(card["assumptions"])
    keys = {assumption.key for assumption in payload.assumptions}
    # The classes the generator always writes, whatever the template.
    assert "long_only" in keys
    assert "equal_weight" in keys
    assert keys & {"benchmark", "benchmark_same_modeled_costs"}
    assert keys & {"no_costs", "modeled_fee_bps"}
    if modeled_costs:
        assert {"modeled_fee_bps", "modeled_slippage_bps"} <= keys
        assert "benchmark_same_modeled_costs" in keys
    else:
        assert "no_costs" in keys
        assert "benchmark" in keys


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_the_strategy_a_receipt_shows_is_never_empty(
    template: str, modeled_costs: bool
) -> None:
    payload, _ = _template_payload(template, modeled_costs=modeled_costs)
    keys = [fact.key for fact in payload.strategy_facts]
    assert keys[0] == "strategy_type"
    assert payload.strategy_facts[0].value


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_no_typed_projection_comes_back_empty(
    template: str, modeled_costs: bool
) -> None:
    """The blunt version of the same question, asked of all three projections.

    An empty list is the shape a silent drop leaves behind, and it is the shape a
    cross-language comparison cannot see.
    """
    payload, _ = _template_payload(template, modeled_costs=modeled_costs)
    assert payload.metrics
    assert payload.assumptions
    assert payload.strategy_facts
    assert payload.date_range.start and payload.date_range.end


@pytest.mark.parametrize(("template", "modeled_costs"), TEMPLATE_CASES)
def test_the_whole_shape_space_is_language_invariant_too(
    template: str, modeled_costs: bool
) -> None:
    """The original invariant, now run over every template rather than one."""
    english, _ = _template_payload(
        template, modeled_costs=modeled_costs, language="en"
    )
    spanish, _ = _template_payload(
        template, modeled_costs=modeled_costs, language="es-419"
    )
    left = english.model_dump(mode="json")
    right = spanish.model_dump(mode="json")
    assert left.pop("content_language") == "en"
    assert right.pop("content_language") == "es-419"
    assert left == right


def test_an_unknown_metric_key_refuses_rather_than_disappearing() -> None:
    """A generator that grows a row must break loudly, not quietly say less."""
    card = {
        **build_result_card(),
        "rows": [
            *build_result_card()["rows"],
            {"key": "sortino_ratio", "label": "Sortino", "value": "1.8"},
        ],
    }
    with pytest.raises(PublicExcerptSourceError):
        _payload(
            artifact=build_artifact(payload=build_artifact_payload(result_card=card))
        )
