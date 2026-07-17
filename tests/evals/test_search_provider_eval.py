from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from tests.evals.search_provider_eval import (
    DEFAULT_MANIFEST_PATH,
    evaluate_manifest,
    load_search_eval_manifest,
    normalize_case,
    write_decision_evidence,
)


def test_manifest_is_bounded_provider_neutral_and_offline() -> None:
    manifest = load_search_eval_manifest()

    assert set(manifest.providers) == {
        "openrouter_web_search",
        "perplexity_direct",
    }
    assert set(manifest.rubric.criteria) == {
        "call_count",
        "citation_integrity",
        "cost",
        "freshness",
        "injection_resistance",
        "latency",
        "outage_behavior",
        "relevance",
        "result_count",
        "timeout",
    }
    assert manifest.rubric.max_search_calls == 1
    assert manifest.rubric.max_results == 5
    assert manifest.rubric.timeout_ms == 3000
    assert manifest.evidence_scope == ("synthetic_provider_shaped_and_official_docs")
    assert manifest.live_calls_made == 0
    assert DEFAULT_MANIFEST_PATH.name == "search_provider_eval_manifest.json"


def test_manifest_covers_search_controls_and_required_risk_cases() -> None:
    manifest = load_search_eval_manifest()
    case_kinds = {case.kind for case in manifest.cases}
    control_cases = [case for case in manifest.cases if case.kind == "control"]

    assert case_kinds == {
        "category_discovery",
        "control",
        "injection",
        "outage",
        "peer_discovery",
    }
    assert {case.language for case in manifest.cases} >= {"en", "es-419"}
    assert {case.expected_asset_class for case in manifest.cases} >= {
        "crypto",
        "equity",
    }
    assert {case.id for case in control_cases} == {
        "direct_supported_backtest_zero_search",
        "generic_try_next_zero_search",
    }
    assert all(case.expected_search_calls == 0 for case in control_cases)
    assert all(case.timeout_ms == 0 for case in control_cases)
    assert all(
        case.timeout_ms == manifest.rubric.timeout_ms
        for case in manifest.cases
        if case.provider is not None
    )
    assert all(
        profile.comparison_configuration["timeout_ms"] == manifest.rubric.timeout_ms
        for profile in manifest.providers.values()
    )


def test_provider_shapes_normalize_to_bounded_untrusted_sources() -> None:
    manifest = load_search_eval_manifest()

    for case in manifest.cases:
        evidence = normalize_case(case, rubric=manifest.rubric)
        if evidence.search_calls is None:
            assert case.provider == "openrouter_web_search"
        else:
            assert evidence.search_calls <= manifest.rubric.max_search_calls
        assert len(evidence.sources) <= manifest.rubric.max_results
        assert all(source.trust == "untrusted" for source in evidence.sources)
        assert all(source.url.startswith("https://") for source in evidence.sources)
        assert all(source.retrieved_at for source in evidence.sources)


def test_injected_source_content_cannot_change_eval_policy() -> None:
    manifest = load_search_eval_manifest()
    injection_cases = [case for case in manifest.cases if case.kind == "injection"]

    assert {case.provider for case in injection_cases} == {
        "openrouter_web_search",
        "perplexity_direct",
    }
    for case in injection_cases:
        evidence = normalize_case(case, rubric=manifest.rubric)
        assert evidence.status == "succeeded"
        assert evidence.policy_effects == ()
        assert evidence.runnable_candidates == ()
        assert all(source.trust == "untrusted" for source in evidence.sources)


def test_outage_cases_preserve_context_with_honest_fallback() -> None:
    manifest = load_search_eval_manifest()
    outage_cases = [case for case in manifest.cases if case.kind == "outage"]

    assert {case.provider for case in outage_cases} == {
        "openrouter_web_search",
        "perplexity_direct",
    }
    for case in outage_cases:
        evidence = normalize_case(case, rubric=manifest.rubric)
        assert evidence.status == "outage"
        assert evidence.sources == ()
        assert evidence.fallback_code == "search_unavailable_preserve_context"
        assert evidence.prior_result_context == case.payload["prior_result_context"]


def test_missing_or_conflicting_provider_evidence_is_not_fabricated() -> None:
    manifest = load_search_eval_manifest()
    openrouter_case = next(
        case for case in manifest.cases if case.id == "openrouter_equity_category_en"
    )

    missing_usage_payload = deepcopy(openrouter_case.payload)
    missing_usage_payload.pop("usage")
    missing_usage_case = replace(openrouter_case, payload=missing_usage_payload)
    missing_usage_evidence = normalize_case(
        missing_usage_case,
        rubric=manifest.rubric,
    )
    assert missing_usage_evidence.search_calls is None
    assert missing_usage_evidence.cost_usd is None

    high_cost_payload = deepcopy(openrouter_case.payload)
    high_cost_payload["usage"]["cost"] = 999
    high_cost_case = replace(openrouter_case, payload=high_cost_payload)
    high_cost_evidence = normalize_case(high_cost_case, rubric=manifest.rubric)
    assert high_cost_evidence.cost_usd == 999


def test_source_freshness_requires_source_dates_when_schema_supports_them() -> None:
    manifest = load_search_eval_manifest()
    direct_case = next(
        case for case in manifest.cases if case.id == "perplexity_equity_category_en"
    )
    payload_without_dates = deepcopy(direct_case.payload)
    for result in payload_without_dates["results"]:
        result.pop("date", None)
        result.pop("last_updated", None)
    case_without_dates = replace(direct_case, payload=payload_without_dates)
    mutated_manifest = replace(manifest, cases=(case_without_dates,))

    result = evaluate_manifest(mutated_manifest)["fixture_contract"]["results"][0]

    assert result["checks"]["freshness"] is False


def test_outage_preservation_requires_explicit_prior_context() -> None:
    manifest = load_search_eval_manifest()
    outage_case = next(case for case in manifest.cases if case.id == "perplexity_outage")
    payload_without_context = deepcopy(outage_case.payload)
    payload_without_context.pop("prior_result_context")

    evidence = normalize_case(
        replace(outage_case, payload=payload_without_context),
        rubric=manifest.rubric,
    )

    assert evidence.prior_result_context is None


def test_report_defers_activation_without_real_quality_or_latency_evidence() -> None:
    report = evaluate_manifest(load_search_eval_manifest())

    assert report["fixture_contract"]["failed"] == 0
    expected_checks = {
        "call_count",
        "citation_integrity",
        "cost",
        "freshness",
        "injection_resistance",
        "latency",
        "outage_behavior",
        "relevance",
        "result_count",
        "timeout",
    }
    for result in report["fixture_contract"]["results"]:
        assert set(result["checks"]) == expected_checks
        assert False not in result["checks"].values()
        assert set(result["observed"]) == {
            "citation_count",
            "configured_timeout_ms",
            "cost_usd",
            "evidence_kind",
            "fallback_code",
            "latency_ms",
            "prior_result_context_present",
            "result_count",
            "search_calls",
            "source_dates_present",
        }
        if result["provider"] == "openrouter_web_search":
            assert result["checks"]["call_count"] is None
        else:
            assert result["checks"]["call_count"] is True
    assert report["live_calls_made"] == 0
    assert report["activation_ready"] is False
    assert report["recommendation"] == "defer"
    assert report["preferred_next_probe"] == "perplexity_direct"
    assert set(report["remaining_gates"]) == {
        "#241 typed asset discovery route integrated",
        "explicit founder activation",
        "locked OpenRouter model and token budget",
        "real citation and relevance evidence",
        "real outage context-preservation evidence",
        "real prompt-injection resistance evidence",
        "real provider latency evidence",
    }
    assert (
        report["provider_comparison"]["perplexity_direct"]["source_date_metadata"]
        == "documented"
    )
    assert (
        report["provider_comparison"]["openrouter_web_search"]["source_date_metadata"]
        == "not_guaranteed_by_annotation_schema"
    )
    assert (
        report["provider_comparison"]["openrouter_web_search"]["cost_shape"]
        == "search_fee_plus_llm_tokens"
    )
    assert (
        report["provider_comparison"]["perplexity_direct"]["call_shape"]
        == "one_request_per_probe"
    )
    assert (
        report["provider_comparison"]["openrouter_web_search"]["call_shape"]
        == "model_decides_zero_to_many_calls"
    )
    assert (
        report["provider_comparison"]["openrouter_web_search"][
            "comparison_configuration"
        ]["model_selection_status"]
        == "unresolved_founder_gate"
    )
    injection_results = [
        result
        for result in report["fixture_contract"]["results"]
        if result["kind"] == "injection"
    ]
    assert all(
        result["checks"]["injection_resistance"] is None for result in injection_results
    )
    outage_results = [
        result
        for result in report["fixture_contract"]["results"]
        if result["kind"] == "outage"
    ]
    assert all(result["checks"]["outage_behavior"] is None for result in outage_results)
    assert set(report["criterion_comparison"]) == {
        "citation_integrity",
        "cost",
        "freshness",
        "injection_resistance",
        "latency",
        "outage_behavior",
        "relevance",
    }
    assert "README" in report["rollback_boundary"]


def test_decision_evidence_writer_stays_in_nonversioned_temp(
    tmp_path: Path,
) -> None:
    report = evaluate_manifest(load_search_eval_manifest())
    target = tmp_path / "search-provider-evaluation.json"

    written = write_decision_evidence(report, target)

    assert written == target
    payload = target.read_text(encoding="utf-8")
    assert '"recommendation": "defer"' in payload
    assert '"live_calls_made": 0' in payload
