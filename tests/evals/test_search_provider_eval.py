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
        "source_date_metadata",
        "timeout",
    }
    assert manifest.rubric.max_search_calls == 1
    assert manifest.rubric.max_results == 5
    assert manifest.rubric.timeout_ms == 3000
    assert manifest.evidence_scope == (
        "authored_synthetic_fixtures_and_official_documentation"
    )
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
            assert case.provider != "openrouter_web_search" or "usage" not in case.payload
        else:
            assert case.provider == "openrouter_web_search"
            assert evidence.search_calls <= manifest.rubric.max_search_calls
        assert len(evidence.sources) <= manifest.rubric.max_results
        assert all(source.trust == "untrusted" for source in evidence.sources)
        assert all(source.url.startswith("https://") for source in evidence.sources)
        assert all(source.retrieved_at for source in evidence.sources)


def test_injection_fixtures_mark_sources_untrusted_without_claiming_policy() -> None:
    manifest = load_search_eval_manifest()
    injection_cases = [case for case in manifest.cases if case.kind == "injection"]

    assert {case.provider for case in injection_cases} == {
        "openrouter_web_search",
        "perplexity_direct",
    }
    for case in injection_cases:
        evidence = normalize_case(case, rubric=manifest.rubric)
        assert evidence.status == "fixture_response"
        assert evidence.policy_effects is None
        assert evidence.runnable_candidates is None
        assert all(source.trust == "untrusted" for source in evidence.sources)


def test_relabeling_synthetic_fixture_does_not_create_empirical_evidence() -> None:
    manifest = load_search_eval_manifest()
    injection_case = next(
        case for case in manifest.cases if case.id == "perplexity_injection_source"
    )
    observed_case = replace(
        injection_case,
        evidence_kind="real_provider_observation",
    )

    result = evaluate_manifest(replace(manifest, cases=(observed_case,)))[
        "fixture_validation"
    ]["results"][0]

    assert all(value is None for value in result["empirical_checks"].values())
    assert "injection_resistance" in result["unproven_empirical_checks"]
    assert result["status"] == "unproven"


def test_missing_runtime_observations_are_not_manufactured() -> None:
    manifest = load_search_eval_manifest()
    control_case = next(
        case
        for case in manifest.cases
        if case.id == "direct_supported_backtest_zero_search"
    )
    injection_case = next(
        case for case in manifest.cases if case.id == "perplexity_injection_source"
    )
    outage_case = next(case for case in manifest.cases if case.id == "perplexity_outage")

    control_evidence = normalize_case(control_case, rubric=manifest.rubric)
    injection_evidence = normalize_case(injection_case, rubric=manifest.rubric)
    outage_evidence = normalize_case(outage_case, rubric=manifest.rubric)

    assert control_evidence.search_calls is None
    assert injection_evidence.policy_effects is None
    assert injection_evidence.runnable_candidates is None
    assert outage_evidence.fallback_code is None
    assert outage_evidence.prior_result_context is None

    partial_payload = deepcopy(injection_case.payload)
    partial_payload["runtime_observation"] = {"policy_effects": []}
    partial_case = replace(injection_case, payload=partial_payload)
    partial_result = evaluate_manifest(replace(manifest, cases=(partial_case,)))[
        "fixture_validation"
    ]["results"][0]

    assert partial_result["fixture_checks"]["declared_runtime_effects_safe"] is None
    assert partial_result["empirical_checks"]["injection_resistance"] is None


def test_declared_malicious_runtime_effects_are_retained_and_fail_closed() -> None:
    manifest = load_search_eval_manifest()
    injection_case = next(
        case for case in manifest.cases if case.id == "perplexity_injection_source"
    )
    payload = deepcopy(injection_case.payload)
    payload["runtime_observation"] = {
        "policy_effects": ["policy_overridden"],
        "runnable_candidates": ["UNVALIDATED"],
    }
    malicious_case = replace(injection_case, payload=payload)

    evidence = normalize_case(malicious_case, rubric=manifest.rubric)
    report = evaluate_manifest(replace(manifest, cases=(malicious_case,)))
    result = report["fixture_validation"]["results"][0]

    assert evidence.policy_effects == ("policy_overridden",)
    assert evidence.runnable_candidates == ("UNVALIDATED",)
    assert result["fixture_checks"]["declared_runtime_effects_safe"] is False
    assert result["status"] == "fixture_failed"
    assert all(value is None for value in result["empirical_checks"].values())
    assert report["empirical_evidence"]["failed"] == 0
    assert report["empirical_evidence"]["unproven"] == 1


def test_controls_and_outages_are_fixture_scenarios_not_runtime_proof() -> None:
    report = evaluate_manifest(load_search_eval_manifest())
    results = report["fixture_validation"]["results"]
    control_results = [result for result in results if result["kind"] == "control"]
    outage_results = [result for result in results if result["kind"] == "outage"]

    assert control_results
    assert outage_results
    assert all("observed" not in result for result in control_results + outage_results)
    assert all(
        result["fixture_checks"]["control_declares_zero_search"] is True
        for result in control_results
    )
    assert all(
        result["fixture_checks"]["outage_fixture_has_context_precondition"] is True
        for result in outage_results
    )
    assert all(
        result["empirical_checks"]["call_count"] is None for result in control_results
    )
    assert all(
        result["empirical_checks"]["outage_behavior"] is None for result in outage_results
    )


def test_provider_selection_is_only_a_documentation_based_probe_hypothesis() -> None:
    report = evaluate_manifest(load_search_eval_manifest())

    assert "provider_comparison" not in report
    assert "criterion_comparison" not in report
    assert "preferred_next_probe" not in report
    assert report["next_probe_hypothesis"] == {
        "provider": "perplexity_direct",
        "basis": "official_documentation_only",
        "status": "not_empirically_compared",
    }
    assert report["recommendation_basis"] == "missing_empirical_evidence"


def test_outage_fixtures_define_context_preconditions_without_claiming_fallback() -> None:
    manifest = load_search_eval_manifest()
    outage_cases = [case for case in manifest.cases if case.kind == "outage"]

    assert {case.provider for case in outage_cases} == {
        "openrouter_web_search",
        "perplexity_direct",
    }
    for case in outage_cases:
        evidence = normalize_case(case, rubric=manifest.rubric)
        result = evaluate_manifest(replace(manifest, cases=(case,)))[
            "fixture_validation"
        ]["results"][0]

        assert evidence.status == "fixture_outage"
        assert evidence.sources == ()
        assert evidence.fallback_code is None
        assert evidence.prior_result_context is None
        assert result["fixture_checks"]["outage_fixture_has_context_precondition"] is True
        assert result["empirical_checks"]["outage_behavior"] is None


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
    high_cost_result = evaluate_manifest(replace(manifest, cases=(high_cost_case,)))[
        "fixture_validation"
    ]["results"][0]
    assert high_cost_result["status"] == "fixture_failed"
    assert (
        high_cost_result["fixture_checks"]["reported_fixture_cost_matches_declared"]
        is False
    )
    assert high_cost_result["empirical_checks"]["cost"] is None


def test_reported_fixture_call_overage_fails_fixture_validation() -> None:
    manifest = load_search_eval_manifest()
    openrouter_case = next(
        case for case in manifest.cases if case.id == "openrouter_equity_category_en"
    )
    overage_payload = deepcopy(openrouter_case.payload)
    overage_payload["usage"]["server_tool_use"]["web_search_requests"] = 99
    overage_case = replace(openrouter_case, payload=overage_payload)

    result = evaluate_manifest(replace(manifest, cases=(overage_case,)))[
        "fixture_validation"
    ]["results"][0]

    assert result["status"] == "fixture_failed"
    assert (
        result["fixture_checks"]["reported_fixture_call_count_matches_expected"] is False
    )
    assert result["empirical_checks"]["call_count"] is None


def test_source_date_metadata_does_not_claim_freshness() -> None:
    manifest = load_search_eval_manifest()
    direct_case = next(
        case for case in manifest.cases if case.id == "perplexity_equity_category_en"
    )
    payload_with_stale_dates = deepcopy(direct_case.payload)
    for item in payload_with_stale_dates["results"]:
        item["date"] = "2000-01-01"
        item["last_updated"] = "2000-01-01"
    case_with_stale_dates = replace(direct_case, payload=payload_with_stale_dates)
    mutated_manifest = replace(manifest, cases=(case_with_stale_dates,))

    result = evaluate_manifest(mutated_manifest)["fixture_validation"]["results"][0]

    assert result["fixture_checks"]["source_date_field_shape"] is True
    assert result["empirical_checks"]["freshness"] is None
    assert result["status"] == "unproven"


def test_outage_preservation_requires_explicit_prior_context() -> None:
    manifest = load_search_eval_manifest()
    outage_case = next(case for case in manifest.cases if case.id == "perplexity_outage")
    payload_without_context = deepcopy(outage_case.payload)
    payload_without_context.pop("prior_result_context")

    case_without_context = replace(outage_case, payload=payload_without_context)
    evidence = normalize_case(case_without_context, rubric=manifest.rubric)
    result = evaluate_manifest(replace(manifest, cases=(case_without_context,)))[
        "fixture_validation"
    ]["results"][0]

    assert evidence.prior_result_context is None
    assert result["status"] == "fixture_failed"
    assert result["fixture_checks"]["outage_fixture_has_context_precondition"] is False
    assert result["empirical_checks"]["outage_behavior"] is None


def test_synthetic_provider_fixtures_never_pass_empirical_criteria() -> None:
    report = evaluate_manifest(load_search_eval_manifest())
    provider_results = [
        result
        for result in report["fixture_validation"]["results"]
        if result["provider"] is not None
    ]

    assert all(result["status"] == "unproven" for result in provider_results)
    assert all(
        all(value is None for value in result["empirical_checks"].values())
        for result in provider_results
    )


def test_report_defers_activation_without_real_quality_or_latency_evidence() -> None:
    report = evaluate_manifest(load_search_eval_manifest())

    assert report["fixture_validation"]["validated_cases"] == 12
    assert report["fixture_validation"]["failed_cases"] == 0
    assert report["empirical_evidence"] == {
        "interpretation": (
            "No independently captured provider or runtime observations are "
            "present. Every empirical criterion remains unproven."
        ),
        "passed": 0,
        "failed": 0,
        "unproven": 12,
    }
    expected_fixture_checks = {
        "citation_shape_well_formed",
        "configured_timeout_bounded",
        "control_declares_zero_search",
        "declared_fixture_cost_within_provisional_bound",
        "declared_runtime_effects_safe",
        "expected_call_count_bounded",
        "outage_fixture_has_context_precondition",
        "reported_fixture_call_count_matches_expected",
        "reported_fixture_cost_matches_declared",
        "result_shape_bounded",
        "source_date_field_shape",
        "sources_labeled_untrusted",
        "term_coverage_fixture",
    }
    expected_empirical_checks = set(load_search_eval_manifest().rubric.criteria)
    for result in report["fixture_validation"]["results"]:
        assert set(result["fixture_checks"]) == expected_fixture_checks
        assert set(result["empirical_checks"]) == expected_empirical_checks
        assert False not in result["fixture_checks"].values()
        assert all(value is None for value in result["empirical_checks"].values())
        assert result["unproven_empirical_checks"]
        assert set(result["fixture_input"]) == {
            "declared_cost_usd",
            "declared_latency_ms",
            "evidence_kind_label",
            "expected_search_calls",
        }
        assert set(result["normalized_fixture"]) == {
            "citation_count",
            "configured_timeout_ms",
            "reported_cost_usd",
            "reported_search_calls",
            "result_count",
            "source_dates_present",
        }
        assert set(result["runtime_observation"]) == {
            "fallback_code",
            "policy_effects",
            "present",
            "prior_result_context_present",
            "runnable_candidates",
        }
        assert result["runtime_observation"]["present"] is False
    assert report["live_calls_made"] == 0
    assert report["activation_ready"] is False
    assert report["recommendation"] == "defer"
    assert report["recommendation_basis"] == "missing_empirical_evidence"
    assert set(report["remaining_gates"]) == {
        "#241 typed asset discovery route integrated",
        "approved public citation/context schema",
        "explicit founder activation",
        "founder-approved rubric thresholds",
        "locked OpenRouter model and token budget",
        "real citation and relevance evidence",
        "real end-to-end cost evidence",
        "real freshness evidence",
        "real outage context-preservation evidence",
        "real prompt-injection resistance evidence",
        "real provider latency evidence",
    }
    assert (
        report["documentation_summary"]["providers"]["perplexity_direct"][
            "source_date_metadata"
        ]
        == "documented"
    )
    assert (
        report["documentation_summary"]["providers"]["openrouter_web_search"][
            "source_date_metadata"
        ]
        == "not_guaranteed_by_annotation_schema"
    )
    assert (
        report["documentation_summary"]["providers"]["openrouter_web_search"][
            "cost_shape"
        ]
        == "search_fee_plus_llm_tokens"
    )
    assert (
        report["documentation_summary"]["providers"]["perplexity_direct"]["call_shape"]
        == "one_request_per_probe"
    )
    assert (
        report["documentation_summary"]["providers"]["openrouter_web_search"][
            "call_shape"
        ]
        == "model_decides_zero_to_many_calls"
    )
    assert (
        report["documentation_summary"]["providers"]["openrouter_web_search"][
            "comparison_configuration"
        ]["model_selection_status"]
        == "unresolved_founder_gate"
    )
    injection_results = [
        result
        for result in report["fixture_validation"]["results"]
        if result["kind"] == "injection"
    ]
    assert all(
        result["fixture_checks"]["sources_labeled_untrusted"] is True
        for result in injection_results
    )
    assert all(
        result["fixture_checks"]["declared_runtime_effects_safe"] is None
        for result in injection_results
    )
    assert all(
        result["empirical_checks"]["injection_resistance"] is None
        for result in injection_results
    )
    outage_results = [
        result
        for result in report["fixture_validation"]["results"]
        if result["kind"] == "outage"
    ]
    assert all(
        result["fixture_checks"]["outage_fixture_has_context_precondition"] is True
        for result in outage_results
    )
    assert all(
        result["empirical_checks"]["outage_behavior"] is None for result in outage_results
    )
    assert "README" in report["rollback_boundary"]


def test_decision_packet_keeps_public_schema_approval_as_a_gate() -> None:
    report = evaluate_manifest(load_search_eval_manifest())

    assert "approved public citation/context schema" in report["remaining_gates"]


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
