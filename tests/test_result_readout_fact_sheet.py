"""Readout facts retain the engine's units, grain and available evidence."""

import json
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

import pytest
from argus.domain.result_readout_grounding import stored_readout_facts
from faker import Faker

FIXTURES = (
    Path(__file__).parents[1]
    / "tests/fixtures/result_readouts/recorded_runs.json"
)
CASES = {case["id"]: case["run"] for case in json.loads(FIXTURES.read_text())["cases"]}


def projection(run):
    run = deepcopy(run)
    # Capture the genuine raw boundary for mutations before testing this owner.
    with patch(
        "argus.domain.result_readout_grounding.build_labeled_fact_sheet",
        side_effect=lambda raw: raw,
    ):
        return stored_readout_facts(
            metrics=run["metrics"],
            config_snapshot=run["config_snapshot"],
            symbols=run["symbols"],
            benchmark_symbol=run["benchmark_symbol"],
            date_range=run["conversation_result_card"]["date_range"],
            chart=run.get("chart"),
        )


def sheet(raw):
    try:
        module = import_module("argus.domain.result_readout_fact_sheet")
    except ModuleNotFoundError:
        pytest.fail("The shared labeled readout fact-sheet owner does not exist")
    return module.build_labeled_fact_sheet(raw)


def resolve(value, key):
    return import_module("argus.domain.result_readout_fact_sheet").resolve_readout_fact(
        value, key
    )


@pytest.mark.parametrize("case_id", CASES)
def test_stored_metrics_keep_units_scope_and_nulls(case_id):
    run = CASES[case_id]
    result = sheet(projection(run))
    rows = result["facts"]
    aggregate = run["metrics"]["aggregate"]
    assert (
        rows["portfolio.executed_fills"]["value"]
        == aggregate["efficiency"]["total_trades"]
    )
    assert rows["portfolio.executed_fills"]["unit"] == "count"
    assert "purchases and sales" in rows["portfolio.executed_fills"]["meaning"].lower()
    assert (
        rows["portfolio.annualized_volatility"]["value"]
        == aggregate["risk"]["volatility_pct"]
    )
    assert (
        rows["portfolio.annualized_volatility"]["basis"]
        == "annualized_flow_adjusted_return_dispersion"
    )
    assert rows["portfolio.completed_trades"]["value"] is None
    assert (
        rows["portfolio.profit_factor"]["value"]
        == aggregate["efficiency"]["profit_factor"]
    )
    for symbol in run["symbols"]:
        assert rows[f"symbol.{symbol}.executed_fills"]["scope"] == f"symbol:{symbol}"
    assert "metrics" not in result


def test_dca_seed_contribution_and_money_weighted_return_are_distinct():
    run = CASES["dca_costs_recorded"]
    rows = sheet(projection(run))["facts"]
    plan = run["config_snapshot"]["engine_config"]["dca_capital"]
    assert rows["configuration.starting_capital"]["value"] == plan["starting_capital"]
    assert rows["configuration.recurring_contribution"]["value"] == plan["contribution"]
    assert rows["portfolio.annualized_return"]["basis"] == "money_weighted_annual_return"
    assert rows["portfolio.total_return"]["basis"] == "return_on_contributed_money"
    assert rows["portfolio.drawdown.peak_equity"]["value"] is None
    assert "flow" in rows["portfolio.drawdown.peak_equity"]["provenance"]["reason"]
    assert rows["portfolio.ending_equity"]["value"] == run["chart"]["series"][-1]["value"]


def test_chart_points_have_individual_typed_references_without_duplicate_tree():
    run = CASES["docn_buyhold_recorded"]
    result = sheet(projection(run))
    point = run["chart"]["series"][-1]
    index = len(run["chart"]["series"]) - 1
    value = resolve(result, f"chart.portfolio_equity.{index}.value")
    date = resolve(result, f"chart.portfolio_equity.{index}.time")
    assert value["value"] == point["value"]
    assert value["unit"] == "currency" and value["currency"] == "USD"
    assert date["value"] == point["time"] and date["unit"] == "timestamp"
    assert "nominal" in value["meaning"]
    assert resolve(result, "chart.portfolio_equity.-1.value") is None
    assert resolve(result, f"chart.portfolio_equity.{index + 1}.value") is None
    assert resolve(result, "chart.portfolio_equity.0.missing") is None


def test_fixed_capital_drawdown_uses_prior_peak_not_global_extrema():
    result = sheet(projection(CASES["docn_buyhold_recorded"]))
    rows = result["facts"]
    assert rows["portfolio.drawdown.peak_equity"]["value"] == pytest.approx(1747.10)
    assert rows["portfolio.drawdown.trough_equity"]["value"] == pytest.approx(963.34)
    assert rows["portfolio.drawdown.peak_date"]["value"].startswith("2025-02-18")
    assert rows["portfolio.drawdown.trough_date"]["value"].startswith("2025-08-01")
    assert (
        rows["portfolio.peak_equity"]["value"]
        != rows["portfolio.drawdown.peak_equity"]["value"]
    )


@pytest.mark.parametrize(
    "defect",
    [
        "missing_point",
        "duplicate_time",
        "reverse",
        "ratio_only",
        "wrong_metric",
        "sampled",
        "multiple_symbols",
    ],
)
def test_drawdown_does_not_claim_full_path_from_incomplete_evidence(defect):
    raw = projection(deepcopy(CASES["docn_buyhold_recorded"]))
    if defect == "missing_point":
        raw["chart"]["series"].pop()
    elif defect == "duplicate_time":
        raw["chart"]["series"][1]["time"] = raw["chart"]["series"][0]["time"]
    elif defect == "reverse":
        raw["chart"]["series"].reverse()
    elif defect == "ratio_only":
        raw["metrics"]["aggregate"]["performance"]["benchmark_coverage"].pop(
            "target_points"
        )
    elif defect == "wrong_metric":
        raw["metrics"]["aggregate"]["risk"]["max_drawdown_pct"] = -99
    elif defect == "sampled":
        raw["chart"]["sampled"] = True
    else:
        raw["symbols"].append("SPY")
    assert sheet(raw)["facts"]["portfolio.drawdown.peak_equity"]["value"] is None


def test_unknown_metric_preserved_without_inventing_definition_or_mutating_input():
    raw = projection(deepcopy(CASES["rsi14_recorded"]))
    value = Faker().pyfloat(min_value=2, max_value=9, right_digits=3)
    raw["metrics"]["aggregate"]["risk"]["new_measure"] = value
    before = deepcopy(raw)
    result = sheet(raw)
    row = result["facts"]["portfolio.metrics.risk.new_measure"]
    assert row["value"] == value and row["unit"] == "unknown"
    assert "definition unavailable" in row["meaning"].lower()
    assert row["provenance"]["path"] == "metrics.aggregate.risk.new_measure"
    assert raw == before


def test_chart_absence_does_not_invent_ending_equity_or_drawdown_dates():
    raw = projection(CASES["docn_buyhold_recorded"])
    raw.pop("chart")
    rows = sheet(raw)["facts"]
    assert rows["portfolio.ending_equity"]["value"] is None
    assert rows["portfolio.drawdown.peak_date"]["value"] is None
    assert (
        rows["portfolio.drawdown_illustration"]["basis"]
        == "starting_capital_illustration"
    )


def test_presentation_conversions_are_declared_only_for_known_fraction_and_signed_facts():
    rows = sheet(projection(CASES["rsi14_recorded"]))["facts"]
    assert rows["portfolio.win_rate"]["presentation"] == ["fraction_as_percent"]
    assert rows["portfolio.observed_ratio"]["presentation"] == ["fraction_as_percent"]
    assert rows["portfolio.max_drawdown"]["presentation"] == ["absolute_magnitude"]
    assert rows["portfolio.benchmark_gap"]["presentation"] == ["absolute_magnitude"]
    assert "presentation" not in rows["portfolio.executed_fills"]


def test_additional_root_metrics_are_preserved_and_unknown_count_is_not_zero():
    raw = projection(CASES["docn_buyhold_recorded"])
    raw["metrics"]["engine_extension"] = {"measurement": 7.25}
    rows = sheet(raw)["facts"]
    assert rows["metrics.engine_extension.measurement"]["value"] == 7.25
    assert rows["portfolio.completed_trades"]["value"] is None


def test_total_contributed_money_uses_stored_ending_equity_and_profit_identity():
    run = CASES["dca_costs_recorded"]
    result = sheet(projection(run))
    rows = result["facts"]
    expected = (
        run["chart"]["series"][-1]["value"]
        - run["metrics"]["aggregate"]["performance"]["profit"]
    )
    assert rows["portfolio.invested_capital"]["value"] == pytest.approx(expected)
    assert rows["portfolio.invested_capital"]["basis"] == "total_contributed_money"
    assert rows["portfolio.invested_capital"]["provenance"]["inputs"] == [
        "portfolio.ending_equity",
        "portfolio.profit",
    ]


@pytest.mark.parametrize(
    "defect", ["wrong_window", "currency_missing", "series_sampled", "nonfinite"]
)
def test_drawdown_requires_window_currency_and_series_integrity(defect):
    raw = projection(deepcopy(CASES["docn_buyhold_recorded"]))
    if defect == "wrong_window":
        raw["configuration"]["end_date"] = "2024-01-01"
    elif defect == "currency_missing":
        raw["chart"].pop("currency")
    elif defect == "series_sampled":
        raw["chart"]["series_summary"] = {"sampled": True}
    else:
        raw["chart"]["series"][1]["value"] = float("nan")
    assert sheet(raw)["facts"]["portfolio.drawdown.peak_equity"]["value"] is None


def test_explicit_stored_completed_count_is_not_replaced_with_unavailable():
    raw = projection(CASES["rsi14_recorded"])
    raw["metrics"]["aggregate"]["efficiency"]["completed_trades"] = 2
    assert sheet(raw)["facts"]["portfolio.completed_trades"]["value"] == 2


def test_capital_aliases_preserve_their_actual_source_paths():
    raw = projection(CASES["dca_costs_recorded"])
    rows = sheet(raw)["facts"]
    contribution = rows["configuration.recurring_contribution"]
    assert contribution["provenance"]["path"] == "configuration.dca_capital.contribution"
    assert "configuration.capital_amount" in contribution["provenance"]["also_stored_at"]


def test_missing_terminal_point_cannot_be_called_the_ending_equity():
    raw = projection(CASES["docn_buyhold_recorded"])
    raw["chart"]["series"].pop()
    assert sheet(raw)["facts"]["portfolio.ending_equity"]["value"] is None


def test_legacy_annual_volatility_uses_the_same_canonical_definition():
    raw = projection(CASES["rsi14_recorded"])
    risk = raw["metrics"]["aggregate"]["risk"]
    expected = sheet(raw)["facts"]["portfolio.annualized_volatility"]
    risk["volatility_annual_pct"] = risk.pop("volatility_pct")
    actual = sheet(raw)["facts"]["portfolio.annualized_volatility"]
    assert {key: actual[key] for key in ("value", "unit", "meaning", "basis")} == {
        key: expected[key] for key in ("value", "unit", "meaning", "basis")
    }
    assert actual["provenance"]["path"].endswith("volatility_annual_pct")


@pytest.mark.parametrize("case_id", CASES)
def test_legacy_return_basis_derives_from_the_executed_template(case_id):
    raw = projection(CASES[case_id])
    expected = sheet(raw)["facts"]
    for group in [raw["metrics"]["aggregate"], *raw["metrics"]["by_symbol"].values()]:
        group["performance"].pop("return_basis")
    rows = sheet(raw)["facts"]
    for key in ("portfolio.total_return", "portfolio.annualized_return"):
        assert rows[key]["basis"] == expected[key]["basis"]


def test_grouped_markers_retain_every_point_and_original_reference_key():
    run = CASES["dca_costs_recorded"]
    result = sheet(projection(run))
    assert result["series"]["execution_markers"]["points"] == run["chart"]["markers"]
    assert not any(key.startswith("chart.markers.") for key in result["facts"])
    for index, marker in enumerate(run["chart"]["markers"]):
        row = resolve(result, f"chart.markers.{index}.time")
        assert row["value"] == marker["time"] and row["unit"] == "timestamp"
        assert "group" in row["meaning"]
        for symbol_index, symbol in enumerate(marker["symbols"]):
            assert (
                resolve(result, f"chart.markers.{index}.symbols.{symbol_index}")["value"]
                == symbol
            )


def test_grouped_nonnumeric_context_retains_original_reference_and_meaning():
    raw = projection(CASES["rsi14_recorded"])
    raw["configuration"]["extra_context"] = {"label": "Measured fixture context"}
    result = sheet(raw)
    key = "configuration.extra_context.label"
    assert key not in result["facts"]
    row = resolve(result, key)
    assert row["value"] == raw["configuration"]["extra_context"]["label"]
    assert row["unit"] == "text" and row["scope"] == "execution_configuration"
    assert "definition unavailable" in row["meaning"].lower()


def test_compaction_never_removes_equity_points_or_numeric_configuration():
    raw = projection(CASES["rsi14_recorded"])
    raw["configuration"]["unrecognized_setting"] = 17.42
    result = sheet(raw)
    assert result["series"]["portfolio_equity"]["points"] == raw["chart"]["series"]
    assert resolve(result, "configuration.unrecognized_setting")["value"] == 17.42


def test_chart_base_value_is_post_execution_equity_not_initial_funding():
    run = CASES["dca_costs_recorded"]
    result = sheet(projection(run))
    row = resolve(result, "chart.base_value")
    assert row["value"] == run["chart"]["series"][0]["value"]
    assert row["value"] != result["facts"]["configuration.starting_capital"]["value"]
    assert row["unit"] == "currency" and row["currency"] == "USD"
    assert row["basis"] == "first_nominal_equity_close"
    assert "first" in row["meaning"].lower() and "post-execution" in row["meaning"]
    assert "contributions" in row["meaning"] and "initial" in row["meaning"]


@pytest.mark.parametrize("side", ["entry", "exit"])
def test_rsi_configuration_numbers_keep_typed_indicator_and_rule_context(side):
    raw = projection(CASES["rsi14_recorded"])
    result = sheet(raw)
    rule = raw["configuration"]["resolved_strategy"][f"{side}_rule"]
    for prefix in ("", "parameters."):
        condition_prefix = f"{prefix}rule_spec.{side}.conditions.0."
        for suffix in (f"{prefix}{side}_threshold", f"{condition_prefix}right"):
            row = resolve(result, f"configuration.{suffix}")
            assert row["value"] == rule["threshold"]
            assert row["unit"] == "indicator_points"
            assert "RSI" in row["meaning"] and side in row["meaning"]
            assert ("at or below" if side == "entry" else "at or above") in row["meaning"]
            assert row["basis"] == "configured_indicator_threshold"
        period = resolve(result, f"configuration.{condition_prefix}left.period")
        assert period["value"] == rule["period"] and period["unit"] == "count"
        assert "RSI" in period["meaning"] and side in period["meaning"]
        assert period["basis"] == "indicator_observation_window"
    for name, unit in (("period", "count"), ("threshold", "indicator_points")):
        key = f"configuration.resolved_strategy.{side}_rule.{name}"
        row = resolve(result, key)
        assert row["value"] == rule[name] and row["unit"] == unit
        assert "RSI" in row["meaning"] and side in row["meaning"]


@pytest.mark.parametrize("defect", ["unknown_indicator", "unknown_operator", "unrelated"])
def test_unrecognized_configuration_never_borrows_typed_rule_meaning(defect):
    raw = projection(CASES["rsi14_recorded"])
    condition = raw["configuration"]["rule_spec"]["entry"]["conditions"][0]
    if defect == "unknown_indicator":
        condition["left"]["key"] = "unrecognized"
    elif defect == "unknown_operator":
        condition["operator"] = "unrecognized"
    else:
        raw["configuration"]["unrelated"] = {"period": 14, "right": 30.0}
    result = sheet(raw)
    key = (
        "configuration.unrelated.right"
        if defect == "unrelated"
        else "configuration.rule_spec.entry.conditions.0.right"
    )
    row = resolve(result, key)
    assert row["value"] == condition["right"] and row["unit"] == "unknown"
    assert "definition unavailable" in row["meaning"]


@pytest.mark.parametrize("template", [None, "unrecognized"])
def test_unknown_funding_never_claims_compounded_return_or_dated_drawdown(template):
    raw = projection(CASES["docn_buyhold_recorded"])
    raw["metrics"]["aggregate"]["performance"].pop("return_basis")
    if template is None:
        raw["configuration"].pop("template")
    else:
        raw["configuration"]["template"] = template
    rows = sheet(raw)["facts"]
    assert rows["portfolio.annualized_return"]["basis"] == "return_basis_unavailable"
    assert rows["portfolio.total_return"]["basis"] == "return_basis_unavailable"
    assert rows["portfolio.drawdown.dollar_loss"]["value"] is None
    assert (
        "funding basis" in rows["portfolio.drawdown.dollar_loss"]["provenance"]["reason"]
    )


def test_explicit_funding_basis_wins_over_unrecognized_template():
    raw = projection(CASES["docn_buyhold_recorded"])
    expected = sheet(raw)["facts"]
    raw["configuration"]["template"] = "unrecognized"
    rows = sheet(raw)["facts"]
    assert (
        rows["portfolio.annualized_return"]["basis"]
        == expected["portfolio.annualized_return"]["basis"]
    )
    assert (
        rows["portfolio.drawdown.dollar_loss"]["value"]
        == expected["portfolio.drawdown.dollar_loss"]["value"]
    )


def test_legacy_comparison_gap_keeps_canonical_magnitude_presentation():
    raw = projection(CASES["rsi14_recorded"])
    expected = sheet(raw)["facts"]["portfolio.benchmark_gap"]
    raw["metrics"] = {}
    row = sheet(raw)["facts"]["portfolio.benchmark_gap"]
    assert row["value"] == expected["value"]
    assert row["presentation"] == expected["presentation"]
