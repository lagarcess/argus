import ast
import inspect
import textwrap
from datetime import date

import argus.agent_runtime.strategy_contract as strategy_contract_module
from argus.agent_runtime.run_field_contract import (
    current_message_execution_context_tokens,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type,
    executable_strategy_type_from_extracted_fields,
    normalize_date_range_candidate,
    resolve_date_range,
    strategy_can_be_approved,
)
from argus.agent_runtime.turn_execution_evidence import (
    current_turn_has_material_execution_evidence,
)
from argus.nlp.natural_time import resolve_date_range_intent


def test_resolve_date_range_requires_canonical_state_for_month_name_ranges() -> None:
    resolved = resolve_date_range(
        "Jan 1 2010 to Dec 31 2020",
        today=date(2026, 5, 3),
    )

    assert resolved.used_default is True
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}


def test_lump_sum_strategy_alias_executes_as_buy_and_hold() -> None:
    assert (
        executable_strategy_type(StrategySummary(strategy_type="lump_sum_investment"))
        == "buy_and_hold"
    )


def test_locale_strategy_phrases_do_not_canonicalize_through_runtime_contract() -> None:
    assert canonical_strategy_type("compra y mantén") != "buy_and_hold"
    assert canonical_strategy_type("comprar_y_mantener") != "buy_and_hold"


def test_strategy_aliases_live_in_capability_registry_not_runtime_contract() -> None:
    tree = ast.parse(
        textwrap.dedent(
            inspect.getsource(strategy_contract_module.canonical_strategy_type)
        )
    )

    local_alias_dicts = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "aliases"
            for target in node.targets
        )
        and isinstance(node.value, ast.Dict)
    ]

    assert local_alias_dicts == []


def test_broad_investment_label_is_not_a_strategy_alias() -> None:
    assert (
        executable_strategy_type(StrategySummary(strategy_type="investment"))
        != "buy_and_hold"
    )


def test_month_span_with_shared_year_requires_canonical_intent() -> None:
    resolved = resolve_date_range(
        "march through october 2024",
        today=date(2026, 5, 3),
    )

    assert resolved.used_default is True

    canonical = resolve_date_range_intent(
        {
            "kind": "explicit_range",
            "start": "2024-03-01",
            "end": "2024-10-31",
            "evidence": "march through october 2024",
        },
        today=date(2026, 5, 3),
    )

    assert canonical is not None
    assert canonical.payload == {"start": "2024-03-01", "end": "2024-10-31"}


def test_current_message_contract_preserves_canonical_explicit_day_ranges() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "explicit_range",
            "start": "2020-03-01",
            "end": "2021-08-01",
            "evidence": "from March 1 2020 to August 1 2021",
        },
        today=date(2026, 5, 3),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2020-03-01", "end": "2021-08-01"}


def test_month_year_to_today_requires_canonical_intent() -> None:
    resolved = resolve_date_range(
        "January 2022 to today",
        today=date(2026, 5, 20),
    )

    assert resolved.used_default is True

    canonical = resolve_date_range_intent(
        {
            "kind": "since",
            "start": "2022-01-01",
            "end": "2026-05-20",
            "evidence": "January 2022 to today",
        },
        today=date(2026, 5, 20),
    )

    assert canonical is not None
    assert canonical.payload == {"start": "2022-01-01", "end": "2026-05-20"}


def test_relative_endpoint_tokens_require_canonical_endpoint_intent() -> None:
    resolved = resolve_date_range(
        {"start": "2026-01-01", "end": "yesterday"},
        today=date(2026, 6, 3),
    )

    assert resolved.used_default is True

    canonical = resolve_date_range_intent(
        {
            "kind": "endpoint_patch",
            "endpoint": "end",
            "anchor": "today",
            "day_offset": -1,
            "evidence": "yesterday",
        },
        today=date(2026, 6, 3),
    )

    assert canonical is not None
    assert canonical.payload == {"end": "2026-06-02"}


def test_resolve_date_range_accepts_structured_iso_month_endpoints() -> None:
    resolved = resolve_date_range(
        {"start": "2021-01", "end": "2024-01"},
        today=date(2026, 6, 3),
    )

    assert resolved.payload == {"start": "2021-01-01", "end": "2024-01-31"}
    assert resolved.display == "January 1, 2021 - January 31, 2024"
    assert resolved.used_default is False

    string_resolved = resolve_date_range(
        "2021-01 to 2024-01",
        today=date(2026, 6, 3),
    )
    assert string_resolved.payload == resolved.payload
    assert string_resolved.used_default is False


def test_compact_month_year_spans_require_nlp_boundary() -> None:
    resolved = resolve_date_range(
        "Jan 2021-Jan 2024",
        today=date(2026, 6, 3),
    )

    assert resolved.used_default is True


def test_bounded_compact_month_year_spans_require_nlp_boundary() -> None:
    resolved = resolve_date_range(
        "Jan 2021-Jan 2024",
        today=date(2026, 6, 3),
    )

    assert resolved.used_default is True


def test_calendar_year_intent_resolves_without_phrase_scan() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "calendar_year",
            "year": 2024,
            "evidence": "2024",
        },
        today=date(2026, 5, 3),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2024-01-01", "end": "2024-12-31"}


def test_multi_year_contract_uses_explicit_range_intent() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "explicit_range",
            "start": "2024-01-01",
            "end": "2025-12-31",
            "evidence": "2024 and 2025",
        },
        today=date(2026, 5, 3),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2024-01-01", "end": "2025-12-31"}


def test_current_year_so_far_uses_year_to_date_intent() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "year_to_date",
            "year": 2026,
            "evidence": "2026 so far",
        },
        today=date(2026, 6, 1),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2026-01-01", "end": "2026-06-01"}


def test_canonical_year_to_date_intent_resolves_without_phrase_scan() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "year_to_date",
            "year": 2026,
            "evidence": "2026 so far",
        },
        today=date(2026, 6, 1),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2026-01-01", "end": "2026-06-01"}


def test_raw_semantic_date_windows_require_canonical_intent() -> None:
    today = date(2026, 6, 1)

    for phrase in (
        "last month",
        "over 2024 and 2025",
        "in 2026 so far",
        "use the past year instead",
        "since 2021",
    ):
        resolved = resolve_date_range(phrase, today=today)
        assert resolved.used_default is True

    rolling = resolve_date_range_intent(
        {
            "kind": "rolling_window",
            "count": 1,
            "unit": "month",
            "anchor": "today",
        },
        today=today,
    )

    assert rolling is not None
    assert rolling.payload == {"start": "2026-05-01", "end": "2026-06-01"}


def test_spanish_month_year_spans_require_nlp_boundary() -> None:
    resolved = resolve_date_range(
        "desde enero de 2021 hasta diciembre de 2024",
        today=date(2026, 6, 1),
    )

    assert resolved.used_default is True


def test_canonical_endpoint_intent_resolves_relative_end_date_edit() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "endpoint_patch",
            "endpoint": "end",
            "anchor": "today",
            "day_offset": -1,
            "evidence": "yesterday",
        },
        today=date(2026, 6, 3),
    )

    assert resolved is not None
    assert resolved.payload == {"end": "2026-06-02"}


def test_dca_cadence_phrases_do_not_bypass_llm_interpretation() -> None:
    assert canonical_strategy_type(None, cadence="weekly") == "dca_accumulation"
    assert canonical_strategy_type(None, cadence="semanal") != "dca_accumulation"


def test_indicator_context_tokens_exclude_indicator_names_from_asset_grounding() -> None:
    tokens = current_message_execution_context_tokens(
        "Quiero GOOG con RSI desde 2025",
        strategy_type="indicator_threshold",
    )

    assert "rsi" in tokens
    assert "goog" not in tokens


def test_active_context_asset_mentions_need_requested_field_context() -> None:
    assert current_turn_has_material_execution_evidence(
        "QQQ",
        has_provider_asset_mention=True,
        active_strategy_context=True,
        requested_field="comparison_baseline",
    )
    assert not current_turn_has_material_execution_evidence(
        "what is QQQ?",
        has_provider_asset_mention=True,
        active_strategy_context=True,
        requested_field=None,
    )


def test_normalize_date_range_preserves_structured_month_name_ranges() -> None:
    normalized = normalize_date_range_candidate(
        {"start": "2020-02-07", "end": "2024-02-07"},
        today=date(2026, 5, 3),
    )

    assert normalized == {"start": "2020-02-07", "end": "2024-02-07"}


def test_raw_phrase_no_longer_overrides_structured_date_range() -> None:
    normalized = normalize_date_range_candidate(
        "past year",
        raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
        today=date(2026, 5, 3),
    )

    assert normalized == "past year"


def test_relative_period_intents_resolve_without_phrase_scan() -> None:
    cases = {
        ("month", 1): ("2026-04-03", "2026-05-03"),
        ("week", 1): ("2026-04-26", "2026-05-03"),
        ("quarter", 1): ("2026-02-03", "2026-05-03"),
    }

    for (unit, count), (start, end) in cases.items():
        resolved = resolve_date_range_intent(
            {
                "kind": "rolling_window",
                "unit": unit,
                "count": count,
                "anchor": "today",
            },
            today=date(2026, 5, 3),
        )

        assert resolved is not None
        assert resolved.payload == {"start": start, "end": end}


def test_embedded_raw_relative_periods_default_without_intent() -> None:
    resolved = resolve_date_range(
        "use the past year instead",
        today=date(2026, 5, 3),
    )

    assert resolved.label == "past year"
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}
    assert resolved.used_default is True


def test_resolve_date_range_exposes_default_fallback() -> None:
    resolved = resolve_date_range("the previous market mood", today=date(2026, 5, 3))

    assert resolved.label == "past year"
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}
    assert resolved.used_default is True


def test_dca_strategy_requires_explicit_recurring_amount_for_approval() -> None:
    strategy = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Tesla every month.",
        asset_universe=["TSLA"],
        date_range="past year",
        cadence="monthly",
    )

    assert strategy_can_be_approved(strategy) is False

    strategy.capital_amount = 500

    assert strategy_can_be_approved(strategy) is True


def test_extracted_fields_resolve_indicator_threshold_from_registry() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "indicator": "sma",
            "entry_threshold": 450,
            "exit_threshold": 500,
        }
    )

    assert resolved == "indicator_threshold"


def test_extracted_fields_do_not_force_unknown_strategy_contract() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "strategy_type": "sentiment_strategy",
            "entry_logic": "news sentiment turns positive",
            "asset_universe": ["AAPL"],
            "date_range": "past year",
        }
    )

    assert resolved is None


def test_extracted_fields_do_not_accept_unknown_rule_spec_as_signal_strategy() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "strategy_type": "signal_strategy",
            "rule_spec": {"type": "news_sentiment", "sentiment_direction": "positive"},
            "asset_universe": ["AAPL"],
            "date_range": "past year",
        }
    )

    assert resolved is None
